# -*- coding: utf-8 -*-
"""Plone 5 browser implementations for the four remaining legacy sites.

The old Plone 4 applications used site-specific portal_skins main templates,
Python Scripts and Archetypes helper methods.  Keep their business behavior in
explicit browser views instead of reviving the old global skin machinery.
"""
from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO
import json

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


DAY_NAMES = {
    0: u'ponedeljek', 1: u'torek', 2: u'sreda', 3: u'četrtek',
    4: u'petek', 5: u'sobota', 6: u'nedelja',
}
MONTH_NAMES = {
    1: u'januar', 2: u'februar', 3: u'marec', 4: u'april',
    5: u'maj', 6: u'junij', 7: u'julij', 8: u'avgust',
    9: u'september', 10: u'oktober', 11: u'november', 12: u'december',
}
BACKGROUND_DATA = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAYAAAADCAIAAAA/Y+msAAAABGdBTUEAAK/INwWK6QAAABl0'
    'RVh0U29mdHdhcmUAQWRvYmUgSW1hZ2VSZWFkeXHJZTwAAAAcSURBVHjaYnr69Ol/MIAzGJD5'
    'EJIBWR7CBggwAMnZM/mCB9LIAAAAAElFTkSuQmCC'
)


def _portal(context):
    return api.portal.get()


def _application(context):
    root = context.getPhysicalRoot()
    return root


def _sibling_site(context, site_id):
    root = _application(context)
    return root.get(site_id)


def _staff_directory(context):
    site = _sibling_site(context, 'dezurstva')
    return site.get('seznam_zaposlenih') if site is not None else None


def _staff_objects(context):
    directory = _staff_directory(context)
    if directory is None:
        return []
    result = []
    for employee in directory.objectValues():
        if getattr(employee, 'portal_type', None) != 'imi.staff.employee':
            continue
        if bool(getattr(employee, 'exclude_from_nav', False)):
            continue
        result.append(employee)
    return result


def _employee_id(employee):
    return str(getattr(employee, 'source_employee_id', '') or employee.getId())


def _employee_by_id(context, identifier):
    identifier = str(identifier or '')
    directory = _staff_directory(context)
    if directory is None:
        return None
    found = directory.get(identifier)
    if found is not None:
        return found
    for employee in _staff_objects(context):
        if _employee_id(employee) == identifier:
            return employee
    return None


def _staff_title(context, identifier):
    employee = _employee_by_id(context, identifier)
    return employee.Title() if employee is not None else str(identifier or '')


def _staff_options(context):
    items = [(_employee_id(employee), employee.Title() or _employee_id(employee))
             for employee in _staff_objects(context)]
    return sorted(items, key=lambda item: item[1].lower())


def _parse_date(value, default_today=False):
    value = str(value or '').strip()
    if not value and default_today:
        return date.today()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(u'Datum mora biti veljaven.')


def _formatted_date(value):
    prefix = u'danes, ' if value == date.today() else u''
    return u'%s%s, %02d.%02d.%04d' % (
        prefix, DAY_NAMES[value.weekday()], value.day, value.month, value.year)


def _rich(value):
    if value is None:
        return u''
    output = getattr(value, 'output', None)
    if output is not None:
        return output
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return raw
    return str(value)


def _period(request):
    mode = str(request.form.get('izbira') or request.form.get('izvoz-1-izbira') or
               request.form.get('izvoz-2-izbira') or '')
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if mode == 'teden':
        return monday - timedelta(days=7), monday - timedelta(days=1)
    if mode == 'tedenplus2':
        return monday, monday + timedelta(days=14)
    if mode == 'tekoci':
        first = today.replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first, next_month - timedelta(days=1)
    if mode == 'pretekli':
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        return last.replace(day=1), last
    if mode == 'oddo':
        first = _parse_date(request.form.get('od'))
        last = _parse_date(request.form.get('do'))
        return (first, last) if first <= last else (last, first)
    raise ValueError(u'Izberite obdobje za izvoz.')


