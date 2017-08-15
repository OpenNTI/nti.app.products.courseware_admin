#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time
import tempfile

from zope import component

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry


def export_course(context, backup=True, salt=None, path=None):
    course = ICourseInstance(context)
    filer = ICourseExportFiler(course)
    entry = ICourseCatalogEntry(course)
    try:
        # prepare filer
        filer.prepare()
        # export course
        salt = salt or str(time.time())
        logger.info('Initiating course export for %s. (backup=%s) (salt=%s)',
                    entry.ntiid, backup, salt)
        exporter = component.getUtility(ICourseExporter)
        exporter.export(course, filer, backup, salt)
        # zip contents
        path = path or tempfile.mkdtemp()
        zip_file = filer.asZip(path=path)
        return zip_file
    finally:
        filer.reset()
