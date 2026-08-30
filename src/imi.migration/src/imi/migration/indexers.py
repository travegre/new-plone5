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
    return _raw_text(getattr(obj, 'sklop', None))


@indexer(IExamination)
def examination_sinonim(obj):
    return _raw_text(getattr(obj, 'sinonim', None))


@indexer(IExamination)
def examination_moj(obj):
    """Combined full-text value used by the legacy Preiskave ``moj`` index."""
    values = [
        obj.Title() or '',
        getattr(obj, 'vzorci', '') or '',
        _raw_text(getattr(obj, 'sinonim', None)),
        u' '.join(getattr(obj, 'podrocje', ()) or ()),
        _raw_text(getattr(obj, 'sklop', None)),
        getattr(obj, 'vzorci_lab', '') or '',
    ]
    return u' '.join(str(value) for value in values if value)


DIRECTORY_SEARCHABLE_FIELDS = (
    'predime', 'ime', 'priimek', 'zaime', 'oddelek', 'telefon', 'vuporabi',
    'opis', 'enota', 'lokacija', 'dodatna', 'dect', 'fax', 'multitone',
    'mobilna', 'zunanja', 'enaslov', 'zenaslov',
)


@indexer(IDirectoryPerson)
def directory_searchable_text(obj):
    """Reproduce Archetypes ``searchable=True`` fields from IMENIK 4.3."""
    values = [obj.Title() or '', obj.Description() or '']
    for field in DIRECTORY_SEARCHABLE_FIELDS:
        values.append(getattr(obj, field, '') or '')
    return u' '.join(str(value) for value in values if value)
