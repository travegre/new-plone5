#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import compatible Plone 4.3 users/groups/roles and site settings.

Reads ``security-settings.json`` created by
``plone43_export_security_settings.py``.  Users are recreated with random,
unknown passwords because the normal export deliberately contains no password
material.  Administrators must reset passwords (or we can add a separate,
carefully controlled PAS password-hash migration after verifying compatibility).
"""
import json
import os
import secrets
import sys

import plone.api
from zope.component.hooks import setSite

SCRIPT = 'plone52_import_security_settings.py'


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


def create_groups(site, records):
    created = existing = 0
    for record in records:
        group_id = str(record.get('id') or '')
        if not group_id:
            continue
        if plone.api.group.get(groupname=group_id) is None:
            plone.api.group.create(
                groupname=group_id,
                title=record.get('title') or group_id,
                description=record.get('description') or '',
                roles=tuple(record.get('roles') or ()),
            )
            created += 1
        else:
            existing += 1
    return created, existing


def create_users(site, records):
    created = existing = 0
    reset_required = []
    for record in records:
        user_id = str(record.get('id') or '')
        if not user_id:
            continue
        if plone.api.user.get(username=user_id) is None:
            props = dict(record.get('properties') or {})
            email = props.pop('email', '') or None
            # Deliberately unknown to operators/users; account exists so roles
            # and ownership work, but a real password must be reset separately.
            password = secrets.token_urlsafe(32)
            plone.api.user.create(
                username=user_id,
                password=password,
                email=email,
                properties=props,
                roles=tuple(record.get('roles') or ()),
            )
            created += 1
            reset_required.append(user_id)
        else:
            existing += 1
    return created, existing, reset_required


def add_memberships(records):
    added = 0
    for record in records:
        user_id = str(record.get('id') or '')
        if not user_id or plone.api.user.get(username=user_id) is None:
            continue
        for group_id in record.get('groups') or ():
            group_id = str(group_id)
            if plone.api.group.get(groupname=group_id) is None:
                continue
            try:
                plone.api.group.add_user(groupname=group_id, username=user_id)
                added += 1
            except Exception:
                # Membership may already exist; importer is intentionally
                # idempotent.
                pass
    return added


def apply_site_local_roles(site, records):
    count = 0
    for principal, roles in records or ():
        try:
            site.manage_setLocalRoles(str(principal), tuple(str(r) for r in roles))
            count += 1
        except Exception:
            pass
    return count


def apply_site_properties(site, properties):
    changed = []
    props_tool = getattr(site, 'portal_properties', None)
    sheet = getattr(props_tool, 'site_properties', None) if props_tool is not None else None
    if sheet is not None:
        for name, value in (properties or {}).items():
            try:
                if sheet.hasProperty(name):
                    sheet.manage_changeProperties(**{name: value})
                    changed.append(name)
            except Exception:
                pass
    default_language = (properties or {}).get('default_language')
    if default_language:
        languages = getattr(site, 'portal_languages', None)
        setter = getattr(languages, 'setDefaultLanguage', None)
        if callable(setter):
            try:
                setter(str(default_language))
                if 'default_language' not in changed:
                    changed.append('default_language')
            except Exception:
                pass
    return changed


def apply_mailhost(site, record):
    if not record:
        return []
    mh = getattr(site, 'MailHost', None)
    if mh is None:
        return []
    changed = []
    for name in ('smtp_host', 'smtp_port', 'smtp_uid'):
        if name not in record or record[name] is None:
            continue
        try:
            setattr(mh, name, record[name])
            changed.append(name)
        except Exception:
            pass
    return changed


def apply_workflow_chains(site, chains):
    """Apply a source chain only when every named workflow exists in target."""
    tool = getattr(site, 'portal_workflow', None)
    if tool is None:
        return []
    applied = []
    known = set(tool.objectIds())
    for type_id, chain in (chains or {}).items():
        if not chain or not all(name in known for name in chain):
            continue
        if type_id not in site.portal_types.objectIds():
            continue
        try:
            tool.setChainForPortalTypes((str(type_id),), tuple(str(x) for x in chain))
            applied.append(str(type_id))
        except Exception:
            pass
    return applied


def run(app, input_dir):
    path = os.path.join(input_dir, 'security-settings.json')
    if not os.path.isfile(path):
        raise SystemExit('Missing %s; run the Plone 4.3 security/settings exporter first.' % path)
    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)

    import transaction
    report = {'sites': {}, 'password_resets_required': {}}
    try:
        for record in payload.get('sites') or ():
            site_id = str(record.get('id') or '')
            site = app.get(site_id)
            if site is None:
                print('Missing target site: %s' % site_id)
                continue
            setSite(site)

            groups_created, groups_existing = create_groups(site, record.get('groups') or ())
            users_created, users_existing, resets = create_users(site, record.get('users') or ())
            memberships = add_memberships(record.get('users') or ())
            local_roles = apply_site_local_roles(site, record.get('site_local_roles') or ())
            props = apply_site_properties(site, record.get('properties') or {})
            mail = apply_mailhost(site, record.get('mailhost'))
            workflows = apply_workflow_chains(site, record.get('workflow_chains') or {})

            try:
                site.reindexObject()
            except Exception:
                pass

            report['sites'][site_id] = {
                'groups_created': groups_created,
                'groups_existing': groups_existing,
                'users_created': users_created,
                'users_existing': users_existing,
                'memberships_added': memberships,
                'site_local_roles_applied': local_roles,
                'site_properties_applied': props,
                'mailhost_fields_applied': mail,
                'workflow_chains_applied': workflows,
                'smtp_password_required': bool((record.get('mailhost') or {}).get('smtp_password_configured')),
            }
            report['password_resets_required'][site_id] = resets
            print('%s: users +%d/%d existing, groups +%d/%d existing, memberships %d' %
                  (site_id, users_created, users_existing,
                   groups_created, groups_existing, memberships))
            transaction.commit()
    finally:
        setSite(None)

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'plone52-security-settings-import.json')
    with open(report_path, 'w', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('Security/settings report: %s' % report_path)
    print('User passwords were NOT migrated; newly-created users require password reset.')
    print('SMTP password was NOT migrated and must be configured securely if required.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
