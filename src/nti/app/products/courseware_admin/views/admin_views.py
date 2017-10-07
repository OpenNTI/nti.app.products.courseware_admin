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

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.sharing import update_package_permissions

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields

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
