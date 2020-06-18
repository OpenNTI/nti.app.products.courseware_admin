#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time
import shutil
import gevent
import functools

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.event import notify

from zope.security.interfaces import IPrincipal

from zope.security.permission import allPermissions

from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.interfaces import IRolePermissionManager

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICoursesCatalogCollection

from nti.app.products.courseware.views import raise_error

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.views import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin.views import VIEW_COURSE_SUGGESTED_TAGS

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.base._compat import text_

from nti.common.string import is_true

from nti.coremetadata.interfaces import IMarkedForDeletion

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.creator import create_course
from nti.contenttypes.courses.creator import install_admin_level
from nti.contenttypes.courses.creator import create_course_subinstance

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSubInstances
from nti.contenttypes.courses.interfaces import CourseRolesUpdatedEvent
from nti.contenttypes.courses.interfaces import CourseRolesSynchronized
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import CourseInstanceRemovedEvent
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import CourseAlreadyExistsException

from nti.contenttypes.courses.sharing import add_principal_to_course_content_roles

from nti.contenttypes.courses.subscribers import remove_enrollment_records
from nti.contenttypes.courses.subscribers import unindex_enrollment_records

from nti.contenttypes.courses.utils import get_course_tags
from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import deny_instructor_access_to_course
from nti.contenttypes.courses.utils import grant_instructor_access_to_course
from nti.contenttypes.courses.utils import remove_principal_from_course_content_roles

from nti.coremetadata.interfaces import IUser

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin, ROLE_SITE_ADMIN
from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import IDataserverTransactionRunner

from nti.externalization.externalization import to_external_object

from nti.externalization.internalization import find_factory_for

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from nti.zodb.containers import time_to_64bit_int

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='GET',
             permission=nauth.ACT_CONTENT_EDIT)
class AdminLevelsGetView(AbstractAuthenticatedView):
    """
    Fetch the administrative levels under the course catalog.
    """

    def readInput(self):
        return CaseInsensitiveDict(self.request.params)

    def __call__(self):
        data = self.readInput()
        # This is typically fetched when creating courses, therefore we'll
        # want to return the admin levels from this site, which this user
        # should have access to insert into (but may not for parent site
        # admin levels). Plus, parent site admins would not want to create
        # courses in the parent site from a sub-site; that would be confusing.
        parents = is_true(data.get('parents', 'false'))
        result = LocatedExternalDict()
        # pylint: disable=no-member
        admin_levels = self.context.get_admin_levels(parents)
        # TODO: Now that we allow dupe admin level names, we probably need
        # to return list here with appropriate links.
        result[ITEMS] = {
            x: to_external_object(y, name='summary')
            for x, y in admin_levels.items()
        }
        result[ITEM_COUNT] = result[TOTAL] = len(admin_levels)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='POST',
             permission=nauth.ACT_CONTENT_EDIT)
