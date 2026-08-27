#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify migrated EasyForms and their mailer action models.

Compares pfg-easyform.jsonl against target EasyForm objects. XML models are
canonicalized before comparison so formatting differences do not count.
Also reports MailHost readiness without requiring or exposing SMTP secrets.
"""
import json
import os
import sys

from lxml import etree
from zope.component.hooks import setSite

SCRIPT = 'plone52_verify_easyforms.py'


def parse_input_dir(argv):
    values = list(argv)
    pos = max(i for i, value in enumerate(values)
              if os.path.basename(value) == SCRIPT)
    args = values[pos + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        return os.path.abspath(args[0].split('=', 1)[1])
    if len(args) == 2 and args[0] == '--input-dir':
        return os.path.abspath(args[1])
    raise SystemExit('Use --input-dir=/migration-data/export')


def canonical_xml(value):
    if value is None:
        return b''
    if isinstance(value, str):
        value = value.encode('utf-8')
    root = etree.fromstring(value)
    return etree.tostring(root, method='c14n')


def target_object(app, record):
    site = app[record['site']]
    source = record['source_path'].strip('/').split('/')
    current = site
    for part in source[1:]:
        current = current[part]
    return site, current


def workflow_state(site, obj):
    try:
        return site.portal_workflow.getInfoFor(obj, 'review_state', None)
    except Exception:
        return None


def local_roles(obj):
    try:
        return sorted((str(p), tuple(sorted(str(r) for r in roles)))
                      for p, roles in obj.get_local_roles())
    except Exception:
        return []


def mailer_summary(actions_model):
    result = []
    if not actions_model:
        return result
    if isinstance(actions_model, str):
        actions_model = actions_model.encode('utf-8')
    root = etree.fromstring(actions_model)
    ns = {'s': 'http://namespaces.plone.org/supermodel/schema'}
    for field in root.xpath('.//s:field', namespaces=ns):
        if field.get('type') != 'collective.easyform.actions.Mailer':
            continue
        item = {'name': field.get('name')}
        for name in ('recipient_name', 'recipient_email', 'replyto_field',
                     'subject_field', 'msg_subject', 'to_field'):
            node = field.find('{http://namespaces.plone.org/supermodel/schema}%s' % name)
            if node is not None and node.text:
                item[name] = node.text
        result.append(item)
    return result


def mailhost_summary(site):
    mh = getattr(site, 'MailHost', None)
    if mh is None:
        return {'present': False}
    return {
        'present': True,
        'smtp_host': getattr(mh, 'smtp_host', None),
        'smtp_port': getattr(mh, 'smtp_port', None),
        'smtp_uid_configured': bool(getattr(mh, 'smtp_uid', None)),
        'smtp_password_configured': bool(getattr(mh, 'smtp_pwd', None)),
    }


def run(app, input_dir):
    source = os.path.join(input_dir, 'pfg-easyform.jsonl')
    if not os.path.isfile(source):
        raise SystemExit('Missing %s' % source)

    report = {'forms': [], 'sites': {}}
    total_differences = 0
    current_site = None
    with open(source, 'r', encoding='utf-8') as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            site, obj = target_object(app, record)
            if current_site is not site:
                setSite(site)
                current_site = site
            diffs = []
            if getattr(obj, 'portal_type', None) != 'EasyForm':
                diffs.append('target type is %r' % getattr(obj, 'portal_type', None))
            try:
                if canonical_xml(record.get('fields_model')) != canonical_xml(obj.fields_model):
                    diffs.append('fields_model differs')
            except Exception as exc:
                diffs.append('fields_model parse/compare error: %r' % exc)
            try:
                if canonical_xml(record.get('actions_model')) != canonical_xml(obj.actions_model):
                    diffs.append('actions_model differs')
            except Exception as exc:
                diffs.append('actions_model parse/compare error: %r' % exc)

            metadata = record.get('metadata') or {}
            if metadata:
                expected_state = metadata.get('workflow_state')
                if expected_state is not None and workflow_state(site, obj) != expected_state:
                    diffs.append('workflow state differs')
                expected_roles = sorted((str(p), tuple(sorted(str(r) for r in roles)))
                                        for p, roles in metadata.get('local_roles') or ())
                if local_roles(obj) != expected_roles:
                    diffs.append('local roles differ')
                exclude = metadata.get('exclude_from_nav')
                if exclude is not None and bool(getattr(obj, 'exclude_from_nav', False)) != bool(exclude):
                    diffs.append('exclude_from_nav differs')

            mailers = mailer_summary(record.get('actions_model'))
            item = {
                'site': record['site'],
                'source_path': record['source_path'],
                'status': 'ok' if not diffs else 'different',
                'differences': diffs,
                'mailers': mailers,
            }
            report['forms'].append(item)
            total_differences += len(diffs)
            print('%s: %s (%d mailer actions)' %
                  (record['source_path'], item['status'].upper(), len(mailers)))
            for mailer in mailers:
                print('  MAILER %s recipient=%r to_field=%r replyto=%r subject=%r' %
                      (mailer.get('name'), mailer.get('recipient_email'),
                       mailer.get('to_field'), mailer.get('replyto_field'),
                       mailer.get('msg_subject')))
            for diff in diffs:
                print('  DIFF: %s' % diff)

    setSite(None)
    for site_id in sorted(set(item['site'] for item in report['forms'])):
        site = app[site_id]
        setSite(site)
        summary = mailhost_summary(site)
        report['sites'][site_id] = {'mailhost': summary}
        print('%s MailHost: host=%r port=%r uid_configured=%s password_configured=%s' %
              (site_id, summary.get('smtp_host'), summary.get('smtp_port'),
               summary.get('smtp_uid_configured'),
               summary.get('smtp_password_configured')))
    setSite(None)

    report['total_differences'] = total_differences
    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    path = os.path.join(report_dir, 'plone52-easyform-parity.json')
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('EasyForm parity report: %s' % path)
    print('Total differences: %d' % total_differences)


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
