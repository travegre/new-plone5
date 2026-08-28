#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit physically stored migrated content without relying on portal_catalog.

Use this when catalog counts are unexpectedly zero. The script walks the ZODB
object tree directly and reports portal_type counts, representative paths, and
explicit counts for the custom types expected in each migrated site.
"""
from collections import Counter, defaultdict


EXPECTED_TYPES = {
    'portal': (
        'imi.directory.person',
    ),
    'dezurstva': (
        'imi.duty.roster_day',
        'imi.staff.directory',
        'imi.staff.employee',
    ),
    'kiestra': (
        'imi.kiestra.work_day',
    ),
    'preiskave': (
        'imi.exams.examination',
    ),
    'nadomescanja': (
        'imi.replacements.day',
        'imi.replacements.laboratory',
    ),
}


def walk(obj, path=''):
    try:
        obj_id = obj.getId()
    except Exception:
        obj_id = getattr(obj, 'id', '') or ''
    here = (path.rstrip('/') + '/' + str(obj_id)).replace('//', '/') if obj_id else (path or '/')
    yield obj, here
    object_values = getattr(obj, 'objectValues', None)
    if callable(object_values):
        try:
            children = list(object_values())
        except Exception:
            children = []
        for child in children:
            for item in walk(child, here):
                yield item


def audit_site(site, roots=None):
    site_id = site.getId()
    print('\n=== /%s ===' % site_id)
    starts = []
    if roots:
        for root_id in roots:
            root = site.get(root_id)
            if root is None:
                print('missing root: /%s/%s' % (site_id, root_id))
            else:
                starts.append(root)
    if not starts:
        starts = [site]

    counts = Counter()
    samples = defaultdict(list)
    total = 0
    for start in starts:
        base_parent = '/' + site_id
        for obj, path in walk(start, base_parent):
            total += 1
            portal_type = str(getattr(obj, 'portal_type', '') or obj.__class__.__name__)
            counts[portal_type] += 1
            if len(samples[portal_type]) < 8:
                samples[portal_type].append(path)

    print('objects walked: %d' % total)
    print('expected migrated custom content:')
    for portal_type in EXPECTED_TYPES.get(site_id, ()):
        count = counts.get(portal_type, 0)
        print('  %-35s %d %s' % (
            portal_type, count, 'OK' if count else 'MISSING'))
        for path in samples.get(portal_type, ()): 
            print('      %s' % path)

    print('all physical portal_type counts:')
    for portal_type, count in counts.most_common():
        print('  %-35s %d' % (portal_type, count))
        if portal_type not in EXPECTED_TYPES.get(site_id, ()):
            for path in samples[portal_type]:
                print('      %s' % path)


def run(app):
    # Keep the audit scoped to the legacy business-data roots where known.
    # Kiestra/Nadomescanja are walked from the site root because their old
    # /nastavitve/dezurstva acquisition path cannot be safely recreated.
    plans = (
        ('portal', ('data2',)),
        ('dezurstva', ('dezurstva-1', 'seznam_zaposlenih')),
        ('kiestra', None),
        ('preiskave', ('preiskave-1',)),
        ('nadomescanja', None),
    )
    for site_id, roots in plans:
        if site_id not in app.objectIds():
            print('\n=== /%s missing ===' % site_id)
            continue
        audit_site(app[site_id], roots)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
