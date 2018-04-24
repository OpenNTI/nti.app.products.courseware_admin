#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: course_import_views.py 113825 2017-05-31 03:08:26Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import time
import tempfile

from requests.structures import CaseInsensitiveDict

from zope import component

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.event import notify

from zope.security.management import endInteraction
from zope.security.management import restoreInteraction

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_all_sources
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import raise_error
from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware_admin import MessageFactory as _

from nti.app.products.courseware_admin.importer import create_course
from nti.app.products.courseware_admin.importer import import_course

from nti.app.products.courseware_admin.views import VIEW_IMPORT_COURSE
from nti.app.products.courseware_admin.views import VIEW_ADMIN_IMPORT_COURSE

from nti.cabinet.filer import transfer_to_native_file

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses.creator import delete_directory
from nti.contenttypes.courses.creator import install_admin_level

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import InvalidCourseArchiveException
from nti.contenttypes.courses.interfaces import ImportCourseTypeUnsupportedError
from nti.contenttypes.courses.interfaces import DuplicateImportFromExportException

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_content_admin

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import ObjectModifiedFromExternalEvent

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.hostpolicy import get_host_site

from nti.site.site import get_component_hierarchy_names

NTIID = StandardExternalFields.NTIID

logger = __import__('logging').getLogger(__name__)


class CourseImportMixin(AbstractAuthenticatedView,
                        ModeledContentUploadRequestUtilsMixin):

    def readInput(self, value=None):
        if not self.request.body:
            return CaseInsensitiveDict()
        else:
            result = super(CourseImportMixin, self).readInput(value)
            return CaseInsensitiveDict(result)

    def _get_validate_export_hash(self, values):
        """
        Get the validate_export_hash param from the user. We only allow
        users to override this export_hash validation if they are an NT
        or content admin.
        """
        validate_export_hash = True
        if is_admin_or_content_admin(self.remoteUser):
            # Default to True if not specified
            validate_export_hash = not is_false(values.get('validate_export_hash'))
        return validate_export_hash

    def _get_source_paths(self, values):
        tmp_path = None
        path = values.get('path')
        if path and not os.path.exists(path):
            raise_error({
                'message': _(u"Invalid path."),
                'code': 'InvalidPath',
            })
        elif self.request.POST:
            source = None
            filename = None
            for name, source in get_all_sources(self.request, None).items():
                filename = getattr(source, 'filename', name)
                filename = safe_filename(os.path.split(filename)[1])
                break
            if not filename:
                raise_error({
                    'message': _(u"No archive source uploaded."),
                    'code': 'InvalidSource',
                })
            tmp_path = tempfile.mkdtemp()
            path = os.path.join(tmp_path, filename)
            transfer_to_native_file(source, path)
            logger.info("Source data saved to %s", path)
        elif not path:
            raise_error({
                'message': _(u"No archive source specified."),
                'code': 'NoSourceSpecified',
            })
        return path, tmp_path

    def _do_call(self):
        pass

    def __call__(self):
        endInteraction()
        try:
            return self._do_call()
        except DuplicateImportFromExportException:
            raise_error({
                    'message': _(u"Duplicate import from export file error"),
                    'code': 'DuplicateImportFromExportError',
                })
        except InvalidCourseArchiveException:
            raise_error({
                'message': _(u"Error importing: Invalid course archive"),
                'code': 'InvalidCourseArchiveException'
                })
        except ImportCourseTypeUnsupportedError:
            raise_error({
                   'message':  _(u'Import error: unsupported course type'),
                   'code': 'ImportCourseTypeUnsupportedError'
                })
        finally:
            restoreInteraction()


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_IMPORT_COURSE,
               permission=nauth.ACT_CONTENT_EDIT)
class CourseImportView(CourseImportMixin):

    def _do_call(self):
        tmp_path = None
        now = time.time()
        values = self.readInput()
        result = LocatedExternalDict()
        try:
            entry = ICourseCatalogEntry(self.context)
            path, tmp_path = self._get_source_paths(values)
            clear = is_true(values.get('clear'))
            writeout = is_true(values.get('writeout') or values.get('save'))
            lockout = is_true(values.get('lock') or values.get('lockout'))
            validate_export_hash = self._get_validate_export_hash(values)
            preview_raw_value = getattr(entry, 'PreviewRawValue', None)
            import_course(entry.ntiid,
                          os.path.abspath(path),
                          writeout,
                          lockout,
                          clear=clear,
                          validate_export_hash=validate_export_hash)
            if preview_raw_value is not None:
                entry.Preview = preview_raw_value
            else:
                delattr(entry, 'Preview')
            result['Elapsed'] = time.time() - now
            course = ICourseInstance(self.context)
            result['Course'] = course
            notify(ObjectModifiedFromExternalEvent(course))
            notify(ObjectModifiedFromExternalEvent(entry))
        finally:
            delete_directory(tmp_path)
        return result


