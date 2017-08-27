#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import greater_than
from hamcrest import greater_than_or_equal_to
does_not = is_not

import shutil
import zipfile
import tempfile

from zope import component

from nti.cabinet.mixins import get_file_size

from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseExport(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @classmethod
    def catalog_entry(cls):
        return find_object_with_ntiid(cls.entry_ntiid)

    @WithSharedApplicationMockDS(testapp=False, users=False)
    def test_get_exporters(self):
        exporters = component.getUtilitiesFor(ICourseSectionExporter)
        sections = sorted(x for x, _ in exporters)
        import pprint
        pprint.pprint(sections)
        assert_that(sections, has_length(greater_than_or_equal_to(12)))
        assert_that('001:Bundle_Metainfo', is_in(sections))
        assert_that('002:Bundle_DC_Metadata', is_in(sections))
        assert_that('003:Presentation_Assets', is_in(sections))
        assert_that('004:Course_Info', is_in(sections))
        assert_that('005:Vendor_Info', is_in(sections))
        assert_that('006:Role_Info', is_in(sections))
        assert_that('008:Course_Outline', is_in(sections))
        assert_that('011:Assessments', is_in(sections))
        assert_that('012:Evaluations', is_in(sections))
        assert_that('014:ContentPackages', is_in(sections))
        assert_that('017:User_Assets', is_in(sections))
        assert_that('018:Lesson_Overviews', is_in(sections))
        assert_that('020:Course_Discussions', is_in(sections))
        assert_that('100:Assignment_Policies', is_in(sections))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_export_course(self):
        href = '/dataserver2/CourseAdmin/@@ExportCourse'
        data = {'ntiid': self.entry_ntiid}
        res = self.testapp.post_json(href, data)
        tmp_dir = tempfile.mkdtemp()
        try:
            path = tmp_dir + "/exported.zip"
            with open(path, "wb") as fp:
                for data in res.app_iter:
                    fp.write(data)
            assert_that(get_file_size(path), greater_than(0))
            assert_that(zipfile.is_zipfile(path), is_(True))
        finally:
            shutil.rmtree(tmp_dir, True)
