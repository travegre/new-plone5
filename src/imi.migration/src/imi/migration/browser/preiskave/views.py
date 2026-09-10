# -*- coding: utf-8 -*-
"""Production-fidelity Preiskave browser views."""
from urllib.parse import quote

from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .exams_production_fidelity import ExamsAllView as BaseExamsAllView
from .exams_production_fidelity import ExamsAreasView as BaseExamsAreasView
from .exams_production_fidelity import ExamsGroupsView as BaseExamsGroupsView
from .exams_production_fidelity import ExamsGuardiansView as BaseExamsGuardiansView
from .exams_production_fidelity import ExamsHomeView as BaseExamsHomeView
from .exams_production_fidelity import ExamsLabsView as BaseExamsLabsView
from .exams_production_fidelity import LegacyExamsLiveSearchView as BaseLegacyExamsLiveSearchView
from .exams_production_fidelity import ExamsNewView as BaseExamsNewView
from .exams_production_fidelity import ExamsQuickView as BaseExamsQuickView
from .exams_production_fidelity import ExamsSamplesView as BaseExamsSamplesView
from .exams_production_fidelity import ExamsUrgentView as BaseExamsUrgentView
from .exams_production_fidelity import ExaminationPublicView as BaseExaminationPublicView
from .imports import ExamsImportView
from .runtime_fixes import _walk


class _CanonicalURLMixin(object):
    """Keep public navigation on the real migrated content tree."""

    def exam_url(self, obj):
        url = obj.absolute_url()
        selected = getattr(self, 'selected_facet', lambda: '')()
        mode = getattr(self, 'legacy_mode', '')
        if selected and mode in ('labs', 'areas', 'groups'):
            url += '?podrocje=' + quote(selected)
        return url

    def mode_url(self):
        return self.context.absolute_url()

    def quick_url(self):
        for key, _label, href in self.menu():
            if key == 'quick':
                return href
        return self.portal.absolute_url()


class _ListingTemplateMixin(object):
    template = ViewPageTemplateFile('preiskave_legacy.pt')


class ExamsHomeView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsHomeView):
    pass


class ExamsAllView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsAllView):
    pass


class ExamsQuickView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsQuickView):
    pass


class ExamsLabsView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsLabsView):
    pass


class ExamsNewView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsNewView):
    pass


class ExamsUrgentView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsUrgentView):
    pass


class ExamsAreasView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsAreasView):
    pass


class ExamsGroupsView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsGroupsView):
    pass


class ExamsSamplesView(_CanonicalURLMixin, _ListingTemplateMixin, BaseExamsSamplesView):
    pass


class ExamsGuardiansView(_CanonicalURLMixin, BaseExamsGuardiansView):
    template = ViewPageTemplateFile('preiskave_skrbniki.pt')


class LegacyExamsLiveSearchView(_CanonicalURLMixin, BaseLegacyExamsLiveSearchView):
    """Legacy livesearch markup with canonical result and menu URLs."""

    def exam_url(self, obj):
        # The inherited renderer appends ``&searchterm=...`` because the old
        # proxy URL already had an ``id`` query parameter. Give it a temporary
        # query separator and normalize the generated link afterwards.
        return obj.absolute_url() + '?'

    def __call__(self):
        html = super().__call__()
        html = html.replace('?&searchterm=', '?searchterm=')
        old_quick = self.portal.absolute_url() + '/@@preiskave_hitro_view'
        html = html.replace(old_quick, self.quick_url())
        return html


class ExaminationPublicView(_CanonicalURLMixin, BaseExaminationPublicView):
    template = ViewPageTemplateFile('preiskave_detail_legacy.pt')


def _proxy_exam(request):
    exam_id = str(request.form.get('id') or '').strip()
    portal = api.portal.get()
    base = portal.get('preiskave-1')
    if exam_id and base is not None:
        for candidate in _walk(base):
            if (candidate.getId() == exam_id and
                    getattr(candidate, 'portal_type', None) == 'imi.exams.examination'):
                return candidate
    return None


class ExaminationPublicProxyView(BrowserView):
    """Backward-compatible redirect from the former proxy URL."""

    def __call__(self):
        obj = _proxy_exam(self.request)
        if obj is None:
            self.request.response.setStatus(404)
            return u'Preiskava ne obstaja.'
        self.request.response.redirect(obj.absolute_url())
        return ''


class ExaminationAdminProxyView(BrowserView):
    """Backward-compatible redirect from the former proxy URL in admin mode."""

    def __call__(self):
        obj = _proxy_exam(self.request)
        if obj is None:
            self.request.response.setStatus(404)
            return u'Preiskava ne obstaja.'
        self.request.response.redirect(obj.absolute_url())
        return ''


class ExamsAdminView(BaseExamsHomeView):
    template = ViewPageTemplateFile('exams_admin.pt')

    def __call__(self):
        return self.template()
