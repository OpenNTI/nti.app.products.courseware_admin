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
import argparse

from zope import component

from nti.app.products.courseware.importer import create_course
from nti.app.products.courseware.importer import import_course

from nti.base._compat import text_

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.utils import run_with_dataserver

from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context


def _process(args):
    library = component.getUtility(IContentPackageLibrary)
    library.syncContentPackages()
    set_site(args.site)
    path = os.path.expanduser(args.path or os.getcwd())
    path = os.path.abspath(path)
    if hasattr(args, 'ntiid'):
        import_course(text_(args.ntiid), 
                      text_(path),
                      writeout=args.writeout,
                      lockout=args.lockout,
                      clear=args.clear)
    else:
        create_course(text_(args.admin), 
                      text_(args.key),
                      archive_path=text_(path),
                      writeout=args.writeout,
                      lockout=args.lockout,
                      clear=args.clear)


def main():
    arg_parser = argparse.ArgumentParser(description="Import/Create a course")
    arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
                            dest='verbose')

    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('-p', '--path',
                               dest='path',
                               help="Archive path",
                               required=False)
    parent_parser.add_argument('-s', '--site',
                               dest='site',
                               help="Application SITE.",
                               required=True)
    parent_parser.add_argument('-w', '--writeout',
                               dest='writeout',
                               help="Save sources on disk.",
                               action='store_true')
    parent_parser.add_argument('-l', '--lockout',
                               dest='lockout',
                               help="Lock course.",
                               action='store_true')
    parent_parser.add_argument('-c', '--clear',
                               dest='clear',
                               help="Clear course resources.",
                               action='store_true')

    subparsers = arg_parser.add_subparsers(help='sub-command help')

    # create
    parser_create = subparsers.add_parser('create', help='Create command',
                                          parents=[parent_parser])
    parser_create.add_argument('-a', '--admin',
                               dest='admin',
                               help="Administrative level", required=True)
    parser_create.add_argument('-k', '--key',
                               dest='key',
                               help="Course key", required=True)

    # import
    parser_import = subparsers.add_parser('import', help='Import command',
                                          parents=[parent_parser])
    parser_import.add_argument('-n', '--ntiid',
                               dest='ntiid',
                               help="Course NTIID", required=True)

    parsed = arg_parser.parse_args()
    if not parsed.site:
        raise ValueError("No site specified")
    env_dir = os.getenv('DATASERVER_DIR')
    if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
        raise IOError("Invalid dataserver environment root directory")

    context = create_context(env_dir, with_library=True)
    conf_packages = ('nti.appserver',)

    run_with_dataserver(environment_dir=env_dir,
                        xmlconfig_packages=conf_packages,
                        verbose=parsed.verbose,
                        context=context,
                        function=lambda: _process(parsed))
    sys.exit(0)


if __name__ == '__main__':
    main()
