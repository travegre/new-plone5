# -*- coding: utf-8 -*-
"""Runtime compatibility fixes for migrated legacy public sites."""
from Acquisition import aq_parent
from html import escape
from Products.Five import BrowserView

from .exams_compat import ExaminationView
from .legacy_sites import ExamsLiveSearchView as BaseExamsLiveSearchView
from .legacy_sites import KiestraPublicView as BaseKiestraPublicView
from .legacy_sites import ReplacementsPublicView as BaseReplacementsPublicView


def _brains(portal, portal_type, **kw):
    query = {
        'portal_type': portal_type,
        'path': '/'.join(portal.getPhysicalPath()),
    }
    query.update(kw)
    return portal.portal_catalog(**query)


def _walk(container):
    for obj in container.objectValues():
        yield obj
        if hasattr(obj, 'objectValues'):
            for child in _walk(obj):
                yield child


class KiestraPublicView(BaseKiestraPublicView):
    """Kiestra frontend independent of the old /nastavitve/dezurstva path."""

    def day_object(self):
        brains = _brains(self.portal, 'imi.kiestra.work_day', id=self.selected_date_id())
        return brains[0].getObject() if brains else None

    def last_change(self):
        brains = _brains(self.portal, 'imi.kiestra.work_day', sort_on='modified', sort_order='descending')
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
        brains = _brains(self.portal, 'imi.replacements.day', id=self.selected_date_id())
        return brains[0].getObject() if brains else None


class ExamsLiveSearchView(BaseExamsLiveSearchView):
    """Return livesearch links through the anonymous site-root proxy."""

    def __call__(self):
        query = str(self.request.form.get('q') or '').strip()
        results = self.filtered_exams(query)
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return '<fieldset class="livesearchContainer"><legend>Live search</legend><div id="LSNothingFound">No match found</div></fieldset>'
        limit = 20
        base = self.portal.absolute_url() + '/@@preiskava-public?id='
        out = ['<fieldset class="livesearchContainer"><legend>Live search results: %d</legend><ul class="LSTable">' % len(results)]
        for obj in results[:limit]:
            out.append('<li class="LSRow"><a href="%s%s">%s</a><div class="LSDescr">%s</div></li>' % (
                base, escape(obj.getId()), escape(obj.Title()), escape(obj.Description() or '')))
        if len(results) > limit:
            out.append('<li class="LSRow">prikazanih %d od %d zadetkov</li>' % (limit, len(results)))
        out.append('</ul></fieldset>')
        return ''.join(out)


class ExaminationPublicProxyView(BrowserView):
    """Render an examination through the public site root."""

    def _exam(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        if not exam_id:
            return None
        portal = self.context
        brains = portal.portal_catalog(id=exam_id, path='/'.join(portal.getPhysicalPath()))
        for brain in brains:
            try:
                obj = brain.getObject()
            except Exception:
                continue
            if getattr(obj, 'portal_type', None) == 'imi.exams.examination':
                return obj
        base = portal.get('preiskave-1')
        if base is not None:
            for obj in _walk(base):
                if obj.getId() == exam_id and getattr(obj, 'portal_type', None) == 'imi.exams.examination':
                    return obj
        return None

    def __call__(self):
        obj = self._exam()
        if obj is None:
            self.request.response.setStatus(404)
            return u'Preiskava ne obstaja.'
        return ExaminationView(obj, self.request)()
