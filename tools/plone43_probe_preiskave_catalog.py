#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only probe for the legacy Preiskave ``moj`` catalog index.

Run this with the *Plone 4.3* instance, not the Plone 5.2 instance. The script
prints the concrete index class, source fields/attributes and reference query
counts so the 5.2 compatibility search can reproduce the old ZCTextIndex
instead of guessing its configuration.

Example::

    bin/instance run /path/to/new-plone5/tools/plone43_probe_preiskave_catalog.py

It does not modify the ZODB.
"""
from __future__ import print_function


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


def legacy_query(q):
    """Exact query rewrite used by preiskave.podoba/livesearch_reply.py."""
    for char in '?-+*':
        q = q.replace(char, ' ')
    words = q.split()
    value = ' AND '.join(words)
    # quote_bad_chars() only quoted literal parentheses; ordinary words such as
    # ``test`` were left untouched. Then one trailing wildcard was appended.
    value = value.replace('(', '"("').replace(')', '")"')
    return value + '*'


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

    print('\nREFERENCE COUNTS')
    for query in ('test*', '"test"*', 'test', 'test AND test*'):
        try:
            results = catalog(moj=query, portal_type='imipreiskava')
            print('%r -> %d' % (query, len(results)))
        except Exception as exc:
            print('%r -> ERROR %r' % (query, exc))

    q = 'test'
    transformed = legacy_query(q)
    try:
        results = catalog(moj=transformed, portal_type='imipreiskava')
        print('\nlegacy q=%r transformed query %r -> %d' %
              (q, transformed, len(results)))
        print('First 20 titles:')
        for brain in results[:20]:
            print('  - %s' % brain.Title)
    except Exception as exc:
        print('legacy q=test query failed: %r' % exc)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 4.3 buildout.')
run(app)
