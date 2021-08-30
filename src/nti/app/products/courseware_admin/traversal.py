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

from zope.traversing.interfaces import ITraversable

from pyramid.interfaces import IRequest

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware_admin.adapters import CourseAdminsContainer

from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.traversal.traversal import ContainerAdapterTraversable

@interface.implementer(ITraversable)
@component.adapter(ICourseCatalog, IRequest)
class CourseAdminsTraversable(ContainerAdapterTraversable):
    def traverse(self, key, remaining_path):
        return super(CourseAdminsTraversable, self).traverse(key, remaining_path)



@interface.implementer(IPathAdapter)
@component.adapter(ICourseCatalog, IRequest)
def course_admins_path_adapter(course_catalog, request):
    course_catalog = component.queryUtility(ICourseCatalog)
    course_admins_container = CourseAdminsContainer(course_catalog, request)
    return course_admins_container