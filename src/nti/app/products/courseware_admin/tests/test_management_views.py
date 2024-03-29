#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_item
from hamcrest import has_items
from hamcrest import not_none
from hamcrest import contains
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import contains_inanyorder
from hamcrest import greater_than_or_equal_to
does_not = is_not

import shutil
import transaction

from six.moves import urllib_parse

from zope import component

from zope.intid.interfaces import IIntIds

from nti.app.contenttypes.presentation import VIEW_CONTENTS
from nti.app.contenttypes.presentation import VIEW_OVERVIEW_CONTENT

from nti.app.products.courseware.views import VIEW_COURSE_ACCESS_TOKENS

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.products.courseware_admin import VIEW_COURSE_EDITORS
from nti.app.products.courseware_admin import VIEW_COURSE_INSTRUCTORS
from nti.app.products.courseware_admin import VIEW_COURSE_ADMIN_LEVELS
from nti.app.products.courseware_admin import VIEW_COURSE_SUGGESTED_TAGS

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.assessment.interfaces import ALL_ASSIGNMENT_MIME_TYPES

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.interfaces import IDelimitedHierarchyContentPackageEnumeration

from nti.contenttypes.completion.interfaces import ICompletableItemDefaultRequiredPolicy

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.contenttypes.courses.index import IX_COURSE_TO_ENTRY_INTID
from nti.contenttypes.courses.index import IX_ENTRY_TO_COURSE_INTID

from nti.contenttypes.courses.index import get_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.contenttypes.courses.utils import get_course_editors

from nti.dataserver.contenttypes.forums.forum import DEFAULT_FORUM_NAME

from nti.dataserver.users.communities import Community

from nti.dataserver.tests import mock_dataserver

