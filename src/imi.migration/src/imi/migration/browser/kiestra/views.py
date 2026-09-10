# -*- coding: utf-8 -*-
"""Template ownership for the Kiestra frontend/editor."""
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from ..legacy.legacy_admin import KiestraAdminView as BaseKiestraAdminView
from ..legacy.legacy_editors import KiestraEditView as BaseKiestraEditView
from ..legacy.runtime_fixes import KiestraPublicView as BaseKiestraPublicView

class KiestraPublicView(BaseKiestraPublicView):
    template = ViewPageTemplateFile('kiestra_public.pt')
class KiestraAdminView(BaseKiestraAdminView):
    template = ViewPageTemplateFile('kiestra_admin.pt')
class KiestraEditView(BaseKiestraEditView):
    template = ViewPageTemplateFile('kiestra_edit.pt')
