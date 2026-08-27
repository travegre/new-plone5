#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restore the legacy Dežurstva root navigation order and visibility.

The old site exposed these root objects in this order:

* seznam_zaposlenih
* dezurstva-1 (Dežurstva)
* spremeni-dezurstvo (Sprememba dežurstva)
* objekt-za-seznam-zaposlenih-v-formi-spremeni-dezurstvo-ne-brisi

The final helper object is intentionally preserved: the legacy
``Sprememba dežurstva`` form used it as the context exposing
``getSampleVocabulary50()``.
"""

NAV_IDS = (
    'seznam_zaposlenih',
    'dezurstva-1',
    'spremeni-dezurstvo',
    'objekt-za-seznam-zaposlenih-v-formi-spremeni-dezurstvo-ne-brisi',
)


def run(app):
    import transaction

    if 'dezurstva' not in app.objectIds():
        raise SystemExit('Missing /dezurstva site')

    site = app['dezurstva']
    missing = [obj_id for obj_id in NAV_IDS if obj_id not in site.objectIds()]
    if missing:
        raise SystemExit('Missing required Dežurstva objects: %s' % ', '.join(missing))

    for position, obj_id in enumerate(NAV_IDS):
        obj = site[obj_id]
        if hasattr(obj, 'exclude_from_nav'):
            obj.exclude_from_nav = False
        try:
            obj.reindexObject(idxs=['exclude_from_nav', 'sortable_title'])
        except Exception:
            try:
                obj.reindexObject()
            except Exception:
                pass

        mover = getattr(site, 'moveObjectToPosition', None)
        if callable(mover):
            mover(obj_id, position)

        print('%d. /dezurstva/%s -> visible' % (position + 1, obj_id))

    transaction.commit()
    print('Dežurstva root navigation restored.')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
