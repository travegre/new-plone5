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
    """Synchronously reindex selected indexes through Plone's catalog wrapper."""
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


def _clear_indexes(catalog, names):
    """Clear named indexes with portal_catalog as acquisition parent.

    The index objects live in ``catalog._catalog.indexes`` and are not exposed
    as attributes of portal_catalog.  ZCTextIndex.clear() nevertheless needs
    portal_catalog as its acquisition parent so getLexicon() can resolve the
    configured htmltext_lexicon.  Wrap each raw index explicitly with
    ``__of__(catalog)`` before clearing it.
    """
    cleared = []
    for name in names:
        raw = catalog._catalog.indexes.get(name)
        if raw is None:
            continue
        index = raw.__of__(catalog)
        index.clear()
        cleared.append(name)
    return cleared


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
            names = tuple(expected.keys())
            cleared = _clear_indexes(catalog, names)
            print('CLEARED PREISKAVE INDEXES:', cleared)
            count = _reindex_objects(
                site,
                'imi.exams.examination',
                names,
            )
            print('REINDEXED PREISKAVE EXAMS:', count)
            _print_index_state(catalog, names)
            scope = {
                'portal_type': 'imi.exams.examination',
                'path': {'query': '/'.join(site.getPhysicalPath()), 'depth': -1},
            }
            for term in ('Toxoplasma*', 'PARAZITOLOGIJA*'):
                found = catalog.unrestrictedSearchResults(moj=term, **scope)
                print('  moj %r -> %d' % (term, len(found)))
        elif changed:
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