class AdminLevelsPostView(AbstractAuthenticatedView,
                          ModeledContentUploadRequestUtilsMixin):
    """
    A view to create a new ICourseAdministrativeLevel, given as a 'key' param.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(AdminLevelsPostView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_admin_key(self, values):
        result = values.get('name') \
              or values.get('level') \
              or values.get('key')
        if not result:
            raise_error({
                'message': _(u'Must supply admin level key.'),
                'code': 'InvalidAdminKey',
            })
        return result

    def _insert(self, context, admin_key):
        # For child sites, we'll want to allow creating admin levels
        # that may be duplicates of parent admin levels. This allows
        # child site admins to create structure in their site.
        admin_levels = context.get_admin_levels(parents=False)
        if admin_key in admin_levels:
            raise_error({
                'message': _(u'Admin key already exists.'),
                'code': 'DuplicateAdminKey',
            })
        result = install_admin_level(admin_key, catalog=self.context)
        return result

    @property
    def _catalog(self):
        return self.context

    def __call__(self):
        values = self.readInput()
        admin_key = self._get_admin_key(values)
        new_level = self._insert(self._catalog, admin_key)
        logger.info("Created new admin level (%s)", admin_key)
        return to_external_object(new_level, name="summary")


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=IHostPolicyFolder,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='POST',
             permission=nauth.ACT_CONTENT_EDIT)
class SiteAdminLevelsPostView(AdminLevelsPostView):

    @Lazy
    def _catalog(self):
        with current_site(self.context):
            catalog = component.queryUtility(ICourseCatalog)
            if catalog is None:
                raise_error({
                    'message': _(u'Course catalog is missing.'),
                    'code': 'MissingCourseCatalog',
                })
            return catalog


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseAdministrativeLevel,
             request_method='DELETE',
             permission=nauth.ACT_CONTENT_EDIT)
class AdminLevelsDeleteView(UGDDeleteView):
    """
    Currently only allow deletion of admin levels if it is empty.
    """

    def _do_delete_object(self, theObject):
        del theObject.__parent__[theObject.__name__]
        return theObject

    def __call__(self):
        if len(self.context):
            raise_error({
                'message': _(u'Cannot delete admin level with underlying objects.'),
                'code': 'CannotDeleteAdminLevel',
            })
        result = super(AdminLevelsDeleteView, self).__call__()
        logger.info('Deleted %s', self.context)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseAdministrativeLevel,
             request_method='POST',
             permission=nauth.ACT_CONTENT_EDIT)
class CreateCourseView(AbstractAuthenticatedView,
                       ModeledContentUploadRequestUtilsMixin):
    """
    Creates a basic course. The finished product will be in preview mode and
    non-public. We'll have a GUID for the course catalog entry NTIID.

    The course name/key/ProviderUniqueId is essentially an additional
    classifier for the course (e.g. UCOL 1002). We also happened to use this
    as a the course key within the admin level. This `ProviderUniqueID` field
    and the course `title` are required.

    We'll also continue creating our course (incrementing the key) until we
    succeed.
    """

    DEFAULT_FACTORY_MIMETYPE = 'application/vnd.nextthought.courses.courseinstance'

    def readInput(self, value=None):
        if self.request.body:
            values = super(CreateCourseView, self).readInput(value)
        else:
            values = self.request.params
        values = dict(values)
        # Can't be CaseInsensitive with internalization
        if MIMETYPE not in values:
            values[MIMETYPE] = self.DEFAULT_FACTORY_MIMETYPE
        return values

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def _course_classifier(self):
        # pylint: disable=no-member
        values = self._params
        result = values.get('ProviderUniqueID')
        if not result:
            raise_error({'field': 'ProviderUniqueID',
                         'message': _(u'Missing ProviderUniqueID'),
                         'code': 'RequiredMissing'})
        return result

    def _post_create(self, course):
        catalog_entry = ICourseCatalogEntry(course)
        fill_entry_from_legacy_json(catalog_entry, self._params,
                                    notify=True, delete=False)
        catalog_entry.Preview = True
        interface.alsoProvides(course, INonPublicCourseInstance)
        interface.alsoProvides(catalog_entry, INonPublicCourseInstance)
        notify(CourseInstanceAvailableEvent(course))
        return catalog_entry

    def _generate_key(self):
        return text_(time_to_64bit_int(time.time()))

    def _get_course_key_iter(self):
        base_key = self._course_classifier or self._generate_key()
        yield base_key
        idx = 0
        while True:
            yield '%s.%s' % (base_key, idx)
            idx += 1

    def _create_course(self, admin_level):
        """
        Iterating over our ``_get_course_key_iter`` until we have
        successfully created a course.
        """
        key = course = None
        factory = find_factory_for(self._params) or ContentCourseInstance
        course_key_iter = self._get_course_key_iter()
        for key in course_key_iter:
            try:
                # pylint: disable=no-member
                course = create_course(admin_level,
                                       key,
                                       writeout=False,
                                       strict=True,
                                       creator=self.remoteUser.username,
                                       factory=factory)
                break
            except CourseAlreadyExistsException:
                pass
        return course, key

    def _do_call(self):
        admin_level = self.context.__name__
        course, key = self._create_course(admin_level)
        entry = self._post_create(course)
        logger.info('Creating course (%s) (admin=%s) (ntiid=%s) (key=%s)',
                    self._course_classifier, admin_level, entry.ntiid, key)
        return course


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseSubInstances,
             request_method='POST',
             permission=nauth.ACT_CONTENT_EDIT)
class CreateCourseSubinstanceView(CreateCourseView):
    """
    Creates a section course.
    """

    @Lazy
    def parent_course(self):
        return find_interface(self.context, ICourseInstance)

    @Lazy
    def copy_roles(self):
        # pylint: disable=no-member
        result = self._params.get('copy_roles') \
              or self._params.get('copy_instructor') \
              or self._params.get('copy_instructors')
        return is_true(result)

    def do_copy_roles(self, course):
        # pylint: disable=too-many-function-args,no-member
        if self.copy_roles:
            prm = IPrincipalRoleManager(course)
            parent_course = get_parent_course(course)
            for prin in parent_course.instructors or ():
                user = IUser(prin, None)
                if user is None:
                    continue
                prm.assignRoleToPrincipal(RID_INSTRUCTOR, prin.id)
                course.instructors += (prin,)
                grant_instructor_access_to_course(user, course)
            for editor_prin in get_course_editors(parent_course) or ():
                user = IUser(editor_prin, None)
                if user is None:
                    continue
                prm.assignRoleToPrincipal(RID_CONTENT_EDITOR, editor_prin.id)
                add_principal_to_course_content_roles(user, course)
            notify(CourseRolesSynchronized(course))

    def _post_create(self, course):
        self.do_copy_roles(course)
        return super(CreateCourseSubinstanceView, self)._post_create(course)

    def _create_course(self, parent_course):  # pylint: disable=arguments-differ
        base_key = self._course_classifier
        course = None
        try:
            # pylint: disable=no-member
            course = create_course_subinstance(parent_course,
                                               base_key,
                                               writeout=False,
                                               strict=True,
                                               creator=self.remoteUser.username)
        except CourseAlreadyExistsException:
            raise_error({'message': _(u'Course already exists.'),
                         'code': 'CourseAlreadyExists'},
                         factory=hexc.HTTPConflict)
        return course

    def _do_call(self):
        course = self._create_course(self.parent_course)
        entry = self._post_create(course)
        logger.info('Creating course section (%s) (parent=%s) (ntiid=%s) (key=%s)',
                    self._course_classifier,
                    ICourseCatalogEntry(self.parent_course).ntiid,
                    entry.ntiid,
                    course.__name__)
        return course


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE')
class DeleteCourseView(AbstractAuthenticatedView):
    """
    Delete a course instance. Since these objects may contain a massive tree
    of objects, this can be transactionally expensive. Therefore, we spawn a
    greenlet that will split this up into multiple transactions.
    """

    @Lazy
    def site_name(self):
        return getattr(getSite(), '__name__', '')

    def _do_delete_course(self, course_ntiid):
        course = find_object_with_ntiid(course_ntiid)
        entry = ICourseCatalogEntry(course)
        folder = IHostPolicyFolder(course)
        logger.info("[%s] Deleting course (%s) (%s)",
                    self.site_name,
                    entry.ntiid,
                    self.remoteUser)
        del course.__parent__[course.__name__]
        notify(CourseInstanceRemovedEvent(course, entry, folder))
        try:
            logger.info('[%s] Deleting path (%s)',
                        self.site_name,
                        course.root.absolute_path)
            shutil.rmtree(course.root.absolute_path, ignore_errors=True)
        except AttributeError:
            pass

    def _unenroll_all(self, entry_ntiid, course):
        dropped_records = remove_enrollment_records(course)
        unindex_enrollment_records(course)
        logger.info("[%s] Dropped users from course during course deletion (%s) (%s)",
                    self.site_name,
                    len(dropped_records),
                    entry_ntiid)

    def _deny_site_admins(self, course):
        rpm = IRolePermissionManager(course)
        for permission_id in allPermissions(None):
            rpm.denyPermissionToRole(permission_id, ROLE_SITE_ADMIN.id)

    def _remove_course_admins(self, entry_ntiid, course):
        # XXX: We need to ensure this works correctly if we are on a course
        # subinstance. We do not want admins to lose access when the section
        # course goes away, and the user is still an admin of the parent
        # course.
        role_manager = IPrincipalRoleManager(course)
        def remove_access(prin, role_id, is_instructor=False):
            user = IUser(prin)
            principal_id = IPrincipal(user).id
            role_manager.unsetRoleForPrincipal(role_id, principal_id)
            if is_instructor:
                deny_instructor_access_to_course(user, course)
                remove_principal_from_course_content_roles(user,
                                                           course,
                                                           unenroll=True)

        for instructor in course.instructors:
            remove_access(instructor, RID_INSTRUCTOR, is_instructor=True)
        course.instructors = ()

        for editor in get_course_editors(course):
            remove_access(editor, RID_CONTENT_EDITOR, is_instructor=False)

        notify(CourseRolesUpdatedEvent(course))
        logger.info("[%s] Removed course admins during course deletion (%s)",
                    self.site_name,
                    entry_ntiid)

    def _remove_user_access(self, entry_ntiid, course):
        self._deny_site_admins(course)
        self._remove_course_admins(entry_ntiid, course)
        self._unenroll_all(entry_ntiid, course)

    def _delete_course_data(self, course_ntiids):
        """
        Performs the actual work of deleting the course. This could be
        split into more transactions if needed.

        The first priority is removing access (admins, instructors, enrolled
        users). That should effectively cut off access to everyone except NT
        admins (and make auxiliary API like search work as expected). After
        that, we're left with cleaning up content and db cruft.

        - delete course
        """
        for entry_ntiid, course_ntiid in course_ntiids:
            logger.info("[%s] Deleting course data (%s)",
                        self.site_name, entry_ntiid)
            delete_func = functools.partial(self._do_delete_course, course_ntiid)

            tx_runner = component.getUtility(IDataserverTransactionRunner)
            for func in (delete_func,):
                tx_runner(func, retries=5, sleep=0.1, site_names=(self.site_name,))
            logger.info("[%s] Finished course deletion (%s)",
                        self.site_name,
                        entry_ntiid)

    def _delete_course(self, course):
        """
        Marks the course as deleted and remove user access to this course
        (except for NT admins). We then spawn a greenlet that will actually
        perform the course deletion steps, which should take take of the rest
        of the course data (outline, completion data, etc).
        """
        entry = ICourseCatalogEntry(course)
        logger.info('[%s] Marking course deleted (%s) (%s)',
                    self.site_name, entry.ntiid, self.remoteUser)
        courses = []
        # Make sure we operate on subinstances first
        courses.extend(get_course_subinstances(course) or ())
        courses.append(course)
        course_ntiids = []
        for course in courses:
            entry_ntiid = ICourseCatalogEntry(course).ntiid
            course_ntiid = to_external_ntiid_oid(course)
            course_ntiids.append((entry_ntiid, course_ntiid))

            self._remove_user_access(entry_ntiid, course)
            interface.alsoProvides(course, IMarkedForDeletion)
            interface.alsoProvides(course, IDeletedCourse)

        # Now commit the work we've done (or we've failed)
        # <commit>
        try:
            glet = gevent.spawn(self._delete_course_data, course_ntiids)
            glet.get()
        except:
            logger.exception("[%s] Error during course data deletion",
                             self.site_name)
            raise

    def _check_access(self):
        if not is_admin_or_content_admin_or_site_admin(self.remoteUser):
            raise_error({
                'message': _(u'Cannot delete course.'),
                'code': 'CannotDeleteCourse',
            })

    def __call__(self):
        self._check_access()
        # Do not go through the process if another tx beat us to it, unless we
        # are an NT admin.
        course = ICourseInstance(self.context)
        if     not IDeletedCourse.providedBy(course) \
            or is_admin(self.remoteUser):
            self._delete_course(course)
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=ICoursesCatalogCollection,
             name=VIEW_COURSE_SUGGESTED_TAGS,
             permission=nauth.ACT_READ)
class CourseSuggestedTagsView(AbstractAuthenticatedView,
                              BatchingUtilsMixin):
    """
    Get suggested course tags, optionally batched and filtered.
    The results are sorted by exact matches first, and then starting
    with the optional filter str.

    params
        filter - (optional) only include tags with this str
    """

    _DEFAULT_BATCH_SIZE = None
    _DEFAULT_BATCH_START = None

    def readInput(self):
        result = CaseInsensitiveDict(self.request.params)
        return result

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def include_str(self):
        # pylint: disable=no-member
        result = self._params.get('tag') \
              or self._params.get('filter')
        return result and result.lower()

    def sort_key(self, tag):
        return (tag != self.include_str,
                not tag.startswith(self.include_str),
                tag.lower())

    def __call__(self):
        result = LocatedExternalDict()
        # Only editors should use this for now
        tags = get_course_tags(filter_str=self.include_str,
                               filter_hidden=False)
        if self.include_str:
            tags = sorted(tags, key=self.sort_key)
        else:
            tags = sorted(tags, key=lambda x: x.lower())
        result[TOTAL] = len(tags)
        self._batch_items_iterable(result, tags)
        result[ITEM_COUNT] = len(tags)
        return result
