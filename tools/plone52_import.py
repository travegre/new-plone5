#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-pass importer for the streaming Plone 4.3 export.

This pass imports standard content and custom Dexterity content.  PFG/EasyForm
conversion is intentionally separate and reads `pfg.jsonl` in a later pass.

Run inside the Plone 5.2 target container::

    bin/instance run tools/plone52_import.py --input-dir=/migration-data/export
"""
import json
import os
import sys

import plone.api
from plone.app.textfield.value import RichTextValue
from plone.namedfile.file import NamedBlobFile

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
    'Document': 'Document',
    'Folder': 'Folder',
    'File': 'File',
    'Image': 'Image',
    'Link': 'Link',
    'News Item': 'News Item',
    'Event': 'Event',
    'Topic': 'Collection',
}

SKIP_TYPES = {
    'uvoz',
    'FormFolder', 'FormMailerAdapter', 'FormSelectionField',
    'FormStringField', 'FormTextField', 'FormThanksPage',
}

RICH_FIELDS = {
    'sklop', 'sinonim', 'metode', 'opis', 'opombe', 'trajanje', 'urnik',
    'stalni_tekst',
}

BASIC_SOURCE_FIELDS = {
    'id', 'title', 'description', 'allowDiscussion', 'subject', 'relatedItems',
    'location', 'language', 'effectiveDate', 'expirationDate', 'creators',
    'contributors', 'rights', 'excludeFromNav',
}


def parse_input_dir(argv):
    values = list(argv)
    script_pos = max(i for i, v in enumerate(values)
                     if os.path.basename(v) == 'plone52_import.py')
    args = values[script_pos + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        return args[0].split('=', 1)[1]
    if len(args) == 2 and args[0] == '--input-dir':
        return args[1]
    raise SystemExit('Use --input-dir=/migration-data/export')


def field_map(record):
    return {item['name']: item for item in record.get('fields', [])
            if item.get('name')}


def source_relative_path(record):
    source = record['source_path'].strip('/')
    site = record['site']
    if source == site:
        return ''
    prefix = site + '/'
    return source[len(prefix):] if source.startswith(prefix) else source


def target_type(record):
    site = record['site']
    source_type = record.get('portal_type')

    # Legacy staff entries are ordinary Folder objects below the special
    # seznam_zaposlenih container. Convert them to real employee records.
    rel = source_relative_path(record)
    if site in ('dezurstva', 'nadomescanja') and '/seznam_zaposlenih/' in ('/' + rel + '/'):
        if source_type == 'Folder' and not rel.endswith('/seznam_zaposlenih'):
            return 'imi.staff.employee'

    if (site, source_type) in CUSTOM_TYPE_MAP:
        return CUSTOM_TYPE_MAP[(site, source_type)]
    return STANDARD_TYPE_MAP.get(source_type)


def target_parent(site, record, path_map):
    rel = source_relative_path(record)
    parent_rel = os.path.dirname(rel).replace('\\', '/')
    if not parent_rel:
        return site
    key = (record['site'], parent_rel)
    if key not in path_map:
        raise KeyError('parent not imported: %r for %s' % (key, rel))
    return path_map[key]


def convert_rich(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = '\n'.join(str(x) for x in value)
    return RichTextValue(
        raw=str(value),
        mimeType='text/html',
        outputMimeType='text/x-html-safe',
    )


def binary_value(input_dir, binary_info):
    if not binary_info:
        return None
    filename = binary_info.get('filename') or 'legacy-file'
    path = os.path.join(input_dir, 'binaries', binary_info['path'])
    with open(path, 'rb') as handle:
        data = handle.read()
    return NamedBlobFile(data=data, filename=str(filename))


def parse_employee(record):
    """Parse the legacy staff Folder convention title + contact|email."""
    description = record.get('description') or ''
    contact, email = description, ''
    if '|' in description:
        contact, email = description.split('|', 1)
    return {
        'source_employee_id': str(record.get('id') or ''),
        'contact': contact,
        'email': '' if email == '-' else email,
    }


def apply_custom_fields(obj, record, input_dir):
    fields = field_map(record)
    target_pt = obj.portal_type

    if target_pt == 'imi.staff.employee':
        for key, value in parse_employee(record).items():
            setattr(obj, key, value)
        return

    for name, item in fields.items():
        if name in BASIC_SOURCE_FIELDS or name in ('id', 'title', 'description'):
            continue
        if not hasattr(obj, name):
            continue
        if 'binary' in item:
            value = binary_value(input_dir, item.get('binary'))
        else:
            value = item.get('value')
        if name in RICH_FIELDS:
            value = convert_rich(value)
        elif isinstance(getattr(obj, name, None), tuple) and isinstance(value, list):
            value = tuple(str(v) for v in value)
        try:
            setattr(obj, name, value)
        except (TypeError, ValueError):
            # Tuple fields are common in migrated Archetypes LinesFields.
            if isinstance(value, list):
                setattr(obj, name, tuple(str(v) for v in value))
            else:
                raise


def apply_local_roles(obj, metadata):
    roles = metadata.get('local_roles') or []
    for principal, principal_roles in roles:
        try:
            obj.manage_setLocalRoles(str(principal), tuple(principal_roles))
        except Exception:
            pass
    if metadata.get('local_role_block'):
        method = getattr(obj, 'blockLocalRoles', None)
        if callable(method):
            try:
                method()
            except Exception:
                pass


def transition_to_state(obj, state):
    if not state:
        return
    try:
        current = plone.api.content.get_state(obj=obj)
    except Exception:
        return
    if current == state:
        return
    workflow = plone.api.portal.get_tool('portal_workflow')
    chain = workflow.getChainFor(obj)
    if not chain:
        return
    wf = workflow.getWorkflowById(chain[0])
    # Use a direct state assignment only in this controlled migration context;
    # legacy transition graphs may not provide a valid path from initial state.
    try:
        status = workflow.getStatusOf(chain[0], obj) or {}
        status = dict(status)
        status['review_state'] = state
        workflow.setStatusOf(chain[0], obj, status)
        obj.reindexObject(idxs=['review_state'])
    except Exception:
        pass


def create_record(app, record, input_dir, path_map):
    site = app[record['site']]
    rel = source_relative_path(record)
    if not rel:
        return site

    source_type = record.get('portal_type')
    if source_type in SKIP_TYPES or source_type.startswith('Form'):
        return None
    pt = target_type(record)
    if not pt:
        return None

    parent = target_parent(site, record, path_map)
    obj_id = str(record.get('id') or rel.rsplit('/', 1)[-1])
    if obj_id in parent.objectIds():
        obj = parent[obj_id]
    else:
        obj = plone.api.content.create(
            container=parent,
            type=pt,
            id=obj_id,
            title=record.get('title') or obj_id,
            description=record.get('description') or '',
            safe_id=False,
        )

    apply_custom_fields(obj, record, input_dir)
    apply_local_roles(obj, record.get('metadata') or {})
    try:
        if record.get('metadata', {}).get('exclude_from_nav') is not None:
            obj.exclude_from_nav = bool(record['metadata']['exclude_from_nav'])
    except Exception:
        pass
    obj.reindexObject()
    path_map[(record['site'], rel)] = obj
    return obj


def run(app, input_dir):
    objects_file = os.path.join(input_dir, 'objects.jsonl')
    if not os.path.isfile(objects_file):
        raise SystemExit('Missing %s' % objects_file)

    path_map = {}
    states = []
    created = 0
    skipped = 0
    errors = []

    with open(objects_file, 'r', encoding='utf-8') as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            try:
                obj = create_record(app, record, input_dir, path_map)
                if obj is None:
                    skipped += 1
                    continue
                created += 1
                states.append((obj, (record.get('metadata') or {}).get('workflow_state')))
            except Exception as exc:
                errors.append({
                    'line': lineno,
                    'site': record.get('site'),
                    'source_path': record.get('source_path'),
                    'portal_type': record.get('portal_type'),
                    'error': repr(exc),
                })

    for obj, state in states:
        transition_to_state(obj, state)

    import transaction
    transaction.commit()

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, 'plone52-import-errors.json'), 'w',
              encoding='utf-8') as handle:
        json.dump(errors, handle, ensure_ascii=False, indent=2, sort_keys=True)

    print('Imported/visited: %d' % created)
    print('Skipped: %d' % skipped)
    print('Errors: %d' % len(errors))
    if errors:
        print('See reports/plone52-import-errors.json')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
