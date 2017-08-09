#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than_or_equal_to
does_not = is_not

import os
import shutil

import fudge

from zope import component

from nti.app.products.courseware_admin.exporter import export_course

from nti.app.products.courseware_admin.importer import create_course

from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCourseImport(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def catalog_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_get_importers(self):
        importers = component.getUtilitiesFor(ICourseSectionImporter)
        sections = tuple(x for x, _ in importers)
        assert_that(sections, has_length(greater_than_or_equal_to(11)))
        assert_that('001:Bundle_Metainfo', is_in(sections))
        assert_that('003:Presentation_Assets', is_in(sections))
        assert_that('004:Course_Info', is_in(sections))
        assert_that('008:Course_Outline', is_in(sections))
        assert_that('010:Assessments', is_in(sections))
        assert_that('012:Evaluations', is_in(sections))
        assert_that('015:Lesson_Overviews', is_in(sections))
        assert_that('100:Assignment_Policies', is_in(sections))
        assert_that('666:Role_Info', is_in(sections))
        assert_that('777:Vendor_Info', is_in(sections))
        assert_that('888:Course_Discussions', is_in(sections))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.products.courseware_admin.views.import_views.create_course',
                 'nti.app.products.courseware_admin.views.import_views.import_course')
    def test_fake_imports(self, mock_create, mock_import):
        mock_create.is_callable().with_args().returns(False)
        mock_import.is_callable().with_args().returns(False)

        path = os.getcwd()
        href = '/dataserver2/CourseAdmin/@@ImportCourse'
        data = {'ntiid': self.entry_ntiid, 'path': path}
        self.testapp.post_json(href, data, status=200)

        data = {'admin': 'Fall2015', 'key': 'Bleach', 'path': path}
        self.testapp.post_json(href, data, status=200)

    @WithSharedApplicationMockDS(testapp=False, users=True)
    def test_import_export(self):
        path = None
        try:
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                entry = find_object_with_ntiid(self.entry_ntiid)
                path = export_course(entry, False)
            
            with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
                course = create_course(u"Anime", u"Bleach", path, 
                                       writeout=False, lockout=True)
                assert_that(course, is_not(none()))
        finally:
            if path:
                shutil.rmtree(path, True)