from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid


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
            # pylint: disable=no-member
            shutil.rmtree(enumeration.root.absolute_path, True)

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

    def _get_admin_href(self):
        service_res = self.fetch_service_doc()
        workspaces = service_res.json_body['Items']
        courses_workspace = next(
            x for x in workspaces if x['Title'] == 'Courses'
        )
        admin_href = self.require_link_href_with_rel(courses_workspace,
                                                     VIEW_COURSE_ADMIN_LEVELS)
        return admin_href

    def _check_default_forum(self, course_ext):
        """
        Check we have a default forum. Validate we can edit board title/description.
        """
        discussions = course_ext.get('Discussions')
        assert_that(discussions, not_none())
        board_edit_href = self.require_link_href_with_rel(discussions, 'edit')
        contents_href = self.require_link_href_with_rel(discussions, 'contents')
        contents_res = self.testapp.get(contents_href).json_body
        assert_that(contents_res.get('TotalItemCount'), is_(5))
        forums = contents_res.get('Items')
        default_forum = None
        for forum in forums:
            if forum.get('title') == DEFAULT_FORUM_NAME:
                assert_that(default_forum, none())
                default_forum = forum
                assert_that(forum.get('IsDefaultForum'), is_(True))
            else:
                assert_that(forum.get('IsDefaultForum'), is_(False))

        new_board_title = u'new board title'
        new_board_desc = u'new board description'
        res = self.testapp.put_json(board_edit_href, {'title': new_board_title,
                                                      'description': new_board_desc})
        assert_that(res.json_body, has_entries('title', new_board_title,
                                               'description', new_board_desc))

        new_forum_title = u'new forum title'
        new_forum_desc = u'new forum description'
        forum_edit_href = self.require_link_href_with_rel(default_forum, 'edit')
        res = self.testapp.put_json(forum_edit_href, {'title': new_forum_title,
                                                      'description': new_forum_desc})
        assert_that(res.json_body, has_entries('title', new_forum_title,
                                               'description', new_forum_desc))

    def _check_default_outline(self, course_href):
        """
        New courses should have a default outline template
        (see nti.app.contenttypes.presentation.subscribers).
        """
        course = self.testapp.get(course_href).json_body
        outline = course['Outline']
        outline_href = self.require_link_href_with_rel(outline, VIEW_CONTENTS)
        parsed = urllib_parse.urlparse(outline_href)
        parsed = parsed._replace(query="omit_unpublished=False")
        outline_href = parsed.geturl()

        outline_res = self.testapp.get(outline_href)
        outline_res = outline_res.json_body
        assert_that(outline_res, has_length(1))
        unit_node = outline_res[0]
        assert_that(unit_node['title'], is_(u'Unit 1'))
        assert_that(unit_node['PublicationState'], is_('DefaultPublished'))

        lesson_nodes = unit_node['contents']
        assert_that(lesson_nodes, has_length(1))
        lesson_node = lesson_nodes[0]
        assert_that(lesson_node['title'], is_(u'Lesson 1'))
        assert_that(lesson_node['PublicationState'], is_('DefaultPublished'))

        lesson_href = self.require_link_href_with_rel(lesson_node, VIEW_OVERVIEW_CONTENT)
        parsed = urllib_parse.urlparse(lesson_href)
        parsed = parsed._replace(query="omit_unpublished=False")
        lesson_href = parsed.geturl()
        lesson_res = self.testapp.get(lesson_href).json_body

        groups = lesson_res['Items']
        assert_that(groups, has_length(1))
        group = groups[0]
        assert_that(group['title'], is_(u'Section 1'))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_admin_views(self):
        """
        Validate basic admin level management.
        """
        admin_href = self._get_admin_href()
        parents_admin_href = '%s?parents=True' % admin_href
        admin_levels = self.testapp.get(parents_admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        admin_levels = self.testapp.get(admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(0))

        # Create
        test_admin_key = 'TestAdminKey'
        res = self.testapp.post_json(admin_href, {'key': test_admin_key})
        res = res.json_body
        assert_that(res['href'], not_none())
        admin_levels = self.testapp.get(parents_admin_href)
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

        admin_levels = self.testapp.get(parents_admin_href)
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
        parents_admin_href = '%s?parents=True' % admin_href
        admin_levels = self.testapp.get(parents_admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(2))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015'))

        # Create
        test_admin_key = 'TestAdminKey'
        self.testapp.post_json(admin_href, {'key': test_admin_key})
        admin_levels = self.testapp.get(parents_admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        new_admin = admin_levels[ITEMS][test_admin_key]
        new_admin_href = new_admin['href']
        assert_that(new_admin_href, not_none())

        # Sync is ok
        self._sync()
        admin_levels = self.testapp.get(parents_admin_href)
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
        admin_levels = self.testapp.get(parents_admin_href)
        admin_levels = admin_levels.json_body
        assert_that(admin_levels[ITEM_COUNT], is_(3))
        assert_that(admin_levels[ITEMS],
                    contains_inanyorder('Fall2013', 'Fall2015', test_admin_key))

        # Delete
        self.testapp.delete(new_admin_href)
        self.testapp.get(new_admin_href, status=404)

        admin_levels = self.testapp.get(parents_admin_href)
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
        # Our course deletion runs in a greenlet. Since we are not monkey
        # patched here, we temporarily override our transaction manager to
        # be gevent aware.
        from gevent._patcher import import_patched
        manager = import_patched('transaction._manager').module.ThreadTransactionManager()
        old_manager = transaction.manager
        transaction.manager = manager
        try:
            self._do_test_course_views()
        finally:
            transaction.manager = old_manager

    def _do_test_course_views(self):
        """
        Validate basic course management.
        """
        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user('instructor1')
            self._create_user('section_instructor1')
            self._create_user('editor1')

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
        self._check_default_outline(new_course_href)
        self._check_default_forum(new_course)
        self.require_link_href_with_rel(new_course, VIEW_COURSE_ACCESS_TOKENS)
        course_delete_href = self.require_link_href_with_rel(new_course,
                                                             'delete')
        assert_that(new_course_href, not_none())
        assert_that(new_course[CLASS], is_('CourseInstance'))
        assert_that(new_course[MIMETYPE],
                    is_('application/vnd.nextthought.courses.courseinstance'))
        assert_that(new_course['NTIID'], not_none())
        assert_that(new_course['TotalEnrolledCount'], is_(0))
        assert_that(new_course['ContentPackageBundle']['title'], is_(new_course_title))

        with mock_dataserver.mock_db_trans(self.ds):
            # Validate index mapping after creation
            intids = component.getUtility(IIntIds)
            courses_catalog = get_courses_catalog()
            course = find_object_with_ntiid(new_course.get('OID'))
            idx1 = courses_catalog.get(IX_COURSE_TO_ENTRY_INTID)
            idx2 = courses_catalog.get(IX_ENTRY_TO_COURSE_INTID)
            rs = idx2.apply({'any_of': (course._ds_intid,)})
            assert_that(rs, has_length(1))
            entry = ICourseCatalogEntry(course)
            assert_that(intids.queryObject(rs[0]), is_(entry))
            rs = idx1.apply({'any_of': (entry._ds_intid,)})
            assert_that(rs, has_length(1))
            assert_that(intids.queryObject(rs[0]), is_(course))

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

        # Add editor and instructor
        editor_href = self.require_link_href_with_rel(new_course,
                                                      VIEW_COURSE_EDITORS)

        instructor_href = self.require_link_href_with_rel(new_course,
                                                          VIEW_COURSE_INSTRUCTORS)
        self.testapp.post_json(instructor_href, {'user': 'instructor1'})
        self.testapp.post_json(editor_href, {'user': 'editor1'})

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

            # Default Assignemnts are required
            policy = ICompletableItemDefaultRequiredPolicy(course_object)
            assert_that(policy.mime_types, has_length(3))
            assert_that(policy.mime_types, has_items(*tuple(ALL_ASSIGNMENT_MIME_TYPES)))

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
        self.testapp.post_json(
            new_admin_href, {'ProviderUniqueID': 'id001'}, status=422)
        self.testapp.post_json(new_admin_href, {'title': 'id001'}, status=422)

        # Not sure this is externalized like we want.
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, has_item(new_course_key))

        # Create subinstance
        subinstances_href = '%s/SubInstances' % new_course_href
        section_course = self.testapp.post_json(subinstances_href,
                                                {'ProviderUniqueID': 'section 001',
                                                 'title': 'SectionTitle',
                                                 'RichDescription': 'SectionDesc'})

        section_course = section_course.json_body
        section_course_href = section_course['href']
        assert_that(section_course_href, not_none())

        catalog = self.testapp.get('%s/CourseCatalogEntry' % section_course_href)
        catalog = catalog.json_body
        section_entry_ntiid = catalog['NTIID']
        assert_that(section_entry_ntiid, not_none())
        assert_that(section_entry_ntiid, is_not(entry_ntiid))
        assert_that(catalog['ProviderUniqueID'], is_('section 001'))
        assert_that(catalog['title'], is_('SectionTitle'))
        assert_that(catalog['RichDescription'], is_('SectionDesc'))

        # Verify default assignments
        new_section_course_ntiid = section_course['NTIID']
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            section_course_object = find_object_with_ntiid(new_section_course_ntiid)

            policy = ICompletableItemDefaultRequiredPolicy(section_course_object)
            assert_that(policy.mime_types, has_length(3))
            assert_that(policy.mime_types, has_items(*tuple(ALL_ASSIGNMENT_MIME_TYPES)))
            assert_that(policy.child_policy.mime_types, has_length(0))
            assert_that(policy.parent_policy.mime_types, has_length(3))
            assert_that(policy.parent_policy.mime_types, has_items(*tuple(ALL_ASSIGNMENT_MIME_TYPES)))

        # Section 2 with instructors
        section_course = self.testapp.post_json(subinstances_href,
                                                {'ProviderUniqueID': 'section 002',
                                                 'title': 'SectionTitle2',
                                                 'copy_roles': 'true',
                                                 'RichDescription': 'SectionDesc2'})

        section_course = section_course.json_body
        section_course_href2 = section_course['href']
        assert_that(section_course_href, not_none())

        catalog = self.testapp.get('%s/CourseCatalogEntry' % section_course_href2)
        catalog = catalog.json_body
        section_entry_ntiid2 = catalog['NTIID']
        assert_that(section_entry_ntiid2, not_none())
        assert_that(section_entry_ntiid2, is_not(entry_ntiid))
        assert_that(section_entry_ntiid2, is_not(section_entry_ntiid))

        # Validate instructors/editors copy
        inst_environ = self._make_extra_environ('instructor1')
        section2_inst_environ = self._make_extra_environ('section_instructor1')
        editor_environ = self._make_extra_environ('editor1')
        res = self.testapp.get(section_course_href,
                               extra_environ=inst_environ)
        self.forbid_link_with_rel(res.json_body, VIEW_COURSE_INSTRUCTORS)

        res = self.testapp.get(section_course_href,
                               extra_environ=editor_environ)
        self.forbid_link_with_rel(res.json_body, VIEW_COURSE_EDITORS)

        res = self.testapp.get(section_course_href2,
                               extra_environ=inst_environ)
        section2_instr_href = self.require_link_href_with_rel(res.json_body,
                                                             VIEW_COURSE_INSTRUCTORS)

        res = self.testapp.get(section_course_href2,
                               extra_environ=editor_environ)
        self.require_link_href_with_rel(res.json_body, VIEW_COURSE_EDITORS)

        # Parent course entry ntiid and instructors/editors
        with mock_dataserver.mock_db_trans(self.ds, site_name='janux.ou.edu'):
            course_object = find_object_with_ntiid(new_course_ntiid)
            assert_that(INonPublicCourseInstance.providedBy(course_object))
            catalog_entry = ICourseCatalogEntry(course_object)
            assert_that(INonPublicCourseInstance.providedBy(catalog_entry))
            entry = find_object_with_ntiid(entry_ntiid)
            assert_that(entry.ntiid, is_(catalog_entry_ntiid))

            section1 = find_object_with_ntiid(section_entry_ntiid)
            section1 = ICourseInstance(section1)
            section2 = find_object_with_ntiid(section_entry_ntiid2)
            section2 = ICourseInstance(section2)
            assert_that(course_object.instructors, has_length(1))
            assert_that(section1.instructors, has_length(0))
            assert_that(section2.instructors, has_length(1))

            assert_that(get_course_editors(course_object), has_length(1))
            assert_that(get_course_editors(section1), has_length(0))
            assert_that(get_course_editors(section2), has_length(1))

        # Disable the catalog entry
        new_course_entry_href = '%s/CourseCatalogEntry' % new_course_href
        res = self.testapp.put_json(new_course_entry_href, {'is_non_public': True})

        # Section instr can access parent course
        self.testapp.post_json(section2_instr_href, {'user': 'section_instructor1'})
        self.testapp.get(new_course_entry_href, extra_environ=inst_environ)
        self.testapp.get(new_course_entry_href, extra_environ=section2_inst_environ)

        # Delete sections
        self.testapp.delete(section_course_href)
        self.testapp.delete(section_course_href2)
        res = self.testapp.get(subinstances_href).json_body
        assert_that(res.get('Items'), none())

        # After deleting section, section instr can no longer access parent course entry
        # (but instr in both courses can).
        self.testapp.get(new_course_entry_href, extra_environ=inst_environ)
        self.testapp.get(new_course_entry_href, extra_environ=section2_inst_environ, status=403)

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
        assert_that(catalog_collections,
                    has_length(greater_than_or_equal_to(2)))
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
        tags = [u'DELTA', u'alpha', u'alph', u'BETA',
                u'gaMMA', u'omega', u'law', u'LAW', u'.hidden']
        lower_tag_set = {x.lower() for x in tags}
        tag_count = len(lower_tag_set)
        # We now return hidden tags
        non_hidden_tag_count = tag_count
        entry = self.testapp.put_json(entry_href, {"tags": tags})
        entry = entry.json_body
        assert_that(entry,
                    has_entry('tags', contains_inanyorder(*lower_tag_set)))

        courses_collection = self._get_catalog_collection()
        tag_url = self.require_link_href_with_rel(courses_collection,
                                                  VIEW_COURSE_SUGGESTED_TAGS)
        tags = self.testapp.get(tag_url).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(non_hidden_tag_count))
        assert_that(tags, contains(has_entries('count', 3, 'tag', '.hidden'),
                                   has_entries('count', 3, 'tag', u'alph'),
                                   has_entries('count', 3, 'tag', u'alpha'),
                                   has_entries('count', 3, 'tag', u'beta'),
                                   has_entries('count', 3, 'tag', u'delta'),
                                   has_entries('count', 3, 'tag', u'gamma'),
                                   has_entries('count', 3, 'tag', u'law'),
                                   has_entries('count', 3, 'tag', u'omega')))

        tags = self.testapp.get('%s?filter=%s' % (tag_url, 'ALPH')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(2))
        tags = [x.get('tag') for x in tags]
        assert_that(tags, contains(u'alph', u'alpha'))

        # startswith comes first
        tags = self.testapp.get('%s?filter=%s' % (tag_url, 'a')).json_body
        tags = tags[ITEMS]
        assert_that(tags, has_length(non_hidden_tag_count - 1))
        starts_with = tags[:2]
        starts_with = [x.get('tag') for x in starts_with]
        other = tags[2:]
        other = [x.get('tag') for x in other]
        assert_that(starts_with, contains(u'alph', u'alpha'))
        assert_that(other,
                    contains_inanyorder(u'beta', u'delta', u'gamma', u'law', u'omega'))

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
        assert_that(res['tags'], has_length(non_hidden_tag_count - 1))

        # Validation
        tags = ('too_long' * 50,)
        self.testapp.put_json(entry_href, {"tags": tags}, status=422)


    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_enrollment_visibility(self):
        """
        Test catalog entry enrollment visiblity.
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
        new_course_title = 'CommunityRestricted'
        new_course_desc = 'rich description'
        courses = self.testapp.get(new_admin_href)
        assert_that(courses.json_body, does_not(has_item(new_course_key)))

        # Create course
        new_course = self.testapp.post_json(new_admin_href,
                                            {'ProviderUniqueID': new_course_key,
                                             'title': new_course_title,
                                             'RichDescription': new_course_desc})
        course_href = new_course.json_body.get('href')
        assert_that(course_href, not_none())

        entry_href = '%s/CourseCatalogEntry' % course_href
        entry_res = self.testapp.get(entry_href).json_body
        entry_ntiid = entry_res.get('NTIID')
        assert_that(entry_ntiid, not_none())

        with mock_dataserver.mock_db_trans(self.ds):
            self._create_user(u'marco')
            community_member = self._create_user(u'alana')
            new_community = Community.create_community(username='law_community')
            new_community._note_member(community_member)
            community_member.record_dynamic_membership(new_community)
            community_member.follow(new_community)
            community_ntiid = to_external_ntiid_oid(new_community)

        # Visible only to our new community
        res = self.testapp.put_json(entry_href,
                                    {'AvailableToEntityNTIIDs': [community_ntiid,]})
        res = res.json_body
        assert_that(res.get('AvailableToEntityNTIIDs'), has_length(1))
        assert_that(res.get('AvailableToEntityNTIIDs'), contains(community_ntiid))

        non_community_user_environ = self._make_extra_environ(username='marco')
        community_user_environ = self._make_extra_environ(username='alana')

        # Non public instances are unavailable to everyone
        self.testapp.post_json('/dataserver2/users/marco/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=non_community_user_environ,
                               status=403)

        self.testapp.post_json('/dataserver2/users/alana/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=community_user_environ,
                               status=403)

        # Now public and available to community member
        res = self.testapp.put_json(entry_href,
                                    {'is_non_public': False})

        res = self.testapp.get("/dataserver2/users/marco/Courses/AllCourses",
                               extra_environ=non_community_user_environ)
        res = [x['NTIID'] for x in res.json_body['Items']]
        assert_that(res, does_not(has_item(entry_ntiid)))

        res = self.testapp.get("/dataserver2/users/alana/Courses/AllCourses",
                               extra_environ=community_user_environ)
        res = [x['NTIID'] for x in res.json_body['Items']]
        assert_that(res, has_item(entry_ntiid))

        self.testapp.post_json('/dataserver2/users/marco/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=non_community_user_environ,
                               status=403)

        self.testapp.post_json('/dataserver2/users/alana/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=community_user_environ)

        # Remove
        res = self.testapp.put_json(entry_href,
                                    {'AvailableToEntityNTIIDs': []})
        res = res.json_body
        assert_that(res.get('AvailableToEntityNTIIDs'), has_length(0))

        # Available to all
        self.testapp.post_json('/dataserver2/users/marco/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=non_community_user_environ)

        self.testapp.post_json('/dataserver2/users/alana/Courses/EnrolledCourses',
                               entry_ntiid,
                               extra_environ=community_user_environ)


class TestDeleteAllCourses(ApplicationLayerTest):
    """
    Test deleting all section. We do not want to do this in janux and
    remove actual testable section courses.

    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://alpha.nextthought.com'

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def tearDown(self):
        """
        Our alpha site should not have an admin level
        """
        with mock_dataserver.mock_db_trans(site_name='alpha.nextthought.com'):
            library = component.getUtility(IContentPackageLibrary)
            enumeration = IDelimitedHierarchyContentPackageEnumeration(library)
            # pylint: disable=no-member
            shutil.rmtree(enumeration.root.absolute_path, True)

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

        # Create subinstance
        subinstances_href = '%s/SubInstances' % new_course_href
        section_course = self.testapp.post_json(subinstances_href,
                                                {'ProviderUniqueID': 'section 001',
                                                 'title': 'SectionTitle',
                                                 'RichDescription': 'SectionDesc'})

        section_course = section_course.json_body
        section_course_href = section_course['href']
        assert_that(section_course_href, not_none())

        # Section 2 with instructors
        section_course = self.testapp.post_json(subinstances_href,
                                                {'ProviderUniqueID': 'section 002',
                                                 'title': 'SectionTitle2',
                                                 'copy_roles': 'true',
                                                 'RichDescription': 'SectionDesc2'})

        section_course = section_course.json_body
        section_course_href2 = section_course['href']
