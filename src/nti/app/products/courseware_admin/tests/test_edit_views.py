#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id:
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import has_entry

import json

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS


class TestCourseEdits(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = str('http://janux.ou.edu')

    course_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/CourseCatalogEntry'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_edit(self):
        instructor_environ = self._make_extra_environ()

        res = self.testapp.get(
            '/dataserver2/Objects/' + self.entry_ntiid,
            extra_environ=instructor_environ)
        res_dict = json.loads(res.body)

        # Set new info for the course
        res_dict["title"] = "Another Course"
        res_dict["ProviderDepartmentTitle"] = "Department of Austin Graham"
        res_dict["description"] = "Yet another course"

        edit_path = self.course_path + "/edit"

        # Edit the course with the new information,
        # but since this duration is invalid should raise bad request
        self.testapp.put(edit_path,
                         json.dumps(res_dict),
                         extra_environ=instructor_environ,
                         status=400)

        # Give valid duration and try again
        res_dict["duration"] = "16 weeks"
        self.testapp.put(edit_path,
                         json.dumps(res_dict),
                         extra_environ=instructor_environ)

        res = self.testapp.get(
            self.course_path,
            extra_environ=instructor_environ)

        res_dict = json.loads(res.body)

        # Be sure the new information is contained in the course
        assert_that(res_dict, has_entries("title", "Another Course",
                                          "ProviderDepartmentTitle", "Department of Austin Graham",
                                          "description", "Yet another course"))
