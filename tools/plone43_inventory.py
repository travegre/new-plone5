#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only Plone 4.3 / Zope 2.13 database inventory.

Run inside the Plone 4.3 buildout with::

    bin/instance run src/plone43_inventory.py --output-dir=/plone/instance/src

The script is intentionally self-contained and uses only APIs available in
Plone 4.3 / Zope 2.13.  It never mutates ZODB objects, workflows, indexes or
schemas.
"""
from __future__ import print_function

import datetime
import json
import os
import sys
import traceback
from collections import Counter, defaultdict

from Acquisition import aq_base
from Products.CMFCore.interfaces import IFolderish
from zope.interface import implementedBy, providedBy

SCRIPT_BASENAME = 'plone43_inventory.py'
SITES = (
    ('portal', '/portal', 'IMI imenik'),
    ('dezurstva', '/dezurstva', 'Dežurstva'),
    ('kiestra', '/kiestra', 'Kiestra'),
    ('preiskave', '/preiskave', 'Preiskave'),
    ('nadomescanja', '/nadomescanja', 'Nadomeščanja'),
)
MAX_SAMPLES = 5
MAX_FIELDS = 100
MAX_VALUE = 1500
MAX_CHILDREN = 500

try:
    text_type = unicode
except NameError:
    text_type = str


def text(value, limit=MAX_VALUE):
    if value is None:
        return None
    try:
        value = value if isinstance(value, text_type) else text_type(value)
    except Exception:
        value = repr(value)
    if len(value) > limit:
        value = value[:limit] + '...'
    return value


def dotted(obj):
    cls = getattr(obj, '__class__', None)
    if cls is None:
        return None
    return '%s.%s' % (getattr(cls, '__module__', '<unknown>'),
                      getattr(cls, '__name__', '<unknown>'))


def object_path(obj):
    try:
        return obj.absolute_url_path()
    except Exception:
        parts = []
        cur = obj
        for unused in range(100):
            if cur is None:
                break
            try:
                ident = getattr(cur, 'id', None)
                if ident:
                    parts.append(ident)
                cur = getattr(cur, 'aq_parent', None)
            except Exception:
                break
        return '/' + '/'.join(reversed(parts))


def portal_type(obj):
    try:
        return obj.portal_type
    except Exception:
        try:
            return obj.getPortalTypeName()
        except Exception:
            return None


def uid(obj):
    try:
        return obj.UID()
    except Exception:
        return None


def hierarchy(obj):
    result = []
    seen = set()
    cls = getattr(obj, '__class__', None)
    while cls is not None and cls not in seen:
        seen.add(cls)
        result.append(dotted(cls))
        bases = getattr(cls, '__bases__', ())
        cls = bases[0] if bases else None
    return result


def interfaces(obj):
    def names(spec):
        try:
            return ['%s.%s' % (i.__module__, i.__name__) for i in spec]
        except Exception:
            return []
    return {'provided': names(providedBy(obj)),
            'implemented': names(implementedBy(obj.__class__))}


def scalar(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [scalar(v) for v in list(value)[:100]]
    if isinstance(value, dict):
        return dict((text(k, 300), scalar(v))
                    for k, v in list(value.items())[:100])
    try:
        if hasattr(value, 'absolute_url_path'):
            return {'path': object_path(value), 'uid': uid(value),
                    'class': dotted(value)}
    except Exception:
        pass
    return text(value)


class Context(object):
    def __init__(self, site):
        self.site = site
        self.errors = []

    def error(self, operation, obj=None, field=None, exception=None,
              message=None):
        item = {'site': self.site, 'path': None, 'portal_type': None,
                'class': None, 'operation': operation, 'field': field,
                'exception_type': (exception.__class__.__name__ if exception
                                   is not None else None),
                'message': text(exception if exception is not None else message)}
        if obj is not None:
            for key, fn in (('path', lambda: object_path(obj)),
                            ('portal_type', lambda: portal_type(obj)),
                            ('class', lambda: dotted(obj))):
                try:
                    item[key] = fn()
                except Exception:
                    pass
        self.errors.append(item)
        return item


def safe(ctx, operation, fn, obj=None, field=None, default=None):
    try:
        return fn()
    except Exception as exc:
        ctx.error(operation, obj=obj, field=field, exception=exc)
        return default


def schema_info(obj, ctx):
    """Return real Archetypes schema only when the runtime supports Schema()."""
    try:
        method = getattr(obj, 'Schema', None)
    except Exception as exc:
        ctx.error('archetypes.schema_capability', obj=obj, exception=exc)
        return {'archetypes': False, 'available': False,
                'reason': 'Schema attribute could not be inspected',
                'fields': []}
    if not callable(method):
        return {'archetypes': False, 'available': False,
                'reason': 'No callable Archetypes Schema method', 'fields': []}
    try:
        schema = method()
        fields = schema.fields()
    except Exception as exc:
        ctx.error('archetypes.schema', obj=obj, exception=exc)
        return {'archetypes': True, 'available': False,
                'reason': 'Schema() or Schema.fields() failed', 'fields': []}
    result = {'archetypes': True, 'available': True,
              'schema_class': dotted(schema), 'fields': []}
    for field in list(fields)[:MAX_FIELDS]:
        result['fields'].append(field_info(field, obj, ctx))
    return result


def field_info(field, obj, ctx):
    name = safe(ctx, 'field.name', field.getName, obj=obj, default=None)
    result = {'name': name, 'class': dotted(field),
              'field_type': getattr(field.__class__, '__name__', None),
              'required': None, 'multivalued': None, 'searchable': None,
              'index': None, 'storage': None, 'default': None,
              'default_factory': None, 'vocabulary': {}, 'errors': []}
    for attr in ('required', 'multiValued', 'searchable', 'index'):
        key = 'multivalued' if attr == 'multiValued' else attr
        try:
            result[key] = scalar(getattr(field, attr))
        except Exception as exc:
            result['errors'].append(ctx.error('field.%s' % attr, obj=obj,
                                              field=name, exception=exc))
    try:
        result['storage'] = dotted(field.getStorage())
    except Exception as exc:
        result['errors'].append(ctx.error('field.storage', obj=obj,
                                          field=name, exception=exc))
    try:
        result['default'] = scalar(field.getDefault(obj))
    except Exception:
        try:
            result['default'] = scalar(getattr(field, 'default', None))
        except Exception as exc:
            result['errors'].append(ctx.error('field.default', obj=obj,
                                              field=name, exception=exc))
    try:
        result['default_factory'] = text(field.default_method)
    except Exception:
        pass
    for attr in ('widget', 'widgetFactory', 'enforceVocabulary'):
        try:
            if hasattr(field, attr):
                value = getattr(field, attr)
                result[attr] = (dotted(value) if not isinstance(value, (str, text_type))
                                else text(value))
        except Exception as exc:
            result['errors'].append(ctx.error('field.%s' % attr, obj=obj,
                                              field=name, exception=exc))
    result['vocabulary'] = vocabulary_info(field, obj, ctx, name)
    return result


def vocabulary_info(field, obj, ctx, name):
    result = {}
    for method_name in ('Vocabulary', 'vocabulary', 'getVocabulary'):
        try:
            method = getattr(field, method_name, None)
            if not callable(method):
                continue
            value = method(obj)
            result['method'] = method_name
            try:
                result['items'] = [scalar(v) for v in list(value)[:200]]
            except Exception as exc:
                ctx.error('field.vocabulary.items', obj=obj, field=name,
                          exception=exc)
            break
        except Exception as exc:
            ctx.error('field.vocabulary', obj=obj, field=name, exception=exc)
    for attr in ('vocabulary', 'enforceVocabulary'):
        try:
            if hasattr(field, attr):
                result[attr] = scalar(getattr(field, attr))
        except Exception as exc:
            ctx.error('field.vocabulary.%s' % attr, obj=obj, field=name,
                      exception=exc)
    try:
        result['name'] = text(field.getVocabularyName())
    except Exception:
        pass
    return result


def field_values(obj, schema, ctx):
    result = {}
    if not schema.get('available'):
        return result
    try:
        fields = obj.Schema().fields()
    except Exception as exc:
        ctx.error('field_values.schema', obj=obj, exception=exc)
        return result
    for field in list(fields)[:MAX_FIELDS]:
        name = safe(ctx, 'field.name', field.getName, obj=obj, default=None)
        if not name:
            continue
        try:
            value = field.getRaw(obj)
        except Exception as exc:
            ctx.error('field.value.raw', obj=obj, field=name, exception=exc)
            try:
                value = field.get(obj)
            except Exception as exc2:
                ctx.error('field.value', obj=obj, field=name, exception=exc2)
                continue
        item = {'value': scalar(value)}
        try:
            item['content_type'] = text(field.getContentType(obj))
        except Exception as exc:
            ctx.error('field.value.content_type', obj=obj, field=name,
                      exception=exc)
        result[name] = item
    return result


def stored_attributes(obj, ctx):
    result = {}
    try:
        values = getattr(aq_base(obj), '__dict__', {})
        for key, value in values.items():
            if key.startswith('_'):
                continue
            try:
                result[key] = scalar(value)
            except Exception as exc:
                ctx.error('stored_attribute.value', obj=obj, field=key,
                          exception=exc)
    except Exception as exc:
        ctx.error('stored_attributes', obj=obj, exception=exc)
    return result


def local_roles(obj, ctx):
    roles = safe(ctx, 'local_roles', obj.get_local_roles, obj=obj, default={})
    blocked = safe(ctx, 'local_role_block', obj.get_local_role_block, obj=obj,
                   default=None)
    return {'roles': dict(roles or {}), 'blocked': blocked}


def permissions(obj, ctx):
    result = {}
    try:
        for item in getattr(obj.__class__, '__ac_permissions__', ()):
            try:
                result[text(item[0])] = list(item[1] or ())
            except Exception as exc:
                ctx.error('permissions.item', obj=obj, exception=exc)
    except Exception as exc:
        ctx.error('permissions', obj=obj, exception=exc)
    return result


def workflow_info(obj, tool, ctx):
    result = {'chain': [], 'review_state': None, 'states_by_chain': {}}
    if tool is None:
        return result
    try:
        result['chain'] = list(tool.getChainForPortalType(portal_type(obj)) or ())
    except Exception as exc:
        ctx.error('workflow.chain', obj=obj, exception=exc)
    try:
        result['review_state'] = tool.getInfoFor(obj, 'review_state', None)
    except Exception as exc:
        ctx.error('workflow.review_state', obj=obj, exception=exc)
    try:
        result['states_by_chain'] = dict(tool.getWorkflowStateByChainFor(obj) or {})
    except Exception as exc:
        ctx.error('workflow.states_by_chain', obj=obj, exception=exc)
    return result


def references(obj, catalog, ctx):
    result = {'outgoing': [], 'incoming': [], 'broken_outgoing': [],
              'broken_incoming': []}
    try:
        for target in obj.getRefs():
            try:
                item = {'path': object_path(target), 'uid': uid(target),
                        'class': dotted(target)}
                result['outgoing'].append(item)
            except Exception as exc:
                ctx.error('references.outgoing.target', obj=obj, exception=exc)
                result['broken_outgoing'].append({'path': None})
    except Exception as exc:
        ctx.error('references.outgoing', obj=obj, exception=exc)
    if catalog is not None:
        try:
            for ref in catalog.getBackReferences(obj):
                try:
                    target = ref.getObject()
                    result['incoming'].append({'uid': uid(ref),
                                              'path': object_path(target),
                                              'class': dotted(target)})
                except Exception as exc:
                    ctx.error('references.incoming.target', obj=obj,
                              exception=exc)
                    result['broken_incoming'].append({'uid': uid(ref), 'path': None})
        except Exception as exc:
            ctx.error('references.incoming', obj=obj, exception=exc)
    return result


def binaries(obj, schema, ctx):
    result = []
    if not schema.get('available'):
        return result
    try:
        fields = obj.Schema().fields()
    except Exception as exc:
        ctx.error('binaries.schema', obj=obj, exception=exc)
        return result
    for field in list(fields):
        kind = getattr(field.__class__, '__name__', '')
        if kind not in ('FileField', 'ImageField'):
            continue
        name = safe(ctx, 'binary.field_name', field.getName, obj=obj, default=None)
        try:
            value = field.getRaw(obj)
        except Exception as exc:
            ctx.error('binary.value', obj=obj, field=name, exception=exc)
            continue
        if value is None:
            continue
        size = None
        try:
            size = value.getSize()
        except Exception:
            try:
                size = len(value.data)
            except Exception as exc:
                ctx.error('binary.size', obj=obj, field=name, exception=exc)
        result.append({'field': name, 'type': kind, 'size': size,
                       'filename': text(getattr(value, 'filename', None))})
    return result


def inspect_object(obj, wf, refs, ctx):
    schema = schema_info(obj, ctx)
    return {
        'path': safe(ctx, 'object.path', lambda: object_path(obj), obj=obj),
        'id': safe(ctx, 'object.id', obj.getId, obj=obj,
                   default=getattr(obj, 'id', None)),
        'title': safe(ctx, 'object.title', obj.Title, obj=obj,
                      default=getattr(obj, 'title', None)),
        'portal_type': portal_type(obj), 'class': dotted(obj),
        'class_hierarchy': hierarchy(obj), 'interfaces': interfaces(obj),
        'archetypes_schema': schema,
        'field_values': field_values(obj, schema, ctx),
        'stored_attributes': stored_attributes(obj, ctx),
        'workflow': workflow_info(obj, wf, ctx),
        'local_roles': local_roles(obj, ctx),
        'permissions': permissions(obj, ctx),
        'references': references(obj, refs, ctx),
        'binaries': binaries(obj, schema, ctx),
        'folderish': safe(ctx, 'object.folderish',
                          lambda: IFolderish.providedBy(obj), obj=obj,
                          default=False),
    }


def is_pfg(obj):
    pt = portal_type(obj) or ''
    cls = dotted(obj) or ''
    return (any(x in pt for x in ('FormFolder', 'FormMailer', 'FormField',
                                  'FormCustomScript', 'FormSaveData'))
            or 'PloneFormGen' in cls)


def pfg_dump(obj, ctx, depth=0):
    result = inspect_object(obj, None, None, ctx)
    result['children'] = []
    if depth >= 8:
        return result
    try:
        if IFolderish.providedBy(obj):
            for child in list(obj.objectValues() or [])[:MAX_CHILDREN]:
                try:
                    result['children'].append(pfg_dump(child, ctx, depth + 1))
                except Exception as exc:
                    ctx.error('pfg.child', obj=obj, exception=exc)
    except Exception as exc:
        ctx.error('pfg.children', obj=obj, exception=exc)
    return result


def walk(root, ctx):
    stack = [root]
    while stack:
        obj = stack.pop()
        yield obj
        try:
            if IFolderish.providedBy(obj):
                stack.extend(reversed(list(obj.objectValues() or [])))
        except Exception as exc:
            ctx.error('walk.children', obj=obj, exception=exc)


def type_definition(site, pt, ctx):
    try:
        info = site.portal_types.getTypeInfo(pt)
    except Exception as exc:
        ctx.error('portal_type.definition', obj=site, message=pt,
                  exception=exc)
        return None
    if info is None:
        return None
    result = {'id': pt, 'title': text(getattr(info, 'title', None)),
              'factory': text(getattr(info, 'factory', None)),
              'klass': text(getattr(info, 'klass', None)),
              'allowed_content_types': list(getattr(info, 'allowed_content_types', ()) or ()),
              'global_allow': bool(getattr(info, 'global_allow', False)),
              'filter_content_types': bool(getattr(info, 'filter_content_types', False)),
              'default_view': text(getattr(info, 'default_view', None)),
              'immediate_view': text(getattr(info, 'immediate_view', None)),
              'aliases': dict(getattr(info, 'aliases', {}) or {}),
              'workflow_chain': [], 'permissions': {}}
    try:
        result['workflow_chain'] = list(site.portal_workflow.getChainForPortalType(pt) or ())
    except Exception as exc:
        ctx.error('portal_type.workflow_chain', obj=site, message=pt,
                  exception=exc)
    try:
        result['permissions'] = dict(info.getPermissionMap())
    except Exception as exc:
        ctx.error('portal_type.permissions', obj=site, message=pt,
                  exception=exc)
    return result


def site_inventory(site, name, label, global_errors):
    ctx = Context(name)
    wf = safe(ctx, 'site.portal_workflow', lambda: site.portal_workflow,
              obj=site)
    refs = safe(ctx, 'site.reference_catalog', lambda: site.reference_catalog,
                obj=site)
    counts = Counter(); classes = defaultdict(set); samples = defaultdict(list)
    workflows = defaultdict(Counter); role_counts = Counter()
    pfgs = []; unknown = []; binaries_count = Counter(); binaries_bytes = Counter()
    total = 0
    try:
        for obj in walk(site, ctx):
            total += 1
            try:
                pt = portal_type(obj) or '<no portal_type>'
                counts[pt] += 1
                classes[pt].add(dotted(obj))
            except Exception as exc:
                ctx.error('object.classification', obj=obj, exception=exc)
                pt = '<classification error>'
                counts[pt] += 1
            if len(samples[pt]) < MAX_SAMPLES:
                try:
                    sample = inspect_object(obj, wf, refs, ctx)
                    samples[pt].append(sample)
                    for binary in sample.get('binaries', []):
                        binaries_count[binary['type']] += 1
                        binaries_bytes[binary['type']] += binary.get('size') or 0
                except Exception as exc:
                    ctx.error('object.sample', obj=obj, exception=exc)
                    samples[pt].append({'path': object_path(obj),
                                        'portal_type': pt,
                                        'class': dotted(obj),
                                        'inspection_failed': True})
            if pt in ('Unknown', '<no portal_type>'):
                try:
                    unknown.append(inspect_object(obj, wf, refs, ctx))
                except Exception as exc:
                    ctx.error('unknown.summary', obj=obj, exception=exc)
            try:
                for wid in workflow_info(obj, wf, ctx).get('chain', []):
                    workflows[pt][wid] += 1
            except Exception as exc:
                ctx.error('workflow.aggregate', obj=obj, exception=exc)
            try:
                if local_roles(obj, ctx).get('roles'):
                    role_counts[pt] += 1
            except Exception as exc:
                ctx.error('local_roles.aggregate', obj=obj, exception=exc)
            try:
                if is_pfg(obj):
                    pfgs.append(pfg_dump(obj, ctx))
            except Exception as exc:
                ctx.error('pfg.detect', obj=obj, exception=exc)
    except Exception as exc:
        ctx.error('site.walk', obj=site, exception=exc)
    result_types = {}
    for pt in sorted(counts):
        result_types[pt] = {'count': counts[pt],
                            'classes': sorted(x for x in classes[pt] if x),
                            'definition': type_definition(site, pt, ctx),
                            'workflow_assignments': dict(workflows[pt]),
                            'samples': samples[pt]}
    global_errors.extend(ctx.errors)
    return {'site': name, 'path': object_path(site), 'title': label,
            'objects_walked': total, 'portal_types': result_types,
            'pfg_objects': pfgs, 'unknown_objects': unknown,
            'binary_summary': {'sample_counts': dict(binaries_count),
                               'sample_bytes': dict(binaries_bytes)},
            'objects_with_local_roles': dict(role_counts),
            'class': dotted(site), 'class_hierarchy': hierarchy(site),
            'interfaces': interfaces(site),
            'inspection_errors': len(ctx.errors)}


def global_inventory(app, errors):
    result = {'portal_types': [], 'workflows': [], 'tools': {}}
    for name in ('portal_types', 'portal_workflow', 'portal_catalog',
                 'reference_catalog', 'portal_registry'):
        try:
            result['tools'][name] = bool(hasattr(app, name))
        except Exception as exc:
            errors.append({'site': None, 'path': '/', 'portal_type': None,
                'class': dotted(app), 'operation': 'global.tool.%s' % name,
                'field': None, 'exception_type': exc.__class__.__name__,
                'message': text(exc)})
    try:
        for info in app.portal_types.objectValues():
            result['portal_types'].append({
                'id': getattr(info, 'id', None),
                'title': text(getattr(info, 'title', None)),
                'factory': text(getattr(info, 'factory', None)),
                'klass': text(getattr(info, 'klass', None))})
    except Exception as exc:
        errors.append({'site': None, 'path': '/portal_types',
            'portal_type': None, 'class': dotted(app),
            'operation': 'global.portal_types', 'field': None,
            'exception_type': exc.__class__.__name__, 'message': text(exc)})
    try:
        for definition in app.portal_workflow.objectValues():
            try:
                states = [getattr(s, 'id', None)
                          for s in definition.states.objectValues()]
            except Exception as exc:
                states = []
                errors.append({'site': None, 'path': None, 'portal_type': None,
                    'class': dotted(definition),
                    'operation': 'global.workflow.states', 'field': None,
                    'exception_type': exc.__class__.__name__,
                    'message': text(exc)})
            result['workflows'].append({
                'id': getattr(definition, 'id', None),
                'title': text(getattr(definition, 'title', None)),
                'class': dotted(definition), 'states': states})
    except Exception as exc:
        errors.append({'site': None, 'path': '/', 'portal_type': None,
            'class': dotted(app), 'operation': 'global.workflows',
            'field': None, 'exception_type': exc.__class__.__name__,
            'message': text(exc)})
    return result


def parse_output_dir(args):
    if not args:
        return '/tmp/plone43-inventory'
    if len(args) == 1 and args[0].startswith('--output-dir='):
        value = args[0].split('=', 1)[1]
        if value:
            return value
        raise SystemExit('--output-dir requires a directory.')
    if args and args[0] == '--output-dir':
        if len(args) == 2 and not args[1].startswith('-'):
            return args[1]
        raise SystemExit('Usage: bin/instance run src/plone43_inventory.py --output-dir /path')
    if args[0].startswith('-'):
        raise SystemExit('Unexpected option %s. Use --output-dir /path.' % args[0])
    raise SystemExit('Unexpected inventory argument %s. Use --output-dir /path.' % args[0])


def parse_inventory_args(argv):
    """Normalize actual Plone 4.3/Zope 2.13 instance-run argv.

    The launcher can expose the script name once or more than once and can
    expose Python's ``-c`` marker.  We identify the inventory script by its
    known basename, take only arguments following its final occurrence, and
    then apply strict inventory-option parsing.  Unknown options are never
    silently discarded.
    """
    argv = list(argv)
    positions = []
    for index, value in enumerate(argv):
        try:
            if os.path.basename(value) == SCRIPT_BASENAME:
                positions.append(index)
        except Exception:
            pass
    if not positions:
        raise SystemExit('Unexpected Plone/Zope run argv shape: %r' % argv)
    args = argv[positions[-1] + 1:]
    if args and args[0] == '-c':
        args = args[1:]
    return parse_output_dir(args)


def markdown(data):
    lines = ['# Plone 4.3 Read-only Database Inventory', '',
             '**Generated:** `%s`' % data['generated_at'],
             '**Read-only:** `%s`' % data['read_only'], '',
             '## Inspection errors', '',
             '**Total:** %s' % len(data['errors']), '']
    if data['errors']:
        lines.extend(['| Site | Path | Portal type | Class | Operation | Field | Exception | Message |',
                      '|---|---|---|---|---|---|---|---|'])
        for error in data['errors'][:5000]:
            values = []
            for key in ('site', 'path', 'portal_type', 'class', 'operation',
                        'field', 'exception_type', 'message'):
                values.append(text(error.get(key) or '', 500).replace('|', '\\|').replace('\n', ' '))
            lines.append('| %s |' % ' | '.join(values))
    else:
        lines.append('None.')
    for site in data['sites']:
        lines.extend(['', '## /%s — %s' % (site['site'], site['title']), '',
                      '**Objects walked:** %s' % site['objects_walked'],
                      '**Inspection errors:** %s' % site['inspection_errors'], '',
                      '| Portal type | Count | Runtime classes | Workflow chains |',
                      '|---|---:|---|---|'])
        for pt, info in sorted(site['portal_types'].items()):
            lines.append('| `%s` | %s | %s | %s |' % (
                pt, info['count'], '<br>'.join(info['classes']),
                '<br>'.join(sorted(info['workflow_assignments']))))
        lines.extend(['', '### PloneFormGen', ''])
        if site['pfg_objects']:
            for form in site['pfg_objects']:
                lines.extend(['#### `%s`' % form.get('path'), '', '```json',
                    json.dumps(form, ensure_ascii=False, indent=2,
                               sort_keys=True), '```', ''])
        else:
            lines.append('No PFG objects detected by runtime class/portal-type heuristics.')
        lines.extend(['', '### Binary summary', '', '```json',
            json.dumps(site['binary_summary'], indent=2, sort_keys=True),
            '```', '', '### Unknown/no-portal-type objects', ''])
        if site['unknown_objects']:
            lines.extend(['```json', json.dumps(site['unknown_objects'],
                ensure_ascii=False, indent=2, sort_keys=True), '```'])
        else:
            lines.append('None detected.')
        lines.extend(['', '### Representative samples', ''])
        for pt, info in sorted(site['portal_types'].items()):
            for sample in info['samples']:
                lines.extend(['<details><summary><code>%s</code> — %s</summary>' %
                    (pt, sample.get('path')), '', '```json',
                    json.dumps(sample, ensure_ascii=False, indent=2,
                               sort_keys=True), '```', '</details>', ''])

    #lines_unicode = [line.decode('utf-8') if isinstance(line, str) else line for line in lines]
    def to_unicode(v):
      if isinstance(v, unicode):
        return v
      if isinstance(v, str):
        return v.decode('utf-8')
      return unicode(v)

    return u'\n'.join(to_unicode(line) for line in lines) + u'\n'
    #return '\n'.join(lines) + '\n'


def run(app, outdir):
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    errors = []
    result = {'schema_version': 3, 'read_only': True,
              'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
              'runtime': {'python': sys.version, 'zope': None, 'plone': None},
              'global': global_inventory(app, errors), 'sites': [], 'errors': errors}
    try:
        import Zope2
        result['runtime']['zope'] = text(getattr(Zope2, '__version__', None))
    except Exception as exc:
        errors.append({'site': None, 'path': None, 'portal_type': None,
            'class': None, 'operation': 'runtime.zope_version', 'field': None,
            'exception_type': exc.__class__.__name__, 'message': text(exc)})
    try:
        import Products.CMFPlone
        result['runtime']['plone'] = text(getattr(Products.CMFPlone, '__version__', None))
    except Exception as exc:
        errors.append({'site': None, 'path': None, 'portal_type': None,
            'class': None, 'operation': 'runtime.plone_version', 'field': None,
            'exception_type': exc.__class__.__name__, 'message': text(exc)})
    for name, site_path, label in SITES:
        try:
            site = app.unrestrictedTraverse(site_path.lstrip('/'))
            result['sites'].append(site_inventory(site, name, label, errors))
        except Exception as exc:
            errors.append({'site': name, 'path': site_path, 'portal_type': None,
                'class': None, 'operation': 'site.open', 'field': None,
                'exception_type': exc.__class__.__name__, 'message': text(exc),
                'traceback': traceback.format_exc()})
    with open(os.path.join(outdir, 'plone43_inventory.json'), 'w') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(outdir, 'plone43_inventory.md'), 'wb') as handle:
        handle.write(markdown(result).encode('utf-8'))
    print('Inventory written to %s' % os.path.abspath(outdir))


if 'app' not in globals():
    raise SystemExit('Use the Plone 4.3 bin/instance run command; do not execute with system Python.')
run(app, parse_inventory_args(sys.argv))
