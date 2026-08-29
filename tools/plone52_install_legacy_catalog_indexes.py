#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Install/reindex the legacy custom catalog indexes in all five Plone 5.2 sites."""
from __future__ import print_function

from imi.migration.setuphandlers import HTMLTEXT_LEXICON_ID
from imi.migration.setuphandlers import SITE_INDEXES
from imi.migration.setuphandlers import install_catalog_indexes


SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


def run(app):
    for site_id in SITES:
        print('\n' + '=' * 78)
        print('SITE:', site_id)
        try:
            site = app.unrestrictedTraverse(site_id)
        except Exception as exc:
            print('ERROR finding site:', repr(exc))
            continue

        try:
            changed = install_catalog_indexes(site, reindex=True)
        except Exception as exc:
            print('ERROR installing indexes:', repr(exc))
            raise

        expected = SITE_INDEXES[site_id]
        catalog = site.portal_catalog

        # IMENIK 4.3 searched the standard SearchableText index.  The migrated
        # Dexterity type now has an explicit SearchableText adapter reproducing
        # the old Archetypes searchable=True fields, so refresh this existing
        # standard index once after deploying the adapter.
        if site_id == 'portal':
            print('REINDEX: SearchableText')
            catalog.manage_reindexIndex(ids=['SearchableText'])

        print('CHANGED:', list(changed))
        print('CUSTOM INDEXES:')
        for name in sorted(expected):
            index = catalog._catalog.indexes.get(name)
            if index is None:
                print('  MISSING', name)
                continue
            try:
                attrs = list(index.getIndexSourceNames() or ())
            except Exception:
                attrs = list(getattr(index, '_indexed_attrs', ()) or ())
            print('  %s\t%s\t%r' %
                  (name, getattr(index, 'meta_type', index.__class__.__name__), attrs))
        if any(spec[2] == HTMLTEXT_LEXICON_ID for spec in expected.values()):
            lexicon = getattr(catalog, HTMLTEXT_LEXICON_ID, None)
            pipeline = []
            if lexicon is not None:
                pipeline = ['%s.%s' % (item.__class__.__module__, item.__class__.__name__)
                            for item in getattr(lexicon, '_pipeline', ())]
            print('LEXICON %s: %r' % (HTMLTEXT_LEXICON_ID, pipeline))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
