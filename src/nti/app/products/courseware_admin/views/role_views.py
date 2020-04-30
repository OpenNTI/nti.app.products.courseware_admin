#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import csv
from io import BytesIO

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import lifecycleevent

from zope.cachedescriptors.property import Lazy

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import raise_error
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin import VIEW_COURSE_ROLES
from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.app.products.courseware_admin.mixins import RoleManageMixin
from nti.app.products.courseware_admin.mixins import EditorManageMixin
from nti.app.products.courseware_admin.mixins import InstructorManageMixin

from nti.app.products.courseware_admin.views.view_mixins import tx_string

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.index import get_enrollment_catalog

from nti.contenttypes.courses.interfaces import EDITOR
from nti.contenttypes.courses.interfaces import INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import RID_CONTENT_EDITOR

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import CourseEditorAddedEvent
from nti.contenttypes.courses.interfaces import CourseEditorRemovedEvent
from nti.contenttypes.courses.interfaces import CourseInstructorAddedEvent
from nti.contenttypes.courses.interfaces import CourseInstructorRemovedEvent

from nti.contenttypes.courses.sharing import add_principal_to_course_content_roles
from nti.contenttypes.courses.sharing import remove_principal_from_course_content_roles

from nti.contenttypes.courses.utils import is_enrolled, is_course_editor
from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors
from nti.contenttypes.courses.utils import deny_instructor_access_to_course
from nti.contenttypes.courses.utils import grant_instructor_access_to_course

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.site.site import get_component_hierarchy_names

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


def _get_external_users(users):
    """
    For these admin views, we'll want to return information about these users
    available to admins.
    """
    return [to_external_object(x, name='admin-summary') for x in users]


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_INSTRUCTORS,
             request_method='GET')
class CourseInstructorsView(AbstractAuthenticatedView, InstructorManageMixin):
    """
    Fetch all instructors for the given course.
    """

    def __call__(self):
        self.require_access(self.remoteUser, self.context)
        instructors = get_course_instructors(self.context)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = len(instructors)
        users = (User.get_user(x) for x in instructors)
        result[ITEMS] = _get_external_users(users)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_EDITORS,
             request_method='GET')
class CourseEditorsView(AbstractAuthenticatedView, EditorManageMixin):
    """
    Fetch all editors for the given course.
    """

    def __call__(self):
        self.require_access(self.remoteUser, self.context)
        editors = get_course_editors(self.context)
        result = LocatedExternalDict()
        result[ITEM_COUNT] = len(editors)
        users = (IUser(x) for x in editors)
        result[ITEMS] = _get_external_users(users)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_ROLES,
             request_method='GET')
class CourseRolesView(AbstractAuthenticatedView, RoleManageMixin):
    """
    Fetch all editors for the given course.
    """

    def __call__(self):
        self.require_access(self.remoteUser, self.context)
        editors = [IUser(x) for x in get_course_editors(self.context)]
        instructors = [User.get_user(x) for x in get_course_instructors(self.context)]
        result = LocatedExternalDict()
        result['roles'] = roles = dict()
        for data_seq, name in ((editors, 'editors'), (instructors, 'instructors')):
            roles[name] = items = dict()
            items[ITEM_COUNT] = len(data_seq)
            items[ITEMS] = _get_external_users(data_seq)
        return result


class AbstractRoleManagerView(AbstractAuthenticatedView,
                              ModeledContentUploadRequestUtilsMixin):
    """
    A base class for granting/denying user permissions to a course.

    params:
        user - the username of the person to add to the course role
    """

    def _edit_permissions(self, user):
        """
        Alters permission on the course for the given user.
        """
        raise NotImplementedError()

    def readInput(self, unused_value=None):
        if self.request.body:
            values = read_body_as_external_object(self.request)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_users(self):
        values = self.readInput()
        result = values.get('name') \
              or values.get('user') \
              or values.get('users')
        if not result and self.request.subpath:
            result = self.request.subpath[0]
        if not result:
            raise_error({
                'message': _(u"No users given."),
                'code': 'NoUsersGiven.',
            })
        try:
            result = result.split(',')
        except AttributeError:
            # List
            pass
        return result

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def entry_ntiid(self):
        return ICourseCatalogEntry(self.course).ntiid

    @Lazy
    def role_manager(self):
        return IPrincipalRoleManager(self.course)

    def __call__(self):
        # pylint: disable=no-member
        self.require_access(self.remoteUser, self.context)
        usernames = self._get_users()
        for username in usernames:
            username = username.strip()
            user = User.get_user(username)
            if not IUser.providedBy(user):
                raise_error({
                    'message': _(u"User does not exist."),
                    'code': 'UserDoesNotExist',
                })
            self._edit_permissions(user)
            notify(self.EVENT_FACTORY(user, self.course))

        if usernames:
            # re-indexing instructors/editors.
            lifecycleevent.modified(self.course)
        return hexc.HTTPNoContent()


