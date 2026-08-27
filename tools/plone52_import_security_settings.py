#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import compatible Plone 4.3 users/groups/roles and site settings.

Reads ``security-settings.json`` created by
``plone43_export_security_settings.py``.

The import is intentionally idempotent. Passwords and SMTP passwords are never
read or written by this script. Missing users get random unknown passwords so
that principals, ownership and permissions exist immediately; real passwords
must be reset/configured separately.
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


def ensure_group(record, stats):
    group_id = str(record.get('id') or '')
    if not group_id:
        return
    group = plone.api.group.get(groupname=group_id)
    if group is None:
        try:
            plone.api.group.create(
                groupname=group_id,
                title=record.get('title') or group_id,
                description=record.get('description') or '',
            )
            stats['groups_created'] += 1
        except Exception as exc:
            stats['errors'].append('group %s create: %r' % (group_id, exc))
            return
    else:
        stats['groups_existing'] += 1

    roles = [str(r) for r in (record.get('roles') or ())
             if r not in ('Authenticated',)]
    if roles:
        try:
            plone.api.group.grant_roles(groupname=group_id, roles=roles)
        except Exception as exc:
            stats['errors'].append('group %s roles: %r' % (group_id, exc))


def ensure_user(site, record, stats):
    user_id = str(record.get('id') or '')
    if not user_id:
        return

    props = dict(record.get('properties') or {})
    email = props.pop('email', '') or None
    fullname = props.get('fullname') or ''
    user = plone.api.user.get(username=user_id)

    if user is None:
        try:
            plone.api.user.create(
                username=user_id,
                password=secrets.token_urlsafe(32),
                email=email,
                properties=props,
            )
            stats['users_created'] += 1
            stats['password_resets_required'].append(user_id)
        except Exception as exc:
            stats['errors'].append('user %s create: %r' % (user_id, exc))
            return
    else:
        stats['users_existing'] += 1

    member = site.portal_membership.getMemberById(user_id)
    if member is not None:
        changes = {}
        if email:
            changes['email'] = email
        if fullname:
            changes['fullname'] = fullname
        for key in ('description', 'location', 'home_page'):
            value = props.get(key)
            if value not in (None, ''):
                changes[key] = value
        if changes:
            try:
                member.setMemberProperties(changes)
            except Exception as exc:
                stats['errors'].append('user %s properties: %r' % (user_id, exc))

    roles = [str(r) for r in (record.get('roles') or ())
             if r not in ('Authenticated',)]
    if roles:
        try:
            plone.api.user.grant_roles(username=user_id, roles=roles)
        except Exception as exc:
            stats['errors'].append('user %s roles: %r' % (user_id, exc))


def restore_memberships(site_record, stats):
    desired = {}
    for group in site_record.get('groups') or ():
        gid = str(group.get('id') or '')
        if gid:
            desired.setdefault(gid, set()).update(
                str(uid) for uid in group.get('members') or ())
    for user in site_record.get('users') or ():
        uid = str(user.get('id') or '')
        for gid in user.get('groups') or ():
            desired.setdefault(str(gid), set()).add(uid)

    for gid, members in desired.items():
        if plone.api.group.get(groupname=gid) is None:
            continue
        for uid in sorted(members):
            if plone.api.user.get(username=uid) is None:
                stats['errors'].append('membership %s <- %s: user missing' % (gid, uid))
                continue
            try:
                plone.api.group.add_user(groupname=gid, username=uid)
                stats['memberships_added'] += 1
            except Exception:
                # Existing membership is fine; verify before reporting failure.
                try:
                    group = plone.api.group.get(groupname=gid)
                    member_ids = set(m.getId() for m in group.getGroupMembers())
                    if uid not in member_ids:
                        raise
                except Exception as exc:
                    stats['errors'].append('membership %s <- %s: %r' % (gid, uid, exc))


def apply_site_local_roles(site, records, stats):
    for principal, roles in records or ():
        try:
            site.manage_setLocalRoles(str(principal), tuple(str(r) for r in roles))
            stats['site_local_roles_applied'] += 1
        except Exception as exc:
            stats['errors'].append('site local role %s: %r' % (principal, exc))


def apply_site_identity(site, record, stats):
    try:
        if record.get('title') is not None:
            site.setTitle(record.get('title'))
        if record.get('description') is not None:
            site.setDescription(record.get('description'))
        site.reindexObject()
        stats['site_identity_applied'] = True
    except Exception as exc:
        stats['errors'].append('site identity: %r' % exc)


