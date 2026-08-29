# -*- coding: utf-8 -*-
"""Route-specific Preiskave views ported from the Plone 4 skin."""
from collections import OrderedDict
from html import escape
from urllib.parse import quote

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .exams_runtime import ExamsListView, ExamsLiveSearchView, ExamsPublicView, SLO_LETTERS


def _text(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw or '')
    output = getattr(value, 'output', None)
    if output is not None:
        return str(output or '')
    return str(value or '')


def _seq(value):
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return [str(item or '').strip() for item in value if str(item or '').strip()]
    value = str(value or '').strip()
    return [value] if value else []


def _split(value):
    values = []
    for item in _seq(value):
        for part in item.split('|'):
            part = part.strip()
            if part and part not in values:
                values.append(part)
    return values


class _LegacyMenuMixin(object):
    def menu(self):
        base = self.portal.absolute_url()
        return [
            ('all', u'Preiskave', base + '/@@preiskave_view'),
            ('quick', u'Hitro iskanje', base + '/@@preiskave_hitro_view'),
            ('labs', u'Laboratoriji', base + '/@@preiskave_lab_view'),
            ('new', u'Nove', base + '/@@preiskave_nove_view'),
            ('urgent', u'Nujne', base + '/@@preiskave_nujne_view'),
            ('areas', u'Področja', base + '/@@preiskave_podrocja_view'),
            ('groups', u'Sklopi', base + '/@@preiskave_sklopi_view'),
            ('samples', u'Vzorci', base + '/@@preiskave_vzorci_view'),
            ('guardians', u'Skrbniki', base + '/@@preiskave_skrbniki_view'),
        ]


class ExamsHomeView(_LegacyMenuMixin, ExamsPublicView):
    pass


class _LegacyModeView(_LegacyMenuMixin, ExamsListView):
    legacy_mode = 'home'
    legacy_name = ''

    def mode(self):
        return self.legacy_name

    def mode_key(self):
        return self.legacy_mode

    def mode_url(self):
        return self.portal.absolute_url() + '/@@' + self.legacy_name

    def facet_current_label(self):
        return {
            'labs': u'Trenutno izbran laboratorij',
            'areas': u'Trenutno izbrano področje preiskav',
            'groups': u'Trenutno izbrani sklop',
        }.get(self.legacy_mode, u'')

    def exam_url(self, obj):
        url = super().exam_url(obj)
        selected = self.selected_facet()
        if selected and self.legacy_mode in ('labs', 'areas', 'groups'):
            url += '&podrocje=' + quote(selected)
        return url

    def alphabet_groups(self, exams=None):
        exams = self.all_exams() if exams is None else list(exams or [])
        buckets = OrderedDict()
        for obj in exams:
            try:
                title = str(obj.Title() or '').strip()
            except Exception:
                title = str(getattr(obj, 'title', '') or '').strip()
            if not title:
                continue
            letter = title[0].upper()
            buckets.setdefault(letter, []).append(obj)
        ordered = []
        used = set()
        for letter in SLO_LETTERS:
            if letter in buckets:
                ordered.append({'letter': letter, 'items': buckets[letter]})
                used.add(letter)
        for letter in sorted([x for x in buckets if x not in used], key=lambda x: str(x).casefold()):
            ordered.append({'letter': letter, 'items': buckets[letter]})
        return ordered

    def facet_values(self):
        values = []
        for obj in self.all_exams():
            if self.legacy_mode == 'labs':
                current = _split(getattr(obj, 'laboratoriji', ''))
            elif self.legacy_mode == 'areas':
                current = _seq(getattr(obj, 'podrocje', ()))
            elif self.legacy_mode == 'groups':
                current = _split(_text(getattr(obj, 'sklop', '')))
            else:
                current = []
            for value in current:
                if value not in values:
                    values.append(value)
        return sorted(values, key=lambda x: x.casefold())

    def facet_exams(self):
        selected = self.selected_facet()
        if not selected:
            return self.all_exams()
        result = []
        for obj in self.all_exams():
            if self.legacy_mode == 'labs':
                match = selected in _text(getattr(obj, 'laboratoriji', ''))
            elif self.legacy_mode == 'areas':
                match = selected in _seq(getattr(obj, 'podrocje', ()))
            elif self.legacy_mode == 'groups':
                match = selected in _text(getattr(obj, 'sklop', ''))
            else:
                match = False
            if match:
                result.append(obj)
        return result


