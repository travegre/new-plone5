#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the five clean Plone 5.2 target sites and install imi.migration.

Run inside the target container before importing data::

    bin/instance run tools/plone52_prepare.py
"""
from __future__ import print_function

import transaction
from Products.CMFPlone.factory import addPloneSite

SITES = (
    ('portal', 'IMI imenik'),
    ('dezurstva', 'Dežurstva'),
    ('kiestra', 'Kiestra'),
    ('preiskave', 'Preiskave'),
    ('nadomescanja', 'Nadomeščanja'),
)
PROFILE = 'profile-imi.migration:default'


def ensure_site(app, site_id, title):
    if site_id not in app.objectIds():
        print('Creating /%s' % site_id)
        addPloneSite(app, site_id, title=title, extension_ids=())
        transaction.commit()
    site = app[site_id]

    # Running the extension profile is idempotent for the FTI/profile pieces
    # used by this migration. Its metadata pulls in Dexterity and EasyForm.
    print('Installing/updating %s in /%s' % (PROFILE, site_id))
    site.portal_setup.runAllImportStepsFromProfile(PROFILE)
    transaction.commit()
    return site


def run(app):
    for site_id, title in SITES:
        ensure_site(app, site_id, title)
    print('Target preparation complete for: %s' %
          ', '.join(site_id for site_id, unused in SITES))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
