#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid import httpexceptions as hexc

from nti.app.products.courseware_admin import MessageFactory as _

from nti.contenttypes.courses.utils import is_course_editor
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.authorization import is_admin_or_content_admin


class InstructorManageMixin(object):
    """
    Defines who has access to manage instructors in a course. Only instructors
    (including TAs), admins and global editors can currently manage instructor
    access.
    """

    def has_access(self, user, course):
        return is_admin_or_content_admin(user) \
            or is_course_instructor(course, user)

    def require_access(self, user, course):
        if not self.has_access(user, course):
            raise hexc.HTTPForbidden(
                    _("Do not have permission to manage instructors."))


class EditorManageMixin(object):
    """
    Defines who has access to manage instructors in a course. Only course
    editors, admins and global editors can currently manage editors.
    """

    def has_access(self, user, course):
        return is_admin_or_content_admin(user) \
            or is_course_editor(course, user)

    def require_access(self, user, course):
        if not self.has_access(user, course):
            raise hexc.HTTPForbidden(
                    _("Do not have permission to manage editors."))