class ExamsAllView(_LegacyModeView):
    legacy_mode = 'all'
    legacy_name = 'preiskave_view'


class ExamsQuickView(_LegacyModeView):
    legacy_mode = 'quick'
    legacy_name = 'preiskave_hitro_view'


class ExamsLabsView(_LegacyModeView):
    legacy_mode = 'labs'
    legacy_name = 'preiskave_lab_view'


class ExamsNewView(_LegacyModeView):
    legacy_mode = 'new'
    legacy_name = 'preiskave_nove_view'

    def new_groups(self):
        result = []
        for year in ('2016', '2017'):
            exams = [obj for obj in self.all_exams()
                     if str(getattr(obj, 'nova_pre', '') or '').strip() == year]
            result.append({'year': year, 'groups': self.alphabet_groups(exams)})
        return result


class ExamsUrgentView(_LegacyModeView):
    legacy_mode = 'urgent'
    legacy_name = 'preiskave_nujne_view'


class ExamsAreasView(_LegacyModeView):
    legacy_mode = 'areas'
    legacy_name = 'preiskave_podrocja_view'


class ExamsGroupsView(_LegacyModeView):
    legacy_mode = 'groups'
    legacy_name = 'preiskave_sklopi_view'


class ExamsSamplesView(_LegacyModeView):
    legacy_mode = 'samples'
    legacy_name = 'preiskave_vzorci_view'


class ExamsGuardiansView(_LegacyModeView):
    legacy_mode = 'guardians'
    legacy_name = 'preiskave_skrbniki_view'
    template = ViewPageTemplateFile('preiskave_skrbniki.pt')

    def title(self):
        return u'Skrbniki'

    def guardians_html(self):
        base = self.base_folder()
        if base is None:
            return u''
        folder = base.get('skrbniki')
        document = folder is not None and folder.get('skrbniki-1') or None
        if document is None:
            return u''
        return _text(getattr(document, 'text', ''))


class LegacyExamsLiveSearchView(_LegacyMenuMixin, ExamsLiveSearchView):
    limit = 20

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
            '<fieldset class="livesearchContainer">',
            '<legend id="livesearchLegend">Live search results: %d</legend>' % len(results),
            '<div class="LSIEFix"><ul class="LSTable">',
        ]
        for obj in results[:self.limit]:
            title = str(obj.Title() or '')
            description = str(obj.Description() or '')
            if len(description) > 93:
                description = description[:93] + '...'
            out.append(
                '<li class="LSRow"><a href="%s" title="%s">%s</a>'
                '<div class="LSDescr">%s</div></li>' % (
                    escape(self.exam_url(obj)), escape(title), escape(title), escape(description)))
        out.append('<li class="LSRow"><br /></li>')
        if len(results) > self.limit:
            out.append(
                '<li class="LSRow"><span>prikazanih %d od %d zadetkov</span> '
                '<a href="%s/@@preiskave_hitro_view?moj=%s" style="font-weight:normal">'
                'prikaži vse zadetke</a></li>' % (
                    self.limit, len(results), self.portal.absolute_url(), quote(query)))
        out.append('</ul></div></fieldset>')
        return ''.join(out)


__all__ = (
    'ExamsHomeView', 'ExamsAllView', 'ExamsQuickView', 'ExamsLabsView',
    'ExamsNewView', 'ExamsUrgentView', 'ExamsAreasView', 'ExamsGroupsView',
    'ExamsSamplesView', 'ExamsGuardiansView', 'LegacyExamsLiveSearchView',
)
