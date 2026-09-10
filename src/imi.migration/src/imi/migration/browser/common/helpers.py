# -*- coding: utf-8 -*-
"""Small helpers genuinely shared by the five browser applications."""
from datetime import date, datetime, timedelta

from plone import api


DAY_NAMES = {
    0: u'ponedeljek', 1: u'torek', 2: u'sreda', 3: u'četrtek',
    4: u'petek', 5: u'sobota', 6: u'nedelja',
}
MONTH_NAMES = {
    1: u'januar', 2: u'februar', 3: u'marec', 4: u'april',
    5: u'maj', 6: u'junij', 7: u'julij', 8: u'avgust',
    9: u'september', 10: u'oktober', 11: u'november', 12: u'december',
}


def portal(context=None):
    return api.portal.get()


def sibling_site(context, site_id):
    return context.getPhysicalRoot().get(site_id)


def inner_site(context, site_id):
    inner = context.get(site_id)
    if inner is not None and getattr(inner, 'portal_type', None) == 'Plone Site':
        return inner
    return context


def staff_directory(context):
    site = sibling_site(context, 'dezurstva')
    return site.get('seznam_zaposlenih') if site is not None else None


def staff_objects(context):
    directory = staff_directory(context)
    if directory is None:
        return []
    result = []
    for employee in directory.objectValues():
        if getattr(employee, 'portal_type', None) != 'imi.staff.employee':
            continue
        if bool(getattr(employee, 'exclude_from_nav', False)):
            continue
        result.append(employee)
    return result


def employee_id(employee):
    return str(getattr(employee, 'source_employee_id', '') or employee.getId())


def employee_by_id(context, identifier):
    identifier = str(identifier or '')
    directory = staff_directory(context)
    if directory is None:
        return None
    found = directory.get(identifier)
    if found is not None:
        return found
    for employee in staff_objects(context):
        if employee_id(employee) == identifier:
            return employee
    return None


def staff_title(context, identifier):
    employee = employee_by_id(context, identifier)
    return employee.Title() if employee is not None else str(identifier or '')


def staff_options(context):
    items = [(employee_id(employee), employee.Title() or employee_id(employee))
             for employee in staff_objects(context)]
    return sorted(items, key=lambda item: item[1].lower())


def parse_date(value, default_today=False):
    value = str(value or '').strip()
    if not value and default_today:
        return date.today()
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(u'Datum mora biti veljaven.')


def formatted_date(value):
    prefix = u'danes, ' if value == date.today() else u''
    return u'%s%s, %02d.%02d.%04d' % (
        prefix, DAY_NAMES[value.weekday()], value.day, value.month, value.year)


def rich(value):
    if value is None:
        return u''
    output = getattr(value, 'output', None)
    if output is not None:
        return str(output or '')
    raw = getattr(value, 'raw', None)
    if raw is not None:
        return str(raw or '')
    return str(value or '')


def period(request):
    mode = str(request.form.get('izbira') or request.form.get('izvoz-1-izbira') or
               request.form.get('izvoz-2-izbira') or '')
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if mode == 'teden':
        return monday - timedelta(days=7), monday - timedelta(days=1)
    if mode == 'tedenplus2':
        return monday, monday + timedelta(days=14)
    if mode == 'tekoci':
        first = today.replace(day=1)
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        return first, next_month - timedelta(days=1)
    if mode == 'pretekli':
        first = today.replace(day=1)
        last = first - timedelta(days=1)
        return last.replace(day=1), last
    if mode == 'oddo':
        first = parse_date(request.form.get('od'))
        last = parse_date(request.form.get('do'))
        return (first, last) if first <= last else (last, first)
    raise ValueError(u'Izberite obdobje za izvoz.')


def date_group(rows):
    grouped = {}
    for item in rows:
        grouped.setdefault(item['date'].year, {}).setdefault(item['date'].month, []).append(item)
    result = []
    for year in sorted(grouped, reverse=True):
        months = []
        for month in sorted(grouped[year], reverse=True):
            months.append({
                'number': month,
                'name': MONTH_NAMES[month],
                'dates': sorted(grouped[year][month], key=lambda row: row['date'], reverse=True),
            })
        result.append({'year': year, 'months': months})
    return result


def is_editor(context):
    return api.user.has_permission('Modify portal content', obj=context)


def walk(container):
    for obj in container.objectValues():
        yield obj
        if hasattr(obj, 'objectValues'):
            for child in walk(obj):
                yield child
