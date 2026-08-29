# -*- coding: utf-8 -*-
"""Route-specific Preiskave views matching the Plone 4 skin semantics.

The legacy site used a separate page template for every menu item.  Keeping a
single renderer in Plone 5 is fine, but the traversed browser-view name must not
be inferred from REQUEST['URL']: that value is not a reliable discriminator for
Five browser views.  These tiny classes make each legacy route explicit.
"""
from html import escape
from urllib.parse import quote

from .exams_runtime import ExamsListView, ExamsLiveSearchView


class _LegacyModeView(ExamsListView):
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
        # The old template contains two explicit sections, in this order.
        result = []
        for year in ('2016', '2017'):
            exams = [obj for obj in self.all_exams()
                     if str(getattr(obj, 'nova_pre', '') or '').strip() == year]
            result.append({'year': year, 'groups': self.alphabet_groups(exams)})
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


class LegacyExamsLiveSearchView(ExamsLiveSearchView):
    """Port the visible behaviour of the old Preiskave livesearch_reply.py."""

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
            title = obj.Title() or ''
            description = obj.Description() or ''
            if len(description) > 93:
                description = description[:93] + '...'
            out.append(
                '<li class="LSRow"><a href="%s" title="%s">%s</a>'
                '<div class="LSDescr">%s</div></li>' % (
                    escape(self.exam_url(obj)), escape(title), escape(title),
                    escape(description)))

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
    'ExamsAllView', 'ExamsQuickView', 'ExamsLabsView', 'ExamsNewView',
    'ExamsUrgentView', 'ExamsAreasView', 'ExamsGroupsView', 'ExamsSamplesView',
    'LegacyExamsLiveSearchView',
)
