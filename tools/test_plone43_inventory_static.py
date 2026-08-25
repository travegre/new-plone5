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
    assert '_base' in functions
    assert '_normalize' in functions

    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name in ('_base', '_normalize')]
    module = ast.Module(body=selected)
    ast.fix_missing_locations(module)
    namespace = {'os': os}
    exec(compile(module, SOURCE, 'exec'), namespace)
    normalize = namespace['_normalize']
    script = 'src/plone43_inventory.py'
    output = '--output-dir=/plone/instance/src'

    cases = [
        [script, output],
        [script, script, output],
        [script, '-c', script, output],
        ['/plone/instance/parts/instance/bin/interpreter', '-c', script,
         output],
        ['-c', script, output],
    ]
    for argv in cases:
        result = normalize(argv)
        assert os.path.basename(result[0]) == 'plone43_inventory_original.py'
        assert result[1:] == [output]

    # Normalization must not hide genuine inventory arguments.  The original
    # implementation's parse_output_dir() remains responsible for rejecting
    # these after launcher bookkeeping has been removed.
    assert normalize([script, '--bogus'])[1:] == ['--bogus']
    assert normalize([script, 'other.py'])[1:] == ['other.py']

    print('plone43_inventory.py argv compatibility checks: OK')


if __name__ == '__main__':
    main()
