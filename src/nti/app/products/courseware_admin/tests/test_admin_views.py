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
from hamcrest import has_item
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import none
from hamcrest import not_none
from hamcrest import is_

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
from nti.app.products.courseware_admin import VIEW_EXPLICTLY_ADMINISTERED_COURSES

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

from nti.dataserver.metadata.index import IX_CREATEDTIME
from nti.dataserver.users.index import IX_DISPLAYNAME

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

ITEMS = StandardExternalFields.ITEMS


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

    default_origin = 'http://platform.ou.edu'

    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'
    
    course_ntiid2 = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'
        
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
            set_user_creation_site(user, 'platform.ou.edu')
                       
    def _get_course_admins_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        course_admins_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMINS)
        return course_admins_href

 
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_course_admins(self):
        """
        Validate getting an iterable of all course admins (instructors and editors) in a site, including filtering for either
        """ 
        #Site Admin
        test_site_admin_username = u'test_site_admin'
        
        #Normal User
        normal_user_username = u'izuku.midoriya'
        
        #Instructor
        instructor_username = u'shota.aizawa'
        
        #Editor
        editor_username = u'tenya.ida'
        
        #Instructor/Editor
        instructor_and_editor_username = u'toshinori.yagi'
        
        #Instructor created outside site
        outside_site_instructor_username = u'vlad.king'
        
        with mock_dataserver.mock_db_trans(self.ds):
            site_admin = self._create_user(test_site_admin_username)
            normal_user = self._create_user(normal_user_username)
            outside_site_instructor = self._create_user(outside_site_instructor_username)
            set_user_creation_site(site_admin, 'platform.ou.edu')
            set_user_creation_site(normal_user, 'platform.ou.edu')
            set_user_creation_site(outside_site_instructor, 'janux.ou.edu')
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.course_ntiid)
            course_oid = to_external_ntiid_oid(ICourseInstance(entry))
            
        nt_admin_environ = self._make_extra_environ()
        site_admin_environ = self._make_extra_environ(user=test_site_admin_username)
        normal_user_environ = self._make_extra_environ(user=normal_user_username)   
        
        self.create_user(instructor_username)
        self.create_user(editor_username)
        self.create_user(instructor_and_editor_username)

        # Admin links
        course = self.testapp.get('/dataserver2/Objects/%s' % course_oid)
        course_ext = course.json_body
        course_roles_href = self.require_link_href_with_rel(course_ext, VIEW_COURSE_ROLES)
        course_admins_href = self._get_course_admins_href()

        headers = {'accept': str('application/json')}
        data = dict()
        data['roles'] = roles = dict()
        roles['instructors'] = list(['jmadden', 'harp4162', instructor_username, instructor_and_editor_username])
        roles['editors'] = list(['jmadden', 'harp4162', editor_username, instructor_and_editor_username])
        self.testapp.put_json(course_roles_href, data)
        
        #Test permissions
        self.testapp.get(course_admins_href, extra_environ=normal_user_environ, status=403)

        #Test for all course admins using nt super admin
        course_admins = self.testapp.get(course_admins_href, headers=headers, extra_environ=nt_admin_environ)
        res = course_admins.json_body
        usernames = [x['username'] for x in res['Items']]
        assert_that(usernames, has_items(instructor_username,
                                                   instructor_and_editor_username,
                                                   editor_username))
        
        #Test filtering and not filtering instructors not created in site
        roles['instructors'].append(outside_site_instructor_username)
        self.testapp.put_json(course_roles_href, data)
        course_admins = self.testapp.get(course_admins_href, headers=headers, extra_environ=nt_admin_environ)
        res = course_admins.json_body
        usernames = [x['username'] for x in res['Items']]
        assert_that(usernames, not(has_item(outside_site_instructor_username)))
        
        #Check mimetype and user objects
        for item in res['Items']:
            assert_that(item['MimeType'], is_("application/vnd.nextthought.courseadminsummary"))
            assert_that(item['user']['Username'], is_(item['username']))        
        
        #Save list of all course admins in site to compare for sorting
        with mock_dataserver.mock_db_trans(self.ds):
            all_course_admins = [User.get_user(x) for x in usernames]
            all_course_admins.sort(key=lambda x: getattr(x, IX_CREATEDTIME, 0)) #Sorts list of all course admin user objects in this site by createdTime
        
        #Test Sorting
        sorted_usernames = sorted(usernames) #Sorts usernames alphabetically; equivalent to sortOn: displayName, sortOrder: ascending
        
        params = {"sortOn": IX_DISPLAYNAME}
        course_admins = self.testapp.get(course_admins_href, params, headers=headers, extra_environ=site_admin_environ)
        res = course_admins.json_body
        for x in range(len(res['Items'])):
            assert_that(res['Items'][x]['username'], is_(sorted_usernames[x]))
        
        params = {"sortOn": IX_CREATEDTIME}
        course_admins = self.testapp.get(course_admins_href, params, headers=headers, extra_environ=site_admin_environ)
        res = course_admins.json_body
        with mock_dataserver.mock_db_trans(self.ds):
            for x in range(len(res['Items'])):
                assert_that(res['Items'][x]['username'], is_(all_course_admins[x].username))
                
        #Test for just instructors
        params = {"filterEditors": True}
        course_admins = self.testapp.get(course_admins_href, params, headers=headers, extra_environ=site_admin_environ)
        res = course_admins.json_body
        usernames = [x['username'] for x in res['Items']]
        assert_that(usernames, has_items(instructor_username,
                                                   instructor_and_editor_username))
        assert_that(usernames, not(has_items(editor_username)))
        
        #Test for just editors
        params = {"filterInstructors": True}
        course_admins = self.testapp.get(course_admins_href, params, headers=headers, extra_environ=site_admin_environ)
        res = course_admins.json_body
        usernames = [x['username'] for x in res['Items']]
        assert_that(usernames, has_items(editor_username,
                                                    instructor_and_editor_username))
        assert_that(usernames, not(has_items(instructor_username)))
        
        #Test for filtering everything
        params = {"filterInstructors": True, "filterEditors": True}
        course_admins = self.testapp.get(course_admins_href, params, headers=headers, extra_environ=site_admin_environ)
        res = course_admins.json_body
        assert_that(len(res['Items']), is_(0))
        
        # CSV
        params = {'sortOn': 'createdTime'}
        headers = {'accept': str('text/csv')}
        res = self.testapp.get(course_admins_href, params, status=200, headers=headers,
                               extra_environ=site_admin_environ)
        csv_reader = csv.DictReader(StringIO(res.body))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(len(all_course_admins)))
        assert_that(csv_reader, has_items(has_entries('username', instructor_username,
                                                      'username', editor_username,
                                                      'username', instructor_and_editor_username,
                                                      'email', '%s@gmail.com' % instructor_username,
                                                      'email', '%s@gmail.com' % editor_username,
                                                      'email', '%s@gmail.com' % instructor_and_editor_username)))
        
        res = self.testapp.post('%s?format=text/csv&sortOn=createdTime' % course_admins_href,
                                extra_environ=site_admin_environ)
        csv_reader = csv.DictReader(StringIO(res.body))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(len(all_course_admins)))
        assert_that(csv_reader, has_items(has_entries('username', instructor_username,
                                                      'username', editor_username,
                                                      'username', instructor_and_editor_username,
                                                      'email', '%s@gmail.com' % instructor_username,
                                                      'email', '%s@gmail.com' % editor_username,
                                                      'email', '%s@gmail.com' % instructor_and_editor_username)))
        
        usernames = {'usernames': [instructor_username, 'dneusername']}
        res = self.testapp.post_json('%s?format=text/csv&sortOn=createdTime' % course_admins_href,
                                     usernames,
                                     extra_environ=site_admin_environ)
        csv_reader = csv.DictReader(StringIO(res.body))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(1))
        assert_that(csv_reader[0], has_entries('username', instructor_username))
        
        res = self.testapp.post('%s?format=text/csv&sortOn=createdTime' % course_admins_href,
                                params=usernames,
                                content_type='application/x-www-form-urlencoded',
                                extra_environ=site_admin_environ)
        csv_reader = csv.DictReader(StringIO(res.body))
        csv_reader = tuple(csv_reader)
        assert_that(csv_reader, has_length(1))
        assert_that(csv_reader[0], has_entries('username', instructor_username))

        #Restore original instructors and editors
        roles['instructors'] = list(['jmadden', 'harp4162'])
        roles['editors'] = list(['jmadden', 'harp4162'])
        self.testapp.put_json(course_roles_href, data)
        
        
    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_get_courses_administered(self):
        
        #Normal user
        normal_user_username = u'yugi.moto'
        
        #Site Admin
        test_site_admin_username = u'test_site_admin'
        
        #Course Admin
        course_admin_username = u'seto.kaiba'
        
        #Outside site Course Admin
        outside_site_course_admin_username = u'gary.oak'
        
        with mock_dataserver.mock_db_trans(self.ds):
            normal_user = self._create_user(normal_user_username)
            site_admin = self._create_user(test_site_admin_username)
            outside_site_course_admin = self._create_user(outside_site_course_admin_username)
            set_user_creation_site(site_admin, 'platform.ou.edu')
            set_user_creation_site(normal_user, 'platform.ou.edu')
            set_user_creation_site(outside_site_course_admin, 'janux.ou.edu')
        
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            principal_role_manager = IPrincipalRoleManager(getSite())
            principal_role_manager.assignRoleToPrincipal(ROLE_SITE_ADMIN.id,
                                                         test_site_admin_username)
            
            entry = find_object_with_ntiid(self.course_ntiid)
            course_oid = to_external_ntiid_oid(ICourseInstance(entry))
            
            entry2 = find_object_with_ntiid(self.course_ntiid2)
            course_oid2 = to_external_ntiid_oid(ICourseInstance(entry2))
        
        normal_user_environ = self._make_extra_environ(user=normal_user_username)
        site_admin_environ = self._make_extra_environ(user=test_site_admin_username)
        nt_admin_environ = self._make_extra_environ()
           
        self.create_user(course_admin_username)
        course_admin_environ = self._make_extra_environ(user=course_admin_username)
        
        # Admin links
        course = self.testapp.get('/dataserver2/Objects/%s' % course_oid)
        course2 = self.testapp.get('/dataserver2/Objects/%s' % course_oid2)
        course_ext = course.json_body
        course_ext2 = course2.json_body
        course_roles_href = self.require_link_href_with_rel(course_ext, VIEW_COURSE_ROLES)
        course_roles_href2 = self.require_link_href_with_rel(course_ext2, VIEW_COURSE_ROLES)
        #course_admins_href = self._get_course_admins_href()
        
        #headers = {'accept': str('application/json')}
        data = dict()
        data['roles'] = roles = dict()
        roles['instructors'] = list([course_admin_username])
        roles['editors'] = list([])
        
        #Set up instructor
        self.testapp.put_json(course_roles_href, data)
        #course_admins = self.testapp.get(course_admins_href, headers=headers, extra_environ=site_admin_environ)
        #res = course_admins.json_body
        course_admin_href = '/dataserver2/ResolveUser/%s' % course_admin_username
        course_admin_ext = self.testapp.get(course_admin_href)
        course_admin_ext = course_admin_ext.json_body[ITEMS][0]
        courses_administered_href = self.require_link_href_with_rel(course_admin_ext, VIEW_EXPLICTLY_ADMINISTERED_COURSES)
        
        #Test permissions
        self.testapp.get(courses_administered_href, extra_environ=normal_user_environ, status=403)
        self.testapp.get(courses_administered_href, extra_environ=nt_admin_environ)
        self.testapp.get(courses_administered_href, extra_environ=course_admin_environ)
        
        #Test Courses Administered
        courses_administered = self.testapp.get(courses_administered_href, extra_environ=site_admin_environ)
        res = courses_administered.json_body
        assert_that(len(res['Items']), is_(1))
        assert_that(res['Items'], has_item(has_entries('Links', has_item(has_entries('ntiid', self.course_ntiid)))))
        
        #Remove instructor from course and make sure no courses are administered (should 404)
        roles['instructors'] = list([])
        self.testapp.put_json(course_roles_href, data)
        
        courses_administered = self.testapp.get(courses_administered_href, extra_environ=site_admin_environ, status=404)
        
        #Add instructor back to course, plus a second one
        roles['instructors'] = list([course_admin_username])
        self.testapp.put_json(course_roles_href, data)
        self.testapp.put_json(course_roles_href2, data)
        
        courses_administered = self.testapp.get(courses_administered_href, extra_environ=site_admin_environ)
        res = courses_administered.json_body
        assert_that(len(res['Items']), is_(2))
        assert_that(res['Items'], has_item(has_entries('Links', has_item(has_entries('ntiid', self.course_ntiid)),
                                                       'Links', has_item(has_entries('ntiid', self.course_ntiid2)))))
        
        #Test trying to get course admin from outside site
        roles['instructors'] = list([outside_site_course_admin_username])
        self.testapp.put_json(course_roles_href, data)
        self.testapp.get('/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/CourseAdmins/%s/@@CoursesExplicitlyAdministered' % outside_site_course_admin_username,
                          extra_environ=site_admin_environ, status=404)
        
        #Restore original instructors and editors
        roles['instructors'] = list(['jmadden', 'harp4162'])
        roles['editors'] = list(['jmadden', 'harp4162'])
        self.testapp.put_json(course_roles_href, data)