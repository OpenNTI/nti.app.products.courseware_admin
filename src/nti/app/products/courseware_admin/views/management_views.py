#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope.event import notify
from zope import interface

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import raise_error

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.views import VIEW_COURSE_ADMIN_LEVELS

from nti.appserver.ugd_edit_views import UGDDeleteView

from nti.contenttypes.courses.creator import create_course
from nti.contenttypes.courses.creator import install_admin_level

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import CourseAlreadyExistsException

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.dataserver import authorization as nauth

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='GET',
             permission=nauth.ACT_NTI_ADMIN)
class AdminLevelsGetView(AbstractAuthenticatedView):
    """
    Fetch the administrative levels under the course catalog.
    """

    def __call__(self):
        result = LocatedExternalDict()
        admin_levels = self.context.get_admin_levels()
        result[ITEMS] = {x: to_external_object(y, name='summary')
                         for x, y in admin_levels.items()}
        result[ITEM_COUNT] = len(admin_levels)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseCatalog,
             name=VIEW_COURSE_ADMIN_LEVELS,
             request_method='POST',
             permission=nauth.ACT_NTI_ADMIN)
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

    def _get_admin_key(self):
        values = self.readInput()
        result = values.get('name') \
            or values.get('level') \
            or values.get('key')
        if not result:
            raise_error({
                'message': _(u'Must supply admin level key.'),
                'code': 'InvalidAdminKey',
            })
        return result

    def _insert(self, admin_key):
        # Do not allow children levels to mask parent levels.
        admin_levels = self.context.get_admin_levels()
        if admin_key in admin_levels:
            raise_error({
                'message': _(u'Admin key already exists.'),
                'code': 'DuplicateAdminKey',
            })
        result = install_admin_level(admin_key, catalog=self.context)
        return result

    def __call__(self):
        admin_key = self._get_admin_key()
        new_level = self._insert(admin_key)
        logger.info("Created new admin level (%s)", admin_key)
        return new_level


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseAdministrativeLevel,
             request_method='DELETE',
             permission=nauth.ACT_NTI_ADMIN)
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
             permission=nauth.ACT_NTI_ADMIN)
class CreateCourseView(AbstractAuthenticatedView,
                       ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if self.request.body:
            values = super(CreateCourseView, self).readInput(value)
        else:
            values = self.request.params
        result = CaseInsensitiveDict(values)
        return result

    def _get_course_key(self, values):
        result = values.get('key') \
            or values.get('name') \
            or values.get('course')
        return result

    def __call__(self):
        # TODO: Do we need to create this in preview mode by default?
        params = self.readInput()
        key = self._get_course_key(params)
        admin_level = self.context.__name__
        logger.info('Creating course (%s) (admin=%s)', key, admin_level)
        try:
            course = create_course(
                admin_level, key, writeout=False, strict=True)
        except CourseAlreadyExistsException as e:
            raise hexc.HTTPUnprocessableEntity(e.message)
        # create non-public by default for both the course
        # and its catalog entry
        interface.alsoProvides(course, INonPublicCourseInstance)
        catalog_entry = ICourseCatalogEntry(course)
        interface.alsoProvides(catalog_entry, INonPublicCourseInstance)
        notify(CourseInstanceAvailableEvent(course))
        return course


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='DELETE',
               permission=nauth.ACT_NTI_ADMIN)
class DeleteCourseView(AbstractAuthenticatedView):

    def __call__(self):
        course = ICourseInstance(self.context)
        logger.info('Deleting course (%s)', ICourseCatalogEntry(course).ntiid)
        del course.__parent__[course.__name__]
        return hexc.HTTPNoContent()
