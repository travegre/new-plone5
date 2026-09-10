# -*- coding: utf-8 -*-
"""Hostname-selected administrative browser layer.

The same ZODB content tree is rendered differently for administrative requests.
Locally, requests through 127.0.0.1 activate admin mode.  In production, any
hostname beginning with ``admin.`` does the same.  Reverse proxies are supported
through X-Forwarded-Host.
"""
from zope.interface import alsoProvides
from Products.Five import BrowserView

from .interfaces import IIMIAdminLayer


def _request_host(request):
    environ = getattr(request, 'environ', {}) or {}
    forwarded = environ.get('HTTP_X_FORWARDED_HOST', '')
    raw = (forwarded.split(',')[0].strip() if forwarded else
           environ.get('HTTP_HOST', '') or
           environ.get('SERVER_NAME', ''))
    # Strip an ordinary host:port suffix while keeping IPv6 literals harmless.
    host = raw.strip().lower()
    if host.startswith('['):
        end = host.find(']')
        return host[1:end] if end != -1 else host
    if host.count(':') == 1:
        host = host.split(':', 1)[0]
    return host.rstrip('.')


def is_admin_request(request):
    host = _request_host(request)
    return host == '127.0.0.1' or host.startswith('admin.')


def activate_admin_layer(context, event):
    request = event.request
    if is_admin_request(request) and not IIMIAdminLayer.providedBy(request):
        alsoProvides(request, IIMIAdminLayer)


class AdminFolderView(BrowserView):
    """Render a folder using Plone's normal content-management listing."""

    def __call__(self):
        return self.context.restrictedTraverse('folder_contents')()


class AdminContentView(BrowserView):
    """Render editable content using its normal Dexterity edit form."""

    def __call__(self):
        return self.context.restrictedTraverse('@@edit')()
