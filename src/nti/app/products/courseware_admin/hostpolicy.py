#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: hostpolicy.py 120355 2017-08-23 19:33:13Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.annotation.interfaces import IAnnotations

from zope.component.hooks import getSite

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.courses.interfaces import NTIID_ENTRY_PROVIDER

logger = __import__('logging').getLogger(__name__)


def get_site_provider():
    policy = component.queryUtility(ISitePolicyUserEventListener)
    result = getattr(policy, 'PROVIDER', None)
    if not result:
        annontations = IAnnotations(getSite(), {})
        result = annontations.get('PROVIDER')
    return result or NTIID_ENTRY_PROVIDER
