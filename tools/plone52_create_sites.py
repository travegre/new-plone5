#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the five clean Plone 5.2 target sites and install migration profile.

Run inside the target container with::

    bin/instance run tools/plone52_create_sites.py
"""
from Products.CMFPlone.factory import addPloneSite

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
    setup = site.portal_setup
    setup.runAllImportStepsFromProfile(PROFILE)
    return site


def run(app):
    for site_id, title in SITES:
        site = ensure_site(app, site_id, title)
        print('ready: /%s (%s)' % (site_id, site.Title()))
    import transaction
    transaction.commit()


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
