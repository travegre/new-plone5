# -*- coding: utf-8 -*-
"""Faithful public runtime for the legacy Preiskave site.

The Plone-4 skin did not use one generic listing. Each menu entry had its own
view semantics while sharing one public shell. This module ports those
behaviours against the migrated Dexterity objects without relying on catalog
indexes or workflow visibility.
"""
from collections import OrderedDict
from html import escape
from urllib.parse import quote

from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone import api

from .exams_compat import ExaminationView as BaseExaminationView
from .runtime_fixes import _walk


SLO_LETTERS = (u'A', u'B', u'C', u'Č', u'D', u'E', u'F', u'G', u'H', u'I',
               u'J', u'K', u'L', u'M', u'N', u'O', u'P', u'R', u'S', u'Š',
               u'T', u'U', u'V', u'Z', u'Ž', u'Q', u'X', u'Y', u'W')


def _rich(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw or '')
    output = getattr(value, 'output', None)
    if output is not None:
        return str(output or '')
    return str(value or '')


def _lines(value):
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return [str(x or '') for x in value]
    text = str(value or '')
    if not text:
        return []
    return text.split('\n')


def _parts(value, separators=('|',)):
    work = [str(value or '')]
    for sep in separators:
        next_work = []
        for item in work:
            next_work.extend(item.split(sep))
        work = next_work
    result = []
    for item in work:
        item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


