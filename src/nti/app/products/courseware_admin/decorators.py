#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: decorators.py 113814 2017-05-31 02:18:58Z josh.zuech $
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.location.interfaces import ILocation

from nti.app.products.courseware.interfaces import ICoursesWorkspace

from nti.app.products.courseware_admin import VIEW_EXPORT_COURSE
from nti.app.products.courseware_admin import VIEW_IMPORT_COURSE
from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.app.products.courseware_admin.mixins import EditorManageMixin
from nti.app.products.courseware_admin.mixins import InstructorManageMixin

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.authorization import ACT_NTI_ADMIN
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _ImportExportLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the import/export  links on the given context if the
    remote user has edit permissions.
    """

    def _predicate(self, context, result):
        return self._is_authenticated \
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

    def _predicate(self, context, result):
        # Currently only NTI admins can access the admin level views.
        return has_permission(ACT_NTI_ADMIN, self.catalog, self.request)

    def _do_decorate_external(self, context, result):
        if self.catalog is not None:
            _links = result.setdefault(LINKS, [])
            link = Link(self.catalog,
                        rel=VIEW_COURSE_ADMIN_LEVELS,
                        elements=('@@%s' % VIEW_COURSE_ADMIN_LEVELS,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstructorManagementLinkDecorator(AbstractAuthenticatedRequestAwareDecorator,
                                               InstructorManageMixin):
    """
    A decorator that provides links for course role management.
    """

    def _predicate(self, context, result):
        return  self._is_authenticated \
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
@interface.implementer(IExternalObjectDecorator)
class _CourseEditorManagementLinkDecorator(AbstractAuthenticatedRequestAwareDecorator,
                                           EditorManageMixin):
    """
    A decorator that provides links for course role management.
    """

    def _predicate(self, context, result):
        return  self._is_authenticated \
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
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _AdminCourseLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A decorator that provides admin course links.
    """

    def _predicate(self, context, result):
        return is_admin(self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel='delete', method='DELETE')
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)
