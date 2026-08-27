# -*- coding: utf-8 -*-
"""Dynamic vocabularies used by the migrated editing forms."""
from zope.component.hooks import getSite
from zope.interface import provider
from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleTerm
from zope.schema.vocabulary import SimpleVocabulary


def _staff_directory():
    site = getSite()
    if site is None:
        return None

    # The old Nadomeščanja getSampleVocabulary50() explicitly traversed
    # /dezurstva/seznam_zaposlenih, so preserve that cross-site dependency.
    site_id = getattr(site, 'getId', lambda: '')()
    if site_id == 'nadomescanja':
        app = getattr(site, 'aq_parent', None)
        dezurstva = app.get('dezurstva') if app is not None else None
        if dezurstva is not None:
            return dezurstva.get('seznam_zaposlenih')

    return site.get('seznam_zaposlenih')


def _visible_employees(directory):
    if directory is None:
        return ()
    return (
        employee for employee in directory.objectValues()
        if getattr(employee, 'portal_type', None) == 'imi.staff.employee'
        and not bool(getattr(employee, 'exclude_from_nav', False))
    )


@provider(IVocabularyFactory)
def duty_staff_vocabulary(context):
    """Return the old roster ``(id, title)`` staff vocabulary.

    Plone 4 stored person ids in every roster LinesField and used the title
    from ``/dezurstva/seznam_zaposlenih`` only as the widget label. Preserve
    that contract so migrated values remain unchanged while editors see names.
    """
    terms = []
    for employee in _visible_employees(_staff_directory()):
        employee_id = str(employee.getId())
        title = employee.Title() or employee_id
        terms.append(SimpleTerm(
            value=employee_id,
            token=employee_id,
            title=title,
        ))
    return SimpleVocabulary(terms)


@provider(IVocabularyFactory)
def form_staff_email_vocabulary(context):
    """Vocabulary used by the migrated PFG ``ime-in-priimek`` field.

    This reproduces the old ``getSampleVocabulary50`` contract exactly:
    the visible label is the employee title; the stored value is the employee
    e-mail address when one exists, otherwise the employee id. Mailer2 in the
    old form used the presence of ``@`` in this value to decide whether to send
    a copy of the submission to the selected employee.
    """
    terms = [SimpleTerm(value='', token='', title='')]
    seen_tokens = {''}
    for employee in _visible_employees(_staff_directory()):
        employee_id = str(employee.getId())
        email = str(getattr(employee, 'email', '') or '').strip()
        value = email or employee_id
        title = employee.Title() or employee_id
        # Vocabulary tokens must be unique. In the unlikely event of duplicate
        # e-mail values, fall back to the employee id so the form remains usable.
        token = value
        if token in seen_tokens:
            value = employee_id
            token = employee_id
        seen_tokens.add(token)
        terms.append(SimpleTerm(value=value, token=token, title=title))
    return SimpleVocabulary(terms)
