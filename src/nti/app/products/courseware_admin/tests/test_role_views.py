#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_string
from hamcrest import contains_inanyorder
does_not = is_not

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin import VIEW_COURSE_ROLES
from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses import ROLE_INFO_NAME

from nti.contenttypes.courses._role_parser import fill_roles_from_key

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.tests import mock_dataserver

from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid

ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestRoleViews(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    enrolled_courses_href = '/dataserver2/users/%s/Courses/EnrolledCourses'
    admin_courses_href = '/dataserver2/users/%s/Courses/AdministeredCourses'
    course_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2013_CLC3403_LawAndJustice'

    def _sync(self):
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            course_catalog = component.getUtility(ICourseCatalog)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            enumeration_root = enumeration.root

            name = course_catalog.__name__
            # pylint: disable=no-member
            courses_bucket = enumeration_root.getChildNamed(name)
            synchronize_catalog_from_root(course_catalog, courses_bucket)

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

    def create_user(self, username):
        with mock_dataserver.mock_db_trans(self.ds):
            user = self._create_user(username)
            IUserProfile(user).email = '%s@gmail.com' % username

    def _get_course_package_hrefs(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course = find_object_with_ntiid(self.course_oid)
            packages = get_course_packages(course)
            ntiids = (x.ntiid for x in packages)
            return ['/dataserver2/Objects/%s' % x for x in ntiids]

    def _validate_manage_links(self,
                               env=None,
                               has_instructor_links=False,
                               has_editor_links=False):
        inst_test = self.require_link_href_with_rel if has_instructor_links else self.forbid_link_with_rel
        editor_test = self.require_link_href_with_rel if has_editor_links else self.forbid_link_with_rel
        course_ext = self._get_course_ext(env)
        for rel in (VIEW_COURSE_INSTRUCTORS, VIEW_COURSE_REMOVE_INSTRUCTORS):
            inst_test(course_ext, rel)

        for rel in (VIEW_COURSE_EDITORS, VIEW_COURSE_EDITORS):
            editor_test(course_ext, rel)

    def _sync_instructors(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course = find_object_with_ntiid(self.course_oid)
            role_json_key = course.root.getChildNamed(ROLE_INFO_NAME)
            result = fill_roles_from_key(course, role_json_key, force=True)
            assert_that(result, is_(True), 'Instructors did not sync')

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_roles(self):
        """
        Validate basic course role management: adding, removing, syncing.
        """
        # Instructor (was enrolled)
        self.create_user(u'ampersand')
        amp_environ = self._make_extra_environ('ampersand')
        self.testapp.post_json(self.enrolled_courses_href % 'ampersand',
                               self.course_ntiid,
                               extra_environ=amp_environ)
        self._validate_manage_links(amp_environ)

        # Editor
        self.create_user(u'three-fifty-five')
        three_environ = self._make_extra_environ('three-fifty-five')
        self._validate_manage_links(three_environ)

        # Neither
        self.create_user(u'hero.brown')
        hero_environ = self._make_extra_environ('hero.brown')
        self._validate_manage_links(hero_environ)

        # Both
        self.create_user(u'yorick.brown')
        yorick_environ = self._make_extra_environ('yorick.brown')
        self._validate_manage_links(yorick_environ)

        package_hrefs = self._get_course_package_hrefs()

        # Admin links
        course = self._get_course_ext()
        roles_href = self.require_link_href_with_rel(course,
                                                     VIEW_COURSE_ROLES)

        self.require_link_href_with_rel(course, VIEW_COURSE_EDITORS)

        instructor_href = self.require_link_href_with_rel(course,
                                                          VIEW_COURSE_INSTRUCTORS)

        self.require_link_href_with_rel(course,
                                        VIEW_COURSE_REMOVE_EDITORS)

        self.require_link_href_with_rel(course, VIEW_COURSE_REMOVE_INSTRUCTORS)

        # Validate base state (no admin courses/enrollment)
        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
                              ('yorick.brown', yorick_environ),
                              ('three-fifty-five', three_environ)):

            for rel in (VIEW_COURSE_ROLES,
                        VIEW_COURSE_EDITORS,
                        VIEW_COURSE_INSTRUCTORS,
                        VIEW_COURSE_REMOVE_EDITORS,
                        VIEW_COURSE_REMOVE_INSTRUCTORS):
                course_ext = self._get_course_ext(env)
                self.forbid_link_with_rel(course_ext, rel)

            admin_courses = self.testapp.get(self.admin_courses_href % username,
                                             extra_environ=env)
            admin_courses = admin_courses.json_body
            assert_that(admin_courses[ITEMS], has_length(0))

            enroll_courses = self.testapp.get(self.enrolled_courses_href % username,
                                              extra_environ=env)
            enroll_courses = enroll_courses.json_body
            if username == 'ampersand':
                assert_that(enroll_courses[ITEMS], has_length(1))
                for package_href in package_hrefs:
                    self.testapp.get(package_href, extra_environ=env)
            else:
                assert_that(enroll_courses[ITEMS], has_length(0))
                for package_href in package_hrefs:
                    self.testapp.get(package_href,
                                     extra_environ=env,
                                     status=403)

        def _get_names(role_name):
            result = self.testapp.get(roles_href)
            result = result.json_body
            usernames = []
            for ext_user in result.get('roles', {}).get(role_name, {}).get(ITEMS, []):
                username = ext_user['Username']
                if username in ('ampersand', 'hero.brown',
                                'yorick.brown', 'three-fifty-five'):
                    user_email = '%s@gmail.com' % username
                    assert_that(ext_user, has_entry('email', user_email))
                usernames.append(username)
            return usernames

        def _instructor_names():
            return _get_names('instructors')

        def _editor_names():
            return _get_names('editors')

        update_marker = object()
        def _update_roles(instructors=update_marker, editors=update_marker):
            data = dict()
            data['roles'] = roles = dict()
            if instructors is not update_marker:
                roles['instructors'] = list(instructors) if instructors else instructors
            if editors is not update_marker:
                roles['editors'] = list(editors) if editors else editors
            self.testapp.put_json(roles_href, data)

        # Error handling; bad input, non-existent user
        self.testapp.post_json(instructor_href, status=422)
        self.testapp.post_json(instructor_href,
                               {'user': 'does-not-exist'},
                               status=422)

        # Add instructor (twice is ok)
        instructors = _instructor_names()
        assert_that(instructors, has_length(2))
        _update_roles(instructors=['jmadden', 'harp4162', 'ampersand'])
        _update_roles(instructors=['jmadden', 'harp4162', 'ampersand'])
        instructors = _instructor_names()
        assert_that(instructors, has_length(3))
        assert_that(instructors,
                    contains_inanyorder('jmadden', 'harp4162', 'ampersand'))
        self._validate_manage_links(amp_environ, has_instructor_links=True)

        # Add editor (twice is ok)
        editors = _editor_names()
        assert_that(editors, has_length(2))
        _update_roles(editors=['jmadden', 'harp4162', 'three-fifty-five'])
        _update_roles(editors=['jmadden', 'harp4162', 'three-fifty-five'])
        editors = _editor_names()
        assert_that(editors, has_length(3))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162', 'three-fifty-five'))
        self._validate_manage_links(three_environ, has_editor_links=True)

        # Add instructor/editor user
        _update_roles(instructors=['jmadden', 'harp4162', 'ampersand', 'yorick.brown'],
                      editors=['jmadden', 'harp4162', 'three-fifty-five', 'yorick.brown'])
        instructors = _instructor_names()
        assert_that(instructors, has_length(4))
        assert_that(instructors,
                    contains_inanyorder('jmadden', 'harp4162',
                                        'yorick.brown', 'ampersand'))
        editors = _editor_names()
        assert_that(editors, has_length(4))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162',
                                        'yorick.brown', 'three-fifty-five'))
        self._validate_manage_links(yorick_environ,
                                    has_instructor_links=True,
                                    has_editor_links=True)

        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
                              ('yorick.brown', yorick_environ),
                              ('three-fifty-five', three_environ)):
            admin_courses = self.testapp.get(self.admin_courses_href % username,
                                             extra_environ=env)
            admin_courses = admin_courses.json_body
            if username == 'hero.brown':
                assert_that(admin_courses[ITEMS], has_length(0))
                for package_href in package_hrefs:
                    self.testapp.get(package_href, extra_environ=env,
                                     status=403)
            else:
                assert_that(admin_courses[ITEMS], has_length(1))
                for package_href in package_hrefs:
                    self.testapp.get(package_href, extra_environ=env)

            enroll_courses = self.testapp.get(self.enrolled_courses_href % username,
                                              extra_environ=env)
            enroll_courses = enroll_courses.json_body
            assert_that(enroll_courses[ITEMS], has_length(0))

        # Get all roles
        href = '/dataserver2/CourseAdmin/@@course_roles'
        res = self.testapp.get(href)
        assert_that(res.body,
                    contains_string('three-fifty-five,three-fifty-five@gmail.com,Law and Justice'))
        assert_that(res.body,
                    contains_string('ampersand,ampersand@gmail.com,Law and Justice'))

        # Syncing does not change state
        self._sync_instructors()
        instructors = _instructor_names()
        assert_that(instructors, has_length(4))
        assert_that(instructors,
                    contains_inanyorder('jmadden', 'harp4162',
                                        'yorick.brown', 'ampersand'))
        editors = _editor_names()
        assert_that(editors, has_length(4))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162',
                                        'yorick.brown', 'three-fifty-five'))

        # Remove instructor/editor
        _update_roles(instructors=['jmadden', 'harp4162', 'ampersand'])
        instructors = _instructor_names()
        assert_that(instructors, has_length(3))
        assert_that(instructors,
                    contains_inanyorder('jmadden', 'harp4162', 'ampersand'))
        editors = _editor_names()
        assert_that(editors, has_length(4))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162',
                                        'yorick.brown', 'three-fifty-five'))
        self._validate_manage_links(yorick_environ, has_editor_links=True)
        # Still an editor; so retain package access.
        for package_href in package_hrefs:
            self.testapp.get(package_href, extra_environ=env)
        _update_roles(editors=['jmadden', 'harp4162', 'three-fifty-five'])
        self._validate_manage_links(yorick_environ)
        # Re-add instructor and now remove editor (still have package access)
        _update_roles(instructors=['jmadden', 'harp4162', 'ampersand', 'yorick.brown'],
                      editors=['jmadden', 'harp4162', 'three-fifty-five'])
        self._validate_manage_links(yorick_environ, has_instructor_links=True)
        for package_href in package_hrefs:
            self.testapp.get(package_href, extra_environ=env)

        # Remove instructor
        _update_roles(instructors=['jmadden', 'harp4162'],
                      editors=['jmadden', 'harp4162', 'three-fifty-five'])
        instructors = _instructor_names()
        assert_that(instructors, has_length(2))
        assert_that(instructors, contains_inanyorder('jmadden', 'harp4162'))
        self._validate_manage_links(amp_environ)

        # Remove editor
        _update_roles(instructors=['jmadden', 'harp4162'],
                      editors=['jmadden', 'harp4162'])
        editors = _editor_names()
        assert_that(editors, has_length(2))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162'))
        self._validate_manage_links(three_environ)

        # Everything is gone
        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
                              ('yorick.brown', yorick_environ),
                              ('three-fifty-five', three_environ)):
            admin_courses = self.testapp.get(self.admin_courses_href % username,
                                             extra_environ=env)
            admin_courses = admin_courses.json_body
            assert_that(admin_courses[ITEMS], has_length(0))
            enroll_courses = self.testapp.get(self.enrolled_courses_href % username,
                                              extra_environ=env)
            enroll_courses = enroll_courses.json_body
            assert_that(enroll_courses[ITEMS], has_length(0))
            for package_href in package_hrefs:
                self.testapp.get(package_href, extra_environ=env, status=403)
