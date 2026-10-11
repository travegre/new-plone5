# -*- coding: utf-8 -*-
"""Base helpers for Preiskave detail views."""
from Products.Five import BrowserView

from ..common.helpers import rich


class ExaminationView(BrowserView):
    def rich(self, name):
        return rich(getattr(self.context, name, ''))

    def text(self, name):
        value = getattr(self.context, name, '')
        if isinstance(value, (tuple, list)):
            return u', '.join(str(v) for v in value if v)
        return str(value or '')

    def code(self):
        value = str(getattr(self.context, 'sifra', '') or '')
        if value:
            return value
        object_id = self.context.getId()
        return object_id.split('_', 1)[1] if '_' in object_id else object_id

    def samples(self):
        raw_samples = getattr(self.context, 'vzorci', '') or ''
        if isinstance(raw_samples, (tuple, list)):
            samples = list(raw_samples)
        else:
            text = str(raw_samples)
            samples = [part for part in text.split('\n') if part.strip()]
            if len(samples) <= 1 and '###' in text:
                samples = [part for part in text.split('###') if part.strip()]
        return [str(item) for item in samples if str(item).strip()]
