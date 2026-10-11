#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize public layouts and hostname-aware admin presentation.

The public applications use standalone legacy-fidelity templates. Diazo is
configured with the package's ``imi-admin`` theme: normal hosts are explicitly
left unthemed, while 127.0.0.1 and admin.* hosts fall through to Barceloneta.
There is no physical ``admin`` folder. Import workflows remain physical
``uvoz`` folders at the site root.
"""

import transaction
from plone import api
from plone.app.theming.interfaces import IThemeSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.hooks import setSite


SITE_LAYOUTS = (
    ('portal', '@@imenik-home'),
    ('dezurstva', '@@dezurstva-home'),
    ('kiestra', '@@kiestra-home'),
    ('preiskave', '@@preiskave-home'),
    ('nadomescanja', '@@nadomescanja-home'),
)

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

# Stock Products.CMFPlone 5.2 ``Plone Default`` skin path. Legacy *.podoba
# admin layers contained old main_template.pt files and must not participate in
# Plone 5 backend template resolution.
PLONE5_DEFAULT_SKIN_LAYERS = (
    'custom',
    'plone_wysiwyg',
    'plone_prefs',
    'plone_templates',
    'plone_form_scripts',
    'plone_scripts',
    'plone_images',
)

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


def repair_plone_default_skin(site, failures):
    """Remove legacy *.podoba layers from main_template resolution."""
    skins = getattr(site, 'portal_skins', None)
    if skins is None:
        failures.append('/%s has no portal_skins' % site.getId())
        return False

    skin_path = ','.join(PLONE5_DEFAULT_SKIN_LAYERS)
    missing = [name for name in PLONE5_DEFAULT_SKIN_LAYERS
               if not hasattr(skins, name)]
    if missing:
        failures.append('/%s portal_skins missing Plone 5 layers: %s' %
                        (site.getId(), ', '.join(missing)))
        return False

    try:
        skins.addSkinSelection('Plone Default', skin_path, make_default=1)
    except Exception as exc:
        failures.append('/%s could not reset Plone Default skin path: %s' %
                        (site.getId(), exc))
        return False

    actual = skins.getSkinPath('Plone Default')
    print('  Plone Default skin path -> %s' % actual)
    return True


def activate_hostname_theme(site, failures):
    """Activate the IMI Diazo switcher and let its rules decide by hostname."""
    try:
        registry = getUtility(IRegistry)
        settings = registry.forInterface(IThemeSettings, False)
        settings.enabled = True
        settings.currentTheme = 'imi-admin'
        settings.rules = '/++theme++imi-admin/rules.xml'
        settings.absolutePrefix = '/++theme++barceloneta'
        # The standard theming UI commonly uses 127.0.0.1 as an unthemed
        # development hostname. That would bypass Diazo before our $host rule
        # is evaluated, so host switching belongs exclusively in rules.xml.
        settings.hostnameBlacklist = []
    except Exception as exc:
        failures.append('/%s could not activate IMI hostname theme: %s' %
                        (site.getId(), exc))
        return False

    print('  Diazo theme -> imi-admin (127.0.0.1/admin.* = Barceloneta)')
    print('  Diazo hostname blacklist -> empty')
    return True


def ensure_barceloneta(site, failures):
    """Repair Barceloneta resources, Plone skin path, and IMI Diazo state."""
    setup = getattr(site, 'portal_setup', None)
    if setup is None:
        failures.append('/%s has no portal_setup' % site.getId())
        return False
    try:
        # Ensure Barceloneta and plone.app.theming resources/profiles exist on
        # these already-migrated ZODB sites. The IMI theme is activated below.
        setup.runAllImportStepsFromProfile(
            'profile-plonetheme.barceloneta:default')
    except Exception as exc:
        failures.append('/%s could not prepare Barceloneta: %s' %
                        (site.getId(), exc))
        return False

    if not repair_plone_default_skin(site, failures):
        return False
    if not activate_hostname_theme(site, failures):
        return False

    print('  Barceloneta resources/profile -> ready')
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


def remove_obsolete_admin_folder(site):
    """Remove only the dummy admin folder created by the previous finalizer."""
    admin = site.get('admin')
    if admin is None:
        return
    if getattr(admin, 'portal_type', None) != 'Folder':
        print('  /admin exists but is not a Folder; left untouched')
        return
    layout = getattr(admin, 'getLayout', lambda: '')()
    if layout not in (
        '@@imenik-admin', '@@dezurstva-admin', '@@kiestra-admin',
        '@@preiskave-admin', '@@nadomescanja-admin',
    ):
        print('  /admin is not the generated dummy folder; left untouched')
        return
    api.content.delete(obj=admin)
    print('  removed obsolete generated /admin folder')


def configure_import_navigation(site, site_id, failures):
    import_config = IMPORT_LAYOUTS.get(site_id)
    if not import_config:
        return
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
            ensure_barceloneta(site, failures)

            set_default = getattr(site, 'setDefaultPage', None)
            if callable(set_default):
                set_default(None)
            if not set_layout(site, layout, failures, '/%s' % site_id):
                continue

            remove_obsolete_admin_folder(site)
            configure_import_navigation(site, site_id, failures)

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
    print('All migrated sites finalized with hostname-aware Barceloneta admin mode.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
