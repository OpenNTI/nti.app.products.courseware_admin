#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin import VIEW_EXPORT_COURSE
from nti.app.products.courseware_admin import VIEW_IMPORT_COURSE

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

from nti.dataserver.tests import mock_dataserver


class TestDecorators(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    @Lazy
    def course_oid(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            result = to_external_ntiid_oid(ICourseInstance(entry))
            return result

    def _get_course_ext(self, environ=None):
        if environ is not None:
            result = self.testapp.get('/dataserver2/Objects/%s' % self.course_oid,
                                      extra_environ=environ)
        else:
            href = '/dataserver2/Objects/%s' % self.course_oid
            result = self.testapp.get(href)
        return result.json_body

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_import_export(self):
        course = self._get_course_ext()
        self.require_link_href_with_rel(course, VIEW_EXPORT_COURSE)
        self.require_link_href_with_rel(course, VIEW_IMPORT_COURSE)
