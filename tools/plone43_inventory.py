#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only Plone 4.3 / Zope 2.13 database inventory.

Run inside the real Plone 4.3 environment, for example:
    bin/instance run tools/plone43_inventory.py --output-dir /tmp/plone43-inventory

``bin/instance run`` in the Plone 4.3 generation of
``plone.recipe.zope2instance`` executes the script through Python's ``-c``
launcher.  Depending on the exact 4.3-era recipe/instance wrapper, that
launcher marker can remain at the front of ``sys.argv``.  ``parse_inventory_args``
recognizes that specific launcher shape; it does not silently discard arbitrary
unknown options.
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
from zope.interface import providedBy, implementedBy

SITES = (('portal', '/portal', 'IMI imenik'), ('dezurstva', '/dezurstva', 'Dežurstva'),
         ('kiestra', '/kiestra', 'Kiestra'), ('preiskave', '/preiskave', 'Preiskave'),
         ('nadomescanja', '/nadomescanja', 'Nadomeščanja'))
MAX_SAMPLES = 5
MAX_FIELDS = 100
MAX_VALUE = 1500
MAX_DEPTH = 8
try:
    text_type = unicode
except NameError:
    text_type = str


class InventoryContext(object):
    """Collect non-fatal inspection errors with object context."""
    def __init__(self, site=None):
        self.site = site
        self.errors = []

    def error(self, operation, obj=None, message=None, exception=None, field=None):
        item = {'site': self.site, 'path': None, 'portal_type': None, 'class': None,
                'operation': operation, 'field': field,
                'exception_type': exception.__class__.__name__ if exception is not None else None,
                'message': text(exception if exception is not None else message)}
        if obj is not None:
            try:
                item['path'] = path(obj)
            except Exception:
                pass
            try:
                item['portal_type'] = ptype(obj)
            except Exception:
                pass
            try:
                item['class'] = dotted(obj)
            except Exception:
                pass
        self.errors.append(item)
        return item


def text(value, limit=MAX_VALUE):
    if value is None:
        return None
    try:
        value = value if isinstance(value, text_type) else text_type(value)
    except Exception:
        value = repr(value)
    return value if len(value) <= limit else value[:limit] + '...'