class ExamsBase(BrowserView):
    template = ViewPageTemplateFile('preiskave_legacy.pt')

    @property
    def portal(self):
        return api.portal.get()

    def base_folder(self):
        return self.portal.get('preiskave-1')

    def all_exams(self):
        cached = getattr(self.portal, '_v_imi_exams_objects', None)
        if cached is not None:
            return cached
        base = self.base_folder()
        result = [] if base is None else [
            obj for obj in _walk(base)
            if getattr(obj, 'portal_type', None) == 'imi.exams.examination'
        ]
        result.sort(key=lambda obj: (obj.Title() or '').casefold())
        self.portal._v_imi_exams_objects = result
        return result

    def exam_url(self, obj):
        return self.portal.absolute_url() + '/@@preiskava-public?id=' + quote(obj.getId())

    def _searchable(self, obj):
        values = [obj.Title(), obj.Description(), getattr(obj, 'sifra', ''),
                  getattr(obj, 'laboratoriji', ''), getattr(obj, 'vzorci', '')]
        for name in ('podrocje', 'sklop', 'sinonim', 'metode', 'opis', 'opombe',
                     'trajanje', 'urnik', 'vzorci_lab', 'vzorci_lab_kratica'):
            value = getattr(obj, name, '')
            if isinstance(value, (tuple, list)):
                values.extend(value)
            else:
                values.append(_rich(value))
        return u' '.join(str(value or '') for value in values).casefold()

    def filtered_exams(self, query=None):
        query = str(query if query is not None else
                    (self.request.form.get('q') or self.request.form.get('moj') or '')).strip()
        words = [word.casefold() for word in query.replace('*', ' ').replace('+', ' ').split() if word]
        if not words:
            return self.all_exams()
        return [obj for obj in self.all_exams()
                if all(word in self._searchable(obj) for word in words)]

    def query(self):
        return str(self.request.form.get('q') or self.request.form.get('moj') or '')

    def mode(self):
        url = str(self.request.get('URL') or '')
        return url.rstrip('/').rsplit('/', 1)[-1]

    def mode_url(self):
        mode = self.mode()
        if mode.startswith('@@'):
            mode = mode[2:]
        return self.portal.absolute_url() + '/@@' + mode

    def mode_key(self):
        return {
            'preiskave_view': 'all', 'content_view': 'all',
            'preiskave_hitro_view': 'quick',
            'preiskave_lab_view': 'labs',
            'preiskave_nove_view': 'new',
            'preiskave_nujne_view': 'urgent',
            'preiskave_podrocja_view': 'areas',
            'preiskave_sklopi_view': 'groups',
            'preiskave_vzorci_view': 'samples',
        }.get(self.mode().replace('@@', ''), 'home')

    def title(self):
        return {
            'home': u'PREISKAVE', 'all': u'Preiskave', 'quick': u'Hitro iskanje',
            'labs': u'Laboratoriji', 'new': u'Nove preiskave', 'urgent': u'Nujne preiskave',
            'areas': u'Področja preiskav', 'groups': u'Sklopi preiskav', 'samples': u'Vzorci',
        }[self.mode_key()]

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
        ]

    def _initial(self, title):
        title = (title or '').strip()
        if not title:
            return u''
        return title[0].upper()

    def alphabet_groups(self, exams=None):
        exams = self.all_exams() if exams is None else exams
        groups = OrderedDict()
        for obj in exams:
            letter = self._initial(obj.Title())
            if letter:
                groups.setdefault(letter, []).append(obj)
        ordered = []
        used = set()
        for letter in SLO_LETTERS:
            if letter in groups:
                ordered.append({'letter': letter, 'items': groups[letter]})
                used.add(letter)
        for letter in sorted((letter for letter in groups if letter not in used), key=lambda value: value.casefold()):
            ordered.append({'letter': letter, 'items': groups[letter]})
        return ordered

    def selected_facet(self):
        return str(self.request.form.get('podrocje') or '').strip()

    def facet_values(self):
        mode = self.mode_key()
        values = []
        for obj in self.all_exams():
            if mode == 'labs':
                current = _parts(getattr(obj, 'laboratoriji', ''), ('|',))
            elif mode == 'areas':
                current = [str(v).strip() for v in (getattr(obj, 'podrocje', ()) or ()) if str(v).strip()]
            elif mode == 'groups':
                current = _parts(_rich(getattr(obj, 'sklop', '')), ('|',))
            else:
                current = []
            for value in current:
                if value not in values:
                    values.append(value)
        return sorted(values, key=lambda value: value.casefold())

    def facet_label(self):
        return {'labs': u'laboratorij', 'areas': u'področje preiskav', 'groups': u'sklop'}.get(self.mode_key(), '')

    def facet_all_label(self):
        return {'labs': u'- VSI LABORATORIJI -', 'areas': u'VSA PODROČJA', 'groups': u'- VSI SKLOPI -'}.get(self.mode_key(), '')

    def facet_exams(self):
        selected = self.selected_facet()
        if not selected:
            return self.all_exams()
        mode = self.mode_key()
        result = []
        for obj in self.all_exams():
            if mode == 'labs' and selected in _parts(getattr(obj, 'laboratoriji', ''), ('|',)):
                result.append(obj)
            elif mode == 'areas' and selected in tuple(str(v) for v in (getattr(obj, 'podrocje', ()) or ())):
                result.append(obj)
            elif mode == 'groups' and selected in _parts(_rich(getattr(obj, 'sklop', '')), ('|',)):
                result.append(obj)
        return result

    def new_groups(self):
        by_year = {}
        for obj in self.all_exams():
            year = str(getattr(obj, 'nova_pre', '') or '').strip()
            if not year or year.lower() in ('0', 'false', 'ne'):
                continue
            by_year.setdefault(year, []).append(obj)
        def year_sort(value):
            try:
                return int(value)
            except Exception:
                return 0
        return [{'year': year, 'groups': self.alphabet_groups(by_year[year])}
                for year in sorted(by_year, key=year_sort, reverse=True)]

    def urgent_exams(self):
        return [obj for obj in self.all_exams()
                if str(getattr(obj, 'nujna_pre', '') or '').strip().casefold() in ('da', 'yes', 'true', '1')]

    def urgent_samples(self):
        rows = []
        for obj in self.all_exams():
            samples = _lines(getattr(obj, 'vzorci', ''))
            flags = _lines(getattr(obj, 'preiskava_vzorec_nujno', ()))
            for index, flag in enumerate(flags):
                if str(flag).strip().casefold() not in ('da', 'yes', 'true', '1') or index >= len(samples):
                    continue
                rows.append({'exam': obj, 'sample': samples[index].split('###')[0].strip()})
        rows.sort(key=lambda row: ((row['exam'].Title() or '').casefold(), row['sample'].casefold()))
        return rows

    def sample_selected(self):
        return [str(self.request.form.get('nivo%d' % n) or '').strip() for n in range(1, 6)]

    def selected_area(self):
        return str(self.request.form.get('podrocje') or '').strip()

    def sample_records(self):
        area = self.selected_area()
        rows = []
        for obj in self.all_exams():
            if area and area not in tuple(str(v) for v in (getattr(obj, 'podrocje', ()) or ())):
                continue
            for raw in _lines(getattr(obj, 'vzorci', '')):
                if '###' not in raw:
                    continue
                parts = raw.split('###')
                rows.append({'exam': obj, 'name': parts[0].strip(),
                             'levels': [parts[i].strip() if i < len(parts) else '' for i in range(2, 7)]})
        return rows

    def sample_choices(self):
        selected = self.sample_selected()
        depth = 0
        while depth < len(selected) and selected[depth]:
            depth += 1
        if depth >= 5:
            return []
        values = []
        for row in self.sample_records():
            if any(selected[i] and row['levels'][i] != selected[i] for i in range(depth)):
                continue
            value = row['levels'][depth]
            if value and value not in values:
                values.append(value)
        return sorted(values, key=lambda value: value.casefold())

    def sample_choice_url(self, choice):
        selected = self.sample_selected()
        depth = 0
        while depth < len(selected) and selected[depth]:
            depth += 1
        params = []
        area = self.selected_area()
        if area:
            params.append(('podrocje', area))
        for index in range(depth):
            params.append(('nivo%d' % (index + 1), selected[index]))
        params.append(('nivo%d' % (depth + 1), choice))
        return self.portal.absolute_url() + '/@@preiskave_vzorci_view?' + '&'.join(
            '%s=%s' % (key, quote(value)) for key, value in params)

    def sample_breadcrumbs(self):
        selected = self.sample_selected()
        rows = [{'label': u'vsi vzorci', 'url': self.portal.absolute_url() + '/@@preiskave_vzorci_view'}]
        for index, value in enumerate(selected):
            if not value:
                break
            params = []
            area = self.selected_area()
            if area:
                params.append(('podrocje', area))
            for i in range(index + 1):
                params.append(('nivo%d' % (i + 1), selected[i]))
            rows.append({'label': value, 'url': self.portal.absolute_url() + '/@@preiskave_vzorci_view?' + '&'.join(
                '%s=%s' % (key, quote(val)) for key, val in params)})
        return rows

    def sample_matching_exams(self):
        selected = self.sample_selected()
        if not any(selected):
            return []
        result = []
        for row in self.sample_records():
            if all(not selected[i] or row['levels'][i] == selected[i] for i in range(5)) and row['exam'] not in result:
                result.append(row['exam'])
        return result

    def areas(self):
        values = []
        for obj in self.all_exams():
            for value in (getattr(obj, 'podrocje', ()) or ()):
                value = str(value).strip()
                if value and value not in values:
                    values.append(value)
        return sorted(values, key=lambda value: value.casefold())

    def results(self):
        mode = self.mode_key()
        if mode == 'quick':
            return self.filtered_exams(self.query()) if self.query() else []
        if mode in ('labs', 'areas', 'groups'):
            return self.facet_exams()
        if mode == 'urgent':
            return self.urgent_exams()
        if mode == 'samples':
            return self.sample_matching_exams()
        return self.all_exams()

    def __call__(self):
        return self.template()


