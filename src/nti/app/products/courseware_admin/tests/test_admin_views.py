#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import contains
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import has_items
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import none
from hamcrest import not_none

from six.moves import urllib_parse
from six.moves import StringIO

import csv

from zope import interface
from zope import component

from zope.component.hooks import getSite

from zope.component.hooks import getSite

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin import VIEW_COURSE_ADMINS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.coremetadata.interfaces import IDeactivatedUser

from nti.dataserver.authorization import ROLE_SITE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

from nti.dataserver.users.index import IX_DISPLAYNAME

from nti.dataserver.users.interfaces import IUserProfile

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid


class TestAdminViews(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
    
    service_url = '/dataserver2/service/'

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
                
    def _get_course_admin_href(self, environ=None, require=True):
        service_res = self.testapp.get(self.service_url,
                                       extra_environ=environ)
        service_res = service_res.json_body
        workspaces = service_res['Items']
        admin_ws = None
        try:
            admin_ws = next(x for x in workspaces if x['Title'] == 'Courses')
        except StopIteration:
            pass
        if require:
            assert_that(admin_ws, not_none())
            return self.require_link_href_with_rel(admin_ws, VIEW_COURSE_ADMINS)
        assert_that(admin_ws, none())
    
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_course_admins(self):
        """
        Validate getting an iterable of all course admins (instructors and editors) in a site, including filtering for either
        """
        test_user_username = u'test_user'
        test_instructor_username = u'test_instructor'
        test_editor_username = u'test_editor'
        test_site_admin_username = u'test_site_admin'

        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(test_user_username)
            instructor = self._create_user(test_instructor_username)
            editor = self._create_user(test_editor_username)
            site_admin = self._create_user(test_site_admin_username)
            set_user_creation_site(user, 'alpha.dev')
            set_user_creation_site(instructor, 'alpha.dev')
            set_user_creation_site(editor, 'alpha.dev')
            set_user_creation_site(site_admin, 'alpha.dev')

        with mock_dataserver.mock_db_trans(self.ds, site_name='alpha.dev'):
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            principal_role_manager.assignRoleToPrincipal(ROLE_CONTENT_ADMIN.id,
                                                         test_instructor_username)
            principal_role_manager.assignRoleToPrincipal(ROLE_CONTENT_EDITOR.id,
                                                         test_editor_username)
            
        nt_admin_environ = self._make_extra_environ()
        nt_admin_environ['HTTP_ORIGIN'] = 'http://alpha.dev'
        site_admin_environ = self._make_extra_environ(user=test_site_admin_username)
        site_admin_environ['HTTP_ORIGIN'] = 'http://alpha.dev'
        instructor_environ = self._make_extra_environ(user=test_instructor_username)
        instructor_environ['HTTP_ORIGIN'] = 'http://alpha.dev'
        editor_environ = self._make_extra_environ(user=test_editor_username)
        editor_environ['HTTP_ORIGIN'] = 'http://alpha.dev'
        user_environ = self._make_extra_environ(user=test_user_username)
        user_environ['HTTP_ORIGIN'] = 'http://alpha.dev'
            
        headers = {'accept': str('application/json')}
        get_course_admins_href = self._get_course_admin_href(nt_admin_environ)
        res = self.testapp.get(get_course_admins_href, extra_environ=nt_admin_environ, headers=headers)
        res = res.json_body
        