#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Dependency-free static checks for the Plone 4.3 inventory tool.

This test intentionally does not import Plone/Zope. It can run with either
Python 2.7 or Python 3 and catches accidental regression to newer Zope imports
or to unconditional Schema() access.
"""
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
    assert 'archetypes_schema' in functions
    assert 'schema' in functions
    assert 'field_values' in functions
    assert 'binaries' in functions

    schema_source = ast.get_source_segment(text, functions['archetypes_schema']) if hasattr(ast, 'get_source_segment') else ''
    if not schema_source:
        # Python 2.7 compatibility: inspect the source text directly.
        start = text.index('def archetypes_schema')
        end = text.index('\ndef schema_field', start)
        schema_source = text[start:end]
    assert "getattr(obj, 'Schema', None)" in schema_source
    assert 'callable(schema_method)' in schema_source
    assert 'Schema()' not in schema_source.replace('schema_method()', '')

    # The tool must expose an explicit output option so a Zope option such as
    # '-c' cannot silently become a directory name.
    assert 'def parse_output_dir(args):' in text
    assert "args[0].startswith('-')" in text
    print('plone43_inventory.py static compatibility checks: OK')


if __name__ == '__main__':
    main()
