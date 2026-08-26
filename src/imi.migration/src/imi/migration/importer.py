# -*- coding: utf-8 -*-
"""Import the read-only Plone 4.3 JSONL export into clean Plone 5.2 sites.

The importer is deliberately explicit and restart-friendly.  It does not read
Data.fs directly; it consumes the export directory produced by the Plone 4.3
exporter (objects.jsonl, pfg.jsonl, binaries/, manifest.json).
"""
from __future__ import absolute_import

import json
import os

import transaction
from DateTime import DateTime
from plone import api
from plone.app.textfield.value import RichTextValue
from plone.namedfile.file import NamedBlobFile
from Products.CMFPlone.factory import addPloneSite
from Products.CMFPlone.utils import get_installer


SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')

PFG_TYPES = {
    'FormFolder', 'FormMailerAdapter', 'FormSelectionField',
    'FormStringField', 'FormTextField', 'FormThanksPage',
}

TYPE_MAP = {
    ('portal', 'produkti'): 'imi.directory.person',
    ('portal', 'uvoz'): None,
    ('dezurstva', 'dezurstvo'): 'imi.duty.roster_day',
    ('dezurstva', 'seznam_zaposlenih'): 'imi.staff.directory',
    ('kiestra', 'dezurstvo'): 'imi.kiestra.work_day',
    ('preiskave', 'imipreiskava'): 'imi.exams.examination',
    ('preiskave', 'imiuvozipreiskavo'): None,
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

RICH_FIELDS = {
    'imi.kiestra.work_day': {'stalni_tekst'},
    'imi.exams.examination': {
        'sklop', 'sinonim', 'metode', 'opis', 'opombe', 'trajanje', 'urnik',
    },
}

TUPLE_FIELDS = {
    'imi.duty.roster_day': {
        'dezurni_zdravnik', 'nadzorni_zdravnik', 'specializant', 'sarsifon',
        'dezurni_tehnik', 'izobrazevanje', 'bakterioloski_tehnik',
        'inoqula_tehnik', 'sprejem_predpriprava_tehnik', 'vpis',
        'intervencijska_skupina', 'BOR', 'HIV', 'HUM', 'IT', 'PRZ', 'KLM',
        'KOV', 'VINVZV', 'VINDIF', 'WHO', 'kiestra',
    },
    'imi.kiestra.work_day': {
        'priprava_vzorcev', 'cepljenje_vzorcev', 'odcitavanje',
        'identifikacija', 'antibiogram', 'izolacija', 'odpad', 'ciscenje',
    },
    'imi.replacements.laboratory': {'privzeti_vodja'},
    'imi.exams.examination': {'podrocje', 'preiskava_vzorec_nujno'},
}

COMMON_AT_FIELDS = {
    'id', 'title', 'description', 'subject', 'relatedItems', 'location',
    'language', 'effectiveDate', 'expirationDate', 'creation_date',
    'modification_date', 'creators', 'contributors', 'rights',
    'allowDiscussion', 'excludeFromNav', 'nextPreviousEnabled',
    'constrainTypesMode', 'locallyAllowedTypes', 'immediatelyAddableTypes',
}


def _fields(record):
    return dict((f.get('name'), f.get('value')) for f in record.get('fields', []))


def _target_type(record):
    legacy = record.get('portal_type')
    site = record.get('site')
    if legacy in PFG_TYPES:
        return None
    if (site, legacy) in TYPE_MAP:
        return TYPE_MAP[(site, legacy)]
    return STANDARD_TYPE_MAP.get(legacy)


def _site(app, site_id):
    try:
        return app[site_id]
    except KeyError:
        addPloneSite(app, site_id, title=site_id, extension_ids=())
        transaction.commit()
        return app[site_id]


def ensure_sites(app):
    result = {}
    for site_id in SITES:
        site = _site(app, site_id)
        installer = get_installer(site)
        if not installer.is_product_installed('imi.migration'):
            installer.install_product('imi.migration')
            transaction.commit()
        result[site_id] = site
    return result


def _relative_parts(record):
    source = record['source_path'].strip('/')
    parts = source.split('/')
    if not parts or parts[0] != record['site']:
        raise ValueError('Source path/site mismatch: %r' % record['source_path'])
    return parts[1:]


def _traverse(site, parts):
    obj = site
    for part in parts:
        obj = obj[part]
    return obj


def _parent_for(site, parts):
    return _traverse(site, parts[:-1]) if len(parts) > 1 else site


def _rich(value):
    if value in (None, ''):
        return RichTextValue('', 'text/html', 'text/x-html-safe')
    return RichTextValue(str(value), 'text/html', 'text/x-html-safe')


def _tuple(value):
    if value in (None, ''):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value if v is not None)
    return (str(value),)


def _binary_from_export(export_dir, value):
    """Return NamedBlobFile for exporter binary descriptors when present."""
    if not isinstance(value, dict):
        return None
    relpath = value.get('binary_path') or value.get('path')
    if not relpath:
        return None
    path = os.path.join(export_dir, relpath)
    if not os.path.isfile(path):
        raise IOError('Missing exported binary: %s' % path)
    with open(path, 'rb') as handle:
        data = handle.read()
    return NamedBlobFile(
        data=data,
        filename=value.get('filename') or os.path.basename(path),
        contentType=value.get('content_type') or 'application/octet-stream',
    )


