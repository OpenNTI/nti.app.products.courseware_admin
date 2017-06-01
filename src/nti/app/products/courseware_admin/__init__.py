#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.courseware import MessageFactory

VIEW_EXPORT_COURSE = 'Export'
VIEW_IMPORT_COURSE = 'Import'
VIEW_COURSE_ADMIN_LEVELS = 'AdminLevels'