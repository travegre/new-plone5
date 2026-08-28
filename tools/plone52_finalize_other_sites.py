#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize clean root application views for the four non-Dežurstva sites.

Do not manufacture the old /nastavitve/dezurstva path here. In this multi-site
Zope application the top-level /dezurstva site makes that id acquisition-visible
and therefore reserved below other folders. The migration/import code is
responsible for preserving real business content; this finalizer only sets root
layouts and validates non-conflicting required roots.
"""

import transaction
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


def run(app):
    failures = []
    for site_id, layout in SITE_LAYOUTS:
        if site_id not in app.objectIds():
            failures.append('/%s missing' % site_id)
            continue
        site = app[site_id]
        setSite(site)
        try:
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
    print('Other-site root layouts finalized.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
