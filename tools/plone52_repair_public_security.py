#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Repair public View declarations created on migrated custom content."""
from __future__ import print_function

import transaction

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
CUSTOM_TYPES = {
    'imi.directory.person',
    'imi.staff.directory',
    'imi.staff.employee',
    'imi.duty.roster_day',
    'imi.kiestra.work_day',
    'imi.replacements.day',
    'imi.replacements.laboratory',
    'imi.exams.examination',
}


def _selected_roles(obj, permission):
    return [row['name'] for row in obj.rolesOfPermission(permission)
            if row.get('selected')]


def run(app):
    total = 0
    for site_id in SITES:
        site = app.unrestrictedTraverse(site_id)
        catalog = site.portal_catalog

        # The applications are public. Keep the site root public and acquiring.
        roles = _selected_roles(site, 'View')
        if 'Anonymous' not in roles:
            roles.append('Anonymous')
        site.manage_permission('View', roles=roles, acquire=True)

        brains = catalog.unrestrictedSearchResults(
            path={'query': '/'.join(site.getPhysicalPath()), 'depth': -1},
        )
        repaired = 0
        by_type = {}
        for brain in brains:
            if brain.portal_type not in CUSTOM_TYPES:
                continue
            obj = brain._unrestrictedGetObject()
            raw = getattr(obj, '_View_Permission', None)
            effective = _selected_roles(obj, 'View')
            # Imported custom objects have no workflow chain.  A local
            # _View_Permission tuple without Anonymous overrides the public
            # folder/site permission and is exactly what made catalog security
            # hide every person/examination.  Restore Anonymous while retaining
            # all existing roles and acquisition.
            if raw is not None and 'Anonymous' not in effective:
                new_roles = list(effective)
                new_roles.append('Anonymous')
                obj.manage_permission('View', roles=new_roles, acquire=True)
                obj.reindexObjectSecurity()
                repaired += 1
                by_type[brain.portal_type] = by_type.get(brain.portal_type, 0) + 1
        total += repaired
        print('%s: repaired=%d by_type=%r' % (site_id, repaired, by_type))

    transaction.commit()
    print('\nCOMMITTED custom-content public View repair: %d objects.' % total)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
