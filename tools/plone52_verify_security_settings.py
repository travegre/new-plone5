#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify migrated users/groups/roles and compatible site settings.

Compares the Plone 5.2 target against ``security-settings.json`` exported from
Plone 4.3. Virtual PAS groups such as AuthenticatedUsers are ignored because
they are computed automatically rather than stored as ordinary groups.
"""
import json
import os
import sys

import plone.api
from zope.component.hooks import setSite

SCRIPT = 'plone52_verify_security_settings.py'
VIRTUAL_GROUPS = frozenset((
    'AuthenticatedUsers', 'Anonymous Users', 'Authenticated Users',
))
IGNORED_ROLES = frozenset(('Authenticated',))


def parse_input_dir(argv):
    values = list(argv)
    positions = [i for i, value in enumerate(values)
                 if os.path.basename(value) == SCRIPT]
    if not positions:
        raise SystemExit('Unexpected instance-run argv: %r' % values)
    args = values[positions[-1] + 1:]
    if len(args) == 1 and args[0].startswith('--input-dir='):
        return os.path.abspath(args[0].split('=', 1)[1])
    if len(args) == 2 and args[0] == '--input-dir':
        return os.path.abspath(args[1])
    raise SystemExit('Use --input-dir=/migration-data/export')


def role_set(values):
    return set(str(v) for v in (values or ()) if str(v) not in IGNORED_ROLES)


def target_user_roles(site, user_id):
    try:
        principal = site.acl_users.getUserById(user_id)
        if principal is None:
            return set()
        wrapped = principal.__of__(site.acl_users)
        return role_set(wrapped.getRoles())
    except Exception:
        return set()


def target_group_roles(site, group_id):
    try:
        group = site.portal_groups.getGroupById(group_id)
        if group is None:
            return set()
        return role_set(group.getRoles())
    except Exception:
        return set()


def target_groups_for_user(user_id):
    try:
        groups = plone.api.group.get_groups(username=user_id)
        return set(str(g.getId()) for g in groups
                   if str(g.getId()) not in VIRTUAL_GROUPS)
    except Exception:
        return set()


def local_roles_map(obj):
    try:
        return dict((str(p), role_set(roles)) for p, roles in obj.get_local_roles())
    except Exception:
        return {}


def compare_site(site, source):
    diffs = []

    # Identity.
    if str(site.Title() or '') != str(source.get('title') or ''):
        diffs.append('site title differs')
    if str(site.Description() or '') != str(source.get('description') or ''):
        diffs.append('site description differs')

    # Users and memberships/roles.
    source_users = source.get('users') or ()
    for record in source_users:
        user_id = str(record.get('id') or '')
        if not user_id:
            continue
        user = plone.api.user.get(username=user_id)
        if user is None:
            diffs.append('missing user %s' % user_id)
            continue
        expected_roles = role_set(record.get('roles'))
        actual_roles = target_user_roles(site, user_id)
        if not expected_roles.issubset(actual_roles):
            diffs.append('user roles differ %s: missing %s' %
                         (user_id, sorted(expected_roles - actual_roles)))
        expected_groups = set(str(g) for g in record.get('groups') or ()
                              if str(g) not in VIRTUAL_GROUPS)
        actual_groups = target_groups_for_user(user_id)
        if expected_groups != actual_groups:
            diffs.append('user groups differ %s: source=%s target=%s' %
                         (user_id, sorted(expected_groups), sorted(actual_groups)))

    # Real groups and their roles/members.
    for record in source.get('groups') or ():
        group_id = str(record.get('id') or '')
        if not group_id or group_id in VIRTUAL_GROUPS:
            continue
        group = plone.api.group.get(groupname=group_id)
        if group is None:
            diffs.append('missing group %s' % group_id)
            continue
        expected_roles = role_set(record.get('roles'))
        actual_roles = target_group_roles(site, group_id)
        if not expected_roles.issubset(actual_roles):
            diffs.append('group roles differ %s: missing %s' %
                         (group_id, sorted(expected_roles - actual_roles)))
        expected_members = set(str(m) for m in record.get('members') or ())
        try:
            actual_members = set(str(m.getId()) for m in group.getGroupMembers())
        except Exception:
            actual_members = set()
        if expected_members != actual_members:
            diffs.append('group members differ %s: source=%s target=%s' %
                         (group_id, sorted(expected_members), sorted(actual_members)))

    # Site-root local roles.
    expected_local = dict((str(p), role_set(roles))
                          for p, roles in source.get('site_local_roles') or ())
    actual_local = local_roles_map(site)
    for principal, roles in expected_local.items():
        missing = roles - actual_local.get(principal, set())
        if missing:
            diffs.append('site local roles differ %s: missing %s' %
                         (principal, sorted(missing)))

    # Compatible MailHost fields; password intentionally not checked.
    source_mail = source.get('mailhost') or {}
    target_mail = getattr(site, 'MailHost', None)
    if target_mail is not None:
        for name in ('smtp_host', 'smtp_port', 'smtp_uid'):
            if name not in source_mail or source_mail[name] is None:
                continue
            actual = getattr(target_mail, name, None)
            if str(actual or '') != str(source_mail[name] or ''):
                diffs.append('MailHost %s differs: source=%r target=%r' %
                             (name, source_mail[name], actual))

    return diffs


def run(app, input_dir):
    path = os.path.join(input_dir, 'security-settings.json')
    if not os.path.isfile(path):
        raise SystemExit('Missing %s' % path)
    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)

    report = {'sites': {}, 'total_differences': 0}
    try:
        for source in payload.get('sites') or ():
            site_id = str(source.get('id') or '')
            site = app.get(site_id)
            if site is None:
                diffs = ['missing target site']
            else:
                setSite(site)
                diffs = compare_site(site, source)
            report['sites'][site_id] = {
                'status': 'ok' if not diffs else 'different',
                'differences': diffs,
            }
            report['total_differences'] += len(diffs)
            print('%s: %s (%d differences)' %
                  (site_id, 'OK' if not diffs else 'DIFFERENT', len(diffs)))
            for diff in diffs:
                print('  %s' % diff)
    finally:
        setSite(None)

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'plone52-security-settings-parity.json')
    with open(report_path, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('Security/settings parity report: %s' % report_path)
    print('Total differences: %d' % report['total_differences'])


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
