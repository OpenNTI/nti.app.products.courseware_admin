#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.completion.interfaces import ICompletables
from nti.contenttypes.completion.interfaces import ICompletableItem

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.app.products.courseware.interfaces import ICoursesWorkspace

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICompletables)
class CourseAdminsCompletables(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def iter_objects(self):
        from IPython.terminal.debugger import set_trace;set_trace()
        for unused_name, item in component.getUtilitiesFor(ICoursesWorkspace):
            if ICompletableItem.providedBy(item):
                yield item
