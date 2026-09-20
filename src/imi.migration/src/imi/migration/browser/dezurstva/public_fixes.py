# -*- coding: utf-8 -*-
"""Dežurstva public frontend fixes that avoid unreliable catalog state."""
from datetime import datetime

from .duty_compat import DutyPublicView as BaseDutyPublicView


def _walk(container):
    """Yield descendants without depending on catalog state."""
    try:
        children = container.objectValues()
    except (AttributeError, TypeError):
        return
    for child in children:
        yield child
        for descendant in _walk(child):
            yield descendant


class DutyPublicView(BaseDutyPublicView):
    """Resolve person history directly from the migrated roster container."""

    def person_dates(self):
        person = self.selected_person()
        if not person:
            return []
        rows = []
        for obj in _walk(self.roster_folder):
            if getattr(obj, 'portal_type', None) != 'imi.duty.roster_day':
                continue
            if not self._person_matches_roster(obj, person):
                continue
            try:
                parsed = datetime.strptime(obj.getId(), '%Y-%m-%d').date()
            except ValueError:
                continue
            rows.append({
                'id': obj.getId(), 'date': parsed, 'year': parsed.year,
                'month': parsed.month,
                'label': '%02d.%02d.%04d' % (parsed.day, parsed.month, parsed.year),
            })
        rows.sort(key=lambda row: row['date'])
        return rows
