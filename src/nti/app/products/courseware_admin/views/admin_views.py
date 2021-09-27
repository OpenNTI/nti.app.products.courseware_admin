#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component

from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import site as current_site
from zope.component.hooks import getSite

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.interfaces import ICourseAdminsContainer,\
    CourseAdminSummary

from nti.app.users.views.view_mixins import AbstractEntityViewMixin
from nti.app.users.views.view_mixins import UsersCSVExportMixin

from nti.common.string import is_true

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import CourseRolesSynchronized

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog

from nti.contenttypes.courses.sharing import update_package_permissions

from nti.contenttypes.courses.utils import get_course_instructors

from nti.coremetadata.interfaces import IDeactivatedUser
from nti.coremetadata.interfaces import IX_LASTSEEN_TIME

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser

from nti.dataserver.metadata.index import IX_CREATEDTIME
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.users.index import IX_ALIAS
from nti.dataserver.users.index import IX_REALNAME
from nti.dataserver.users.index import IX_DISPLAYNAME

from nti.dataserver.users.index import get_entity_catalog

from nti.dataserver.users.users import User

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.interfaces import ILinkExternalHrefOnly

from nti.links.links import Link

from nti.links.externalization import render_link

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
TOTAL = StandardExternalFields.TOTAL

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             name='AuditUsageInfo',
             permission=nauth.ACT_NTI_ADMIN,
             context=ICourseCatalog)
class CatalogUsageSummary(AbstractAuthenticatedView):

    def __call__(self):
        items = {}

        provenance_link_cache = {}

        for catalog_entry in self.context.iterCatalogEntries():

            # We want to indicate what catalog each course comes from
            # for this admin view. We look for the ICourseCatalog and render a link to it.
            # We can't render links to the global catalog so if a course
            # is global we omit the provenance
            provenance = None
            owner_catalog = find_interface(catalog_entry, ICourseCatalog)

            if not IGlobalCourseCatalog.providedBy(owner_catalog):
                provenance = provenance_link_cache.get(owner_catalog, None)
                if provenance is None:
                    owner_catalog_link = Link(owner_catalog)
                    interface.alsoProvides(owner_catalog_link, ILinkExternalHrefOnly)
                    provenance = render_link(owner_catalog_link)
                    provenance_link_cache[owner_catalog] = provenance

            course_summary = {}
            course_summary['provenance'] = provenance

            roles = {}

            course = ICourseInstance(catalog_entry)

            prm = IPrincipalRoleManager(course)
            for role in (RID_TA, RID_INSTRUCTOR, RID_CONTENT_EDITOR,):
                pids = (pid for (pid, setting) in prm.getPrincipalsForRole(role)
                        if setting == Allow)
                pids = [pid for pid in pids if User.get_user(pid) is not None
                        and not IDeactivatedUser.providedBy(User.get_user(pid))]
                roles[role] = pids

            course_summary['roles'] = roles

            items[catalog_entry.ntiid] = course_summary

        result = LocatedExternalDict()
        result.__parent__ = self.context
        result.__name__ = self.request.view_name
        result[ITEMS] = items
        result[ITEM_COUNT] = result[TOTAL] = len(items)
        return result


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name='UpdateCourseContentPermissions',
               permission=nauth.ACT_NTI_ADMIN)
class CourseContentPermissionUpdateView(AbstractAuthenticatedView):
    """
    Update the package permissions for a course.
    """

    def __call__(self):
        packages = get_course_packages(self.context)
        update_package_permissions(self.context, added=packages)
        return hexc.HTTPNoContent()


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name='GetCourse',
               permission=nauth.ACT_READ)
class GetCourseView(AbstractAuthenticatedView):

    def readInput(self):
        result = CaseInsensitiveDict(self.request.params)
        return result

    def checkAccess(self):
        if not is_admin_or_site_admin(self.remoteUser):
            raise hexc.HTTPForbidden()

    def __call__(self):
        self.checkAccess()
        values = self.readInput()
        admin = values.get('admin') or values.get('adminLevel')
        if not admin:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Must provide an admin level."),
                             },
                             None)

        name = values.get('name') or values.get('key')
        if not name:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Must provide a course key/name."),
                             },
                             None)

        site = values.get('site')
        names = get_component_hierarchy_names()
        if site:
            site = site.lower()
            if site not in names:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid site."),
                                 },
                                 None)
            else:
                sites = (get_host_site(site),)
        else:
            sites = [get_host_site(x) for x in names]

        section = values.get('section')
        for site in sites:
            with current_site(site):
                catalog = component.queryUtility(ICourseCatalog)
                if catalog is None:
                    continue
                try:
                    course = catalog[admin][name]
                    if section:
                        course = course.SubInstances[section]
                    return course
                except (AttributeError, KeyError):
                    pass
        raise hexc.HTTPNotFound()


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name='GetCatalogEntry',
               permission=nauth.ACT_READ)
class GetCatalogEntryView(GetCourseView):

    def __call__(self):
        result = super(GetCatalogEntryView, self).__call__()
        return ICourseCatalogEntry(result)


