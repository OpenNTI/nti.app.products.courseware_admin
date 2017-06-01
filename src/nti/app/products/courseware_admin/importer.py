#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: importer.py 112089 2017-05-04 18:26:44Z carlos.sanchez $
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import zipfile
import tempfile

from zope import component
from zope import lifecycleevent

from nti.cabinet.filer import DirectoryFiler

from nti.contentfolder.interfaces import IRootFolder

from nti.contenttypes.courses.creator import delete_directory
from nti.contenttypes.courses.creator import create_course_subinstance
from nti.contenttypes.courses.creator import create_course as course_creator

from nti.contenttypes.courses.interfaces import SECTIONS

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseImporter
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIMedia
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import IItemAssetContainer

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.interfaces import IRecordable


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


def _execute(course, archive_path, writeout=True, lockout=False, clear=False):
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
        importer = component.getUtility(ICourseImporter)
        result = importer.process(course, filer, writeout)
        if lockout:
            _lockout(course)
        return result
    finally:
        delete_directory(tmp_path)


def import_course(ntiid, archive_path, writeout=True, lockout=False, clear=False):
    """
    Import a course from a file archive

    :param ntiid Course NTIID
    :param archive_path archive path
    """
    course = find_object_with_ntiid(ntiid) if ntiid else None
    _execute(course, archive_path, writeout, lockout, clear)
    return course


def create_course(admin, key, archive_path, catalog=None, writeout=True,
                  lockout=False, clear=False):
    """
    Creates a course from a file archive

    :param admin Administrative level key
    :param key Course name
    :param archive_path archive path
    """
    tmp_path = None
    course = course_creator(admin, key, catalog=catalog, writeout=writeout)
    try:
        tmp_path = check_archive(archive_path)
        archive_sec_path = os.path.expanduser(tmp_path or archive_path)
        archive_sec_path = os.path.join(archive_sec_path, SECTIONS)
        # Import sections, if necessary.
        if os.path.isdir(archive_sec_path):
            for name in os.listdir(archive_sec_path):
                ipath = os.path.join(archive_sec_path, name)
                if not os.path.isdir(ipath):
                    continue
                create_course_subinstance(course, name, writeout=writeout)
        # process
        _execute(course, tmp_path or archive_path, writeout, lockout, clear)
        return course
    finally:
        delete_directory(tmp_path)
