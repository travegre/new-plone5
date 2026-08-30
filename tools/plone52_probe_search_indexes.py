#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe workflow security and Plone 5.2 catalog/indexer wiring."""
from __future__ import print_function

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SpecialUsers import nobody
from plone.indexer.interfaces import IIndexer
from plone.indexer.interfaces import IIndexableObject
from zope.component import queryMultiAdapter
from zope.interface import providedBy

from imi.migration.content import IDirectoryPerson
from imi.migration.content import IExamination


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


def _interfaces(obj, expected):
    print('EXPECTED SCHEMA PROVIDED:', expected.providedBy(obj))
    print('PROVIDED INTERFACES:')
    for iface in providedBy(obj).flattened():
        print(' ', getattr(iface, '__identifier__', repr(iface)))


def _fti(site, obj):
    fti = site.portal_types.get(obj.portal_type)
    print('FTI:', fti)
    if fti is None:
        return
    print('FTI klass:', getattr(fti, 'klass', None))
    print('FTI schema:', getattr(fti, 'schema', None))
    try:
        schema = fti.lookupSchema()
    except Exception as exc:
        print('FTI lookupSchema ERROR:', repr(exc))
    else:
        print('FTI lookupSchema:', getattr(schema, '__identifier__', repr(schema)))
        print('FTI schema provided by object:', schema.providedBy(obj))


def _adapter(obj, catalog, name):
    # plone.indexer 1.x (used by Plone 5.2) defines an indexer as a named
    # multi-adapter from (object, catalog) to IIndexer.  The IndexableObject
    # wrapper performs this same lookup.  Do not use queryAdapter(obj, ...)
    # and do not use the request as the second adapted object.
    adapter = queryMultiAdapter((obj, catalog), IIndexer, name=name)
    print('INDEXER %s:' % name, adapter)
    if adapter is not None:
        try:
            print('INDEXER %s VALUE:' % name, repr(adapter())[:4000])
        except Exception as exc:
            print('INDEXER %s ERROR:' % name, repr(exc))

    wrapper = queryMultiAdapter((obj, catalog), IIndexableObject)
    print('INDEXABLE WRAPPER:', wrapper)
    if wrapper is not None:
        try:
            value = getattr(wrapper, name)
            if callable(value):
                value = value()
            print('WRAPPER %s VALUE:' % name, repr(value)[:4000])
        except Exception as exc:
            print('WRAPPER %s ERROR:' % name, repr(exc))


def _directory_field_queries(catalog, base, obj):
    print('DIRECTORY FIELD VALUES:')
    for field in ('ime', 'priimek', 'oddelek', 'telefon', 'enota', 'lokacija',
                  'dect', 'fax', 'mobilna', 'enaslov'):
        value = getattr(obj, field, '') or ''
        print('  %s=%r' % (field, value))
        text = str(value).strip()
        if not text:
            continue
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
        _fti(site, obj)
        _interfaces(obj, IDirectoryPerson)
        _adapter(obj, catalog, 'SearchableText')
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
        _fti(site, obj)
        _interfaces(obj, IExamination)
        _adapter(obj, catalog, 'moj')
        _adapter(obj, catalog, 'sklop')
        _adapter(obj, catalog, 'sinonim')
    idx = catalog._catalog.indexes.get('moj')
    print('moj numObjects:', idx.numObjects() if idx is not None else 'MISSING')
    for term in ('Toxoplasma*', 'test*'):
        found = list(catalog.unrestrictedSearchResults(moj=term, **scope))
        print('moj %r unrestricted: %d' % (term, len(found)))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
