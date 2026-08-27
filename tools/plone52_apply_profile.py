#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reapply the imi.migration GenericSetup profile to existing Plone 5.2 sites.

This is intentionally idempotent and does not touch migrated content.  It is
used when the migration package gains registry/resources/type configuration
that existing test sites need without recreating the database.
"""
from zope.component import getUtility
from zope.component.hooks import setSite
from plone.registry.interfaces import IRegistry

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
PROFILE = 'profile-imi.migration:default'


def ensure_imi_types_in_navigation(site):
    """Make every current/future migration-created ``imi.*`` FTI navigable."""
    registry = getUtility(IRegistry)
    key = 'plone.displayed_types'
    current = list(registry.get(key, ()) or ())
    custom_types = sorted(
        type_id for type_id in site.portal_types.objectIds()
        if str(type_id).startswith('imi.')
    )
    changed = False
    for type_id in custom_types:
        if type_id not in current:
            current.append(type_id)
            changed = True
    if changed:
        registry[key] = tuple(current)
    return custom_types


def run(app):
    import transaction

    updated = 0
    try:
        for site_id in SITES:
            site = app.get(site_id)
            if site is None:
                print('Missing site: %s' % site_id)
                continue
            setSite(site)
            site.portal_setup.runAllImportStepsFromProfile(PROFILE)
            custom_types = ensure_imi_types_in_navigation(site)
            updated += 1
            print('Updated profile: %s' % site_id)
            print('  navigation IMI types: %s' % ', '.join(custom_types))
        transaction.commit()
    finally:
        setSite(None)
    print('Sites updated: %d' % updated)


run(app)
