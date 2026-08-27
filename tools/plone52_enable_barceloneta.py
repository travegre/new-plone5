#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ensure the five migrated Plone sites use the stock Barceloneta theme.

This is intentionally separate from the future public-site presentation port:
while we rebuild the old ``*.podoba`` behavior, editors should always have a
known-good stock Plone 5 UI.

Run with the main instance stopped::

    bin/instance run tools/plone52_enable_barceloneta.py
"""
from plone.app.theming.interfaces import IThemeSettings
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.component.hooks import setSite

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


def run(app):
    import transaction

    changed = 0
    try:
        for site_id in SITES:
            site = app.get(site_id)
            if site is None:
                print('missing: /%s' % site_id)
                continue

            setSite(site)
            registry = getUtility(IRegistry)
            settings = registry.forInterface(IThemeSettings, check=False)

            before_enabled = getattr(settings, 'enabled', None)
            before_theme = getattr(settings, 'current_theme', None)

            settings.enabled = True
            settings.current_theme = 'barceloneta'

            print(
                '/%s: enabled %r -> %r, theme %r -> %r' % (
                    site_id,
                    before_enabled,
                    settings.enabled,
                    before_theme,
                    settings.current_theme,
                )
            )
            changed += 1

        transaction.commit()
        print('Sites updated: %d' % changed)
    finally:
        setSite(None)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
