#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore the final Dežurstva root navigation and remove obsolete helpers.

The old PFG vocabulary helper is no longer needed because the migrated
EasyForm uses the named ``imi.form.staff_email`` vocabulary directly.
"""

from plone import api
from plone.app.dexterity.behaviors.exclfromnav import IExcludeFromNavigation

NAV_IDS = (
    'seznam_zaposlenih',
    'dezurstva-1',
    'spremeni-dezurstvo',
)

OBSOLETE_IDS = (
    'objekt-za-seznam-zaposlenih-v-formi-spremeni-dezurstvo-ne-brisi',
)


def _make_navigation_visible(obj):
    behavior = IExcludeFromNavigation(obj, None)
    if behavior is not None:
        behavior.exclude_from_nav = False
    elif hasattr(obj, 'exclude_from_nav'):
        obj.exclude_from_nav = False
    elif hasattr(obj, 'setExcludeFromNav'):
        obj.setExcludeFromNav(False)


def _publish_if_possible(obj):
    try:
        state = api.content.get_state(obj=obj)
    except Exception:
        state = None
    if state == 'published':
        return state
    try:
        transitions = api.content.get_transitions(obj=obj)
        ids = [item.get('id') for item in transitions]
        if 'publish' in ids:
            api.content.transition(obj=obj, transition='publish')
    except Exception:
        pass
    try:
        return api.content.get_state(obj=obj)
    except Exception:
        return state


def run(app):
    import transaction
    from zope.component.hooks import setSite

    if 'dezurstva' not in app.objectIds():
        raise SystemExit('Missing /dezurstva site')

    site = app['dezurstva']
    setSite(site)
    try:
        for obj_id in OBSOLETE_IDS:
            if obj_id in site.objectIds():
                api.content.delete(obj=site[obj_id], check_linkintegrity=False)
                print('Deleted obsolete helper: /dezurstva/%s' % obj_id)

        missing = [obj_id for obj_id in NAV_IDS if obj_id not in site.objectIds()]
        if missing:
            raise SystemExit('Missing required Dežurstva objects: %s' % ', '.join(missing))

        mover = getattr(site, 'moveObjectToPosition', None)
        for position, obj_id in enumerate(NAV_IDS):
            obj = site[obj_id]
            _make_navigation_visible(obj)
            state = _publish_if_possible(obj)
            try:
                obj.reindexObject()
            except Exception:
                pass
            if callable(mover):
                mover(obj_id, position)
            print('%d. /dezurstva/%s type=%s state=%s exclude_from_nav=%r' % (
                position + 1,
                obj_id,
                getattr(obj, 'portal_type', None),
                state,
                getattr(IExcludeFromNavigation(obj, None), 'exclude_from_nav',
                        getattr(obj, 'exclude_from_nav', None)),
            ))

        try:
            site.reindexObject()
        except Exception:
            pass
        transaction.commit()
        print('Dežurstva root navigation restored.')
    finally:
        setSite(None)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
