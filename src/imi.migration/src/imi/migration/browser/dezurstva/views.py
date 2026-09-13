# -*- coding: utf-8 -*-
"""Dežurstva browser views."""
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .duty_compat import DutyChangeRequestView as BaseDutyChangeRequestView
from .public_fixes import DutyPublicView as BaseDutyPublicView
from .staff_import import StaffImportView as BaseStaffImportView


class DutyPublicView(BaseDutyPublicView):
    template = ViewPageTemplateFile('duty_public.pt')


class StaffImportView(BaseStaffImportView):
    template = ViewPageTemplateFile('staff_import.pt')


class DutyChangeRequestView(BaseDutyChangeRequestView):
    def __call__(self):
        rendered = super(DutyChangeRequestView, self).__call__()
        if not isinstance(rendered, str):
            return rendered
        return rendered.replace(
            '/++resource++imi.migration/duty-public.css',
            '/++resource++imi.migration/dezurstva/duty-public.css')