@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_ADMIN_IMPORT_COURSE,
               permission=nauth.ACT_CONTENT_EDIT)
class ImportCourseView(CourseImportMixin):

    def _import_course(self, ntiid, path, writeout=True,
                       lockout=False, clear=False, validate_export_hash=True):
        context = find_object_with_ntiid(ntiid)
        course = ICourseInstance(context, None)
        if course is None:
            raise_error({
                'message': _(u"Invalid course."),
                'code': 'InvalidCourse',
            })
        return import_course(ntiid,
                             path,
                             writeout,
                             lockout,
                             clear=clear,
                             validate_export_hash=validate_export_hash)

    def _create_course(self, admin, key, path, writeout=True,
                       lockout=False, clear=False, site=None, validate_export_hash=True):
        if not admin:
            raise_error({
                'message': _(u"No administrative level specified."),
                'code': 'MissingAdminLevel',
            })
        if not key:
            raise_error({
                'message': _(u"No course key specified."),
                'code': 'MissingCourseKey',
            })

        sites = get_component_hierarchy_names()
        if site and site not in sites:
            raise_error({
                'message': _(u"Invalid site."),
                'code': 'InvalidSite',
            })
        elif not site:
            site = getSite().__name__

        catalog = None
        site = get_host_site(site)
        with current_site(site):
            adm_levels = component.queryUtility(ICourseCatalog)
            if adm_levels is not None:
                if admin not in adm_levels:
                    install_admin_level(admin, adm_levels, site, writeout, False)
                catalog = adm_levels

        if catalog is None:
            raise_error({
                'message': _(u"Invalid administrative level."),
                'code': 'InvalidAdminLevel',
            })
        logger.info('Importing course (key=%s) (admin=%s) (path=%s) (lockout=%s) (clear=%s) (writeout=%s) (site=%s) (validate_export_hash=%s)',
                    key, admin, path, lockout, clear, writeout, site.__name__,
                    validate_export_hash)
        # pylint: disable=no-member
        return create_course(admin, key, path, catalog, writeout,
                             lockout, clear, self.remoteUser.username,
                             validate_export_hash=validate_export_hash)

    def _do_call(self):
        tmp_path = None
        now = time.time()
        values = self.readInput()
        result = LocatedExternalDict()
        params = result['Params'] = {}
        try:
            ntiid = values.get('ntiid')
            path, tmp_path = self._get_source_paths(values)
            path = os.path.abspath(path)
            clear = is_true(values.get('clear'))
            writeout = is_true(values.get('writeout') or values.get('save'))
            validate_export_hash = self._get_validate_export_hash(values)
            lockout = is_true(   values.get('lock')
                              or values.get('lockout')
                              or 'True')
            if ntiid:
                params[NTIID] = ntiid
                context = find_object_with_ntiid(ntiid)
                course = ICourseInstance(context, None)
                entry = ICourseCatalogEntry(course, None)
                preview_raw_value = getattr(entry, 'PreviewRawValue', None)
                course = self._import_course(ntiid, path, writeout,
                                             lockout, clear=clear,
                                             validate_export_hash=validate_export_hash)
                if preview_raw_value is not None:
                    entry.Preview = preview_raw_value
                else:
                    delattr(entry, 'Preview')
            else:
                site = values.get('site')
                params['Key'] = key = values.get('key')
                params['Admin'] = admin = values.get('admin')
                course = self._create_course(admin, key, path, writeout,
                                             lockout, clear, site,
                                             validate_export_hash=validate_export_hash)
            notify(ObjectModifiedFromExternalEvent(course))
            # Test safety
            entry = ICourseCatalogEntry(course, None)
            if entry is not None:
                notify(ObjectModifiedFromExternalEvent(entry))
            result['Course'] = course
            result['Elapsed'] = time.time() - now
        except Exception as e:
            logger.exception("Cannot import/create course")
            tmp_path = None
            raise e
        finally:
            delete_directory(tmp_path)
        return result
