# -*- coding: utf-8 -*-
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
    parts = value.split('-')
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError('Datum mora biti v obliki LLLL-MM-DD.')
    year, month, day = [int(part) for part in parts]
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2200):
        raise ValueError('Neveljaven datum.')
    return '%04d-%02d-%02d' % (year, month, day)


def _publish_if_possible(obj):
    try:
        transitions = api.content.get_transitions(obj=obj)
        ids = [item.get('id') for item in transitions]
        if 'publish' in ids:
            api.content.transition(obj=obj, transition='publish')
    except Exception:
        pass


class DutyAdminView(BrowserView):
    """Plone 5 replacement for the legacy ``dezurstva_admin.pt`` page."""


class DutyHomeView(BrowserView):
    """Default site-root view: editor dashboard for editors, public page otherwise."""

    admin_template = ViewPageTemplateFile('duty_admin.pt')

    def __call__(self):
        portal = _portal(self.context)
        if api.user.has_permission('Modify portal content', obj=portal):
            return self.admin_template()

        # Until the legacy public dezurstva view is ported, keep anonymous users
        # on the migrated front page.  This will be replaced by the public view.
        front_page = portal.get('front-page')
        if front_page is not None:
            self.request.response.redirect(front_page.absolute_url())
            return ''
        return self.admin_template()


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
