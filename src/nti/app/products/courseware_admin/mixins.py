#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware_admin import MessageFactory as _

from nti.contenttypes.courses.utils import is_course_editor
from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.authorization import is_admin_or_content_admin

logger = __import__('logging').getLogger(__name__)


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
            raise_json_error(get_current_request(),
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Do not have permission to manage instructors."),
                             },
                             None)


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
            raise_json_error(get_current_request(),
                             hexc.HTTPForbidden,
                             {
                                 'message': _(u"Do not have permission to manage editors."),
                             },
                             None)
