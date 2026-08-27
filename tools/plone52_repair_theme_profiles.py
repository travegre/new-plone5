#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Install missing Plone 5 theming profiles on existing target sites."""

from plone.app.theming.interfaces import IThemeSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.hooks import setSite

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
PROFILES = (
    'profile-plone.app.theming:default',
    'profile-plonetheme.barceloneta:default',
    'profile-imi.migration:default',
)


def ensure_theme_registry(site):
    setSite(site)
    registry = getUtility(IRegistry)
    try:
        settings = registry.forInterface(IThemeSettings)
    except KeyError:
        registry.registerInterface(IThemeSettings)
        settings = registry.forInterface(IThemeSettings)
    if settings.currentTheme is None:
        settings.currentTheme = u''
    return settings


def run(app):
    import transaction

    updated = 0
    for site_id in SITES:
        if site_id not in app.objectIds():
            print('missing: /%s' % site_id)
            continue
        site = app[site_id]
        setSite(site)
        setup = site.portal_setup
        try:
            ensure_theme_registry(site)
            for profile in PROFILES:
                setup.runAllImportStepsFromProfile(profile)
                print('/%s: applied %s' % (site_id, profile))
            transaction.commit()
            updated += 1
        except Exception as exc:
            transaction.abort()
            print('/%s: ERROR %r' % (site_id, exc))
    setSite(None)
    print('Sites repaired: %d' % updated)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