def apply_site_properties(site, properties, stats):
    props_tool = getattr(site, 'portal_properties', None)
    sheet = getattr(props_tool, 'site_properties', None) if props_tool is not None else None
    if sheet is not None:
        for name, value in sorted((properties or {}).items()):
            try:
                if sheet.hasProperty(name):
                    sheet._updateProperty(name, value)
                    stats['site_properties_applied'].append(name)
                else:
                    stats['site_properties_skipped'].append(name)
            except Exception as exc:
                stats['errors'].append('site property %s: %r' % (name, exc))

    default_language = (properties or {}).get('default_language')
    if default_language:
        languages = getattr(site, 'portal_languages', None)
        setter = getattr(languages, 'setDefaultLanguage', None)
        if callable(setter):
            try:
                setter(str(default_language))
                if 'default_language' not in stats['site_properties_applied']:
                    stats['site_properties_applied'].append('default_language')
            except Exception as exc:
                stats['errors'].append('default language: %r' % exc)

    # Plone 5 moved sender settings to registry-backed control panels in many
    # installations. Copy the source values there when those records exist.
    registry = getattr(site, 'portal_registry', None)
    if registry is not None:
        for old_name, registry_name in (
                ('email_from_address', 'plone.email_from_address'),
                ('email_from_name', 'plone.email_from_name')):
            value = (properties or {}).get(old_name)
            if value in (None, ''):
                continue
            try:
                registry[registry_name] = value
                stats['registry_settings_applied'].append(registry_name)
            except Exception:
                stats['warnings'].append('registry record unavailable: %s' % registry_name)


def apply_mailhost(site, record, stats):
    if not record:
        return
    mh = getattr(site, 'MailHost', None)
    if mh is None:
        stats['warnings'].append('MailHost unavailable')
        return
    for name in ('smtp_host', 'smtp_port', 'smtp_uid'):
        if name not in record or record[name] is None:
            continue
        try:
            setattr(mh, name, record[name])
            stats['mailhost_fields_applied'].append(name)
        except Exception as exc:
            stats['errors'].append('MailHost %s: %r' % (name, exc))
    if record.get('smtp_password_configured'):
        stats['warnings'].append(
            'source SMTP password was configured; set target SMTP password separately')


def apply_workflow_chains(site, chains, stats):
    tool = getattr(site, 'portal_workflow', None)
    if tool is None:
        return
    known = set(tool.objectIds())
    target_types = set(site.portal_types.objectIds())
    for type_id, chain in sorted((chains or {}).items()):
        chain = [str(x) for x in chain]
        if str(type_id) not in target_types:
            stats['workflow_chains_skipped'].append('%s (target type missing)' % type_id)
            continue
        missing = [name for name in chain if name not in known]
        if missing:
            stats['workflow_chains_skipped'].append(
                '%s -> %s (missing workflows: %s)' %
                (type_id, ','.join(chain), ','.join(missing)))
            continue
        try:
            tool.setChainForPortalTypes((str(type_id),), tuple(chain))
            stats['workflow_chains_applied'].append(str(type_id))
        except Exception as exc:
            stats['errors'].append('workflow %s: %r' % (type_id, exc))


def import_site(app, record):
    site_id = str(record.get('id') or '')
    site = app.get(site_id)
    stats = {
        'site': site_id,
        'users_created': 0,
        'users_existing': 0,
        'groups_created': 0,
        'groups_existing': 0,
        'memberships_added': 0,
        'site_local_roles_applied': 0,
        'site_identity_applied': False,
        'site_properties_applied': [],
        'site_properties_skipped': [],
        'registry_settings_applied': [],
        'mailhost_fields_applied': [],
        'workflow_chains_applied': [],
        'workflow_chains_skipped': [],
        'password_resets_required': [],
        'warnings': [],
        'errors': [],
    }
    if site is None:
        stats['errors'].append('target site missing')
        return stats

    setSite(site)
    apply_site_identity(site, record, stats)
    for group in record.get('groups') or ():
        ensure_group(group, stats)
    for user in record.get('users') or ():
        ensure_user(site, user, stats)
    restore_memberships(record, stats)
    apply_site_local_roles(site, record.get('site_local_roles') or (), stats)
    apply_site_properties(site, record.get('properties') or {}, stats)
    apply_mailhost(site, record.get('mailhost'), stats)
    apply_workflow_chains(site, record.get('workflow_chains') or {}, stats)
    return stats


def run(app, input_dir):
    path = os.path.join(input_dir, 'security-settings.json')
    if not os.path.isfile(path):
        raise SystemExit(
            'Missing %s; run the Plone 4.3 security/settings exporter first.' % path)
    with open(path, 'r', encoding='utf-8') as handle:
        payload = json.load(handle)

    import transaction
    results = []
    try:
        for record in payload.get('sites') or ():
            stats = import_site(app, record)
            results.append(stats)
            if stats['errors']:
                transaction.abort()
                print('%s: FAILED (%d errors)' % (stats['site'], len(stats['errors'])))
                for error in stats['errors']:
                    print('  ERROR: %s' % error)
                continue
            transaction.commit()
            print('%s: users +%d/%d existing, groups +%d/%d existing, memberships %d' %
                  (stats['site'], stats['users_created'], stats['users_existing'],
                   stats['groups_created'], stats['groups_existing'],
                   stats['memberships_added']))
            for warning in stats['warnings']:
                print('  WARNING: %s' % warning)
            for skipped in stats['workflow_chains_skipped']:
                print('  WORKFLOW SKIPPED: %s' % skipped)
    finally:
        setSite(None)

    report_dir = os.path.join(input_dir, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, 'plone52-security-settings-import.json')
    with open(report_path, 'w', encoding='utf-8') as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print('Security/settings report: %s' % report_path)
    print('User passwords were NOT migrated; newly-created users require password reset.')
    print('SMTP password was NOT migrated and must be configured securely if required.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app, parse_input_dir(sys.argv))
