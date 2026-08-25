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

    functions = dict((node.name, node) for node in tree.body if isinstance(node, ast.FunctionDef))
    for name in ('archetypes_schema', 'schema', 'field_values', 'binaries',
                 'parse_inventory_args', 'parse_output_dir'):
        assert name in functions

    schema_source = ast.get_source_segment(text, functions['archetypes_schema']) if hasattr(ast, 'get_source_segment') else ''
    if not schema_source:
        start = text.index('def archetypes_schema')
        end = text.index('\ndef schema_field', start)
        schema_source = text[start:end]
    assert "getattr(obj, 'Schema', None)" in schema_source
    assert 'callable(schema_method)' in schema_source
    assert 'schema_method()' in schema_source

    # This is the problematic deployed Plone 4.3 shape: Python's -c launcher
    # remains in argv ahead of the script name. It must be consumed only in
    # that exact launcher position.
    namespace = {'os': os}
    selected = [node for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name in ('parse_inventory_args', 'parse_output_dir')]
    module = ast.Module(body=selected)
    if hasattr(ast, 'fix_missing_locations'):
        ast.fix_missing_locations(module)
    code = compile(module, SOURCE, 'exec')
    exec(code, namespace)

    parser = namespace['parse_inventory_args']
    assert parser(['src/plone43_inventory.py', '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == '/plone/instance/src'
    assert parser(['-c', 'src/plone43_inventory.py', '--output-dir=/plone/instance/src'],
                  'src/plone43_inventory.py') == '/plone/instance/src'
    assert parser(['-c', 'src/plone43_inventory.py', '--output-dir', '/tmp/out'],
                  'src/plone43_inventory.py') == '/tmp/out'

    try:
        parser(['src/plone43_inventory.py', '-c'], 'src/plone43_inventory.py')
    except SystemExit:
        pass
    else:
        raise AssertionError('A genuine -c inventory option must not be silently ignored')

    try:
        parser(['-c', 'other.py', '--output-dir=/tmp/out'], 'src/plone43_inventory.py')
    except SystemExit:
        pass
    else:
        raise AssertionError('An unrelated script after -c must be rejected')

    try:
        parser(['src/plone43_inventory.py', '--bogus'], 'src/plone43_inventory.py')
    except SystemExit:
        pass
    else:
        raise AssertionError('Unknown inventory options must be rejected')

    print('plone43_inventory.py static/argv compatibility checks: OK')


if __name__ == '__main__':
    main()
