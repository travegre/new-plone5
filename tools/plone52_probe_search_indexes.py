#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe the live 5.2 catalog/indexer state for IMENIK and PREISKAVE."""
from __future__ import print_function

from plone.indexer.wrapper import IndexableObjectWrapper


def _sample_brain(catalog, portal_type, path):
    brains = catalog(portal_type=portal_type, path=path)
    return brains[0] if brains else None, len(brains)


def _print_index(catalog, name):
    index = catalog._catalog.indexes.get(name)
    if index is None:
        print('INDEX %s: MISSING' % name)
        return
    try:
        attrs = list(index.getIndexSourceNames() or ())
    except Exception:
        attrs = list(getattr(index, '_indexed_attrs', ()) or ())
    print('INDEX %s: %s attrs=%r lexicon=%r' % (
        name,
        getattr(index, 'meta_type', index.__class__.__name__),
        attrs,
        getattr(index, 'lexicon_id', None),
    ))


def _probe_imenik(app):
    site = app.unrestrictedTraverse('portal')
    catalog = site.portal_catalog
    base = site.get('data2')
    path = '/'.join(base.getPhysicalPath()) if base is not None else '/'.join(site.getPhysicalPath())
    print('\n=== IMENIK ===')
    _print_index(catalog, 'SearchableText')
    _print_index(catalog, 'priimek')
    brain, count = _sample_brain(catalog, 'imi.directory.person', path)
    print('PERSON BRAINS:', count)
    if brain is None:
        return
    obj = brain.getObject()
    wrapper = IndexableObjectWrapper(obj, catalog)
    print('SAMPLE PATH:', '/'.join(obj.getPhysicalPath()))
    print('SAMPLE TITLE:', repr(obj.Title()))
    print('SAMPLE IME/PRIIMEK:', repr(getattr(obj, 'ime', '')), repr(getattr(obj, 'priimek', '')))
    try:
        value = wrapper.SearchableText
    except Exception as exc:
        value = 'ERROR %r' % (exc,)
    print('WRAPPER SearchableText:', repr(value)[:1000])
    probes = []
    for raw in (getattr(obj, 'priimek', ''), getattr(obj, 'ime', ''), obj.Title()):
        raw = str(raw or '').strip()
        if raw:
            probes.append(raw.split()[0])
    for q in probes[:3]:
        transformed = ' AND '.join(q.replace('?', ' ').replace('-', ' ').replace('+', ' ').replace('*', ' ').split()) + '*'
        result = catalog(SearchableText=transformed,
                         portal_type='imi.directory.person', path=path)
        print('QUERY SearchableText %r -> %d' % (transformed, len(result)))


def _probe_preiskave(app):
    site = app.unrestrictedTraverse('preiskave')
    catalog = site.portal_catalog
    base = site.get('preiskave-1')
    path = '/'.join(base.getPhysicalPath()) if base is not None else '/'.join(site.getPhysicalPath())
    print('\n=== PREISKAVE ===')
    for name in ('moj', 'moj_sklop', 'sklop', 'podrocje', 'vzorci_lab'):
        _print_index(catalog, name)
    brain, count = _sample_brain(catalog, 'imi.exams.examination', path)
    print('EXAM BRAINS:', count)
    if brain is None:
        return
    obj = brain.getObject()
    wrapper = IndexableObjectWrapper(obj, catalog)
    print('SAMPLE PATH:', '/'.join(obj.getPhysicalPath()))
    print('SAMPLE TITLE:', repr(obj.Title()))
    for name in ('moj', 'sklop', 'sinonim', 'vzorci', 'podrocje', 'vzorci_lab'):
        try:
            value = getattr(wrapper, name)
        except Exception as exc:
            value = 'ERROR %r' % (exc,)
        print('WRAPPER %s: %r' % (name, value)[:1000])
    title = str(obj.Title() or '').strip()
    if title:
        q = title.split()[0]
        transformed = ' AND '.join(q.replace('?', ' ').replace('-', ' ').replace('+', ' ').replace('*', ' ').split()) + '*'
        result = catalog(moj=transformed,
                         portal_type='imi.exams.examination', path=path)
        print('QUERY moj %r -> %d' % (transformed, len(result)))


def run(app):
    _probe_imenik(app)
    _probe_preiskave(app)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
