#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from zope import component

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.contentlibrary.views.sync_views import _SyncAllLibrariesView

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contentlibrary.interfaces import IEditableContentPackage

from nti.contenttypes.courses.common import get_course_packages
from nti.contenttypes.courses.common import get_course_site_name

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IObjectEntrySynchronizer

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict

logger = __import__('logging').getLogger(__name__)


@view_config(name='Sync')
@view_config(name='SyncCourse')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseInstance,
               permission=nauth.ACT_SYNC_LIBRARY)
class SyncCourseView(_SyncAllLibrariesView):
    """
    Sync the course.

    params:
        packages - (default True) sync the underlying course packages
    """

    def _do_call(self):
        values = self.readInput()
        sync_packages = not is_false(values.get('packages'))
        allowRemoval = values.get('allowRemoval') or u''
        allowRemoval = is_true(allowRemoval)
        course = ICourseInstance(self.context)
        entry = ICourseCatalogEntry(self.context)
        if sync_packages:  # legacy
            # collect all course associated ntiids
            ntiids = [entry.ntiid]
            ntiids.extend(p.ntiid for p in get_course_packages(course)
                          if not IEditableContentPackage.providedBy(p))
            ntiids.extend(
                ICourseCatalogEntry(s).ntiid for s in get_course_subinstances(course)
            )
            # do sync
            result = self._do_sync(site=get_course_site_name(course),
                                   ntiids=ntiids,
                                   allowRemoval=allowRemoval)
        else:
            now = time.time()
            sync = component.getMultiAdapter((course, course.root),
                                             IObjectEntrySynchronizer)
            sync_results = sync.synchronize(course, course.root)
            result = LocatedExternalDict()
            result['Results'] = sync_results
            result['Transaction'] = self._txn_id()
            result['SyncTime'] = time.time() - now
        return result


@view_config(name='Sync')
@view_config(name='SyncCourse')
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name='SyncCourse',
               context=ICourseCatalogEntry,
               permission=nauth.ACT_SYNC_LIBRARY)
class SyncEntryView(SyncCourseView):
    pass
