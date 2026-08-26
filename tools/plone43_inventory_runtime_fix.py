#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runtime safety wrapper for the Plone 4.3 inventory.

This wrapper exists because the main inventory script still auto-executes at
module import time. Importing it normally therefore cannot be used to patch
runtime-only issues first.

The wrapper loads only the definitions from plone43_inventory.py, patches the
runtime issues discovered against the real Plone 4.3 ZODB, and then runs the
inventory exactly once with the ``app`` supplied by ``bin/instance run``.

Run with::

    bin/instance run src/plone43_inventory_runtime_fix.py \
        --output-dir=/plone/instance/src
"""
from __future__ import print_function

import os
import sys

WRAPPER_BASENAME = 'plone43_inventory_runtime_fix.py'


def wrapper_position(argv):
    """Return the final argv index of this wrapper under ``instance run``."""
    positions = []
    for index, value in enumerate(list(argv)):
        try:
            if os.path.basename(value) == WRAPPER_BASENAME:
                positions.append(index)
        except Exception:
            pass
    if not positions:
        raise SystemExit(
            'Could not locate %s in Plone/Zope argv: %r' %
            (WRAPPER_BASENAME, list(argv))
        )
    return positions[-1]


def executed_script_path(argv):
    """Resolve this script from the argv shape produced by Zope instance run."""
    value = list(argv)[wrapper_position(argv)]
    if not os.path.isabs(value):
        value = os.path.abspath(value)
    return value


def wrapper_output_dir(argv, parse_output_dir):
    """Parse only arguments belonging to this wrapper.

    Typical Plone 4.3/Zope 2.13 argv is::

        interpreter -c src/plone43_inventory_runtime_fix.py --output-dir=...

    The ``-c`` belongs to the generated instance interpreter and appears
    before the wrapper path. We intentionally ignore everything before the
    wrapper and strictly parse only arguments after it.
    """
    argv = list(argv)
    args = argv[wrapper_position(argv) + 1:]
    return parse_output_dir(args)


SCRIPT = executed_script_path(sys.argv)
HERE = os.path.dirname(SCRIPT)
SOURCE = os.path.join(HERE, 'plone43_inventory.py')

if 'app' not in globals():
    raise SystemExit(
        'Use the Plone 4.3 bin/instance run command; '
        'do not execute with system Python.'
    )

if not os.path.isfile(SOURCE):
    raise SystemExit(
        'Could not find plone43_inventory.py next to wrapper: %s' % SOURCE
    )

# Load the main inventory definitions without executing its final auto-run
# block. This is intentionally narrow: we cut only the known final runner
# block, rather than ignoring arbitrary code or options.
with open(SOURCE, 'rb') as handle:
    source = handle.read()

marker = "\nif 'app' not in globals():\n"
position = source.rfind(marker)
if position < 0:
    raise SystemExit(
        'Could not locate the expected final runner block in %s' % SOURCE
    )

source = source[:position]
namespace = {
    '__name__': 'plone43_inventory_runtime_base',
    '__file__': SOURCE,
}
exec(compile(source, SOURCE, 'exec'), namespace)


def local_roles(obj, ctx):
    """Collect local roles without eagerly touching optional methods."""
    roles_method = getattr(obj, 'get_local_roles', None)
    block_method = getattr(obj, 'get_local_role_block', None)

    roles = {}
    if callable(roles_method):
        roles = namespace['safe'](
            ctx,
            'local_roles',
            roles_method,
            obj=obj,
            default={}
        )

    blocked = None
    if callable(block_method):
        blocked = namespace['safe'](
            ctx,
            'local_role_block',
            block_method,
            obj=obj,
            default=None
        )

    try:
        roles = dict(roles or {})
    except Exception as exc:
        ctx.error('local_roles.normalize', obj=obj, exception=exc)
        roles = {}

    return {'roles': roles, 'blocked': blocked}


def is_pfg(obj):
    """Recognize the PloneFormGen portal types present in this database."""
    pt = namespace['portal_type'](obj) or ''
    cls = namespace['dotted'](obj) or ''
    value = pt.lower()

    if value in ('formfolder', 'formthankspage'):
        return True
    if value.startswith('fieldset'):
        return True
    if value.startswith('form') and (
            value.endswith('field') or value.endswith('adapter')):
        return True
    if 'ploneformgen' in cls.lower():
        return True
    return False


def to_unicode(v):
    """Use the same Python 2 str/unicode normalization as markdown()."""
    if isinstance(v, unicode):
        return v
    if isinstance(v, str):
        return v.decode('utf-8')
    return unicode(v)


def normalize_json_value(value):
    """Recursively normalize Python 2 byte strings before JSON encoding."""
    if isinstance(value, unicode):
        return value
    if isinstance(value, str):
        return value.decode('utf-8')
    if isinstance(value, dict):
        return dict((normalize_json_value(key), normalize_json_value(item))
                    for key, item in value.items())
    if isinstance(value, list):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_json_value(item) for item in value]
    if isinstance(value, set):
        return [normalize_json_value(item) for item in value]
    return value


def utf8_json_dumps(obj, **kwargs):
    """Normalize the complete object tree before any JSON encoder sees it."""
    normalized = normalize_json_value(obj)
    rendered = namespace['json_dumps_original'](normalized, **kwargs)
    return to_unicode(rendered)


def utf8_json_dump(obj, handle, **kwargs):
    """Write the normalized JSON document as explicit UTF-8 bytes."""
    rendered = utf8_json_dumps(obj, **kwargs)
    handle.write(rendered.encode('utf-8'))


# Patch the exact global names used by site_inventory()/inspect_object().
namespace['local_roles'] = local_roles
namespace['is_pfg'] = is_pfg

# IMPORTANT: patch BOTH dumps() and dump().  markdown() embeds JSON using
# json.dumps(), while run() writes the standalone JSON file using json.dump().
# Both must pass through the same recursive Unicode normalization on Python 2.
namespace['json_dumps_original'] = namespace['json'].dumps
namespace['json'].dumps = utf8_json_dumps
namespace['json'].dump = utf8_json_dump

# Run exactly once using the Plone/Zope ``app`` supplied to this wrapper.
outdir = wrapper_output_dir(sys.argv, namespace['parse_output_dir'])
namespace['run'](app, outdir)
