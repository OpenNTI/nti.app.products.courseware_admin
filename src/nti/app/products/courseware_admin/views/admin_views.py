#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from requests.structures import CaseInsensitiveDict

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope import component

from zope.component.hooks import site as current_site

from zope.event import notify

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware_admin import MessageFactory as _

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import CourseRolesSynchronized

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.sharing import update_package_permissions

from nti.contenttypes.courses.utils import get_course_instructors

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.users import User

from nti.externalization.interfaces import StandardExternalFields

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


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
