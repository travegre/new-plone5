# -*- coding: utf-8 -*-
"""Runtime compatibility fixes for migrated legacy public sites."""
from Acquisition import aq_parent
from html import escape
from Products.Five import BrowserView

from .exams_compat import ExaminationView
from .legacy_sites import DirectorySearchView as BaseDirectorySearchView
from .legacy_sites import ExamsLiveSearchView as BaseExamsLiveSearchView
from .legacy_sites import KiestraPublicView as BaseKiestraPublicView
from .legacy_sites import ReplacementsPublicView as BaseReplacementsPublicView
from .legacy_sites import _date_group
from .legacy_sites import _parse_date


def _content_site(portal):
    """Return the real migrated content site.

    Kiestra and Nadomescanja were imported below an accidental same-named
    nested Plone site (for example /kiestra/kiestra).  Public browser views are
    registered on the outer site, so data access must deliberately cross into
    that inner site instead of relying on acquisition or the outer catalog.
    """
    site_id = portal.getId()
    nested = portal.get(site_id)
    if nested is not None and getattr(nested, 'portal_type', None) == 'Plone Site':
        return nested
    return portal


def _brains(portal, portal_type, **kw):
    content_site = _content_site(portal)
    query = {
        'portal_type': portal_type,
        'path': '/'.join(content_site.getPhysicalPath()),
    }
    query.update(kw)
    return content_site.portal_catalog(**query)


def _walk(container):
    for obj in container.objectValues():
        yield obj
        if hasattr(obj, 'objectValues'):
            for child in _walk(obj):
                yield child


class DirectorySearchView(BaseDirectorySearchView):
    """IMENIK livesearch that does not depend on a stale/broken catalog."""

    def __call__(self):
        portal = self.context
        query = str(self.request.form.get('q') or self.request.form.get('searchGadget') or '').strip()
        words = [word.lower() for word in query.replace('*', ' ').replace('+', ' ').split() if word]
        base = portal.get('data2')
        objects = []
        if base is not None and words:
            for obj in _walk(base):
                if getattr(obj, 'portal_type', None) != 'imi.directory.person':
                    continue
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


class KiestraPublicView(BaseKiestraPublicView):
    """Kiestra frontend reading the actual nested migrated content site."""

    def day_object(self):
        brains = _brains(self.portal, 'imi.kiestra.work_day', id=self.selected_date_id())
        return brains[0].getObject() if brains else None

    def last_change(self):
        brains = _brains(self.portal, 'imi.kiestra.work_day', sort_on='modified', sort_order='descending')
        if not brains:
            return ''
        try:
            value = brains[0].modified.asdatetime()
            return value.strftime('%d.%m.%Y ob %H:%M')
        except Exception:
            return ''

    def person_dates(self):
        person = self.selected_person()
        if not person:
            return []
        result = []
        for brain in _brains(self.portal, 'imi.kiestra.work_day', sort_on='id', sort_order='ascending'):
            obj = brain.getObject()
            found = False
            for field, _note, _label in self.columns_definition():
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

    def columns_definition(self):
        from .legacy_sites import KIESTRA_FIELDS
        return KIESTRA_FIELDS

    def person_dates_by_year(self):
        return _date_group(self.person_dates())


class ReplacementsPublicView(BaseReplacementsPublicView):
    """Nadomeščanja frontend reading its actual nested migrated content site."""

    @property
    def content_site(self):
        return _content_site(self.portal)

    def days_folder(self):
        folder = self.content_site.get('nadomescanja-1')
        if folder is not None:
            return folder
        brains = _brains(self.portal, 'imi.replacements.day')
        if not brains:
            return None
        try:
            return aq_parent(brains[0].getObject())
        except Exception:
            return None

    def labs_folder(self):
        return self.content_site.get('laboratoriji')

    def day_object(self):
        folder = self.days_folder()
        if folder is not None:
            obj = folder.get(self.selected_date_id())
            if obj is not None:
                return obj
        brains = _brains(self.portal, 'imi.replacements.day', id=self.selected_date_id())
        return brains[0].getObject() if brains else None


class ExamsLiveSearchView(BaseExamsLiveSearchView):
    """Return livesearch links through the anonymous site-root proxy."""

    def __call__(self):
        query = str(self.request.form.get('q') or '').strip()
        results = self.filtered_exams(query)
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return '<fieldset class="livesearchContainer"><legend>Live search</legend><div id="LSNothingFound">No match found</div></fieldset>'
        limit = 20
        base = self.portal.absolute_url() + '/@@preiskava-public?id='
        out = ['<fieldset class="livesearchContainer"><legend>Live search results: %d</legend><ul class="LSTable">' % len(results)]
        for obj in results[:limit]:
            out.append('<li class="LSRow"><a href="%s%s">%s</a><div class="LSDescr">%s</div></li>' % (
                base, escape(obj.getId()), escape(obj.Title()), escape(obj.Description() or '')))
        if len(results) > limit:
            out.append('<li class="LSRow">prikazanih %d od %d zadetkov</li>' % (limit, len(results)))
        out.append('</ul></fieldset>')
        return ''.join(out)


class ExaminationPublicProxyView(BrowserView):
    """Render an examination through the public site root."""

    def _exam(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        if not exam_id:
            return None
        portal = self.context
        brains = portal.portal_catalog(id=exam_id, path='/'.join(portal.getPhysicalPath()))
        for brain in brains:
            try:
                obj = brain.getObject()
            except Exception:
                continue
            if getattr(obj, 'portal_type', None) == 'imi.exams.examination':
                return obj
        base = portal.get('preiskave-1')
        if base is not None:
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
