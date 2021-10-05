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

from pyramid.interfaces import IRequest

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware_admin.adapters import CourseAdminsContainer

from nti.site.interfaces import IHostPolicySiteManager

@interface.implementer(IPathAdapter)
@component.adapter(IHostPolicySiteManager, IRequest)
def course_admins_path_adapter(host_site_manager, request):
    return CourseAdminsContainer(host_site_manager)
