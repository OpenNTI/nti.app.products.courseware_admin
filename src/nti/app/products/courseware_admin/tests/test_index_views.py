#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import greater_than
does_not = is_not

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestIndexViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_courses_catalog(self):
        href = '/dataserver2/CourseAdmin/@@RebuildCoursesCatalog'
        res = self.testapp.post_json(href, status=200)
        assert_that(res.json_body,
                    has_entry('Total', is_(greater_than(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_course_outline_catalog(self):
        href = '/dataserver2/CourseAdmin/@@RebuildCourseOutlineCatalog'
        res = self.testapp.post_json(href, status=200)
        assert_that(res.json_body,
                    has_entry('Total', is_(greater_than(0))))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_rebuild_enrollment_catalog(self):
        href = '/dataserver2/CourseAdmin/@@RebuildEnrollmentCatalog'
        res = self.testapp.post_json(href, status=200)
        assert_that(res.json_body,
                    has_entry('Total', is_(greater_than(0))))
