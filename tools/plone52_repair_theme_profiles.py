#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install missing Plone 5 theming profiles on existing target sites."""

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
PROFILES = (
    'profile-plone.app.theming:default',
    'profile-plonetheme.barceloneta:default',
    'profile-imi.migration:default',
)


def run(app):
    import transaction

    updated = 0
    for site_id in SITES:
        if site_id not in app.objectIds():
            print('missing: /%s' % site_id)
            continue
        site = app[site_id]
        setup = site.portal_setup
        for profile in PROFILES:
            setup.runAllImportStepsFromProfile(profile)
            print('/%s: applied %s' % (site_id, profile))
        updated += 1
    transaction.commit()
    print('Sites repaired: %d' % updated)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
