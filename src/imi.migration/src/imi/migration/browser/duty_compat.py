# -*- coding: utf-8 -*-
"""Compatibility helpers for the Dežurstva public frontend.

Keep the visual/template port separate from identifier compatibility.  The
legacy roster stores employee identifiers from Plone 4, while migrated staff
objects also carry that identifier explicitly as ``source_employee_id``.
"""
from plone import api

from .duty import DutyExportView as BaseDutyExportView
from .duty import DutyHomeView as BaseDutyHomeView
from .duty import DutyPublicView as BaseDutyPublicView


class DutyPublicView(BaseDutyPublicView):

    def _employee_legacy_id(self, employee):
        return str(getattr(employee, 'source_employee_id', '') or employee.getId())

    def _employee_by_identifier(self, identifier):
        identifier = str(identifier or '')
        directory = self._staff_directory()
        if directory is None:
            return None
        employee = directory.get(identifier)
        if employee is not None:
            return employee
        for candidate in directory.objectValues():
            if getattr(candidate, 'portal_type', None) != 'imi.staff.employee':
                continue
            if self._employee_legacy_id(candidate) == identifier:
                return candidate
        return None

    def staff_title(self, employee_id):
        employee = self._employee_by_identifier(employee_id)
        if employee is not None:
            try:
                return employee.Title() or str(employee_id)
            except Exception:
                pass
        return str(employee_id or '')

    def staff_options(self):
        directory = self._staff_directory()
        if directory is None:
            return []
        result = []
        for employee in directory.objectValues():
            if getattr(employee, 'portal_type', None) != 'imi.staff.employee':
                continue
            if bool(getattr(employee, 'exclude_from_nav', False)):
                continue
            employee_id = self._employee_legacy_id(employee)
            result.append((employee_id, employee.Title() or employee_id))
        return sorted(result, key=lambda item: item[1].lower())

    def easyform_url(self):
        form = self.portal.get('spremeni-dezurstvo')
        if form is None:
            return ''
        # EasyForm 3.2.1 explicitly aliases its public form view to @@view.
        # Use it directly so the request cannot resolve through a site layout.
        return form.absolute_url() + '/@@view'


class DutyHomeView(BaseDutyHomeView):
    """Editor dashboard for editors; legacy public frontend for everyone else."""

    def __call__(self):
        portal = api.portal.get()
        if api.user.has_permission('Modify portal content', obj=portal):
            return self.admin_template()
        return DutyPublicView(self.context, self.request)()


class DutyExportView(BaseDutyExportView):
    """Export view; selector values now use the legacy employee identifiers."""

    pass
