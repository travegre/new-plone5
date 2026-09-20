# -*- coding: utf-8 -*-
"""Small traversal helper used by the Preiskave runtime modules."""


def _walk(container):
    for obj in container.objectValues():
        yield obj
        if hasattr(obj, 'objectValues'):
            for child in _walk(obj):
                yield child
