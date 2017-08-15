#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import time
import pprint
import argparse

from zope import component

from nti.base._compat import text_

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid


def _sync_library():
    try:
        library = component.queryUtility(IContentPackageLibrary)
        library.syncContentPackages()
    except AttributeError:
        pass


def _list(site):
    set_site(site)
    catalog = component.getUtility(ICourseCatalog)
    result = []
    for entry in catalog.iterCatalogEntries():
        result.append(("%s,'%s'" % (entry.ntiid, entry.Title)))
    pprint.pprint(sorted(result))


def _export(ntiid, site, backup, salt=None, path=None):
    _sync_library()
    set_site(site)
    course = find_object_with_ntiid(ntiid)
    course = ICourseInstance(course, None)
    if course is None:
        raise ValueError("Invalid course")

    path = path or os.getcwd()
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        os.makedirs(path)
    elif not os.path.isdir(path):
        raise ValueError("Invalid output path")

    # prepare source filer
    filer = ICourseExportFiler(course)
    filer.prepare()

    # export course
    exporter = component.getUtility(ICourseExporter)
    exporter.export(course, filer, backup=backup, salt=salt)

    # zip contents
    zip_file = filer.asZip(path=path)

    # remove all content
    filer.reset()

    logger.info("Course exported to %s", zip_file)
    return zip_file


def _process(args):
    site = args.site
    if args.list:
        return _list(site)
    else:
        salt = args.salt
        backup = args.backup
        ntiid = text_(args.ntiid)
        path = args.path or os.getcwd()
        salt = str(time.time()) if not salt and not backup else salt
        return _export(ntiid, site, backup, salt=salt, path=path)


def main():
    arg_parser = argparse.ArgumentParser(description="Export a course")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
                            dest='verbose')
    arg_parser.add_argument('-p', '--path',
                            dest='path',
                            help="Output path")
    arg_parser.add_argument('-s', '--site',
                            dest='site',
                            help="Application SITE.")
    arg_parser.add_argument('-b', '--backup',
                            help="Backup flag", action='store_true',
                            dest='backup')
    arg_parser.add_argument('-t', '--salt',
                            dest='salt',
                            help="Hash salt.")
    site_group = arg_parser.add_mutually_exclusive_group()
    site_group.add_argument('-n', '--ntiid',
                            dest='ntiid',
                            help="Course NTIID")
    site_group.add_argument('--list',
                            help="List courses", action='store_true',
                            dest='list')
    args = arg_parser.parse_args()

    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    if not args.list:
        if not args.ntiid:
            raise ValueError("No course specified")

    if not args.site:
        raise ValueError("No site specified")

    context = create_context(env_dir, with_library=True)
    conf_packages = ('nti.appserver',)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        verbose=args.verbose,
                        context=context,
                        function=lambda: _process(args))
    sys.exit(0)


if __name__ == '__main__':
    main()
