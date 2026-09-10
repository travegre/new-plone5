# -*- coding: utf-8 -*-
"""Template ownership for the production-fidelity Preiskave frontend."""
from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from ..legacy.exams_production_fidelity import ExamsAllView as BaseExamsAllView, ExamsAreasView as BaseExamsAreasView, ExamsGroupsView as BaseExamsGroupsView, ExamsGuardiansView as BaseExamsGuardiansView, ExamsHomeView as BaseExamsHomeView, ExamsLabsView as BaseExamsLabsView, ExamsNewView as BaseExamsNewView, ExamsQuickView as BaseExamsQuickView, ExamsSamplesView as BaseExamsSamplesView, ExamsUrgentView as BaseExamsUrgentView, ExaminationPublicView as BaseExaminationPublicView
from ..legacy.imports import ExamsImportView as BaseExamsImportView
from ..legacy.legacy_admin import ExamsAdminView as BaseExamsAdminView
from ..legacy.runtime_fixes import _walk

class _ListingTemplateMixin(object):
    template = ViewPageTemplateFile('preiskave_legacy.pt')
class ExamsHomeView(_ListingTemplateMixin, BaseExamsHomeView): pass
class ExamsAllView(_ListingTemplateMixin, BaseExamsAllView): pass
class ExamsQuickView(_ListingTemplateMixin, BaseExamsQuickView): pass
class ExamsLabsView(_ListingTemplateMixin, BaseExamsLabsView): pass
class ExamsNewView(_ListingTemplateMixin, BaseExamsNewView): pass
class ExamsUrgentView(_ListingTemplateMixin, BaseExamsUrgentView): pass
class ExamsAreasView(_ListingTemplateMixin, BaseExamsAreasView): pass
class ExamsGroupsView(_ListingTemplateMixin, BaseExamsGroupsView): pass
class ExamsSamplesView(_ListingTemplateMixin, BaseExamsSamplesView): pass
class ExamsGuardiansView(BaseExamsGuardiansView):
    template = ViewPageTemplateFile('preiskave_skrbniki.pt')
class ExaminationPublicView(BaseExaminationPublicView):
    template = ViewPageTemplateFile('preiskave_detail_legacy.pt')
class ExaminationPublicProxyView(BrowserView):
    def __call__(self):
        exam_id = str(self.request.form.get('id') or '').strip()
        portal = api.portal.get(); base = portal.get('preiskave-1'); obj = None
        if exam_id and base is not None:
            for candidate in _walk(base):
                if candidate.getId() == exam_id and getattr(candidate,'portal_type',None) == 'imi.exams.examination': obj = candidate; break
        if obj is None:
            self.request.response.setStatus(404); return u'Preiskava ne obstaja.'
        return ExaminationPublicView(obj, self.request)()
class ExamsAdminView(BaseExamsAdminView):
    template = ViewPageTemplateFile('exams_admin.pt')
class ExamsImportView(BaseExamsImportView):
    template = ViewPageTemplateFile('exams_import.pt')
