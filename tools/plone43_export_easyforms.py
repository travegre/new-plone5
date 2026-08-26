#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export PloneFormGen forms as EasyForm XML models on Plone 4.3.

This exporter is intentionally self-contained.  It follows the conversion
semantics used by collective.easyform's ``pfg-migration-plone4`` branch, but
it does *not* install collective.easyform (or its Plone-5-era dependency
stack) into the Plone 4.3 buildout.

The current IMI sites use the PFG types covered below: string, selection and
text fields plus mailer adapters.  Unsupported PFG field/action types are
reported rather than silently converted.

Run::

    bin/instance run src/plone43_export_easyforms.py \
        --output-dir=/plone/instance/src/export
"""
from __future__ import print_function

import json
import os
import sys
import traceback

from lxml import etree
from Products.PloneFormGen.content.actionAdapter import FormActionAdapter
from Products.PloneFormGen.content.fieldsBase import BaseFormField

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
SCRIPT_BASENAME = 'plone43_export_easyforms.py'
SCHEMA_NS = 'http://namespaces.plone.org/supermodel/schema'
EASYFORM_NS = 'http://namespaces.plone.org/supermodel/easyform'
FORM_NS = 'http://namespaces.plone.org/supermodel/form'

try:
    unicode_type = unicode
except NameError:  # pragma: no cover
    unicode_type = str


def to_unicode(value):
    if value is None:
        return None
    if isinstance(value, unicode_type):
        return value
    if isinstance(value, str):
        return value.decode('utf-8')
    return unicode_type(value)


def normalize(value):
    if isinstance(value, unicode_type):
        return value
    if isinstance(value, str):
        return value.decode('utf-8')
    if isinstance(value, dict):
        return dict((normalize(k), normalize(v)) for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return [normalize(v) for v in value]
    return value


def json_line(value):
    rendered = json.dumps(normalize(value), ensure_ascii=False, sort_keys=True)
    if isinstance(rendered, unicode_type):
        rendered = rendered.encode('utf-8')
    return rendered + b'\n'


def parse_output_dir(argv):
    values = list(argv)
    positions = [i for i, value in enumerate(values)
                 if os.path.basename(value) == SCRIPT_BASENAME]
    if not positions:
        raise SystemExit('Unexpected instance-run argv: %r' % values)
    args = values[positions[-1] + 1:]
    if len(args) == 1 and args[0].startswith('--output-dir='):
        result = args[0].split('=', 1)[1]
    elif len(args) == 2 and args[0] == '--output-dir':
        result = args[1]
    else:
        raise SystemExit('Use --output-dir=/plone/instance/src/export')
    if not result:
        raise SystemExit('--output-dir may not be empty')
    return os.path.abspath(result)


def object_path(obj):
    try:
        return to_unicode(obj.absolute_url_path())
    except Exception:
        return None


def safe_call(obj, name, default=None):
    method = getattr(obj, name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:
        return default


def rich_raw(value):
    if value is None:
        return None
    raw = getattr(value, 'raw', None)
    return to_unicode(raw if raw is not None else value)


def new_model():
    model = etree.Element('{%s}model' % SCHEMA_NS,
                          nsmap={None: SCHEMA_NS,
                                 'easyform': EASYFORM_NS,
                                 'form': FORM_NS})
    schema = etree.SubElement(model, '{%s}schema' % SCHEMA_NS)
    return model, schema


def add_text(parent, name, value):
    if value is None:
        return
    node = etree.SubElement(parent, '{%s}%s' % (SCHEMA_NS, name))
    if isinstance(value, (list, tuple)):
        value = u' '.join(to_unicode(v) for v in value)
    else:
        value = to_unicode(value)
    node.text = value


def add_list(parent, name, values):
    node = etree.SubElement(parent, '{%s}%s' % (SCHEMA_NS, name))
    for value in values or ():
        value = to_unicode(value)
        child = etree.SubElement(node, '{%s}element' % SCHEMA_NS)
        if u'|' in value:
            key, value = value.split(u'|', 1)
            child.set('key', key)
        child.text = value


def field_properties(obj):
    props = {}
    for field in obj.Schema().fields():
        name = field.getName()
        try:
            accessor = field.getEditAccessor(obj)
            props[name] = accessor()
        except Exception:
            try:
                props[name] = field.get(obj)
            except Exception:
                pass
    return props


def fix_tales(value):
    value = to_unicode(value or u'')
    if value == u'here/memberEmail':
        return u"python:member and member.getProperty('email', '') or ''"
    if value == u'here/memberFullName':
        return u"python:member and member.getProperty('fullname', '') or ''"
    if value == u'here/memberId':
        return u"python:member and member.getProperty('id', '') or ''"
    return value


def set_easyform_attr(node, name, value):
    if value in (None, u'', ''):
        return
    node.set('{%s}%s' % (EASYFORM_NS, name), to_unicode(value))


def append_pfg_field(schema, obj):
    pt = obj.portal_type
    mapping = {
        'FormStringField': 'zope.schema.TextLine',
        'FormSelectionField': 'zope.schema.Choice',
        'FormTextField': 'zope.schema.Text',
        'FormLinesField': 'zope.schema.Text',
        'FormBooleanField': 'zope.schema.Bool',
        'FormIntegerField': 'zope.schema.Int',
        'FormMultiSelectionField': 'zope.schema.Set',
    }
    target_type = mapping.get(pt)
    if target_type is None:
        raise ValueError('Unsupported PFG field type: %s' % pt)

    props = field_properties(obj)
    field = etree.SubElement(schema, '{%s}field' % SCHEMA_NS)
    field.set('name', to_unicode(obj.getId()))
    field.set('type', target_type)

    add_text(field, 'title', props.get('title') or safe_call(obj, 'Title', obj.getId()))
    if props.get('description'):
        add_text(field, 'description', props.get('description'))
    if props.get('required') is False:
        add_text(field, 'required', u'False')
    default = props.get('fgDefault')
    if default not in (None, u'', '') and not isinstance(default, (list, tuple)):
        add_text(field, 'default', default)

    vocabulary = props.get('fgVocabulary')
    if vocabulary:
        if target_type == 'zope.schema.Set':
            value_type = etree.SubElement(field, '{%s}value_type' % SCHEMA_NS)
            value_type.set('type', 'zope.schema.Choice')
            add_list(value_type, 'values', vocabulary)
        else:
            add_list(field, 'values', vocabulary)

    for source_name, target_name in (
        ('fgTDefault', 'TDefault'),
        ('fgTEnabled', 'TEnabled'),
        ('fgTValidator', 'TValidator'),
        ('hidden', 'THidden'),
        ('serverSide', 'serverSide'),
    ):
        value = props.get(source_name)
        if value not in (None, u'', '', False):
            set_easyform_attr(field, target_name,
                              fix_tales(value) if source_name.startswith('fgT') else value)
    return field


def fields_model(form):
    model, schema = new_model()
    for obj in form.objectValues():
        if isinstance(obj, BaseFormField):
            append_pfg_field(schema, obj)
    return etree.tostring(model, pretty_print=True, encoding='utf-8')


def append_mailer(schema, obj):
    props = field_properties(obj)
    field = etree.SubElement(schema, '{%s}field' % SCHEMA_NS)
    field.set('name', to_unicode(obj.getId()))
    field.set('type', 'collective.easyform.actions.Mailer')

    simple = (
        'title', 'description', 'recipient_name', 'recipient_email',
        'replyto_field', 'subject_field', 'msg_subject', 'body_pre',
        'body_post', 'body_footer', 'body_type', 'to_field',
        'cc_recipients', 'bcc_recipients', 'recipientOverride',
        'subjectOverride', 'senderOverride', 'ccOverride', 'bccOverride',
    )
    for name in simple:
        value = props.get(name)
        if value not in (None, u'', ''):
            add_text(field, name, value)

    for name in ('showFields', 'xinfo_headers', 'additional_headers'):
        value = props.get(name)
        if value:
            add_list(field, name, value)

    for name in ('showAll', 'includeEmpties'):
        value = props.get(name)
        if value is not None:
            add_text(field, name, u'True' if bool(value) else u'False')

    condition = props.get('execCondition')
    if condition:
        set_easyform_attr(field, 'execCondition', condition)

    # Deliberately omit PFG's body_pt.  EasyForm will use its own default
    # mail template, matching the upstream PFG migration helper behavior.
    return field


def actions_model(form):
    model, schema = new_model()
    for obj in form.objectValues():
        if not isinstance(obj, FormActionAdapter):
            continue
        if obj.portal_type != 'FormMailerAdapter':
            raise ValueError('Unsupported PFG action type: %s' % obj.portal_type)
        append_mailer(schema, obj)
    return etree.tostring(model, pretty_print=True, encoding='utf-8')


def fix_model_expressions(model):
    if not model:
        return model
    replacements = (
        (b"request.form['", b"request.form['form.widgets."),
        (b"request.form.get('", b"request.form.get('form.widgets."),
        (b"member and member.id or ''",
         b"member and member.getProperty('id', '') or ''"),
    )
    for old, new in replacements:
        model = model.replace(old, new)
    for fieldname in ('email', 'replyto'):
        old = ('request/form/%s' % fieldname).encode('utf-8')
        new = ("python: request.form.get('form.widgets.%s')" % fieldname).encode('utf-8')
        model = model.replace(old, new)
    return model


def export_form(site_name, obj):
    return {
        'site': site_name,
        'source_path': object_path(obj),
        'id': safe_call(obj, 'getId', getattr(obj, 'id', None)),
        'title': safe_call(obj, 'Title', getattr(obj, 'title', None)),
        'description': safe_call(obj, 'Description', None),
        'target_type': 'EasyForm',
        'fields_model': fix_model_expressions(fields_model(obj)),
        'actions_model': fix_model_expressions(actions_model(obj)),
        'form_tabbing': False,
    }


def run(app, output_dir):
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, 'pfg-easyform.jsonl')
    error_path = os.path.join(output_dir, 'reports', 'pfg-easyform-errors.json')
    report_dir = os.path.dirname(error_path)
    if not os.path.isdir(report_dir):
        os.makedirs(report_dir)

    exported = 0
    errors = []
    with open(output_path, 'wb') as handle:
        for site_name in SITES:
            try:
                site = app.unrestrictedTraverse(site_name)
                brains = site.portal_catalog(portal_type='FormFolder')
            except Exception as exc:
                errors.append({'site': site_name, 'operation': 'catalog',
                               'error': repr(exc),
                               'traceback': traceback.format_exc()})
                continue
            for brain in brains:
                try:
                    obj = brain.getObject()
                    record = export_form(site_name, obj)
                    thanks_id = safe_call(obj, 'getThanksPage', None)
                    thanks = obj.get(thanks_id, None) if thanks_id else None
                    if thanks is not None:
                        record.update({
                            'thankstitle': to_unicode(getattr(thanks, 'title', None)),
                            'thanksdescription': safe_call(thanks, 'Description', None),
                            'showAll': getattr(thanks, 'showAll', None),
                            'showFields': getattr(thanks, 'showFields', None),
                            'includeEmpties': getattr(thanks, 'includeEmpties', None),
                            'thanksPrologue': rich_raw(getattr(thanks, 'thanksPrologue', None)),
                            'thanksEpilogue': rich_raw(getattr(thanks, 'thanksEpilogue', None)),
                        })
                    handle.write(json_line(record))
                    exported += 1
                except Exception as exc:
                    errors.append({
                        'site': site_name,
                        'source_path': getattr(brain, 'getPath', lambda: None)(),
                        'operation': 'export_form', 'error': repr(exc),
                        'traceback': traceback.format_exc(),
                    })

    rendered = json.dumps(normalize(errors), ensure_ascii=False, indent=2,
                          sort_keys=True)
    if isinstance(rendered, unicode_type):
        rendered = rendered.encode('utf-8')
    with open(error_path, 'wb') as handle:
        handle.write(rendered)
        handle.write(b'\n')

    print('EasyForm migration models: %s' % output_path)
    print('Exported FormFolders: %d' % exported)
    print('Errors: %d' % len(errors))


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 4.3 buildout.')
run(app, parse_output_dir(sys.argv))
