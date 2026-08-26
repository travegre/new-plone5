#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export PloneFormGen FormFolders as EasyForm migration models.

This is a read-only Plone 4.3/Python 2 pass.  It deliberately uses the
migration helpers supplied by collective.easyform's Plone-4 migration branch
instead of reimplementing the PFG->EasyForm XML conversion.

The EasyForm package does not need to be installed into the Plone site; its
Python code only needs to be present on the buildout path so these imports are
available::

    from collective.easyform.migration.fields import fields_model
    from collective.easyform.migration.actions import actions_model

Run::

    bin/instance run src/plone43_export_easyforms.py \
        --output-dir=/plone/instance/src/export

Output: ``pfg-easyform.jsonl`` in the existing export directory.
"""
from __future__ import print_function

import json
import os
import sys
import traceback

SITES = ('portal', 'dezurstva', 'kiestra', 'preiskave', 'nadomescanja')
SCRIPT_BASENAME = 'plone43_export_easyforms.py'

try:
    unicode_type = unicode
except NameError:  # pragma: no cover
    unicode_type = str

try:
    from collective.easyform.migration.fields import fields_model
    from collective.easyform.migration.actions import actions_model
except ImportError:
    raise SystemExit(
        'Missing collective.easyform Plone-4 migration helpers. Add the '
        'migration_features_1.x EasyForm code to the old buildout path; the '
        'product does NOT need to be installed into the Plone site.')


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


def fix_model_expressions(model):
    if not model:
        return model
    replacements = (
        ("request.form['", "request.form['form.widgets."),
        ("request.form.get('", "request.form.get('form.widgets."),
        ("member and member.id or ''",
         "member and member.getProperty('id', '') or ''"),
    )
    for old, new in replacements:
        model = model.replace(old, new)
    for fieldname in ('email', 'replyto'):
        old = 'request/form/%s' % fieldname
        new = "python: request.form.get('form.widgets.%s')" % fieldname
        model = model.replace(old, new)
    return model


def rich_raw(value):
    if value is None:
        return None
    raw = getattr(value, 'raw', None)
    return to_unicode(raw if raw is not None else value)


def export_form(site_name, obj):
    record = {
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
    return record


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
                errors.append({
                    'site': site_name, 'operation': 'catalog',
                    'error': repr(exc), 'traceback': traceback.format_exc()})
                continue
            for brain in brains:
                try:
                    obj = brain.getObject()
                    handle.write(json_line(export_form(site_name, obj)))
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
