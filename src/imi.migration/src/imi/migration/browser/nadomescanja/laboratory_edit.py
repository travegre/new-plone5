# -*- coding: utf-8 -*-
"""Standard Dexterity laboratory editor with sorted Select2 staff results."""
from plone.dexterity.browser.edit import DefaultEditView


class ReplacementLaboratoryEditView(DefaultEditView):
    """Keep Plone's standard form, only correct its employee dropdown order."""

    def __call__(self):
        html = super(ReplacementLaboratoryEditView, self).__call__()
        if not isinstance(html, str) or '</body>' not in html:
            return html
        script = (
            '<script src="++resource++imi.migration/'
            'nadomescanja/laboratory_staff_sort.js?v=20261011-1"></script>'
        )
        return html.replace('</body>', script + '</body>', 1)
