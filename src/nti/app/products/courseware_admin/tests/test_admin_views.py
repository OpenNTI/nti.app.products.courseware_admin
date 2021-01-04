#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import contains
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import contains_inanyorder

from six.moves import urllib_parse

from zope import interface

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.coremetadata.interfaces import IDeactivatedUser

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User


class TestAdminViews(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

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

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sync_instructors(self):
        href = "/dataserver2/Objects/%s/@@SyncInstructors" % self.entry_ntiid
        self.testapp.post(href, status=204)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_catalog_audit_usage(self):
        href = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/@@AuditUsageInfo'
        res = self.testapp.get(href, status=200)

        res = res.json_body

        assert_that(res, has_entries('Total', 8 ,
                                     'Items',
                                     has_entries('tag:nextthought.com,2011-10:OU-HTML-ENGR1510_Intro_to_Water.course_info', has_entries('provenance', None),
                                                 'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323_SubInstances_995', has_entries('provenance', '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses'))))

        roles = res['Items']['tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323']['roles']
        assert_that(roles, has_entries('nti.roles.course_content_editor', contains_inanyorder('tryt3968'),
                                       'nti.roles.course_instructor', contains_inanyorder('cs1323_instructor', 'tryt3968'),
                                       'nti.roles.course_ta', []))

        # Deactivated admin
        with mock_dataserver.mock_db_trans(self.ds):
            user = User.get_user('tryt3968')
            interface.alsoProvides(user, IDeactivatedUser)
            notify(ObjectModifiedEvent(user))

        try:
            href = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses/@@AuditUsageInfo'
            res = self.testapp.get(href, status=200).json_body
            roles = res['Items']['tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323']['roles']
            assert_that(roles, has_entries('nti.roles.course_content_editor', has_length(0),
                                           'nti.roles.course_instructor', contains('cs1323_instructor'),
                                           'nti.roles.course_ta', []))
        finally:
            with mock_dataserver.mock_db_trans(self.ds):
                user = User.get_user('tryt3968')
                interface.noLongerProvides(user, IDeactivatedUser)
                notify(ObjectModifiedEvent(user))
