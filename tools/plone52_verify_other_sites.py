#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify root layouts, browser views, business folders and representative data."""

from zope.component.hooks import setSite


SITE_CHECKS = {
    'portal': {
        'layout': '@@imenik-home',
        'views': ('@@imenik-home', '@@imenik-public', '@@imenik-livesearch', '@@imenik-admin'),
        'types': ('imi.directory.person',),
    },
    'kiestra': {
        'layout': '@@kiestra-home',
        'views': ('@@kiestra-home', '@@kiestra-public', '@@kiestra-admin', '@@kiestra-select', '@@kiestra-copy'),
        'types': ('imi.kiestra.work_day',),
    },
    'preiskave': {
        'layout': '@@preiskave-home',
        'views': ('@@preiskave-home', '@@preiskave-public', '@@preiskave-admin', '@@preiskave-livesearch',
                  '@@preiskave_view', '@@preiskave_hitro_view', '@@preiskave_lab_view',
                  '@@preiskave_nove_view', '@@preiskave_nujne_view', '@@preiskave_podrocja_view',
                  '@@preiskave_sklopi_view', '@@preiskave_vzorci_view'),
        'types': ('imi.exams.examination',),
    },
    'nadomescanja': {
        'layout': '@@nadomescanja-home',
        'views': ('@@nadomescanja-home', '@@nadomescanja-public', '@@nadomescanja-admin',
                  '@@nadomescanja-select', '@@nadomescanja-copy', '@@nadomescanja-izvoz',
                  '@@nadomescanja-change-request'),
        'types': ('imi.replacements.day', 'imi.replacements.laboratory'),
    },
}


def layout(site):
    getter = getattr(site, 'getLayout', None)
    return getter() if callable(getter) else getattr(site, 'layout', None)


def run(app):
    failures = []
    for site_id, check in SITE_CHECKS.items():
        if site_id not in app.objectIds():
            failures.append('/%s missing' % site_id)
            continue
        site = app[site_id]
        setSite(site)
        try:
            actual = layout(site)
            if actual != check['layout']:
                failures.append('/%s layout %r != %r' % (site_id, actual, check['layout']))
            missing_views = []
            for name in check['views']:
                try:
                    site.restrictedTraverse(name)
                except Exception as exc:
                    missing_views.append('%s (%s)' % (name, exc))
            counts = {}
            for portal_type in check['types']:
                counts[portal_type] = len(site.portal_catalog(portal_type=portal_type))
            print('/%s layout=%r' % (site_id, actual))
            print('  views: %s' % ('OK' if not missing_views else 'FAILED'))
            for item in missing_views:
                print('    %s' % item)
                failures.append('/%s %s' % (site_id, item))
            print('  content: %s' % ', '.join('%s=%d' % item for item in sorted(counts.items())))

            # Type-specific browser views on one representative object.
            if site_id == 'kiestra':
                brains = site.portal_catalog(portal_type='imi.kiestra.work_day')
                if brains:
                    brains[0].getObject().restrictedTraverse('@@kiestra-edit')
                    print('  representative Kiestra editor: OK')
            elif site_id == 'preiskave':
                brains = site.portal_catalog(portal_type='imi.exams.examination')
                if brains:
                    obj = brains[0].getObject()
                    obj.restrictedTraverse('@@preiskava_view')
                    obj.restrictedTraverse('@@view')
                    print('  representative examination views: OK')
            elif site_id == 'nadomescanja':
                brains = site.portal_catalog(portal_type='imi.replacements.day')
                if brains:
                    brains[0].getObject().restrictedTraverse('@@nadomescanja-edit')
                    print('  representative replacement editor: OK')
        except Exception as exc:
            failures.append('/%s verification exception: %r' % (site_id, exc))
            print('/%s FAILED: %r' % (site_id, exc))
        finally:
            setSite(None)

    # Cross-site staff dependency used by Kiestra and Nadomeščanja.
    if 'dezurstva' in app.objectIds():
        directory = app['dezurstva'].get('seznam_zaposlenih')
        staff_count = len(directory.objectIds()) if directory is not None else 0
        print('/dezurstva/seznam_zaposlenih staff objects=%d' % staff_count)
        if staff_count == 0:
            failures.append('shared staff directory is empty')

    if failures:
        print('\nVERIFICATION FAILED (%d):' % len(failures))
        for failure in failures:
            print('  - %s' % failure)
        raise SystemExit(1)
    print('\nAll remaining-site registrations and layouts: OK')


if 'app' not in globals():
    raise SystemExit('Run with bin/instance run inside the Plone 5.2 target.')
run(app)
