#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import time

from requests.structures import CaseInsensitiveDict

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware_admin.exporter import export_course

from nti.app.products.courseware_admin.views import VIEW_EXPORT_COURSE

from nti.app.products.courseware_admin.views.view_mixins import parse_course

from nti.common.string import is_true

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth


def _export_course_response(context, backup, salt, response):
    zip_file = None
    try:
        zip_file = export_course(context, backup, salt)
        filename = os.path.split(zip_file)[1]
        response.content_encoding = 'identity'
        response.content_type = 'application/zip; charset=UTF-8'
        content_disposition = 'attachment; filename="%s"' % filename
        response.content_disposition = str(content_disposition)
        response.body_file = open(zip_file, "rb")
        return response
    finally:
        if zip_file:
            os.remove(zip_file)


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_EXPORT_COURSE,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseExportView(AbstractAuthenticatedView):

    def __call__(self):
        values = CaseInsensitiveDict(self.request.params)
        backup = is_true(values.get('backup'))
        salt = values.get('salt')
        if not backup and not salt:
            # Default a salt for course copies.
            salt = str(time.time())
        return _export_course_response(self.context, backup, salt,
                                       self.request.response)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name='ExportCourse',
             context=CourseAdminPathAdapter,
             permission=nauth.ACT_CONTENT_EDIT)
class AdminExportCourseView(AbstractAuthenticatedView,
                            ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        result = CaseInsensitiveDict(self.request.params)
        if self.request.body:
            post = super(AdminExportCourseView, self).readInput(value)
            result.update(post)
        return result

    def __call__(self):
        values = self.readInput()
        context = parse_course(values, self.request)
        backup = is_true(values.get('backup'))
        salt = values.get('salt')
        if not backup and not salt:
            # Default a salt for course copies.
            salt = str(time.time())
        logger.info('Initiating course export for %s. (backup=%s) (salt=%s)',
                    context.ntiid, backup, salt)
        return _export_course_response(context, backup, salt,
                                       self.request.response)
