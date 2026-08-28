# -*- coding: utf-8 -*-
"""Runtime compatibility fixes for migrated legacy public sites."""
from datetime import datetime
from html import escape
from io import BytesIO
import json

from Acquisition import aq_parent
from Products.Five import BrowserView

from .exams_compat import ExaminationView
from .legacy_sites import DirectorySearchView as BaseDirectorySearchView
from .legacy_sites import ExamsLiveSearchView as BaseExamsLiveSearchView
from .legacy_sites import KiestraPublicView as BaseKiestraPublicView
from .legacy_sites import ReplacementsPublicView as BaseReplacementsPublicView
from .legacy_sites import ReplacementsExportView as BaseReplacementsExportView
from .legacy_sites import _date_group, _parse_date, _period, _staff_title


def _walk(container):
    for obj in container.objectValues():
        yield obj
        if hasattr(obj, 'objectValues'):
            for child in _walk(obj):
                yield child


def _inner_site(outer, site_id):
    """Return accidentally nested migrated Plone site when present."""
    inner = outer.get(site_id)
    if inner is not None and getattr(inner, 'portal_type', None) == 'Plone Site':
        return inner
    return outer


class DirectorySearchView(BaseDirectorySearchView):
    """Fast livesearch over the 10k migrated people with hidden detail rows."""

    def _cache(self, portal):
        cached = getattr(portal, '_v_imi_directory_search_cache', None)
        if cached is not None:
            return cached
        rows = []
        base = portal.get('data2')
        if base is not None:
            for obj in _walk(base):
                if getattr(obj, 'portal_type', None) != 'imi.directory.person':
                    continue
                values = []
                for field in self.searchable_fields:
                    value = obj.Title() if field == 'title' else getattr(obj, field, '')
                    values.append(str(value or '').lower())
                rows.append((u' '.join(values), obj))
        portal._v_imi_directory_search_cache = rows
        return rows

    def __call__(self):
        from plone import api
        portal = api.portal.get()
        query = str(self.request.form.get('q') or self.request.form.get('searchGadget') or '').strip()
        words = [w.lower() for w in query.replace('*', ' ').replace('+', ' ').split() if w]
        objects = []
        if words:
            for haystack, obj in self._cache(portal):
                if all(word in haystack for word in words):
                    objects.append(obj)
        objects.sort(key=lambda obj: ((getattr(obj, 'priimek', '') or 'ŽŽŽŽŽ').lower(),
                                      (getattr(obj, 'ime', '') or '').lower()))
        total = len(objects)
        objects = objects[:100]
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not objects:
            return (u'<fieldset class="livesearchContainer"><legend id="livesearchLegend">'
                    u'LiveSearch ↓</legend><div class="LSIEFix"><div id="LSNothingFound">'
                    u'No matching results found.</div></div></fieldset>')
        out = [u'<fieldset class="livesearchContainer">',
               u'<legend id="livesearchLegend">LiveSearch ↓ zadetkov: %d</legend>' % total,
               u'<div class="LSIEFix"><table class="tabela" cellspacing="0" cellpadding="0">',
               u'<thead><tr><th></th><th>Ime</th><th>Priimek</th><th></th><th>Oddelek</th>'
               u'<th>Telefon</th><th>DECT</th><th>Mobilna</th><th>Enota</th></tr></thead><tbody>']
        for obj in objects:
            phone = self._phone(getattr(obj, 'telefon', ''))
            dect = self._phone(getattr(obj, 'dect', ''))
            mobile = self._phone(getattr(obj, 'mobilna', ''), mobile=True)
            full_name = u' '.join(filter(None, [str(getattr(obj, 'predime', '') or ''),
                                                str(getattr(obj, 'ime', '') or ''),
                                                str(getattr(obj, 'priimek', '') or ''),
                                                str(getattr(obj, 'zaime', '') or '')]))
            out.append(u'<tr class="tri"><td class="enota">%s</td><td>%s</td><td>%s</td><td class="enota">%s</td>'
                       u'<td class="enota">%s</td><td>%s</td><td class="enota">%s</td><td class="enota">%s</td><td class="enota">%s</td></tr>' % (
                           escape(str(getattr(obj, 'predime', '') or '')),
                           escape(str(getattr(obj, 'ime', '') or '')),
                           escape(str(getattr(obj, 'priimek', '') or '')),
                           escape(str(getattr(obj, 'zaime', '') or '')),
                           escape(str(getattr(obj, 'oddelek', '') or '')),
                           escape(phone), escape(dect), escape(mobile),
                           escape(str(getattr(obj, 'enota', '') or ''))))
            out.append(u'<tr class="person-detail" style="display:none"><td colspan="9">'
                       u'<div class="ime">%s</div><div class="stevilka">%s</div><br />%s<br />%s<br />%s<br />%s</td></tr>' % (
                           escape(full_name), escape(phone),
                           escape(str(getattr(obj, 'oddelek', '') or '')),
                           escape(str(getattr(obj, 'opis', '') or '')),
                           escape(str(getattr(obj, 'enota', '') or '')),
                           escape(str(getattr(obj, 'lokacija', '') or ''))))
        out.append(u'</tbody></table></div></fieldset>')
        return u''.join(out)


