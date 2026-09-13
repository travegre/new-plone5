# -*- coding: utf-8 -*-
"""Nadomeščanja public, admin, edit, export and request views."""
from datetime import date, timedelta
from io import BytesIO
import json

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from ..common.helpers import date_group
from ..common.helpers import formatted_date
from ..common.helpers import inner_site
from ..common.helpers import parse_date
from ..common.helpers import period
from ..common.helpers import staff_options
from ..common.helpers import staff_title


class ReplacementsBase(BrowserView):
    @property
    def portal(self):
        return inner_site(self.context, 'nadomescanja')

    def days_folder(self):
        return self.portal.get('nadomescanja-1')

    def selected_date(self):
        try:
            return parse_date(self.request.form.get('datum'), default_today=True)
        except ValueError:
            return date.today()

    def selected_date_id(self):
        return self.selected_date().strftime('%Y-%m-%d')

    def today_id(self):
        return date.today().strftime('%Y-%m-%d')

    def day_object(self):
        folder = self.days_folder()
        return folder.get(self.selected_date_id()) if folder is not None else None

    def labs_folder(self):
        return self.portal.get('laboratoriji')

    def laboratories(self):
        folder = self.labs_folder()
        if folder is None:
            return []
        return [obj for obj in folder.objectValues()
                if getattr(obj, 'portal_type', None) == 'imi.replacements.laboratory']

    def staff_options(self):
        return staff_options(self.context)

    def _rows_from_obj(self, obj):
        if obj is None:
            return []
        try:
            value = json.loads(str(getattr(obj, 'nadomescanja_json', '') or '[]'))
            return value if isinstance(value, list) else []
        except Exception:
            return []

    def replacement_map(self):
        return {str(row.get('laboratorij_okrajsava') or ''): row
                for row in self._rows_from_obj(self.day_object())}

    def public_rows(self):
        replacements = self.replacement_map()
        result = []
        for lab in self.laboratories():
            abbreviation = str(getattr(lab, 'okrajsava', '') or lab.getId())
            leader_ids = tuple(getattr(lab, 'privzeti_vodja', ()) or ())
            leader = staff_title(self.context, leader_ids[0]) if leader_ids else ''
            row = replacements.get(abbreviation, {})
            replacement = str(row.get('nadomestni_vodja_naziv') or '')
            result.append({
                'abbreviation': abbreviation,
                'leader': leader,
                'replacement': replacement,
                'replaced': bool(replacement),
            })
        return result

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

    def formatted_date(self):
        return formatted_date(self.selected_date())

    def previous_date(self):
        return (self.selected_date() - timedelta(days=1)).strftime('%Y-%m-%d')

    def next_date(self):
        return (self.selected_date() + timedelta(days=1)).strftime('%Y-%m-%d')

    def selected_person(self):
        return str(self.request.form.get('oseba') or '')

    def selected_person_title(self):
        return staff_title(self.context, self.selected_person())

    def person_dates(self):
        person = self.selected_person()
        folder = self.days_folder()
        if not person or folder is None:
            return []
        wanted_name = staff_title(self.context, person)
        result = []
        for obj in folder.objectValues():
            if getattr(obj, 'portal_type', None) != 'imi.replacements.day':
                continue
            rows = self._rows_from_obj(obj)
            if not any(str(row.get('nadomestni_vodja_id') or '') == person or
                       str(row.get('nadomestni_vodja_naziv') or '') == wanted_name
                       for row in rows):
                continue
            try:
                parsed = parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result

    def person_dates_by_year(self):
        return date_group(self.person_dates())


class ReplacementsPublicView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_public.pt')

    def __call__(self):
        return self.template()


class ReplacementsAdminView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_admin.pt')

    def __call__(self):
        return self.template()


