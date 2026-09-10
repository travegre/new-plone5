# -*- coding: utf-8 -*-
"""Compatibility helpers for the parallel legacy Preiskave sample fields."""
from .legacy_sites import ExaminationView as BaseExaminationView


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return [str(item or '') for item in value]
    text = str(value or '')
    if not text:
        return []
    # Exported Archetypes LinesFields arrive as tuple/list. Keep newline as a
    # tolerant fallback for manually edited/migrated values.
    return [item for item in text.split('\n')]


def _at(values, index):
    return values[index] if index < len(values) else ''


def _youtube_embed_url(value):
    """Port the old template's watch?v= -> v/ conversion without JS."""
    url = str(value or '').strip()
    if not url:
        return ''
    return url.replace('watch?v=', 'v/')


class ExaminationView(BaseExaminationView):

    def sample_rows(self):
        samples = _as_list(getattr(self.context, 'vzorci', None))
        labs = _as_list(getattr(self.context, 'vzorci_lab', None))
        phones = _as_list(getattr(self.context, 'vzorci_lab_tel', None))
        abbreviations = _as_list(getattr(self.context, 'vzorci_lab_kratica', None))
        collection = _as_list(getattr(self.context, 'vzorci_odvzem', None))
        videos = _as_list(getattr(self.context, 'vzorci_odvzem_video_sifra', None))
        amounts = _as_list(getattr(self.context, 'vzorci_kolicina', None))
        packaging = _as_list(getattr(self.context, 'embalaza_slika_sifra', None))
        transport = _as_list(getattr(self.context, 'vzorci_transport', None))
        notes = _as_list(getattr(self.context, 'vzorci_opomba', None))

        rows = []
        for index, raw_sample in enumerate(samples):
            if not raw_sample:
                continue
            sample_parts = raw_sample.split('###')
            lab_names = _at(labs, index).split('###') if _at(labs, index) else []
            lab_phones = _at(phones, index).split('###') if _at(phones, index) else []
            lab_codes = _at(abbreviations, index).split('###') if _at(abbreviations, index) else []
            lab_rows = []
            maximum = max(len(lab_names), len(lab_phones), len(lab_codes), 0)
            for pos in range(maximum):
                name = _at(lab_names, pos)
                phone = _at(lab_phones, pos)
                code = _at(lab_codes, pos)
                if name or phone or code:
                    lab_rows.append({
                        'name': name,
                        'phone': phone,
                        'code': code,
                        'number': pos + 1,
                    })
            rows.append({
                'name': sample_parts[0],
                'collection': _at(collection, index),
                'transport': _at(transport, index),
                'amount': _at(amounts, index),
                'note': _at(notes, index),
                'packaging': [item for item in _at(packaging, index).split('#') if item],
                'video': _youtube_embed_url(_at(videos, index)),
                'labs': lab_rows,
            })
        return rows

    def packaging_url(self, code):
        site = self.context.getPhysicalRoot().get('preiskave')
        base = site.absolute_url() if site is not None else self.context.portal_url()
        return base + '/++resource++imi.migration/embalazaSlike/' + str(code)