class KiestraPublicView(BaseKiestraPublicView):
    @property
    def portal(self):
        return _inner_site(self.context, 'kiestra')

    def _days(self):
        folder = self.portal.get('dezurstva-1')
        return folder

    def day_object(self):
        folder = self._days()
        return folder.get(self.selected_date_id()) if folder is not None else None

    def last_change(self):
        folder = self._days()
        if folder is None:
            return ''
        objects = [obj for obj in folder.objectValues()
                   if getattr(obj, 'portal_type', None) == 'imi.kiestra.work_day']
        if not objects:
            return ''
        latest = max(objects, key=lambda obj: getattr(obj, 'modified', lambda: None)())
        try:
            return latest.modified().strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return ''

    def person_dates(self):
        person = self.selected_person()
        folder = self._days()
        if not person or folder is None:
            return []
        result = []
        for obj in folder.objectValues():
            if getattr(obj, 'portal_type', None) != 'imi.kiestra.work_day':
                continue
            found = False
            for field in ('priprava_vzorcev', 'cepljenje_vzorcev', 'odcitavanje',
                          'identifikacija', 'antibiogram', 'izolacija', 'odpad', 'ciscenje'):
                if person in tuple(str(x) for x in (getattr(obj, field, ()) or ())):
                    found = True
                    break
            if not found:
                continue
            try:
                parsed = _parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result


class ExamsMixin(object):
    def all_exams(self):
        base = self.portal.get('preiskave-1')
        if base is None:
            return []
        result = [obj for obj in _walk(base)
                  if getattr(obj, 'portal_type', None) == 'imi.exams.examination']
        result.sort(key=lambda obj: (obj.Title() or '').lower())
        return result


class ExamsLiveSearchView(ExamsMixin, BaseExamsLiveSearchView):
    def __call__(self):
        query = str(self.request.form.get('q') or '').strip()
        results = self.filtered_exams(query)
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


class ExaminationPublicProxyView(BrowserView):
    def _exam(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        base = self.context.get('preiskave-1')
        if not exam_id or base is None:
            return None
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


class ReplacementsPublicView(BaseReplacementsPublicView):
    @property
    def portal(self):
        return _inner_site(self.context, 'nadomescanja')

    def days_folder(self):
        return self.portal.get('nadomescanja-1')

    def labs_folder(self):
        return self.portal.get('laboratoriji')

    def day_object(self):
        folder = self.days_folder()
        return folder.get(self.selected_date_id()) if folder is not None else None

    def last_change(self):
        folder = self.days_folder()
        if folder is None:
            return ''
        days = [obj for obj in folder.objectValues()
                if getattr(obj, 'portal_type', None) == 'imi.replacements.day']
        if not days:
            return ''
        try:
            latest = max(days, key=lambda obj: obj.modified())
            return latest.modified().strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return ''

    def person_dates(self):
        person = self.selected_person()
        folder = self.days_folder()
        if not person or folder is None:
            return []
        result = []
        for obj in folder.objectValues():
            if getattr(obj, 'portal_type', None) != 'imi.replacements.day':
                continue
            rows = self._rows_from_obj(obj)
            matched = False
            for row in rows:
                replacement_id = str(row.get('nadomestni_vodja_id') or '')
                replacement_name = str(row.get('nadomestni_vodja_naziv') or '')
                if replacement_id == person or replacement_name == _staff_title(self.context, person):
                    matched = True
                    break
            if not matched:
                continue
            try:
                parsed = _parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result


class ReplacementsExportView(BaseReplacementsExportView):
    @property
    def portal(self):
        return _inner_site(self.context, 'nadomescanja')

    def days_folder(self):
        return self.portal.get('nadomescanja-1')

    def __call__(self):
        from openpyxl import Workbook
        try:
            first, last = _period(self.request)
        except ValueError as exc:
            from plone import api
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(self.context.absolute_url())
            return ''
        person = str(self.request.form.get('izvoz-2-oseba') or self.request.form.get('oseba') or '')
        folder = self.days_folder()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'izpis'
        heading = 'Izpis: %s - %s' % (first.strftime('%d.%m.%Y'), last.strftime('%d.%m.%Y'))
        if person:
            heading += ' za osebo ' + _staff_title(self.context, person)
        sheet.cell(1, 1, heading)
        sheet.append([])
        sheet.append(['Datum', 'Enota', 'Vodja', u'Nadomešča'])
        if folder is not None:
            for obj in sorted(folder.objectValues(), key=lambda item: item.getId()):
                if getattr(obj, 'portal_type', None) != 'imi.replacements.day':
                    continue
                try:
                    day = _parse_date(obj.getId())
                except ValueError:
                    continue
                if day < first or day > last:
                    continue
                try:
                    rows = json.loads(str(getattr(obj, 'nadomescanja_json', '') or '[]'))
                except Exception:
                    rows = []
                for row in rows:
                    if person and str(row.get('nadomestni_vodja_id') or '') != person:
                        continue
                    sheet.append([day.strftime('%d.%m.%Y'), row.get('laboratorij_okrajsava', ''),
                                  row.get('privzeti_vodja_naziv', ''), row.get('nadomestni_vodja_naziv', '')])
        payload = BytesIO()
        workbook.save(payload)
        payload.seek(0)
        filename = 'izpis_%s-%s.xlsx' % (first.strftime('%d_%m_%Y'), last.strftime('%d_%m_%Y'))
        self.request.response.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader('Content-Disposition', 'attachment; filename="%s"' % filename)
        return payload.getvalue()
