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

from zope.container.contained import Contained

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware_admin import VIEW_COURSE_ADMINS

from nti.app.products.courseware_admin.interfaces import ICourseAdminsContainer

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.contenttypes.courses.utils import get_instructors
from nti.contenttypes.courses.utils import get_editors
from nti.contenttypes.courses.utils import get_instructors_and_editors

@component.adapter(ICourseCatalog)
@interface.implementer(ICourseAdminsContainer)
class CourseAdminsContainer(Contained):

    __name__ = VIEW_COURSE_ADMINS
    __parent__ = None
    __site__ = getSite().__name__

    def __init__(self, course_catalog):
        self.__parent__ = course_catalog
        
    @property
    def course_catalog(self):
        return self.__parent__
    
    def course_admin_intids(self, filterInstructors=False, filterEditors=False):
        intids = component.getUtility(IIntIds)
        users = []
        userIntids =[]
        if filterInstructors and filterEditors:
            return {}
        elif filterInstructors:
            users = get_editors(self.__site__)
        elif filterEditors:
            users = get_instructors(self.__site__)
        else:
            users = get_instructors_and_editors(self.__site__)
            
        for user in users:
            doc_id = intids.getId(user)
            userIntids.append(doc_id)
            
        return userIntids