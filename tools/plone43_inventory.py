#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Plone 4.3 bin/instance-run entry point for the read-only inventory.

The Zope 2.13 run wrapper does not guarantee that ``__file__`` is the
inventory script path.  In the real Plone 4.3 runner it can be the generated
interpreter path.  Therefore the implementation is located from the actual
script argument before normalizing argv.

This file is intentionally a small Python 2.7-compatible launcher.  Copy
this file together with ``plone43_inventory_original.py`` from this
repository's ``tools/`` directory when placing the inventory under
``src/`` in a Plone 4.3 buildout.
"""
from __future__ import print_function

import os
import sys

SCRIPT = 'plone43_inventory.py'
IMPLEMENTATION_NAME = 'plone43_inventory_original.py'


def _base(value):
    try:
        return os.path.basename(value)
    except Exception:
        return value


def _find_implementation(argv):
    """Find the implementation next to the script actually passed to Zope.

    ``__file__`` is deliberately not used: under the Plone 4.3 instance
    runner it may refer to ``parts/instance/bin/interpreter``.
    """
    candidates = []
    for value in argv:
        try:
            if _base(value) != SCRIPT:
                continue
            script_path = os.path.abspath(value)
            candidates.append(os.path.join(os.path.dirname(script_path),
                                           IMPLEMENTATION_NAME))
        except Exception:
            pass

    # The normal command in the buildout is run from /plone/instance and the
    # script is commonly copied to src/.  Also allow the repository layout
    # where the two files remain under tools/.
    here = os.getcwd()
    candidates.extend([
        os.path.join(here, 'src', IMPLEMENTATION_NAME),
        os.path.join(here, 'tools', IMPLEMENTATION_NAME),
    ])

    seen = set()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if candidate in seen:
            continue
        seen.add(candidate)
        if os.path.isfile(candidate):
            return candidate

    raise SystemExit(
        'Cannot find %s. Copy tools/%s alongside '
        'tools/plone43_inventory.py.' %
        (IMPLEMENTATION_NAME, IMPLEMENTATION_NAME))


def _normalize(argv, implementation):
    argv = list(argv)
    if not argv:
        raise SystemExit('Unable to determine inventory script arguments.')

    # Documented Zope script context: [script, script_args...].
    if _base(argv[0]) == SCRIPT:
        args = argv[1:]
        if args and _base(args[0]) == SCRIPT:
            args = args[1:]
        if args and args[0] == '-c':
            args = args[1:]
            if args and _base(args[0]) == SCRIPT:
                args = args[1:]
        return [implementation] + args

    # Full Python/Zope launcher: [interpreter, -c, script, args...].
    if (len(argv) >= 3 and argv[1] == '-c' and
            _base(argv[2]) == SCRIPT):
        return [implementation] + argv[3:]

    # Direct -c launcher: [-c, script, args...].
    if (argv[0] == '-c' and len(argv) >= 2 and
            _base(argv[1]) == SCRIPT):
        return [implementation] + argv[2:]

    raise SystemExit('Unexpected Plone/Zope run argv shape: %r' % argv)


implementation = _find_implementation(sys.argv)
sys.argv = _normalize(sys.argv, implementation)
globals()['__file__'] = implementation
execfile(implementation, globals(), globals())
