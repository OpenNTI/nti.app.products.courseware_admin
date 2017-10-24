#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time
import collections

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_input_data

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.views import VIEW_ASSESSMENT_POLICIES

from nti.assessment.interfaces import IQAssignmentPolicies

from nti.cabinet.filer import read_source

from nti.contenttypes.courses._assessment_override_parser import fill_asg_from_json
from nti.contenttypes.courses._assessment_policy_validator import validate_assigment_policies

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import is_valid_ntiid_string

logger = __import__('logging').getLogger(__name__)


@view_config(name='assessment_policies')
@view_config(name=VIEW_ASSESSMENT_POLICIES)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               context=ICourseInstance,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseAssessmentPolicyGetView(AbstractAuthenticatedView):

    def __call__(self):
        course = ICourseInstance(self.context)
        result = IQAssignmentPolicies(course)
        return result


@view_config(name='assessment_policies')
@view_config(name=VIEW_ASSESSMENT_POLICIES)
@view_defaults(route_name='objects.generic.traversal',
               request_method='GET',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryAssessmentPolicyGetView(CourseAssessmentPolicyGetView):
    pass


@view_config(name='assessment_policies')
@view_config(name=VIEW_ASSESSMENT_POLICIES)
@view_defaults(route_name='objects.generic.traversal',
               request_method='PUT',
               context=ICourseInstance,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseAssessmentPolicyPutView(AbstractAuthenticatedView,
                                    ModeledContentUploadRequestUtilsMixin):

    def clean_input(self, values):
        for key in list(values.keys()):
            if not is_valid_ntiid_string(key):
                values.pop(key, None)
        return values

    def readInput(self, value=None):
        if self.request.body:
            source = super(CourseAssessmentPolicyPutView, self).readInput(value)
        elif self.request.POST:
            sources = get_all_sources(self.request)
            if not sources:
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"No source was specified."),
                                 },
                                 None)
            source = next(iter(sources.values()))  # pick first
            source = read_input_data(read_source(source), self.request)
            if not isinstance(source, collections.Mapping):
                raise_json_error(self.request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Invalid input format."),
                                 },
                                 None)
        if source is not None:
            self.clean_input(source)
        if source is None:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No input data specified."),
                             },
                             None)
        return source

    def __call__(self):
        entry = ICourseCatalogEntry(self.context, None)
        if entry is None or ILegacyCourseCatalogEntry.providedBy(self.context):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot update a legacy course."),
                             },
                             None)
        values = self.readInput()
        course = ICourseInstance(entry)
        # fill new policy -> force new changes
        result = fill_asg_from_json(course, values, time.time(), True)
        validate_assigment_policies(result)
        return result


@view_config(name='assessment_policies')
@view_config(name=VIEW_ASSESSMENT_POLICIES)
@view_defaults(route_name='objects.generic.traversal',
               request_method='PUT',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryAssessmentPolicyPutView(CourseAssessmentPolicyPutView):
    pass
