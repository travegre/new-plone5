# Plone 4.3 -> 5.2 legacy behavior parity audit

This audit treats TAL/Python expressions, skin scripts, JavaScript, field ordering, hidden columns, sorting, formatting and URL behavior as application logic. Visual similarity alone is not considered parity.

Source baseline: `travegre/my-plone-migration` at `66815cf3e91ed7f81d1ceab1238da2f09dfbd52b`.
Target: `travegre/new-plone5`, branch `frontend-legacy-fidelity`.

Status vocabulary:

- **PRESERVED**: equivalent behavior exists in the Plone 5 implementation.
- **FIXED**: a migration omission was found and corrected.
- **MODERNIZED**: implementation changed but the intended user-visible behavior is preserved.
- **OPEN DEFECT**: verified mismatch still requiring a code fix.
- **OPEN DECISION**: old behavior and new behavior differ, but it is not yet clear whether the old behavior was intentional.

## Cross-site date handling

### Source behavior

Dežurstva, Kiestra and Nadomeščanja used a text date field showing Slovenian `dd.mm.yyyy`. The old jQuery UI picker used `dateFormat: "dd.mm.yy"`; JavaScript converted the selected date to ISO only when necessary for the old request flow. The date shown in the input was the currently selected day, not unconditionally today's date.

### Target audit

- **FIXED** Native `<input type="date">` was a fidelity regression. `lang="sl-SI"` does not guarantee Slovenian presentation and the HTML value remains ISO.
- **FIXED** Public selected-date inputs now display `dd.mm.yyyy`.
- **FIXED** Date-range export inputs now display and submit `dd.mm.yyyy`, matching the server parsers.
- **FIXED** A shared vanilla-JS Slovenian picker replaces the obsolete jQuery UI dependency. It uses Slovenian month/day labels and Monday as the first day of the week.
- **FIXED** The selected day, rather than always today, is placed in the main date input.
- **MODERNIZED** jQuery UI is not reintroduced; only its relevant user-visible date behavior is reproduced.

Shared implementation:

- `src/imi.migration/src/imi/migration/static/common/sl-date-picker.js`
- `src/imi.migration/src/imi/migration/static/common/sl-date-picker.css`

## IMENIK

Source template:

- `src/imiimenik.podoba/imiimenik/podoba/skins/imiimenik_podoba_custom_templates/main_template.pt`
- legacy `imiimenik.js` and `livesearch_reply` behavior

Target:

- `browser/imenik/directory_public.pt`
- `browser/imenik/runtime.py`
- `static/imenik/directory-legacy.css`

Audit results:

- **PRESERVED** Search field identity and legacy interaction model (`#searchGadget`, category-driven search, live result area).
- **PRESERVED** Empty/too-short searches do not return the complete directory.
- **FIXED** Legacy-result response format was previously wrong during migration; the Plone 5 endpoint now returns a result fragment instead of a full page.
- **FIXED** Contact-detail interaction no longer disappears immediately because of the old blur/hide timing behavior.
- **FIXED** Stale asynchronous searches can no longer overwrite a newer query. A request-generation guard ensures that only the newest live-search response updates the result area.
- **MODERNIZED** Old Plone/jQuery livesearch internals are replaced by a site-local fetch implementation rather than emulating Plone 4's global livesearch object.
- **VERIFY IN BROWSER** Category expansion/sorting and all legacy contact-field formatting should be regression-tested against representative records, especially records with missing telephone/DECT/mobile values.

## DEŽURSTVA

Source template:

- `src/dezurstva.podoba/dezurstva/podoba/skins/dezurstva_podoba_custom_templates/main_template.pt`
- `dezurstva_brez_kontaktov.pt` is a second legacy presentation variant.

Target:

- `browser/dezurstva/duty.py`
- `browser/dezurstva/duty_public.pt`
- `static/dezurstva/duty-public.js`

Audit results:

- **PRESERVED** Slovenian weekday/date heading and previous/next-day navigation.
- **PRESERVED** Last-change display is localized as `dd.mm.yyyy ob HH:MM`.
- **PRESERVED** Automatic refresh just after midnight (`00:00:10`).
- **PRESERVED** Employee selectors are alphabetically sorted in the new Python implementation rather than by `jquery.tinysort`.
- **PRESERVED** `vpis` personnel are displayed in reverse list order, matching the legacy `[::-1]` rule.
- **PRESERVED** "all duties for person" is based on `dezurni_zdravnik`, matching the old catalog query.
- **FIXED** Public date selection and export ranges use explicit Slovenian `dd.mm.yyyy` input/picker behavior.
- **MODERNIZED** The old jQuery UI datepicker and tinysort dependencies are removed.
- **OPEN DEFECT** Readiness rows (`BOR`, `HIV`, `HUM`, `PRZ`, `IT`, `KLM`, `KOV`, `WHO`, `kiestra`) have a third contact column in the template, but the current target row builder does not populate `row['contact']`. The old template obtained the value from the employee `Description().split('|')[0]` (except in the `dezurstva_brez_kontaktov` variant). This must be restored.
- **VERIFY/FIX** Compare every legacy readiness field and label, including fields that were commented out in the old template, against the current `TEAM_FIELDS` and `READINESS_FIELDS`. Commented-out legacy fields should remain intentionally omitted rather than being accidentally resurrected.
- **VERIFY/FIX** Confirm intervention-group telephone fallback and employee-contact parsing against representative migrated staff data.

## KIESTRA

Source template:

- `src/kiestra.podoba/kiestra/podoba/skins/kiestra_podoba_custom_templates/main_template.pt`

Target:

