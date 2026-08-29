#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize public application views for all migrated sites.

Site roots receive their public application view.  Preiskave additionally keeps
its legacy content-driven navigation: the visible menu is made from the actual
folders under /preiskave/preiskave-1, and those folders get the corresponding
ported browser view as their default layout.  Titles and ordering remain normal
Plone content and can be changed by editors.
"""

import transaction
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-public'),
    ('dezurstva', '@@dezurstva-public'),
    ('kiestra', '@@kiestra-public'),
    ('preiskave', '@@preiskave-public'),
    ('nadomescanja', '@@nadomescanja-public'),
)

REQUIRED_ROOT_OBJECTS = {
    'portal': ('data2',),
    'dezurstva': ('dezurstva-1', 'seznam_zaposlenih'),
    'preiskave': ('preiskave-1',),
    'nadomescanja': ('laboratoriji', 'sprememba-nadomescanja'),
}

# Folder ids are stable content identifiers from the migrated 4.3 tree.  The
# public label is *not* stored here: menu labels come from each folder.Title().
PREISKAVE_FOLDER_LAYOUTS = {
    'hitro-iskanje': '@@preiskave_hitro_view',
    'preiskave-po-podrocjih': '@@preiskave_podrocja_view',
    'preiskave-po-vzorcih': '@@preiskave_vzorci_view',
    'katalog-preiskav': '@@preiskave_view',
    'preiskave-po-laboratorijih': '@@preiskave_lab_view',
    'preiskave-po-sklopih': '@@preiskave_sklopi_view',
    'nujne-preiskave': '@@preiskave_nujne_view',
    'nove-preiskave': '@@preiskave_nove_view',
    'skrbniki': '@@preiskave_skrbniki_view',
}


def set_layout(obj, layout, failures, label):
    setter = getattr(obj, 'setLayout', None)
    if not callable(setter):
        failures.append('%s has no setLayout' % label)
        return False
    setter(layout)
    try:
        obj.reindexObject()
    except Exception:
        pass
    return True


def finalize_preiskave_folders(site, failures):
    base = site.get('preiskave-1')
    if base is None:
        return
    configured = 0
    for folder_id, layout in PREISKAVE_FOLDER_LAYOUTS.items():
        folder = base.get(folder_id)
        if folder is None:
            # The public menu is content-driven, so absence is not itself a
            # finalizer failure; it simply means no such menu entry is shown.
            continue
        if set_layout(folder, layout, failures,
                      '/preiskave/preiskave-1/%s' % folder_id):
            configured += 1
            print('  /preiskave-1/%s layout -> %s (title=%r)' %
                  (folder_id, layout, folder.Title()))
    print('  Preiskave public folders configured: %d' % configured)


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
            if not set_layout(site, layout, failures, '/%s' % site_id):
                continue

            missing = [obj_id for obj_id in REQUIRED_ROOT_OBJECTS.get(site_id, ())
                       if obj_id not in site.objectIds()]
            print('/%s layout -> %s' % (site_id, layout))
            print('  objects=%d required-missing=%s' %
                  (len(site.objectIds()), ','.join(missing) if missing else 'none'))
            if missing:
                failures.append('/%s missing required: %s' %
                                (site_id, ', '.join(missing)))

            if site_id == 'preiskave':
                finalize_preiskave_folders(site, failures)
        finally:
            setSite(None)

    if failures:
        transaction.abort()
        raise SystemExit('Finalizer aborted:\n  ' + '\n  '.join(failures))
    transaction.commit()
    print('All migrated site roots/public folder layouts finalized.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
