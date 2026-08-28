#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize root application views for the four non-Dežurstva sites."""

import transaction
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-home'),
    ('kiestra', '@@kiestra-home'),
    ('preiskave', '@@preiskave-home'),
    ('nadomescanja', '@@nadomescanja-home'),
)

EXPECTED = {
    'portal': ('data2',),
    'kiestra': ('nastavitve',),
    'preiskave': ('preiskave-1',),
    'nadomescanja': ('nastavitve', 'laboratoriji', 'sprememba-nadomescanja'),
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
            missing = [obj_id for obj_id in EXPECTED.get(site_id, ())
                       if obj_id not in site.objectIds()]
            print('/%s layout -> %s' % (site_id, layout))
            print('  objects=%d expected-missing=%s' %
                  (len(site.objectIds()), ','.join(missing) if missing else 'none'))
            if missing:
                failures.append('/%s missing expected: %s' %
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
