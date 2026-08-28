#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild each migrated Plone site's catalog.

The first bulk import can precede the final custom-type/profile state.  A full
catalog rebuild makes portal_type/path/workflow indexes agree with the actual
objects in the ZODB.  This is required by the public IMENIK, Preiskave,
Kiestra, Dežurstva and Nadomeščanja views.
"""
import transaction
from zope.component.hooks import setSite

SITE_IDS = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
CUSTOM_TYPES = (
    'imi.directory.person',
    'imi.duty.roster_day',
    'imi.staff.employee',
    'imi.kiestra.work_day',
    'imi.exams.examination',
    'imi.replacements.day',
    'imi.replacements.laboratory',
)


def run(app):
    for site_id in SITE_IDS:
        if site_id not in app.objectIds():
            print('/%s missing - skipped' % site_id)
            continue
        site = app[site_id]
        setSite(site)
        try:
            catalog = site.portal_catalog
            print('/%s: rebuilding portal_catalog ...' % site_id)
            catalog.clearFindAndRebuild()
            transaction.commit()
            counts = []
            for portal_type in CUSTOM_TYPES:
                count = len(catalog(portal_type=portal_type,
                                    path='/'.join(site.getPhysicalPath())))
                if count:
                    counts.append('%s=%d' % (portal_type, count))
            print('  custom content: %s' % (', '.join(counts) if counts else 'none'))
        except Exception:
            transaction.abort()
            raise
        finally:
            setSite(None)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
