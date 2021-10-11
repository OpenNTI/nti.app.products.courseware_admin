#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.container.contained import Contained

from zope.container.interfaces import IContainer
from zope.container.interfaces import IContained

from nti.dataserver.interfaces import IUser

from nti.schema.field import TextLine
from nti.schema.field import Object

class ICourseAdminsContainer(IContainer,
                             IContained):
    """
    Assets associated with a course.
    """

    def course_admin_intids(filterInstructors=False, filterEditors=False):
        """
        An iterable of intids for IUser objects which are instructors and/or
        editors of one or more courses in this course catalog
        """
        pass
    
class ICourseAdminSummary(IContained):
    """
    Wrapper object for course admins that contains their username and
    other useful information
    """
    user = Object(IUser,
                   title=u'User object',
                   description=u'The User object for this course admin',
                   required=True)
    username = TextLine(title=u'Users username',
                           description=u'The username for this course admin',
                           required=True)
    
    
@interface.implementer(ICourseAdminSummary)
class CourseAdminSummary(Contained):
    
    mime_type = mimeType = "application/vnd.nextthought.courseadminsummary"
    
    __name__ = None
    __parent__ = None 
    
    def __init__(self, user, container):
        self.__name__ = user.username
        self.__parent__ = container
        self.user = user
        self.username = user.username
        