# -*- coding: utf-8 -*-
"""Catalog setup for the five migrated legacy Plone sites.

The Plone 4.3 sites had a small set of site-specific custom indexes in
addition to the standard Plone catalog.  Keep those indexes explicit here so
new 5.2 databases and already-migrated databases use the same search model.
"""
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


# name -> (meta_type, indexed attributes, lexicon id or None)
SITE_INDEXES = {
    'portal': {
        'priimek': ('FieldIndex', ('priimek',), None),
    },
    'dezurstva': {
        'dezurni_zdravnik': (
            'ZCTextIndex',
            (
                'sprejem_predpriprava_tehnik', 'inoqula_tehnik',
                # The migrated Dexterity model stores the legacy
                # kiestra_tehnik value in ``kiestra``.
                'kiestra', 'dezurni_zdravnik', 'nadzorni_zdravnik',
                'dezurni_tehnik', 'izobrazevanje', 'BOR', 'HIV', 'HUM',
                'IT', 'KLM', 'KOV', 'VINVZV', 'VINDIF', 'WHO',
                'specializant', 'vpis', 'bakterioloski_tehnik', 'sarsifon',
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
        'moj': (
            'ZCTextIndex',
            ('Title', 'vzorci', 'sinonim', 'podrocje', 'sklop', 'vzorci_lab'),
            HTMLTEXT_LEXICON_ID,
        ),
        'moj_laboratoriji': (
            'ZCTextIndex', ('laboratoriji',), HTMLTEXT_LEXICON_ID),
        'moj_sklop': ('ZCTextIndex', ('sklop',), HTMLTEXT_LEXICON_ID),
        'podrocje': ('KeywordIndex', ('podrocje',), None),
        'sklop': ('KeywordIndex', ('sklop',), None),
        'vzorci_lab': ('KeywordIndex', ('vzorci_lab',), None),
    },
    'nadomescanja': {},
}


class _IndexExtra(object):
    """Attribute container expected by ZCatalog index factories."""

    def __init__(self, indexed_attrs, lexicon_id=None):
        self.indexed_attrs = tuple(indexed_attrs)
        # ZCTextIndex reads the comma-separated ``doc_attr`` value and splits
        # it into _indexed_attrs.  Keep indexed_attrs too for Field/Keyword
        # index factories and for introspection.
        self.doc_attr = ','.join(self.indexed_attrs)
        if lexicon_id:
            self.lexicon_id = lexicon_id
            self.index_type = 'Okapi BM25 Rank'


def _dotted(obj):
    return '%s.%s' % (obj.__class__.__module__, obj.__class__.__name__)


def _ensure_htmltext_lexicon(catalog):
    existing = getattr(catalog, HTMLTEXT_LEXICON_ID, None)
    if existing is not None:
        pipeline = tuple(_dotted(item)
                         for item in getattr(existing, '_pipeline', ()))
        if pipeline != HTMLTEXT_PIPELINE:
            raise RuntimeError(
                'Existing %s has incompatible pipeline %r' %
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
    source_names = ()
    try:
        source_names = tuple(index.getIndexSourceNames() or ())
    except Exception:
        source_names = tuple(getattr(index, '_indexed_attrs', ()) or ())
    lexicon_id = getattr(index, 'lexicon_id', None)
    return source_names, lexicon_id


def _ensure_index(catalog, name, meta_type, attrs, lexicon_id):
    indexes = catalog._catalog.indexes
    existing = indexes.get(name)
    expected = (tuple(attrs), lexicon_id)
    if existing is not None:
        current = _index_configuration(existing)
        current_meta = getattr(existing, 'meta_type', None)
        if current_meta == meta_type and current == expected:
            return False
        catalog.delIndex(name)

    extra = _IndexExtra(attrs, lexicon_id=lexicon_id)
    catalog.addIndex(name, meta_type, extra=extra)
    return True


def install_catalog_indexes(portal, reindex=True):
    """Install the custom indexes required by this migrated site.

    Returns a tuple containing the index ids that were created or corrected.
    """
    site_id = portal.getId()
    definitions = SITE_INDEXES.get(site_id)
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
    """GenericSetup post-handler for newly installed/reinstalled profiles."""
    portal = context.getSite()
    install_catalog_indexes(portal, reindex=True)
