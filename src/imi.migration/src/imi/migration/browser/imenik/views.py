# -*- coding: utf-8 -*-
"""IMI imenik browser views."""
from plone import api
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from .imports import DirectoryImportView


class DirectoryPublicView(BrowserView):
    template = ViewPageTemplateFile('directory_public.pt')

    def __call__(self):
        return self.template()

    @property
    def portal(self):
        return api.portal.get()

    def categories(self):
        base = self.portal.get('data2')
        if base is None:
            return []
        result = []
        for folder in base.objectValues():
            if getattr(folder, 'portal_type', None) != 'Folder':
                continue
            children = [child for child in folder.objectValues()
                        if getattr(child, 'portal_type', None) == 'Folder']
            result.append({
                'title': folder.Title() or folder.getId(),
                'children': [child.Title() or child.getId() for child in children],
            })
        return result

    def is_editor(self):
        return api.user.has_permission('Modify portal content', obj=self.portal)


class DirectoryAdminView(DirectoryPublicView):
    template = ViewPageTemplateFile('directory_admin.pt')

    def __call__(self):
        return self.template()
