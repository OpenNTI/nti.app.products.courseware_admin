#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.container.interfaces import IContained

class ICourseAdminsContainer(IContained):
    """
    Assets associated with a course.
    """

    def course_admin_intids(filterInstructors=False, filterEditors=False):
        """
        An iterable of intids for IUser objects which are instructors and/or
        editors of one or more courses in this course catalog
        """
        pass