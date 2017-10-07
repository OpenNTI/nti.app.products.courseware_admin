#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: providers.py 121882 2017-09-18 21:28:16Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.products.courseware_admin import VIEW_ADMIN_IMPORT_COURSE

from nti.appserver._util import link_belongs_to_user

from nti.appserver.workspaces.interfaces import IUserWorkspaceLinkProvider

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.interfaces import IUser

from nti.links.links import Link

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser)
@interface.implementer(IUserWorkspaceLinkProvider)
class _CourseImportLinkProvider(object):

    def __init__(self, user):
        self.user = user

    def links(self, unused_workspace):
        if is_admin_or_site_admin(self.user):
            user = self.user
            link = Link(user, rel=VIEW_ADMIN_IMPORT_COURSE, method='POST')
            link_belongs_to_user(link, user)
            return [link]
        return ()
