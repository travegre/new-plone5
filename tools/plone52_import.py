#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-pass importer for the streaming Plone 4.3 export.

This pass imports standard content and custom Dexterity content. PFG/EasyForm
conversion is intentionally separate and reads `pfg.jsonl` in a later pass.
"""
import json
import os
import sys

import plone.api
from plone.app.textfield import RichText
from plone.app.textfield.value import RichTextValue
from plone.dexterity.utils import iterSchemata
from plone.namedfile.file import NamedBlobFile
from zope.component.hooks import setSite
from zope.schema import getFields

from imi.migration.setuphandlers import install_catalog_indexes

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
    'uvoz', 'FormFolder', 'FormMailerAdapter', 'FormSelectionField',
    'FormStringField', 'FormTextField', 'FormThanksPage',
}

# This legacy roster-day object existed only to provide getSampleVocabulary50()
# to the PFG form.  EasyForm now uses the named imi.form.staff_email vocabulary,
# so the helper is deliberately absent from Plone 5.
SKIP_PATHS = {
    '/dezurstva/objekt-za-seznam-zaposlenih-v-formi-spremeni-dezurstvo-ne-brisi',
}

BASIC_SOURCE_FIELDS = {
    'id', 'title', 'description', 'allowDiscussion', 'subject', 'relatedItems',
    'location', 'language', 'effectiveDate', 'expirationDate', 'creators',
    'contributors', 'rights', 'excludeFromNav',
}

COMMIT_EVERY = 500
SITE_IDS = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')


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
    rel = source_relative_path(record)
    if site in ('dezurstva', 'nadomescanja') and \
            '/seznam_zaposlenih/' in ('/' + rel + '/'):
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
    return RichTextValue(raw=str(value), mimeType='text/html',
                         outputMimeType='text/x-html-safe')


def binary_value(input_dir, binary_info):
    if not binary_info:
        return None
    filename = binary_info.get('filename') or 'legacy-file'
    path = os.path.join(input_dir, 'binaries', binary_info['path'])
    with open(path, 'rb') as handle:
        data = handle.read()
    return NamedBlobFile(data=data, filename=str(filename))


def parse_employee(record):
    description = record.get('description') or ''
    contact, email = description, ''
    if '|' in description:
        contact, email = description.split('|', 1)
    return {
        'source_employee_id': str(record.get('id') or ''),
        'contact': contact,
        'email': '' if email == '-' else email,
    }


def dexterity_fields(obj):
    fields = {}
    for iface in iterSchemata(obj):
        fields.update(getFields(iface))
    return fields


def lines_value(value):
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return (str(value),)


def apply_custom_fields(obj, record, input_dir):
    fields = field_map(record)

    if obj.portal_type == 'imi.staff.employee':
        for key, value in parse_employee(record).items():
            setattr(obj, key, value)
        return

    target_fields = dexterity_fields(obj)
    for name, item in fields.items():
        if name in BASIC_SOURCE_FIELDS or name in ('id', 'title', 'description'):
            continue
        target_field = target_fields.get(name)
        if target_field is None:
            continue
        if 'binary' in item:
            value = binary_value(input_dir, item.get('binary'))
        else:
            value = item.get('value')
        if isinstance(target_field, RichText):
            value = convert_rich(value)
        elif item.get('field_type') == 'LinesField':
            value = lines_value(value)
        setattr(obj, name, value)


def apply_local_roles(obj, metadata):
    for principal, principal_roles in metadata.get('local_roles') or []:
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
    try:
        status = dict(workflow.getStatusOf(chain[0], obj) or {})
        status['review_state'] = state
        workflow.setStatusOf(chain[0], obj, status)
        obj.reindexObject(idxs=['review_state'])
    except Exception:
        pass


def synchronous_catalog_object(obj):
    """Catalog the final imported state immediately through Plone's wrapper.

    CatalogTool.catalog_object adapts ``(obj, portal_catalog)`` to
    ``IIndexableObject`` before ZCatalog sees it, so our named plone.indexer
    adapters (SearchableText, moj, sklop, ...) are used.  Doing this after all
    fields have been assigned avoids relying on the transaction-aware indexing
    queue for migration correctness.
    """
    catalog = plone.api.portal.get_tool('portal_catalog')
    catalog.catalog_object(
        obj,
        uid='/'.join(obj.getPhysicalPath()),
        idxs=[],
        update_metadata=1,
    )


def create_record(app, record, input_dir, path_map):
    if record.get('source_path') in SKIP_PATHS:
        return None
    site = app[record['site']]
    setSite(site)
    rel = source_relative_path(record)
    if not rel:
        return site
    source_type = record.get('portal_type')
    if source_type in SKIP_TYPES or (source_type or '').startswith('Form'):
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
            container=parent, type=pt, id=obj_id,
            title=record.get('title') or obj_id,
            description=record.get('description') or '', safe_id=False)
    apply_custom_fields(obj, record, input_dir)
    apply_local_roles(obj, record.get('metadata') or {})
    try:
        value = record.get('metadata', {}).get('exclude_from_nav')
        if value is not None:
            obj.exclude_from_nav = bool(value)
    except Exception:
        pass
    transition_to_state(obj, (record.get('metadata') or {}).get('workflow_state'))
    synchronous_catalog_object(obj)
    path_map[(record['site'], rel)] = obj
    return obj


def install_migration_catalogs(app):
    """Ensure every site's legacy catalog definitions exist before import."""
    for site_id in SITE_IDS:
        site = app.get(site_id)
        if site is None:
            continue
        setSite(site)
        changed = install_catalog_indexes(site, reindex=False)
        if changed:
            print('Catalog indexes prepared for %s: %s' %
                  (site_id, ', '.join(changed)))


def run(app, input_dir):
    objects_file = os.path.join(input_dir, 'objects.jsonl')
    if not os.path.isfile(objects_file):
        raise SystemExit('Missing %s' % objects_file)
    path_map = {}
    created = skipped = processed = 0
    errors = []
    import transaction

    # A clean export/import must be self-contained: create the catalog indexes
    # first, then each imported object is indexed only after its final field
    # values have been assigned.
    install_migration_catalogs(app)
    transaction.commit()

    with open(objects_file, 'r', encoding='utf-8') as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            processed += 1
            try:
                obj = create_record(app, record, input_dir, path_map)
                if obj is None:
                    skipped += 1
                else:
                    created += 1
            except Exception as exc:
                errors.append({
                    'line': lineno,
                    'site': record.get('site'),
                    'source_path': record.get('source_path'),
                    'portal_type': record.get('portal_type'),
                    'error': repr(exc),
                })
            if processed % COMMIT_EVERY == 0:
                import transaction
                transaction.commit()
                print('Progress: %d processed, %d imported/visited, %d skipped, %d errors' %
                      (processed, created, skipped, len(errors)))

    import transaction
    transaction.commit()
    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report = os.path.join(report_dir, 'plone52-import-errors.json')
    with open(report, 'w', encoding='utf-8') as handle:
        json.dump(errors, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('Imported/visited: %d' % created)
    print('Skipped: %d' % skipped)
    print('Errors: %d' % len(errors))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
