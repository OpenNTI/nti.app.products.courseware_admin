#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import greater_than_or_equal_to
does_not = is_not

import shutil

from zope import component

from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin import VIEW_COURSE_SUGGESTED_TAGS

from nti.app.products.courseware.views import VIEW_COURSE_ACCESS_TOKENS

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

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
        res = self.testapp.post_json(admin_href, {'key': test_admin_key})
        res = res.json_body
        assert_that(res['href'], not_none())
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
        new_course_title = 'The Last Man'
        new_course_desc = 'rich description'
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, does_not(has_item(new_course_key)))

        # Create course
        new_course = self.testapp.post_json(new_admin_href,
                                            {'ProviderUniqueID': new_course_key,
                                             'title': new_course_title,
                                             'RichDescription': new_course_desc})

        new_course = new_course.json_body
        new_course_href = new_course['href']
        course_token_href = self.require_link_href_with_rel(new_course,
                                                            VIEW_COURSE_ACCESS_TOKENS)
        course_delete_href = self.require_link_href_with_rel(new_course,
                                                             'delete')
        assert_that(new_course_href, not_none())
        assert_that(new_course[CLASS], is_('CourseInstance'))
        assert_that(new_course[MIMETYPE],
                    is_('application/vnd.nextthought.courses.courseinstance'))
        assert_that(new_course['NTIID'], not_none())
        assert_that(new_course['TotalEnrolledCount'], is_(0))

        # Has an invitation
        tokens = self.testapp.get(course_token_href)
        tokens = tokens.json_body
        tokens = tokens[ITEMS]
        assert_that(tokens, has_length(1))
        token = tokens[0]
        assert_that(token.get('Code'), not_none())
        assert_that(token.get('MimeType'), not_none())
        assert_that(token.get('Scope'), not_none())

        catalog = self.testapp.get('%s/CourseCatalogEntry' % new_course_href)
        catalog = catalog.json_body
        entry_ntiid = catalog['NTIID']
        assert_that(entry_ntiid, not_none())
        # GUID NTIID
        assert_that(entry_ntiid,
                    is_not('tag:nextthought.com,2011-10:NTI-CourseInfo-TheLastMan_Yorick'))
        assert_that(catalog['ProviderUniqueID'], is_(new_course_key))
        assert_that(catalog['title'], is_(new_course_title))
        assert_that(catalog['RichDescription'], is_(new_course_desc))

        # Verify that this course is non-public.
        new_course_ntiid = new_course['NTIID']
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            course_object = find_object_with_ntiid(new_course_ntiid)
            assert_that(INonPublicCourseInstance.providedBy(course_object))
            catalog_entry = ICourseCatalogEntry(course_object)
            assert_that(INonPublicCourseInstance.providedBy(catalog_entry))
            catalog_entry_ntiid = catalog_entry.ntiid
            # Entry is set up correctly
            entry = find_object_with_ntiid(entry_ntiid)
            assert_that(entry, not_none())
            assert_that(entry.ntiid, is_(entry_ntiid))
            assert_that(entry, is_(catalog_entry))

        catalog_href = '/dataserver2/Objects/' + catalog_entry_ntiid
        catalog_entry_res = self.testapp.get(catalog_href)
        assert_that(catalog_entry_res.json, has_entry('is_non_public', True))
        assert_that(new_course, has_entry('is_non_public', True))

        # Edit catalog entry
        catalog_entry_res = self.testapp.put_json(catalog_href,
                                                  {'title': 'new_title'})
        catalog_entry_res = catalog_entry_res.json_body
        assert_that(catalog_entry_res, has_entry('is_non_public', True))
        assert_that(catalog_entry_res, has_entry('title', 'new_title'))

        # This view will create the course no matter what, in this case by
        # toggling the key.
        res = self.testapp.post_json(new_admin_href,
                                     {'ProviderUniqueID': new_course_key,
                                      'title': 'course title2'})
        res = res.json_body
        new_course_href2 = res['href']
        assert_that(new_course_href2, is_not(new_course_href))
        course_delete_href2 = self.require_link_href_with_rel(res, 'delete')

        catalog = self.testapp.get('%s/CourseCatalogEntry' % new_course_href2)
        catalog = catalog.json_body
        entry_ntiid2 = catalog['NTIID']
        assert_that(entry_ntiid, is_not(entry_ntiid2))
        assert_that(catalog['ProviderUniqueID'], is_(new_course_key))
        assert_that(catalog['title'], is_('course title2'))

        # We at least need the title/ProviderUniqueID to create a course
        self.testapp.post_json(new_admin_href, status=422)
        self.testapp.post_json(new_admin_href, {'ProviderUniqueID': 'id001'}, status=422)
        self.testapp.post_json(new_admin_href, {'title': 'id001'}, status=422)

        # XXX: Not sure this is externalized like we want.
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, has_item(new_course_key))

        # Delete
        self.testapp.delete(course_delete_href)
        self.testapp.get(new_course_href, status=404)
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, does_not(has_item(new_course_key)))
        self.testapp.delete(course_delete_href2)
        self.testapp.get(new_course_href2, status=404)

    def _get_catalog_collection(self, name='Courses'):
        """
        Get the named collection in the `Catalog` workspace in the service doc.
        """
        service_res = self.testapp.get('/dataserver2/service/')
        service_res = service_res.json_body
        workspaces = service_res['Items']
        catalog_ws = next(x for x in workspaces if x['Title'] == 'Catalog')
        assert_that(catalog_ws, not_none())
        catalog_collections = catalog_ws['Items']
        assert_that(catalog_collections, has_length(greater_than_or_equal_to(2)))
        courses_collection = next(
            x for x in catalog_collections if x['Title'] == name
        )
        assert_that(courses_collection, not_none())
        return courses_collection

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_tags(self):
        """
        Validate setting tags on an entry and retrieving suggested tags.
        """
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('non_admin_user')
        user_environ = self._make_extra_environ('non_admin_user')
        # Set tags on an object
        entry_href = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2013/CLC3403_LawAndJustice/CourseCatalogEntry'
        tags = [u'DELTA', u'alpha', u'alph', u'BETA', u'gaMMA', u'omega', u'law', u'LAW', u'.hidden']
        lower_tag_set = {x.lower() for x in tags}
        tag_count = len(lower_tag_set)
        non_hidden_tag_count = tag_count - 1
        entry = self.testapp.put_json(entry_href, {"tags": tags})
        entry = entry.json_body
        assert_that(entry, has_entry('tags', contains_inanyorder(*lower_tag_set)))

        courses_collection = self._get_catalog_collection()
        tag_url = self.require_link_href_with_rel(courses_collection,
                                                  VIEW_COURSE_SUGGESTED_TAGS)
        tags = self.testapp.get(tag_url).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(non_hidden_tag_count))
        assert_that(tags, contains(u'alph', u'alpha', u'beta',
                                   u'delta', u'gamma', u'law', u'omega'))

        tags = self.testapp.get('%s?filter=%s' % (tag_url, 'alph')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(2))
        assert_that(tags, contains(u'alph', u'alpha'))

        # startswith comes first
        tags = self.testapp.get('%s?filter=%s' % (tag_url, 'a')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(non_hidden_tag_count))
        starts_with = tags[:2]
        other = tags[2:]
        assert_that(starts_with, contains(u'alph', u'alpha'))
        assert_that(other, contains_inanyorder(u'beta', u'delta', u'gamma', u'law', u'omega'))

        # Batching
        tags = self.testapp.get('%s?filter=%s&batchStart=0&batchSize=2' % (tag_url, 'a'))
        tags = tags.json_body[ITEMS]
        assert_that(tags, has_length(2))
        assert_that(tags, contains(u'alph', u'alpha'))
        tags = self.testapp.get('%s?filter=%s&batchStart=2&batchSize=10' % (tag_url, 'a'))
        tags = tags.json_body[ITEMS]
        assert_that(tags, has_length(5))
        assert_that(tags, contains_inanyorder(u'beta', u'delta', u'gamma', u'law', u'omega'))


        tags = self.testapp.get('%s?filter=%s' % (tag_url, 'xxx')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(0))
        tags = self.testapp.get('%s?filter=%s&batchStart=0&batchSize=3'
                                % (tag_url, 'xxx')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(0))

        # User tags
        res = self.testapp.get(entry_href, extra_environ=user_environ)
        res = res.json_body
        assert_that(res['tags'], has_length(non_hidden_tag_count))

        # Validation
        tags = ('too_long' * 50,)
        self.testapp.put_json(entry_href, {"tags": tags}, status=422)

