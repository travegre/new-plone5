# -*- coding: utf-8 -*-
"""Production-render fidelity overrides for the migrated Preiskave site.

Keep the route implementations from exams_legacy_modes while matching the
legacy public rendering and the old custom ``moj`` ZCTextIndex livesearch.
Navigation is content-driven: published folder titles, order and public URLs
come from Plone, as in the Plone-4 main template.
"""
from html import escape
import re
import unicodedata
from urllib.parse import quote, quote_plus

from Products.Five import BrowserView
from plone import api

from . import exams_legacy_modes as legacy
from .exams_runtime import ExaminationPublicView as BaseExaminationPublicView
from .runtime_fixes import _walk


def _plain(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        value = raw
    elif isinstance(value, (tuple, list)):
        value = u' '.join(str(item or '') for item in value)
    text = str(value or '')
    return re.sub(r'<[^>]+>', ' ', text)


def _fold(value):
    text = unicodedata.normalize('NFKD', _plain(value))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _tokens(value):
    return re.findall(r'[\w]+', _fold(value), flags=re.UNICODE)


def _is_published(obj):
    try:
        return api.content.get_state(obj=obj) == 'published'
    except Exception:
        return False


def _dynamic_menu(portal, request):
    """Reproduce the legacy published-folder navigation.

    The old main_template queried published Folder objects ordered by
    getObjPositionInParent and linked to the folders themselves. Route matching
    here identifies only the logical active item; label, order and href all
    remain live Plone content values.
    """
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


class ProductionSearchMixin(object):
    """Approximate the old ``portal_catalog(moj='word AND word*')`` index.

    Only the old Archetypes fields marked ``searchable=True`` are included,
    plus Title/Description which Archetypes/ATContentTypes supplied to its text
    indexes. Non-searchable display fields must not enlarge the result set.
    """
    searchable_fields = (
        'sklop', 'sinonim', 'vzorci', 'vzorci_lab', 'vzorci_lab_tel',
        'vzorci_odvzem', 'vzorci_odvzem_video_sifra', 'vzorci_kolicina',
        'embalaza_slika_sifra', 'vzorci_transport', 'vzorci_opomba',
        'vzorci_nivo1', 'vzorci_nivo2', 'vzorci_nivo3', 'vzorci_nivo4',
        'vzorci_nivo5', 'vzorci_nivo6',
    )

    def _moj_tokens(self, obj):
        values = [obj.Title(), obj.Description()]
        values.extend(getattr(obj, field, '') for field in self.searchable_fields)
        tokens = []
        for value in values:
            tokens.extend(_tokens(value))
        return tokens

    def filtered_exams(self, query=None):
        query = str(query if query is not None else
                    (self.request.form.get('q') or self.request.form.get('moj') or '')).strip()
        for char in '?-+*':
            query = query.replace(char, ' ')
        wanted = [_fold(word) for word in query.split() if word]
        if not wanted:
            return self.all_exams()
        result = []
        for obj in self.all_exams():
            indexed = self._moj_tokens(obj)
            if all(any(token.startswith(word) for token in indexed) for word in wanted):
                result.append(obj)
        return result


class ExamsHomeView(ProductionMenuMixin, legacy.ExamsHomeView):
    pass


class ExamsAllView(ProductionMenuMixin, legacy.ExamsAllView):
    def title(self):
        return u'Katalog preiskav'


class ExamsQuickView(ProductionSearchMixin, ProductionMenuMixin, legacy.ExamsQuickView):
    pass


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
    """Reproduce the old livesearch_reply.py response contract."""
    limit = 20
    max_title = 100
    max_description = 93

    def __call__(self):
        query = str(self.request.form.get('q') or self.request.form.get('moj') or '').strip()
        results = self.filtered_exams(query) if len(query) > 1 else []
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')

        if not results:
            return (
                '<fieldset class="livesearchContainer">'
                '<legend id="livesearchLegend">Live search</legend>'
                '<div class="LSIEFix"><div id="LSNothingFound">No match found</div>'
                '<div class="LSRow"></div></div></fieldset>'
            )

        out = [
            '<fieldset class="livesearchContainer">',
            '<legend id="livesearchLegend">Live search results: %d</legend>' % len(results),
            '<div class="LSIEFix"><ul class="LSTable">',
        ]
        for obj in results[:self.limit]:
            full_title = str(obj.Title() or '')
            display_title = full_title
            if len(display_title) > self.max_title:
                display_title = display_title[:self.max_title] + '...'
            description = str(obj.Description() or '')
            if len(description) > self.max_description:
                description = description[:self.max_description] + '...'
            href = self.exam_url(obj) + '&searchterm=' + quote_plus(query)
            out.append(
                '<li class="LSRow"><a href="%s" title="%s">%s</a>'
                '<div class="LSDescr">%s</div></li>' % (
                    escape(href), escape(full_title), escape(display_title),
                    escape(description)))

        out.append('<li class="LSRow"><br /></li>')
        if len(results) > self.limit:
            out.append(
                '<li class="LSRow"><span>prikazanih %d od %d zadetkov</span> '
                '<a href="%s/@@preiskave_hitro_view?moj=%s" style="font-weight:normal">'
                'prikaži vse zadetke</a></li>' % (
                    self.limit, len(results), self.portal.absolute_url(),
                    quote(query)))
        out.append('</ul></div></fieldset>')
        return ''.join(out)


class ExaminationPublicView(ProductionMenuMixin, BaseExaminationPublicView):
    pass


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
