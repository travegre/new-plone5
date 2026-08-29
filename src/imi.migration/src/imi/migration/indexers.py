# -*- coding: utf-8 -*-
"""Catalog index adapters for migrated Dexterity content."""
from plone.indexer import indexer

from .content import IExamination


def _raw_text(value):
    if value is None:
        return u''
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw or '')
    return str(value or '')


@indexer(IExamination)
def examination_sklop(obj):
    """Expose RichText ``sklop`` as the plain string the legacy indexes saw."""
    return _raw_text(getattr(obj, 'sklop', None))


@indexer(IExamination)
def examination_sinonim(obj):
    """Expose RichText ``sinonim`` as the plain string the legacy index saw."""
    return _raw_text(getattr(obj, 'sinonim', None))
