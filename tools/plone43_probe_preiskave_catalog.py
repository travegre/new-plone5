#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only probe for the legacy Preiskave ``moj`` catalog index."""
from __future__ import print_function
import sys


def call_or_value(obj, name):
    try:
        value = getattr(obj, name)
    except Exception as exc:
        return '<error reading %s: %r>' % (name, exc)
    if callable(value):
        try:
            return value()
        except TypeError:
            return '<call requires arguments>'
        except Exception as exc:
            return '<error calling %s: %r>' % (name, exc)
    return value


def describe_index(index):
    print('INDEX CLASS:', '%s.%s' % (index.__class__.__module__, index.__class__.__name__))
    for name in (
        'id', 'meta_type', 'getId', 'getIndexSourceNames', 'getLexicon',
        'lexicon_id', '_indexed_attrs', 'indexed_attrs', 'source_names',
    ):
        if hasattr(index, name):
            print('%s: %r' % (name, call_or_value(index, name)))
    print('INDEX __dict__ keys:', sorted(getattr(index, '__dict__', {}).keys()))
    for key in sorted(getattr(index, '__dict__', {}).keys()):
        if any(token in key.lower() for token in ('source', 'attr', 'lexicon')):
            try:
                print('  %s = %r' % (key, getattr(index, key)))
            except Exception as exc:
                print('  %s = <error: %r>' % (key, exc))


def describe_lexicon(site, catalog, lexicon_id):
    print('\nLEXICON')
    lexicon = None
    for parent in (site, catalog):
        try:
            lexicon = parent.unrestrictedTraverse(lexicon_id)
            break
        except Exception:
            try:
                lexicon = getattr(parent, lexicon_id)
                break
            except Exception:
                pass
    if lexicon is None:
        print('Could not traverse lexicon %r' % lexicon_id)
        return

    print('LEXICON CLASS:', '%s.%s' %
          (lexicon.__class__.__module__, lexicon.__class__.__name__))
    print('id:', repr(getattr(lexicon, 'id', None)))
    print('meta_type:', repr(getattr(lexicon, 'meta_type', None)))
    print('LEXICON __dict__ keys:', sorted(getattr(lexicon, '__dict__', {}).keys()))

    pipeline = getattr(lexicon, '_pipeline', None)
    if pipeline is None:
        pipeline = getattr(lexicon, 'pipeline', None)
    if pipeline is None:
        print('pipeline: <not found>')
        return

    print('pipeline length:', len(pipeline))
    for pos, element in enumerate(pipeline):
        print('  %02d %s.%s' %
              (pos, element.__class__.__module__, element.__class__.__name__))
        data = getattr(element, '__dict__', {})
        if data:
            for key in sorted(data.keys()):
                try:
                    print('       %s = %r' % (key, data[key]))
                except Exception as exc:
                    print('       %s = <error: %r>' % (key, exc))


def legacy_query(q):
    for char in '?-+*':
        q = q.replace(char, ' ')
    value = ' AND '.join(q.split())
    value = value.replace('(', '"("').replace(')', '")"')
    return value + '*'


def brain_id(brain):
    for name in ('getId', 'id'):
        try:
            value = getattr(brain, name)
            value = value() if callable(value) else value
            if value:
                return value
        except Exception:
            pass
    try:
        return brain.getPath().rstrip('/').rsplit('/', 1)[-1]
    except Exception:
        return ''


def dump_query(catalog, q):
    transformed = legacy_query(q)
    try:
        results = catalog(moj=transformed, portal_type='imipreiskava')
        print('\nlegacy q=%r transformed query %r -> %d' %
              (q, transformed, len(results)))
        print('FULL LEGACY RESULT ORDER FOR %r' % q)
        for position, brain in enumerate(results, 1):
            try:
                path = brain.getPath()
            except Exception:
                path = ''
            print('%03d\t%s\t%s\t%s' %
                  (position, brain_id(brain), path, brain.Title))
    except Exception as exc:
        print('legacy q=%r query failed: %r' % (q, exc))


def run(app):
    site = app.unrestrictedTraverse('preiskave')
    catalog = site.portal_catalog
    indexes = catalog._catalog.indexes
    if 'moj' not in indexes:
        print("ERROR: portal_catalog has no index named 'moj'")
        print('Available indexes:', sorted(indexes.keys()))
        return

    index = indexes['moj']
    describe_index(index)
    describe_lexicon(site, catalog, getattr(index, 'lexicon_id', 'htmltext_lexicon'))

    print('\nREFERENCE COUNTS')
    for query in ('test*', '"test"*', 'test', 'test AND test*', 'te*'):
        try:
            results = catalog(moj=query, portal_type='imipreiskava')
            print('%r -> %d' % (query, len(results)))
        except Exception as exc:
            print('%r -> ERROR %r' % (query, exc))

    queries = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
    if not queries:
        queries = ['test', 'te']
    for q in queries:
        dump_query(catalog, q)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 4.3 buildout.')
run(app)
