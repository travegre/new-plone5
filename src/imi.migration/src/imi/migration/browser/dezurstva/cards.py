# -*- coding: utf-8 -*-
"""Card-based Dežurstva roster editing and read-only display.

Keep the legacy roster's stored employee IDs and field semantics intact.
"""
from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from ..common.helpers import staff_options, staff_title
from .duty import TEAM_FIELDS, READINESS_FIELDS


# These fields were omitted from the old Plone editing form; never clear them.
HIDDEN_FIELDS = ('dezurni_tehnik', 'izobrazevanje', 'VINVZV', 'VINDIF')
GROUPS = (
    (u'Dežurna ekipa', TEAM_FIELDS + (
        ('intervencijska_skupina', u'Intervencijska skupina'),
    )),
    (u'Stanje pripravljenosti', READINESS_FIELDS),
)


class DutyCardsBase(BrowserView):
    def groups(self):
        result = []
        for heading, fields in GROUPS:
            rows = []
            for field, label in fields:
                selected = tuple(str(v) for v in (getattr(self.context, field, ()) or ()))
                rows.append({
                    'field': field,
                    'label': label,
                    'selected': selected,
                    'people': [staff_title(self.context, value) for value in selected],
                })
            result.append({'heading': heading, 'rows': rows})
        return result

    def staff_options(self):
        return staff_options(self.context)

    def options_for(self, row):
        """Include legacy selected IDs even when no longer in the directory."""
        options = list(self.staff_options())
        existing = set(str(value) for value, _label in options)
        for value in row['selected']:
            if value not in existing:
                options.append((value, staff_title(self.context, value)))
        return options

    def intervention_phone(self):
        return str(getattr(self.context, 'intervencijska_skupina_telefon', '') or '')

    def copy_week(self):
        return bool(getattr(self.context, 'klukca', False))


class DutyCardsView(DutyCardsBase):
    template = ViewPageTemplateFile('duty_cards_view.pt')

    def __call__(self):
        return self.template()


class DutyCardsEdit(DutyCardsBase):
    template = ViewPageTemplateFile('duty_cards_edit.pt')

    def __call__(self):
        self.request.response.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.request.response.setHeader('Pragma', 'no-cache')
        if self.request.method == 'POST':
            self.save()
            self.request.response.redirect(self.context.absolute_url(), status=303)
            return ''
        return self.template()

    def save(self):
        request = self.request.form
        for _heading, fields in GROUPS:
            for field, _label in fields:
                values = request.get(field, ())
                if isinstance(values, str):
                    values = (values,)
                setattr(self.context, field, tuple(str(v) for v in values if str(v)))
        self.context.intervencijska_skupina_telefon = str(
            request.get('intervencijska_skupina_telefon') or '')
        self.context.klukca = bool(request.get('klukca'))
        self.context.reindexObject()
        api.portal.show_message(u'Dežurstvo je shranjeno.', request=self.request)
