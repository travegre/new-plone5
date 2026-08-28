# -*- coding: utf-8 -*-
"""Purpose-built editor views for legacy applications.

These views preserve the old business-oriented editing workflows instead of
exposing raw tuple/JSON storage fields to editors.
"""
from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .legacy_sites import KIESTRA_COPY_FIELDS
from .legacy_sites import _parse_date
from .legacy_sites import _portal
from .legacy_sites import _settings_days
from .legacy_sites import _staff_options
from .legacy_sites import _staff_title


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


class KiestraSelectView(BrowserView):
    """Open/create the chosen work day in the dedicated Kiestra editor."""

    def __call__(self):
        portal = _portal(self.context)
        folder = _settings_days(portal)
        try:
            if folder is None:
                raise ValueError(u'Manjka mapa nastavitve/dezurstva.')
            day_id = _parse_date(self.request.form.get('datum')).strftime('%Y-%m-%d')
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
    """Copy one Kiestra work day while preserving every legacy field."""

    def __call__(self):
        portal = _portal(self.context)
        folder = _settings_days(portal)
        try:
            old_id = _parse_date(self.request.form.get('star')).strftime('%Y-%m-%d')
            new_id = _parse_date(self.request.form.get('nov')).strftime('%Y-%m-%d')
            source = folder.get(old_id) if folder is not None else None
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
        return _staff_options(self.context)

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
        return [_staff_title(self.context, value) for value in row['selected']]

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
