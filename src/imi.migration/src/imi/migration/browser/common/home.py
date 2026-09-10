# -*- coding: utf-8 -*-
"""Public site-root dispatcher.

Administrative rendering is selected separately by the request browser layer;
this view deliberately contains no editor/user/path-based switching.
"""
from plone import api
from Products.Five import BrowserView


PUBLIC_VIEWS = {
    'portal': '@@imenik-public',
    'dezurstva': '@@dezurstva-public',
    'kiestra': '@@kiestra-public',
    'preiskave': '@@preiskave_hitro_view',
    'nadomescanja': '@@nadomescanja-public',
}


class SiteHomeView(BrowserView):
    """Render the public frontend selected for this migrated site."""

    def __call__(self):
        site = api.portal.get()
        public_view = PUBLIC_VIEWS.get(site.getId())
        if public_view:
            return site.restrictedTraverse(public_view)()
        return ''
