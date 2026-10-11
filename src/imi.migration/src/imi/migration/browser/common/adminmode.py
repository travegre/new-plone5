# -*- coding: utf-8 -*-
"""Hostname-selected administrative presentation.

Admin mode is deliberately detected from the request hostname without changing
the request's browser-layer interfaces.  This keeps Plone/Barceloneta's normal
backend layers, viewlets and resource registrations intact.

Locally, requests through 127.0.0.1 activate admin mode.  In production, any
hostname beginning with ``admin.`` does the same.  Reverse proxies are supported
through X-Forwarded-Host.
"""
from Products.Five import BrowserView


def request_host(request):
    environ = getattr(request, 'environ', {}) or {}
    forwarded = environ.get('HTTP_X_FORWARDED_HOST', '')
    raw = (forwarded.split(',')[0].strip() if forwarded else
           environ.get('HTTP_HOST', '') or
           environ.get('SERVER_NAME', ''))
    host = raw.strip().lower()
    if host.startswith('['):
        end = host.find(']')
        return host[1:end] if end != -1 else host
    if host.count(':') == 1:
        host = host.split(':', 1)[0]
    return host.rstrip('.')


def is_admin_request(request):
    host = request_host(request)
    return host == '127.0.0.1' or host.startswith('admin.')


class AdminFolderView(BrowserView):
    """Render a folder using Plone's normal content-management listing."""

    def __call__(self):
        return self.context.restrictedTraverse('folder_contents')()


class AdminContentView(BrowserView):
    """Render editable content using its normal Dexterity edit form."""

    def __call__(self):
        return self.context.restrictedTraverse('@@edit')()
