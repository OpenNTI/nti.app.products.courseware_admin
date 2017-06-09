#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from nti.app.externalization.error import raise_json_error

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


def tx_string(s):
    if s and isinstance(s, six.text_type):
        s = s.encode('utf-8')
    return s


def parse_user(values, request=None):
    request = request or get_current_request()
    username = values.get('username') or values.get('user')
    if not username:
        raise_json_error(request,
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': "No username.",
                         },
                         None)

    user = User.get_user(username)
    if not user or not IUser.providedBy(user):
        raise_json_error(request,
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': "User not found.",
                         },
                         None)

    return username, user


def parse_courses(values, request=None):
    request = request or get_current_request()
    ntiids = values.get('ntiid') or values.get('ntiids')
    if not ntiids:
        raise_json_error(request,
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': "No course entry identifier.",
                         },
                         None)

    if isinstance(ntiids, six.string_types):
        ntiids = ntiids.split()

    result = []
    for ntiid in ntiids:
        context = find_object_with_ntiid(ntiid)
        if not ILegacyCourseInstance.providedBy(context):
            context = ICourseCatalogEntry(context, None)
        if context is not None:
            result.append(context)
    return result


def parse_course(values, request=None):
    request = request or get_current_request()
    result = parse_courses(values, request)
    if not result:
        raise_json_error(request,
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': "Course not found.",
                         },
                         None)
    return result[0]