def scalar(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [scalar(x) for x in list(value)[:100]]
    if isinstance(value, dict):
        return dict((text(k, 300), scalar(v)) for k, v in list(value.items())[:100])
    try:
        if hasattr(value, 'absolute_url_path'):
            return {'path': path(value), 'uid': safe_uid(value)}
    except Exception:
        pass
    return text(value)


def safe_call(ctx, operation, fn, obj=None, field=None, default=None):
    try:
        return fn()
    except Exception as exc:
        ctx.error(operation, obj=obj, field=field, exception=exc)
        return default


def dotted(obj):
    cls = getattr(obj, '__class__', None)
    if cls is None:
        return None
    return '%s.%s' % (getattr(cls, '__module__', '<unknown>'), getattr(cls, '__name__', '<unknown>'))


def hierarchy(obj):
    result = []
    seen = set()
    cls = getattr(obj, '__class__', None)
    while cls is not None and cls not in seen:
        seen.add(cls)
        result.append('%s.%s' % (getattr(cls, '__module__', '<unknown>'), getattr(cls, '__name__', '<unknown>')))
        bases = getattr(cls, '__bases__', ())
        cls = bases[0] if bases else None
    return result


def interfaces(obj):
    def names(spec):
        try:
            return ['%s.%s' % (i.__module__, i.__name__) for i in spec]
        except Exception:
            return []
    return {'provided': names(providedBy(obj)), 'implemented': names(implementedBy(obj.__class__))}


def path(obj):
    try:
        return obj.absolute_url_path()
    except Exception:
        parts = []
        current = obj
        for _ in range(100):
            if current is None:
                break
            try:
                parts.append(getattr(current, 'id', ''))
                current = getattr(current, 'aq_parent', None)
            except Exception:
                break
        return '/' + '/'.join(reversed([p for p in parts if p]))


def safe_uid(obj):
    try:
        return obj.UID()
    except Exception:
        return None


def ptype(obj):
    try:
        return obj.portal_type
    except Exception:
        try:
            return obj.getPortalTypeName()
        except Exception:
            return None


def field_name(field, ctx, obj=None):
    try:
        return field.getName()
    except Exception as exc:
        ctx.error('field.name', obj=obj, exception=exc)
        return None


def archetypes_schema(obj, ctx):
    """Inspect AT only when the runtime object actually exposes Schema()."""
    try:
        schema_method = getattr(obj, 'Schema', None)
    except Exception as exc:
        ctx.error('archetypes.schema_capability', obj=obj, exception=exc)
        return {'archetypes': False, 'available': False,
                'reason': 'Schema attribute could not be inspected', 'fields': []}
    if not callable(schema_method):
        return {'archetypes': False, 'available': False,
                'reason': 'No callable Archetypes Schema method', 'fields': []}
    try:
        schema_obj = schema_method()
    except Exception as exc:
        ctx.error('archetypes.schema', obj=obj, exception=exc)
        return {'archetypes': True, 'available': False,
                'reason': 'Schema() raised an exception', 'fields': []}
    try:
        field_list = schema_obj.fields()
    except Exception as exc:
        ctx.error('archetypes.schema.fields', obj=obj, exception=exc)
        return {'archetypes': True, 'available': False,
                'reason': 'Schema.fields() raised an exception', 'fields': []}
    fields = [schema_field(field, obj, ctx) for field in list(field_list)[:MAX_FIELDS]]
    return {'archetypes': True, 'available': True, 'schema_class': dotted(schema_obj), 'fields': fields}


def schema_field(field, obj, ctx):
    name = field_name(field, ctx, obj)
    result = {'name': name, 'class': dotted(field), 'field_type': getattr(field.__class__, '__name__', None),
              'required': None, 'multivalued': None, 'searchable': None, 'index': None, 'storage': None,
              'default': None, 'default_factory': None, 'vocabulary': {}, 'errors': []}
    for attr in ('required', 'multiValued', 'searchable', 'index'):
        key = 'multivalued' if attr == 'multiValued' else attr
        try:
            result[key] = scalar(getattr(field, attr))
        except Exception as exc:
            result['errors'].append(ctx.error('field.%s' % attr, obj=obj, field=name, exception=exc))
    try:
        result['storage'] = dotted(field.getStorage())
    except Exception as exc:
        result['errors'].append(ctx.error('field.storage', obj=obj, field=name, exception=exc))
    try:
        result['default'] = scalar(field.getDefault(obj))
    except Exception:
        try:
            result['default'] = scalar(getattr(field, 'default', None))
        except Exception as exc:
            result['errors'].append(ctx.error('field.default', obj=obj, field=name, exception=exc))
    try:
        result['default_factory'] = text(field.default_method)
    except Exception:
        pass
    result['vocabulary'] = vocabulary(field, obj, ctx)
    for attr in ('widget', 'widgetFactory', 'enforceVocabulary'):
        try:
            if hasattr(field, attr):
                value = getattr(field, attr)
                result[attr] = dotted(value) if not isinstance(value, (str, text_type)) else text(value)
        except Exception as exc:
            result['errors'].append(ctx.error('field.%s' % attr, obj=obj, field=name, exception=exc))
    return result


def vocabulary(field, obj, ctx):
    result = {}
    name = field_name(field, ctx, obj)
    for method_name in ('Vocabulary', 'vocabulary', 'getVocabulary'):
        try:
            method = getattr(field, method_name, None)
        except Exception as exc:
            ctx.error('field.vocabulary.capability', obj=obj, field=name, exception=exc)
            continue
        if not callable(method):
            continue
        try:
            value = method(obj)
            result['method'] = method_name
            try:
                result['items'] = [scalar(x) for x in list(value)[:200]]
            except Exception as exc:
                ctx.error('field.vocabulary.items', obj=obj, field=name, exception=exc)
                result['items'] = []
            break
        except Exception as exc:
            ctx.error('field.vocabulary', obj=obj, field=name, exception=exc)
            result['error'] = {'exception_type': exc.__class__.__name__, 'message': text(exc)}
    for attr in ('vocabulary', 'enforceVocabulary'):
        try:
            if hasattr(field, attr):
                result[attr] = scalar(getattr(field, attr))
        except Exception as exc:
            ctx.error('field.vocabulary.%s' % attr, obj=obj, field=name, exception=exc)
    try:
        result['name'] = text(field.getVocabularyName())
    except Exception:
        pass
    return result


def schema(obj, ctx):
    return archetypes_schema(obj, ctx)


def field_values(obj, at_schema, ctx):
    result = {}
    if not at_schema.get('available'):
        return result
    try:
        fields = getattr(obj, 'Schema')().fields()
    except Exception as exc:
        ctx.error('field_values.schema', obj=obj, exception=exc)
        return result
    for field in list(fields)[:MAX_FIELDS]:
        name = field_name(field, ctx, obj)
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
            ctx.error('field.value.content_type', obj=obj, field=name, exception=exc)
        result[name] = item
    return result


def binaries(obj, at_schema, ctx):
    result = []
    if not at_schema.get('available'):
        return result
    try:
        fields = getattr(obj, 'Schema')().fields()
    except Exception as exc:
        ctx.error('binaries.schema', obj=obj, exception=exc)
        return result
    for field in list(fields):
        try:
            field_class = field.__class__.__name__
        except Exception as exc:
            ctx.error('binaries.field_class', obj=obj, exception=exc)
            continue
        if field_class not in ('FileField', 'ImageField'):
            continue
        name = field_name(field, ctx, obj)
        try:
            value = field.getRaw(obj)
        except Exception as exc:
            ctx.error('binary.value', obj=obj, field=name, exception=exc)
            continue
        if value is None:
            continue
        try:
            size = value.getSize()
        except Exception:
            try:
                size = len(value.data)
            except Exception as exc:
                ctx.error('binary.size', obj=obj, field=name, exception=exc)
                size = None
        try:
            filename = text(getattr(value, 'filename', None))
        except Exception as exc:
            ctx.error('binary.filename', obj=obj, field=name, exception=exc)
            filename = None
        result.append({'field': name, 'type': field_class, 'size': size, 'filename': filename})
    return result


def local_roles(obj, ctx):
    roles = safe_call(ctx, 'local_roles', lambda: obj.get_local_roles(), obj=obj, default={})
    blocked = safe_call(ctx, 'local_role_block', lambda: obj.get_local_role_block(), obj=obj)
    try:
        has_roles = bool(getattr(aq_base(obj), '__ac_local_roles__', None))
    except Exception as exc:
        ctx.error('local_roles.persistent_attribute', obj=obj, exception=exc)
        has_roles = False
    return {'roles': dict(roles or {}), 'blocked': blocked, 'has_ac_local_roles': has_roles}


def permissions(obj, ctx):
    result = {}
    try:
        declarations = getattr(obj.__class__, '__ac_permissions__', ())
        for item in declarations:
            try:
                result[text(item[0])] = list(item[1] or ())
            except Exception as exc:
                ctx.error('permissions.item', obj=obj, exception=exc)
    except Exception as exc:
        ctx.error('permissions', obj=obj, exception=exc)
    return result


def workflow(obj, tool, ctx):
    result = {'chain': [], 'review_state': None, 'states_by_chain': {}}
    if tool is None:
        return result
    try:
        result['chain'] = list(tool.getChainForPortalType(ptype(obj)) or ())
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


def references(obj, reference_catalog, ctx):
    result = {'outgoing': [], 'incoming': [], 'broken_outgoing': [], 'broken_incoming': []}
    try:
        for target in obj.getRefs():
            item = {'path': path(target), 'uid': safe_uid(target), 'class': dotted(target)}
            result['outgoing' if item['path'] else 'broken_outgoing'].append(item)
    except Exception as exc:
        ctx.error('references.outgoing', obj=obj, exception=exc)
    if reference_catalog is not None:
        try:
            for backref in reference_catalog.getBackReferences(obj):
                try:
                    target = backref.getObject()
                except Exception as exc:
                    ctx.error('references.incoming.target', obj=obj, exception=exc)
                    target = None
                item = {'uid': safe_uid(backref), 'path': path(target) if target else None}
                result['incoming' if target else 'broken_incoming'].append(item)
        except Exception as exc:
            ctx.error('references.incoming', obj=obj, exception=exc)
    return result


def stored(obj, ctx):
    result = {}
    try:
        values = getattr(aq_base(obj), '__dict__', {})
        for key, value in values.items():
            if key.startswith('_v_') or key.startswith('_p_') or key.startswith('_'):
                continue
            try:
                result[key] = scalar(value)
            except Exception as exc:
                ctx.error('stored_attribute.value', obj=obj, field=key, exception=exc)
    except Exception as exc:
        ctx.error('stored_attributes', obj=obj, exception=exc)
    return result


def summary(obj, wf, reference_catalog, ctx):
    at_schema = schema(obj, ctx)
    return {'path': safe_call(ctx, 'object.path', lambda: path(obj), obj=obj),
            'id': safe_call(ctx, 'object.id', lambda: obj.getId(), obj=obj, default=getattr(obj, 'id', None)),
            'title': safe_call(ctx, 'object.title', lambda: obj.Title(), obj=obj,
                               default=safe_call(ctx, 'object.title_attribute', lambda: obj.title, obj=obj)),
            'portal_type': ptype(obj), 'class': dotted(obj), 'class_hierarchy': hierarchy(obj),
            'interfaces': interfaces(obj), 'archetypes_schema': at_schema,
            'field_values': field_values(obj, at_schema, ctx), 'stored_attributes': stored(obj, ctx),
            'workflow': workflow(obj, wf, ctx), 'local_roles': local_roles(obj, ctx),
            'permissions': permissions(obj, ctx), 'references': references(obj, reference_catalog, ctx),
            'binaries': binaries(obj, at_schema, ctx),
            'folderish': safe_call(ctx, 'object.folderish', lambda: IFolderish.providedBy(obj), obj=obj, default=False)}


def walk(root, ctx):
    stack = [root]
    while stack:
        obj = stack.pop()
        yield obj
        try:
            is_folderish = IFolderish.providedBy(obj)
        except Exception as exc:
            ctx.error('walk.folderish', obj=obj, exception=exc)
            is_folderish = False
        if is_folderish:
            try:
                children = obj.objectValues()
            except Exception as exc:
                ctx.error('walk.objectValues', obj=obj, exception=exc)
                continue
            stack.extend(reversed(list(children or [])))


def type_definition(site, portal_type, ctx):
    try:
        type_info = site.portal_types.getTypeInfo(portal_type)
    except Exception as exc:
        ctx.error('portal_type.definition', obj=site, message=portal_type, exception=exc)
        return None
    if type_info is None:
        return None
    result = {'id': portal_type, 'title': text(getattr(type_info, 'title', None)),
              'factory': text(getattr(type_info, 'factory', None)), 'klass': text(getattr(type_info, 'klass', None)),
              'allowed_content_types': list(getattr(type_info, 'allowed_content_types', ()) or ()),
              'global_allow': bool(getattr(type_info, 'global_allow', False)),
              'filter_content_types': bool(getattr(type_info, 'filter_content_types', False)),
              'default_view': text(getattr(type_info, 'default_view', None)),
              'immediate_view': text(getattr(type_info, 'immediate_view', None)),
              'aliases': dict(getattr(type_info, 'aliases', {}) or {}), 'actions': [],
              'workflow_chain': [], 'permissions': {}}
    try:
        result['actions'] = [scalar(a) for a in type_info.listActions()]
    except Exception as exc:
        ctx.error('portal_type.actions', obj=site, message=portal_type, exception=exc)
    try:
        result['workflow_chain'] = list(site.portal_workflow.getChainForPortalType(portal_type) or ())
    except Exception as exc:
        ctx.error('portal_type.workflow_chain', obj=site, message=portal_type, exception=exc)
    try:
        result['permissions'] = dict(type_info.getPermissionMap())
    except Exception as exc:
        ctx.error('portal_type.permissions', obj=site, message=portal_type, exception=exc)
    return result


def pfg(obj, ctx, depth=0):
    at_schema = schema(obj, ctx)
    result = {'path': safe_call(ctx, 'pfg.path', lambda: path(obj), obj=obj),
              'id': safe_call(ctx, 'pfg.id', lambda: obj.getId(), obj=obj, default=getattr(obj, 'id', None)),
              'title': safe_call(ctx, 'pfg.title', lambda: obj.Title(), obj=obj),
              'class': dotted(obj), 'portal_type': ptype(obj), 'interfaces': interfaces(obj),
              'stored_attributes': stored(obj, ctx), 'archetypes_schema': at_schema,
              'field_values': field_values(obj, at_schema, ctx), 'children': []}
    if depth < MAX_DEPTH:
        try:
            is_folderish = IFolderish.providedBy(obj)
        except Exception as exc:
            ctx.error('pfg.folderish', obj=obj, exception=exc)
            is_folderish = False
        if is_folderish:
            try:
                children = obj.objectValues()
            except Exception as exc:
                ctx.error('pfg.children', obj=obj, exception=exc)
                children = []
            for child in list(children or [])[:500]:
                result['children'].append(pfg(child, ctx, depth + 1))
    return result


def is_pfg(obj):
    pt = ptype(obj) or ''
    cls = dotted(obj) or ''
    return (any(x in pt for x in ('FormFolder', 'FormMailer', 'FormField', 'FormCustomScript'))
            or 'PloneFormGen' in cls or 'Products.PloneFormGen' in cls)


def site_inventory(site, name, label, global_errors):
    ctx = InventoryContext(name)
    wf = safe_call(ctx, 'site.portal_workflow', lambda: site.portal_workflow, obj=site)
    reference_catalog = safe_call(ctx, 'site.reference_catalog', lambda: site.reference_catalog, obj=site)
    counts = Counter(); classes = defaultdict(set); samples = defaultdict(list)
    pfg_objects = []; unknown = []; workflow_assignments = defaultdict(Counter)
    local_role_counts = Counter(); binary_counts = Counter(); binary_bytes = Counter(); total = 0
    try:
        for obj in walk(site, ctx):
            total += 1
            try:
                portal_type = ptype(obj) or '<no portal_type>'
                counts[portal_type] += 1
                classes[portal_type].add(dotted(obj))
            except Exception as exc:
                ctx.error('object.classification', obj=obj, exception=exc)
                portal_type = '<classification error>'
                counts[portal_type] += 1
            if len(samples[portal_type]) < MAX_SAMPLES:
                try:
                    samples[portal_type].append(summary(obj, wf, reference_catalog, ctx))
                except Exception as exc:
                    ctx.error('object.summary', obj=obj, exception=exc)
                    samples[portal_type].append({'path': path(obj), 'portal_type': ptype(obj),
                                                 'class': dotted(obj), 'inspection_failed': True})
            try:
                if is_pfg(obj):
                    pfg_objects.append(pfg(obj, ctx))
            except Exception as exc:
                ctx.error('pfg.detect', obj=obj, exception=exc)
            if portal_type in ('Unknown', '<no portal_type>'):
                try:
                    unknown.append(summary(obj, wf, reference_catalog, ctx))
                except Exception as exc:
                    ctx.error('unknown.summary', obj=obj, exception=exc)
            try:
                if samples[portal_type] and samples[portal_type][-1].get('path') == path(obj):
                    for binary in samples[portal_type][-1].get('binaries', []):
                        binary_counts[binary.get('type')] += 1
                        binary_bytes[binary.get('type')] += binary.get('size') or 0
            except Exception as exc:
                ctx.error('binary.aggregate', obj=obj, exception=exc)
            try:
                for workflow_id in workflow(obj, wf, ctx).get('chain', []):
                    workflow_assignments[portal_type][workflow_id] += 1
            except Exception as exc:
                ctx.error('workflow.aggregate', obj=obj, exception=exc)
            try:
                if local_roles(obj, ctx).get('roles'):
                    local_role_counts[portal_type] += 1
            except Exception as exc:
                ctx.error('local_roles.aggregate', obj=obj, exception=exc)
    except Exception as exc:
        ctx.error('site.walk', obj=site, exception=exc)
    types = {}
    for portal_type in sorted(counts):
        types[portal_type] = {'count': counts[portal_type], 'classes': sorted(x for x in classes[portal_type] if x),
                              'definition': type_definition(site, portal_type, ctx),
                              'workflow_assignments': dict(workflow_assignments[portal_type]),
                              'samples': samples[portal_type]}
    global_errors.extend(ctx.errors)
    return {'site': name, 'path': safe_call(ctx, 'site.path', lambda: site.absolute_url_path(), obj=site),
            'title': label, 'objects_walked': total, 'portal_types': types, 'pfg_objects': pfg_objects,
            'unknown_objects': unknown,
            'binary_summary': {'counts': dict(binary_counts), 'bytes': dict(binary_bytes),
                               'note': 'Binary details are complete for representative samples; aggregate counts are not inferred for unsampled objects.'},
            'objects_with_local_roles': dict(local_role_counts), 'class': dotted(site),
            'class_hierarchy': hierarchy(site), 'interfaces': interfaces(site),
            'inspection_errors': len(ctx.errors)}


def global_inventory(app, errors):
    result = {'portal_types': [], 'workflows': [], 'tools': {}}
    for name in ('portal_types', 'portal_workflow', 'portal_catalog', 'reference_catalog', 'portal_registry'):
        try:
            result['tools'][name] = hasattr(app, name)
        except Exception as exc:
            errors.append({'site': None, 'path': '/', 'portal_type': None, 'class': dotted(app),
                           'operation': 'global.tool.%s' % name, 'field': None,
                           'exception_type': exc.__class__.__name__, 'message': text(exc)})
            result['tools'][name] = False
    try:
        for type_info in app.portal_types.objectValues():
            try:
                result['portal_types'].append({'id': getattr(type_info, 'id', None),
                                               'title': text(getattr(type_info, 'title', None)),
                                               'factory': text(getattr(type_info, 'factory', None)),
                                               'klass': text(getattr(type_info, 'klass', None))})
            except Exception as exc:
                errors.append({'site': None, 'path': '/portal_types', 'portal_type': None,
                               'class': dotted(type_info), 'operation': 'global.portal_type', 'field': None,
                               'exception_type': exc.__class__.__name__, 'message': text(exc)})
    except Exception as exc:
        errors.append({'site': None, 'path': '/', 'portal_type': None, 'class': dotted(app),
                       'operation': 'global.portal_types', 'field': None,
                       'exception_type': exc.__class__.__name__, 'message': text(exc)})
    try:
        workflow_tool = app.portal_workflow
        for definition in workflow_tool.objectValues():
            states = []
            try:
                states = [getattr(state, 'id', None) for state in definition.states.objectValues()]
            except Exception as exc:
                errors.append({'site': None, 'path': None, 'portal_type': None, 'class': dotted(definition),
                               'operation': 'global.workflow.states', 'field': None,
                               'exception_type': exc.__class__.__name__, 'message': text(exc)})
            result['workflows'].append({'id': getattr(definition, 'id', None),
                                        'title': text(getattr(definition, 'title', None)),
                                        'class': dotted(definition), 'states': states})
    except Exception as exc:
        errors.append({'site': None, 'path': '/', 'portal_type': None, 'class': dotted(app),
                       'operation': 'global.workflows', 'field': None,
                       'exception_type': exc.__class__.__name__, 'message': text(exc)})
    return result


def markdown(data):
    lines = ['# Plone 4.3 Read-only Database Inventory', '',
             'Generated by `tools/plone43_inventory.py`. Representative values are bounded; this is not a content export.', '',
             '## Runtime', '', '- Generated: `%s`' % data['generated_at'],
             '- Python: `%s`' % data['runtime']['python'].replace('\n', ' '),
             '- Zope: `%s`' % data['runtime'].get('zope'), '- Plone: `%s`' % data['runtime'].get('plone'),
             '- Read-only mode: `%s`' % data['read_only'], '', '## Inspection errors', '',
             '**Total non-fatal inspection errors:** %s' % len(data['errors']), '']
    if data['errors']:
        lines.extend(['| Site | Path | Portal type | Class | Operation | Field | Exception | Message |',
                      '|---|---|---|---|---|---|---|---|'])
        for error in data['errors'][:5000]:
            vals = [error.get(k) or '' for k in ('site', 'path', 'portal_type', 'class', 'operation', 'field', 'exception_type', 'message')]
            vals = [text(v, 500).replace('|', '\\|').replace('\n', ' ') for v in vals]
            lines.append('| %s |' % ' | '.join(vals))
        if len(data['errors']) > 5000:
            lines.extend(['', 'Only the first 5000 errors are rendered in Markdown; all errors remain in JSON.'])
    else:
        lines.append('None.')
    for site in data['sites']:
        lines.extend(['', '## /%s — %s' % (site['site'], site['title']), '',
                       '**Objects walked:** %s  ' % site['objects_walked'],
                       '**Inspection errors:** %s' % site['inspection_errors'], '',
                       '| Portal type | Count | Runtime classes | Workflow chains |', '|---|---:|---|---|'])
        for portal_type, info in sorted(site['portal_types'].items()):
            lines.append('| `%s` | %s | %s | %s |' % (portal_type, info['count'],
                          '<br>'.join(info['classes']), '<br>'.join(sorted(info['workflow_assignments']))))
        lines.extend(['', '### PloneFormGen', ''])
        if site['pfg_objects']:
            for form in site['pfg_objects']:
                lines.extend(['#### `%s`' % form.get('path'), '', '```json',
                              json.dumps(form, ensure_ascii=False, indent=2, sort_keys=True), '```', ''])
        else:
            lines.append('No PFG objects detected by runtime class/portal-type heuristics.')
        lines.extend(['', '### Binary summary', '', '```json', json.dumps(site['binary_summary'], indent=2, sort_keys=True),
                      '```', '', '### Unknown/no-portal-type objects', ''])
        if site['unknown_objects']:
            lines.extend(['```json', json.dumps(site['unknown_objects'], ensure_ascii=False, indent=2, sort_keys=True), '```'])
        else:
            lines.append('None detected by the inventory heuristics.')
        lines.extend(['', '### Representative object samples', ''])
        for portal_type, info in sorted(site['portal_types'].items()):
            for sample in info['samples']:
                lines.extend(['<details><summary><code>%s</code> — %s</summary>' % (portal_type, sample.get('path')),
                              '', '```json', json.dumps(sample, ensure_ascii=False, indent=2, sort_keys=True),
                              '```', '</details>', ''])
    return '\n'.join(lines) + '\n'


def parse_inventory_args(argv, script_name):
    """Return only arguments intended for this inventory script.

    The documented Plone/Zope ``run`` interface says argv[0] is the script
    name.  The Plone 4.3-era control-script implementation normally removes
    Python's ``-c`` marker before execfile(), but some deployed 4.3 wrappers
    leave the marker in argv.  We accept only these two concrete shapes:

        [script_name, script_args...]
        ['-c', script_name, script_args...]

    A ``-c`` appearing elsewhere is not silently ignored and therefore still
    produces an invocation error.  This is deliberately narrower than
    filtering unknown options.
    """
    argv = list(argv)
    if not argv:
        raise SystemExit('Unable to determine inventory script arguments.')

    basename = os.path.basename(script_name)
    first = os.path.basename(argv[0])
    if first == basename:
        args = argv[1:]
    elif argv[0] == '-c' and len(argv) > 1 and os.path.basename(argv[1]) == basename:
        args = argv[2:]
    else:
        raise SystemExit('Unexpected Plone/Zope run argv shape: %r' % argv)
    return parse_output_dir(args)


def parse_output_dir(args):
    """Parse inventory options; reject all unknown options."""
    if not args:
        return '/tmp/plone43-inventory'
    if len(args) == 1 and args[0].startswith('--output-dir='):
        value = args[0].split('=', 1)[1]
        if not value:
            raise SystemExit('--output-dir requires a directory.')
        return value
    if args[0] == '--output-dir':
        if len(args) != 2 or args[1].startswith('-'):
            raise SystemExit('Usage: bin/instance run tools/plone43_inventory.py --output-dir /path')
        return args[1]
    if args[0].startswith('-'):
        raise SystemExit('Unexpected option %s. Use --output-dir /path.' % args[0])
    raise SystemExit('Unexpected inventory argument %s. Use --output-dir /path.' % args[0])


def run(app, outdir):
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    errors = []
    result = {'schema_version': 2, 'read_only': True,
              'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
              'runtime': {'python': sys.version, 'zope': None, 'plone': None},
              'global': global_inventory(app, errors), 'sites': [], 'errors': errors}
    try:
        import Zope2
        result['runtime']['zope'] = text(getattr(Zope2, '__version__', None))
    except Exception as exc:
        errors.append({'site': None, 'path': None, 'portal_type': None, 'class': None,
                       'operation': 'runtime.zope_version', 'field': None,
                       'exception_type': exc.__class__.__name__, 'message': text(exc)})
    try:
        import Products.CMFPlone
        result['runtime']['plone'] = text(getattr(Products.CMFPlone, '__version__', None))
    except Exception as exc:
        errors.append({'site': None, 'path': None, 'portal_type': None, 'class': None,
                       'operation': 'runtime.plone_version', 'field': None,
                       'exception_type': exc.__class__.__name__, 'message': text(exc)})
    for name, site_path, label in SITES:
        try:
            site = app.unrestrictedTraverse(site_path.lstrip('/'))
            result['sites'].append(site_inventory(site, name, label, errors))
        except Exception as exc:
            errors.append({'site': name, 'path': site_path, 'portal_type': None, 'class': None,
                           'operation': 'site.open', 'field': None,
                           'exception_type': exc.__class__.__name__, 'message': text(exc),
                           'traceback': traceback.format_exc()})
    with open(os.path.join(outdir, 'plone43_inventory.json'), 'w') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, sort_keys=True)
    with open(os.path.join(outdir, 'plone43_inventory.md'), 'wb') as handle:
        handle.write(markdown(result).encode('utf-8'))
    print('Inventory written to %s' % os.path.abspath(outdir))


if 'app' not in globals():
    raise SystemExit('Use the Plone 4.3 bin/instance run command; do not execute with system Python.')
run(app, parse_inventory_args(sys.argv, globals().get('__file__', 'plone43_inventory.py')))
