# -*- coding: utf-8 -*-
from datetime import date
from datetime import datetime
from datetime import timedelta

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


ROSTER_TYPE = 'imi.duty.roster_day'
ROSTER_FOLDER_ID = 'dezurstva-1'
COPY_FIELDS = (
    'dezurni_zdravnik', 'nadzorni_zdravnik', 'specializant', 'sarsifon',
    'dezurni_tehnik', 'izobrazevanje', 'bakterioloski_tehnik',
    'inoqula_tehnik', 'sprejem_predpriprava_tehnik', 'vpis',
    'intervencijska_skupina', 'intervencijska_skupina_telefon',
    'BOR', 'HIV', 'HUM', 'IT', 'PRZ', 'KLM', 'KOV', 'VINVZV', 'VINDIF',
    'WHO', 'kiestra', 'klukca',
)

TEAM_FIELDS = (
    ('dezurni_zdravnik', u'dežurni zdravnik'),
    ('nadzorni_zdravnik', u'nadzorni zdravnik'),
    ('specializant', u'specializant na usposabljanju'),
    ('sarsifon', u'Virološki laboratoriji'),
    ('bakterioloski_tehnik', u'Urgentni laboratorij'),
    ('inoqula_tehnik', u'BMK laboratorij'),
    ('sprejem_predpriprava_tehnik', u'sprejem/predpriprava'),
    ('vpis', u'vpis'),
    ('intervencijska_skupina', u'Intervencijska skupina'),
)

READINESS_FIELDS = (
    ('BOR', u'BOR'),
    ('HIV', u'HIV'),
    ('HUM', u'HUM'),
    ('PRZ', u'PRZ'),
    ('IT', u'IT'),
    ('KLM', u'KLM'),
    ('KOV', u'VZ'),
    ('WHO', u'WHO'),
    ('kiestra', u'Kiestra'),
)

DAY_NAMES = {
    0: u'ponedeljek', 1: u'torek', 2: u'sreda', 3: u'četrtek',
    4: u'petek', 5: u'sobota', 6: u'nedelja',
}


def _portal(context):
    return api.portal.get()


def _roster_folder(context):
    portal = _portal(context)
    folder = portal.get(ROSTER_FOLDER_ID)
    if folder is None:
        raise KeyError('Missing roster folder /%s/%s' % (portal.getId(), ROSTER_FOLDER_ID))
    return folder


def _normalise_date(value):
    value = (value or '').strip()
    if not value:
        raise ValueError('Datum je obvezen.')
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Datum mora biti veljaven in v obliki LLLL-MM-DD.')
    return parsed.strftime('%Y-%m-%d')


def _publish_if_possible(obj):
    try:
        transitions = api.content.get_transitions(obj=obj)
        ids = [item.get('id') for item in transitions]
        if 'publish' in ids:
            api.content.transition(obj=obj, transition='publish')
    except Exception:
        pass


