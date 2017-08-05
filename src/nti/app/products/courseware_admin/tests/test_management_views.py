#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_item
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import contains_inanyorder
does_not = is_not

import shutil

from zope import component

from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.externalization.interfaces import StandardExternalFields

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

ITEMS = StandardExternalFields.ITEMS
CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class TestCourseManagement(ApplicationLayerTest):

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def tearDown(self):
        """
        Our janux.ou.edu site should have no courses in it.
        """
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            shutil.rmtree(enumeration.root.absolute_path, True)

    def _sync(self):
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            library = component.getUtility(IContentPackageLibrary)
            course_catalog = component.getUtility(ICourseCatalog)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            enumeration_root = enumeration.root

            name = course_catalog.__name__
            courses_bucket = enumeration_root.getChildNamed(name)
            synchronize_catalog_from_root(course_catalog, courses_bucket)

    def _get_admin_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        admin_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMIN_LEVELS)
        return admin_href

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_admin_views(self):
        """
        Validate basic admin level management.
        """
        admin_href = self._get_admin_href()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        # Create
        test_admin_key = 'TestAdminKey'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        # Duplicate
        self.testapp.post_json(admin_href, {'key': test_admin_key}, status=422)

        # Delete
        self.testapp.delete(new_admin_href)
        self.testapp.get(new_admin_href, status=404)

        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_sync(self):
        """
        Validate syncs and admin levels.
        """
        admin_href = self._get_admin_href()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        # Create
        test_admin_key = 'TestAdminKey'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        # Sync is ok
        self._sync()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        # Remove filesystem path and re-sync; no change.
        with mock_dataserver.mock_db_trans(site_name='janux.ou.edu'):
            course_catalog = component.getUtility(ICourseCatalog)
            admin_level = course_catalog[test_admin_key]
            shutil.rmtree(admin_level.root.absolute_path, False)

        self._sync()
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        # Delete
        self.testapp.delete(new_admin_href)
        self.testapp.get(new_admin_href, status=404)

        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

    @WithSharedApplicationMockDS(testapp=True, users=('non_admin_user',))
    def test_permissions(self):
        """
        Validate non-admin access.
        """
        environ = self._make_extra_environ('non_admin_user')
        service_res = self.testapp.get('/dataserver2', extra_environ=environ)
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        self.forbid_link_with_rel(courses_workspace, VIEW_COURSE_ADMIN_LEVELS)

        course_href = '/dataserver2/++etc++hostsites/janux.ou.edu/++etc++site/Courses'
        admin_href = '%s/@@%s' % (course_href, VIEW_COURSE_ADMIN_LEVELS)
        self.testapp.get(admin_href, extra_environ=environ, status=403)
        self.testapp.post_json(admin_href, {'key': 'TestAdminKey'},
                               extra_environ=environ, status=403)

        course_href = '/dataserver2/++etc++hostsites/platform.ou.edu/++etc++site/Courses'
        self.testapp.delete('%s/%s' % (course_href, 'Fall2013'),
                            extra_environ=environ, status=403)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_views(self):
        """
        Validate basic course management.
        """
        admin_href = self._get_admin_href()
        # Create admin level
        test_admin_key = 'TheLastMan'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        new_course_key = 'Yorick'
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, does_not(has_item(new_course_key)))

        # Create course
        new_course = self.testapp.post_json(new_admin_href,
                                            {'course': new_course_key})

        new_course = new_course.json_body
        new_course_href = new_course['href']
        assert_that(new_course_href, not_none())
        assert_that(new_course[CLASS], is_('CourseInstance'))
        assert_that(new_course[MIMETYPE],
                    is_('application/vnd.nextthought.courses.courseinstance'))
        assert_that(new_course['NTIID'], not_none())
        assert_that(new_course['TotalEnrolledCount'], is_(0))

        catalog = self.testapp.get('%s/CourseCatalogEntry' % new_course_href)
        catalog = catalog.json_body
        assert_that(catalog['NTIID'],
                    is_('tag:nextthought.com,2011-10:NTI-CourseInfo-TheLastMan_Yorick'))

        # Verify that this course is non-public.
        new_course_ntiid = new_course['NTIID']
        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            course_object = find_object_with_ntiid(new_course_ntiid)
            assert_that(INonPublicCourseInstance.providedBy(course_object))
            catalog_entry = ICourseCatalogEntry(course_object)
            assert_that(INonPublicCourseInstance.providedBy(catalog_entry))
            catalog_entry_ntiid = catalog_entry.ntiid

        catalog_entry_res = self.testapp.get(
            '/dataserver2/Objects/' + catalog_entry_ntiid)
        assert_that(catalog_entry_res.json, has_entry('is_non_public', True))
        assert_that(new_course, has_entry('is_non_public', True))

        # Idempotent
        self.testapp.post_json(new_admin_href,
                               {'course': new_course_key})

        # XXX: Not sure this is externalized like we want.
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, has_item(new_course_key))

        # Delete
        self.testapp.delete(new_course['href'])
        self.testapp.get(new_course_href, status=404)
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, does_not(has_item(new_course_key)))
        self.testapp.delete(new_admin_href)
