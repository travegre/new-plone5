# -*- coding: utf-8 -*-
"""Browser-layer interfaces shared by the migrated IMI sites."""
from plone.theme.interfaces import IDefaultPloneLayer


class IIMIAdminLayer(IDefaultPloneLayer):
    """Request marker for the administrative presentation of an IMI site."""
