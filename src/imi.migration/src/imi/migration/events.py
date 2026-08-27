# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from plone import api


ROSTER_TYPE = 'imi.duty.roster_day'
READY_FIELDS = (
    'BOR', 'HIV', 'HUM', 'PRZ', 'IT', 'KLM', 'KOV',
    'VINVZV', 'VINDIF', 'WHO', 'kiestra',
)


def _publish_if_possible(obj):
    try:
        transitions = api.content.get_transitions(obj=obj)
        ids = [item.get('id') for item in transitions]
        if 'publish' in ids:
            api.content.transition(obj=obj, transition='publish')
    except Exception:
        pass


def copy_readiness_to_week(obj, event):
    """Reproduce legacy ``ustvari_cel_teden`` on save/create.

    When ``klukca`` is checked, copy only the readiness fields to Monday-Sunday
    of the week containing this roster date. Missing days are created; existing
    days are updated. The checkbox is then reset so later saves do not repeat it.
    """
    if getattr(obj, 'portal_type', None) != ROSTER_TYPE:
        return
    if not getattr(obj, 'klukca', False):
        return

    try:
        current = datetime.strptime(obj.getId(), '%Y-%m-%d')
    except Exception:
        # Legacy code used the date-shaped title/id. If this is not a date, do
        # not make speculative week objects; just leave the value unchanged.
        return

    parent = obj.__parent__
    monday = current - timedelta(days=current.weekday())
    values = {name: getattr(obj, name, ()) for name in READY_FIELDS}

    for offset in range(7):
        day_id = (monday + timedelta(days=offset)).strftime('%Y-%m-%d')
        day = parent.get(day_id)
        if day is None:
            day = api.content.create(
                container=parent,
                type=ROSTER_TYPE,
                id=day_id,
                title=day_id,
                **values
            )
        else:
            for name, value in values.items():
                setattr(day, name, value)
            try:
                day.reindexObject()
            except Exception:
                pass
        _publish_if_possible(day)

    obj.klukca = False
    try:
        obj.reindexObject()
    except Exception:
        pass
