#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Apply workflow permission mappings to already-migrated content."""
from __future__ import print_function

import transaction

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


def run(app):
    for site_id in SITES:
        site = app.unrestrictedTraverse(site_id)
        workflow = site.portal_workflow
        catalog = site.portal_catalog
        print('\nSITE:', site_id)
        workflow.updateRoleMappings()
        # allowedRolesAndUsers is derived from the effective permissions/local
        # roles. Refresh it after workflow permission maps have been applied.
        catalog.manage_reindexIndex(ids=['allowedRolesAndUsers'])
        print('  workflow role mappings applied')
        print('  allowedRolesAndUsers reindexed')
    transaction.commit()
    print('\nCOMMITTED public-security repair.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
