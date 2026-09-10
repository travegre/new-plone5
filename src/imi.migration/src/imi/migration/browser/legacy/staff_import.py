# -*- coding: utf-8 -*-
"""Admin-only replacement for seznam_zaposlenih Excel upload fields."""
from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .imports import _cell, _upload_bytes, _workbook_rows


class StaffImportView(BrowserView):
    template = ViewPageTemplateFile('staff_import.pt')

    def __init__(self, context, request):
        super().__init__(context, request)
        self.report = None
        self.error = None

    def __call__(self):
        if self.request.get('REQUEST_METHOD', 'GET').upper() == 'POST':
            try:
                self.report = self._import()
                api.portal.show_message(
                    'Uvoz zaposlenih je končan: %d novih, %d posodobljenih, %d preskočenih, %d napak.' % (
                        self.report['created'], self.report['updated'],
                        self.report['skipped'], len(self.report['errors'])),
                    request=self.request)
            except Exception as exc:
                import transaction
                transaction.abort()
                self.error = str(exc)
                api.portal.show_message('Uvoz zaposlenih ni uspel: %s' % exc,
                                        request=self.request, type='error')
        return self.template()

    def _directory(self):
        site = api.portal.get()
        directory = site.get('seznam_zaposlenih')
        if directory is None:
            raise ValueError('Manjka /dezurstva/seznam_zaposlenih.')
        return directory

    def _existing(self, directory, source_id):
        obj = directory.get(source_id)
        if obj is not None:
            return obj
        for child in directory.objectValues():
            if getattr(child, 'portal_type', None) != 'imi.staff.employee':
                continue
            if str(getattr(child, 'source_employee_id', '') or '') == source_id:
                return child
        return None

    def _set_values(self, obj, source_id, title, contact, email=None):
        obj.title = title or source_id
        obj.source_employee_id = source_id
        obj.contact = contact or ''
        if email is not None:
            obj.email = email or ''
        obj.reindexObject()

    def _import(self):
        base_data, base_name = _upload_bytes(self.request, 'datoteka1')
        phone_data, phone_name = _upload_bytes(self.request, 'datoteka2')
        if not base_data and not phone_data:
            raise ValueError('Izberite vsaj eno Excel datoteko.')
        directory = self._directory()
        created = updated = skipped = 0
        errors = []

        if base_data:
            rows = _workbook_rows(base_data, base_name)
            for index, raw in enumerate(rows, 1):
                try:
                    row = list(raw) + ['', '', '']
                    source_id, title, contact = (_cell(row[0]).strip(), _cell(row[1]).strip(), _cell(row[2]).strip())
                    if not source_id:
                        skipped += 1
                        continue
                    obj = self._existing(directory, source_id)
                    if obj is None:
                        obj = api.content.create(
                            container=directory, type='imi.staff.employee',
                            id=source_id, title=title or source_id,
                            source_employee_id=source_id, contact=contact,
                            email='', safe_id=False)
                        created += 1
                    else:
                        # The old first upload only created rows. Preserve that
                        # contract and leave existing records for datoteka2.
                        skipped += 1
                        continue
                    obj.reindexObject()
                except Exception as exc:
                    errors.append('%s vrstica %d: %s' % (base_name, index, exc))

        if phone_data:
            rows = _workbook_rows(phone_data, phone_name)
            for index, raw in enumerate(rows, 1):
                try:
                    row = list(raw) + ['', '', '', '']
                    source_id = _cell(row[0]).strip()
                    title = _cell(row[1]).strip()
                    contact = _cell(row[2]).strip()
                    email = _cell(row[3]).strip()
                    if not source_id:
                        skipped += 1
                        continue
                    obj = self._existing(directory, source_id)
                    if obj is None:
                        obj = api.content.create(
                            container=directory, type='imi.staff.employee',
                            id=source_id, title=title or source_id,
                            source_employee_id=source_id, contact=contact,
                            email=email, safe_id=False)
                        created += 1
                    else:
                        self._set_values(obj, source_id, title, contact, email)
                        updated += 1
                except Exception as exc:
                    errors.append('%s vrstica %d: %s' % (phone_name, index, exc))

        import transaction
        transaction.commit()
        return {
            'base_filename': base_name, 'phone_filename': phone_name,
            'created': created, 'updated': updated, 'skipped': skipped,
            'errors': errors,
        }
