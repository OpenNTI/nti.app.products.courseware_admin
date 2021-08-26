#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.products.courseware_admin.interfaces import ICourseAdminsContainer

def _course_admins_path_adapter(context, request):
    return ICourseAdminsContainer(context)