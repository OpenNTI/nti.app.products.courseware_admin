#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid.view import view_config

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.event import notify

from nti.app.products.courseware_admin.views.management_views import CreateCourseSubinstanceView

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.common.string import is_true
from nti.common.string import is_false

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_json

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from nti.contenttypes.courses.interfaces import CourseVendorInfoSynchronized

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import ISiteHierarchy

from nti.dataserver.users.communities import Community

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             permission=nauth.ACT_NTI_ADMIN)
class CreateChildSiteSectionCourses(CreateCourseSubinstanceView):
    """
    Creates a section course mapping to each child site below our current site.
    These section courses are visible only to `AvailableToEntityNTIIDs` of the
    child site community.

    This view can be called with GET to simulate the results.

    This view should be idempotent.

    This was originally developed for OPSRC.

    params:
        included_courses - entry ntiids of courses to create child sections

        excluded_courses - entry ntiids of courses to not create child sections

        preview - (default False) create courses in preview mode
    """

    @Lazy
    def parent_course(self):
        return self.context

    @Lazy
    def _course_classifier(self):
        return None

    @Lazy
    def preview(self):
        # pylint: disable=no-member
        result = self._params.get('preview')
        return is_true(result)

    @Lazy
    def non_public(self):
        # pylint: disable=no-member
        result = self._params.get('non_public')
        return not is_false(result)

    @Lazy
    def included_courses(self):
        """
        NTIIDs of courses we want to create sections on.
        """
        result = self._params.get('included_courses')
        return set(result)

    @Lazy
    def excluded_courses(self):
        """
        NTIIDs of courses we do not want to create sections on.
        """
        result = self._params.get('excluded_courses')
        return set(result)

    def _post_create(self, course, section_values, community_ntiid):
        """
        Roll with our own post_create implementation since we have specific
        args to pass to section catalog entry.
        """
        self.do_copy_roles(course)
        catalog_entry = ICourseCatalogEntry(course)
        fill_entry_from_legacy_json(catalog_entry, section_values,
                                    notify=True, delete=False)

        # By default, share with our community ntiid
        vendor = ICourseInstanceVendorInfo(course)
        vendor['NTI']['DefaultSharingScopeNTIID'] = community_ntiid
        notify(CourseVendorInfoSynchronized(course))

        if self.preview:
            catalog_entry.Preview = True
        if self.non_public:
            interface.alsoProvides(course, INonPublicCourseInstance)
            interface.alsoProvides(catalog_entry, INonPublicCourseInstance)
        notify(CourseInstanceAvailableEvent(course))
        return catalog_entry

    def get_child_sites(self):
        site = getSite()
        site_hierarchy_utility = component.getUtility(ISiteHierarchy)
        site_hierarchy = site_hierarchy_utility.tree
        site_node = site_hierarchy.get_node_from_object(site.__name__)
        return site_node.children_objects

    def get_courses(self):
        """
        Retrieve the courses that we need to create section courses for.
        """
        result = []
        catalog = component.getUtility(ICourseCatalog)
        for entry in catalog.iterCatalogEntries():
            if      (   not self.included_courses
                     or entry.ntiid in self.included_courses) \
                and (   not self.excluded_courses
                     or entry.ntiid not in self.excluded_courses):
                course = ICourseInstance(entry, None)
                if course is not None:
                    result.append(course)
        return result

    def get_child_section_dict(self, course, child_site):
        parent_entry = ICourseCatalogEntry(course)
        child_site_manager = child_site.getSiteManager()
        child_policy = child_site_manager.getUtility(ISitePolicyUserEventListener)
        child_com_username = child_policy.COM_USERNAME
        community = Community.get_community(child_com_username)
        community_ntiid = community.NTIID

        result = dict()
        # XXX: This seems hacky, but not sure of a better way to generate these
        parent_site_name = getSite().__name__
        if parent_site_name in child_com_username:
            puid_suffix = child_com_username.replace('-%s' % parent_site_name, '')
        else:
            puid_suffix = child_policy.COM_ALIAS
        puid_suffix = puid_suffix.upper()
        new_puid = '%s-%s' % (parent_entry.ProviderUniqueID, puid_suffix)
        new_puid = new_puid[:32]

        result['ProviderUniqueID'] = new_puid
        result['title'] = parent_entry.title
        result['RichDescription'] = parent_entry.RichDescription
        result['AvailableToEntityNTIIDs'] = [community_ntiid]
        return result, community_ntiid

    def need_to_create_child_site_section(self, community_ntiid, course):
        """
        We do not need to create the child section course if our
        child site community_ntiid is already in a section course's
        AvailableToEntityNTIIDs field.
        """
        for course_section in course.SubInstances.values():
            if community_ntiid in ICourseCatalogEntry(course_section).AvailableToEntityNTIIDs:
                # We already created this section course.
                return False
        return True

    def _do_call(self):
        # Gather all child site information
        # Check if section course already exists for that child site
        result = LocatedExternalDict()
        # Return a dict of child_site -> [parent_entry_ntiids_of_created_sections]
        result[ITEMS] = items = {}
        courses_created = 0
        courses = self.get_courses()
        for child_site in self.get_child_sites():
            for course in courses:
                new_entry_dict, community_ntiid = self.get_child_section_dict(course, child_site)
                if not self.need_to_create_child_site_section(community_ntiid, course):
                    continue
                courses_created += 1
                course = self._create_course(self.parent_course)
                entry = self._post_create(course, new_entry_dict, community_ntiid)
                parent_ntiid = ICourseCatalogEntry(self.parent_course).ntiid
                logger.info('[%s] Creating child site section (parent=%s) (ntiid=%s) (key=%s)',
                            child_site.__name__,
                            parent_ntiid,
                            entry.ntiid,
                            course.__name__)
                created_courses = items.setdefault(child_site.__name__, [])
                created_courses.append(parent_ntiid)
        result['TotalSiteCount'] = len(items)
        result['TotalCourseCreatedCount'] = courses_created
        return course

