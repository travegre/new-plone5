#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe actual 5.2 catalog contents for IMENIK and PREISKAVE."""
from __future__ import print_function
from collections import Counter


def _path(obj):
    return '/'.join(obj.getPhysicalPath()) if obj is not None else None


def _dump(site, base_id, label):
    catalog = site.portal_catalog
    base = site.get(base_id)
    print('\n=== %s ===' % label)
    print('SITE PATH:', _path(site))
    print('BASE %s:' % base_id, repr(base), 'PATH:', _path(base))

    restricted = list(catalog())
    unrestricted = list(catalog.unrestrictedSearchResults())
    print('CATALOG TOTAL restricted:', len(restricted))
    print('CATALOG TOTAL unrestricted:', len(unrestricted))
    print('RAW CATALOG LENGTH:', len(catalog._catalog.data))

    counts = Counter(str(b.portal_type) for b in unrestricted)
    print('PORTAL TYPES (unrestricted):')
    for name, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
        print('  %r: %d' % (name, count))

    if base is not None:
        query_path = {'query': _path(base), 'depth': -1}
        rbrains = list(catalog(path=query_path))
        ubrains = list(catalog.unrestrictedSearchResults(path=query_path))
        print('UNDER BASE restricted:', len(rbrains))
        print('UNDER BASE unrestricted:', len(ubrains))
        base_counts = Counter(str(b.portal_type) for b in ubrains)
        for name, count in sorted(base_counts.items(), key=lambda row: (-row[1], row[0])):
            print('  %r: %d' % (name, count))
        print('FIRST 10 UNDER BASE unrestricted:')
        for brain in ubrains[:10]:
            print('  type=%r path=%r title=%r' %
                  (brain.portal_type, brain.getPath(), brain.Title))

    print('FIRST 10 SITE CATALOG unrestricted:')
    for brain in unrestricted[:10]:
        print('  type=%r path=%r title=%r' %
              (brain.portal_type, brain.getPath(), brain.Title))


def run(app):
    _dump(app.unrestrictedTraverse('portal'), 'data2', 'IMENIK')
    _dump(app.unrestrictedTraverse('preiskave'), 'preiskave-1', 'PREISKAVE')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