class DutyPublicView(BrowserView):
    """Plone-5 public replacement for the old dezurstva_brez_kontaktov skin."""

    template = ViewPageTemplateFile('duty_public.pt')

    def __call__(self):
        return self.template()

    @property
    def portal(self):
        return _portal(self.context)

    @property
    def roster_folder(self):
        return _roster_folder(self.context)

    def selected_date(self):
        raw = self.request.form.get('datum')
        if raw:
            try:
                return datetime.strptime(_normalise_date(raw), '%Y-%m-%d').date()
            except ValueError:
                pass
        return date.today()

    def selected_date_id(self):
        return self.selected_date().strftime('%Y-%m-%d')

    def formatted_date(self):
        selected = self.selected_date()
        prefix = u'danes, ' if selected == date.today() else u''
        return u'%s%s, %02d.%02d.%04d' % (
            prefix, DAY_NAMES[selected.weekday()], selected.day,
            selected.month, selected.year)

    def previous_date(self):
        return (self.selected_date() - timedelta(days=1)).strftime('%Y-%m-%d')

    def next_date(self):
        return (self.selected_date() + timedelta(days=1)).strftime('%Y-%m-%d')

    def roster(self):
        return self.roster_folder.get(self.selected_date_id())

    def _staff_directory(self):
        return self.portal.get('seznam_zaposlenih')

    def staff_title(self, employee_id):
        directory = self._staff_directory()
        employee_id = str(employee_id or '')
        if directory is not None:
            employee = directory.get(employee_id)
            if employee is not None:
                try:
                    return employee.Title() or employee_id
                except Exception:
                    pass
        return employee_id

    def _field_rows(self, definitions):
        roster = self.roster()
        if roster is None:
            return []
        rows = []
        for field_name, label in definitions:
            values = list(getattr(roster, field_name, ()) or ())
            if field_name == 'vpis':
                values.reverse()  # preserve the old public template semantics
            for employee_id in values:
                rows.append({
                    'field': field_name,
                    'label': label,
                    'employee_id': str(employee_id),
                    'name': self.staff_title(employee_id),
                })
        return rows

    def team_rows(self):
        return self._field_rows(TEAM_FIELDS)

    def readiness_rows(self):
        return self._field_rows(READINESS_FIELDS)

    def intervention_phone(self):
        roster = self.roster()
        return getattr(roster, 'intervencijska_skupina_telefon', '') if roster is not None else ''

    def last_change(self):
        try:
            brains = self.portal.portal_catalog(
                portal_type=ROSTER_TYPE,
                path='/'.join(self.roster_folder.getPhysicalPath()),
                sort_on='modified', sort_order='descending')
            if not brains:
                return u''
            value = brains[0].modified.asdatetime()
            return value.strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return u''

    def staff_options(self):
        directory = self._staff_directory()
        if directory is None:
            return []
        result = []
        for employee in directory.objectValues():
            if getattr(employee, 'portal_type', None) != 'imi.staff.employee':
                continue
            if bool(getattr(employee, 'exclude_from_nav', False)):
                continue
            employee_id = str(employee.getId())
            result.append((employee_id, employee.Title() or employee_id))
        return sorted(result, key=lambda item: item[1].lower())

    def selected_person(self):
        return str(self.request.form.get('oseba') or '')

    def person_dates(self):
        person = self.selected_person()
        if not person:
            return []
        rows = []
        try:
            brains = self.portal.portal_catalog(
                portal_type=ROSTER_TYPE,
                path='/'.join(self.roster_folder.getPhysicalPath()),
                sort_on='id', sort_order='ascending')
            for brain in brains:
                obj = brain.getObject()
                if person in tuple(getattr(obj, 'dezurni_zdravnik', ()) or ()):
                    try:
                        parsed = datetime.strptime(obj.getId(), '%Y-%m-%d').date()
                    except ValueError:
                        continue
                    rows.append({
                        'id': obj.getId(),
                        'label': '%02d.%02d.%04d' % (parsed.day, parsed.month, parsed.year),
                    })
        except Exception:
            pass
        return rows


class DutyAdminView(BrowserView):
    """Plone 5 replacement for the legacy ``dezurstva_admin.pt`` page."""


class DutyHomeView(BrowserView):
    """Default site-root view: editor dashboard for editors, public roster otherwise."""

    admin_template = ViewPageTemplateFile('duty_admin.pt')
    public_template = ViewPageTemplateFile('duty_public.pt')

    def __call__(self):
        portal = _portal(self.context)
        if api.user.has_permission('Modify portal content', obj=portal):
            return self.admin_template()
        # Render through DutyPublicView so all public helper methods are present.
        return DutyPublicView(self.context, self.request)()


class SelectDutyView(BrowserView):
    """Open an existing roster day or create it, then enter edit mode."""

    def __call__(self):
        request = self.request
        try:
            date_id = _normalise_date(request.form.get('datum'))
            folder = _roster_folder(self.context)
            obj = folder.get(date_id)
            if obj is None:
                obj = api.content.create(
                    container=folder,
                    type=ROSTER_TYPE,
                    id=date_id,
                    title=date_id,
                )
                _publish_if_possible(obj)
            request.response.redirect(obj.absolute_url() + '/edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=request, type='error')
            request.response.redirect(_portal(self.context).absolute_url() + '/@@dezurstva-admin')
        return ''


class CopyDutyView(BrowserView):
    """Clone duty-roster values from one date to another."""

    def __call__(self):
        request = self.request
        portal = _portal(self.context)
        try:
            source_id = _normalise_date(request.form.get('star'))
            target_id = _normalise_date(request.form.get('nov'))
            folder = _roster_folder(self.context)
            target = folder.get(target_id)
            if target is not None:
                api.portal.show_message(u'Dežurstvo že obstaja.', request=request, type='warning')
                request.response.redirect(target.absolute_url() + '/edit')
                return ''

            source = folder.get(source_id)
            if source is None:
                raise KeyError(u'Izvorno dežurstvo %s ne obstaja.' % source_id)

            values = {}
            for name in COPY_FIELDS:
                if hasattr(source, name):
                    values[name] = getattr(source, name)

            target = api.content.create(
                container=folder,
                type=ROSTER_TYPE,
                id=target_id,
                title=target_id,
                **values
            )
            _publish_if_possible(target)
            api.portal.show_message(u'Dežurstvo je bilo uspešno kopirano.', request=request)
            request.response.redirect(folder.absolute_url())
        except Exception as exc:
            api.portal.show_message(str(exc), request=request, type='error')
            request.response.redirect(portal.absolute_url() + '/@@dezurstva-admin')
        return ''
