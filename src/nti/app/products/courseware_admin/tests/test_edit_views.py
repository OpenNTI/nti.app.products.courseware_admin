#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import contains
from hamcrest import has_entries
from hamcrest import assert_that
from hamcrest import contains_inanyorder

import os
import shutil
import tempfile

import fudge

from nti.app.products.courseware_admin import VIEW_PRESENTATION_ASSETS

from nti.app.products.courseware.tests import PersistentInstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.cabinet.mixins import SourceFile

from nti.contentlibrary.filesystem import FilesystemBucket

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid


class TestCourseEdits(ApplicationLayerTest):
    """
    Test the editing of ICourseCatalogEntries
    """

    layer = PersistentInstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    course_path = '/dataserver2/%2B%2Betc%2B%2Bhostsites/platform.ou.edu/%2B%2Betc%2B%2Bsite/Courses/Fall2015/CS%201323/CourseCatalogEntry'

    entry_ntiid = u'tag:nextthought.com,2011-10:NTI-CourseInfo-Fall2015_CS_1323'

    asset_dir_path = os.path.join(os.path.dirname(__file__),
                                  "presentation-assets")

    def presentation_assets_zip(self, tmpdir=None):
        tmpdir = tmpdir or tempfile.mkdtemp()
        outfile = os.path.join(tmpdir, "assets")
        return shutil.make_archive(outfile, "zip", self.asset_dir_path)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    def test_course_edit(self):
        instructor_environ = self._make_extra_environ()

        res_dict = {}
        res_dict["title"] = "Another Course"
        res_dict["ProviderDepartmentTitle"] = "Department of Austin Graham"
        res_dict["description"] = "Yet another course"

        # Edit the course with the new information,
        res = self.testapp.put_json(self.course_path,
                                    res_dict,
                                    extra_environ=instructor_environ,
                                    status=200)

        assert_that(res.json_body,
                    has_entries("title", "Another Course",
                                "ProviderDepartmentTitle", "Department of Austin Graham",
                                "description", "Yet another course"))

        # valid duration and try again
        res_dict["Duration"] = "16 weeks"
        res = self.testapp.put_json(self.course_path,
                                    res_dict,
                                    extra_environ=instructor_environ)

        # Be sure the new information is contained in the course
        assert_that(res.json_body,
                    has_entries("Duration", 'P112D'))

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):
            entry = find_object_with_ntiid(self.entry_ntiid)
            assert_that(entry.is_locked(), is_(True))

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.contentlibrary.views.bundle_views.get_all_sources',
                 'nti.app.products.courseware_admin.views.edit_views.save_presentation_assets')
    def test_presentation_assets_zip(self, mock_src, mock_save):
        tmpdir = tempfile.mkdtemp()
        try:
            path = self.presentation_assets_zip(tmpdir)
            with open(path, "rb") as fp:
                source = SourceFile(name="assets.zip", data=fp.read())
            mock_src.is_callable().returns({"assets.zip": source})
            mock_save.is_callable().returns(None)

            res_dict = {}
            res_dict["title"] = "Another Course"
            self.testapp.put_json(self.course_path, res_dict, status=200)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @WithSharedApplicationMockDS(testapp=True, users=True)
    @fudge.patch('nti.app.products.courseware_admin.views.edit_views.CatalogEntryPresentationAssetsPutView._get_bucket')
    def test_presentation_assets(self, mock_save_dir):
        """
        Test uploading four set presentation-asset files parses and saves
        correctly to our fudged tmp dir.
        """
        tmpdir = tempfile.mkdtemp()
        bucket = FilesystemBucket(name=u"test")
        bucket.absolute_path = tmpdir
        mock_save_dir.is_callable().returns(bucket)
        try:
            background_key = 'catalog-background'
            promo_key = 'catalog-promo-large'
            cover_key = 'catalog-entry-cover'
            thumbnail_key = 'catalog-entry-thumbnail'
            source_dir = os.path.join(self.asset_dir_path, 'shared', 'v1')
            background_file = os.path.join(source_dir, 'background.png')
            cover_file = os.path.join(source_dir, 'contentpackage-cover-256x156.png')
            promo_file = os.path.join(source_dir, 'contentpackage-landing-232x170.png')
            thumbnail_file = os.path.join(source_dir, 'thumb.png')
            with open(background_file, "rb") as fp:
                background_source = fp.read()
            with open(promo_file, "rb") as fp:
                promo_source = fp.read()
            with open(cover_file, "rb") as fp:
                cover_source = fp.read()
            with open(thumbnail_file, "rb") as fp:
                thumnail_source = fp.read()

            entry_res = self.testapp.get(self.course_path)
            assets_href = self.require_link_href_with_rel(entry_res.json_body,
                                                          VIEW_PRESENTATION_ASSETS)
            self.testapp.put(assets_href,
                             upload_files=[
                                (background_key, background_key, background_source),
                                (promo_key, promo_key, promo_source),
                                (cover_key, cover_key, cover_source)],
                             status=422)

            self.testapp.put(assets_href,
                             upload_files=[
                                (background_key, background_key, background_source),
                                (promo_key, promo_key, promo_source),
                                (cover_key, cover_key, cover_source),
                                (thumbnail_key, thumbnail_key, thumnail_source)])

            # Valdate tree
            image_files = ['background.png',
                           'contentpackage-cover-256x156.png',
                           'contentpackage-landing-232x170.png',
                           'contentpackage-thumb-60x60.png',
                           'course-cover-232x170.png',
                           'course-promo-large-16x9.png']
            assert_that(os.listdir(tmpdir), contains('presentation-assets'))
            assert_that(os.listdir(tmpdir), contains('presentation-assets'))
            asset_dir = os.path.join(tmpdir, 'presentation-assets')
            client_dirs = os.listdir(asset_dir)
            assert_that(client_dirs,
                        contains_inanyorder('shared', 'iPad', 'webapp'))
            for client in client_dirs:
                client_dir = os.path.join(asset_dir, client)
                assert_that(os.listdir(client_dir), contains('v1'))
                version_dir = os.path.join(client_dir, 'v1')
                assert_that(os.listdir(version_dir),
                            contains_inanyorder(*image_files))
                # Validate files and symlinks
                for image_file in image_files:
                    image_path = os.path.join(version_dir, image_file)
                    assert_that(os.path.exists(image_path), is_(True))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