class AbstractCourseGrantView(AbstractRoleManagerView):  # pylint: disable=abstract-method

    def grant_permission(self, user):
        # pylint: disable=no-member
        principal_id = IPrincipal(user).id
        self.role_manager.assignRoleToPrincipal(self.ROLE_ID, principal_id)
        logger.info('Granted user access to course (%s) (%s) (%s)',
                    user.username, self.ROLE_ID, self.entry_ntiid)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_INSTRUCTORS,
             request_method='POST')
class CourseInstructorsInsertView(AbstractCourseGrantView, InstructorManageMixin):
    """
    Insert new instructors for the given course. We do not accept
    TAs at this point.
    """

    ROLE_ID = RID_INSTRUCTOR
    EVENT_FACTORY = CourseInstructorAddedEvent

    def grant_permission(self, user):
        super(CourseInstructorsInsertView, self).grant_permission(user)
        prin = IPrincipal(user)
        # Idempotent
        if prin not in self.course.instructors:
            self.course.instructors += (prin,)
        grant_instructor_access_to_course(user, self.course)
    _edit_permissions = grant_permission


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_EDITORS,
             request_method='POST')
class CourseEditorsInsertView(AbstractCourseGrantView, EditorManageMixin):
    """
    Insert new editors for the given course.
    """

    ROLE_ID = RID_CONTENT_EDITOR
    EVENT_FACTORY = CourseEditorAddedEvent

    def grant_permission(self, user):
        super(CourseEditorsInsertView, self).grant_permission(user)
        add_principal_to_course_content_roles(user, self.course)
    _edit_permissions = grant_permission


class AbstractCourseDenyView(AbstractRoleManagerView):  # pylint: disable=abstract-method

    def deny_permission(self, user):
        principal_id = IPrincipal(user).id
        # Matches what we do during sync.
        # pylint: disable=no-member
        self.role_manager.unsetRoleForPrincipal(self.ROLE_ID, principal_id)
        logger.info('Removed user access to course (%s) (%s) (%s)',
                    user.username, self.ROLE_ID, self.entry_ntiid)


@view_config(name=VIEW_COURSE_INSTRUCTORS,
             request_method='DELETE')
@view_config(name=VIEW_COURSE_REMOVE_INSTRUCTORS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseInstance)
class CourseInstructorsRemovalView(AbstractCourseDenyView, InstructorManageMixin):
    """
    Remove instructor(s) for the given course.
    """

    ROLE_ID = RID_INSTRUCTOR
    EVENT_FACTORY = CourseInstructorRemovedEvent

    def deny_permission(self, user):
        super(CourseInstructorsRemovalView, self).deny_permission(user)
        to_remove = IPrincipal(user)
        instructors = self.course.instructors
        self.course.instructors = tuple(
            x for x in instructors if x != to_remove
        )
        deny_instructor_access_to_course(user, self.course)
    _edit_permissions = deny_permission


@view_config(name=VIEW_COURSE_EDITORS,
             request_method='DELETE')
@view_config(name=VIEW_COURSE_REMOVE_EDITORS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseInstance)
class CourseEditorsRemovalView(AbstractCourseDenyView, EditorManageMixin):
    """
    Remove editor(s) for the given course.
    """

    ROLE_ID = RID_CONTENT_EDITOR
    EVENT_FACTORY = CourseEditorRemovedEvent

    def deny_permission(self, user):
        super(CourseEditorsRemovalView, self).deny_permission(user)
        if      IPrincipal(user) not in self.course.instructors \
            and not is_enrolled(self.course, user):
            # If not instructor and not enrolled, remove content access.
            remove_principal_from_course_content_roles(user,
                                                       self.course,
                                                       unenroll=True)
    _edit_permissions = deny_permission


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             name=VIEW_COURSE_ROLES,
             request_method='PUT')
