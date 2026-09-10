# -*- coding: utf-8 -*-
"""Route-specific Preiskave views ported from the Plone 4 skin.

The old site had separate page templates for each public route. Keep the route
semantics here and expose template-safe values; do not make the page template
rediscover legacy data conventions.
"""
from collections import OrderedDict
from html import escape
from urllib.parse import quote
import unicodedata

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .exams_runtime import ExamsListView, ExamsLiveSearchView, ExamsPublicView, SLO_LETTERS


def _text(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw or '')
    output = getattr(value, 'output', None)
    if output is not None:
        return str(output or '')
    return str(value or '')


def _seq(value):
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return [str(item or '').strip() for item in value]
    value = str(value or '').strip()
    return [value] if value else []


def _split(value):
    values = []
    for item in _seq(value):
        for part in item.split('|'):
            part = part.strip()
            if part and part not in values:
                values.append(part)
    return values


def _norm(value):
    value = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii')
    return ''.join(ch for ch in value.casefold() if ch.isalnum())


# Route names are 5.2 implementation details. Labels are fallbacks only. The
# Plone 4 main_template built the menu from published folders sorted by their
# position in /preiskave-1. Include both legacy ids/titles and the known layout
# names so migrated folders can be matched without inventing their labels.
_MENU = (
    ('all', u'Preiskave', 'preiskave_view',
     ('preiskave', 'katalogpreiskav', 'preiskaveview', 'contentview')),
    ('quick', u'Hitro iskanje', 'preiskave_hitro_view',
     ('hitroiskanje', 'hitro', 'preiskavehitroview')),
    ('labs', u'Laboratoriji', 'preiskave_lab_view',
     ('laboratoriji', 'laboratorij', 'preiskavepolaboratorijih', 'preiskavelabview')),
    ('new', u'Nove', 'preiskave_nove_view',
     ('nove', 'novepreiskave', 'preiskavenoveview')),
    ('urgent', u'Nujne', 'preiskave_nujne_view',
     ('nujne', 'nujnepreiskave', 'preiskavenujneview')),
    ('areas', u'Področja', 'preiskave_podrocja_view',
     ('podrocja', 'podrocjapreiskav', 'preiskavepopodrocjih', 'preiskavepodrocjaview')),
    ('groups', u'Sklopi', 'preiskave_sklopi_view',
     ('sklopi', 'sklopipreiskav', 'preiskavesklopiview')),
    ('samples', u'Vzorci', 'preiskave_vzorci_view',
     ('vzorci', 'preiskavepovzorcih', 'preiskavevzorciview')),
    ('guardians', u'Skrbniki', 'preiskave_skrbniki_view',
     ('skrbniki', 'preiskaveskrbnikiview')),
)


class _LegacyMenuMixin(object):
    def _legacy_children(self):
        """Return migrated legacy Folder children in their object order."""
        base = self.base_folder()
        if base is None:
            return []
        try:
            children = list(base.values())
        except Exception:
            return []
        return [child for child in children
                if getattr(child, 'portal_type', '') in ('Folder', 'folder')]

    def _menu_match(self, child):
        try:
            cid = child.getId()
            title = child.Title() or cid
        except Exception:
            return None
        try:
            layout = child.getLayout() or ''
        except Exception:
            layout = getattr(child, 'layout', '') or ''
        candidates = {_norm(cid), _norm(title), _norm(layout)}
        for row in _MENU:
            key, fallback, route, aliases = row
            accepted = {_norm(route)}
            accepted.update(_norm(alias) for alias in aliases)
            if candidates.intersection(accepted):
                return row
        return None

    def menu(self):
        """Port the old dynamic folder menu, preserving labels and order.

        The legacy main_template queried the actual published folders sorted by
        getObjPositionInParent. Dexterity folder values preserve object order,
        so use those migrated objects first. Only unmatched/missing routes use
        fallback labels from _MENU.
        """
        base_url = self.portal.absolute_url()
        rows = []
        used = set()
        for child in self._legacy_children():
            match = self._menu_match(child)
            if match is None:
                continue
            key, fallback, route, aliases = match
            if key in used:
                continue
            try:
                label = child.Title() or fallback
            except Exception:
                label = fallback
            rows.append((key, label, base_url + '/@@' + route))
            used.add(key)

        for key, fallback, route, aliases in _MENU:
            if key not in used:
                rows.append((key, fallback, base_url + '/@@' + route))
        return rows


class ExamsHomeView(_LegacyMenuMixin, ExamsPublicView):
    pass


