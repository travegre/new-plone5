#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Probe persisted search terms and anonymous visibility in Plone 5.2."""
from __future__ import print_function

from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import noSecurityManager
from AccessControl.SpecialUsers import nobody


def _path(obj):
    return '/'.join(obj.getPhysicalPath()) if obj is not None else None


def _query(catalog, **kw):
    try:
        return list(catalog.unrestrictedSearchResults(**kw))
    except Exception as exc:
        print('  QUERY ERROR %r: %r' % (kw, exc))
        return []


def _anonymous_count(catalog, **kw):
    noSecurityManager()
    newSecurityManager(None, nobody)
    try:
        return len(catalog(**kw))
    finally:
        noSecurityManager()


def _probe_imenik(app):
    site = app.unrestrictedTraverse('portal')
    catalog = site.portal_catalog
    base = site.get('data2')
    path = _path(base)
    scope = dict(portal_type='imi.directory.person',
                 path={'query': path, 'depth': -1})
    brains = _query(catalog, **scope)
    print('\n=== IMENIK ===')
    print('PERSONS unrestricted:', len(brains))
    print('PERSONS anonymous:', _anonymous_count(catalog, **scope))
    if brains:
        brain = brains[0]
        obj = brain._unrestrictedGetObject()
        print('SAMPLE:', brain.getPath(), repr(brain.Title))
        try:
            print('SAMPLE review_state:', repr(brain.review_state))
        except Exception:
            pass
        print('SAMPLE rolesOfPermission(View):')
        for row in obj.rolesOfPermission('View'):
            if row.get('selected'):
                print(' ', row)
        for term in ('Vilma*', 'Zakrajšek*'):
            kw = dict(scope)
            kw['SearchableText'] = term
            print('SearchableText %r unrestricted: %d' %
                  (term, len(_query(catalog, **kw))))
            print('SearchableText %r anonymous: %d' %
                  (term, _anonymous_count(catalog, **kw)))


def _probe_preiskave(app):
    site = app.unrestrictedTraverse('preiskave')
    catalog = site.portal_catalog
    base = site.get('preiskave-1')
    path = _path(base)
    scope = dict(portal_type='imi.exams.examination',
                 path={'query': path, 'depth': -1})
    brains = _query(catalog, **scope)
    print('\n=== PREISKAVE ===')
    print('EXAMS unrestricted:', len(brains))
    print('EXAMS anonymous:', _anonymous_count(catalog, **scope))
    if brains:
        brain = brains[0]
        print('SAMPLE:', brain.getPath(), repr(brain.Title))
        try:
            print('SAMPLE review_state:', repr(brain.review_state))
        except Exception:
            pass
    for term in ('Toxoplasma*', 'test*'):
        kw = dict(scope)
        kw['moj'] = term
        found = _query(catalog, **kw)
        print('moj %r unrestricted: %d' % (term, len(found)))
        print('moj %r anonymous: %d' % (term, _anonymous_count(catalog, **kw)))
        for brain in found[:3]:
            print(' ', brain.getPath(), repr(brain.Title))

    idx = catalog._catalog.indexes.get('moj')
    if idx is not None:
        print('moj numObjects:', idx.numObjects())
        try:
            print('moj uniqueValues sample:', list(idx.uniqueValues())[:30])
        except Exception as exc:
            print('moj uniqueValues ERROR:', repr(exc))


def run(app):
    _probe_imenik(app)
    _probe_preiskave(app)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 buildout.')
run(app)
