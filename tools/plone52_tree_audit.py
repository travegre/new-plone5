#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit physically stored content without relying on portal_catalog.

Use this when catalog counts are unexpectedly zero. The script walks the ZODB
object tree directly and reports portal_type counts plus representative paths.
"""
from collections import Counter, defaultdict


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
    print('\n=== /%s ===' % site.getId())
    starts = []
    if roots:
        for root_id in roots:
            root = site.get(root_id)
            if root is None:
                print('missing root: /%s/%s' % (site.getId(), root_id))
            else:
                starts.append(root)
    if not starts:
        starts = [site]

    counts = Counter()
    samples = defaultdict(list)
    total = 0
    for start in starts:
        base_parent = '/' + site.getId()
        for obj, path in walk(start, base_parent):
            total += 1
            portal_type = str(getattr(obj, 'portal_type', '') or obj.__class__.__name__)
            counts[portal_type] += 1
            if len(samples[portal_type]) < 8:
                samples[portal_type].append(path)

    print('objects walked: %d' % total)
    for portal_type, count in counts.most_common():
        print('  %-35s %d' % (portal_type, count))
        for path in samples[portal_type]:
            print('      %s' % path)


def run(app):
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
