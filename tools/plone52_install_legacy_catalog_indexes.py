#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Install/reindex the legacy custom catalog indexes in all five Plone 5.2 sites."""
from __future__ import print_function

import transaction

from imi.migration.setuphandlers import HTMLTEXT_LEXICON_ID
from imi.migration.setuphandlers import SITE_INDEXES
from imi.migration.setuphandlers import install_catalog_indexes


SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


def _reindex_objects(site, portal_type, idxs):
    """Synchronously reindex selected indexes through Plone's catalog wrapper.

    ``obj.reindexObject()`` goes through CMFCore's transaction-aware indexing
    queue.  For this offline migration/repair script we deliberately call
    ``portal_catalog.catalog_object`` directly: CatalogTool wraps the object
    with ``IIndexableObject`` before handing it to ZCatalog, so named
    ``plone.indexer`` adapters are still used, but the selected indexes are
    updated immediately and can be verified in this same process.
    """
    catalog = site.portal_catalog
    brains = list(catalog.unrestrictedSearchResults(
        portal_type=portal_type,
        path={'query': '/'.join(site.getPhysicalPath()), 'depth': -1},
    ))
    for brain in brains:
        obj = brain._unrestrictedGetObject()
        catalog.catalog_object(
            obj,
            uid=brain.getPath(),
            idxs=list(idxs),
            update_metadata=0,
        )
    return len(brains)


def _print_index_state(catalog, names):
    print('INDEX OBJECT COUNTS:')
    for name in names:
        index = catalog._catalog.indexes.get(name)
        if index is None:
            print('  %s: MISSING' % name)
            continue
        try:
            count = index.numObjects()
        except Exception:
            count = '<unavailable>'
        print('  %s: %s' % (name, count))


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
            changed = install_catalog_indexes(site, reindex=False)
        except Exception as exc:
            print('ERROR installing indexes:', repr(exc))
            transaction.abort()
            raise

        expected = SITE_INDEXES[site_id]
        catalog = site.portal_catalog

        if site_id == 'portal':
            count = _reindex_objects(
                site, 'imi.directory.person', ('SearchableText', 'priimek'))
            print('REINDEXED IMENIK PERSONS:', count)
            _print_index_state(catalog, ('SearchableText', 'priimek'))
            scope = {
                'portal_type': 'imi.directory.person',
                'path': {'query': '/'.join(site.getPhysicalPath()), 'depth': -1},
            }
            for term in ('Reklamacijsko*', 'Financna*', '2573*'):
                found = catalog.unrestrictedSearchResults(SearchableText=term, **scope)
                print('  SearchableText %r -> %d' % (term, len(found)))
        elif site_id == 'preiskave':
            count = _reindex_objects(
                site,
                'imi.exams.examination',
                tuple(expected.keys()),
            )
            print('REINDEXED PREISKAVE EXAMS:', count)
            _print_index_state(catalog, tuple(expected.keys()))
            scope = {
                'portal_type': 'imi.exams.examination',
                'path': {'query': '/'.join(site.getPhysicalPath()), 'depth': -1},
            }
            for term in ('Toxoplasma*', 'PARAZITOLOGIJA*'):
                found = catalog.unrestrictedSearchResults(moj=term, **scope)
                print('  moj %r -> %d' % (term, len(found)))
        elif changed:
            # These indexes use object attributes directly and do not need a
            # custom named indexer. Reindexing a newly-created/corrected index
            # through ZCatalog is sufficient.
            catalog.manage_reindexIndex(ids=list(changed))

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

    transaction.commit()
    print('\nCOMMITTED catalog/index changes.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
