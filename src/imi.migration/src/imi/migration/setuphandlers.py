# -*- coding: utf-8 -*-
"""Catalog setup for the five migrated legacy Plone sites."""
from Products.ZCTextIndex.HTMLSplitter import HTMLWordSplitter
from Products.ZCTextIndex.Lexicon import CaseNormalizer
from Products.ZCTextIndex.Lexicon import StopWordRemover
from Products.ZCTextIndex.ZCTextIndex import PLexicon


HTMLTEXT_LEXICON_ID = 'htmltext_lexicon'
HTMLTEXT_PIPELINE = (
    'Products.ZCTextIndex.HTMLSplitter.HTMLWordSplitter',
    'Products.ZCTextIndex.Lexicon.CaseNormalizer',
    'Products.ZCTextIndex.Lexicon.StopWordRemover',
)

SITE_INDEXES = {
    'portal': {
        'priimek': ('FieldIndex', ('priimek',), None),
    },
    'dezurstva': {
        'dezurni_zdravnik': (
            'ZCTextIndex',
            (
                'sprejem_predpriprava_tehnik', 'inoqula_tehnik', 'kiestra',
                'dezurni_zdravnik', 'nadzorni_zdravnik', 'dezurni_tehnik',
                'izobrazevanje', 'BOR', 'HIV', 'HUM', 'IT', 'KLM', 'KOV',
                'VINVZV', 'VINDIF', 'WHO', 'specializant', 'vpis',
                'bakterioloski_tehnik', 'sarsifon',
            ),
            HTMLTEXT_LEXICON_ID,
        ),
        'tit': ('FieldIndex', ('Title',), None),
    },
    'kiestra': {
        'priprava_vzorcev': (
            'ZCTextIndex',
            (
                'priprava_vzorcev', 'cepljenje_vzorcev', 'odcitavanje',
                'identifikacija', 'antibiogram', 'izolacija', 'odpad',
                'ciscenje',
            ),
            HTMLTEXT_LEXICON_ID,
        ),
    },
    'preiskave': {
        'laboratorij': ('KeywordIndex', ('vzorci_lab',), None),
        # In Plone 4 this ZCTextIndex read six Archetypes fields directly.
        # In Plone 5 the RichText fields must be normalized by a named
        # plone.indexer adapter; the resulting indexed text is equivalent.
        'moj': ('ZCTextIndex', ('moj',), HTMLTEXT_LEXICON_ID),
        'moj_laboratoriji': ('ZCTextIndex', ('laboratoriji',), HTMLTEXT_LEXICON_ID),
        'moj_sklop': ('ZCTextIndex', ('sklop',), HTMLTEXT_LEXICON_ID),
        'podrocje': ('KeywordIndex', ('podrocje',), None),
        'sklop': ('KeywordIndex', ('sklop',), None),
        'vzorci_lab': ('KeywordIndex', ('vzorci_lab',), None),
    },
    'nadomescanja': {},
}


class _IndexExtra(object):
    def __init__(self, indexed_attrs, lexicon_id=None):
        self.indexed_attrs = tuple(indexed_attrs)
        self.doc_attr = ','.join(self.indexed_attrs)
        if lexicon_id:
            self.lexicon_id = lexicon_id
            self.index_type = 'Okapi BM25 Rank'


def _dotted(obj):
    return '%s.%s' % (obj.__class__.__module__, obj.__class__.__name__)


def _ensure_htmltext_lexicon(catalog):
    existing = getattr(catalog, HTMLTEXT_LEXICON_ID, None)
    if existing is not None:
        pipeline = tuple(_dotted(item) for item in getattr(existing, '_pipeline', ()))
        if pipeline != HTMLTEXT_PIPELINE:
            raise RuntimeError('Existing %s has incompatible pipeline %r' %
                               (HTMLTEXT_LEXICON_ID, pipeline))
        return False
    lexicon = PLexicon(
        HTMLTEXT_LEXICON_ID,
        'Legacy HTML text lexicon',
        HTMLWordSplitter(),
        CaseNormalizer(),
        StopWordRemover(),
    )
    catalog._setObject(HTMLTEXT_LEXICON_ID, lexicon)
    return True


def _index_configuration(index):
    try:
        source_names = tuple(index.getIndexSourceNames() or ())
    except Exception:
        source_names = tuple(getattr(index, '_indexed_attrs', ()) or ())
    return source_names, getattr(index, 'lexicon_id', None)


def _ensure_index(catalog, name, meta_type, attrs, lexicon_id):
    existing = catalog._catalog.indexes.get(name)
    expected = (tuple(attrs), lexicon_id)
    if existing is not None:
        current = _index_configuration(existing)
        if getattr(existing, 'meta_type', None) == meta_type and current == expected:
            return False
        catalog.delIndex(name)
    catalog.addIndex(name, meta_type, extra=_IndexExtra(attrs, lexicon_id=lexicon_id))
    return True


def install_catalog_indexes(portal, reindex=True):
    definitions = SITE_INDEXES.get(portal.getId())
    if definitions is None:
        return ()
    catalog = portal.portal_catalog
    if any(spec[2] == HTMLTEXT_LEXICON_ID for spec in definitions.values()):
        _ensure_htmltext_lexicon(catalog)
    changed = []
    for name, (meta_type, attrs, lexicon_id) in definitions.items():
        if _ensure_index(catalog, name, meta_type, attrs, lexicon_id):
            changed.append(name)
    if reindex and changed:
        catalog.manage_reindexIndex(ids=changed)
    return tuple(changed)


def post_install(context):
    install_catalog_indexes(context.getSite(), reindex=True)
