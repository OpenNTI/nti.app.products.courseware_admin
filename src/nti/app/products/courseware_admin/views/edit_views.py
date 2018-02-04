#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentlibrary.utils.bundle import save_presentation_assets

from nti.app.contentlibrary.views.bundle_views import ContentPackageBundleMixin

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware_admin import VIEW_PRESENTATION_ASSETS

from nti.app.products.courseware_admin import MessageFactory as _

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import StandardInternalFields

NTIID = StandardExternalFields.NTIID
INT_NTIID = StandardInternalFields.NTIID

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             request_method='PUT',
             name=VIEW_PRESENTATION_ASSETS,
             context=ICourseCatalogEntry,
             permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryPresentationAssetsPutView(AbstractAuthenticatedView,
                                            ModeledContentUploadRequestUtilsMixin,
                                            ContentPackageBundleMixin):

    def _get_bucket(self, course):
        return course.root

    def handle_presentation_assets(self):
        # handle presentation-assets and save
        assets = self.get_source(self.request)
        if assets is not None:
            intids = component.getUtility(IIntIds)
            course = ICourseInstance(self.context)
            # check for transaction retrial
            jid = getattr(self.request, 'jid', None)
            if jid is None:
                doc_id = intids.getId(course)
                bucket = self._get_bucket(course)
                save_presentation_assets(assets, bucket)
                entry = ICourseCatalogEntry(course)
                entry.root = course.root
                self.request.jid = doc_id
            return jid
        return None

    def _do_call(self):
        # Not allowed to edit these courses
        if ILegacyCourseCatalogEntry.providedBy(self.context):
            raise_json_error(self.request,
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Cannot update a legacy course."),
                             },
                             None)
        self.handle_presentation_assets()
        return self.context


@view_config(route_name='objects.generic.traversal',
             request_method='PUT',
             context=ICourseCatalogEntry,
             permission=nauth.ACT_CONTENT_EDIT)
class CatalogEntryPutView(CatalogEntryPresentationAssetsPutView):
    """
    Route making ICourseCatalogEntries available for editing.
    Takes attributes to update as parameters.
    """

    def clean_input(self, values):
        # These won't set properly, so we won't change or delete them
        values.pop("PlatformPresentationResources", None)
        if "Duration" in values:
            values[u"duration"] = values["Duration"]
        # pylint: disable=expression-not-assigned
        [values.pop(x, None) for x in (NTIID, INT_NTIID)]
        if "tags" in values:
            # Dedupe and sanitize these.
            tags = values['tags'] or ()
            values[u'tags'] = tuple({x.lower() for x in tags})
        return values

    def readInput(self, value=None):
        values = ModeledContentUploadRequestUtilsMixin.readInput(self, value)
        return self.clean_input(values)

    def _do_call(self):
        CatalogEntryPresentationAssetsPutView._do_call(self)
        # Get the new course info as input data
        values = self.readInput()
        fill_entry_from_legacy_json(self.context, values,
                                    notify=True, delete=False)
        # Return new catalog entry object
        return self.context
