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
from nti.app.products.courseware_admin.interfaces import ICourseAdminSummary
from nti.app.products.courseware_admin.interfaces import CourseAdminSummary

from nti.app.users.utils import get_user_creation_site

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.utils import get_instructors
from nti.contenttypes.courses.utils import get_editors
from nti.contenttypes.courses.utils import get_instructors_and_editors

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.users import User

from nti.site.interfaces import IHostPolicySiteManager

@component.adapter(IHostPolicySiteManager)
@interface.implementer(ICourseAdminsContainer)
class CourseAdminsContainer(CaseInsensitiveCheckingLastModifiedBTreeContainer,
                            Contained):
    __name__ = VIEW_COURSE_ADMINS
    __parent__ = None
    __site__ = None

    def __init__(self, context):
        """
        Traversal requires __parent__ to be not None, so we set one here;
        We only want course admins for this site, not all the sites in the heirarchy,
        so we explicitly pass it to the util functions instead of using their default
        method (which goes up the heirarchy to find all of the sites therein) 
        """
        self.__parent__ = context
        self.__site__ = getSite()
        
    def get(self, key, default=None):
        user = User.get_user(key)
        if user is None or self.__site__ is not get_user_creation_site(user):
            return default
        return CourseAdminSummary(user, self)
        
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
            if (self.__site__ == get_user_creation_site(user)):
                doc_id = intids.getId(user)
                userIntids.append(doc_id)
            
        return userIntids
    
@component.adapter(IUser)
@interface.implementer(ICourseAdminSummary)
def _user_to_course_admin_summary(user):
    parent = CourseAdminsContainer(getSite().getSiteManager())
    return CourseAdminSummary(user, parent)
    