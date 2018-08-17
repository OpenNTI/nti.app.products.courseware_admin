#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import none
from hamcrest import has_entries
from hamcrest import assert_that

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseAssessmentPolicyViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    clicker = 'tag:nextthought.com,2011-10:OU-NAQ-CS1323_F_2015_Intro_to_Computer_Programming.naq.asg.assignment:iClicker_9_30'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_assessment_policy(self):
        href = "/dataserver2/Objects/%s/@@AssessmentPolicies" % self.entry_ntiid
        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entries(self.clicker, has_entries('auto_grade', is_(none()))))

        data = {
            self.clicker: {
                'locked': True,
                "available_for_submission_beginning": "2018-05-04T12:00:43Z",
                'auto_grade': {
                    'total_points': 100,
                }
            }
        }
        self.testapp.put_json(href, data, status=200)

        res = self.testapp.get(href, status=200)
        assert_that(res.json_body,
                    has_entries(self.clicker,
                                has_entries('auto_grade',  has_entries('total_points', 100),
                                            'locked', is_(True))))
