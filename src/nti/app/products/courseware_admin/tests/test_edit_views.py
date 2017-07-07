#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_entries
from hamcrest import assert_that

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestCourseEdits(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/CourseCatalogEntry'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_edit(self):
        instructor_environ = self._make_extra_environ()

        res_dict = {}
        res_dict["title"] = "Another Course"
        res_dict["ProviderDepartmentTitle"] = "Department of Austin Graham"
        res_dict["description"] = "Yet another course"

        # Edit the course with the new information,
        res = self.testapp.put_json(self.course_path,
                                    res_dict,
                                    extra_environ=instructor_environ,
                                    status=200)

        assert_that(res.json_body,
                    has_entries("title", "Another Course",
                                "ProviderDepartmentTitle", "Department of Austin Graham",
                                "description", "Yet another course"))

        # valid duration and try again
        res_dict["Duration"] = "16 weeks"
        res = self.testapp.put_json(self.course_path,
                                    res_dict,
                                    extra_environ=instructor_environ)

        # Be sure the new information is contained in the course
        assert_that(res.json_body,
                    has_entries("Duration", 'P112D'))
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.entry_ntiid)
            assert_that(entry.is_locked(), is_(True))
