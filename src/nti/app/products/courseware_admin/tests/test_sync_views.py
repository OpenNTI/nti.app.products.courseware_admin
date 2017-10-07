#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import none
from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import greater_than
does_not = is_not

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver


class TestSyncViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    @property
    def course_oid(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.entry_ntiid)
            result = to_external_ntiid_oid(ICourseInstance(entry))
            return result

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sync_course(self):
        href = '/dataserver2/Objects/%s/@@SyncCourse' % self.course_oid
        res = self.testapp.post_json(href, status=200)
        assert_that(res.json_body,
                    has_entries('Results', has_length(greater_than(0)),
                                'SyncTime', is_not(none()),
                                'Transaction', is_not(none())))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sync_course_no_pacakges(self):
        data = {'pacakges': False}
        href = '/dataserver2/Objects/%s/@@SyncCourse' % self.course_oid
        res = self.testapp.post_json(href, data, status=200)
        assert_that(res.json_body,
                    has_entries('Results', has_length(greater_than(0)),
                                'SyncTime', is_not(none()),
                                'Transaction', is_not(none())))
