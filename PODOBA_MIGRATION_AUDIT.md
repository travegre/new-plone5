# Podoba migration audit: Plone 4.3 -> Plone 5.2

## Purpose

The five `*.podoba` packages are **not just public themes**. They contain a mixture of public presentation, shared templates/resources, and editor/admin customizations. The Plone 5.2 migration must preserve the editing workflows that depend on those overrides, not merely reproduce the anonymous appearance.

Source of truth for this audit: the current `main` tree of `travegre/my-plone-migration`.

## Migration rule

Do **not** install or mechanically port the old CMF `portal_skins` layers into Plone 5.2. Reimplement each behavior using Plone 5-compatible browser views, Dexterity/z3c.form widgets, view/template overrides, adapters, and resource registrations. Preserve behavior first; preserve visual appearance second.

The old skin-path configuration itself proves that admin layers were part of the active application. For example, `dezurstva.podoba` defines `dezurstva podoba` as the default skin and includes `dezurstva_podoba_admin` in that skin path after the public image/template/style layers.

## Priority classes

| Priority | Meaning | Acceptance requirement |
| --- | --- | --- |
| P0 | Editing/admin behavior | Must work before public cut-over. Editors must be able to perform the same business task in Plone 5.2. |
| P1 | Shared application behavior | Must be functionally equivalent before cut-over. |
| P2 | Public rendering | Must reproduce the required public views and interactions. |
| P3 | Cosmetic/static assets | Port after behavior is correct; no legacy JS library is copied blindly. |

## Cross-package findings

### Legacy technologies that must be replaced

- CMF `portal_skins` filesystem layers and skin selections.
- Old `main_template.pt` replacements where they encode business/edit behavior.
- Python Scripts stored under skin folders (`*.py`).
- Bundled jQuery 1.5.1 and old jQuery UI.
- `cssregistry.xml` / `jsregistry.xml` registrations.
- Old Archetypes-era edit/view assumptions.

### Plone 5.2 replacement patterns

- Browser views (`BrowserView`) for Python skin scripts and complex page templates.
- Dexterity edit-form/widget customizations for editor-side interaction.
- z3c.form adapters/widgets or form-extender patterns where a content edit form needs custom behavior.
- Browser-layer-specific template overrides only when the underlying Plone 5 view still exists and an override is genuinely required.
- `plone.resource` / Resource Registry bundles for JS/CSS, using the Plone 5 jQuery stack rather than bundling jQuery 1.5.1.
- Dedicated views/endpoints for legacy helpers such as `izberi_dezurstvo.py`, `izvoz.py`, and livesearch logic.

## Site-by-site audit

### 1. `imiimenik.podoba` — `/portal`

Observed structure:

- browser package with `configure.zcml`, browser-layer interface, viewlet code/template and resource directories;
- `imiimenik_podoba_custom_images`;
- `imiimenik_podoba_custom_templates`;
- `imiimenik_podoba_styles`;
- GenericSetup `cssregistry.xml`, `jsregistry.xml`, `skins.xml`, and `viewlets.xml`.

Important legacy files already identified:

- `skins/imiimenik_podoba_custom_templates/main_template.pt`
- `skins/imiimenik_podoba_custom_templates/livesearch_reply.py`
- image assets including `logo.png`, `krivulja.png`, `ozadje_body.png`

Classification:

| Area | Priority | Plone 5.2 action |
| --- | --- | --- |
| `livesearch_reply.py` | P1/P2 | Reimplement as an explicit browser endpoint/view. Preserve the response contract that the old one-page directory UI expects. Do not restore the old Plone 4 livesearch implementation wholesale. |
| custom `main_template.pt` | P1/P2 | Extract layout and behavior dependencies. Implement the public directory page/view without replacing the global Plone 5 admin template. |
| CSS/images/viewlets | P2/P3 | Move to a site-specific resource bundle/browser layer. |
| editor/admin behavior | P0 | No dedicated `_admin` skin directory is visible in this package, but any edit-related assumptions in `main_template.pt`, viewlets or JS must be tested before declaring this site complete. |

Acceptance tests:

- anonymous directory page behaves like the Plone 4 public version;
- livesearch returns the same business results for representative queries;
- logged-in editor can open/edit a migrated directory person using Plone 5 UI without the public template interfering;
- no old jQuery library is loaded.

### 2. `dezurstva.podoba` — `/dezurstva`

This package is explicitly mixed public/admin code.

Observed admin artifacts:

