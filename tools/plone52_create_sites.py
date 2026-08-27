#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the five clean Plone 5.2 target sites and install migration profile.

Run inside the target container with::

    bin/instance run tools/plone52_create_sites.py
"""
from Products.CMFPlone.factory import addPloneSite
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.hooks import setSite

SITES = (
    ('portal', 'IMI imenik'),
    ('dezurstva', 'Dežurstva'),
    ('kiestra', 'Kiestra'),
    ('preiskave', 'Preiskave'),
    ('nadomescanja', 'Nadomeščanja'),
)
PROFILE = 'profile-imi.migration:default'
EXTENSION_IDS = (
    'plone.app.theming:default',
    'plonetheme.barceloneta:default',
)


def ensure_imi_types_in_navigation(site):
    """Add every current/future ``imi.*`` FTI to Plone navigation types."""
    registry = getUtility(IRegistry)
    key = 'plone.displayed_types'
    current = list(registry.get(key, ()) or ())
    for type_id in sorted(site.portal_types.objectIds()):
        if str(type_id).startswith('imi.') and type_id not in current:
            current.append(type_id)
    registry[key] = tuple(current)


def configure_site_root(site, site_id):
    if site_id != 'dezurstva':
        return
    set_default = getattr(site, 'setDefaultPage', None)
    if callable(set_default):
        set_default(None)
    set_layout = getattr(site, 'setLayout', None)
    if callable(set_layout):
        set_layout('@@dezurstva-home')


def ensure_site(app, site_id, title):
    if site_id not in app.objectIds():
        addPloneSite(
            app,
            site_id,
            title=title,
            default_language='sl',
            setup_content=False,
            extension_ids=EXTENSION_IDS,
        )
    site = app[site_id]
    setSite(site)
    setup = site.portal_setup
    setup.runAllImportStepsFromProfile(PROFILE)
    ensure_imi_types_in_navigation(site)
    configure_site_root(site, site_id)
    return site


def run(app):
    import transaction
    try:
        for site_id, title in SITES:
            site = ensure_site(app, site_id, title)
            print('ready: /%s (%s)' % (site_id, site.Title()))
        transaction.commit()
    finally:
        setSite(None)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
