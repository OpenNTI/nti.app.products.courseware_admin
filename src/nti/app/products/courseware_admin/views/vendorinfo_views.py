#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import collections

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope.event import notify

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_input_data

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.views import VIEW_VENDOR_INFO

from nti.cabinet.filer import read_source

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

EXCLUDE = tuple(StandardExternalFields.EXTERNAL_KEYS) + (StandardInternalFields.NTIID,)

logger = __import__('logging').getLogger(__name__)


@view_config(name='vendor_info')
@view_config(name='vendor-info')
@view_config(name=VIEW_VENDOR_INFO)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               context=ICourseInstance,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseVendorInfoGetView(AbstractAuthenticatedView):

    def __call__(self):
        course = ICourseInstance(self.context)
        vendor = ICourseInstanceVendorInfo(course)
        return vendor


@view_config(name='vendor_info')
@view_config(name='vendor-info')
@view_config(name=VIEW_VENDOR_INFO)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryVendorInfoGetView(CourseVendorInfoGetView):
    pass


@view_config(name='vendor_info')
@view_config(name='vendor-info')
@view_config(name=VIEW_VENDOR_INFO)
@view_defaults(route_name='objects.generic.traversal',
               request_method='PUT',
               context=ICourseInstance,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseVendorInfoPutView(AbstractAuthenticatedView,
                              ModeledContentUploadRequestUtilsMixin):

    def clean_input(self, values):
        # pylint: disable=expression-not-assigned
        [values.pop(x, None) for x in EXCLUDE]
        return values

    def readInput(self, value=None):
        source = None
        sources = get_all_sources(self.request)
        if sources:
            source = next(iter(sources.values()))  # pick first
            source = read_input_data(read_source(source), self.request)
            if not isinstance(source, collections.Mapping):
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid input format."),
                                 },
                                 None)
        elif self.request.body:
            source = super(CourseVendorInfoPutView, self).readInput(value)
        if not source:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No input data specified."),
                             },
                             None)
        return self.clean_input(source)

    def __call__(self):
        entry = ICourseCatalogEntry(self.context, None)
        if entry is None or ILegacyCourseCatalogEntry.providedBy(entry):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot update a legacy course."),
                             },
                             None)
        values = self.readInput()
        course = ICourseInstance(entry)
        vendor = ICourseInstanceVendorInfo(course)
        # pylint: disable=too-many-function-args
        vendor.clear()
        vendor.update(values)
        notify(CourseVendorInfoSynchronized(course))
        return vendor


@view_config(name='vendor_info')
@view_config(name='vendor-info')
@view_config(name=VIEW_VENDOR_INFO)
@view_defaults(route_name='objects.generic.traversal',
               request_method='PUT',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryVendorInfoPutView(CourseVendorInfoPutView):
    pass
