#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dependency-free argv compatibility test for the Plone 4.3 inventory."""
from __future__ import print_function

import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'plone43_inventory.py')


def main():
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

    print('plone43_inventory argv compatibility checks: OK')


if __name__ == '__main__':
    main()
