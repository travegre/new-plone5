#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe workflow security and registered search indexers."""
from __future__ import print_function

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SpecialUsers import nobody
from plone.indexer.interfaces import IIndexer
from zope.component import queryAdapter


def _path(obj):
    return '/'.join(obj.getPhysicalPath()) if obj is not None else None


def _anonymous_count(catalog, **kw):
    noSecurityManager(); newSecurityManager(None, nobody)
    try:
        return len(catalog(**kw))
    finally:
        noSecurityManager()


def _selected_roles(obj, permission):
    try:
        return [row['name'] for row in obj.rolesOfPermission(permission)
                if row.get('selected')]
    except Exception:
        return '<unavailable>'


def _workflow(site, obj):
    wf = site.portal_workflow
    print('TYPE:', obj.portal_type)
    print('CHAIN:', tuple(wf.getChainFor(obj)))
    print('STATE:', wf.getInfoFor(obj, 'review_state', None))
    print('VIEW ROLES:', _selected_roles(obj, 'View'))


def _adapter(obj, name):
    # @plone.indexer.indexer factories are named single adapters from the
    # content object to IIndexer.  Earlier probes incorrectly queried a
    # content+request multi-adapter and therefore always printed None.
    adapter = queryAdapter(obj, IIndexer, name=name)
    print('INDEXER %s:' % name, adapter)
    if adapter is not None:
        try:
            value = adapter()
            print('INDEXER %s VALUE:' % name, repr(value)[:4000])
        except Exception as exc:
            print('INDEXER %s ERROR:' % name, repr(exc))


def _directory_field_queries(catalog, base, obj):
    print('DIRECTORY FIELD VALUES:')
    for field in ('ime', 'priimek', 'oddelek', 'telefon', 'enota', 'lokacija',
                  'dect', 'fax', 'mobilna', 'enaslov'):
        value = getattr(obj, field, '') or ''
        print('  %s=%r' % (field, value))
        text = str(value).strip()
        if not text:
            continue
        # Use the first nontrivial token exactly as the legacy prefix search does.
        token = next((part for part in text.replace('/', ' ').replace(',', ' ').split()
                      if len(part) >= 3), None)
        if token:
            brains = catalog.unrestrictedSearchResults(
                SearchableText=token + '*',
                portal_type='imi.directory.person',
                path={'query': _path(base), 'depth': -1},
            )
            print('    SearchableText %r -> %d' % (token + '*', len(brains)))


def run(app):
    site = app.unrestrictedTraverse('portal')
    catalog = site.portal_catalog
    base = site.get('data2')
    scope = dict(portal_type='imi.directory.person', path={'query': _path(base), 'depth': -1})
    brains = list(catalog.unrestrictedSearchResults(**scope))
    print('\n=== IMENIK ===')
    print('PERSONS unrestricted:', len(brains), 'anonymous:', _anonymous_count(catalog, **scope))
    if brains:
        obj = brains[0]._unrestrictedGetObject()
        print('SAMPLE:', _path(obj), repr(obj.Title()))
        _workflow(site, obj)
        _adapter(obj, 'SearchableText')
        _directory_field_queries(catalog, base, obj)

    site = app.unrestrictedTraverse('preiskave')
    catalog = site.portal_catalog
    base = site.get('preiskave-1')
    scope = dict(portal_type='imi.exams.examination', path={'query': _path(base), 'depth': -1})
    brains = list(catalog.unrestrictedSearchResults(**scope))
    print('\n=== PREISKAVE ===')
    print('EXAMS unrestricted:', len(brains), 'anonymous:', _anonymous_count(catalog, **scope))
    if brains:
        obj = brains[0]._unrestrictedGetObject()
        print('SAMPLE:', _path(obj), repr(obj.Title()))
        _workflow(site, obj)
        _adapter(obj, 'moj')
        _adapter(obj, 'sklop')
        _adapter(obj, 'sinonim')
    idx = catalog._catalog.indexes.get('moj')
    print('moj numObjects:', idx.numObjects() if idx is not None else 'MISSING')
    for term in ('Toxoplasma*', 'test*'):
        found = list(catalog.unrestrictedSearchResults(moj=term, **scope))
        print('moj %r unrestricted: %d' % (term, len(found)))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
