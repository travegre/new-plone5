#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runtime safety wrapper for the Plone 4.3 inventory.

This imports the main inventory module and patches two runtime issues found only
against the real Plone 4.3 ZODB:

* local role blocking must not assume get_local_role_block exists;
* PloneFormGen portal-type detection must recognize Form*Field and
  FormThanksPage types actually present in the database.

Run with Plone 4.3's instance runner, for example:

    bin/instance run src/plone43_inventory_runtime_fix.py \
        --output-dir=/plone/instance/src
"""
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import plone43_inventory as inventory


def local_roles(ctx, obj):
    """Collect local roles without eagerly touching optional methods."""
    roles_method = getattr(obj, 'get_local_roles', None)
    block_method = getattr(obj, 'get_local_role_block', None)

    assignments = []
    if callable(roles_method):
        assignments = inventory.safe_call(
            ctx,
            'local_roles',
            roles_method,
            obj=obj,
            default=[]
        )

    blocks_inheritance = None
    if callable(block_method):
        blocks_inheritance = inventory.safe_call(
            ctx,
            'local_roles.block',
            block_method,
            obj=obj,
            default=None
        )

    return {
        'assignments': inventory.scalar(assignments),
        'blocks_inheritance': blocks_inheritance,
    }


def is_pfg_type(portal_type):
    """Recognize PloneFormGen portal types found in this installation."""
    if not portal_type:
        return False
    value = portal_type.lower()
    if value in ('formfolder', 'formthankspage'):
        return True
    if value.startswith('fieldset'):
        return True
    if value.startswith('form') and (
            value.endswith('field') or value.endswith('adapter')):
        return True
    return False


inventory.local_roles = local_roles
inventory.is_pfg_type = is_pfg_type


if __name__ == '__main__':
    inventory.run(app, inventory.parse_inventory_args(sys.argv))
