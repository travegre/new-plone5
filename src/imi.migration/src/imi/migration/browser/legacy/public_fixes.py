# -*- coding: utf-8 -*-
"""Small public frontend fixes that deliberately avoid unreliable catalog state."""
from datetime import datetime
from html import escape

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .duty_compat import DutyPublicView as BaseDutyPublicView
from .legacy_sites import ExamsPublicView as BaseExamsPublicView
from .legacy_sites import ExamsListView as BaseExamsListView
from .runtime_fixes import _walk


class DutyPublicView(BaseDutyPublicView):
    """Resolve person history directly from the migrated roster container."""

    def person_dates(self):
        person = self.selected_person()
        if not person:
            return []
        rows = []
        for obj in _walk(self.roster_folder):
            if getattr(obj, 'portal_type', None) != 'imi.duty.roster_day':
                continue
            if not self._person_matches_roster(obj, person):
                continue
            try:
                parsed = datetime.strptime(obj.getId(), '%Y-%m-%d').date()
            except ValueError:
                continue
            rows.append({
                'id': obj.getId(), 'date': parsed, 'year': parsed.year,
                'month': parsed.month,
                'label': '%02d.%02d.%04d' % (parsed.day, parsed.month, parsed.year),
            })
        rows.sort(key=lambda row: row['date'])
        return rows


class ExamsMixin(object):
    """Read the 404 migrated examinations directly from /preiskave-1."""

    def all_exams(self):
        base = self.portal.get('preiskave-1')
        if base is None:
            return []
        result = [obj for obj in _walk(base)
                  if getattr(obj, 'portal_type', None) == 'imi.exams.examination']
        result.sort(key=lambda obj: (obj.Title() or '').lower())
        return result

    def filtered_exams(self, query=None):
        query = str(query if query is not None else
                    (self.request.form.get('q') or self.request.form.get('SearchableText') or '')).strip()
        words = [word.lower() for word in query.replace('*', ' ').replace('+', ' ').split() if word]
        result = self.all_exams()
        if not words:
            return result
        matched = []
        for obj in result:
            values = [obj.Title(), obj.Description(), getattr(obj, 'sifra', ''),
                      getattr(obj, 'laboratoriji', ''), getattr(obj, 'vzorci', '')]
            for name in ('podrocje', 'sinonim', 'metode', 'opis', 'opombe'):
                value = getattr(obj, name, '')
                raw = getattr(value, 'raw', value)
                if isinstance(raw, (tuple, list)):
                    values.extend(raw)
                else:
                    values.append(raw)
            haystack = u' '.join(str(value or '') for value in values).lower()
            if all(word in haystack for word in words):
                matched.append(obj)
        return matched


class ExamsPublicView(ExamsMixin, BaseExamsPublicView):
    pass


class ExamsListView(ExamsMixin, BaseExamsListView):
    template = ViewPageTemplateFile('exams_list_public.pt')

    def mode_heading(self):
        return self.title()

    def facets(self):
        mode = self.mode()
        exams = self.all_exams()
        values = set()
        if mode == 'preiskave_lab_view':
            for obj in exams:
                for value in str(getattr(obj, 'laboratoriji', '') or '').replace(';', ',').split(','):
                    if value.strip():
                        values.add(value.strip())
        elif mode == 'preiskave_podrocja_view':
            for obj in exams:
                for value in (getattr(obj, 'podrocje', ()) or ()):
                    if str(value).strip():
                        values.add(str(value).strip())
        elif mode == 'preiskave_sklopi_view':
            for obj in exams:
                value = getattr(obj, 'sklop', '')
                value = getattr(value, 'raw', value)
                if str(value or '').strip():
                    values.add(str(value).strip())
        return sorted(values, key=lambda value: value.lower())


class ExamsLiveSearchView(ExamsMixin, BaseExamsPublicView):
    """Standalone livesearch endpoint over physical examination objects."""

    def __call__(self):
        query = str(self.request.form.get('q') or '').strip()
        results = self.filtered_exams(query) if query else []
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return '<fieldset class="livesearchContainer"><legend>Live search</legend><div id="LSNothingFound">No match found</div></fieldset>'
        base = self.portal.absolute_url() + '/@@preiskava-public?id='
        out = ['<fieldset class="livesearchContainer"><legend>Live search results: %d</legend><ul class="LSTable">' % len(results)]
        for obj in results[:20]:
            out.append('<li class="LSRow"><a href="%s%s">%s</a><div class="LSDescr">%s</div></li>' % (
                base, escape(obj.getId()), escape(obj.Title()), escape(obj.Description() or '')))
        out.append('</ul></fieldset>')
        return ''.join(out)
