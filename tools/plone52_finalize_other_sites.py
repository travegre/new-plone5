#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize public application views for all migrated sites.

Site roots receive their public application view. Preiskave additionally keeps
its legacy content-driven navigation: visible labels still come from the real
folders under /preiskave/preiskave-1, while their layouts and the original
folder order are restored once from the 4.3 public site.
"""

import transaction
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-public'),
    ('dezurstva', '@@dezurstva-public'),
    ('kiestra', '@@kiestra-public'),
    # The legacy Preiskave site opens directly on Hitro iskanje.
    ('preiskave', '@@preiskave_hitro_view'),
    ('nadomescanja', '@@nadomescanja-public'),
)

REQUIRED_ROOT_OBJECTS = {
    'portal': ('data2',),
    'dezurstva': ('dezurstva-1', 'seznam_zaposlenih'),
    'preiskave': ('preiskave-1',),
    'nadomescanja': ('laboratoriji', 'sprememba-nadomescanja'),
}

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

# Original public order visible in the Plone-4 site. Titles are intentionally
# not stored here; editors remain free to rename the folders and menu labels
# continue to come from folder.Title().
PREISKAVE_FOLDER_ORDER = (
    'hitro-iskanje',
    'preiskave-po-podrocjih',
    'preiskave-po-vzorcih',
    'katalog-preiskav',
    'preiskave-po-laboratorijih',
    'preiskave-po-sklopih',
    'nujne-preiskave',
    'nove-preiskave',
    'skrbniki',
)


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


def restore_preiskave_order(base):
    mover = getattr(base, 'moveObjectToPosition', None)
    if not callable(mover):
        return
    for position, folder_id in enumerate(PREISKAVE_FOLDER_ORDER):
        if folder_id in base.objectIds():
            try:
                mover(folder_id, position)
            except Exception:
                pass


def finalize_preiskave_folders(site, failures):
    base = site.get('preiskave-1')
    if base is None:
        return
    restore_preiskave_order(base)
    configured = 0
    for folder_id, layout in PREISKAVE_FOLDER_LAYOUTS.items():
        folder = base.get(folder_id)
        if folder is None:
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