def _date_group(rows):
    grouped = {}
    for item in rows:
        grouped.setdefault(item['date'].year, {}).setdefault(item['date'].month, []).append(item)
    result = []
    for year in sorted(grouped, reverse=True):
        months = []
        for month in sorted(grouped[year], reverse=True):
            months.append({
                'number': month,
                'name': MONTH_NAMES[month],
                'dates': sorted(grouped[year][month], key=lambda row: row['date'], reverse=True),
            })
        result.append({'year': year, 'months': months})
    return result


def _editor(context):
    return api.user.has_permission('Modify portal content', obj=context)


# ---------------------------------------------------------------------------
# IMI IMENIK /portal
# ---------------------------------------------------------------------------

class DirectoryPublicView(BrowserView):
    template = ViewPageTemplateFile('directory_public.pt')

    def __call__(self):
        return self.template()

    @property
    def portal(self):
        return _portal(self.context)

    def categories(self):
        base = self.portal.get('data2')
        if base is None:
            return []
        result = []
        for folder in base.objectValues():
            if getattr(folder, 'portal_type', None) != 'Folder':
                continue
            children = [child for child in folder.objectValues()
                        if getattr(child, 'portal_type', None) == 'Folder']
            result.append({
                'title': folder.Title() or folder.getId(),
                'children': [child.Title() or child.getId() for child in children],
            })
        return result

    def is_editor(self):
        return _editor(self.portal)


class DirectoryHomeView(DirectoryPublicView):
    admin_template = ViewPageTemplateFile('directory_admin.pt')

    def __call__(self):
        if self.is_editor():
            return self.admin_template()
        return self.template()


