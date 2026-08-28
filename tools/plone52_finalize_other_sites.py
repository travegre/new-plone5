#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize root application views for the four non-Dežurstva sites.

The legacy Kiestra and Nadomeščanja applications stored their day objects under
/nastavitve/dezurstva.  Some migrated target databases do not contain those
folder objects even though the browser code expects the same operational path.
Create the folders when absent instead of aborting the whole layout update.
"""

import transaction
from plone import api
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-home'),
    ('kiestra', '@@kiestra-home'),
    ('preiskave', '@@preiskave-home'),
    ('nadomescanja', '@@nadomescanja-home'),
)

REQUIRED_ROOT_OBJECTS = {
    'portal': ('data2',),
    'preiskave': ('preiskave-1',),
    'nadomescanja': ('laboratoriji', 'sprememba-nadomescanja'),
}


def ensure_folder(container, obj_id, title):
    existing = container.get(obj_id)
    if existing is not None:
        return existing, False
    folder = api.content.create(
        container=container,
        type='Folder',
        id=obj_id,
        title=title,
        safe_id=False,
    )
    try:
        folder.exclude_from_nav = True
    except Exception:
        pass
    try:
        folder.reindexObject()
    except Exception:
        pass
    return folder, True


def ensure_schedule_container(site):
    """Ensure the old /nastavitve/dezurstva storage path exists."""
    nastavitve, created_parent = ensure_folder(site, 'nastavitve', 'Nastavitve')
    dezurstva, created_child = ensure_folder(nastavitve, 'dezurstva', 'Dežurstva')
    return dezurstva, created_parent, created_child


def run(app):
    failures = []
    for site_id, layout in SITE_LAYOUTS:
        if site_id not in app.objectIds():
            failures.append('/%s missing' % site_id)
            continue
        site = app[site_id]
        setSite(site)
        try:
            # These are operational storage folders in the legacy applications,
            # not optional public content.
            if site_id in ('kiestra', 'nadomescanja'):
                _, made_parent, made_child = ensure_schedule_container(site)
                if made_parent or made_child:
                    print('/%s created operational path /nastavitve/dezurstva' % site_id)

            set_default = getattr(site, 'setDefaultPage', None)
            if callable(set_default):
                set_default(None)
            set_layout = getattr(site, 'setLayout', None)
            if not callable(set_layout):
                failures.append('/%s has no setLayout' % site_id)
                continue
            set_layout(layout)
            try:
                site.reindexObject()
            except Exception:
                pass

            missing = [obj_id for obj_id in REQUIRED_ROOT_OBJECTS.get(site_id, ())
                       if obj_id not in site.objectIds()]
            print('/%s layout -> %s' % (site_id, layout))
            print('  objects=%d required-missing=%s' %
                  (len(site.objectIds()), ','.join(missing) if missing else 'none'))
            if missing:
                failures.append('/%s missing required: %s' %
                                (site_id, ', '.join(missing)))
        finally:
            setSite(None)

    if failures:
        transaction.abort()
        raise SystemExit('Finalizer aborted:\n  ' + '\n  '.join(failures))
    transaction.commit()
    print('Other-site root layouts and operational folders finalized.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
