# -*- coding: utf-8 -*-
"""Kiestra public, admin and editor views."""
from datetime import date, timedelta

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from ..common.helpers import date_group
from ..common.helpers import formatted_date
from ..common.helpers import inner_site
from ..common.helpers import parse_date
from ..common.helpers import rich
from ..common.helpers import staff_options
from ..common.helpers import staff_title


KIESTRA_FIELDS = (
    ('priprava_vzorcev', 'priprava_vzorcev_text', u'Priprava vzorcev'),
    ('cepljenje_vzorcev', 'cepljenje_vzorcev_text', u'Inoqula + Sortera'),
    ('odcitavanje', 'odcitavanje_text', u'Odčitavanje'),
    ('identifikacija', 'identifikacija_text', u'Ime bakterije'),
    ('antibiogram', 'antibiogram_text', u'ID+ATB, ATB, izolacija'),
    ('odpad', 'odpad_text', u'OFF'),
)
KIESTRA_COPY_FIELDS = (
    'priprava_vzorcev', 'priprava_vzorcev_text', 'cepljenje_vzorcev',
    'cepljenje_vzorcev_text', 'odcitavanje', 'odcitavanje_text',
    'identifikacija', 'identifikacija_text', 'antibiogram',
    'antibiogram_text', 'izolacija', 'izolacija_text', 'odpad',
    'odpad_text', 'ciscenje', 'ciscenje_text', 'stalni_tekst',
)
KIESTRA_EDIT_FIELDS = (
    ('priprava_vzorcev', 'priprava_vzorcev_text', u'Priprava vzorcev'),
    ('cepljenje_vzorcev', 'cepljenje_vzorcev_text', u'Inoqula + Sortera'),
    ('odcitavanje', 'odcitavanje_text', u'Odčitavanje'),
    ('identifikacija', 'identifikacija_text', u'Ime bakterije'),
    ('antibiogram', 'antibiogram_text', u'ID+ATB, ATB, izolacija'),
    ('izolacija', 'izolacija_text', u'Waste'),
    ('odpad', 'odpad_text', u'OFF'),
    ('ciscenje', 'ciscenje_text', u'Čiščenje kiestre'),
)


def _days_folder(portal):
    folder = portal.get('dezurstva-1')
    if folder is not None:
        return folder
    settings = portal.get('nastavitve')
    return settings.get('dezurstva') if settings is not None else None


class KiestraPublicView(BrowserView):
    template = ViewPageTemplateFile('kiestra_public.pt')

    def __call__(self):
        return self.template()

    @property
    def portal(self):
        return inner_site(self.context, 'kiestra')

    def selected_date(self):
        try:
            return parse_date(self.request.form.get('datum'), default_today=True)
        except ValueError:
            return date.today()

    def selected_date_id(self):
        return self.selected_date().strftime('%Y-%m-%d')

    def today_id(self):
        return date.today().strftime('%Y-%m-%d')

    def formatted_date(self):
        return formatted_date(self.selected_date())

    def previous_date(self):
        return (self.selected_date() - timedelta(days=1)).strftime('%Y-%m-%d')

    def next_date(self):
        return (self.selected_date() + timedelta(days=1)).strftime('%Y-%m-%d')

    def _days(self):
        return _days_folder(self.portal)

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
        try:
            latest = max(objects, key=lambda obj: obj.modified())
            return latest.modified().strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return ''

    def _short_name(self, identifier):
        title = staff_title(self.context, identifier).strip()
        parts = title.split()
        if len(parts) > 1:
            return u'%s %s.' % (parts[0], parts[-1][0])
        return title

    def columns(self):
        obj = self.day_object()
        result = []
        for field, note_field, label in KIESTRA_FIELDS:
            values = list(getattr(obj, field, ()) or ()) if obj is not None else []
            result.append({
                'field': field,
                'label': label,
                'names': [self._short_name(value) for value in values],
                'note': str(getattr(obj, note_field, '') or '') if obj is not None else '',
            })
        return result

    def rows(self):
        columns = self.columns()
        maximum = max([len(col['names']) for col in columns] + [0])
        return [[col['names'][idx] if idx < len(col['names']) else '' for col in columns]
                for idx in range(maximum)]

    def notes(self):
        return [col['note'] for col in self.columns()]

    def constant_text(self):
        obj = self.day_object()
        return rich(getattr(obj, 'stalni_tekst', None)) if obj is not None else ''

    def staff_options(self):
        return staff_options(self.context)

    def selected_person(self):
        return str(self.request.form.get('oseba') or '')

    def selected_person_title(self):
        return staff_title(self.context, self.selected_person())

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
                parsed = parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result

    def person_dates_by_year(self):
        return date_group(self.person_dates())


