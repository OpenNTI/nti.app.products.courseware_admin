#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import greater_than_or_equal_to
does_not = is_not

from nose.tools import assert_raises

from nti.testing.matchers import validly_provides

import os
import shutil
import tempfile

import fudge

from zope import component
from zope import interface

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder

from nti.app.products.courseware.resources.model import CourseContentFile

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin.exporter import export_course

from nti.app.products.courseware_admin.importer import create_course

from nti.app.contentfolder.utils import to_external_cf_io_href

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.appserver.workspaces import UserEnumerationWorkspace

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICreatedCourse
from nti.contenttypes.courses.interfaces import ICourseSectionImporter
from nti.contenttypes.courses.interfaces import DuplicateImportFromExportException

from nti.contenttypes.presentation.interfaces import IContentBackedPresentationAsset

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid



class TestCourseImport(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    ref_ntiid = u'tag:nextthought.com,2011-10:OU-RelatedWorkRef-CS1323_F_2015_Intro_to_Computer_Programming.relatedworkref.relwk:syllabus'

    @classmethod
    def catalog_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_get_importers(self):
        importers = component.getUtilitiesFor(ICourseSectionImporter)
        sections = sorted(x for x, _ in importers)
        assert_that(sections, has_length(greater_than_or_equal_to(12)))
        assert_that('001:Bundle_Metainfo', is_in(sections))
        assert_that('002:Presentation_Assets', is_in(sections))
        assert_that('003:Course_Info', is_in(sections))
        assert_that('004:Vendor_Info', is_in(sections))
        assert_that('005:Course_Outline', is_in(sections))
        assert_that('006:Role_Info', is_in(sections))
        assert_that('010:Course_Discussions', is_in(sections))
        assert_that('011:Assessments', is_in(sections))
        assert_that('012:Evaluations', is_in(sections))
        assert_that('014:ContentPackages', is_in(sections))
        assert_that('016:Asset_Cleaner', is_in(sections))
        assert_that('017:User_Assets', is_in(sections))
        assert_that('018:Lesson_Overviews', is_in(sections))
        assert_that('100:Assignment_Policies', is_in(sections))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_links(self):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._get_user(self.default_username)
            worspace = UserEnumerationWorkspace(user)
            names = set(x.rel for x in worspace.links or ())
            assert_that('ImportCourse', is_in(names))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.products.courseware_admin.views.import_views.create_course',
                 'nti.app.products.courseware_admin.views.import_views.import_course')
    def test_fake_imports(self, mock_create, mock_import):
        mock_create.is_callable().with_args().returns(False)
        mock_import.is_callable().with_args().returns(False)

        path = os.getcwd()
        href = '/dataserver2/CourseAdmin/@@ImportCourse'
        data = {'ntiid': self.entry_ntiid, 'path': path, 'site': 'platform.ou.edu'}
        self.testapp.post_json(href, data, status=200)

        data = {'admin': 'Fall2015', 'key': 'Bleach', 'path': path}
        self.testapp.post_json(href, data, status=200)

    def _add_file(self, context):
        course = ICourseInstance(context)
        folder = ICourseRootFolder(course)
        syllabus = CourseContentFile()
        syllabus.filename = syllabus.name = u"syllabus.pdf"
        syllabus.data = b'pdftext'
        syllabus.contentType = 'application/pdf'
        folder.add(syllabus)
        ref = find_object_with_ntiid(self.ref_ntiid)
        ref.href = to_external_cf_io_href(syllabus)
        ref.target = to_external_ntiid_oid(syllabus)
        ref.type = u'application/pdf'
        interface.noLongerProvides(ref, IContentBackedPresentationAsset)

    @WithSharedApplicationMockDS(testapp=False, users=True)
    @fudge.patch('nti.app.products.courseware.utils.exporter.CourseMetaInfoExporter._get_remote_user')
    def test_import_export(self, mock_get_remote_user):
        mock_get_remote_user.is_callable().returns(u'Heisenberg')
        path = tempfile.mkdtemp()
        try:
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                entry = find_object_with_ntiid(self.entry_ntiid)
                self._add_file(entry)
                course = ICourseInstance(entry)
                archive = export_course(entry, False, None, path)

            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = create_course(u"Anime", u"Bleach", archive,
                                       writeout=False, lockout=True,
                                       creator=self.default_username)
                assert_that(course, is_not(none()))
                folder = ICourseRootFolder(course)
                assert_that(folder, has_length(1))
                assert_that(course,
                            has_property('creator', is_(self.default_username)))
                assert_that(course, validly_provides(ICreatedCourse))

                # Cannot create a new course with same import
                with assert_raises(DuplicateImportFromExportException):
                    course = create_course(u"Anime", u"Bleach_key", archive,
                                           writeout=False, lockout=True,
                                           creator=self.default_username)

                # But we can import over the original course with same zip
                create_course(u"Anime", u"Bleach", archive,
                              writeout=False, lockout=True,
                              creator=self.default_username)
        finally:
            if path:
                shutil.rmtree(path, True)
