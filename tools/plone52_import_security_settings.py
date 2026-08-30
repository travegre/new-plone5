#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import compatible Plone 4.3 users/groups/roles and site settings.

Reads ``security-settings.json`` created by
``plone43_export_security_settings.py``. Users are recreated with random,
unknown passwords because the normal export deliberately contains no password
material. Administrators must reset passwords separately.

The importer is idempotent. PAS virtual groups such as ``AuthenticatedUsers``
are ignored because they are computed automatically and are not ordinary
stored groups in Plone 5.
"""
import json
import os
import secrets
import sys

import plone.api
from zope.component.hooks import setSite

SCRIPT = 'plone52_import_security_settings.py'
VIRTUAL_GROUPS = frozenset((
    'AuthenticatedUsers',
    'Anonymous Users',
    'Authenticated Users',
))
BASE_USER_ROLES = ('Member',)


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


def is_virtual_group(group_id):
    return str(group_id or '') in VIRTUAL_GROUPS


def normal_roles(roles):
    ignored = {'Authenticated', 'Anonymous'}
    return tuple(str(role) for role in (roles or ()) if str(role) not in ignored)


def assign_principal_roles(site, principal_id, roles):
    assigned = []
    errors = []
    manager = getattr(site.acl_users, 'portal_role_manager', None)
    if manager is None:
        return assigned, ['missing portal_role_manager for %s' % principal_id]
    for role in normal_roles(roles):
        try:
            manager.assignRoleToPrincipal(role, str(principal_id))
            assigned.append(role)
        except Exception as exc:
            errors.append('role %s -> %s: %r' % (role, principal_id, exc))
    return assigned, errors


def create_groups(site, records):
    created = existing = skipped_virtual = 0
    errors = []
    roles_assigned = 0
    for record in records:
        group_id = str(record.get('id') or '')
        if not group_id:
            continue
        if is_virtual_group(group_id):
            skipped_virtual += 1
            continue
        group = plone.api.group.get(groupname=group_id)
        if group is None:
            try:
                plone.api.group.create(groupname=group_id, title=record.get('title') or group_id,
                                       description=record.get('description') or '', roles=())
                created += 1
            except Exception as exc:
                errors.append('create group %s: %r' % (group_id, exc))
                continue
        else:
            existing += 1
        assigned, role_errors = assign_principal_roles(site, group_id, record.get('roles') or ())
        roles_assigned += len(assigned)
        errors.extend(role_errors)
    return created, existing, skipped_virtual, roles_assigned, errors


def create_users(site, records):
    created = existing = 0
    reset_required = []
    errors = []
    roles_assigned = 0
    for record in records:
        user_id = str(record.get('id') or '')
        if not user_id:
            continue
        user = plone.api.user.get(username=user_id)
        props = dict(record.get('properties') or {})
        email = props.pop('email', '') or None
        if user is None:
            password = secrets.token_urlsafe(32)
            try:
                user = plone.api.user.create(username=user_id, password=password, email=email,
                                             properties=props, roles=BASE_USER_ROLES)
                created += 1
                reset_required.append(user_id)
            except Exception as exc:
                errors.append('create user %s: %r' % (user_id, exc))
                continue
        else:
            existing += 1
            try:
                plone.api.user.update(user=user, email=email, properties=props)
            except Exception as exc:
                errors.append('update user %s properties: %r' % (user_id, exc))
        assigned, role_errors = assign_principal_roles(site, user_id, record.get('roles') or ())
        roles_assigned += len(assigned)
        errors.extend(role_errors)
    return created, existing, reset_required, roles_assigned, errors


def add_memberships(records):
    added = existing = skipped_virtual = 0
    errors = []
    for record in records:
        user_id = str(record.get('id') or '')
        if not user_id or plone.api.user.get(username=user_id) is None:
            continue
        for group_id in record.get('groups') or ():
            group_id = str(group_id)
            if is_virtual_group(group_id):
                skipped_virtual += 1
                continue
            if plone.api.group.get(groupname=group_id) is None:
                errors.append('missing group %s for user %s' % (group_id, user_id))
                continue
            try:
                current_ids = set(g.getId() for g in plone.api.group.get_groups(username=user_id))
            except Exception:
                current_ids = set()
            if group_id in current_ids:
                existing += 1
                continue
            try:
                plone.api.group.add_user(groupname=group_id, username=user_id)
                added += 1
            except Exception as exc:
                errors.append('membership %s <- %s: %r' % (group_id, user_id, exc))
    return added, existing, skipped_virtual, errors


def apply_site_local_roles(site, records):
    count = 0
    errors = []
    for principal, roles in records or ():
        try:
            site.manage_setLocalRoles(str(principal), tuple(str(r) for r in roles))
            count += 1
        except Exception as exc:
            errors.append('site local roles %s: %r' % (principal, exc))
    return count, errors


def apply_site_identity(site, record):
    changed = []
    for name, setter in (('title', 'setTitle'), ('description', 'setDescription')):
        value = record.get(name)
        if value is not None:
            try:
                getattr(site, setter)(value)
                changed.append(name)
            except Exception:
                pass
    return changed


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


def apply_registry_email(site, properties):
    changed = []
    try:
        from plone.registry.interfaces import IRegistry
        from zope.component import getUtility
        registry = getUtility(IRegistry)
    except Exception:
        return changed
    mapping = {'email_from_address': 'plone.email_from_address',
               'email_from_name': 'plone.email_from_name'}
    for source_name, target_name in mapping.items():
        if source_name not in (properties or {}):
            continue
        try:
            if target_name in registry:
                registry[target_name] = properties[source_name]
                changed.append(target_name)
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
    tool = getattr(site, 'portal_workflow', None)
    if tool is None:
        return [], []
    applied = []
    skipped = []
    known = set(tool.objectIds())
    for type_id, chain in (chains or {}).items():
        if type_id not in site.portal_types.objectIds():
            continue
        if not chain or not all(name in known for name in chain):
            skipped.append({'portal_type': str(type_id), 'source_chain': list(chain or ())})
            continue
        try:
            tool.setChainForPortalTypes((str(type_id),), tuple(str(x) for x in chain))
            applied.append(str(type_id))
        except Exception:
            skipped.append({'portal_type': str(type_id), 'source_chain': list(chain or ())})
    # Changing chains does not by itself apply the target workflow's permission
    # role maps to already-migrated objects.  Without this, published content can
    # remain non-viewable by Anonymous even though review_state is 'published'.
    tool.updateRoleMappings()
    return applied, skipped


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
            errors = []
            groups_created, groups_existing, groups_virtual, group_roles, group_errors = create_groups(site, record.get('groups') or ())
            errors.extend(group_errors)
            users_created, users_existing, resets, user_roles, user_errors = create_users(site, record.get('users') or ())
            errors.extend(user_errors)
            memberships_added, memberships_existing, memberships_virtual, membership_errors = add_memberships(record.get('users') or ())
            errors.extend(membership_errors)
            local_roles, local_role_errors = apply_site_local_roles(site, record.get('site_local_roles') or ())
            errors.extend(local_role_errors)
            identity = apply_site_identity(site, record)
            props = apply_site_properties(site, record.get('properties') or {})
            registry_email = apply_registry_email(site, record.get('properties') or {})
            mail = apply_mailhost(site, record.get('mailhost'))
            workflows, workflows_skipped = apply_workflow_chains(site, record.get('workflow_chains') or {})
            try:
                site.portal_catalog.manage_reindexIndex(ids=['allowedRolesAndUsers'])
                site.reindexObject()
            except Exception as exc:
                errors.append('security catalog reindex: %r' % (exc,))

            report['sites'][site_id] = {
                'groups_created': groups_created, 'groups_existing': groups_existing,
                'virtual_groups_skipped': groups_virtual, 'group_roles_assigned': group_roles,
                'users_created': users_created, 'users_existing': users_existing,
                'user_roles_assigned': user_roles, 'memberships_added': memberships_added,
                'memberships_existing': memberships_existing,
                'virtual_memberships_skipped': memberships_virtual,
                'site_local_roles_applied': local_roles, 'site_identity_applied': identity,
                'site_properties_applied': props, 'registry_email_applied': registry_email,
                'mailhost_fields_applied': mail, 'workflow_chains_applied': workflows,
                'workflow_chains_skipped': workflows_skipped,
                'smtp_password_required': bool((record.get('mailhost') or {}).get('smtp_password_configured')),
                'errors': errors,
            }
            report['password_resets_required'][site_id] = resets
            status = 'OK' if not errors else 'FAILED (%d errors)' % len(errors)
            print('%s: %s' % (site_id, status))
            print('  users +%d/%d existing, groups +%d/%d existing, memberships +%d/%d existing, virtual memberships skipped %d' %
                  (users_created, users_existing, groups_created, groups_existing,
                   memberships_added, memberships_existing, memberships_virtual))
            print('  roles assigned: users %d, groups %d' % (user_roles, group_roles))
            for error in errors:
                print('  ERROR: %s' % error)
            for skipped in workflows_skipped:
                print('  WORKFLOW SKIPPED: %s <- %s' % (skipped['portal_type'], ','.join(skipped['source_chain'])))
            if (record.get('mailhost') or {}).get('smtp_password_configured'):
                print('  WARNING: SMTP password was configured on source and must be set separately.')
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
