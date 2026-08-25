#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dependency-free static and argv-shape checks for the Plone 4.3 tool."""
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

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imports.append((node.module, [x.name for x in node.names]))
    assert ('OFS.interfaces', ['IFolderish']) not in imports
    assert ('Products.CMFCore.interfaces', ['IFolderish']) in imports

    functions = dict((node.name, node) for node in tree.body
                     if isinstance(node, ast.FunctionDef))
    for name in ('archetypes_schema', 'schema', 'field_values', 'binaries',
                 '_script_basename', 'parse_inventory_args', 'parse_output_dir'):
        assert name in functions

    schema_source = (ast.get_source_segment(text, functions['archetypes_schema'])
                     if hasattr(ast, 'get_source_segment') else '')
    if not schema_source:
        start = text.index('def archetypes_schema')
        end = text.index('\ndef schema_field', start)
        schema_source = text[start:end]
    assert "getattr(obj, 'Schema', None)" in schema_source
    assert 'callable(schema_method)' in schema_source
    assert 'schema_method()' in schema_source

    namespace = {'os': os}
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name in ('_script_basename', 'parse_inventory_args',
                                  'parse_output_dir')]
    module = ast.Module(body=selected)
    ast.fix_missing_locations(module)
    code = compile(module, SOURCE, 'exec')
    exec(code, namespace)

    parser = namespace['parse_inventory_args']
    expected = '/plone/instance/src'
    assert parser(['src/plone43_inventory.py',
                   '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == expected
    assert parser(['src/plone43_inventory.py', '-c',
                   '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == expected
    assert parser(['-c', 'src/plone43_inventory.py',
                   '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == expected
    # Shape observed from the user's real Plone 4.3 bin/instance wrapper.
    assert parser(['src/plone43_inventory.py', 'src/plone43_inventory.py',
                   '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == expected
    assert parser(['src/plone43_inventory.py', 'src/plone43_inventory.py',
                   '-c', '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == expected
    assert parser(['src/plone43_inventory.py', '-c', '--output-dir', '/tmp/out'],
                  'src/plone43_inventory.py') == '/tmp/out'

    for argv in (
        ['src/plone43_inventory.py', '-c'],
        ['src/plone43_inventory.py', '--bogus'],
        ['-c', 'other.py', '--output-dir=/tmp/out'],
        ['src/plone43_inventory.py', 'other.py', '--output-dir=/tmp/out'],
    ):
        try:
            parser(argv, 'src/plone43_inventory.py')
        except SystemExit:
            pass
        else:
            raise AssertionError('Invalid argv was silently accepted: %r' % (argv,))

    print('plone43_inventory.py static/argv compatibility checks: OK')


if __name__ == '__main__':
    main()
