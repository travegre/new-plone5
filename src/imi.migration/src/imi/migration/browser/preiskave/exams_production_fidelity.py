# -*- coding: utf-8 -*-
"""Production-render fidelity overrides for the migrated Preiskave site."""
from html import escape
from urllib.parse import quote, quote_plus

from Products.Five import BrowserView
from plone import api

from . import exams_legacy_modes as legacy
from .exams_runtime import ExaminationPublicView as BaseExaminationPublicView
from .runtime_fixes import _walk


def _is_published(obj):
    try:
        return api.content.get_state(obj=obj) == 'published'
    except Exception:
        return False


def _legacy_moj_query(query):
    """Build the exact query shape used by the Plone-4 livesearch script."""
    value = str(query or '')
    for char in '?-+*':
        value = value.replace(char, ' ')
    value = ' AND '.join(value.split())
    value = value.replace('(', '"("').replace(')', '")"')
    return value + '*' if value else ''


def _dynamic_menu(portal, request):
    provider = legacy.ExamsHomeView(portal, request)
    rows = []
    used = set()
    for child in provider._legacy_children():
        if not _is_published(child):
            continue
        match = provider._menu_match(child)
        if match is None:
            continue
        key, _fallback, _route, _aliases = match
        if key in used:
            continue
        try:
            label = str(child.Title() or child.getId())
            href = child.absolute_url()
        except Exception:
            continue
        rows.append((key, label, href))
        used.add(key)
    return rows


class ProductionMenuMixin(object):
    def menu(self):
        return _dynamic_menu(self.portal, self.request)

    def launch_items(self):
        launch = {
            'quick': (u'Hitro iskanje', 'search-quick.png'),
            'areas': (u'Po področjih', 'search-podrocja.png'),
            'samples': (u'Po vzorcih', 'search-vzorci.png'),
            'labs': (u'Po laboratorijih', 'search-lab.png'),
        }
        by_key = {row[0]: row for row in self.menu()}
        rows = []
        for key in ('quick', 'areas', 'samples', 'labs'):
            row = by_key.get(key)
            if row is not None:
                caption, icon = launch[key]
                rows.append((key, caption, row[2], icon))
        return rows


class ProductionSearchMixin(object):
    """Use the migrated equivalent of the Plone-4 ``moj`` ZCTextIndex."""

    def _catalog(self):
        catalog = self.portal.portal_catalog
        if 'moj' not in catalog.indexes():
            raise RuntimeError(
                'Preiskave catalog index "moj" is not installed. '
                'Run the legacy catalog index migration.')
        return catalog

    def _base_path(self):
        base = self.base_folder()
        if base is None:
            return None
        return '/'.join(base.getPhysicalPath())

    @staticmethod
    def _brain_object(brain):
        """Resolve an unrestricted result without re-entering security traversal.

        These public views already use ``unrestrictedSearchResults`` to mirror
        the legacy public catalog search.  Calling ``brain.getObject()`` after
        that performs normal traversal again and can turn a valid anonymous
        search result into an authentication challenge.  Use the unrestricted
        brain resolver consistently instead.
        """
        getter = getattr(brain, '_unrestrictedGetObject', None)
        if getter is not None:
            return getter()
        return brain.getObject()

    def _moj_candidates(self):
        path = self._base_path()
        if path is None:
            return []
        brains = self._catalog().unrestrictedSearchResults(
            portal_type='imi.exams.examination',
            path=path,
        )
        return [self._brain_object(brain) for brain in brains]

    def filtered_exams(self, query=None):
        query = str(query if query is not None else
                    (self.request.form.get('q') or
                     self.request.form.get('moj') or '')).strip()
        transformed = _legacy_moj_query(query)
        if not transformed:
            return self._moj_candidates()
        path = self._base_path()
        if path is None:
            return []
        brains = self._catalog().unrestrictedSearchResults(
            moj=transformed,
            portal_type='imi.exams.examination',
            path=path,
        )
        return [self._brain_object(brain) for brain in brains]


class ExamsHomeView(ProductionMenuMixin, legacy.ExamsHomeView):
    pass


class ExamsAllView(ProductionMenuMixin, legacy.ExamsAllView):
    def title(self):
        return u'Katalog preiskav'


class ExamsQuickView(ProductionSearchMixin, ProductionMenuMixin, legacy.ExamsQuickView):
    def results(self):
        return self.filtered_exams(self.query()) if self.query() else []


class ExamsLabsView(ProductionMenuMixin, legacy.ExamsLabsView):
    def title(self):
        return u'Preiskave po laboratorijih'


class ExamsNewView(ProductionMenuMixin, legacy.ExamsNewView):
    pass


