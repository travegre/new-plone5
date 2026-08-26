#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only streaming exporter for the IMI Plone 4.3 migration.

Run inside the stopped Plone 4.3 buildout::

    bin/instance run src/plone43_export.py --output-dir=/plone/instance/src/export

The exporter uses each site's catalog as the authoritative *active* content
set.  It never modifies the ZODB.  Objects are written one-per-line to JSONL;
binary field payloads are written separately.
"""
from __future__ import print_function

import hashlib
import json
import os
import sys
import traceback

try:
    unicode_type = unicode
except NameError:  # pragma: no cover - Python 3 static import only
    unicode_type = str

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
SCRIPT_BASENAMES = ('plone43_export.py',)
PFG_TYPES = (
    'FormFolder', 'FormMailerAdapter', 'FormSelectionField',
    'FormStringField', 'FormTextField', 'FormThanksPage',
)


def to_unicode(value):
    if value is None:
        return None
    if isinstance(value, unicode_type):
        return value
    if isinstance(value, str):
        return value.decode('utf-8')
    try:
        return unicode_type(value)
    except Exception:
        return unicode_type(repr(value), 'utf-8', 'replace')


def normalize_json(value):
    if isinstance(value, unicode_type):
        return value
    if isinstance(value, str):
        return value.decode('utf-8')
    if isinstance(value, dict):
        return dict((normalize_json(k), normalize_json(v))
                    for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return [normalize_json(v) for v in value]
    if value is None or isinstance(value, (bool, int, long, float)):
        return value
    # Zope DateTime and other small scalar-ish objects.
    for attr in ('ISO8601', 'ISO'):
        method = getattr(value, attr, None)
        if callable(method):
            try:
                return to_unicode(method())
            except Exception:
                pass
    return to_unicode(value)


def json_line(value):
    normalized = normalize_json(value)
    rendered = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    if isinstance(rendered, unicode_type):
        rendered = rendered.encode('utf-8')
    return rendered + b'\n'


def parse_output_dir(argv):
    argv = list(argv)
    positions = []
    for i, value in enumerate(argv):
        try:
            if os.path.basename(value) in SCRIPT_BASENAMES:
                positions.append(i)
        except Exception:
            pass
    if not positions:
        raise SystemExit('Unexpected Plone/Zope argv: %r' % argv)
    args = argv[positions[-1] + 1:]
    if len(args) == 1 and args[0].startswith('--output-dir='):
        outdir = args[0].split('=', 1)[1]
    elif len(args) == 2 and args[0] == '--output-dir':
        outdir = args[1]
    else:
        raise SystemExit(
            'Usage: bin/instance run src/plone43_export.py '
            '--output-dir=/path/to/export'
        )
    if not outdir:
        raise SystemExit('--output-dir may not be empty')
    return outdir


def object_path(obj):
    try:
        return to_unicode(obj.absolute_url_path())
    except Exception:
        return None


def portal_type(obj):
    try:
        return to_unicode(obj.getPortalTypeName())
    except Exception:
        return to_unicode(getattr(obj, 'portal_type', None))


def safe_call(obj, name, default=None):
    method = getattr(obj, name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:
        return default


def metadata(obj, site):
    workflow = getattr(site, 'portal_workflow', None)
    state = None
    if workflow is not None:
        try:
            state = workflow.getInfoFor(obj, 'review_state', None)
        except Exception:
            pass

    local_roles = []
    method = getattr(obj, 'get_local_roles', None)
    if callable(method):
        try:
            local_roles = list(method() or ())
        except Exception:
            pass

    blocked = None
    method = getattr(obj, 'get_local_role_block', None)
    if callable(method):
        try:
            blocked = bool(method())
        except Exception:
            pass

    uid = safe_call(obj, 'UID')
    creators = safe_call(obj, 'Creators', ()) or ()

    return {
        'uid': uid,
        'creators': list(creators),
        'created': getattr(obj, 'creation_date', None),
        'modified': getattr(obj, 'modification_date', None),
        'effective': safe_call(obj, 'effective'),
        'expires': safe_call(obj, 'expires'),
        'workflow_state': state,
        'local_roles': local_roles,
        'local_role_block': blocked,
        'exclude_from_nav': safe_call(obj, 'getExcludeFromNav'),
    }


def read_pdata(value):
    """Best-effort extraction of Archetypes File/Image payload bytes."""
    if value is None:
        return None

    # Blob based values.
    blob = getattr(value, '_blob', None)
    if blob is None:
        getter = getattr(value, 'getBlob', None)
        if callable(getter):
            try:
                blob = getter()
            except Exception:
                blob = None
    if blob is not None:
        try:
            handle = blob.open('r')
            try:
                return handle.read()
            finally:
                handle.close()
        except Exception:
            pass

    data = getattr(value, 'data', None)
    if data is None:
        try:
            return str(value)
        except Exception:
            return None
    if isinstance(data, unicode_type):
        return data.encode('utf-8')
    if isinstance(data, str):
        return data

    # OFS.Image.Pdata chain.
    chunks = []
    current = data
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chunk = getattr(current, 'data', current)
        if isinstance(chunk, unicode_type):
            chunk = chunk.encode('utf-8')
        if isinstance(chunk, str):
            chunks.append(chunk)
        current = getattr(current, 'next', None)
    if chunks:
        return ''.join(chunks)
    return None


def field_export(obj, field, binary_dir, site_name, errors):
    try:
        name = field.getName()
    except Exception:
        return None
    field_type = field.__class__.__name__
    item = {
        'name': name,
        'field_type': field_type,
        'required': bool(getattr(field, 'required', False)),
        'multivalued': bool(getattr(field, 'multiValued', False)),
        'searchable': bool(getattr(field, 'searchable', False)),
    }
    try:
        raw = field.getRaw(obj)
    except Exception:
        try:
            raw = field.get(obj)
        except Exception as exc:
            errors.append({
                'site': site_name, 'path': object_path(obj), 'field': name,
                'operation': 'field.get', 'error': repr(exc),
            })
            item['value_error'] = repr(exc)
            return item

    if field_type in ('FileField', 'ImageField'):
        payload = read_pdata(raw)
        if payload is not None:
            digest = hashlib.sha256(payload).hexdigest()
            relpath = os.path.join(site_name, digest[:2], digest)
            path = os.path.join(binary_dir, relpath)
            parent = os.path.dirname(path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            if not os.path.exists(path):
                with open(path, 'wb') as handle:
                    handle.write(payload)
            item['binary'] = {
                'path': relpath.replace(os.sep, '/'),
                'sha256': digest,
                'size': len(payload),
                'filename': getattr(raw, 'filename', None),
            }
            try:
                item['binary']['content_type'] = field.getContentType(obj)
            except Exception:
                pass
        else:
            item['binary'] = None
    else:
        item['value'] = raw
    return item


def export_object(obj, site, site_name, binary_dir, errors):
    record = {
        'site': site_name,
        'source_path': object_path(obj),
        'id': safe_call(obj, 'getId', getattr(obj, 'id', None)),
        'portal_type': portal_type(obj),
        'class': '%s.%s' % (obj.__class__.__module__, obj.__class__.__name__),
        'title': safe_call(obj, 'Title', getattr(obj, 'title', None)),
        'description': safe_call(obj, 'Description', getattr(obj, 'description', None)),
        'metadata': metadata(obj, site),
        'fields': [],
    }

    schema_method = getattr(obj, 'Schema', None)
    if callable(schema_method):
        try:
            fields = schema_method().fields()
        except Exception as exc:
            errors.append({
                'site': site_name, 'path': object_path(obj),
                'operation': 'Schema', 'error': repr(exc),
            })
            fields = []
        for field in fields:
            item = field_export(obj, field, binary_dir, site_name, errors)
            if item is not None:
                record['fields'].append(item)

    return record


def catalog_objects(site, errors, site_name):
    catalog = site.portal_catalog
    brains = list(catalog.unrestrictedSearchResults())
    # Parent paths first makes the target importer deterministic.
    brains.sort(key=lambda brain: (len(brain.getPath().split('/')), brain.getPath()))
    seen = set()
    for brain in brains:
        path = brain.getPath()
        if path in seen:
            continue
        seen.add(path)
        try:
            obj = brain.getObject()
        except Exception as exc:
            errors.append({
                'site': site_name, 'path': path,
                'operation': 'catalog.getObject', 'error': repr(exc),
            })
            continue
        yield obj


def run(app, outdir):
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    binary_dir = os.path.join(outdir, 'binaries')
    report_dir = os.path.join(outdir, 'reports')
    for path in (binary_dir, report_dir):
        if not os.path.isdir(path):
            os.makedirs(path)

    object_pathname = os.path.join(outdir, 'objects.jsonl')
    pfg_pathname = os.path.join(outdir, 'pfg.jsonl')
    errors = []
    counts = {}

    with open(object_pathname, 'wb') as objects_handle, \
            open(pfg_pathname, 'wb') as pfg_handle:
        for site_name in SITES:
            site = app.unrestrictedTraverse(site_name)
            site_counts = {}
            for obj in catalog_objects(site, errors, site_name):
                record = export_object(obj, site, site_name, binary_dir, errors)
                pt = record.get('portal_type') or '<none>'
                site_counts[pt] = site_counts.get(pt, 0) + 1
                if pt in PFG_TYPES or pt.startswith('Form'):
                    pfg_handle.write(json_line(record))
                else:
                    objects_handle.write(json_line(record))
            counts[site_name] = site_counts

    manifest = {
        'schema_version': 1,
        'read_only_source': True,
        'sites': list(SITES),
        'selection': 'portal_catalog active/cataloged objects',
        'counts_by_site_and_type': counts,
        'objects_file': 'objects.jsonl',
        'pfg_file': 'pfg.jsonl',
        'binary_dir': 'binaries',
        'error_count': len(errors),
    }
    with open(os.path.join(outdir, 'manifest.json'), 'wb') as handle:
        handle.write(json_line(manifest))
    with open(os.path.join(report_dir, 'errors.json'), 'wb') as handle:
        rendered = json.dumps(normalize_json(errors), ensure_ascii=False, indent=2,
                              sort_keys=True)
        if isinstance(rendered, unicode_type):
            rendered = rendered.encode('utf-8')
        handle.write(rendered)

    print('Migration export written to %s' % os.path.abspath(outdir))
    print('Objects: %s' % object_pathname)
    print('PFG: %s' % pfg_pathname)
    print('Errors: %d' % len(errors))


if 'app' not in globals():
    raise SystemExit('Use bin/instance run inside the Plone 4.3 buildout.')
run(app, parse_output_dir(sys.argv))