- browser override: `browser/overrides/plone.app.content.browser.folder_contents.pt`;
- skin layer: `dezurstva_podoba_admin`;
- `dezurstva_admin.pt`;
- `dezurstvo.js` and `dezurstvo.css`;
- `izberi_dezurstvo.py`;
- old jQuery 1.5.1, jQuery UI, TinySort, table-filter resources and UI images.

Observed public/shared artifacts include:

- `dezurstva_podoba_custom_templates`;
- `dezurstva_brez_kontaktov.pt`;
- `izberi_dezurstvo.py`;
- `izvoz.py`;
- custom CSS and duplicated old JS libraries;
- image/style layers and viewlet registrations.

Classification:

| Area | Priority | Plone 5.2 action |
| --- | --- | --- |
| `folder_contents.pt` override | **P0** | Diff against the Plone 4 original and identify the business behavior added. Reimplement only that behavior on top of Plone 5 folder/content management; do not copy the Plone 4 template. |
| `dezurstva_admin.pt` | **P0** | Port as a dedicated Plone 5 browser/admin view for duty-roster management. |
| `dezurstvo.js` | **P0** | Read behavior line-by-line; port interactions against the new Dexterity fields/views. Replace old jQuery UI APIs where necessary. |
| `izberi_dezurstvo.py` | P0/P1 | Replace with a browser endpoint/view; preserve request/response semantics used by admin/public JS. |
| `izvoz.py` | P1 | Replace with a browser view/download endpoint and preserve export semantics. |
| `dezurstva_brez_kontaktov.pt` | P2 | Port as a named public view/template. |
| old JS libraries | P3 | Do not copy. Use Plone 5 resources/native browser APIs/current bundled jQuery as needed. |

Acceptance tests:

- editor can perform the same roster-selection/editing workflow that currently uses `dezurstva_admin.pt`, `izberi_dezurstvo.py` and `dezurstvo.js`;
- folder/content-management behavior added by the old `folder_contents.pt` override is preserved;
- public roster views render equivalent data;
- exports still work and produce equivalent business data.

### 3. `kiestra.podoba` — `/kiestra`

Observed skin layers:

- `kiestra_podoba_admin`;
- `kiestra_podoba_custom_images`;
- `kiestra_podoba_custom_templates`;
- `kiestra_podoba_styles`.

Important admin artifacts:

- `dezurstva_admin.pt`;
- `dezurstvo.js` / `dezurstvo.css`;
- `izberi_dezurstvo.py`;
- `base_properties.props`;
- old jQuery 1.5.1, jQuery UI and supporting plugins/images.

Classification:

| Area | Priority | Plone 5.2 action |
| --- | --- | --- |
| admin duty UI (`dezurstva_admin.pt`) | **P0** | Port to a Plone 5 browser/admin view bound to the migrated Kiestra work-day Dexterity type. |
| `dezurstvo.js` | **P0** | Port behavior against Dexterity fields and Plone 5 resources. |
| `izberi_dezurstvo.py` | P0/P1 | Replace with explicit browser endpoint/view. |
| base properties / old skin styling | P2/P3 | Translate only relevant visual variables into new CSS; do not preserve CMF property-sheet mechanics. |
| public templates/resources | P2 | Port as named views and site-specific bundle after admin behavior is verified. |

Acceptance tests:

- editor workflow for selecting/editing duty/work-day data is functionally equivalent;
- migrated `imi.kiestra.work_day` content can be edited without raw Dexterity fallback being the only usable interface;
- public Kiestra rendering works independently of admin UI.

### 4. `preiskave.podoba` — `/preiskave`

Observed skin layers:

- `preiskave_podoba_admin`;
- `preiskave_podoba_custom_images`;
- `preiskave_podoba_custom_templates`;
- `preiskave_podoba_styles`.

The admin layer is substantial and contains multiple large view templates, including:

- `content_view.pt`;
- `main_template.pt`;
- `preiskava_view.pt`;
- `preiskave_view.pt`;
- `preiskave_hitro_view.pt`;
- `preiskave_lab_view.pt`;
- `preiskave_nove_view.pt`;
- `preiskave_nujne_view.pt`;
- `preiskave_podrocja_view.pt`;
- `preiskave_sklopi_view.pt`;
- `preiskave_vzorci_view.pt` and related variants.

Several of the list/view templates in the source tree are byte-identical, which suggests they may be aliases for different view names rather than truly separate implementations. That should be consolidated in Plone 5 instead of copied repeatedly.

Classification:

