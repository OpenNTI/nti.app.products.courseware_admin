#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware_admin import MessageFactory as _

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.dataserver import authorization as nauth


@view_config(route_name='objects.generic.traversal',
             request_method='PUT',
             context=ICourseCatalogEntry,
             permission=nauth.ACT_CONTENT_EDIT)
class EditCatalogEntryView(AbstractAuthenticatedView,
                           ModeledContentUploadRequestUtilsMixin):
    """
    Route making ICourseCatalogEntries available for editing.
    Takes attributes to update as parameters.
    """

    def readInput(self, value=None):
        values = super(AbstractAuthenticatedView, self).readInput(value)
        # These won't set properly, so we won't change or delete them
        values.pop("PlatformPresentationResources", None)
        if "Duration" in values:
            values[u"duration"] = values["Duration"]
        values.pop('ntiid', None)
        values.pop('NTIID', None)
        return values

    def __call__(self):
        # Not allowed to edit these courses
        if ILegacyCourseCatalogEntry.providedBy(self.context):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot update a legacy course."),
                             },
                             None)
        # Get the new course info as input data
        values = self.readInput()
        fill_entry_from_legacy_json(self.context, values,
                                    notify=True, delete=False)
        # Return new catalog entry object
        return self.context
