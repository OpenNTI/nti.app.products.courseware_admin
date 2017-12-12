#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import has_entries
from hamcrest import assert_that

from six.moves import urllib_parse

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
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry'
        self.testapp.get(href, status=422)

        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?admin=Fall2015'
        self.testapp.get(href, status=422)

        params = urllib_parse.urlencode((("admin", 'Fall2015'),
                                         ('key', 'CS 1323'),
                                         ('site', 'bleach.prg')))
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?%s' % params
        self.testapp.get(href, status=422)

        params = urllib_parse.urlencode((("admin", 'Fall2015'),
                                         ('key', 'CS 1323'),
                                         ('site', 'platform.ou.edu')))
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?%s' % params
        res = self.testapp.get(href,
                               status=200)

        assert_that(res.json_body,
                    has_entries('Title', 'Introduction to Computer Programming'))

        params = urllib_parse.urlencode((("admin", 'Fall2015'),
                                         ('key', 'CS 1323'),
                                         ('section', '995'),
                                         ('site', 'platform.ou.edu')))
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?%s' % params
        self.testapp.get(href, status=200)

        params = urllib_parse.urlencode((("admin", 'Fall2015'),
                                         ('key', 'CS 1323'),
                                         ('section', 'xxxx'),
                                         ('site', 'platform.ou.edu')))
        href = '/dataserver2/CourseAdmin/@@GetCatalogEntry?%s' % params
        self.testapp.get(href, status=404)
