#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe actual 5.2 search indexes without request security filtering."""
from __future__ import print_function

from plone.indexer.wrapper import IndexableObjectWrapper


def _path(obj):
    return '/'.join(obj.getPhysicalPath()) if obj is not None else None


def _index_info(catalog, name):
    idx = catalog._catalog.indexes.get(name)
    if idx is None:
        print('INDEX %s: MISSING' % name)
        return
    try:
        attrs = list(idx.getIndexSourceNames() or ())
    except Exception:
        attrs = list(getattr(idx, '_indexed_attrs', ()) or ())
    print('INDEX %s: %s attrs=%r lexicon=%r' % (
        name, getattr(idx, 'meta_type', idx.__class__.__name__), attrs,
        getattr(idx, 'lexicon_id', None)))


def _wrapper_value(obj, catalog, name):
    try:
        return getattr(IndexableObjectWrapper(obj, catalog), name)
    except Exception as exc:
        return 'ERROR %r' % (exc,)


def _probe_imenik(app):
    site = app.unrestrictedTraverse('portal')
    catalog = site.portal_catalog
    base = site.get('data2')
    path = _path(base)
    print('\n=== IMENIK SEARCH ===')
    _index_info(catalog, 'SearchableText')
    _index_info(catalog, 'priimek')
    brains = list(catalog.unrestrictedSearchResults(
        portal_type='imi.directory.person', path={'query': path, 'depth': -1}))
    print('PERSON BRAINS unrestricted:', len(brains))
    if not brains:
        return
    obj = brains[0].getObject()
    print('SAMPLE:', _path(obj), repr(obj.Title()))
    print('WRAPPER SearchableText:', repr(_wrapper_value(obj, catalog, 'SearchableText'))[:1500])
    for raw in (getattr(obj, 'priimek', ''), getattr(obj, 'ime', ''), obj.Title()):
        raw = str(raw or '').strip()
        if not raw:
            continue
        q = raw.split()[0] + '*'
        try:
            result = catalog.unrestrictedSearchResults(
                SearchableText=q, portal_type='imi.directory.person',
                path={'query': path, 'depth': -1})
            print('QUERY SearchableText %r -> %d' % (q, len(result)))
        except Exception as exc:
            print('QUERY SearchableText %r ERROR: %r' % (q, exc))


def _probe_preiskave(app):
    site = app.unrestrictedTraverse('preiskave')
    catalog = site.portal_catalog
    base = site.get('preiskave-1')
    path = _path(base)
    print('\n=== PREISKAVE SEARCH ===')
    for name in ('moj', 'moj_sklop', 'sklop', 'podrocje', 'vzorci_lab'):
        _index_info(catalog, name)
    brains = list(catalog.unrestrictedSearchResults(
        portal_type='imi.exams.examination', path={'query': path, 'depth': -1}))
    print('EXAM BRAINS unrestricted:', len(brains))
    if not brains:
        return
    obj = brains[0].getObject()
    print('SAMPLE:', _path(obj), repr(obj.Title()))
    for name in ('moj', 'sklop', 'sinonim', 'vzorci', 'podrocje', 'vzorci_lab'):
        print('WRAPPER %s: %r' % (name, _wrapper_value(obj, catalog, name))[:1500])
    title = str(obj.Title() or '').strip()
    probes = []
    if title:
        probes.append(title.split()[0])
    probes.extend(['Toxoplasma', 'test'])
    for raw in probes:
        q = raw + '*'
        try:
            result = catalog.unrestrictedSearchResults(
                moj=q, portal_type='imi.exams.examination',
                path={'query': path, 'depth': -1})
            print('QUERY moj %r -> %d' % (q, len(result)))
        except Exception as exc:
            print('QUERY moj %r ERROR: %r' % (q, exc))


def run(app):
    _probe_imenik(app)
    _probe_preiskave(app)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
