#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dependency-free argv compatibility checks for the Plone 4.3 inventory shim."""
from __future__ import print_function

import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, 'plone43_inventory.py')


def main():
    with open(SOURCE, 'rb') as handle:
        source = handle.read()
    text = source.decode('utf-8')
    tree = ast.parse(text, SOURCE)
    functions = dict((node.name, node) for node in tree.body
                     if isinstance(node, ast.FunctionDef))
    for name in ('_base', '_normalize'):
        assert name in functions

    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name in ('_base', '_normalize')]
    module = ast.Module(body=selected)
    ast.fix_missing_locations(module)
    namespace = {'os': os}
    exec(compile(module, SOURCE, 'exec'), namespace)
    normalize = namespace['_normalize']
    script = 'src/plone43_inventory.py'
    expected = 'src/plone43_inventory.py'

    cases = [
        ([script, '--output-dir=/plone/instance/src'], expected),
        ([script, script, '--output-dir=/plone/instance/src'], expected),
        ([script, '-c', script, '--output-dir=/plone/instance/src'], expected),
        (['/plone/instance/parts/instance/bin/interpreter', '-c', script,
          '--output-dir=/plone/instance/src'], expected),
        (['-c', script, '--output-dir=/plone/instance/src'], expected),
    ]
    for argv, first in cases:
        result = normalize(argv)
        assert os.path.basename(result[0]) == os.path.basename(first)
        assert result[1:] == ['--output-dir=/plone/instance/src']

    for argv in (
        [script, '--bogus'],
        [script, '-c'],
        [script, 'other.py', '--output-dir=/tmp/out'],
        ['-c', 'other.py', '--output-dir=/tmp/out'],
    ):
        try:
            normalize(argv)
        except SystemExit:
            pass
        else:
            raise AssertionError('Invalid argv was silently accepted: %r' % (argv,))

    print('plone43_inventory.py argv compatibility checks: OK')


if __name__ == '__main__':
    main()
