# -*- coding: utf-8 -*-
"""Hostname-aware site-root dispatcher for migrated IMI sites."""
from plone import api
from Products.Five import BrowserView

from .adminmode import is_admin_request


PUBLIC_VIEWS = {
    'portal': '@@imenik-public',
    'dezurstva': '@@dezurstva-public',
    'kiestra': '@@kiestra-public',
    'preiskave': '@@preiskave_hitro_view',
    'nadomescanja': '@@nadomescanja-public',
}

ADMIN_VIEWS = {
    'portal': '@@imenik-admin',
    'dezurstva': '@@dezurstva-admin',
    'kiestra': '@@kiestra-admin',
    'preiskave': '@@preiskave-admin',
    'nadomescanja': '@@nadomescanja-admin',
}


class SiteHomeView(BrowserView):
    """Render admin or public site home based only on the request hostname."""

    def __call__(self):
        site = api.portal.get()
        if is_admin_request(self.request):
            admin_view = ADMIN_VIEWS.get(site.getId())
            if admin_view:
                return site.restrictedTraverse(admin_view)()

        public_view = PUBLIC_VIEWS.get(site.getId())
        if public_view:
            return site.restrictedTraverse(public_view)()
        return ''
