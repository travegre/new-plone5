#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Plone 4.3 bin/instance-run entry point for the read-only inventory.

The Zope 2.13 run wrapper can expose launcher bookkeeping in sys.argv.
This shim normalizes only the exact launcher forms before executing the
unchanged inventory implementation.
"""
from __future__ import print_function

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IMPLEMENTATION = os.path.join(HERE, 'plone43_inventory_original.py')
SCRIPT = os.path.basename(__file__)


def _base(value):
    try:
        return os.path.basename(value)
    except Exception:
        return value


def _normalize(argv):
    argv = list(argv)
    if not argv:
        raise SystemExit('Unable to determine inventory script arguments.')

    # Documented Zope script context: [script, script_args...].
    if _base(argv[0]) == SCRIPT:
        args = argv[1:]
        # [script, script, args...]
        if args and _base(args[0]) == SCRIPT:
            args = args[1:]
        # [script, -c, args...] or [script, -c, script, args...]
        if args and args[0] == '-c':
            args = args[1:]
            if args and _base(args[0]) == SCRIPT:
                args = args[1:]
        return [IMPLEMENTATION] + args

    # Full Python/Zope launcher: [interpreter, -c, script, args...].
    if (len(argv) >= 3 and argv[1] == '-c' and
            _base(argv[2]) == SCRIPT):
        return [IMPLEMENTATION] + argv[3:]

    # Direct -c launcher: [-c, script, args...].
    if (argv[0] == '-c' and len(argv) >= 2 and
            _base(argv[1]) == SCRIPT):
        return [IMPLEMENTATION] + argv[2:]

    raise SystemExit('Unexpected Plone/Zope run argv shape: %r' % argv)


sys.argv = _normalize(sys.argv)
globals()['__file__'] = IMPLEMENTATION
execfile(IMPLEMENTATION, globals(), globals())
