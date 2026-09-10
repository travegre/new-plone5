# -*- coding: utf-8 -*-
"""Template ownership for the IMI imenik frontend."""
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from ..legacy.imports import DirectoryImportView as BaseDirectoryImportView
from ..legacy.legacy_admin import DirectoryAdminView as BaseDirectoryAdminView
from ..legacy.legacy_sites import DirectoryPublicView as BaseDirectoryPublicView

class DirectoryPublicView(BaseDirectoryPublicView):
    template = ViewPageTemplateFile('directory_public.pt')
class DirectoryAdminView(BaseDirectoryAdminView):
    template = ViewPageTemplateFile('directory_admin.pt')
class DirectoryImportView(BaseDirectoryImportView):
    template = ViewPageTemplateFile('directory_import.pt')
