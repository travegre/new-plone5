# -*- coding: utf-8 -*-
"""Dynamic vocabularies used by the migrated editing forms."""
from zope.component.hooks import getSite
from zope.interface import provider
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


@provider(IVocabularyFactory)
def duty_staff_vocabulary(context):
    """Return the old dezurstva ``(id, title)`` staff vocabulary.

    Plone 4 stored person ids in every roster LinesField and used the title
    from ``/dezurstva/seznam_zaposlenih`` only as the widget label.  Preserve
    that contract so migrated values remain unchanged while editors see names.
    """
    site = getSite()
    if site is None:
        return SimpleVocabulary([])

    directory = site.get('seznam_zaposlenih')
    if directory is None:
        return SimpleVocabulary([])

    terms = []
    for employee in directory.objectValues():
        if getattr(employee, 'portal_type', None) != 'imi.staff.employee':
            continue
        if bool(getattr(employee, 'exclude_from_nav', False)):
            continue
        employee_id = str(employee.getId())
        title = employee.Title() or employee_id
        terms.append(SimpleTerm(
            value=employee_id,
            token=employee_id,
            title=title,
        ))
    return SimpleVocabulary(terms)