def _custom_value(target_type, name, value, export_dir):
    if name in RICH_FIELDS.get(target_type, ()):
        return _rich(value)
    if name in TUPLE_FIELDS.get(target_type, ()):
        return _tuple(value)
    if target_type == 'imi.exams.examination' and name == 'datoteka':
        return _binary_from_export(export_dir, value)
    return value


def _create_object(parent, record, target_type, export_dir):
    fields = _fields(record)
    kwargs = {
        'container': parent,
        'type': target_type,
        'id': record['id'],
        'title': record.get('title') or record['id'],
    }
    description = record.get('description')
    if description is not None:
        kwargs['description'] = description
    obj = api.content.create(**kwargs)

    for name, value in fields.items():
        if name in COMMON_AT_FIELDS or name in ('id', 'title', 'description'):
            continue
        if not hasattr(obj, name):
            continue
        converted = _custom_value(target_type, name, value, export_dir)
        if converted is not None:
            setattr(obj, name, converted)
    return obj


def _apply_standard_fields(obj, record):
    fields = _fields(record)
    if hasattr(obj, 'exclude_from_nav') and 'excludeFromNav' in fields:
        obj.exclude_from_nav = bool(fields['excludeFromNav'])
    if hasattr(obj, 'language') and fields.get('language'):
        obj.language = fields['language']
    # Standard Document text.
    if record.get('portal_type') == 'Document' and hasattr(obj, 'text'):
        value = fields.get('text')
        if value is not None:
            obj.text = _rich(value)


def _apply_metadata(obj, record):
    metadata = record.get('metadata') or {}
    created = metadata.get('created')
    modified = metadata.get('modified')
    if created:
        obj.setCreationDate(DateTime(created))
    if modified:
        obj.setModificationDate(DateTime(modified))

    effective = metadata.get('effective')
    expires = metadata.get('expires')
    if effective and not effective.startswith('1000-'):
        obj.setEffectiveDate(DateTime(effective))
    if expires and not expires.startswith('2499-'):
        obj.setExpirationDate(DateTime(expires))

    roles = metadata.get('local_roles') or []
    for principal, principal_roles in roles:
        try:
            obj.manage_setLocalRoles(principal, list(principal_roles))
        except Exception:
            pass
    if metadata.get('local_role_block'):
        try:
            obj.__ac_local_roles_block__ = True
        except Exception:
            pass


def _apply_workflow(obj, record):
    state = (record.get('metadata') or {}).get('workflow_state')
    if not state:
        return
    workflow = api.portal.get_tool('portal_workflow')
    current = workflow.getInfoFor(obj, 'review_state', None)
    if current == state:
        return
    # Preserve the requested state where a direct transition exists.  If the
    # target workflow differs, parity reporting will flag it instead of
    # guessing a transition chain.
    for transition in workflow.getTransitionsFor(obj):
        if transition.get('new_state_id') == state:
            workflow.doActionFor(obj, transition['id'])
            return


def _write_json(path, data):
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def import_objects(app, export_dir, commit_every=500):
    sites = ensure_sites(app)
    objects_file = os.path.join(export_dir, 'objects.jsonl')
    if not os.path.isfile(objects_file):
        raise IOError('Missing %s' % objects_file)

    stats = {'created': 0, 'existing': 0, 'skipped': 0, 'errors': []}
    path_map = {}
    pending = []

    with open(objects_file, 'r', encoding='utf-8') as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            target_type = _target_type(record)
            if target_type is None:
                stats['skipped'] += 1
                continue
            pending.append((len(_relative_parts(record)), line_number, record, target_type))

    # Export order is not relied upon; parents are always imported first.
    pending.sort(key=lambda item: (item[0], item[2]['source_path']))

    for unused_depth, line_number, record, target_type in pending:
        site = sites[record['site']]
        parts = _relative_parts(record)
        try:
            parent = _parent_for(site, parts)
            object_id = parts[-1]
            if object_id in parent:
                obj = parent[object_id]
                stats['existing'] += 1
            else:
                obj = _create_object(parent, record, target_type, export_dir)
                stats['created'] += 1
            _apply_standard_fields(obj, record)
            _apply_metadata(obj, record)
            _apply_workflow(obj, record)
            obj.reindexObject()
            path_map[record['source_path']] = '/'.join(obj.getPhysicalPath())
        except Exception as exc:
            stats['errors'].append({
                'line': line_number,
                'source_path': record.get('source_path'),
                'portal_type': record.get('portal_type'),
                'target_type': target_type,
                'error': '%s: %s' % (exc.__class__.__name__, exc),
            })
        if (stats['created'] + stats['existing']) % commit_every == 0:
            transaction.commit()

    transaction.commit()
    reports = os.path.join(export_dir, 'reports')
    os.makedirs(reports, exist_ok=True)
    _write_json(os.path.join(reports, 'plone52-import.json'), stats)
    _write_json(os.path.join(reports, 'plone52-path-map.json'), path_map)
    return stats


def run(app, export_dir, commit_every=500):
    """Public entry point used by tools/plone52_import.py."""
    return import_objects(app, os.path.abspath(export_dir), commit_every=commit_every)
