#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entries
from hamcrest import assert_that

from six.moves.urllib_parse import urlencode

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseEdits(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_catalog_entry(self):
        params = urlencode((("admin", 'Fall2015'),
                            ('key', 'CS 1323'),
                            ('site', 'platform.ou.edu')))
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?%s' % params
        res = self.testapp.get(href,
                               status=200)

        assert_that(res.json_body,
                    has_entries('Title', 'Introduction to Computer Programming'))