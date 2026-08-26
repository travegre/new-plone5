#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dependency-free compatibility checks for the Plone 4.3 inventory tooling."""
from __future__ import print_function

import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'plone43_inventory.py')
WRAPPER = os.path.join(HERE, 'plone43_inventory_runtime_fix.py')


def test_argv_parser():
    with open(SOURCE, 'rb') as handle:
        tree = ast.parse(handle.read().decode('utf-8'), SOURCE)
    wanted = set(('parse_output_dir', 'parse_inventory_args'))
    nodes = [n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(nodes) == 2
    module = ast.Module(body=nodes)
    ast.fix_missing_locations(module)
    namespace = {'os': os}
    exec(compile(module, SOURCE, 'exec'), namespace)
    parse = namespace['parse_inventory_args']
    script = 'src/plone43_inventory.py'
    output = '--output-dir=/plone/instance/src'

    cases = [
        [script, output],
        [script, script, output],
        [script, '-c', script, output],
        ['/plone/instance/parts/instance/bin/interpreter', '-c', script, output],
        ['-c', script, output],
    ]
    for argv in cases:
        assert parse(argv) == '/plone/instance/src', argv

    for argv in ([script, '--bogus'], [script, 'other.py']):
        try:
            parse(argv)
        except SystemExit:
            pass
        else:
            raise AssertionError('unexpected argument accepted: %r' % (argv,))


def test_runtime_wrapper_shape():
    with open(WRAPPER, 'rb') as handle:
        source = handle.read().decode('utf-8')

    # The wrapper must not import the main module normally, because the current
    # main module auto-runs at import time.
    assert 'import plone43_inventory as inventory' not in source
    assert "source.rfind(marker)" in source

    # Patch the exact names used by the main inventory implementation.
    assert "namespace['local_roles'] = local_roles" in source
    assert "namespace['is_pfg'] = is_pfg" in source

    # The wrapper must execute the inventory once after patching.
    assert "namespace['run'](app, namespace['parse_inventory_args'](sys.argv))" in source

    # PFG detection must cover the types observed in the real database.
    for token in ('formfolder', 'formthankspage', 'field', 'adapter'):
        assert token in source


def main():
    test_argv_parser()
    test_runtime_wrapper_shape()
    print('plone43_inventory compatibility checks: OK')


if __name__ == '__main__':
    main()
