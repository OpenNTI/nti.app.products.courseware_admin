#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import tempfile

from zope import component

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler


def export_course(context, backup=True, salt=None, path=None):
    course = ICourseInstance(context)
    filer = ICourseExportFiler(course)
    try:
        # prepare filer
        filer.prepare()
        # export course
        exporter = component.getUtility(ICourseExporter)
        exporter.export(course, filer, backup, salt)
        # zip contents
        path = path or tempfile.mkdtemp()
        zip_file = filer.asZip(path=path)
        return zip_file
    finally:
        filer.reset()
