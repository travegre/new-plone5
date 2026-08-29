# -*- coding: utf-8 -*-
"""Production-render fidelity overrides for the migrated Preiskave site.

The filesystem skin and the migrated folder order are not sufficient to
reconstruct the final Plone-4 rendering.  This module keeps the route
implementations from exams_legacy_modes but fixes the public navigation to the
order visible on the production site and emulates the old custom ``moj``
ZCTextIndex query used by livesearch_reply.py.
"""
import re
import unicodedata

from Products.Five import BrowserView
from plone import api

from . import exams_legacy_modes as legacy
from .exams_runtime import ExaminationPublicView as BaseExaminationPublicView
from .runtime_fixes import _walk


PRODUCTION_MENU = (
    ('quick', u'Hitro iskanje', 'preiskave_hitro_view'),
    ('areas', u'Preiskave po področjih', 'preiskave_podrocja_view'),
    ('samples', u'Preiskave po vzorcih', 'preiskave_vzorci_view'),
    ('all', u'Katalog preiskav', 'preiskave_view'),
    ('labs', u'Preiskave po laboratorijih', 'preiskave_lab_view'),
    ('groups', u'Preiskave po sklopih', 'preiskave_sklopi_view'),
    ('urgent', u'Nujne preiskave', 'preiskave_nujne_view'),
    ('new', u'Nove preiskave', 'preiskave_nove_view'),
    ('guardians', u'Skrbniki', 'preiskave_skrbniki_view'),
)


def _menu(portal):
    base = portal.absolute_url()
    return [(key, label, base + '/@@' + route)
            for key, label, route in PRODUCTION_MENU]


def _plain(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        value = raw
    elif isinstance(value, (tuple, list)):
        value = u' '.join(str(item or '') for item in value)
    text = str(value or '')
    # RichText in these fields is simple, but remove markup so token matching
    # behaves like a text index instead of matching tag/attribute fragments.
    return re.sub(r'<[^>]+>', ' ', text)


def _fold(value):
    text = unicodedata.normalize('NFKD', _plain(value))
    return ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _tokens(value):
    # ZCTextIndex tokenisation is word based.  The legacy script transformed
    # each query word to an AND term and appended ``*`` to the query, i.e. a
    # prefix match, rather than the arbitrary substring test used in 5.2.
    return re.findall(r'[\w]+', _fold(value), flags=re.UNICODE)


class ProductionMenuMixin(object):
    def menu(self):
        return _menu(self.portal)


class ProductionSearchMixin(object):
    """Approximate the old ``portal_catalog(moj='word AND word*')`` index.

    The old Archetypes schema marks the fields below ``searchable=True``.
    Non-searchable technical/display fields (sifra, laboratoriji, metode,
    opis, opombe, trajanje, urnik, podrocje) must not enlarge quick-search
    results as the previous generic 5.2 concatenation did.
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
    pass


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
