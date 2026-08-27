#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import PFG forms exported as EasyForm migration models.

Requires ``collective.easyform`` to be installed in the target Plone 5.2
sites. Reads ``pfg-easyform.jsonl`` produced by the Plone 4.3 source exporter
and creates/updates EasyForm objects at the same source-relative paths.
"""
import json
import os
import sys

import plone.api
from zope.component.hooks import setSite

SCRIPT_BASENAME = 'plone52_import_easyforms.py'


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


def relative_path(record):
    site = record['site']
    source = record['source_path'].strip('/')
    if source == site:
        return ''
    prefix = site + '/'
    return source[len(prefix):] if source.startswith(prefix) else source


def target_site(app, record):
    site_name = record['site']
    if site_name not in app:
        raise KeyError('missing target site %s' % site_name)
    return app[site_name]


def resolve_parent(app, record):
    current = target_site(app, record)
    site_name = record['site']
    rel = relative_path(record)
    parent_rel = os.path.dirname(rel).replace('\\', '/')
    if not parent_rel:
        return current
    for part in [p for p in parent_rel.split('/') if p]:
        if part not in current:
            raise KeyError('missing target parent %s/%s' % (site_name, parent_rel))
        current = current[part]
    return current


def create_or_get(app, record):
    parent = resolve_parent(app, record)
    obj_id = str(record.get('id') or relative_path(record).rsplit('/', 1)[-1])
    if obj_id in parent:
        obj = parent[obj_id]
        if getattr(obj, 'portal_type', None) != 'EasyForm':
            raise ValueError(
                'existing object %s is %s, expected EasyForm' %
                (obj.absolute_url_path(), getattr(obj, 'portal_type', None)))
        return obj, False
    obj = plone.api.content.create(
        container=parent,
        type='EasyForm',
        id=obj_id,
        title=record.get('title') or obj_id,
        description=record.get('description') or '',
        safe_id=False,
    )
    return obj, True


def apply_metadata(obj, record):
    metadata = record.get('metadata') or {}
    for principal, roles in metadata.get('local_roles') or ():
        obj.manage_setLocalRoles(str(principal), tuple(str(r) for r in roles))
    if metadata.get('local_role_block'):
        blocker = getattr(obj, 'blockLocalRoles', None)
        if callable(blocker):
            blocker()
    exclude = metadata.get('exclude_from_nav')
    if exclude is not None:
        try:
            obj.exclude_from_nav = bool(exclude)
        except Exception:
            pass
    state = metadata.get('workflow_state')
    if state:
        try:
            current = plone.api.content.get_state(obj=obj)
        except Exception:
            current = None
        if current != state:
            wf = plone.api.portal.get_tool('portal_workflow')
            chain = wf.getChainFor(obj)
            if chain:
                status = dict(wf.getStatusOf(chain[0], obj) or {})
                status['review_state'] = state
                wf.setStatusOf(chain[0], obj, status)
                obj.reindexObject(idxs=['review_state'])


def apply_record(obj, record):
    obj.fields_model = record['fields_model']
    obj.actions_model = record['actions_model']

    for name in (
        'thankstitle', 'thanksdescription', 'showAll', 'showFields',
        'includeEmpties', 'thanksPrologue', 'thanksEpilogue', 'form_tabbing',
    ):
        if name in record:
            try:
                setattr(obj, name, record[name])
            except Exception:
                pass
    apply_metadata(obj, record)
    obj.reindexObject()


def run(app, input_dir):
    source = os.path.join(input_dir, 'pfg-easyform.jsonl')
    if not os.path.isfile(source):
        raise SystemExit(
            'Missing %s. Run plone43_export_easyforms.py on the 4.3 source '
            'first.' % source)

    created = updated = 0
    errors = []
    current_site_name = None

    try:
        with open(source, 'r', encoding='utf-8') as handle:
            for lineno, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                try:
                    site_name = record['site']
                    if site_name != current_site_name:
                        setSite(target_site(app, record))
                        current_site_name = site_name

                    obj, was_created = create_or_get(app, record)
                    apply_record(obj, record)
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as exc:
                    errors.append({
                        'line': lineno,
                        'site': record.get('site'),
                        'source_path': record.get('source_path'),
                        'error': repr(exc),
                    })
    finally:
        setSite(None)

    import transaction
    transaction.commit()

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report = os.path.join(report_dir, 'plone52-easyform-import-errors.json')
    with open(report, 'w', encoding='utf-8') as handle:
        json.dump(errors, handle, ensure_ascii=False, indent=2, sort_keys=True)

    print('EasyForms created: %d' % created)
    print('EasyForms updated: %d' % updated)
    print('Errors: %d' % len(errors))
    print('Error report: %s' % report)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
