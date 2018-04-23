#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import json
import zipfile
import tempfile

from zope import component
from zope import lifecycleevent

from nti.app.products.courseware.utils import EXPORT_HASH_KEY
from nti.app.products.courseware.utils import COURSE_META_NAME

from nti.cabinet.filer import read_source
from nti.cabinet.filer import DirectoryFiler

from nti.contentfolder.interfaces import IRootFolder

from nti.contenttypes.courses import COURSE_EXPORT_HASH_FILE

from nti.contenttypes.courses.creator import delete_directory
from nti.contenttypes.courses.creator import create_course_subinstance
from nti.contenttypes.courses.creator import create_course as course_creator

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseImportMetadata
from nti.contenttypes.courses.interfaces import DuplicateImportFromExportException

from nti.contenttypes.courses.utils import get_courses_for_export_hash

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.externalization.internalization import find_factory_for

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import IRecordable

logger = __import__('logging').getLogger(__name__)


def check_archive(path):
    if not os.path.isdir(path):
        if not zipfile.is_zipfile(path):
            raise IOError("Invalid archive")
        archive = zipfile.ZipFile(path)
        tmp_path = tempfile.mkdtemp()
        archive.extractall(tmp_path)
        # check for extract dir
        files = os.listdir(tmp_path)
        if len(files) == 1 and os.path.isdir(os.path.join(tmp_path, files[0])):
            tmp_path = os.path.join(tmp_path, files[0])
    else:
        tmp_path = None
    return tmp_path


def _lockout(course):
    logger.info("Locking course")

    def _do_lock(obj):
        if      obj is not None \
            and IRecordable.providedBy(obj) \
            and not INTIMedia.providedBy(obj):
            obj.lock()
            lifecycleevent.modified(obj)

    def _lock_assets(asset):
        _do_lock(asset)
        _do_lock(IConcreteAsset(asset, None))
        if IItemAssetContainer.providedBy(asset):
            for item in asset.Items or ():
                _lock_assets(item)

    def _recur(node):
        if not ICourseOutline.providedBy(node):
            _do_lock(node)
        _lock_assets(INTILessonOverview(node, None))
        for child in node.values():
            _recur(child)
    _recur(course.Outline)


def _check_export_hash(course, filer, validate):
    """
    Validate the export hash has not been seen in this environment by any
    other courses. Otherwise, we may get courses with colliding ntiids.
    """
    source = filer.get(COURSE_META_NAME)
    if source:
        meta = json.load(source)
        export_hash = meta.get(EXPORT_HASH_KEY)
    if not source or not export_hash:
        # Backwards compatibility
        source = filer.get(COURSE_EXPORT_HASH_FILE)
        export_hash = read_source(source)
    if export_hash is not None:
        if validate:
            imported_courses = get_courses_for_export_hash(export_hash)
            if      imported_courses \
                and set(imported_courses) != set((course,)):
                entry_ntiids = [ICourseCatalogEntry(x).ntiid for x in imported_courses]
                logger.warn('Duplicate imported courses from zip file (hash=%s) (%s)',
                            export_hash,
                            entry_ntiids)
                raise DuplicateImportFromExportException(entry_ntiids)
        ICourseImportMetadata(course).import_hash = export_hash


def _execute(course, archive_path, writeout=True, lockout=False, clear=False, validate_export_hash=True):
    course = ICourseInstance(course, None)
    if course is None:
        raise ValueError("Invalid course")
    if clear:
        root = IRootFolder(course)
        root.clear()

    tmp_path = None
    try:
        tmp_path = check_archive(archive_path)
        filer = DirectoryFiler(tmp_path or archive_path)
        _check_export_hash(course, filer, validate_export_hash)
        importer = component.getUtility(ICourseImporter)
        result = importer.process(course, filer, writeout)
        if lockout:
            _lockout(course)
        return result
    finally:
        delete_directory(tmp_path)


def import_course(ntiid, archive_path, writeout=True, lockout=False, clear=False, validate_export_hash=True):
    """
    Import a course from a file archive

    :param ntiid Course NTIID
    :param archive_path archive path
    :param validate_export_hash whether to validate the export_hash against other imported courses
    """
    course = find_object_with_ntiid(ntiid) if ntiid else None
    _execute(course, archive_path, writeout, lockout, clear, validate_export_hash)
    return course


def create_course(admin, key, archive_path, catalog=None, writeout=True,
                  lockout=False, clear=False, creator=None, validate_export_hash=True):
    """
    Creates a course from a file archive

    :param admin Administrative level key
    :param key Course name
    :param archive_path archive path
    """
    tmp_path = None
    try:
        tmp_path = check_archive(archive_path)
        
        # Create course using factory specified by meta-info
        meta_path = os.path.expanduser(tmp_path or archive_path)
        meta_path = os.path.join(meta_path, COURSE_META_NAME)
        filer = DirectoryFiler(tmp_path or archive_path)
        course_factory = None
        meta_source = filer.get(meta_path)
        if meta_source:
            meta = json.load(meta_source)
            course_factory = find_factory_for(meta)
        course = course_creator(admin, key, catalog, writeout, creator=creator, factory=course_factory)
        
        archive_sec_path = os.path.expanduser(tmp_path or archive_path)
        archive_sec_path = os.path.join(archive_sec_path, SECTIONS)
        # Import sections, if necessary.
        if os.path.isdir(archive_sec_path):
            for name in os.listdir(archive_sec_path):
                ipath = os.path.join(archive_sec_path, name)
                if not os.path.isdir(ipath):
                    continue
                create_course_subinstance(course, name, writeout, creator=creator)
        # process
        _execute(course, tmp_path or archive_path, writeout, lockout, clear, validate_export_hash)
        return course
    finally:
        delete_directory(tmp_path)
