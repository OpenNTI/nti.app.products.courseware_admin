#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: decorators.py 113814 2017-05-31 02:18:58Z josh.zuech $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.products.courseware.interfaces import ICoursesWorkspace
from nti.app.products.courseware.interfaces import ICoursesCatalogCollection

from nti.app.products.courseware_admin import VIEW_VENDOR_INFO
from nti.app.products.courseware_admin import VIEW_EXPORT_COURSE
from nti.app.products.courseware_admin import VIEW_IMPORT_COURSE
from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_ASSESSMENT_POLICIES
from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin import VIEW_PRESENTATION_ASSETS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_SUGGESTED_TAGS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.app.products.courseware_admin.mixins import EditorManageMixin
from nti.app.products.courseware_admin.mixins import InstructorManageMixin

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import INonExportable
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IGlobalCourseCatalog

from nti.contenttypes.courses.utils import is_course_editor
from nti.contenttypes.courses.utils import filter_hidden_tags

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


def get_ds2(request=None):
    request = request if request else get_current_request()
    try:
        # e.g. /dataserver2
        result = request.path_info_peek() if request else None
    except AttributeError:  # in unit test we may see this
        result = None
    return result or "dataserver2"


def course_admin_adapter_path(request=None):
    path = '/%s/CourseAdmin' % get_ds2(request)
    return path


def _can_edit_course(course, user):
    return     is_admin_or_content_admin_or_site_admin(user) \
            or is_course_editor(course, user)


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _ImportExportLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the import/export links on the given context if the
    remote user has edit permissions.
    """

    def _predicate(self, context, unused_result):
        course = ICourseInstance(context)
        return self._is_authenticated \
           and not INonExportable.providedBy(course) \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name, method in ((VIEW_EXPORT_COURSE, 'GET'),
                             (VIEW_IMPORT_COURSE, 'POST')):
            link = Link(context,
                        rel=name, elements=('@@%s' % name,),
                        method=method)
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _EntryTagDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Filter hidden tags on :class:`ICourseCatalogEntry` objects.
    """

    def _predicate(self, context, unused_result):
        return not _can_edit_course(context, self.remoteUser)

    def _do_decorate_external(self, unused_context, result):
        if 'tags' in result:
            result['tags'] = filter_hidden_tags(result['tags'])


@component.adapter(ICoursesWorkspace)
@interface.implementer(IExternalObjectDecorator)
class _CourseWorkspaceDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A decorator that provides links for course management.

    Note, we actually decorate and check access on the ICourseCatalog.
    """

    @Lazy
    def catalog(self):
        return component.queryUtility(ICourseCatalog)

    def _predicate(self, unused_context, unused_result):
        return self.catalog is not None \
           and not IGlobalCourseCatalog.providedBy(self.catalog) \
           and is_admin_or_content_admin_or_site_admin(self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(self.catalog,
                    rel=VIEW_COURSE_ADMIN_LEVELS,
                    elements=('@@%s' % VIEW_COURSE_ADMIN_LEVELS,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstructorManagementLinkDecorator(AbstractAuthenticatedRequestAwareDecorator,
                                               InstructorManageMixin):
    """
    A decorator that provides links for course role management.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and self.has_access(self.remoteUser, context)

    def _do_decorate_external(self, context, result):
        for rel in (VIEW_COURSE_INSTRUCTORS,
                    VIEW_COURSE_REMOVE_INSTRUCTORS):
            _links = result.setdefault(LINKS, [])
            link = Link(context, rel=rel, elements=('@@%s' % rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseEditorManagementLinkDecorator(AbstractAuthenticatedRequestAwareDecorator,
                                           EditorManageMixin):
    """
    A decorator that provides links for course role management.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and self.has_access(self.remoteUser, context)

    def _do_decorate_external(self, context, result):
        for rel in (VIEW_COURSE_EDITORS,
                    VIEW_COURSE_REMOVE_EDITORS):
            _links = result.setdefault(LINKS, [])
            link = Link(context, rel=rel, elements=('@@%s' % rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CoursePolicyLinksDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A decorator that provides links for course vendor info and
    assessement policies management.
    """

    def _predicate(self, context, unused_result):
        return  self._is_authenticated \
            and _can_edit_course(context, self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in (VIEW_VENDOR_INFO,
                    VIEW_ASSESSMENT_POLICIES):
            link = Link(context, rel=rel, elements=('@@%s' % rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CatalogEntryEditLinksDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A decorator that provides edit links for :class:`ICourseCatalogEntry`
    objects.
    """

    def _predicate(self, context, unused_result):
        course = ICourseInstance(context)
        return  self._is_authenticated \
            and _can_edit_course(course, self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in (VIEW_PRESENTATION_ASSETS,):
            link = Link(context, rel=rel, elements=('@@%s' % rel,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _AdminCourseLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A decorator that provides admin course links.
    """

    def _predicate(self, unused_context, unused_result):
        return is_admin_or_content_admin_or_site_admin(self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel='delete', method='DELETE')
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICoursesCatalogCollection)
class _CourseCatalogCollectionDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:``ICoursesCatalogCollection`` with a `SuggestedTags` rel.
    """

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_COURSE_SUGGESTED_TAGS,
                    elements=('@@%s' % VIEW_COURSE_SUGGESTED_TAGS,))
        _links.append(link)
