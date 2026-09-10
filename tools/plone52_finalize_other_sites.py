#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize public and administrative views for all migrated sites.

Each migrated Plone site keeps its public frontend for ordinary visitors.  A
physical ``admin`` folder provides the clean ``/admin`` URL.  Sites with an
import workflow also receive a physical ``uvoz`` folder at the site root; that
folder is visible to editors in normal Plone navigation and renders the import
view directly.
"""

import transaction
from plone import api
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-home'),
    ('dezurstva', '@@dezurstva-home'),
    ('kiestra', '@@kiestra-home'),
    ('preiskave', '@@preiskave-home'),
    ('nadomescanja', '@@nadomescanja-home'),
)

ADMIN_LAYOUTS = {
    'portal': '@@imenik-admin',
    'dezurstva': '@@dezurstva-admin',
    'kiestra': '@@kiestra-admin',
    'preiskave': '@@preiskave-admin',
    'nadomescanja': '@@nadomescanja-admin',
}

IMPORT_LAYOUTS = {
    'portal': ('@@imenik-uvoz', u'Uvoz podatkov'),
    'dezurstva': ('@@dezurstva-uvoz-zaposlenih', u'Uvoz zaposlenih'),
    'preiskave': ('@@preiskave-uvoz', u'Uvoz preiskav'),
}

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


def ensure_folder(site, folder_id, title, layout, failures):
    folder = site.get(folder_id)
    if folder is None:
        try:
            folder = api.content.create(
                container=site,
                type='Folder',
                id=folder_id,
                title=title,
                safe_id=False,
            )
        except Exception as exc:
            failures.append('/%s/%s could not be created: %s' %
                            (site.getId(), folder_id, exc))
            return None
    elif getattr(folder, 'portal_type', None) != 'Folder':
        failures.append('/%s/%s exists but is %r, expected Folder' %
                        (site.getId(), folder_id,
                         getattr(folder, 'portal_type', None)))
        return None

    try:
        folder.setTitle(title)
    except Exception:
        pass
    try:
        folder.exclude_from_nav = False
    except Exception:
        pass
    set_layout(folder, layout, failures,
               '/%s/%s' % (site.getId(), folder_id))
    try:
        folder.reindexObject()
    except Exception:
        pass
    return folder


def configure_admin_navigation(site, site_id, failures):
    admin_layout = ADMIN_LAYOUTS.get(site_id)
    if admin_layout:
        admin = ensure_folder(site, 'admin', u'Administracija',
                              admin_layout, failures)
        if admin is not None:
            print('  /admin layout -> %s' % admin_layout)

    import_config = IMPORT_LAYOUTS.get(site_id)
    if import_config:
        layout, title = import_config
        uvoz = ensure_folder(site, 'uvoz', title, layout, failures)
        if uvoz is not None:
            print('  /uvoz layout -> %s (title=%r)' % (layout, title))


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

            configure_admin_navigation(site, site_id, failures)

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
    print('All migrated site roots, admin folders and import folders finalized.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
