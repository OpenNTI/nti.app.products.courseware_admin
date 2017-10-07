#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.contenttypes.courses.index import get_courses_catalog
from nti.contenttypes.courses.index import get_course_outline_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.metadata import queue_add as metadata_queue_add

from nti.site.hostpolicy import get_all_host_sites

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildCoursesCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildCoursesCatalogView(AbstractAuthenticatedView):

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        catalog = get_courses_catalog()
        for index in list(catalog.values()):
            index.clear()
        # reindex
        seen = set()
        items = dict()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                library = component.queryUtility(ICourseCatalog)
                if library is None or library.isEmpty():
                    continue
                count = 0
                for entry in library.iterCatalogEntries():
                    course = ICourseInstance(entry)
                    doc_id = intids.queryId(course)
                    if doc_id is None or doc_id in seen:
                        continue
                    count += 1
                    seen.add(doc_id)
                    catalog.index_doc(doc_id, course)
                    metadata_queue_add(course)
                items[host_site.__name__] = count
        result = LocatedExternalDict()
        result[ITEMS] = items
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name="RebuildCourseOutlineCatalog",
               permission=nauth.ACT_NTI_ADMIN)
class RebuildCourseOutlineCatalogView(AbstractAuthenticatedView):

    def _index_nodes(self, course, catalog, intids):

        def recur(node):
            if node is None:
                return
            doc_id = intids.queryId(node)
            if doc_id is not None:
                catalog.index_doc(doc_id, node)
                metadata_queue_add(node)
            for child in node.values():
                recur(child)

        recur(course.Outline)

    def __call__(self):
        intids = component.getUtility(IIntIds)
        # clear indexes
        catalog = get_course_outline_catalog()
        for index in list(catalog.values()):
            index.clear()
        # reindex
        seen = set()
        items = dict()
        for host_site in get_all_host_sites():  # check all sites
            with current_site(host_site):
                library = component.queryUtility(ICourseCatalog)
                if library is None or library.isEmpty():
                    continue
                count = 0
                for entry in library.iterCatalogEntries():
                    course = ICourseInstance(entry)
                    doc_id = intids.queryId(course)
                    if doc_id is None or doc_id in seen:
                        continue
                    count += 1 
                    seen.add(doc_id)
                    self._index_nodes(course, catalog, intids)
                items[host_site.__name__] = count
        result = LocatedExternalDict()
        result[ITEMS] = items
        result[ITEM_COUNT] = result[TOTAL] = len(seen)
        return result
