#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Restore public View permission inherited by the five legacy sites."""
from __future__ import print_function

import transaction

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


def _selected_roles(obj, permission):
    return [row['name'] for row in obj.rolesOfPermission(permission)
            if row.get('selected')]


def run(app):
    for site_id in SITES:
        site = app.unrestrictedTraverse(site_id)
        catalog = site.portal_catalog
        roles = _selected_roles(site, 'View')
        if 'Anonymous' not in roles:
            roles.append('Anonymous')
        # These five migrated applications are public legacy sites. Their
        # migrated custom Dexterity types have no workflow chain, so workflow
        # role mapping cannot grant View. Restore View at the site root and let
        # descendants acquire it, matching their public legacy behaviour.
        site.manage_permission('View', roles=roles, acquire=True)
        catalog.manage_reindexIndex(ids=['allowedRolesAndUsers'])
        print('%s: View roles=%r; allowedRolesAndUsers reindexed' %
              (site_id, _selected_roles(site, 'View')))
    transaction.commit()
    print('\nCOMMITTED public View repair.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