- `browser/kiestra/views.py`
- `browser/kiestra/kiestra_public.pt`
- `static/kiestra/kiestra-legacy.css`

Verified legacy table rules:

1. Build eight internal assignment lists: `priprava_vzorcev`, `cepljenje_vzorcev`, `odcitavanje`, `identifikacija`, `antibiogram`, `izolacija`, `odpad`, `ciscenje`.
2. Compute the row count from all eight lists and render `max(lengths) + 2` rows.
3. Render source indexes `0..6` but suppress index `5` (`izolacija`), producing visible columns `0,1,2,3,4,6`.
4. Resolve employee IDs through the Dežurstva staff directory.
5. Shorten ordinary employee names to `Firstname S.`.
6. If a resolved title begins with `<span>`, preserve it unchanged and render it as structure/HTML.
7. Render notes as structure/HTML.

Audit results:

- **FIXED** The eight-list row-count rule and `+2` rows have been restored.
- **FIXED** Hidden index 5 / visible-column semantics have been restored rather than approximated as an unrelated six-column table.
- **FIXED** `<span>` employee-title exception and structure rendering have been restored.
- **FIXED** Notes are rendered as structure, matching the old template's behavior.
- **PRESERVED** Ordinary names are shortened to first name plus surname initial.
- **PRESERVED** Staff options are alphabetically sorted without jQuery tinysort.
- **FIXED** Slovenian `dd.mm.yyyy` picker and selected-date display restored.
- **FIXED** Automatic refresh just after midnight restored.
- **MODERNIZED** jQuery UI datepicker replaced with the shared vanilla-JS Slovenian picker.
- **OPEN DECISION** Old "Prikaži vsa dežurstva za osebo" queried only `priprava_vzorcev`. The current Plone 5 implementation searches all eight assignment fields. This is broader and arguably more useful, but it is not strict parity. Do not silently change it until we decide whether to preserve the old limitation.
- **VERIFY/FIX** Compare `stalni_tekst` RichText rendering against actual migrated records, including embedded markup.

## PREISKAVE

Source examples:

- `src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_custom_templates/preiskava_view.pt`
- `src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_styles/imipreiskave.css`
- legacy `livesearch.js` and related skin scripts

Target:

- `browser/preiskave/preiskave_legacy.pt`
- `browser/preiskave/preiskave_detail_legacy.pt`
- `browser/preiskave/views.py`
- `static/preiskave/preiskave-legacy.css`

Audit results already fixed during fidelity work:

- **FIXED** `Vzorci in navodila` starts closed.
- **FIXED** Legacy slide transitions restored.
- **FIXED** `fajli_dol_new.png` / `fajli_gor_new.png` restored.
- **FIXED** Detail columns restored to the old 20% / 55% / 20% proportions.
- **FIXED** `Šifra preiskave` restored in the right column with old-ID fallback.
- **FIXED** RichText output rendered as markup rather than escaped text.
- **FIXED** Non-legacy `Prikaži več` control removed.
- **FIXED** Four original catalog icons restored.
- **FIXED** TAL call corrected to invoke the view method for `laboratoriji` rather than traverse it as an attribute.
- **PRESERVED** Normal navigation uses canonical migrated object URLs rather than proxy-style `@@...?...id=` links.
- **MODERNIZED** Legacy livesearch code is not reused blindly where it depends on Plone 4/global jQuery internals.
- **VERIFY/FIX** Continue field-by-field comparison of menu/category click semantics and search filters against old skin scripts; this site historically contained the highest amount of behavior embedded in skins.

## NADOMEŠČANJA

Source template:

- `src/nadomescanja.podoba/nadomescanja/podoba/skins/nadomescanja_podoba_custom_templates/main_template.pt`

Target:

- `browser/nadomescanja/views.py`
- `browser/nadomescanja/replacements_public.pt`
- `static/nadomescanja/public.js`

Audit results:

- **PRESERVED** Slovenian date heading and previous/next navigation.
- **PRESERVED** Last-change display is localized.
- **PRESERVED** Person-history dates are grouped by year/month with Slovenian month names.
- **PRESERVED** Replacement table keeps the leader/replacement distinction and marks replaced leaders separately.
- **FIXED** Main selected-date input and export ranges now display `dd.mm.yyyy` with a Slovenian/Monday-first picker.
- **MODERNIZED** jQuery UI datepicker replaced with shared vanilla-JS picker.
- **VERIFY/FIX** Compare old person-history selection semantics, export period handling, and any old laboratory ordering rules against migrated JSON-backed rows. These need data-backed regression tests because storage was intentionally redesigned.

## Required regression matrix

For each public site, test at minimum:

1. today and a non-today date;
2. previous/next navigation;
3. manually typed `dd.mm.yyyy` date;
4. calendar-picked date;
5. empty/missing records for the selected day;
6. person-history selection;
7. records with missing employee references;
8. records containing legacy HTML/RichText where applicable;
9. export custom `od-do` dates where supported;
10. midnight-refresh pages (Dežurstva and Kiestra).

## Priority follow-up defects

1. Restore Dežurstva readiness contact values from migrated employee data, matching the old `Description().split('|')[0]` rule or the equivalent migrated field.
2. Decide whether Kiestra person-history must reproduce the old `priprava_vzorcev`-only query or intentionally keep the broader all-fields behavior.
3. Run data-backed parity checks for Preiskave menu/search semantics and Nadomeščanja JSON row ordering.
4. Audit admin/edit forms separately from public fidelity. Public legacy behavior and Barceloneta admin behavior are intentionally different presentation layers, but data transformations must remain equivalent.
