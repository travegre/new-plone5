# -*- coding: utf-8 -*-
"""Template and static-resource ownership for Nadomeščanja."""
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from ..legacy_admin import ReplacementsAdminView as BaseReplacementsAdminView
from ..legacy_sites import ReplacementEditView as BaseReplacementEditView
from ..legacy_sites import ReplacementsChangeRequestView as BaseReplacementsChangeRequestView
from ..runtime_fixes import ReplacementsPublicView as BaseReplacementsPublicView


class ReplacementsPublicView(BaseReplacementsPublicView):
    template = ViewPageTemplateFile('replacements_public.pt')


class ReplacementsAdminView(BaseReplacementsAdminView):
    template = ViewPageTemplateFile('replacements_admin.pt')


class ReplacementEditView(BaseReplacementEditView):
    template = ViewPageTemplateFile('replacements_edit.pt')


class ReplacementsChangeRequestView(BaseReplacementsChangeRequestView):
    def __call__(self):
        rendered = super(ReplacementsChangeRequestView, self).__call__()
        if not isinstance(rendered, str):
            return rendered
        return (rendered
                .replace('/++resource++imi.migration/legacy-sites.css',
                         '/++resource++imi.migration/nadomescanja/public.css')
                .replace('/++resource++imi.migration/legacy-sites.js',
                         '/++resource++imi.migration/nadomescanja/public.js'))
