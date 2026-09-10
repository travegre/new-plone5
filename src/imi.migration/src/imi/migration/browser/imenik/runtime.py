# -*- coding: utf-8 -*-
"""IMENIK livesearch runtime matching the old contact payload."""
from html import escape

from plone import api
from Products.Five import BrowserView


SEARCHABLE_FIELDS = (
    'title', 'predime', 'ime', 'priimek', 'zaime', 'oddelek', 'telefon',
    'opis', 'enota', 'lokacija', 'dodatna', 'dect', 'fax', 'mobilna',
    'multitone', 'zunanja', 'enaslov', 'zenaslov',
)


def _legacy_query(value):
    value = str(value or '')
    for char in ('?', '-', '+', '*', u'\u3000'):
        value = value.replace(char, ' ')
    value = ' AND '.join(value.split())
    value = value.replace('(', '"("').replace(')', '")"')
    return value + '*' if value else ''


class DirectorySearchView(BrowserView):
    searchable_fields = SEARCHABLE_FIELDS

    @staticmethod
    def _phone(value, mobile=False):
        value = str(value or '').strip()
        if not value:
            return ''
        if mobile:
            return value if value.startswith('0') else '0' + value
        if len(value) < 7:
            return '(01)\u00a0522\u00a0' + value
        return value

    def _results(self, portal, query):
        transformed = _legacy_query(query)
        if not transformed:
            return []
        base = portal.get('data2')
        if base is None:
            return []
        brains = portal.portal_catalog.unrestrictedSearchResults(
            SearchableText=transformed,
            portal_type='imi.directory.person',
            path='/'.join(base.getPhysicalPath()),
        )
        objects = [brain.getObject() for brain in brains]
        objects.sort(key=lambda obj: (
            (getattr(obj, 'priimek', '') or u'ŽŽŽŽŽ').lower(),
            (getattr(obj, 'ime', '') or '').lower(),
        ))
        return objects

    def __call__(self):
        portal = api.portal.get()
        query = str(self.request.form.get('q') or self.request.form.get('searchGadget') or '').strip()
        objects = self._results(portal, query)
        total = len(objects)

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
            full_name = u' '.join(filter(None, [
                str(getattr(obj, 'predime', '') or ''),
                str(getattr(obj, 'ime', '') or ''),
                str(getattr(obj, 'priimek', '') or ''),
                str(getattr(obj, 'zaime', '') or ''),
            ]))

            out.append(
                u'<tr class="tri"><td class="enota">%s</td><td>%s</td><td>%s</td><td class="enota">%s</td>'
                u'<td class="enota">%s</td><td>%s</td><td class="enota">%s</td><td class="enota">%s</td><td class="enota">%s</td></tr>' % (
                    escape(str(getattr(obj, 'predime', '') or '')),
                    escape(str(getattr(obj, 'ime', '') or '')),
                    escape(str(getattr(obj, 'priimek', '') or '')),
                    escape(str(getattr(obj, 'zaime', '') or '')),
                    escape(str(getattr(obj, 'oddelek', '') or '')),
                    escape(phone), escape(dect), escape(mobile),
                    escape(str(getattr(obj, 'enota', '') or ''))))

            details = []
            for label, field, mobile_style in (
                (u'Telefon', 'telefon', False), (u'Dodatna', 'dodatna', False),
                (u'DECT', 'dect', False), (u'Fax', 'fax', False),
                (u'Mobitel', 'mobilna', True), (u'Multitone', 'multitone', False),
                (u'Zunanja', 'zunanja', True),
            ):
                raw = str(getattr(obj, field, '') or '').strip()
                if raw:
                    details.append(u'<br />%s: %s' % (
                        escape(label), escape(self._phone(raw, mobile=mobile_style))))
            for label, field in ((u'E-naslov', 'enaslov'), (u'Zunanji e-naslov', 'zenaslov')):
                value = str(getattr(obj, field, '') or '').strip()
                if value:
                    details.append(u'<br />%s: <a href="mailto:%s">%s</a>' % (
                        escape(label), escape(value), escape(value)))

            out.append(
                u'<tr class="person-detail" style="display:none"><td colspan="9">'
                u'<div class="ime">%s</div><div class="stevilka">%s</div><br />%s<br />%s<br />%s<br />%s%s'
                u'</td></tr>' % (
                    escape(full_name), escape(phone),
                    escape(str(getattr(obj, 'oddelek', '') or '')),
                    escape(str(getattr(obj, 'opis', '') or '')),
                    escape(str(getattr(obj, 'enota', '') or '')),
                    escape(str(getattr(obj, 'lokacija', '') or '')),
                    u''.join(details)))

        out.append(u'</tbody></table></div></fieldset>')
        return u''.join(out)
