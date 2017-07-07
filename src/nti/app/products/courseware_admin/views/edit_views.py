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

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.dataserver import authorization as nauth


@view_config(route_name='objects.generic.traversal',
             request_method='PUT',
             name="edit",
             context=ICourseCatalogEntry,
             permission=nauth.ACT_CONTENT_EDIT)
class EditCatalogEntryView(AbstractAuthenticatedView,
                 ModeledContentUploadRequestUtilsMixin):
    """
    Route making ICourseCatalogEntries available for editing.
    Takes attributes to update as parameters.
    """

    def readInput(self, value=None):
        if self.request.body:
            values = super(AbstractAuthenticatedView, self).readInput(value)
        else:
            values = self.request.params
        if "duration" not in values:
            values["duration"] = values["Duration"] if "Duration" in values else None
        
        # These won't set properly, so we won't change or delete them
        values.pop("PlatformPresentationResources")
        
        return values

    def __call__(self):
        # Get the new course info as input data
        values = self.readInput()
        
        # If invalid duration (number followed by work), bad request
        if len(values["duration"].split()) != 2:
            return hexc.HTTPBadRequest()
        
        # Not allowed to edit these courses
        if ILegacyCourseCatalogEntry.providedBy(self.context):
            return hexc.HTTPForbidden()
        
        # If catalog entry is locked, warn and don't update.
        if self.context.isLocked():
            logger.warning("Catalog entry %s is locked, cannot update" % self.context.ntiid)
            return self.context
        
        values["MimeType"] = self.context.mimeType
        
        fill_entry_from_legacy_json(self.context, values, notify=True, delete=False)
        
        # Output information to logger
        logger_str = "".join(["%s: %s\n" % (key, value)
                              for (key, value) in values.items()])
        logger.info(
            "Course catalog %s was modified with values:\n %s" %
            (self.context.ntiid, logger_str))
        
        # Return new catalog entry object
        return self.context
