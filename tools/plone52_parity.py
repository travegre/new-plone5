#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parity checker for the IMI Plone 4.3 -> 5.2 migration.

Run inside the Plone 5.2 target after import::

    bin/instance run tools/plone52_parity.py --input-dir=/migration-data/export

The checker is read-only. It compares the source export manifest/JSONL with
objects currently present in the five target Plone sites and writes a machine-
readable parity report to ``reports/plone52-parity.json``.
"""
import hashlib
import json
import os
import sys
from collections import Counter

from plone.dexterity.utils import iterSchemata
from Products.CMFCore.utils import getToolByName
from zope.component.hooks import setSite
from zope.schema import getFields

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
SCRIPT_BASENAME = 'plone52_parity.py'

CUSTOM_TYPE_MAP = {
    ('portal', 'produkti'): 'imi.directory.person',
    ('dezurstva', 'dezurstvo'): 'imi.duty.roster_day',
    ('dezurstva', 'seznam_zaposlenih'): 'imi.staff.directory',
    ('kiestra', 'dezurstvo'): 'imi.kiestra.work_day',
    ('preiskave', 'imipreiskava'): 'imi.exams.examination',
    ('nadomescanja', 'dezurstvo'): 'imi.replacements.day',
    ('nadomescanja', 'laboratorij'): 'imi.replacements.laboratory',
}
STANDARD_TYPE_MAP = {
    'Document': 'Document', 'Folder': 'Folder', 'File': 'File',
    'Image': 'Image', 'Link': 'Link', 'News Item': 'News Item',
    'Event': 'Event', 'Topic': 'Collection',
}
SKIP_TYPES = {
    'uvoz', 'imiuvozipreiskavo', 'FormFolder', 'FormMailerAdapter',
    'FormSelectionField', 'FormStringField', 'FormTextField', 'FormThanksPage',
}
BASIC_SOURCE_FIELDS = {
    'id', 'title', 'description', 'allowDiscussion', 'subject', 'relatedItems',
    'location', 'language', 'effectiveDate', 'expirationDate', 'creators',
    'contributors', 'rights', 'excludeFromNav',
}

LEGACY_IMPLEMENTATION_FIELDS = {
    'creation_date', 'modification_date', 'constrainTypesMode',
    'locallyAllowedTypes', 'immediatelyAddableTypes', 'nextPreviousEnabled',
    'presentation', 'tableContents',
}


def parse_input_dir(argv):
    values = list(argv)
    positions = [i for i, value in enumerate(values)
                 if os.path.basename(value) == SCRIPT_BASENAME]
    if not positions:
        raise SystemExit('Unexpected instance-run argv: %r' % values)
    args = values[positions[-1] + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        result = args[0].split('=', 1)[1]
    elif len(args) == 2 and args[0] == '--input-dir':
        result = args[1]
    else:
        raise SystemExit('Use --input-dir=/migration-data/export')
    if not result:
        raise SystemExit('--input-dir may not be empty')
    return os.path.abspath(result)


def load_jsonl(path):
    with open(path, 'r', encoding='utf-8') as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                yield lineno, json.loads(line)
            except Exception as exc:
                yield lineno, {'__parse_error__': repr(exc), '__raw__': line[:500]}


def source_relative_path(record):
    source = (record.get('source_path') or '').strip('/')
    site = record.get('site') or record.get('source_site')
    if source == site:
        return ''
    prefix = site + '/'
    return source[len(prefix):] if source.startswith(prefix) else source


def target_type(record):
    site = record.get('site') or record.get('source_site')
    source_type = record.get('portal_type')
    rel = source_relative_path(record)
    if site in ('dezurstva', 'nadomescanja') and \
            '/seznam_zaposlenih/' in ('/' + rel + '/'):
        if source_type == 'Folder' and not rel.endswith('/seznam_zaposlenih'):
            return 'imi.staff.employee'
    if (site, source_type) in CUSTOM_TYPE_MAP:
        return CUSTOM_TYPE_MAP[(site, source_type)]
    return STANDARD_TYPE_MAP.get(source_type)


def source_field_map(record):
    return {item.get('name'): item for item in record.get('fields', [])
            if item.get('name')}


def normalize(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace')
    if isinstance(value, (list, tuple, set)):
        return [normalize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw)
    filename = getattr(value, 'filename', None)
    data = getattr(value, 'data', None)
    if filename is not None and data is not None:
        return {'filename': str(filename), 'size': len(data)}
    return str(value)


def stable_hash(value):
    payload = json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def target_field_names(obj):
    result = set()
    for iface in iterSchemata(obj):
        result.update(getFields(iface).keys())
    return result


def source_value_for_target(item):
    value = item.get('value')
    if item.get('field_type') == 'LinesField':
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(v) for v in value]
        return [str(value)]
    return value


def comparable_source_hashes(record, target_names):
    result = {}
    for name, item in source_field_map(record).items():
        if name in BASIC_SOURCE_FIELDS or name in ('id', 'title', 'description'):
            continue
        if name in LEGACY_IMPLEMENTATION_FIELDS:
            continue
        if name not in target_names:
            continue
        if 'binary' in item:
            continue
        result[name] = stable_hash(source_value_for_target(item))
    return result


def target_custom_field_hashes(obj, source_hashes):
    result = {}
    for name in source_hashes:
        try:
            result[name] = stable_hash(getattr(obj, name, None))
        except Exception:
            result[name] = '<unreadable>'
    return result


def target_binary_hash(value):
    if value is None:
        return None
    data = getattr(value, 'data', None)
    if data is None:
        return None
    if not isinstance(data, bytes):
        data = bytes(data)
    return hashlib.sha256(data).hexdigest()


def find_target(app, record):
    site_name = record.get('site') or record.get('source_site')
    if site_name not in app:
        return None
    site = app[site_name]
    setSite(site)
    current = site
    rel = source_relative_path(record)
    if not rel:
        return current
    for part in [x for x in rel.split('/') if x]:
        if part not in current:
            return None
        current = current[part]
    return current


def current_state(obj):
    try:
        tool = getToolByName(obj, 'portal_workflow')
        return tool.getInfoFor(obj, 'review_state', None)
    except Exception:
        return None


def local_roles(obj):
    method = getattr(obj, 'get_local_roles', None)
    if not callable(method):
        return []
    try:
        return sorted((str(principal), sorted(list(roles)))
                      for principal, roles in method() or ())
    except Exception:
        return []


def source_local_roles(record):
    metadata = record.get('metadata') or {}
    value = metadata.get('local_roles') or record.get('local_roles') or []
    if isinstance(value, dict):
        value = value.get('roles') or value
        if isinstance(value, dict):
            value = list(value.items())
    return sorted((str(principal), sorted(list(roles)))
                  for principal, roles in value)


def check_record(app, record, input_dir):
    source_type = record.get('portal_type')
    expected_type = target_type(record)
    result = {
        'site': record.get('site') or record.get('source_site'),
        'source_path': record.get('source_path'),
        'source_type': source_type,
        'expected_target_type': expected_type,
        'status': 'ok',
        'differences': [],
    }
    if source_type in SKIP_TYPES or (source_type or '').startswith('Form'):
        result['status'] = 'skipped-by-policy'
        return result
    if expected_type is None:
        result['status'] = 'unmapped-type'
        result['differences'].append('no target type mapping')
        return result

    obj = find_target(app, record)
    if obj is None:
        result['status'] = 'missing'
        result['differences'].append('target object not found at source-relative path')
        return result

    if getattr(obj, 'portal_type', None) != expected_type:
        result['differences'].append(
            'portal_type: expected %r got %r' %
            (expected_type, getattr(obj, 'portal_type', None)))

    try:
        target_names = target_field_names(obj)
    except Exception as exc:
        target_names = set()
        result['differences'].append('target schema unreadable: %r' % exc)

    source_hashes = comparable_source_hashes(record, target_names)
    target_hashes = target_custom_field_hashes(obj, source_hashes)
    field_diffs = {}
    for name, source_hash in source_hashes.items():
        target_hash = target_hashes.get(name)
        if target_hash != source_hash:
            field_diffs[name] = {'source': source_hash, 'target': target_hash}
    if field_diffs:
        result['field_hash_differences'] = field_diffs
        result['differences'].append('%d custom field hash differences' % len(field_diffs))

    binaries = []
    for item in record.get('fields', []):
        info = item.get('binary')
        if not info:
            continue
        name = item.get('name')
        if name not in target_names:
            continue
        try:
            target_hash = target_binary_hash(getattr(obj, name, None))
        except Exception:
            target_hash = None
        binaries.append({
            'field': name,
            'source_sha256': info.get('sha256'),
            'target_sha256': target_hash,
            'match': target_hash == info.get('sha256'),
        })
    bad_binaries = [item for item in binaries if not item['match']]
    if bad_binaries:
        result['binary_differences'] = bad_binaries
        result['differences'].append('%d binary hash differences' % len(bad_binaries))

    metadata = record.get('metadata') or {}
    source_state = metadata.get('workflow_state')
    target_state = current_state(obj)
    if source_state and source_state != target_state:
        result['workflow'] = {'source': source_state, 'target': target_state}
        result['differences'].append('workflow state differs')

    src_roles = source_local_roles(record)
    tgt_roles = local_roles(obj)
    if src_roles != tgt_roles:
        result['local_roles'] = {'source': src_roles, 'target': tgt_roles}
        result['differences'].append('local roles differ')

    if result['differences']:
        result['status'] = 'different'
    return result


def run(app, input_dir):
    objects_path = os.path.join(input_dir, 'objects.jsonl')
    pfg_path = os.path.join(input_dir, 'pfg.jsonl')
    if not os.path.isfile(objects_path):
        raise SystemExit('Missing %s' % objects_path)

    results = []
    parse_errors = []
    source_counts = Counter()
    target_expected_counts = Counter()
    status_counts = Counter()

    for lineno, record in load_jsonl(objects_path):
        if '__parse_error__' in record:
            parse_errors.append({'line': lineno, **record})
            continue
        site = record.get('site') or record.get('source_site')
        source_counts[(site, record.get('portal_type'))] += 1
        expected = target_type(record)
        if expected:
            target_expected_counts[(site, expected)] += 1
        result = check_record(app, record, input_dir)
        status_counts[result['status']] += 1
        if result['status'] != 'ok':
            results.append(result)

    pfg_source_counts = Counter()
    if os.path.isfile(pfg_path):
        for lineno, record in load_jsonl(pfg_path):
            if '__parse_error__' in record:
                parse_errors.append({'file': 'pfg.jsonl', 'line': lineno, **record})
                continue
            site = record.get('site') or record.get('source_site')
            pfg_source_counts[site] += 1

    easyform_counts = Counter()
    for site_name in SITES:
        if site_name not in app:
            continue
        try:
            setSite(app[site_name])
            brains = app[site_name].portal_catalog(portal_type='EasyForm')
            easyform_counts[site_name] = len(brains)
        except Exception:
            easyform_counts[site_name] = 0

    report = {
        'schema_version': 2,
        'input_dir': input_dir,
        'status_counts': dict(status_counts),
        'parse_errors': parse_errors,
        'differences': results,
        'source_counts_by_site_type': {
            '%s|%s' % key: value for key, value in sorted(source_counts.items())
        },
        'expected_target_counts_by_site_type': {
            '%s|%s' % key: value for key, value in sorted(target_expected_counts.items())
        },
        'pfg_source_counts': dict(pfg_source_counts),
        'easyform_target_counts': dict(easyform_counts),
        'pfg_easyform_count_match': {
            site: pfg_source_counts.get(site, 0) == easyform_counts.get(site, 0)
            for site in SITES
        },
    }

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    output = os.path.join(report_dir, 'plone52-parity.json')
    with open(output, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('Parity report: %s' % output)
    print('Statuses: %r' % dict(status_counts))
    print('Differences written: %d' % len(results))
    print('Parse errors: %d' % len(parse_errors))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
