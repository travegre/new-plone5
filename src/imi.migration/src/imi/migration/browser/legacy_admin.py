# -*- coding: utf-8 -*-
"""Explicit admin renderers so public __call__ methods cannot mask templates."""
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .legacy_sites import DirectoryPublicView
from .legacy_sites import ExamsBase
from .legacy_sites import KiestraPublicView
from .legacy_sites import ReplacementsBase


class DirectoryAdminView(DirectoryPublicView):
    template = ViewPageTemplateFile('directory_admin.pt')

    def __call__(self):
        return self.template()


class KiestraAdminView(KiestraPublicView):
    template = ViewPageTemplateFile('kiestra_admin.pt')

    def __call__(self):
        return self.template()


class ExamsAdminView(ExamsBase):
    template = ViewPageTemplateFile('exams_admin.pt')

    def __call__(self):
        return self.template()


class ReplacementsAdminView(ReplacementsBase):
    template = ViewPageTemplateFile('replacements_admin.pt')

    def __call__(self):
        return self.template()
