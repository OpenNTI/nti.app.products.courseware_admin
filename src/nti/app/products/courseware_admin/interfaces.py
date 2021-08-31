#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.container.interfaces import IContained

from nti.schema.field import TextLine

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
    
class ICourseAdminSummary(interface.Interface):
    """
    Wrapper object for course admins that contains their username and
    other useful information
    """
    username = TextLine(title=u'Users username',
                           description=u'The current number of admin seats taken in the site.',
                           required=True)
    
@interface.implementer(ICourseAdminSummary)
class CourseAdminSummary(object):
    username = ""
    
    def __init__(self, username):
        self.username = username
    