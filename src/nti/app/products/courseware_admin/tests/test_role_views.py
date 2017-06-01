#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder
does_not = is_not

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_REMOVE_INSTRUCTORS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.externalization.externalization import to_external_ntiid_oid

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

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
            self._create_user(username)

    def _get_course_package_hrefs(self):
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course = find_object_with_ntiid(self.course_oid)
            packages = get_course_packages(course)
            ntiids = (x.ntiid for x in packages)
            return ['/dataserver2/Objects/%s' % x for x in ntiids]

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_roles(self):
        """
        Validate basic course role management: adding, removing, syncing.

        TODO: Test sync
        """
        # Instructor (was enrolled)
        self.create_user(u'ampersand')
        amp_environ = self._make_extra_environ('ampersand')
        self.testapp.post_json(self.enrolled_courses_href % 'ampersand',
                               self.course_ntiid,
                               extra_environ=amp_environ)
        # Editor
        self.create_user(u'three-fifty-five')
        three_environ = self._make_extra_environ('three-fifty-five')

        # Neither
        self.create_user(u'hero.brown')
        hero_environ = self._make_extra_environ('hero.brown')

        package_hrefs = self._get_course_package_hrefs()

        # Admin links
        course = self._get_course_ext()
        editor_href = self.require_link_href_with_rel(course,
                                                      VIEW_COURSE_EDITORS)

        instructor_href = self.require_link_href_with_rel(course,
                                                          VIEW_COURSE_INSTRUCTORS)

        remove_editor_href = self.require_link_href_with_rel(course,
                                                             VIEW_COURSE_REMOVE_EDITORS)

        remove_instructor_href = self.require_link_href_with_rel(course,
                                                                 VIEW_COURSE_REMOVE_INSTRUCTORS)

        # Validate base state (no admin courses/enrollment)
        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
                              ('three-fifty-five', three_environ)):

            for rel in (VIEW_COURSE_EDITORS,
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

        def _get_names(href):
            result = self.testapp.get(href)
            result = result.json_body
            result = [x['Username'] for x in result[ITEMS]]
            return result

        def _instructor_names():
            return _get_names(instructor_href)

        def _editor_names():
            return _get_names(editor_href)

        # Error handling; bad input, non-existant user
        self.testapp.post_json(instructor_href, status=422)
        self.testapp.post_json(instructor_href, 
                               {'user': 'does-not-exist'}, 
                               status=422)

        # Add instructor (twice is ok)
        instructors = _instructor_names()
        assert_that(instructors, has_length(2))
        self.testapp.post_json(instructor_href, {'user': 'ampersand'})
        self.testapp.post_json(instructor_href, {'user': 'ampersand'})
        instructors = _instructor_names()
        assert_that(instructors, has_length(3))
        assert_that(instructors, 
                    contains_inanyorder('jmadden', 'harp4162', 'ampersand'))

        # Add editor (twice is ok)
        editors = _editor_names()
        assert_that(editors, has_length(2))
        self.testapp.post_json(editor_href, {'user': 'three-fifty-five'})
        self.testapp.post_json(editor_href, {'user': 'three-fifty-five'})
        editors = _editor_names()
        assert_that(editors, has_length(3))
        assert_that(editors,
                    contains_inanyorder('jmadden', 'harp4162', 'three-fifty-five'))

        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
                              ('three-fifty-five', three_environ)):
            admin_courses = self.testapp.get(self.admin_courses_href % username,
                                             extra_environ=env)
            admin_courses = admin_courses.json_body
            if username == 'hero.brown':
                assert_that(admin_courses[ITEMS], has_length(0))
                for package_href in package_hrefs:
                    self.testapp.get(
                        package_href, extra_environ=env, status=403)
            else:
                assert_that(admin_courses[ITEMS], has_length(1))
                for package_href in package_hrefs:
                    self.testapp.get(package_href, extra_environ=env)

            enroll_courses = self.testapp.get(self.enrolled_courses_href % username,
                                              extra_environ=env)
            enroll_courses = enroll_courses.json_body
            assert_that(enroll_courses[ITEMS], has_length(0))

        # Remove instructor
        self.testapp.post_json(remove_instructor_href, {'user': 'ampersand'})
        self.testapp.post_json(remove_instructor_href, {'user': 'ampersand'})
        instructors = _instructor_names()
        assert_that(instructors, has_length(2))
        assert_that(instructors, contains_inanyorder('jmadden', 'harp4162'))

        # Remove editor
        self.testapp.post_json(remove_editor_href, 
                               {'user': 'three-fifty-five'})

        self.testapp.post_json(remove_editor_href, 
                               {'user': 'three-fifty-five'})
        editors = _editor_names()
        assert_that(instructors, has_length(2))
        assert_that(instructors, 
                    contains_inanyorder('jmadden', 'harp4162'))

        # Everything is gone
        for username, env in (('ampersand', amp_environ),
                              ('hero.brown', hero_environ),
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