class ReplacementsSelectView(ReplacementsBase):
    def __call__(self):
        folder = self.days_folder()
        try:
            if folder is None:
                raise ValueError(u'Manjka mapa nadomescanja-1.')
            day_id = parse_date(self.request.form.get('datum')).strftime('%Y-%m-%d')
            obj = folder.get(day_id)
            if obj is None:
                obj = api.content.create(container=folder, type='imi.replacements.day',
                                         id=day_id, title=day_id, safe_id=False,
                                         nadomescanja_json='[]')
            self.request.response.redirect(obj.absolute_url() + '/@@nadomescanja-edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(self.portal.absolute_url() + '/@@nadomescanja-admin')
        return ''


class ReplacementsCopyView(ReplacementsBase):
    def __call__(self):
        folder = self.days_folder()
        try:
            if folder is None:
                raise ValueError(u'Manjka mapa nadomescanja-1.')
            old_id = parse_date(self.request.form.get('star')).strftime('%Y-%m-%d')
            new_id = parse_date(self.request.form.get('nov')).strftime('%Y-%m-%d')
            source = folder.get(old_id)
            if source is None:
                raise ValueError(u'Obstoječi datum ne obstaja.')
            target = folder.get(new_id)
            if target is None:
                target = api.content.create(
                    container=folder, type='imi.replacements.day', id=new_id,
                    title=new_id, safe_id=False,
                    nadomescanja_json=str(getattr(source, 'nadomescanja_json', '') or '[]'))
            else:
                api.portal.show_message(u'Nadomeščanja za novi datum že obstajajo.',
                                        request=self.request, type='warning')
            self.request.response.redirect(target.absolute_url() + '/@@nadomescanja-edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(self.portal.absolute_url() + '/@@nadomescanja-admin')
        return ''


class ReplacementEditView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_edit.pt')

    def __call__(self):
        if self.request.method == 'POST':
            self.save()
        return self.template()

    def edit_rows(self):
        existing = {str(row.get('laboratorij_okrajsava') or ''): row
                    for row in self._rows_from_obj(self.context)}
        result = []
        for lab in self.laboratories():
            abbreviation = str(getattr(lab, 'okrajsava', '') or lab.getId())
            leader_ids = tuple(getattr(lab, 'privzeti_vodja', ()) or ())
            leader_id = str(leader_ids[0]) if leader_ids else ''
            result.append({
                'field': 'lab_' + lab.getId().replace('-', '_'),
                'abbreviation': abbreviation,
                'leader_id': leader_id,
                'leader': staff_title(self.context, leader_id),
                'selected': str(existing.get(abbreviation, {}).get('nadomestni_vodja_id') or ''),
            })
        return result

    def save(self):
        rows = []
        for item in self.edit_rows():
            replacement_id = str(self.request.form.get(item['field']) or '')
            if not replacement_id:
                continue
            rows.append({
                'laboratorij_okrajsava': item['abbreviation'],
                'privzeti_vodja_id': item['leader_id'],
                'privzeti_vodja_naziv': item['leader'],
                'nadomestni_vodja_id': replacement_id,
                'nadomestni_vodja_naziv': staff_title(self.context, replacement_id),
            })
        self.context.nadomescanja_json = json.dumps(
            rows, ensure_ascii=False, separators=(',', ':'))
        self.context.reindexObject()
        import transaction
        transaction.commit()
        api.portal.show_message(u'Nadomeščanja so shranjena.', request=self.request)


class ReplacementsExportView(ReplacementsBase):
    def __call__(self):
        from openpyxl import Workbook
        try:
            first, last = period(self.request)
        except ValueError as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(self.context.absolute_url())
            return ''
        person = str(self.request.form.get('izvoz-2-oseba') or
                     self.request.form.get('oseba') or '')
        folder = self.days_folder()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = 'izpis'
        heading = 'Izpis: %s - %s' % (
            first.strftime('%d.%m.%Y'), last.strftime('%d.%m.%Y'))
        if person:
            heading += ' za osebo ' + staff_title(self.context, person)
        sheet.cell(1, 1, heading)
        sheet.append([])
        sheet.append(['Datum', 'Enota', 'Vodja', u'Nadomešča'])
        if folder is not None:
            for obj in sorted(folder.objectValues(), key=lambda item: item.getId()):
                if getattr(obj, 'portal_type', None) != 'imi.replacements.day':
                    continue
                try:
                    day = parse_date(obj.getId())
                except ValueError:
                    continue
                if day < first or day > last:
                    continue
                for row in self._rows_from_obj(obj):
                    if person and str(row.get('nadomestni_vodja_id') or '') != person:
                        continue
                    sheet.append([
                        day.strftime('%d.%m.%Y'),
                        row.get('laboratorij_okrajsava', ''),
                        row.get('privzeti_vodja_naziv', ''),
                        row.get('nadomestni_vodja_naziv', ''),
                    ])
        payload = BytesIO()
        workbook.save(payload)
        payload.seek(0)
        filename = 'izpis_%s-%s.xlsx' % (
            first.strftime('%d_%m_%Y'), last.strftime('%d_%m_%Y'))
        self.request.response.setHeader(
            'Content-Type',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.request.response.setHeader(
            'Content-Disposition', 'attachment; filename="%s"' % filename)
        return payload.getvalue()


class ReplacementsChangeRequestView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_form.pt')

    def __call__(self):
        form = self.portal.get('sprememba-nadomescanja')
        if form is None:
            self.request.response.setStatus(404)
            return u'Obrazec Sprememba nadomeščanja ne obstaja.'
        from collective.easyform.browser.view import EasyFormFormEmbedded
        embedded = EasyFormFormEmbedded(form, self.request)
        original_action = embedded.action
        proxy_url = self.portal.absolute_url() + '/@@nadomescanja-change-request'
        embedded.action = lambda: proxy_url
        embedded.update()
        self.form_html = embedded.render()
        embedded.action = original_action
        return self.template()

    def rendered_form(self):
        return self.form_html

    def requested_date(self):
        try:
            return parse_date(
                self.request.form.get('datum'), default_today=True).strftime('%Y-%m-%d')
        except ValueError:
            return date.today().strftime('%Y-%m-%d')
