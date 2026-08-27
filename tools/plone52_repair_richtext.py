#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Repair plain-string values stored in Dexterity RichText fields.

Reads the original Plone 4.3 objects.jsonl export and rewrites only target
fields whose Dexterity schema says they are RichText but whose current value is
not a RichTextValue. This repairs already-imported sites without a full reimport.

Run with::

    bin/instance run tools/plone52_repair_richtext.py \
        --input-dir=/migration-data/export
"""
import json
import os
import sys

from plone.app.textfield import RichText
from plone.app.textfield.value import RichTextValue
from plone.dexterity.utils import iterSchemata
from zope.component.hooks import setSite
from zope.schema import getFields

COMMIT_EVERY = 250


def parse_input_dir(argv):
    values = list(argv)
    script_pos = max(i for i, v in enumerate(values)
                     if os.path.basename(v) == 'plone52_repair_richtext.py')
    args = values[script_pos + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        return args[0].split('=', 1)[1]
    if len(args) == 2 and args[0] == '--input-dir':
        return args[1]
    raise SystemExit('Use --input-dir=/migration-data/export')


def convert_rich(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = '\n'.join(str(x) for x in value)
    return RichTextValue(raw=str(value), mimeType='text/html',
                         outputMimeType='text/x-html-safe')


def field_map(record):
    return {item['name']: item for item in record.get('fields', [])
            if item.get('name')}


def traverse_target(app, record):
    source_path = (record.get('source_path') or '').strip('/')
    if not source_path:
        return None
    parts = source_path.split('/')
    site_id = parts[0]
    if site_id not in app.objectIds():
        return None
    site = app[site_id]
    setSite(site)
    obj = site
    for part in parts[1:]:
        if part not in obj.objectIds():
            return None
        obj = obj[part]
    return obj


def dexterity_fields(obj):
    result = {}
    for iface in iterSchemata(obj):
        result.update(getFields(iface))
    return result


def run(app, input_dir):
    import transaction

    objects_file = os.path.join(input_dir, 'objects.jsonl')
    if not os.path.isfile(objects_file):
        raise SystemExit('Missing %s' % objects_file)

    processed = repaired = already_ok = missing = errors = 0

    with open(objects_file, 'r', encoding='utf-8') as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            processed += 1
            try:
                obj = traverse_target(app, record)
                if obj is None:
                    missing += 1
                    continue
                target_fields = dexterity_fields(obj)
                source_fields = field_map(record)
                changed = False
                for name, target_field in target_fields.items():
                    if not isinstance(target_field, RichText):
                        continue
                    item = source_fields.get(name)
                    if item is None:
                        continue
                    current = getattr(obj, name, None)
                    if current is None or isinstance(current, RichTextValue):
                        already_ok += 1
                        continue
                    setattr(obj, name, convert_rich(item.get('value')))
                    repaired += 1
                    changed = True
                if changed:
                    obj.reindexObject()
            except Exception as exc:
                errors += 1
                print('ERROR line %d %s: %r' %
                      (lineno, record.get('source_path'), exc), flush=True)

            if processed % COMMIT_EVERY == 0:
                transaction.commit()
                print('Progress: %d processed, %d repaired, %d missing, %d errors' %
                      (processed, repaired, missing, errors), flush=True)

    transaction.commit()
    setSite(None)
    print('Processed: %d' % processed)
    print('RichText fields repaired: %d' % repaired)
    print('RichText fields already OK: %d' % already_ok)
    print('Missing/skipped targets: %d' % missing)
    print('Errors: %d' % errors)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
