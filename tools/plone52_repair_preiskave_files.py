#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore real legacy Preiskave FileField payloads on an imported site.

This is a narrow repair pass for the ``datoteka`` field of legacy
``imipreiskava`` records. Empty Archetypes FileField placeholders are ignored:
the old detail template displayed "Dodatna dokumentacija" only when
``getFilename('datoteka')`` was non-empty, so a zero-byte value with an empty
filename is not user-visible legacy content and must not be manufactured in
Plone 5.2.

Run inside the Plone 5.2 instance::

    bin/instance run tools/plone52_repair_preiskave_files.py \
        --input-dir=/migration-data/export
"""
import json
import os
import sys

from plone.namedfile.file import NamedBlobFile
from zope.component.hooks import setSite


SCRIPT = 'plone52_repair_preiskave_files.py'


def parse_input_dir(argv):
    values = list(argv)
    positions = [i for i, value in enumerate(values)
                 if os.path.basename(value) == SCRIPT]
    if not positions:
        raise SystemExit('Run with bin/instance run inside Plone 5.2.')
    args = values[positions[-1] + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        result = args[0].split('=', 1)[1]
    elif len(args) == 2 and args[0] == '--input-dir':
        result = args[1]
    else:
        raise SystemExit('Use --input-dir=/migration-data/export')
    return os.path.abspath(result)


def field_map(record):
    return {item.get('name'): item for item in record.get('fields', [])
            if item.get('name')}


def target_for_record(site, source_path):
    """Traverse the source-relative path in the migrated Plone site."""
    bits = [part for part in str(source_path or '').strip('/').split('/') if part]
    if bits and bits[0] == 'preiskave':
        bits = bits[1:]
    current = site
    for part in bits:
        current = current.get(part) if current is not None else None
        if current is None:
            return None
    return current


def binary_path(input_dir, info):
    rel = str(info.get('path') or '').replace('/', os.sep)
    return os.path.join(input_dir, 'binaries', rel)


def real_binary(info):
    """Match the legacy template's visibility rule, not exporter placeholders."""
    if not info:
        return False
    try:
        size = int(info.get('size') or 0)
    except (TypeError, ValueError):
        size = 0
    filename = str(info.get('filename') or '').strip()
    return size > 0 and bool(filename)


def has_payload(value):
    if value is None:
        return False
    try:
        return bool(value.data)
    except Exception:
        pass
    try:
        return bool(value.getSize())
    except Exception:
        pass
    return True


def repair(app, input_dir):
    objects_path = os.path.join(input_dir, 'objects.jsonl')
    if not os.path.isfile(objects_path):
        raise SystemExit('Missing %s' % objects_path)
    if not os.path.isdir(os.path.join(input_dir, 'binaries')):
        raise SystemExit('Missing %s' % os.path.join(input_dir, 'binaries'))

    site = app['preiskave']
    setSite(site)
    examined = real_source_files = repaired = already_present = 0
    empty_placeholders = missing_target = missing_binary = 0
    failures = []

    with open(objects_path, 'r', encoding='utf-8') as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get('site') != 'preiskave' or record.get('portal_type') != 'imipreiskava':
                continue
            examined += 1
            item = field_map(record).get('datoteka')
            info = item and item.get('binary')
            if not info:
                continue
            if not real_binary(info):
                empty_placeholders += 1
                continue
            real_source_files += 1
            obj = target_for_record(site, record.get('source_path'))
            if obj is None:
                missing_target += 1
                failures.append((lineno, record.get('source_path'), 'target missing'))
                continue
            if has_payload(getattr(obj, 'datoteka', None)):
                already_present += 1
                continue
            path = binary_path(input_dir, info)
            if not os.path.isfile(path):
                missing_binary += 1
                failures.append((lineno, record.get('source_path'), 'binary missing: %s' % path))
                continue
            try:
                with open(path, 'rb') as binary:
                    data = binary.read()
                if not data:
                    empty_placeholders += 1
                    continue
                kwargs = {
                    'data': data,
                    'filename': str(info['filename']),
                }
                content_type = info.get('content_type') or None
                if content_type:
                    kwargs['contentType'] = str(content_type)
                obj.datoteka = NamedBlobFile(**kwargs)
                obj.reindexObject()
                repaired += 1
            except Exception as exc:
                failures.append((lineno, record.get('source_path'), repr(exc)))

    import transaction
    transaction.commit()
    print('Preiskave examinations inspected: %d' % examined)
    print('Empty datoteka placeholders ignored: %d' % empty_placeholders)
    print('Real source documents: %d' % real_source_files)
    print('Already present in Plone 5.2: %d' % already_present)
    print('Repaired: %d' % repaired)
    print('Missing target objects: %d' % missing_target)
    print('Missing binary files: %d' % missing_binary)
    print('Other failures: %d' % max(0, len(failures) - missing_target - missing_binary))
    for lineno, path, message in failures[:50]:
        print('  line %d %s: %s' % (lineno, path, message))
    if len(failures) > 50:
        print('  ... %d more failures' % (len(failures) - 50))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
repair(app, parse_input_dir(sys.argv))