class _LegacyModeView(_LegacyMenuMixin, ExamsListView):
    legacy_mode = 'home'
    legacy_name = ''

    def mode(self):
        return self.legacy_name

    def mode_key(self):
        return self.legacy_mode

    def mode_url(self):
        return self.portal.absolute_url() + '/@@' + self.legacy_name

    def facet_current_label(self):
        return {
            'labs': u'Trenutno izbran laboratorij',
            'areas': u'Trenutno izbrano področje preiskav',
            'groups': u'Trenutno izbrani sklop',
        }.get(self.legacy_mode, u'')

    def exam_url(self, obj):
        url = super().exam_url(obj)
        selected = self.selected_facet()
        if selected and self.legacy_mode in ('labs', 'areas', 'groups'):
            url += '&podrocje=' + quote(selected)
        return url

    def alphabet_groups(self, exams=None):
        """Create Slovenian alphabetical sections without ZPT name clashes."""
        exams = self.all_exams() if exams is None else list(exams or [])
        buckets = OrderedDict()
        for obj in exams:
            try:
                title = str(obj.Title() or '').strip()
            except Exception:
                title = str(getattr(obj, 'title', '') or '').strip()
            if not title:
                continue
            letter = title[0].upper()
            buckets.setdefault(letter, []).append(obj)
        ordered = []
        used = set()
        for letter in SLO_LETTERS:
            if letter in buckets:
                ordered.append({'letter': letter, 'exams': buckets[letter]})
                used.add(letter)
        for letter in sorted([x for x in buckets if x not in used], key=lambda x: str(x).casefold()):
            ordered.append({'letter': letter, 'exams': buckets[letter]})
        return ordered

    def facet_values(self):
        values = []
        for obj in self.all_exams():
            if self.legacy_mode == 'labs':
                current = _split(getattr(obj, 'laboratoriji', ''))
            elif self.legacy_mode == 'areas':
                current = [x for x in _seq(getattr(obj, 'podrocje', ())) if x]
            elif self.legacy_mode == 'groups':
                current = _split(_text(getattr(obj, 'sklop', '')))
            else:
                current = []
            for value in current:
                if value not in values:
                    values.append(value)
        return sorted(values, key=lambda x: x.casefold())

    def facet_exams(self):
        selected = self.selected_facet()
        if not selected:
            return self.all_exams()
        result = []
        for obj in self.all_exams():
            if self.legacy_mode == 'labs':
                # Legacy template post-filter: podrocje in obj.laboratoriji.
                match = selected in _text(getattr(obj, 'laboratoriji', ''))
            elif self.legacy_mode == 'areas':
                match = selected in _seq(getattr(obj, 'podrocje', ()))
            elif self.legacy_mode == 'groups':
                # Legacy template post-filter: podrocje in obj.sklop.
                match = selected in _text(getattr(obj, 'sklop', ''))
            else:
                match = False
            if match:
                result.append(obj)
        return result


class ExamsAllView(_LegacyModeView):
    legacy_mode = 'all'
    legacy_name = 'preiskave_view'


class ExamsQuickView(_LegacyModeView):
    legacy_mode = 'quick'
    legacy_name = 'preiskave_hitro_view'


class ExamsLabsView(_LegacyModeView):
    legacy_mode = 'labs'
    legacy_name = 'preiskave_lab_view'


class ExamsNewView(_LegacyModeView):
    legacy_mode = 'new'
    legacy_name = 'preiskave_nove_view'

    def new_groups(self):
        result = []
        # This is intentionally not generalized: the legacy template rendered
        # these two sections explicitly and in this order.
        for year in ('2016', '2017'):
            exams = [obj for obj in self.all_exams()
                     if str(getattr(obj, 'nova_pre', '') or '').strip() == year]
            result.append({'year': year, 'sections': self.alphabet_groups(exams)})
        return result


class ExamsUrgentView(_LegacyModeView):
    legacy_mode = 'urgent'
    legacy_name = 'preiskave_nujne_view'


class ExamsAreasView(_LegacyModeView):
    legacy_mode = 'areas'
    legacy_name = 'preiskave_podrocja_view'


class ExamsGroupsView(_LegacyModeView):
    legacy_mode = 'groups'
    legacy_name = 'preiskave_sklopi_view'


