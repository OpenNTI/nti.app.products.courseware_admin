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

import shutil

from six.moves import urllib_parse
from six.moves import StringIO

import csv

from zope import interface
from zope import component

from zope.component.hooks import getSite

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from zope.securitypolicy.interfaces import IPrincipalRoleManager

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin import VIEW_COURSE_ROLES
from nti.app.products.courseware_admin import VIEW_COURSE_ADMINS
from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.users.utils import set_user_creation_site

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IDeactivatedUser

from nti.dataserver.authorization import ROLE_SITE_ADMIN

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users import User

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
                
class TestCourseAdminView(ApplicationLayerTest):
    
    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
        
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def tearDown(self):
        """
        Our janux.ou.edu site should have no courses in it.
        """
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            # pylint: disable=no-member
            shutil.rmtree(enumeration.root.absolute_path, True)
    
    def _sync(self):
        with mock_dataserver.mock_db_trans(site_name='platform.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            course_catalog = component.getUtility(ICourseCatalog)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            enumeration_root = enumeration.root

            name = course_catalog.__name__
            # pylint: disable=no-member
            courses_bucket = enumeration_root.getChildNamed(name)
            synchronize_catalog_from_root(course_catalog, courses_bucket)
    
    def create_user(self, username):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(username)
            IUserProfile(user).email = '%s@gmail.com' % username
            set_user_creation_site(user, 'janux.ou.edu')
            
    def _get_admin_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        admin_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMIN_LEVELS)
        return admin_href
            
    def _get_course_admins_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        course_admins_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMINS)
        return course_admins_href
    """
    def _create_course(self):
        admin_href = self._get_admin_href()
        test_admin_key = 'CourseAdminTestKey'
        admin_res = self.testapp.post_json(admin_href, {'key': test_admin_key}).json_body
        new_admin_href = admin_res['href']
        new_course = self.testapp.post_json(new_admin_href,
                                            {'ProviderUniqueID': 'CourseAdminTestCourse',
                                             'title': 'CourseAdminTestCourse',
                                             'RichDescription': 'CourseAdminTestCourse'})

        new_course = new_course.json_body
        return new_course
    """   
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_course_admins(self):
        """
        Validate getting an iterable of all course admins (instructors and editors) in a site, including filtering for either
        """ 
        #Site Admin
        test_site_admin_username = u'test_site_admin'
        
        with mock_dataserver.mock_db_trans(self.ds):
            site_admin = self._create_user(test_site_admin_username)
            set_user_creation_site(site_admin, 'platform.ou.edu')
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course_oid = to_external_ntiid_oid(ICourseInstance(entry))
            
        nt_admin_environ = self._make_extra_environ()
        nt_admin_environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'
        site_admin_environ = self._make_extra_environ(user=test_site_admin_username)
        site_admin_environ['HTTP_ORIGIN'] = 'http://platform.ou.edu'       
        
        # Instructor
        self.create_user(u'shota.aizawa')

        # Editor
        self.create_user(u'tenya.ida')

        # Both
        self.create_user(u'toshinori.yagi')

        # Admin links
        """
        admin_href = self._get_admin_href()
        test_admin_key = 'CourseAdminTestKey'
        admin_res = self.testapp.post_json(admin_href, {'key': test_admin_key}).json_body
        new_admin_href = admin_res['href']
        new_course = self.testapp.post_json(new_admin_href,
                                            {'ProviderUniqueID': 'CourseAdminTestCourse',
                                             'title': 'CourseAdminTestCourse',
                                             'RichDescription': 'CourseAdminTestCourse'})

        new_course = new_course.json_body
        """
        course = self.testapp.get('/dataserver2/Objects/%s' % course_oid)
        course_ext = course.json_body
        course_roles_href = self.require_link_href_with_rel(course_ext, VIEW_COURSE_ROLES)
        course_admins_href = self._get_course_admins_href()
        
        data = dict()
        data['roles'] = roles = dict()
        roles['instructors'] = list(['jmadden', 'harp4162', 'shota.aizawa', 'toshinori.yagi'])
        roles['editors'] = list(['jmadden', 'harp4162', 'tenya.ida', 'toshinori.yagi'])
        self.testapp.put_json(course_roles_href, data)
        
        #Test for all course admins
        course_admins = self.testapp.get(course_admins_href, extra_environ=nt_admin_environ)
        res = course_admins.json_body
        usernames = [x['Username'] for x in res['Items']]
        assert_that(usernames, has_items('shota.aizawa',
                                                   'toshinori.yagi',
                                                   'tenya.ida'))
        
        #Test for just instructors
        course_admins = self.testapp.get(course_admins_href, extra_environ=site_admin_environ)
        res = course_admins.json_body
        #Remove some of the instructors and editors
        roles['instructors'] = list(['jmadden', 'harp4162'])
        roles['editors'] = list(['jmadden', 'harp4162'])
        self.testapp.put_json(course_roles_href, data)