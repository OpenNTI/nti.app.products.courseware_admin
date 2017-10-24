#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entries
from hamcrest import assert_that

from nti.testing.matchers import is_empty as empty

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseVendorInfo(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_vendor_info(self):
        href = "/dataserver2/Objects/%s/@@vendor_info" % self.entry_ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entries('NTI', has_entries('Forums', is_not(empty()),
                                                   'SharingScopesDisplayInfo', is_not(empty())),
                                'Class', 'DefaultCourseInstanceVendorInfo'))
        info = dict(res.json_body)
        info['Bleach'] = {'Captains': ['Aizen', 'Zaraki']}
        self.testapp.put_json(href, info, status=200)

        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entries('Bleach', has_entries('Captains',  ['Aizen', 'Zaraki'])))
