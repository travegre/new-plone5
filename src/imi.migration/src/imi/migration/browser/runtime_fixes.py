# -*- coding: utf-8 -*-
"""Runtime compatibility fixes for migrated legacy public sites.

The Plone 4 skins assumed hard-coded acquisition paths such as
``nastavitve/dezurstva``.  In the multi-site Plone 5 target those names can be
reserved through acquisition and migrated day objects may live at another
preserved path.  Public views should therefore locate their typed content via
the site catalog instead of depending on one physical folder name.
"""
from Acquisition import aq_parent

from .legacy_sites import KiestraPublicView as BaseKiestraPublicView
from .legacy_sites import ReplacementsPublicView as BaseReplacementsPublicView


def _brains(portal, portal_type, **kw):
    query = {
        'portal_type': portal_type,
        'path': '/'.join(portal.getPhysicalPath()),
    }
    query.update(kw)
    return portal.portal_catalog(**query)


class KiestraPublicView(BaseKiestraPublicView):
    """Kiestra frontend independent of the old /nastavitve/dezurstva path."""

    def day_object(self):
        brains = _brains(
            self.portal,
            'imi.kiestra.work_day',
            id=self.selected_date_id(),
        )
        return brains[0].getObject() if brains else None

    def last_change(self):
        brains = _brains(
            self.portal,
            'imi.kiestra.work_day',
            sort_on='modified',
            sort_order='descending',
        )
        if not brains:
            return ''
        try:
            value = brains[0].modified.asdatetime()
            return value.strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return ''


class ReplacementsPublicView(BaseReplacementsPublicView):
    """Nadomeščanja frontend using whatever migrated day container exists."""

    def days_folder(self):
        brains = _brains(self.portal, 'imi.replacements.day')
        if not brains:
            return None
        try:
            return aq_parent(brains[0].getObject())
        except Exception:
            return None

    def day_object(self):
        brains = _brains(
            self.portal,
            'imi.replacements.day',
            id=self.selected_date_id(),
        )
        return brains[0].getObject() if brains else None
