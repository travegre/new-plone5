#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reapply the imi.migration GenericSetup profile to existing Plone 5.2 sites.

This is intentionally idempotent and does not touch migrated content.  It is
used when the migration package gains registry/resources/type configuration
that existing test sites need without recreating the database.
"""
from zope.component.hooks import setSite

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
PROFILE = 'profile-imi.migration:default'


def run(app):
    updated = 0
    try:
        for site_id in SITES:
            site = app.get(site_id)
            if site is None:
                print('Missing site: %s' % site_id)
                continue
            setSite(site)
            site.portal_setup.runAllImportStepsFromProfile(PROFILE)
            updated += 1
            print('Updated profile: %s' % site_id)
    finally:
        setSite(None)
    print('Sites updated: %d' % updated)


run(app)
