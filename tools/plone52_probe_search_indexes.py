#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe workflow security, permission acquisition and search indexers."""
from __future__ import print_function

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SpecialUsers import nobody
from plone.indexer.interfaces import IIndexer
from zope.component import queryMultiAdapter


def _path(obj):
    return '/'.join(obj.getPhysicalPath()) if obj is not None else None


def _anonymous_count(catalog, **kw):
    noSecurityManager(); newSecurityManager(None, nobody)
    try:
        return len(catalog(**kw))
    finally:
        noSecurityManager()


def _selected_roles(obj, permission):
    return [row['name'] for row in obj.rolesOfPermission(permission)
            if row.get('selected')]


def _permission_chain(obj):
    print('VIEW PERMISSION CHAIN:')
    chain = []
    current = obj
    while current is not None:
        chain.append(current)
        parent = getattr(current, 'aq_parent', None)
        if parent is None or parent is current:
            break
        current = parent
    for item in reversed(chain):
        path = _path(item) if hasattr(item, 'getPhysicalPath') else repr(item)
        local = getattr(item, '_View_Permission', '<inherited/no local declaration>')
        try:
            roles = _selected_roles(item, 'View')
        except Exception:
            roles = '<unavailable>'
        print('  %s' % path)
        print('    _View_Permission=%r' % (local,))
        print('    effective View roles=%r' % (roles,))


def _workflow(site, obj):
    wf = site.portal_workflow
    print('TYPE:', obj.portal_type)
    print('CHAIN:', tuple(wf.getChainFor(obj)))
    print('STATE:', wf.getInfoFor(obj, 'review_state', None))
    for wf_id in wf.getChainFor(obj):
        definition = wf.get(wf_id)
        state_id = wf.getStatusOf(wf_id, obj).get('review_state')
        state = definition.states.get(state_id) if definition is not None else None
        print('WORKFLOW:', wf_id, 'STATE:', state_id)
        if state is not None:
            print('  permission_roles:', repr(getattr(state, 'permission_roles', None)))
    print('VIEW ROLES:', _selected_roles(obj, 'View'))
    _permission_chain(obj)


def _adapter(obj, name):
    adapter = queryMultiAdapter((obj, obj.REQUEST), IIndexer, name=name)
    print('INDEXER %s:' % name, adapter)
    if adapter is not None:
        try:
            value = adapter()
            print('INDEXER %s VALUE:' % name, repr(value)[:2500])
        except Exception as exc:
            print('INDEXER %s ERROR:' % name, repr(exc))


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