class ExamsPublicView(ExamsBase):
    def mode_key(self):
        return 'home'


class ExamsListView(ExamsBase):
    pass


class ExamsLiveSearchView(ExamsBase):
    def __call__(self):
        query = str(self.request.form.get('q') or self.request.form.get('moj') or '').strip()
        results = self.filtered_exams(query) if len(query) > 1 else []
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return '<fieldset class="livesearchContainer"><div id="LSNothingFound">No match found</div></fieldset>'
        out = ['<fieldset class="livesearchContainer"><ul class="LSTable">']
        for obj in results[:30]:
            out.append('<li class="LSRow"><a href="%s">%s</a><div class="LSDescr">%s</div></li>' % (
                escape(self.exam_url(obj)), escape(obj.Title()), escape(obj.Description() or '')))
        out.append('</ul></fieldset>')
        return ''.join(out)


class ExaminationPublicView(BaseExaminationView):
    template = ViewPageTemplateFile('preiskave_detail_legacy.pt')

    @property
    def portal(self):
        return api.portal.get()

    def menu(self):
        return ExamsBase(self.portal, self.request).menu()

    def exam_url(self, obj):
        return self.portal.absolute_url() + '/@@preiskava-public?id=' + quote(obj.getId())

    def __call__(self):
        return self.template()


class ExaminationPublicProxyView(BrowserView):
    def __call__(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        portal = api.portal.get()
        base = portal.get('preiskave-1')
        obj = None
        if exam_id and base is not None:
            for candidate in _walk(base):
                if candidate.getId() == exam_id and getattr(candidate, 'portal_type', None) == 'imi.exams.examination':
                    obj = candidate
                    break
        if obj is None:
            self.request.response.setStatus(404)
            return u'Preiskava ne obstaja.'
        return ExaminationPublicView(obj, self.request)()


__all__ = ('ExamsPublicView', 'ExamsListView', 'ExamsLiveSearchView',
           'ExaminationPublicView', 'ExaminationPublicProxyView')