| Area | Priority | Plone 5.2 action |
| --- | --- | --- |
| admin `main_template.pt` | **P0** | Determine what admin chrome/behavior it changes. Do not globally replace Plone 5 `main_template`; move required behavior into site/browser views. |
| `content_view.pt` and named preiskave views | **P0/P1** | Map each legacy view name to an explicit Plone 5 browser view. Consolidate identical templates behind one implementation where semantics allow. |
| `preiskava_view.pt` | P0/P1 | Port against `imi.exams.examination` Dexterity fields. Verify edit/view assumptions. |
| public custom templates/styles | P2 | Port once business/admin views are correct. |

Acceptance tests:

- every legacy named examination/list view still resolves or has an intentional documented replacement;
- editor can view and edit `imi.exams.examination` records with the information/actions the old admin layer provided;
- specialized lists (`hitro`, `lab`, `nove`, `nujne`, `podrocja`, `sklopi`, `vzorci`, etc.) return equivalent selections/orderings;
- no old global main-template override breaks standard Plone 5 editing UI.

### 5. `nadomescanja.podoba` — `/nadomescanja`

Observed skin layers:

- `nadomescanja_podoba_admin`;
- `nadomescanja_podoba_custom_images`;
- `nadomescanja_podoba_custom_templates`;
- `nadomescanja_podoba_styles`.

Important admin artifacts:

- `dezurstva_admin.pt`;
- `izberi_dezurstvo.py`;
- `base_properties.props`;
- bundled old jQuery 1.5.1, jQuery UI, TinySort, table-filter resources and images.

Classification:

| Area | Priority | Plone 5.2 action |
| --- | --- | --- |
| admin roster/replacement UI | **P0** | Port as Plone 5 browser/admin views using `imi.replacements.day` and `imi.replacements.laboratory`. |
| `izberi_dezurstvo.py` | P0/P1 | Replace with explicit browser endpoint/view and preserve its business-selection behavior. |
| JS/plugin behavior | **P0** where used for editing | Reimplement behavior; do not carry old jQuery library versions. |
| public templates/styles/images | P2/P3 | Port after editing workflow is validated. |

Acceptance tests:

- editor can manage replacement-day/laboratory data through an equivalent workflow;
- selection/filter/sort interactions remain available;
- public replacement views remain independent from standard Plone administration.

## Required implementation order

1. **P0 admin/edit behavior first**
   - `dezurstva`: folder-contents override, admin roster template, selection endpoint, editing JS.
   - `kiestra`: admin duty template, selection endpoint, editing JS.
   - `preiskave`: admin main/content/named views and examination view behavior.
   - `nadomescanja`: admin replacement UI, selection endpoint and editing interactions.
   - `imiimenik`: verify there are no hidden editor dependencies in custom template/viewlet/JS code.

2. **P1 shared endpoints/business views**
   - selection helpers;
   - export helpers;
   - livesearch endpoint;
   - named data/list views.

3. **P2 public templates**
   - reproduce the public presentation using browser views/templates and site-specific browser layers/resources.

4. **P3 assets/resources**
   - migrate CSS/images;
   - replace old jQuery/UI/plugin dependencies rather than copying them.

## Implementation architecture in `new-plone5`

The port should live in the Plone 5 codebase, preferably inside `imi.migration` initially and split later only if maintenance benefits justify separate packages.

Suggested structure:

```text
src/imi.migration/src/imi/migration/
    browser/
        configure.zcml
        directory.py / templates/
        duty.py / templates/
        kiestra.py / templates/
        exams.py / templates/
        replacements.py / templates/
        admin/
    static/
        directory/
        duty/
        kiestra/
        exams/
        replacements/
```

Use browser-layer registrations so site-specific overrides do not leak into all five Plone sites.

## Test/acceptance matrix

For each site, test all three modes separately:

1. **Anonymous/public** — correct public view, search/list/filter behavior and assets.
2. **Authenticated editor** — standard Plone 5 chrome remains usable and all legacy business editing actions are present.
3. **Manager/admin** — folder/content management and special admin pages work; no old public template masks Plone 5 management UI.

For each ported legacy script/template, record:

- legacy path;
- callers/URLs;
- required request parameters;
- business result/output;
- Plone 5 replacement path/view name;
- automated or manual acceptance test.

## Immediate next implementation target

Start with `dezurstva.podoba`, because it demonstrates the full mixed model: a direct `folder_contents.pt` override, a dedicated admin skin, editor JS, Python selection/export helpers, and public templates. Once its Plone 5 pattern is correct, reuse the architecture for Kiestra and Nadomeščanja, then handle the larger Preiskave view set and the IMI directory/livesearch frontend.