class ExamsUrgentView(ProductionMenuMixin, legacy.ExamsUrgentView):
    pass


class ExamsAreasView(ProductionMenuMixin, legacy.ExamsAreasView):
    def title(self):
        return u'Preiskave po področjih'


class ExamsGroupsView(ProductionMenuMixin, legacy.ExamsGroupsView):
    def title(self):
        return u'Preiskave po sklopih'


class ExamsSamplesView(ProductionMenuMixin, legacy.ExamsSamplesView):
    def title(self):
        return u'Preiskave po vzorcih'


class ExamsGuardiansView(ProductionMenuMixin, legacy.ExamsGuardiansView):
    pass


class LegacyExamsLiveSearchView(ProductionSearchMixin,
                                ProductionMenuMixin,
                                legacy.LegacyExamsLiveSearchView):
    limit = 20
    max_title = 100
    max_description = 93

    def __call__(self):
        query = str(self.request.form.get('q') or self.request.form.get('moj') or '').strip()
        results = self.filtered_exams(query) if len(query) > 1 else []
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return ('<fieldset class="livesearchContainer">'
                    '<legend id="livesearchLegend">Live search</legend>'
                    '<div class="LSIEFix"><div id="LSNothingFound">No match found</div>'
                    '<div class="LSRow"></div></div></fieldset>')
        out = [
            '<style>'
            '#exam-live-results .LSRow a.livesearch-show-all{'
            'color:#654fa4!important;background:#fff!important;'
            'border:1px solid rgba(255,255,255,.9)!important;'
            'padding:7px 14px!important;font-weight:700!important;'
            'display:inline-block!important;width:auto!important;float:none!important}'
            '#exam-live-results .LSRow a.livesearch-show-all:hover,'
            '#exam-live-results .LSRow a.livesearch-show-all:focus{'
            'color:#fff!important;background:#2e2c31!important}'
            '</style>',
            '<fieldset class="livesearchContainer">',
            '<legend id="livesearchLegend">Live search results: %d</legend>' % len(results),
            '<div class="LSIEFix"><ul class="LSTable">',
        ]
        for obj in results[:self.limit]:
            full_title = str(obj.Title() or '')
            display_title = full_title if len(full_title) <= self.max_title else full_title[:self.max_title] + '...'
            description = str(obj.Description() or '')
            if len(description) > self.max_description:
                description = description[:self.max_description] + '...'
            href = self.exam_url(obj) + '&searchterm=' + quote_plus(query)
            out.append('<li class="LSRow"><a href="%s" title="%s">%s</a>'
                       '<div class="LSDescr">%s</div></li>' %
                       (escape(href), escape(full_title), escape(display_title), escape(description)))
        out.append('<li class="LSRow"><br /></li>')
        if len(results) > self.limit:
            out.append('<li class="LSRow livesearch-more-row"><span>prikazanih %d od %d zadetkov</span> '
                       '<a class="livesearch-show-all" href="%s/@@preiskave_hitro_view?moj=%s">'
                       'prikaži vse zadetke</a></li>' %
                       (self.limit, len(results), self.portal.absolute_url(), quote(query)))
        out.append('</ul></div></fieldset>')
        return ''.join(out)


class ExaminationPublicView(ProductionMenuMixin, BaseExaminationPublicView):
    def attachment(self):
        attachment = getattr(self.context, 'datoteka', None)
        if attachment is None:
            return None
        filename = str(getattr(attachment, 'filename', '') or '').strip()
        if not filename:
            return None
        size = 0
        getter = getattr(attachment, 'getSize', None)
        try:
            size = int(getter() if callable(getter) else getattr(attachment, 'size', 0) or 0)
        except Exception:
            size = 0
        if size <= 0:
            return None
        return attachment


class ExaminationPublicProxyView(BrowserView):
    def __call__(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        portal = api.portal.get()
        base = portal.get('preiskave-1')
        obj = None
        if exam_id and base is not None:
            for candidate in _walk(base):
                if (candidate.getId() == exam_id and
                        getattr(candidate, 'portal_type', None) == 'imi.exams.examination'):
                    obj = candidate
                    break
        if obj is None:
            self.request.response.setStatus(404)
            return u'Preiskava ne obstaja.'
        return ExaminationPublicView(obj, self.request)()


__all__ = (
    'ExamsHomeView', 'ExamsAllView', 'ExamsQuickView', 'ExamsLabsView',
    'ExamsNewView', 'ExamsUrgentView', 'ExamsAreasView', 'ExamsGroupsView',
    'ExamsSamplesView', 'ExamsGuardiansView', 'LegacyExamsLiveSearchView',
    'ExaminationPublicView', 'ExaminationPublicProxyView',
)