class CourseRolesUpdateView(AbstractRoleManagerView, RoleManageMixin):
    """
    A view to update all course roles in a single API call. This looks for
    a `roles` param, containing `instructors` and `editors` (for our current
    two roles). Each entry will contain a list of usernames of users in that
    roles. Usernames not in those lists will be removed from those roles if
    currently in them. An empty list will remove all users from those roles.
    """

    def deny_permission(self, role_id, user):
        principal_id = IPrincipal(user).id
        # Matches what we do during sync.
        # pylint: disable=no-member
        self.role_manager.unsetRoleForPrincipal(role_id, principal_id)
        logger.info('Removed user access to course (%s) (%s) (%s)',
                    user.username, role_id, self.entry_ntiid)

    def grant_permission(self, role_id, user):
        # pylint: disable=no-member
        principal_id = IPrincipal(user).id
        self.role_manager.assignRoleToPrincipal(role_id, principal_id)
        logger.info('Granted user access to course (%s) (%s) (%s)',
                    user.username, role_id, self.entry_ntiid)

    def maybe_remove_user_from_content_roles(self, user):
        # If not editor, instructor, and enrollmed, remove content access.
        prin = IPrincipal(user)
        if      prin not in self.course.instructors \
            and not is_course_editor(self.course, user) \
            and not is_enrolled(self.course, user):
            remove_principal_from_course_content_roles(user,
                                                       self.course,
                                                       unenroll=True)

    @Lazy
    def _roles(self):
        return self.readInput().get('roles')

    def _get_usernames(self, usernames):
        """
        Validate given usernames
        """
        result = set()
        for username in usernames:
            username = username.strip()
            user = User.get_user(username)
            if not IUser.providedBy(user):
                raise_error({
                    'message': _(u"User does not exist."),
                    'code': 'UserDoesNotExist',
                })
            result.add(username)
        return result

    def update_instructors(self, input_instructor_usernames):
        input_instructor_usernames = self._get_usernames(input_instructor_usernames)
        current_instructors = set(get_course_instructors(self.course))
        instructors_to_add = input_instructor_usernames - current_instructors
        instructors_to_remove = current_instructors - input_instructor_usernames
        for to_add in instructors_to_add:
            user = User.get_user(to_add)
            self.grant_permission(RID_INSTRUCTOR, user)
            grant_instructor_access_to_course(user, self.course)
            notify(CourseInstructorAddedEvent(user, self.course))
        for to_remove in instructors_to_remove:
            user = User.get_user(to_remove)
            self.deny_permission(RID_INSTRUCTOR, user)
            deny_instructor_access_to_course(user, self.course)
            self.maybe_remove_user_from_content_roles(user)
            notify(CourseInstructorRemovedEvent(user, self.course))
        logger.info("Updating course instructors (%s) (added=%s) (removed=%s)",
                    self.entry_ntiid,
                    instructors_to_add,
                    instructors_to_remove)
        self.course.instructors = tuple(IPrincipal(User.get_user(x)) for x in input_instructor_usernames)

    def update_editors(self, input_editor_usernames):
        input_editor_usernames = self._get_usernames(input_editor_usernames)
        current_editors = set(x.id for x in get_course_editors(self.course))
        editors_to_add = input_editor_usernames - current_editors
        editors_to_remove = current_editors - input_editor_usernames
        for to_add in editors_to_add:
            user = User.get_user(to_add)
            self.grant_permission(RID_CONTENT_EDITOR, user)
            add_principal_to_course_content_roles(user, self.course)
            notify(CourseEditorAddedEvent(user, self.course))
        for to_remove in editors_to_remove:
            user = User.get_user(to_remove)
            self.deny_permission(RID_CONTENT_EDITOR, user)
            self.maybe_remove_user_from_content_roles(user)
            notify(CourseEditorRemovedEvent(user, self.course))
        logger.info("Updating course editors (%s) (added=%s) (removed=%s)",
                    self.entry_ntiid,
                    editors_to_add,
                    editors_to_remove)

    def __call__(self):
        # pylint: disable=no-member
        self.require_access(self.remoteUser, self.context)
        role_dict = self._roles
        if not role_dict:
            raise_error({
                    'message': _(u"Must provide roles"),
                    'code': 'RolesNotProvidedError',
                })
        input_editors = role_dict.get('editors')
        input_instructors = role_dict.get('instructors')
        instructors_updated = editors_updated = False

        if input_editors is not None:
            editors_updated = self.update_editors(input_editors)

        if input_instructors is not None:
            instructors_updated = self.update_instructors(input_instructors)

        if instructors_updated or editors_updated:
            # re-indexing instructors/editors.
            lifecycleevent.modified(self.course)
        return hexc.HTTPNoContent()


@view_config(name='CourseRoles')
@view_config(name='course_roles')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=CourseAdminPathAdapter,
               request_method='GET')
class CourseRolesCSVView(AbstractAuthenticatedView):
    """
    Return a CSV with current course roles.
    """

    def __call__(self):
        bio = BytesIO()
        csv_writer = csv.writer(bio)
        header = ['user', 'email', 'title', 'ntiid']
        csv_writer.writerow(header)

        catalog = get_enrollment_catalog()
        intids = component.getUtility(IIntIds)
        site_names = get_component_hierarchy_names()
        query = {
            IX_SITE: {'any_of': site_names},
            IX_SCOPE: {'any_of': (INSTRUCTOR, EDITOR)}
        }
        user_idx = catalog[IX_USERNAME]
        for uid in catalog.apply(query) or ():
            context = intids.queryObject(uid)
            entry = ICourseCatalogEntry(context, None)
            if entry is None:
                continue
            seen = set()
            users = user_idx.documents_to_values.get(uid)
            for username in users or ():
                user = User.get_user(username)
                seen.add(user)
            seen.discard(None)
            for user in seen:
                profile = IUserProfile(user, None)
                email = getattr(profile, 'email', None)
                # write data
                row_data = [user.username, email, entry.title, entry.ntiid]
                csv_writer.writerow([tx_string(x) for x in row_data])

        response = self.request.response
        response.body = bio.getvalue()
        response.content_disposition = 'attachment; filename="CourseRoles.csv"'
        return response
