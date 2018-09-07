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

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent.interfaces import IObjectCreatedEvent

from nti.app.products.courseware_admin.hostpolicy import get_site_provider

from nti.contenttypes.courses.interfaces import ICreatedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.interfaces import NTIID_ENTRY_TYPE

from nti.intid.common import addIntId

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import make_specific_safe

from nti.zodb.containers import time_to_64bit_int

logger = __import__('logging').getLogger(__name__)


def _set_entry_ntiid(entry):
    """
    Set a unique/GUID for these entry NTIIDs. We want to be able to
    have the flexibility to move these entries/courses between admin levels
    without being tied to an admin-level path.

    NTIID of type:
        - NTI-CourseInfo-<intid>.<timestamp>
    """
    # Give our catalog entry an intid and set an NTIID
    intids = component.getUtility(IIntIds)
    if intids.queryId(entry) is None:
        addIntId(entry)
    entry_id = intids.getId(entry)
    current_time = time_to_64bit_int(time.time())
    specific_base = '%s.%s' % (entry_id, current_time)
    specific = make_specific_safe(specific_base)
    ntiid = make_ntiid(nttype=NTIID_ENTRY_TYPE,
                       provider=get_site_provider(),
                       specific=specific)
    entry.ntiid = ntiid


@component.adapter(ICourseInstance, IObjectCreatedEvent)
def _on_course_instance_created(course, unused_event=None):
    if ICreatedCourse.providedBy(course):
        entry = ICourseCatalogEntry(course, None)
        if entry is not None:
            _set_entry_ntiid(entry)