class DirectorySearchView(BrowserView):
    """HTML response compatible with the old livesearch_reply business output."""

    searchable_fields = (
        'title', 'predime', 'ime', 'priimek', 'zaime', 'oddelek', 'telefon',
        'opis', 'enota', 'lokacija', 'dodatna', 'dect', 'fax', 'mobilna',
        'multitone', 'zunanja', 'enaslov', 'zenaslov',
    )

    def _matches(self, obj, words):
        values = []
        for field in self.searchable_fields:
            if field == 'title':
                value = obj.Title()
            else:
                value = getattr(obj, field, '')
            values.append(str(value or '').lower())
        haystack = u' '.join(values)
        return all(word in haystack for word in words)

    def _phone(self, value, mobile=False):
        value = str(value or '').strip()
        if not value:
            return ''
        if mobile:
            return value if value.startswith('0') else '0' + value
        if len(value) < 7:
            return '(01)\u00a0522\u00a0' + value
        return value

    def __call__(self):
        portal = _portal(self.context)
        query = str(self.request.form.get('q') or self.request.form.get('searchGadget') or '').strip()
        words = [word.lower() for word in query.replace('*', ' ').replace('+', ' ').split() if word]
        brains = portal.portal_catalog(
            portal_type='imi.directory.person',
            path='/'.join(portal.getPhysicalPath()),
        )
        objects = []
        if words:
            for brain in brains:
                obj = brain.getObject()
                if self._matches(obj, words):
                    objects.append(obj)
        objects.sort(key=lambda obj: ((getattr(obj, 'priimek', '') or 'ŽŽŽŽŽ').lower(),
                                      (getattr(obj, 'ime', '') or '').lower()))

        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not objects:
            return (u'<fieldset class="livesearchContainer"><legend id="livesearchLegend">'
                    u'LiveSearch ↓</legend><div class="LSIEFix"><div id="LSNothingFound">'
                    u'No matching results found.</div></div></fieldset>')

        out = [u'<fieldset class="livesearchContainer">',
               u'<legend id="livesearchLegend">LiveSearch ↓ zadetkov: %d</legend>' % len(objects),
               u'<div class="LSIEFix"><table class="tabela" cellspacing="0" cellpadding="0">',
               u'<thead><tr><th></th><th>Ime</th><th>Priimek</th><th></th><th>Oddelek</th>'
               u'<th>Telefon</th><th>DECT</th><th>Mobilna</th><th>Enota</th></tr></thead><tbody>']
        for obj in objects:
            phone = self._phone(getattr(obj, 'telefon', ''))
            dect = self._phone(getattr(obj, 'dect', ''))
            mobile = self._phone(getattr(obj, 'mobilna', ''), mobile=True)
            details = []
            for label, attr, is_phone in (
                ('Telefon', 'telefon', True), ('Dodatna', 'dodatna', True),
                ('DECT', 'dect', True), ('Fax', 'fax', True),
                ('Mobitel', 'mobilna', False), ('Multitone', 'multitone', True),
                ('Zunanja', 'zunanja', False),
            ):
                raw = getattr(obj, attr, '') or ''
                if raw:
                    value = self._phone(raw, mobile=(attr in ('mobilna', 'zunanja'))) if is_phone or attr in ('mobilna', 'zunanja') else raw
                    details.append(u'<br />%s: %s' % (escape(label), escape(str(value))))
            for label, attr in (('E-naslov', 'enaslov'), ('Zunanji e-naslov', 'zenaslov')):
                value = str(getattr(obj, attr, '') or '')
                if value:
                    details.append(u'<br />%s: <a href="mailto:%s">%s</a>' %
                                   (escape(label), escape(value), escape(value)))
            full_name = u' '.join(filter(None, [str(getattr(obj, 'predime', '') or ''),
                                                str(getattr(obj, 'ime', '') or ''),
                                                str(getattr(obj, 'priimek', '') or ''),
                                                str(getattr(obj, 'zaime', '') or '')]))
            out.append(u'<tr class="tri" data-person="%s">' % escape(obj.getId()))
            out.append(u'<td class="enota">%s</td><td>%s</td><td>%s</td><td class="enota">%s</td>' % (
                escape(str(getattr(obj, 'predime', '') or '')),
                escape(str(getattr(obj, 'ime', '') or '')),
                escape(str(getattr(obj, 'priimek', '') or '')),
                escape(str(getattr(obj, 'zaime', '') or ''))))
            out.append(u'<td class="enota">%s</td><td>%s</td><td class="enota">%s</td>'
                       u'<td class="enota">%s</td><td class="enota">%s</td></tr>' % (
                           escape(str(getattr(obj, 'oddelek', '') or '')), escape(phone), escape(dect),
                           escape(mobile), escape(str(getattr(obj, 'enota', '') or ''))))
            out.append(u'<tr class="person-detail"><td colspan="9"><div class="ime">%s</div>'
                       u'<div class="stevilka">%s</div><br />%s<br />%s<br />%s<br />%s%s</td></tr>' % (
                           escape(full_name), escape(phone),
                           escape(str(getattr(obj, 'oddelek', '') or '')),
                           escape(str(getattr(obj, 'opis', '') or '')),
                           escape(str(getattr(obj, 'enota', '') or '')),
                           escape(str(getattr(obj, 'lokacija', '') or '')),
                           u''.join(details)))
        out.append(u'</tbody></table></div></fieldset>')
        return u''.join(out)


# ---------------------------------------------------------------------------
# KIESTRA /kiestra
# ---------------------------------------------------------------------------

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


def _settings_days(portal):
    settings = portal.get('nastavitve')
    if settings is None:
        return None
    return settings.get('dezurstva')