class KiestraAdminView(KiestraPublicView):
    template = ViewPageTemplateFile('kiestra_admin.pt')

    def __call__(self):
        return self.template()


class KiestraSelectView(BrowserView):
    def __call__(self):
        portal = inner_site(self.context, 'kiestra')
        folder = _days_folder(portal)
        try:
            if folder is None:
                raise ValueError(u'Manjka mapa z dnevnimi razporedi Kiestre.')
            day_id = parse_date(self.request.form.get('datum')).strftime('%Y-%m-%d')
            obj = folder.get(day_id)
            if obj is None:
                obj = api.content.create(
                    container=folder, type='imi.kiestra.work_day', id=day_id,
                    title=day_id, safe_id=False)
            self.request.response.redirect(obj.absolute_url() + '/@@kiestra-edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(portal.absolute_url() + '/@@kiestra-admin')
        return ''


class KiestraCopyView(BrowserView):
    def __call__(self):
        portal = inner_site(self.context, 'kiestra')
        folder = _days_folder(portal)
        try:
            if folder is None:
                raise ValueError(u'Manjka mapa z dnevnimi razporedi Kiestre.')
            old_id = parse_date(self.request.form.get('star')).strftime('%Y-%m-%d')
            new_id = parse_date(self.request.form.get('nov')).strftime('%Y-%m-%d')
            source = folder.get(old_id)
            if source is None:
                raise ValueError(u'Obstoječi datum ne obstaja.')
            target = folder.get(new_id)
            if target is None:
                values = {name: getattr(source, name) for name in KIESTRA_COPY_FIELDS
                          if hasattr(source, name)}
                target = api.content.create(
                    container=folder, type='imi.kiestra.work_day', id=new_id,
                    title=new_id, safe_id=False, **values)
            else:
                api.portal.show_message(u'Dežurstvo že obstaja.',
                                        request=self.request, type='warning')
            self.request.response.redirect(target.absolute_url() + '/@@kiestra-edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(portal.absolute_url() + '/@@kiestra-admin')
        return ''


class KiestraEditView(BrowserView):
    template = ViewPageTemplateFile('kiestra_edit.pt')

    def __call__(self):
        if self.request.method == 'POST':
            self.save()
        return self.template()

    def staff_options(self):
        return staff_options(self.context)

    def fields(self):
        result = []
        for field, note_field, label in KIESTRA_EDIT_FIELDS:
            result.append({
                'field': field,
                'note_field': note_field,
                'label': label,
                'selected': tuple(str(v) for v in (getattr(self.context, field, ()) or ())),
                'note': str(getattr(self.context, note_field, '') or ''),
            })
        return result

    def selected_titles(self, row):
        return [staff_title(self.context, value) for value in row['selected']]

    def constant_text(self):
        value = getattr(self.context, 'stalni_tekst', None)
        return getattr(value, 'raw', None) or ''

    def save(self):
        from plone.app.textfield.value import RichTextValue

        for field, note_field, _label in KIESTRA_EDIT_FIELDS:
            values = self.request.form.get(field, ())
            if isinstance(values, str):
                values = (values,)
            setattr(self.context, field, tuple(str(v) for v in values if str(v)))
            setattr(self.context, note_field, str(self.request.form.get(note_field) or ''))
        raw = str(self.request.form.get('stalni_tekst') or '')
        self.context.stalni_tekst = RichTextValue(
            raw=raw, mimeType='text/html', outputMimeType='text/x-html-safe')
        self.context.reindexObject()
        api.portal.show_message(u'Dežurstvo je shranjeno.', request=self.request)
