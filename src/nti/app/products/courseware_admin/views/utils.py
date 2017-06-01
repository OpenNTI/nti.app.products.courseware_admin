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

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid


def tx_string(s):
    if s and isinstance(s, six.text_type):
        s = s.encode('utf-8')
    return s


def parse_user(values):
    username = values.get('username') or values.get('user')
    if not username:
        raise hexc.HTTPUnprocessableEntity(detail='No username')

    user = User.get_user(username)
    if not user or not IUser.providedBy(user):
        raise hexc.HTTPUnprocessableEntity(detail='User not found')

    return username, user


def parse_courses(values):
    # get validate course entry
    ntiids = values.get('ntiid') or values.get('ntiids')
    if not ntiids:
        raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

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


def parse_course(values):
    result = parse_courses(values)
    if not result:
        raise hexc.HTTPUnprocessableEntity(detail='Course not found')
    return result[0]