class KiestraPublicView(BrowserView):
    template = ViewPageTemplateFile('kiestra_public.pt')

    def __call__(self):
        return self.template()

    @property
    def portal(self):
        return _portal(self.context)

    def selected_date(self):
        try:
            return _parse_date(self.request.form.get('datum'), default_today=True)
        except ValueError:
            return date.today()

    def selected_date_id(self):
        return self.selected_date().strftime('%Y-%m-%d')

    def today_id(self):
        return date.today().strftime('%Y-%m-%d')

    def formatted_date(self):
        return _formatted_date(self.selected_date())

    def previous_date(self):
        return (self.selected_date() - timedelta(days=1)).strftime('%Y-%m-%d')

    def next_date(self):
        return (self.selected_date() + timedelta(days=1)).strftime('%Y-%m-%d')

    def day_object(self):
        folder = _settings_days(self.portal)
        return folder.get(self.selected_date_id()) if folder is not None else None

    def last_change(self):
        folder = _settings_days(self.portal)
        if folder is None:
            return ''
        brains = self.portal.portal_catalog(
            portal_type='imi.kiestra.work_day',
            path='/'.join(folder.getPhysicalPath()), sort_on='modified', sort_order='descending')
        if not brains:
            return ''
        return brains[0].modified.asdatetime().strftime('%d.%m.%Y ob %H:%M')

    def _short_name(self, identifier):
        title = _staff_title(self.context, identifier).strip()
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
                'field': field, 'label': label,
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
        return _rich(getattr(obj, 'stalni_tekst', None)) if obj is not None else ''

    def staff_options(self):
        return _staff_options(self.context)

    def selected_person(self):
        return str(self.request.form.get('oseba') or '')

    def selected_person_title(self):
        return _staff_title(self.context, self.selected_person())

    def person_dates(self):
        person = self.selected_person()
        folder = _settings_days(self.portal)
        if not person or folder is None:
            return []
        result = []
        brains = self.portal.portal_catalog(
            portal_type='imi.kiestra.work_day', path='/'.join(folder.getPhysicalPath()),
            sort_on='id', sort_order='ascending')
        for brain in brains:
            obj = brain.getObject()
            if person not in tuple(str(x) for x in (getattr(obj, 'priprava_vzorcev', ()) or ())):
                continue
            try:
                parsed = _parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result

    def person_dates_by_year(self):
        return _date_group(self.person_dates())

    def is_editor(self):
        return _editor(self.portal)


class KiestraHomeView(KiestraPublicView):
    admin_template = ViewPageTemplateFile('kiestra_admin.pt')

    def __call__(self):
        if self.is_editor():
            return self.admin_template()
        return self.template()