@view_config(name='SyncInstructors')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseInstance,
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN)
class SyncCourseInstructorsView(AbstractAuthenticatedView):

    def validate(self, name):
        user = User.get_user(name)
        return IUser.providedBy(user)

    def __call__(self):
        course = ICourseInstance(self.context)
        # get and validate role instructors
        role_inst = {
            x.lower() for x in get_course_instructors(course) if self.validate(x)
        }
        # get course instructors
        # pylint: disable=not-an-iterable
        course_insts = {
            IPrincipal(x).id for x in course.instructors or ()
        }
        course_insts = {x.lower() for x in course_insts if self.validate(x)}

        # all instructors
        instructors = course_insts.union(role_inst)
        if not instructors:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Course does not have valid instructors."),
                             },
                             None)

        # reset all TA/Instructor roles while saving valid mappings
        # pylint: disable=too-many-function-args
        roles = {}
        manager = IPrincipalRoleManager(course)
        for role, principal, setting in list(manager.getPrincipalsAndRoles() or ()):
            if role in (RID_TA, RID_INSTRUCTOR):
                pid = getattr(principal, 'id', principal).lower()
                if pid in instructors and setting is Allow:
                    roles[pid] = role
                manager.unsetRoleForPrincipal(role, principal)

        # set course instructors
        course.instructors = tuple(
            IPrincipal(User.get_user(x)) for x in sorted(instructors)
        )

        # set course roles
        for principal in course.instructors:
            pid = principal.id.lower()
            role = roles.get(pid, RID_INSTRUCTOR)
            manager.assignRoleToPrincipal(role, pid)

        # notify
        notify(CourseRolesSynchronized(course))
        return hexc.HTTPNoContent()


@view_config(name='SyncInstructors')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseCatalogEntry,
               request_method='POST',
               permission=nauth.ACT_NTI_ADMIN)
class SyncCatalogEntryInstructorsView(SyncCourseInstructorsView):
    pass

@view_config(context=ICourseAdminsContainer)
@view_defaults(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             permission=nauth.ACT_CONTENT_EDIT)
class CourseAdminsGetView(AbstractEntityViewMixin):
    """
    Return all course admins (instructors and editors of any course in the site)
    Filter by only instructors or only editors if requested
    """
    
    _ALLOWED_SORTING = AbstractEntityViewMixin._ALLOWED_SORTING + (IX_LASTSEEN_TIME,)
    _NUMERIC_SORTING = AbstractEntityViewMixin._NUMERIC_SORTING + (IX_LASTSEEN_TIME,)
    
    @Lazy
    def filterInstructors(self):
        # pylint: disable=no-member
        return is_true(self.params.get('filterInstructors', 'False'))
    
    @Lazy
    def filterEditors(self):
        # pylint: disable=no-member
        return is_true(self.params.get('filterEditors', 'False'))
    
    def get_externalizer(self, unused_entity):
        return 'admin-summary'

    @Lazy
    def sortMap(self):
        return {
            IX_ALIAS: get_entity_catalog(),
            IX_REALNAME: get_entity_catalog(),
            IX_DISPLAYNAME: get_entity_catalog(),
            IX_CREATEDTIME: get_metadata_catalog(),
            IX_LASTSEEN_TIME: get_metadata_catalog(),
        }

    def get_entity_intids(self, site=None):
        course_admin_intids = self.context.course_admin_intids(filterInstructors=self.filterInstructors, filterEditors=self.filterEditors)
        for doc_id in course_admin_intids:
            yield doc_id
    
    def _batch_selector(self, user):
        return CourseAdminSummary(user)
    
    def _post_numeric_sorting(self, ext_res, sort_on, reverse):
        """
        Sorts the `Items` in the result dict in-place, using the sort_on
        and reverse params.
        """
        ext_res[ITEMS] = sorted(ext_res[ITEMS],
                                key=lambda x: getattr(x.user, sort_on, 0),
                                reverse=reverse)

    def __call__(self):
        return self._do_call()
    
@view_config(context=ICourseAdminsContainer)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               accept='text/csv',
               permission=nauth.ACT_CONTENT_EDIT)
class CourseAdminsCSVView(CourseAdminsGetView,
                       UsersCSVExportMixin):

    def _get_filename(self):
        return u'course_admins.csv'

    def __call__(self):
        self.check_access()
        return self._create_csv_response()


@view_config(context=ICourseAdminsContainer)
@view_defaults(route_name='objects.generic.traversal',
               request_method='POST',
               renderer='rest',
               permission=nauth.ACT_CONTENT_EDIT,
               request_param='format=text/csv')
class CourseAdminsCSVPOSTView(CourseAdminsCSVView, 
                           ModeledContentUploadRequestUtilsMixin):
    
    def readInput(self):
        if self.request.POST:
            result = {'usernames': self.request.params.getall('usernames') or []}
        elif self.request.body:
            result = super(CourseAdminsCSVPOSTView, self).readInput()
        else:
            result = self.request.params
        return CaseInsensitiveDict(result)
    
    @Lazy
    def _params(self):
        return self.readInput()

    def _get_result_iter(self):
        usernames = self._params.get('usernames', ())
        if not usernames:
            return super(CourseAdminsCSVPOSTView, self)._get_result_iter()
        intids = component.getUtility(IIntIds)
        result = []
        for username in usernames:
            user = User.get_user(username)
            if user is None:
                continue
            user_intid = intids.queryId(user)
            if user_intid is None:
                continue
            # Validate the user is in the original result set
            if user_intid in self.filtered_intids:
                result.append(user) 
        return result