class ExamsSamplesView(_LegacyModeView):
    legacy_mode = 'samples'
    legacy_name = 'preiskave_vzorci_view'

    def sample_records(self):
        """Rebuild the five-level legacy sample tree from migrated fields.

        Exported objects retain vzorci_nivo1..vzorci_nivo5 separately. Those
        aligned values take priority. Older/malformed objects fall back to the
        historical ``name######nivo1###...`` encoding used by the 4.3 view.
        """
        area = self.selected_area()
        rows = []
        for obj in self.all_exams():
            areas = [x for x in _seq(getattr(obj, 'podrocje', ())) if x]
            if area and area not in areas:
                continue

            samples = _seq(getattr(obj, 'vzorci', ()))
            level_columns = [_seq(getattr(obj, 'vzorci_nivo%d' % n, ())) for n in range(1, 6)]
            has_columns = any(any(column) for column in level_columns)

            for index, raw in enumerate(samples):
                if not raw:
                    continue
                name = raw.split('###', 1)[0].strip()
                if has_columns:
                    levels = [column[index].strip() if index < len(column) else ''
                              for column in level_columns]
                else:
                    parts = raw.split('###')
                    levels = [parts[i].strip() if i < len(parts) else '' for i in range(2, 7)]
                if name or any(levels):
                    rows.append({'exam': obj, 'name': name, 'levels': levels})
        return rows

    def _sample_expression(self, selected=None):
        selected = self.sample_selected() if selected is None else selected
        bits = [value for value in selected if value]
        area = self.selected_area()
        if area:
            bits.append(area)
        return ' AND '.join(bits)

    def sample_choice_url(self, choice):
        selected = self.sample_selected()
        depth = 0
        while depth < len(selected) and selected[depth]:
            depth += 1
        if depth >= 5:
            return self.mode_url()
        selected[depth] = choice
        params = []
        area = self.selected_area()
        if area:
            params.append(('podrocje', area))
        for index, value in enumerate(selected):
            if not value:
                break
            params.append(('nivo%d' % (index + 1), value))
        expression = self._sample_expression(selected)
        if expression:
            params.append(('iskanje_vzorec', expression))
        return self.mode_url() + '?' + '&'.join('%s=%s' % (key, quote(value)) for key, value in params)

    def sample_breadcrumbs(self):
        selected = self.sample_selected()
        area = self.selected_area()
        root_params = [('podrocje', area)] if area else []
        root_url = self.mode_url()
        if root_params:
            root_url += '?' + '&'.join('%s=%s' % (k, quote(v)) for k, v in root_params)
        rows = [{'label': u'vsi vzorci', 'url': root_url}]
        for index, value in enumerate(selected):
            if not value:
                break
            partial = selected[:index + 1] + [''] * (4 - index)
            params = list(root_params)
            for i in range(index + 1):
                params.append(('nivo%d' % (i + 1), selected[i]))
            expression = self._sample_expression(partial)
            if expression:
                params.append(('iskanje_vzorec', expression))
            rows.append({'label': value, 'url': self.mode_url() + '?' + '&'.join(
                '%s=%s' % (key, quote(val)) for key, val in params)})
        return rows


class ExamsGuardiansView(_LegacyModeView):
    legacy_mode = 'guardians'
    legacy_name = 'preiskave_skrbniki_view'
    template = ViewPageTemplateFile('preiskave_skrbniki.pt')

    def title(self):
        return u'Skrbniki'

    def guardians_html(self):
        base = self.base_folder()
        if base is None:
            return u''
        folder = base.get('skrbniki')
        document = folder is not None and folder.get('skrbniki-1') or None
        if document is None:
            return u''
        return _text(getattr(document, 'text', ''))


class LegacyExamsLiveSearchView(_LegacyMenuMixin, ExamsLiveSearchView):
    """HTML shape and 20-result limit from legacy livesearch_reply.py."""
    limit = 20

    def __call__(self):
        query = str(self.request.form.get('q') or self.request.form.get('moj') or '').strip()
        results = self.filtered_exams(query) if len(query) > 1 else []
        self.request.response.setHeader('Content-Type', 'text/html; charset=utf-8')
        if not results:
            return ('<fieldset class="livesearchContainer">'
                    '<legend id="livesearchLegend">Live search</legend>'
                    '<div class="LSIEFix"><div id="LSNothingFound">No match found</div>'
                    '<div class="LSRow"></div></div></fieldset>')
        out = [
            '<fieldset class="livesearchContainer">',
            '<legend id="livesearchLegend">Live search results: %d</legend>' % len(results),
            '<div class="LSIEFix"><ul class="LSTable">',
        ]
        for obj in results[:self.limit]:
            title = str(obj.Title() or '')
            description = str(obj.Description() or '')
            if len(description) > 93:
                description = description[:93] + '...'
            out.append(
                '<li class="LSRow"><a href="%s" title="%s">%s</a>'
                '<div class="LSDescr">%s</div></li>' % (
                    escape(self.exam_url(obj)), escape(title), escape(title), escape(description)))
        out.append('<li class="LSRow"><br /></li>')
        if len(results) > self.limit:
            out.append(
                '<li class="LSRow"><span>prikazanih %d od %d zadetkov</span> '
                '<a href="%s/@@preiskave_hitro_view?moj=%s" style="font-weight:normal">'
                'prikaži vse zadetke</a></li>' % (
                    self.limit, len(results), self.portal.absolute_url(), quote(query)))
        out.append('</ul></div></fieldset>')
        return ''.join(out)


__all__ = (
    'ExamsHomeView', 'ExamsAllView', 'ExamsQuickView', 'ExamsLabsView',
    'ExamsNewView', 'ExamsUrgentView', 'ExamsAreasView', 'ExamsGroupsView',
    'ExamsSamplesView', 'ExamsGuardiansView', 'LegacyExamsLiveSearchView',
)
