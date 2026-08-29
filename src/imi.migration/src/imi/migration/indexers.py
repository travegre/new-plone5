# -*- coding: utf-8 -*-
"""Catalog index adapters for migrated Dexterity content."""
from plone.indexer import indexer

from .content import IDirectoryPerson
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


DIRECTORY_SEARCHABLE_FIELDS = (
    'predime', 'ime', 'priimek', 'zaime', 'oddelek', 'telefon', 'vuporabi',
    'opis', 'enota', 'lokacija', 'dodatna', 'dect', 'fax', 'multitone',
    'mobilna', 'zunanja', 'enaslov', 'zenaslov',
)


@indexer(IDirectoryPerson)
def directory_searchable_text(obj):
    """Reproduce Archetypes ``searchable=True`` fields from IMENIK 4.3.

    The old ``produkti`` type contributed its normal title/description plus
    every field marked ``searchable=True`` to the standard SearchableText
    ZCTextIndex.  ``maticna`` and ``star`` were deliberately not searchable.
    """
    values = [obj.Title() or '', obj.Description() or '']
    for field in DIRECTORY_SEARCHABLE_FIELDS:
        values.append(getattr(obj, field, '') or '')
    return u' '.join(str(value) for value in values if value)
