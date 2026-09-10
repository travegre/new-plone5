# -*- coding: utf-8 -*-
"""Editor-aware site home routing.

The public site root remains the public frontend for anonymous/read-only users.
Editors are redirected to the physical ``admin`` folder so the normal Plone
"Domov" link keeps them inside the administration area.
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
    """Send editors to /admin and everybody else to the public frontend."""

    def __call__(self):
        site = api.portal.get()
        if api.user.has_permission('Modify portal content', obj=site):
            admin = site.get('admin')
            if admin is not None:
                self.request.response.redirect(admin.absolute_url())
                return ''

        public_view = PUBLIC_VIEWS.get(site.getId())
        if public_view:
            return site.restrictedTraverse(public_view)()
        return ''
