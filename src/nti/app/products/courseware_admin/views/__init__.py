#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.courseware_admin import VIEW_EXPORT_COURSE
from nti.app.products.courseware_admin import VIEW_IMPORT_COURSE
from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_ADMIN_IMPORT_COURSE
from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS
