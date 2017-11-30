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

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site

from zope.event import notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ICoursesCatalogCollection

from nti.app.products.courseware.invitations.utils import create_course_invitation

from nti.app.products.courseware.views import raise_error

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.views import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin.views import VIEW_COURSE_SUGGESTED_TAGS

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.base._compat import text_

from nti.common.string import is_true

from nti.contenttypes.courses.courses import ContentCourseInstance

from nti.contenttypes.courses.creator import create_course
from nti.contenttypes.courses.creator import install_admin_level

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import CourseInstanceRemovedEvent
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import CourseAlreadyExistsException

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.contenttypes.courses.utils import get_course_tags

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.site.interfaces import IHostPolicyFolder

from nti.zodb.containers import time_to_64bit_int

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
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
        parents = is_true(data.get('parents', 'true'))
        result = LocatedExternalDict()
        admin_levels = self.context.get_admin_levels(parents)
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
    A view to create a new ICourseAdministrativeLevel, given as
    a 'key' param.
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

    def _insert(self, context, admin_key, parents=True):
        # Do not allow children levels to mask parent levels.
        admin_levels = context.get_admin_levels(parents)
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
        parents = is_true(values.get('parents', 'true'))
        admin_key = self._get_admin_key(values)
        new_level = self._insert(self._catalog, admin_key, parents)
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
    as a the course key within the admin level. This is not especially useful
    for the end-user to have to worry about. Therefore, it is optional in this
    view (auto-creating a GUID if necessary). We'll also continue creating our
    course (incrementing the key) until we succeed.
    """

    _COURSE_INSTANCE_FACTORY = ContentCourseInstance

    def readInput(self, value=None):
        if self.request.body:
            values = super(CreateCourseView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def _course_classifier(self):
        values = self._params
        result = values.get('key') \
              or values.get('name') \
              or values.get('course') \
              or values.get('ProviderUniqueId')
        if not result:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'field': 'password',
                                 'message': _(u'Missing password'),
                                 'code': 'RequiredMissing'
                             },
                             None)
        return result

    def _post_create(self, course):
        catalog_entry = ICourseCatalogEntry(course)
        catalog_entry.Preview = True
        catalog_entry.ProviderUniqueID = self._course_classifier
        interface.alsoProvides(course, INonPublicCourseInstance)
        interface.alsoProvides(catalog_entry, INonPublicCourseInstance)
        create_course_invitation(course, is_generic=True)
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
        course = None
        course_key_iter = self._get_course_key_iter()
        for key in course_key_iter:
            try:
                course = create_course(admin_level,
                                       key,
                                       writeout=False,
                                       strict=True,
                                       creator=self.remoteUser.username,
                                       factory=self._COURSE_INSTANCE_FACTORY)
                break
            except CourseAlreadyExistsException:
                pass
        return course, key

    def __call__(self):
        admin_level = self.context.__name__
        course, key = self._create_course(admin_level)
        entry = self._post_create(course)
        logger.info('Creating course (%s) (admin=%s) (ntiid=%s) (key=%s)',
                    self._course_classifier, admin_level, entry.ntiid, key)
        return course


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE')
class DeleteCourseView(AbstractAuthenticatedView):

    def __call__(self):
        if not is_admin_or_content_admin_or_site_admin(self.remoteUser):
            raise_error({
                'message': _(u'Cannot delete course.'),
                'code': 'CannotDeleteCourse',
            })
        course = ICourseInstance(self.context)
        entry = ICourseCatalogEntry(self.context)
        folder = IHostPolicyFolder(course)
        logger.info('Deleting course (%s)', entry.ntiid)
        try:
            shutil.rmtree(course.root.absolute_path, ignore_errors=True)
            logger.info('Deleting path (%s)', course.root.absolute_path)
        except AttributeError:
            pass
        del course.__parent__[course.__name__]
        notify(CourseInstanceRemovedEvent(course, entry, folder))
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

    _DEFAULT_BATCH_SIZE = 10
    _DEFAULT_BATCH_START = 0

    def readInput(self):
        result = CaseInsensitiveDict(self.request.params)
        return result

    @Lazy
    def _params(self):
        return self.readInput()

    @Lazy
    def include_str(self):
        return self._params.get('tag') \
            or self._params.get('filter')

    def sort_key(self, tag):
        return (
            tag != self.include_str,
            not tag.startswith(self.include_str),
            tag.lower()
        )

    def __call__(self):
        result = LocatedExternalDict()
        tags = get_course_tags(filter_str=self.include_str)
        if self.include_str:
            tags = sorted(tags, key=self.sort_key)
        else:
            tags = sorted(tags, key=lambda x: x.lower())
        result[TOTAL] = len(tags)
        self._batch_items_iterable(result, tags)
        result[ITEM_COUNT] = len(tags)
        return result
