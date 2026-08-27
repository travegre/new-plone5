#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Make the Dežurstva editor dashboard the site-root Pogled view."""


def run(app):
    import transaction

    if 'dezurstva' not in app.objectIds():
        raise SystemExit('Missing /dezurstva site')

    site = app['dezurstva']
    set_default = getattr(site, 'setDefaultPage', None)
    if callable(set_default):
        set_default(None)
    set_layout = getattr(site, 'setLayout', None)
    if not callable(set_layout):
        raise SystemExit('/dezurstva does not support setLayout')
    set_layout('@@dezurstva-home')
    transaction.commit()
    print('/dezurstva: default page cleared')
    print('/dezurstva: layout -> @@dezurstva-home')
    print('/dezurstva/folder_contents remains the Vsebine view')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