class KiestraSelectView(BrowserView):
    def __call__(self):
        portal = _portal(self.context)
        folder = _settings_days(portal)
        if folder is None:
            raise KeyError('Missing /kiestra/nastavitve/dezurstva')
        try:
            day = _parse_date(self.request.form.get('datum'))
            day_id = day.strftime('%Y-%m-%d')
            obj = folder.get(day_id)
            if obj is None:
                obj = api.content.create(container=folder, type='imi.kiestra.work_day',
                                         id=day_id, title=day_id, safe_id=False)
            self.request.response.redirect(obj.absolute_url() + '/edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(portal.absolute_url() + '/@@kiestra-admin')
        return ''


class KiestraCopyView(BrowserView):
    def __call__(self):
        portal = _portal(self.context)
        folder = _settings_days(portal)
        try:
            old_id = _parse_date(self.request.form.get('star')).strftime('%Y-%m-%d')
            new_id = _parse_date(self.request.form.get('nov')).strftime('%Y-%m-%d')
            source = folder.get(old_id)
            if source is None:
                raise ValueError(u'Obstoječi datum ne obstaja.')
            target = folder.get(new_id)
            if target is None:
                values = {name: getattr(source, name) for name in KIESTRA_COPY_FIELDS
                          if hasattr(source, name)}
                target = api.content.create(container=folder, type='imi.kiestra.work_day',
                                            id=new_id, title=new_id, safe_id=False, **values)
            else:
                api.portal.show_message(u'Dežurstvo že obstaja.', request=self.request, type='warning')
            self.request.response.redirect(target.absolute_url() + '/edit')
        except Exception as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(portal.absolute_url() + '/@@kiestra-admin')
        return ''


# ---------------------------------------------------------------------------
# PREISKAVE /preiskave
# ---------------------------------------------------------------------------

EXAM_FIELDS_FOR_SEARCH = (
    'sifra', 'podrocje', 'sklop', 'sinonim', 'laboratoriji', 'metode', 'opis',
    'opombe', 'trajanje', 'urnik', 'vzorci', 'vzorci_lab', 'vzorci_lab_kratica',
)


class ExamsBase(BrowserView):
    @property
    def portal(self):
        return _portal(self.context)

    def is_editor(self):
        return _editor(self.portal)

    def base_folder(self):
        return self.portal.get('preiskave-1')

    def subfolders(self):
        base = self.base_folder()
        if base is None:
            return []
        result = []
        for child in base.objectValues():
            if getattr(child, 'portal_type', None) == 'Folder' and not bool(getattr(child, 'exclude_from_nav', False)):
                result.append({'title': child.Title() or child.getId(), 'url': child.absolute_url()})
        return result

    def _searchable(self, obj):
        values = [obj.Title(), obj.Description()]
        for name in EXAM_FIELDS_FOR_SEARCH:
            value = getattr(obj, name, '')
            if isinstance(value, (tuple, list)):
                values.extend(str(v) for v in value)
            else:
                values.append(_rich(value))
        return u' '.join(str(v or '') for v in values).lower()

    def all_exams(self):
        base = self.base_folder() or self.portal
        brains = self.portal.portal_catalog(
            portal_type='imi.exams.examination', path='/'.join(base.getPhysicalPath()),
            sort_on='sortable_title')
        return [brain.getObject() for brain in brains]

    def filtered_exams(self, query=None):
        query = str(query if query is not None else
                    (self.request.form.get('q') or self.request.form.get('SearchableText') or '')).strip()
        words = [word.lower() for word in query.replace('*', ' ').replace('+', ' ').split() if word]
        result = self.all_exams()
        if words:
            result = [obj for obj in result if all(word in self._searchable(obj) for word in words)]
        return result


class ExamsPublicView(ExamsBase):
    template = ViewPageTemplateFile('exams_home.pt')

    def __call__(self):
        return self.template()

    def results(self):
        query = str(self.request.form.get('q') or '').strip()
        return self.filtered_exams(query)[:50] if query else []

    def query(self):
        return str(self.request.form.get('q') or '')


class ExamsHomeView(ExamsPublicView):
    admin_template = ViewPageTemplateFile('exams_admin.pt')

    def __call__(self):
        if self.is_editor():
            return self.admin_template()
        return self.template()


class ExamsLiveSearchView(ExamsBase):
    def __call__(self):
        query = str(self.request.form.get('q') or '').strip()
        results = self.filtered_exams(query)
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return '<fieldset class="livesearchContainer"><legend>Live search</legend><div id="LSNothingFound">No match found</div></fieldset>'
        limit = 20
        out = ['<fieldset class="livesearchContainer"><legend>Live search results: %d</legend><ul class="LSTable">' % len(results)]
        for obj in results[:limit]:
            out.append('<li class="LSRow"><a href="%s">%s</a><div class="LSDescr">%s</div></li>' % (
                escape(obj.absolute_url()), escape(obj.Title()), escape(obj.Description() or '')))
        if len(results) > limit:
            out.append('<li class="LSRow">prikazanih %d od %d zadetkov</li>' % (limit, len(results)))
        out.append('</ul></fieldset>')
        return ''.join(out)


class ExamsListView(ExamsBase):
    template = ViewPageTemplateFile('exams_list.pt')

    def __call__(self):
        return self.template()

    def mode(self):
        url = str(self.request.get('URL') or '')
        return url.rstrip('/').rsplit('/', 1)[-1]

    def title(self):
        titles = {
            'preiskave_hitro_view': u'Hitro iskanje',
            'preiskave_lab_view': u'Preiskave po laboratorijih',
            'preiskave_nove_view': u'Nove preiskave',
            'preiskave_nujne_view': u'Nujne preiskave',
            'preiskave_podrocja_view': u'Preiskave po področjih',
            'preiskave_sklopi_view': u'Preiskave po sklopih',
            'preiskave_vzorci_view': u'Preiskave po vzorcih',
            'preiskave_view': u'Preiskave',
            'content_view': u'Preiskave',
        }
        return titles.get(self.mode(), u'Preiskave')

    def results(self):
        mode = self.mode()
        query = str(self.request.form.get('q') or self.request.form.get('SearchableText') or '').strip()
        exams = self.filtered_exams(query if mode == 'preiskave_hitro_view' else None)
        if mode == 'preiskave_nove_view':
            exams = [obj for obj in exams if str(getattr(obj, 'nova_pre', '') or '').strip().lower() not in ('', '0', 'false', 'ne')]
        elif mode == 'preiskave_nujne_view':
            exams = [obj for obj in exams if str(getattr(obj, 'nujna_pre', '') or '').strip().lower() not in ('', '0', 'false', 'ne')]
        elif mode == 'preiskave_lab_view':
            needle = str(self.request.form.get('lab') or '').strip().lower()
            if needle:
                exams = [obj for obj in exams if needle in str(getattr(obj, 'laboratoriji', '') or '').lower()]
        elif mode == 'preiskave_podrocja_view':
            needle = str(self.request.form.get('podrocje') or '').strip().lower()
            if needle:
                exams = [obj for obj in exams if needle in u' '.join(getattr(obj, 'podrocje', ()) or ()).lower()]
        elif mode == 'preiskave_sklopi_view':
            needle = str(self.request.form.get('sklop') or '').strip().lower()
            if needle:
                exams = [obj for obj in exams if needle in _rich(getattr(obj, 'sklop', '')).lower()]
        elif mode == 'preiskave_vzorci_view':
            needle = str(self.request.form.get('vzorec') or '').strip().lower()
            if needle:
                exams = [obj for obj in exams if needle in str(getattr(obj, 'vzorci', '') or '').lower()]
        return exams

    def query(self):
        return str(self.request.form.get('q') or self.request.form.get('SearchableText') or '')


class ExaminationView(ExamsBase):
    template = ViewPageTemplateFile('examination_public.pt')

    def __call__(self):
        return self.template()

    def rich(self, name):
        return _rich(getattr(self.context, name, ''))

    def text(self, name):
        value = getattr(self.context, name, '')
        if isinstance(value, (tuple, list)):
            return u', '.join(str(v) for v in value if v)
        return str(value or '')

    def code(self):
        value = str(getattr(self.context, 'sifra', '') or '')
        if value:
            return value
        object_id = self.context.getId()
        return object_id.split('_', 1)[1] if '_' in object_id else object_id

    def samples(self):
        raw_samples = getattr(self.context, 'vzorci', '') or ''
        if isinstance(raw_samples, (tuple, list)):
            samples = list(raw_samples)
        else:
            text = str(raw_samples)
            samples = [part for part in text.split('\n') if part.strip()]
            if len(samples) <= 1 and '###' in text:
                samples = [part for part in text.split('###') if part.strip()]
        return [str(item) for item in samples if str(item).strip()]


# ---------------------------------------------------------------------------
# NADOMEŠČANJA /nadomescanja
# ---------------------------------------------------------------------------

class ReplacementsBase(BrowserView):
    @property
    def portal(self):
        return _portal(self.context)

    def days_folder(self):
        return _settings_days(self.portal)

    def selected_date(self):
        try:
            return _parse_date(self.request.form.get('datum'), default_today=True)
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
        return _staff_options(self.context)

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
            leader = _staff_title(self.context, leader_ids[0]) if leader_ids else ''
            row = replacements.get(abbreviation, {})
            replacement = str(row.get('nadomestni_vodja_naziv') or '')
            result.append({
                'abbreviation': abbreviation,
                'leader': leader,
                'replacement': replacement,
                'replaced': bool(replacement),
            })
        return result

    def is_editor(self):
        return _editor(self.portal)

    def last_change(self):
        folder = self.days_folder()
        if folder is None:
            return ''
        brains = self.portal.portal_catalog(
            portal_type='imi.replacements.day', path='/'.join(folder.getPhysicalPath()),
            sort_on='modified', sort_order='descending')
        return brains[0].modified.asdatetime().strftime('%d.%m.%Y ob %H:%M') if brains else ''

    def formatted_date(self):
        return _formatted_date(self.selected_date())

    def previous_date(self):
        return (self.selected_date() - timedelta(days=1)).strftime('%Y-%m-%d')

    def next_date(self):
        return (self.selected_date() + timedelta(days=1)).strftime('%Y-%m-%d')

    def selected_person(self):
        return str(self.request.form.get('oseba') or '')

    def selected_person_title(self):
        return _staff_title(self.context, self.selected_person())

    def person_dates(self):
        person = self.selected_person()
        folder = self.days_folder()
        if not person or folder is None:
            return []
        result = []
        brains = self.portal.portal_catalog(
            portal_type='imi.replacements.day', path='/'.join(folder.getPhysicalPath()),
            sort_on='id', sort_order='ascending')
        for brain in brains:
            obj = brain.getObject()
            rows = self._rows_from_obj(obj)
            if not any(str(row.get('nadomestni_vodja_id') or '') == person for row in rows):
                continue
            try:
                parsed = _parse_date(obj.getId())
            except ValueError:
                continue
            result.append({'id': obj.getId(), 'date': parsed,
                           'label': parsed.strftime('%d.%m.%Y')})
        return result

    def person_dates_by_year(self):
        return _date_group(self.person_dates())


class ReplacementsPublicView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_public.pt')

    def __call__(self):
        return self.template()


class ReplacementsHomeView(ReplacementsPublicView):
    admin_template = ViewPageTemplateFile('replacements_admin.pt')

    def __call__(self):
        if self.is_editor():
            return self.admin_template()
        return self.template()


class ReplacementsSelectView(ReplacementsBase):
    def __call__(self):
        folder = self.days_folder()
        try:
            day_id = _parse_date(self.request.form.get('datum')).strftime('%Y-%m-%d')
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
            old_id = _parse_date(self.request.form.get('star')).strftime('%Y-%m-%d')
            new_id = _parse_date(self.request.form.get('nov')).strftime('%Y-%m-%d')
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
                'leader': _staff_title(self.context, leader_id),
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
                'nadomestni_vodja_naziv': _staff_title(self.context, replacement_id),
            })
        self.context.nadomescanja_json = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
        self.context.reindexObject()
        import transaction
        transaction.commit()
        api.portal.show_message(u'Nadomeščanja so shranjena.', request=self.request)


class ReplacementsExportView(ReplacementsBase):
    def __call__(self):
        from openpyxl import Workbook
        try:
            first, last = _period(self.request)
        except ValueError as exc:
            api.portal.show_message(str(exc), request=self.request, type='error')
            self.request.response.redirect(self.portal.absolute_url() + '/@@nadomescanja-public')
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
        brains = self.portal.portal_catalog(
            portal_type='imi.replacements.day', path='/'.join(folder.getPhysicalPath()), sort_on='id')
        for brain in brains:
            try:
                day = _parse_date(brain.id)
            except ValueError:
                continue
            if day < first or day > last:
                continue
            for row in self._rows_from_obj(brain.getObject()):
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
        filename = 'izpis_%s-%s.xlsx' % (first.strftime('%d_%m_%Y'), last.strftime('%d_%m_%Y'))
        self.request.response.setHeader(
            'Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
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
            return _parse_date(self.request.form.get('datum'), default_today=True).strftime('%Y-%m-%d')
        except ValueError:
            return date.today().strftime('%Y-%m-%d')
