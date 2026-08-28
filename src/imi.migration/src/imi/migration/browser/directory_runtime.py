# -*- coding: utf-8 -*-
"""IMENIK livesearch output matching the old prettyPhoto contact payload."""
from html import escape

from plone import api

from .runtime_fixes import DirectorySearchView as CachedDirectorySearchView


class DirectorySearchView(CachedDirectorySearchView):
    """Keep cached search, but emit the complete legacy contact detail block."""

    def __call__(self):
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

            details = []
            for label, field, mobile_style in (
                (u'Telefon', 'telefon', False), (u'Dodatna', 'dodatna', False),
                (u'DECT', 'dect', False), (u'Fax', 'fax', False),
                (u'Mobitel', 'mobilna', True), (u'Multitone', 'multitone', False),
                (u'Zunanja', 'zunanja', True),
            ):
                raw = str(getattr(obj, field, '') or '').strip()
                if raw:
                    details.append(u'<br />%s: %s' % (escape(label), escape(self._phone(raw, mobile=mobile_style))))
            for label, field in ((u'E-naslov', 'enaslov'), (u'Zunanji e-naslov', 'zenaslov')):
                value = str(getattr(obj, field, '') or '').strip()
                if value:
                    details.append(u'<br />%s: <a href="mailto:%s">%s</a>' %
                                   (escape(label), escape(value), escape(value)))

            out.append(u'<tr class="person-detail" style="display:none"><td colspan="9">'
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
