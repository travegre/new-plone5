# Plone 4.3 → Plone 5.2 Migration Audit

## Status and scope

**Source:** `travegre/my-plone-migration` (default branch, current source tree inspected)

**Target:** `travegre/new-plone5`

**Requested scope:** audit and implementation plan only. This commit adds this document only; no application code has been rewritten and the source repository has not been modified.

The source buildout is a Plone 4.3.20 standalone Zope instance with a single `Data.fs` and five logical Plone sites/applications:

- `portal` — IMI imenik
- `dezurstva` — Dežurstva
- `kiestra` — Kiestra
- `preiskave` — Preiskave
- `nadomescanja` — Nadomeščanja

The repository groups application code by those site names (`*.podoba` and `*.produkti`). The source code, rather than package names, is treated as authoritative. In particular, the audit does **not** merge identically named content types across packages.

A critical limitation is that the repository does not contain the real `Data.fs` or a database dump. Consequently this audit can determine the declared schemas, code paths, GenericSetup, skins, permissions and migration hooks, but it cannot determine actual object counts, current portal type assignments, runtime workflow assignments, stored field value shapes, PloneFormGen form instances, local roles, relations, revisions, redirects, or site-level configuration stored only in ZODB. Those must be inventoried against a copy of the real 4.3 database before production migration.

## Executive summary

This is a **complex migration**, not a simple version bump.

The main architectural blockers are:

1. The application defines seven custom Archetypes content types across five packages/sites. Plone 5.2 can run Archetypes only on Python 2.7; Archetypes therefore cannot be the final Python 3 architecture.
2. The five `*.produkti` packages are not interchangeable. The source has one `produkti` type in `imiimenik.produkti`, two different `dezurstvo` implementations in `dezurstva.produkti`, `kiestra.produkti`, and `nadomescanja.produkti`, and a separate `laboratorij` type in `nadomescanja.produkti`.
3. The `produkti` type is a person/position directory record in `imiimenik.produkti`; it must not be conflated with the other `*.produkti` packages merely because the package suffix is the same.
4. PloneFormGen is present in the buildout, but no form definition is present in source control. Forms are therefore database content and must be inventoried from each site before deciding exact EasyForm mappings.
5. `collective.easyform` is the appropriate Plone 5.2-era replacement candidate for PloneFormGen. Its 3.x line targets Plone 5.2. There is no evidence in this repository of an automatic PFG-to-EasyForm migration that can be relied upon; form recreation/data migration must be treated as a separate workstream.
6. `Products.TinyMCE` should be removed. Plone 5 provides TinyMCE through the Mockup integration.
7. `collective.editskinswitcher` is a Plone 4-era dependency. Its documented compatibility ends at Plone 4.3; the replacement should be implemented with Plone 5 skin/theme mechanisms (most likely Diazo plus request/role/site logic), after confirming the actual runtime behavior.
8. All five `*.podoba` packages use the old `portal_skins` filesystem skin architecture. Several also contain old-style `cssregistry.xml` and `jsregistry.xml`; Plone 5.2 removed support for those old registries. These need conversion to the Resource Registry and/or a modern theme/package resource structure.
9. The JavaScript is tightly coupled to Plone 4/Archetypes markup and very old jQuery plugins. Several scripts use APIs removed from current jQuery or old Plone DOM IDs. The `dezurstvo.js` code, for example, targets `.ArchetypesInAndOutWidget`, which will disappear when the fields become Dexterity widgets.
10. There is no dedicated migration package or migration script in the source tree. The `at_post_create_script`/`at_post_edit_script` methods are operational import/update hooks, not a controlled Plone 4→5 data migration.
11. The safest route is staged: first establish a reproducible Plone 5.2/Python 2 compatibility environment; run the normal Plone upgrade on a database clone; keep Archetypes temporarily available; migrate custom AT content to Dexterity while still on Python 2; port application code/add-ons to Python 3; then run the offline ZODB Python 2→3 conversion (`zodbupdate`) and validate the resulting database.
12. Plone 5.2.15 is the final 5.2 release and the 5.2 series is now unsupported. If the requirement is specifically Plone 5.2, use 5.2.15 and treat Python 3.8 as a legacy/containment target with an explicit future Plone 6 migration plan. Do not build a new production platform around Python 2.

---

# 1. Complete source package inventory

## 1.1 Buildout/application packages

`buildout.cfg` develops and installs these ten local packages:

| Package | Role | Custom content types found |
|---|---|---|
| `imiimenik.podoba` | IMI imenik theme/skin | none declared |
| `imiimenik.produkti` | IMI imenik application/content | `produkti`, `uvoz` |
| `dezurstva.podoba` | Dežurstva theme/skin/browser overrides/scripts | none declared |
| `dezurstva.produkti` | Dežurstva application/content | `seznam_zaposlenih`, `dezurstvo` |
| `kiestra.podoba` | Kiestra theme/skin/browser scripts | none declared |
| `kiestra.produkti` | Kiestra application/content | `dezurstvo` |
| `preiskave.podoba` | Preiskave theme/skin/browser scripts | none declared |
| `preiskave.produkti` | Preiskave application/content | `imipreiskava`, `imiuvozipreiskavo` |
| `nadomescanja.podoba` | Nadomeščanja theme/skin/browser scripts | none declared |
| `nadomescanja.produkti` | Nadomeščanja application/content/browser views | `laboratorij`, `dezurstvo` |

The package `SOURCES.txt` files confirm the package-level layout. The `.produkti` packages are conventional ZopeSkel-generated add-ons with `content/`, `interfaces/`, `browser/`, `portlets/`, GenericSetup profiles, and tests. The `.podoba` packages are predominantly skin/theme packages with `profiles/default/skins.xml`, browser configuration, templates, CSS/JavaScript and image assets.

### Vendored/generated artifacts

The source tree also contains old vendored Paste distributions in package directories, including versions such as `Paste-1.7.5.1-py2.6.egg`, `Paste-2.0.2-py2.6.egg`, and `Paste-2.0.3-py2.6.egg`, plus generated `*.egg-info` metadata and some `.DS_Store` assets. These are installation-era artifacts, not application source, and must not be carried into the new Python 3 environment. The target build should resolve supported dependencies from the Plone 5.2 stack rather than importing these vendored Python-2-era eggs.

## 1.2 `imiimenik.podoba`

Inventory from `imiimenik.podoba.egg-info/SOURCES.txt`:

- package initialization/configuration: `configure.zcml`, `profiles.zcml`, `skins.zcml`, `setuphandlers.py`, tests
- browser package with `interfaces.py`, `viewlet.pt`, `viewlets.py`, browser ZCML
- GenericSetup: `cssregistry.xml`, `jsregistry.xml`, `skins.xml`, `viewlets.xml`, metadata and `imiimenik.podoba_various.txt`
- filesystem skin layers:
  - `imiimenik_podoba_custom_images`
  - `imiimenik_podoba_custom_templates`
  - `imiimenik_podoba_styles`
- `main_template.pt`, `livesearch_reply.py`, `imiimenik.js`, `imiimenik.css`
- bundled jQuery 1.5.1 and old plugins (`jquery.hotkeys`, `jquery.prettyPhoto`, `jquery.tinysort`)
- numerous legacy image assets

`setuphandlers.py` is only the standard generated flag hook; it contains no migration logic.

## 1.3 `imiimenik.produkti`

The package source list contains:

- `content/produkti.py`
- `content/uvoz.py`
- interfaces for both types
- browser/portlet package scaffolding
- GenericSetup `factorytool.xml`, `types.xml`, `types/produkti.xml`, `types/uvoz.xml`, `rolemap.xml`, metadata and portlets
- generated doctest/test scaffolding

### `produkti`

`produkti.py` is a folder-independent AT content type based on `ATCTContent`. It defines 21 custom `StringField`s:

`predime`, `ime`, `priimek`, `zaime`, `oddelek`, `telefon`, `vuporabi`, `maticna`, `opis`, `enota`, `lokacija`, `dodatna`, `dect`, `fax`, `mobilna`, `multitone`, `zunanja`, `enaslov`, `zenaslov`, `star`, plus inherited title/description.

Most fields are searchable and use `AnnotationStorage`. `maticna` and `star` are explicitly not searchable. The type is registered as portal type `produkti` and is factory-managed.

The implementation strongly suggests a directory/person/job-record use case, and `uvoz.py` confirms this: it parses an imported semicolon-separated data file and creates/updates `produkti` objects under generated department folders.

### `uvoz`

`uvoz.py` is an AT folderish type with two `FileField`s, `datoteka` and `datoteka2`. Its post-create/post-edit hooks call `unpackArchive()`.

The import code:

- reads two uploaded files;
- parses the second file to build a department hierarchy;
- creates normal Plone `Folder` objects under `portal/data2`;
- parses a 21-column-ish semicolon-separated export;
- derives a new object id from name/surname/external ID;
- updates an existing published `produkti` record if found, otherwise creates one;
- deletes the uploaded import file afterwards.

This is not merely a form/upload type. It is a data import tool and therefore its semantics must be retained in the migration design even if `uvoz` itself is ultimately removed from the production content model.

## 1.4 `dezurstva.podoba`

The package contains:

- browser configuration/interface scaffolding and an old folder-contents template override;
- old GenericSetup CSS/JS registry files;
- `skins.xml` with a custom `portal_skins` selection;
- admin and custom-template skin layers;
- Python Scripts including `izberi_dezurstvo.py`, `kopiraj_dezurstvo.py`, `spremeni_dezurstvo_action.py`, `izvoz.py`;
- custom page templates including `dezurstva_admin.pt`, `dezurstva_brez_kontaktov.pt`, and `main_template.pt`;
- jQuery 1.5.1, jQuery UI and `jquery.uitablefilter`/`jquery.tinysort`.

`izberi_dezurstvo.py` creates a `dezurstvo` object and programmatically publishes it. This behavior is important and should become an explicit browser view/service in the target application, not an opaque filesystem Python Script.

## 1.5 `dezurstva.produkti`

The package contains:

- `content/dezurstvo.py`
- `content/seznam_zaposlenih.py`
- `profiles/default/types/*.xml`
- `factorytool.xml`, `rolemap.xml`, portlet configuration
- generated browser/portlet/test scaffolding

The package defines two distinct custom types.

### `seznam_zaposlenih`

Folderish AT type with two `FileField`s: `datoteka1` and `datoteka2`.

Its import hook reads Excel data through `xlrd`, creates `Folder` objects for employees, and updates descriptions with telephone/email information. It deletes both uploaded files after processing.

The implementation contains Python 2 byte/unicode operations (`decode`, `encode`) and Python 2 print statements.

### `dezurstvo`

Folderish AT type with a large schema of `LinesField`s and one Boolean field. The multi-valued fields are populated from a dynamic vocabulary at `dezurstva/seznam_zaposlenih` and use `InAndOutWidget`.

Custom fields include:

- `dezurni_zdravnik`
- `nadzorni_zdravnik`
- `specializant`
- `sarsifon`
- `dezurni_tehnik`
- `izobrazevanje`
- `bakterioloski_tehnik`
- `inoqula_tehnik`
- `sprejem_predpriprava_tehnik`
- `vpis`
- `intervencijska_skupina`
- `intervencijska_skupina_telefon` (`StringField`)
- `BOR`, `HIV`, `HUM`, `IT`, `PRZ`, `KLM`, `KOV`, `VINVZV`, `VINDIF`, `WHO`, `kiestra`
- `klukca` (`BooleanField`)

The type also contains vocabulary methods and an Excel export method. The export code uses an old `openpyxl.Workbook().add_sheet(...)` API and is therefore a separate compatibility risk.

## 1.6 `kiestra.podoba`

Skin/theme package with the same old Plone 4 structure: filesystem skin layers, browser configuration, GenericSetup skin/resource registration and Python Scripts. It contains custom Dežurstvo-related scripts (`izberi_dezurstvo.py`, `kopiraj_dezurstvo.py`) and legacy JavaScript/CSS assets.

## 1.7 `kiestra.produkti`

The source list contains one content type only: `content/dezurstvo.py` plus its interface and GenericSetup.

This `dezurstvo` is **not** the Dežurstva `dezurstvo` type.

Its schema is a folderish AT type containing eight `LinesField`s and eight accompanying `StringField`s used as notes, plus one `TextField`:

- `priprava_vzorcev`
- `priprava_vzorcev_text`
- `cepljenje_vzorcev`
- `cepljenje_vzorcev_text`
- `odcitavanje`
- `odcitavanje_text`
- `identifikacija`
- `identifikacija_text`
- `antibiogram`
- `antibiogram_text`
- `izolacija`
- `izolacija_text`
- `odpad`
- `odpad_text`
- `ciscenje`
- `ciscenje_text`
- `stalni_tekst`

The dynamic vocabulary again traverses `dezurstva/seznam_zaposlenih`, so this site-specific type has a runtime dependency on the Dežurstva employee tree.

## 1.8 `preiskave.podoba`

Large legacy skin package with custom templates, views, search/live-search code, CSS and JavaScript. The source includes custom views for investigations, samples, laboratory views, new/urgent/quick views, grouping views and several admin pages.

`imi.js` uses old jQuery plugins and old APIs including `.live()` and string-based `setTimeout()` patterns. The package also contains an old live-search implementation and tightly coupled DOM selectors.

## 1.9 `preiskave.produkti`

The source list contains:

- `content/imipreiskava.py`
- `content/imiuvozipreiskavo.py`
- interfaces and GenericSetup type definitions
- factory tool and rolemap
- generated browser/portlet/test scaffolding

### `imipreiskava`

Folderish AT type. Custom fields:

- `sifra` — StringField
- `podrocje` — LinesField
- `sklop` — TextField with RichWidget
- `sinonim` — TextField with RichWidget
- `laboratoriji` — StringField
- `metode` — TextField with RichWidget
- `opis` — TextField with RichWidget
- `opombe` — TextField with RichWidget
- `trajanje` — TextField with RichWidget
- `urnik` — TextField with RichWidget
- `link_sop` — StringField
- `nova_pre` — StringField
- `nujna_pre` — StringField
- `vzorci` — StringField rendered with LinesWidget
- `preiskava_vzorec_nujno` — LinesField
- `vzorci_lab_kratica` — StringField rendered with LinesWidget
- `vzorci_lab` — StringField rendered with LinesWidget
- `vzorci_lab_tel` — StringField rendered with LinesWidget
- `vzorci_odvzem` — StringField rendered with LinesWidget
- `vzorci_odvzem_video_sifra` — StringField rendered with LinesWidget
- `vzorci_kolicina` — StringField rendered with LinesWidget
- `embalaza_slika_sifra` — StringField rendered with LinesWidget
- `vzorci_transport` — StringField rendered with LinesWidget
- `vzorci_opomba` — StringField rendered with LinesWidget
- `vzorci_nivo1` through `vzorci_nivo6` — StringFields rendered with LinesWidget
- `datoteka` — FileField

The import code in `imiuvozipreiskavo.py` is particularly important: it reads two Excel files, aggregates rows by investigation code, derives sample data and updates/creates `imipreiskava` objects. It assigns Python lists to several fields that are declared as `StringField`s. Therefore the target schema for those fields **must be decided from real stored values**, not just from the field declaration or widget.

`imipreiskava.at_post_create_script()` creates a child `Folder_datoteke` folder when needed. That child type is a standard `Folder`-like runtime object, not a declared custom AT class in this repository; the real database must be checked for actual `Folder_datoteke` objects and their files.

### `imiuvozipreiskavo`

AT content type based on `ATCTContent` with two `FileField`s: `datoteka1` and `datoteka2`. Its post-create behavior imports investigations and samples into `imipreiskava` objects.

This is an operational import utility rather than ordinary editorial content and should be treated as such during redesign.

## 1.10 `nadomescanja.podoba`

Skin package with admin/custom-template layers, JavaScript, CSS, Python Scripts and custom page templates. It contains `izberi_dezurstvo.py`, `kopiraj_dezurstvo.py`, `izvoz.py`, and `nadomescanja.js`.

## 1.11 `nadomescanja.produkti`

This is the most modern-looking of the custom packages and already contains browser views in addition to AT content.

Types:

- `laboratorij`
- `dezurstvo`

`laboratorij` is a folderish AT type with:

- `okrajsava` — required StringField
- `privzeti_vodja` — LinesField with dynamic vocabulary

It has a custom add permission `nadomescanja.produkti: Add laboratorij` and publishes the object in `at_post_create_script()`.

`dezurstvo` is a folderish AT type with one TextField:

- `nadomescanja_json`, default `'[]'`, hidden on edit but visible on view.

It exposes `getNadomescanjaRows()` and `getNadomescanjaDict()`, and contains an Excel export implementation.

The package also has two browser views:

- `@@nadomescanja-data-json` — JSON endpoint for laboratories and employees
- `@@nadomescanja_view` — HTML view of the JSON rows

`nadomescanja_data.py` explicitly contains Python 2-only byte/unicode handling (`str(...).decode('utf-8')`, `unicode(...)`) and must be rewritten for Python 3.

---

# 2. Site-by-site content-type inventory

The inventory below is the **custom source-defined inventory**. It is deliberately not a claim about every type currently present in the real database.

| Site | Source package | Type | Base | Folderish | Notes |
|---|---|---|---|---|---|
| `portal` | `imiimenik.produkti` | `produkti` | `ATCTContent` | No | Person/job/directory record; 21 custom string fields |
| `portal` | `imiimenik.produkti` | `uvoz` | `ATFolder` | Yes | Two-file directory/data import utility |
| `dezurstva` | `dezurstva.produkti` | `seznam_zaposlenih` | `ATFolder` | Yes | Excel-driven employee folder importer |
| `dezurstva` | `dezurstva.produkti` | `dezurstvo` | `ATFolder` | Yes | Large multi-valued on-call schedule record |
| `kiestra` | `kiestra.produkti` | `dezurstvo` | `ATFolder` | Yes | Completely different schema from Dežurstva `dezurstvo` |
| `preiskave` | `preiskave.produkti` | `imipreiskava` | `ATFolder` | Yes | Investigation record; many rich/list-like fields + file |
| `preiskave` | `preiskave.produkti` | `imiuvozipreiskavo` | `ATCTContent` | No | Excel import utility for investigations/samples |
| `nadomescanja` | `nadomescanja.produkti` | `laboratorij` | `ATFolder` | Yes | Laboratory with abbreviation and default leader |
| `nadomescanja` | `nadomescanja.produkti` | `dezurstvo` | `ATFolder` | Yes | Replacement/on-call JSON record; different from both other `dezurstvo`s |

### Important non-equivalences

- `produkti` exists as an actual custom portal type only in `imiimenik.produkti` in the source inspected. The other `*.produkti` packages do not define a `produkti` content class.
- `dezurstvo` is defined independently in **three packages**. Their schemas and behavior are materially different and they must become separate Dexterity types, even if the visible portal type name is currently the same inside different sites.
- The three `dezurstvo` implementations also have different permissions, UI, exports and data formats.
- A future target should use distinct technical type names, for example `imi_dezurstvo`, `kiestra_dezurstvo`, and `nadomescanje_dezurstvo`, or equivalent package-qualified names. Do not create one shared Dexterity type named `dezurstvo` and try to make it conditional by site.

### Runtime database inventory required before implementation

Against a clone of the real 4.3 database, collect for each site:

- every `portal_type` and `meta_type` actually present;
- object counts per type;
- every custom field name and actual Python/storage type for representative objects;
- object paths and parent types;
- UID/reference catalogs and relation targets;
- local roles and sharing settings;
- workflow chain and state counts per type;
- revisions/versions;
- portlets and content rules;
- redirects/aliases;
- PloneFormGen objects and their child fields/actions;
- files/images stored inside import folders and investigation folders;
- current site properties and registry values;
- selected skin and theme configuration.

This runtime inventory is mandatory because several source declarations are inconsistent with how the code actually writes data.

---

# 3. Archetypes schema → proposed Dexterity schema mapping

The proposed mappings below are based on declared Archetypes fields and the application code. They are **not** a license to guess stored data. Any field whose declaration and runtime usage disagree must be sampled from the real database first.

## 3.1 Common inherited fields

All types inheriting `ATFolderSchema` or `ATContentTypeSchema` inherit the standard Plone/AT metadata and folder settings. In Dexterity these should normally be represented by the standard Plone metadata fields/behaviors rather than duplicated custom fields.

At minimum validate:

- title
- description
- effective/expiration dates if actually present/used
- creators/modification metadata
- subjects/categories
- language
- rights
- related items
- exclude-from-navigation
- next/previous navigation settings
- default-page/folder layout
- lock/version/comment metadata where applicable

Do not blindly copy the entire AT schema into every DX type. Use the appropriate standard Dexterity behaviors and core metadata, then add only application-specific fields.

## 3.2 `portal/produkti`

Proposed target type: `imi_oseba` or `produkti` within an explicitly IMI-specific namespace.

| AT field | AT type | Proposed DX type | Notes |
|---|---|---|---|
| `predime` | String | TextLine | Preserve exact value |
| `ime` | String | TextLine | Used by import/id generation |
| `priimek` | String | TextLine | Used by import/id generation |
| `zaime` | String | TextLine | |
| `oddelek` | String | TextLine | |
| `telefon` | String | TextLine | |
| `vuporabi` | String | TextLine | Preserve source semantics; do not infer Boolean |
| `maticna` | String | TextLine | Non-searchable in source |
| `opis` | String | TextLine | Despite label, source is StringField |
| `enota` | String | TextLine | |
| `lokacija` | String | TextLine | |
| `dodatna` | String | TextLine | |
| `dect` | String | TextLine | |
| `fax` | String | TextLine | |
| `multitone` | String | TextLine | |
| `mobilna` | String | TextLine | |
| `zunanja` | String | TextLine | |
| `enaslov` | String | TextLine | |
| `zenaslov` | String | TextLine | |
| `star` | String | TextLine | Non-searchable in source |

`title` and `description` should remain standard metadata fields. Do not convert `vuporabi` or `star` to Boolean/date merely because their labels suggest it; the source schema says StringField.

## 3.3 `portal/uvoz`

Proposed target: preferably a temporary/admin-only Dexterity utility type or a browser view/action instead of permanent editorial content.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `datoteka` | NamedBlobFile | Import source file |
| `datoteka2` | NamedBlobFile | Department structure file |

The more important migration is the **behavior** of `unpackArchive()`. It should become a tested service/browser view/command with explicit validation, transaction boundaries and reporting. It should not remain an automatic post-save hook that mutates large parts of the site.

## 3.4 `dezurstva/seznam_zaposlenih`

Proposed target: `seznam_zaposlenih` or a clearer technical name such as `employee_import` if the object is retained.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `datoteka1` | NamedBlobFile | XLS import |
| `datoteka2` | NamedBlobFile | telephone/email update |

The child employee records created by this code are ordinary Plone `Folder` objects. They are not custom `seznam_zaposlenih` objects. The real DB must be checked to see whether the folder structure is the actual public data model.

## 3.5 `dezurstva/dezurstvo`

Proposed target: `dezurstva_dezurstvo`.

All `LinesField`s should initially map to `List`/`Tuple` of `TextLine` (or a vocabulary-backed collection where the source vocabulary is preserved). The exact choice between List and Tuple should follow existing API consumers; the source uses both iteration and assignment.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `dezurni_zdravnik` | List of TextLine / vocabulary | Dynamic employee vocabulary |
| `nadzorni_zdravnik` | List of TextLine / vocabulary | Dynamic employee vocabulary |
| `specializant` | List of TextLine / vocabulary | |
| `sarsifon` | List of TextLine / vocabulary | |
| `dezurni_tehnik` | List of TextLine / vocabulary | Hidden in source UI |
| `izobrazevanje` | List of TextLine / vocabulary | Hidden in source UI |
| `bakterioloski_tehnik` | List of TextLine / vocabulary | |
| `inoqula_tehnik` | List of TextLine / vocabulary | |
| `sprejem_predpriprava_tehnik` | List of TextLine / vocabulary | |
| `vpis` | List of TextLine / vocabulary | |
| `intervencijska_skupina` | List of TextLine / vocabulary | |
| `intervencijska_skupina_telefon` | TextLine | |
| `BOR` | List of TextLine / vocabulary | |
| `HIV` | List of TextLine / vocabulary | |
| `HUM` | List of TextLine / vocabulary | |
| `IT` | List of TextLine / vocabulary | |
| `PRZ` | List of TextLine / vocabulary | |
| `KLM` | List of TextLine / vocabulary | |
| `KOV` | List of TextLine / vocabulary | |
| `VINVZV` | List of TextLine / vocabulary | Hidden in source UI |
| `VINDIF` | List of TextLine / vocabulary | Hidden in source UI |
| `WHO` | List of TextLine / vocabulary | |
| `kiestra` | List of TextLine / vocabulary | |
| `klukca` | Bool | Checkbox behavior |

The source vocabulary is not a static vocabulary: it traverses `dezurstva/seznam_zaposlenih`. The DX implementation should use a named vocabulary/source or a helper that returns employee choices. Do not hard-code the values into the schema.

## 3.6 `kiestra/dezurstvo`

Proposed target: `kiestra_dezurstvo`.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `priprava_vzorcev` | List of TextLine / vocabulary | |
| `priprava_vzorcev_text` | TextLine | |
| `cepljenje_vzorcev` | List of TextLine / vocabulary | |
| `cepljenje_vzorcev_text` | TextLine | |
| `odcitavanje` | List of TextLine / vocabulary | |
| `odcitavanje_text` | TextLine | |
| `identifikacija` | List of TextLine / vocabulary | |
| `identifikacija_text` | TextLine | |
| `antibiogram` | List of TextLine / vocabulary | |
| `antibiogram_text` | TextLine | |
| `izolacija` | List of TextLine / vocabulary | |
| `izolacija_text` | TextLine | |
| `odpad` | List of TextLine / vocabulary | |
| `odpad_text` | TextLine | |
| `ciscenje` | List of TextLine / vocabulary | |
| `ciscenje_text` | TextLine | |
| `stalni_tekst` | Text | Plain multiline text in source |

The vocabulary currently reads from `dezurstva/seznam_zaposlenih`, which is an explicit cross-site/application dependency. The migration must either retain that dependency or replace it with a shared employee service.

## 3.7 `preiskave/imipreiskava`

Proposed target: `imipreiskava` as a folderish Dexterity type.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `sifra` | TextLine | Investigation code |
| `podrocje` | List of TextLine | Declared LinesField |
| `sklop` | RichText | RichWidget |
| `sinonim` | RichText | RichWidget |
| `laboratoriji` | TextLine initially | Declared StringField; verify DB |
| `metode` | RichText | RichWidget |
| `opis` | RichText | RichWidget |
| `opombe` | RichText | RichWidget |
| `trajanje` | RichText | RichWidget |
| `urnik` | RichText | RichWidget |
| `link_sop` | TextLine | |
| `nova_pre` | TextLine | Preserve string semantics |
| `nujna_pre` | TextLine | Preserve string semantics |
| `vzorci` | **TBD after DB sample** | Declared StringField but assigned lists by importer |
| `preiskava_vzorec_nujno` | List of TextLine | |
| `vzorci_lab_kratica` | **TBD after DB sample** | StringField + LinesWidget; importer assigns lists |
| `vzorci_lab` | **TBD after DB sample** | Same inconsistency |
| `vzorci_lab_tel` | **TBD after DB sample** | Same inconsistency |
| `vzorci_odvzem` | **TBD after DB sample** | Same inconsistency |
| `vzorci_odvzem_video_sifra` | **TBD after DB sample** | Same inconsistency |
| `vzorci_kolicina` | **TBD after DB sample** | Same inconsistency |
| `embalaza_slika_sifra` | **TBD after DB sample** | Same inconsistency |
| `vzorci_transport` | **TBD after DB sample** | Same inconsistency |
| `vzorci_opomba` | **TBD after DB sample** | Same inconsistency |
| `vzorci_nivo1` … `vzorci_nivo6` | **TBD after DB sample** | Same inconsistency |
| `datoteka` | NamedBlobFile | Additional investigation description/file |

The list-like StringFields are the most important schema ambiguity in the repository. The import code constructs lists and assigns them to these fields, while the schema declares them as strings. The migration must inspect actual stored values and preserve them exactly before choosing the DX field cardinality.

`datoteka` should be a `NamedBlobFile`, with filename and content type preserved. The `Folder_datoteke` child folder created by `narediMape()` should be explicitly inventoried and migrated as ordinary folder/file content.

## 3.8 `preiskave/imiuvozipreiskavo`

Proposed target: temporary/admin import utility, or remove as editorial content after replacing the import operation.

| AT field | Proposed DX type |
|---|---|
| `datoteka1` | NamedBlobFile |
| `datoteka2` | NamedBlobFile |

The important migration asset is the importer logic, not the utility object itself.

## 3.9 `nadomescanja/laboratorij`

Proposed target: `nadomescanja_laboratorij`.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `okrajsava` | TextLine | Required |
| `privzeti_vodja` | List of TextLine / vocabulary | Verify actual cardinality; source is LinesField |

The custom add permission `nadomescanja.produkti: Add laboratorij` must be preserved as an explicit target permission or replaced with a role/permission design that has equivalent security semantics.

## 3.10 `nadomescanja/dezurstvo`

Proposed target: `nadomescanja_dezurstvo`.

| AT field | Proposed DX type | Notes |
|---|---|---|
| `nadomescanja_json` | Text | JSON string is the source contract |

A later application-level refactor could normalize this JSON into structured relational/reference fields, but that is **not** a migration requirement. For the first safe migration, preserve the exact JSON payload and build a tested adapter/service around it.

The type is folderish and the object id encodes the date in existing code. Preserve that path/id contract unless the real DB audit proves it can be changed safely.

---

# 4. Shared versus site-specific content types

## Shared infrastructure

The following behavior is shared across multiple sites:

- employee lookup under `dezurstva/seznam_zaposlenih`;
- dynamic vocabulary methods based on that employee tree;
- date/id-driven `dezurstvo` records;
- Excel export/import patterns;
- legacy `portal_skins` and Python Scripts;
- old jQuery/UI resources.

These should not automatically become shared content types. Shared **services** are preferable to shared schemas when the underlying data models differ.

## Site-specific types

All custom types should initially remain site-specific in the target package structure:

- `portal`: IMI directory data and import tool
- `dezurstva`: employee data and medical/on-call schedule
- `kiestra`: laboratory workflow schedule
- `preiskave`: investigations and import tool
- `nadomescanja`: laboratories and replacement schedule

If later analysis finds a genuinely shared domain object, introduce a common package only after the migrated schemas and runtime usage have been compared. Do not unify types during the first migration.

---

# 5. Add-on replacement/migration matrix

| Source dependency | Evidence | Target decision |
|---|---|---|
| `Products.PloneFormGen 1.7.17` | Explicit buildout egg; no source-defined forms | **Migrate to `collective.easyform` 3.x for Plone 5.2**, but inventory DB forms first. Recreate forms/actions and migrate any stored submissions that must be retained. |
| `Products.TinyMCE` | Explicit buildout egg | **Remove.** Plone 5.2 provides TinyMCE through Mockup. Re-test custom editor configuration and rich-text output. |
| `collective.editskinswitcher 2.3` | Explicit buildout egg/version pin | **Remove/replace.** Documented compatibility is Plone 4.1–4.3. Reimplement switching with Plone 5 skin/theme mechanisms, most likely Diazo/request logic. |
| `z3c.jbot 0.7.2` | Explicit buildout egg | Retain only where a concrete template override is still required. Audit every jbot override; do not carry it forward blindly. |
| `xlrd 0.8.0` | Explicit pin and used by import code | Replace the Python-2-era pin. If inputs are `.xls`, a supported `xlrd` 2.x can read them; if `.xlsx` is required, use `openpyxl` for reading. Verify real import files. |
| `openpyxl 2.6.4` | Explicit pin and used by export code | Upgrade to a Python 3-compatible version that is compatible with the selected Plone stack, and rewrite the old `add_sheet()` usage to `create_sheet()`/worksheet APIs. |
| `wicked 1.1.12` | Version pin only; not explicitly listed in `eggs` | Determine why it is resolved in the current buildout. If only a transitive/unused pin, remove it. Do not preserve a pin without evidence. |
| `Pillow` | Explicit | Keep a Plone-compatible pinned version supplied by the 5.2 release stack. |
| old vendored Paste eggs | Present inside package directories | Do not install/copy. Use the supported Plone/Zope dependency set. |
| `Products.ATContentTypes` / Archetypes | Used by all custom types | Temporary compatibility only on Plone 5.2/Python 2. **Final target must be Dexterity.** |
| old `portal_css`/`portal_javascript` registries | `cssregistry.xml` and `jsregistry.xml` in skins | Replace with Resource Registry records/bundles or package/theme resources. |

### PloneFormGen → EasyForm assessment

The source code does not define any PFG form in `src/`; the buildout only installs the package. This strongly indicates that form instances, if present, live in the real ZODB.

Before implementation:

1. Enumerate every `FormFolder`, `FormSaveDataAdapter`, `FormMailerAdapter`, field, action adapter and related PFG object in all five sites.
2. Export a machine-readable inventory of each form's fields, validators, defaults, actions, mail recipients, save-to-database behavior and custom scripts.
3. Identify forms whose submissions are legally/operationally required to be retained.
4. Map each form to EasyForm fields/actions.
5. Migrate submission data separately from the form definition if retention is required.
6. Test email, validation, file uploads, saved-data behavior and permissions.

Do not delete PFG from the database until the form inventory and retention decision have been signed off.

---

# 6. Python 2 → Python 3 issues

The source is strongly Python 2-specific.

## Direct syntax/API issues observed

- `from StringIO import StringIO` appears in multiple packages. Replace with `io.BytesIO` for binary uploads or `io.StringIO` for text.
- `import cStringIO` is Python 2-only.
- `print value` statements occur in application code.
- `unicode(...)` is used in `nadomescanja_data.py`.
- `.decode('utf-8')` is called on values that may already be Python 3 `str`.
- `.encode('utf-8')`/`.decode('utf-8')` are used inconsistently in Excel import code.
- `dict.keys()` is treated as a list in places where Python 3 returns a view.
- `filter`, `map`, and related iterator semantics need review wherever used in source/scripts.
- old exception syntax and Python 2-only idioms should be found by running a Python 3 parser/precompiler after the Plone 5.2 port.

## Zope/Plone Python API issues

The code uses old imports and APIs such as:

- `from zope.interface import implements` → use `@implementer`.
- `Products.Five.BrowserView` remains usable, but browser views should use modern component APIs and explicit interfaces where appropriate.
- `getToolByName` is still available in Plone 5.2, but new code should prefer `plone.api` or component utilities where practical.
- `portal_workflow.doActionFor` remains a valid legacy operation, but workflow actions should be centralized and checked for failures rather than hidden in filesystem scripts.
- `atapi.ATFieldProperty` disappears with the final AT-to-DX migration.
- `BrowserDefaultMixin` and `CMFDynamicViewFTI` are part of the old AT dynamic-view architecture and should not be copied into DX types unnecessarily.

## Excel/API issues

`dezurstva.produkti` and `nadomescanja.produkti` use old `openpyxl` APIs. The source constructs a workbook and calls `add_sheet()`, whereas current openpyxl uses `create_sheet()`.

The buildout pins `openpyxl 2.6.4`, an old version selected for the Python 2 environment. The target must select versions compatible with the final Python runtime and rewrite the code accordingly.

The import code uses `xlrd`. Modern xlrd supports `.xls` but intentionally does not support `.xlsx`. Real import files must be inspected before choosing the replacement API.

## Recommended Python migration method

Do not attempt the Python 2→3 database conversion at the same time as the first Plone 4.3→5.2 database upgrade.

Use the documented sequence:

1. Port enough add-ons/code to run Plone 5.2 under Python 2.7.
2. Upgrade the database to Plone 5.2 under Python 2.7.
3. Remove/migrate all remaining Archetypes content to Dexterity.
4. Port the final application/add-ons to Python 3.
5. Pack the database to zero days, verify it with `zodbverify`, stop the instance, run `zodbupdate`, verify again, and only then start Plone under Python 3.

The final Python 3 target for the Plone 5.2 line is Python 3.8. This is itself end-of-life today, so the deployment must be treated as a legacy containment platform with a planned Plone 6 upgrade rather than as a long-term modern stack.

---

# 7. Plone 4.3 → 5.2 API and architecture issues

## 7.1 Archetypes

Archetypes is deprecated in Plone 5.2 and only usable there with Python 2.7. It cannot be part of the Python 3 final state.

The target should therefore:

- introduce Dexterity schemas;
- retain AT packages/classes temporarily during migration so old objects can still be loaded;
- migrate content objects;
- only remove AT dependencies after all AT objects and references have been migrated and validated.

## 7.2 Resource Registry

Plone 5.2 removed old-style `portal_css` and `portal_javascript` registries. The source contains `cssregistry.xml` and `jsregistry.xml` in the skin packages. Even where these files are mostly empty/generated, they are part of an obsolete GenericSetup model.

Target implementation should use `registry.xml` with `IResourceRegistry`/`IBundleRegistry`, or package/theme resources included in the appropriate Plone 5 bundle.

## 7.3 Static resources and skin layers

The source uses `portal_skins` filesystem layers and custom `main_template.pt` files. Plone 5 supports skin layers, but the preferred architecture is a Plone 5 theme/resource arrangement, usually Diazo for site-wide presentation plus browser views/templates for application-specific screens.

Do not attempt to mechanically copy the old `main_template.pt` into the target. Each template needs to be checked against Plone 5 macros, viewlets, resource bundles and DOM structure.

## 7.4 Navigation

Plone 5.2 has a new navigation implementation. Any custom navigation markup or overrides should be tested against the Plone 5 navigation provider. The old skin templates should not assume the Plone 4 navigation HTML.

## 7.5 Login and core browser views

Plone 5 moved login behavior from old skin-based implementation to browser views. Any custom template or JavaScript override touching login/logout must be explicitly checked. The source inventory does not show a dedicated login override, but the old global templates should still be searched for references to login macros/IDs during implementation.

## 7.6 Workflow

The repository contains no custom workflow definition XML. It does contain code that programmatically publishes content using `portal_workflow.doActionFor(..., 'publish')`.

Therefore the **workflow definition itself is likely in the database**, not the repository. The real database audit must capture workflow chains and states before any migration.

The migration must preserve at least:

- workflow chain assigned to each type/folder;
- current state of each object;
- local workflow assignments;
- transition permissions;
- any local roles associated with workflow states.

## 7.7 Permissions

The source defines custom add permissions in GenericSetup role maps:

- `imiimenik.produkti: Add uvoz`
- `imiimenik.produkti: Add produkti`
- `dezurstva.produkti: Add seznam_zaposlenih`
- `dezurstva.produkti: Add dezurstvo`
- `kiestra.produkti: Add dezurstvo`
- `preiskave.produkti: Add imiuvozipreiskavo`
- `preiskave.produkti: Add imipreiskava`
- `nadomescanja.produkti: Add dezurstvo`
- `nadomescanja.produkti: Add laboratorij`

The role assignments differ by package. For example, Dežurstva grants its add permissions to Manager and Contributor, while Nadomeščanja's custom permissions include Site Administrator as well.

These permissions must be migrated deliberately. Dexterity FTIs should not simply expose every type to every role.

## 7.8 Factory tool

The source uses `portal_factory` for several AT types. This is part of the old AT add form model. Dexterity uses normal add forms and object creation. Factory-tool registrations should therefore not be copied into the final application.

## 7.9 Rich text/TinyMCE

The source explicitly installs `Products.TinyMCE`. Plone 5.2 uses the Mockup TinyMCE integration. RichText fields should become `plone.app.textfield`/Dexterity RichText fields, and the actual HTML MIME type/content must be preserved.

---

# 8. Template/browser/JavaScript migration issues

## 8.1 Strong AT widget coupling

`dezurstva_podoba_admin/dezurstvo.js` targets `.ArchetypesInAndOutWidget` and manipulates the generated three-column selection table directly. This will not survive an AT→DX migration because Dexterity uses z3c.form widgets.

The filtering and keyboard navigation should be rewritten against stable application-specific markup, ideally as a Plone 5 pattern/module rather than by manipulating generated widget internals.

## 8.2 Old jQuery

The repository bundles jQuery 1.5.1 in several skin layers. It also uses old plugins such as:

- jQuery UI
- `jquery.tinysort`
- `jquery.uitablefilter`
- `jquery.prettyPhoto`
- `carouFredSel`
- `jshowoff`

Several source files use `.live()`, which is removed from modern jQuery. The target should not ship the old jQuery stack merely to make the old code work. Reimplement application interactions using Plone 5 patterns/RequireJS or a small supported module.

## 8.3 Search/live-search

The source includes a legacy `livesearch.js` and a `livesearch_reply.py` skin script. The search JavaScript relies on old IDs (`#searchGadget`) and old jQuery event APIs. Plone 5's search markup and resource system differ.

Recommendation: first determine whether Plone 5's built-in search/live-search behavior is sufficient; if not, port the custom behavior as a browser view + RequireJS module rather than carrying the old script forward.

## 8.4 Old skin templates

The `preiskave_view.pt` template is particularly coupled to Archetypes. It calls:

- `context.Schema().viewableFields(...)`
- `context.getUniqueWidgetAttr(...)`
- `context.getPortalTypeName()`
- dynamic lookup of `<portal_type>_view` macros
- `archetypes_custom_js`
- old skin `base` macros

This is an AT-specific view architecture. The target should replace it with explicit browser views/templates for each application screen.

## 8.5 Python Scripts in skins

Filesystem Python Scripts such as `izberi_dezurstvo.py`, `kopiraj_dezurstvo.py`, `izvoz.py`, and `spremeni_dezurstvo_action.py` should be converted to real browser views/services with:

- explicit permissions;
- input validation;
- proper Unicode handling;
- transaction boundaries;
- test coverage;
- CSRF protection where appropriate;
- predictable redirects/HTTP responses.

Do not copy Python Scripts verbatim into the target.

## 8.6 Browser views already present

`nadomescanja.produkti` already has modern-style `BrowserView` classes. These are a good starting pattern, but they still contain Python 2 string handling and should be modernized.

The JSON endpoint should return real JSON with `Content-Type: application/json` and should use Python 3 `str` values throughout. It should also be reviewed for caching, permission, traversal and error-handling behavior.

---

# 9. Data migration strategy

## 9.1 Principle: never migrate the production database first

All work must be performed against a byte-for-byte copy of the production 4.3 database and blob/file storage.

Maintain at least:

- immutable original 4.3 backup;
- pristine 4.3 clone for repeated rehearsals;
- working 5.2/Python 2 clone;
- migrated 5.2/Dexterity clone;
- final Python 3/ZODB-converted clone.

Never use the only production copy as the migration test environment.

## 9.2 Phase A — database reconnaissance

Before modifying the data model, run a read-only inventory script under the original 4.3 environment.

For every site and every object, record at minimum:

- path
- UID
- portal_type/meta_type
- title/id
- creation/modification dates
- workflow chain/state
- local roles
- field names and Python/storage types
- file names/content types/sizes
- references/relations
- children and parent type
- version/revision information where available

For the problematic fields in `imipreiskava`, record `repr(type(value))` and a sanitized sample of the value for representative objects.

For `nadomescanja_json`, validate every value as JSON and record rows that fail validation.

For PFG, export a complete form inventory and identify stored submissions.

## 9.3 Phase B — Plone 4.3 → Plone 5.2 on Python 2

Build a clean Plone 5.2.15 environment with the minimum necessary compatibility add-ons.

Initially keep the custom AT classes and the old package APIs needed to load the database. Do **not** install the old Plone 4.3 add-on versions blindly. Select Plone 5.2-compatible releases or local compatibility branches.

Run the normal Plone upgrade steps on the clone, including `/@@plone-upgrade`, and resolve all upgrade errors before changing custom content types.

This phase establishes that the ZODB can be opened and the five sites can be traversed on Plone 5.2.

## 9.4 Phase C — custom AT → DX

Create the target Dexterity types first. Keep the original AT classes installed during the migration.

For simple field mappings, reuse `plone.app.contenttypes.migration.migration.migrateCustomAT` where suitable. It provides field migrators for common simple, rich-text, file and date values.

For fields with non-standard data shapes, write explicit custom migrators.

Recommended approach by type:

1. `portal/produkti` → migrate to a new IMI-specific DX type while retaining ids/paths.
2. `portal/uvoz` → migrate only if import history is required; otherwise preserve the data as an archive and replace the operation with a new importer.
3. `dezurstva/seznam_zaposlenih` → migrate the folder container if retained; separately preserve the employee folders it created.
4. `dezurstva/dezurstvo` → migrate all list fields and preserve object ids/dates.
5. `kiestra/dezurstvo` → migrate independently using its own schema and UI.
6. `preiskave/imipreiskava` → migrate rich text/files and explicitly transform the list-like StringFields based on real data samples.
7. `preiskave/imiuvozipreiskavo` → archive/remove as an import utility after ensuring the importer exists in the new system.
8. `nadomescanja/laboratorij` → migrate with custom permission preservation.
9. `nadomescanja/dezurstvo` → preserve `nadomescanja_json` byte-for-byte where valid, then build a compatibility view over it.

## 9.5 UID/path strategy

Do not assume the generic AT→DX migration preserves every identity requirement automatically.

For each type, explicitly test:

- object id unchanged;
- path unchanged;
- UID preserved where possible;
- inbound links still resolve;
- references/relations still resolve;
- parent/child hierarchy unchanged;
- local roles unchanged;
- workflow state unchanged.

If a custom migration must create a new DX object, use a deterministic mapping from old object to new object and record old UID → new UID/path in a migration log.

## 9.6 Files and blobs

`FileField` values must become `NamedBlobFile` or the appropriate Dexterity file field. Validate:

- filename
- MIME type
- size
- content checksum
- download response
- file inside any child folders such as `Folder_datoteke`

Do not use filename alone as the identity check. Compare hashes for migrated binary data.

## 9.7 Workflow and permissions

Before migration, export the workflow chain/state matrix.

After migration, compare the matrix object-by-object. Publishing hooks in the old code should not be allowed to silently change existing workflow states during migration. Migration scripts should set fields and then explicitly restore/verify workflow state rather than invoking normal create-time publish behavior unless required.

## 9.8 Revisions

The standard AT→DX migration can lose historical revisions. If historical revisions are a requirement, they need a separate migration/retention strategy. Do not claim that a successful current-object migration preserves revision history.

## 9.9 Alternative: export/import

If in-place AT→DX migration becomes unreliable because of legacy class references or mixed content, evaluate `collective.exportimport` as a controlled alternative. It supports content export/import across Plone versions and has migration support for AT→DX-related data.

This should be treated as a fallback/controlled migration channel, not introduced prematurely, because a five-site Data.fs with cross-site paths and references may be harder to reconstruct from independent exports.

---

# 10. Docker/buildout/installation strategy

## Current source installation

The source Dockerfile is:

- `python:2.7-slim`
- Plone 4.3.20
- Debian Buster archive repositories
- `zc.buildout==2.13.8`
- `setuptools==44.1.1`
- standalone `plone.recipe.zope2instance`
- source packages copied into `/plone/instance/src`
- `var/filestorage/Data.fs` and blob storage mounted from the host

The compose file mounts `./var/filestorage`, `./var/blobstorage` and `./src`.

## Target recommendation

Use a two-image migration strategy rather than one image that tries to run every stage.

### Image 1: Plone 5.2/Python 2 compatibility image

Purpose: perform the supported 4.3→5.2 upgrade and AT→DX migration.

Characteristics:

- Plone 5.2.15
- Python 2.7 only as a temporary migration environment
- buildout pinned to the official 5.2.15 versions
- only add-ons required to open and migrate the database
- no vendored Paste eggs
- explicit migration utilities and backup tooling

This image should be disposable and never be the final production image.

### Image 2: Plone 5.2/Python 3 image

Purpose: final Plone 5.2 application runtime after all AT content is gone.

Characteristics:

- Plone 5.2.15
- Python 3.8, because this is the supported Python 3 runtime for 5.2.15
- only Python 3-compatible application packages/add-ons
- no `Products.Archetypes`
- no `Products.PloneFormGen`
- no `Products.TinyMCE`
- no old resource registries
- no Python 2 vendored eggs
- deterministic build using the official 5.2.15 versions/constraints

Because Plone 5.2.15 is unsupported today and Python 3.8 is EOL, this image should be considered a compatibility/legacy target. A follow-on Plone 6 migration should be planned.

## Buildout design

Start from the official Plone 5.2.15 `versions.cfg`/constraints rather than modifying the old 4.3 pins one-by-one.

Use explicit local package development entries for the target packages.

Do not carry these source pins into the target without verification:

- `Products.PloneFormGen = 1.7.17`
- `collective.editskinswitcher = 2.3`
- `z3c.jbot = 0.7.2`
- `xlrd = 0.8.0`
- `openpyxl = 2.6.4`
- `wicked = 1.1.12`

## Docker storage

Keep ZODB file storage and blob storage outside the container image. Use separate volumes/bind mounts and make backups part of the deployment process.

Do not mount the development source tree over the installed application package in production. The old compose pattern is useful for development but should be replaced with an immutable application image for deployment.

## Startup

The source runs `bin/instance console`. The target should use a proper foreground process mode suitable for the container and production deployment, with logging to stdout/stderr and persistent ZODB/blob volumes.

---

# 11. Recommended migration order

## Stage 0 — freeze and evidence

1. Freeze application changes in the 4.3 installation.
2. Create and verify a full backup of `Data.fs` and blob/file storage.
3. Create a disposable clone.
4. Run the read-only database inventory described above.
5. Export site-level GenericSetup/runtime configuration where possible.
6. Inventory PFG forms and submissions.
7. Inventory workflow chains/states and local roles.

## Stage 1 — target build skeleton

8. Create the Plone 5.2.15 buildout/Docker skeleton in `new-plone5`.
9. Add only the minimum compatibility add-ons required to open the migrated database.
10. Do not rewrite application behavior yet.
11. Build a clean empty Plone 5.2 site and verify the base installation.

## Stage 2 — Plone upgrade compatibility

12. Port the custom packages just enough to import on Plone 5.2/Python 2.
13. Remove/replace dependencies that cannot load under Plone 5.2.
14. Upgrade a copy of the real database to Plone 5.2/Python 2.
15. Run all Plone upgrade steps.
16. Verify all five sites open and catalog correctly.

## Stage 3 — content model migration

17. Implement all nine custom target types as separate DX types according to the site-specific mappings.
18. Add temporary compatibility views/behaviors where needed.
19. Implement and test custom AT→DX migrators.
20. Migrate `produkti`.
21. Migrate Dežurstva employee data and `dezurstvo`.
22. Migrate Kiestra `dezurstvo` independently.
23. Migrate Preiskave investigations and files.
24. Migrate Nadomeščanja laboratories and JSON schedule.
25. Compare counts, ids, UIDs, fields, files, workflow and permissions.

## Stage 4 — form and UI migration

26. Recreate required PFG forms as EasyForms.
27. Migrate required submission history.
28. Replace old skin templates with Plone 5 browser views/theme resources.
29. Replace Python Scripts with browser views/services.
30. Replace old JavaScript and jQuery dependencies.
31. Replace old CSS/JS registries with Resource Registry/bundles.
32. Replace/remove `collective.editskinswitcher`.

## Stage 5 — remove Archetypes

33. Prove zero live custom AT objects remain.
34. Prove no custom code imports Archetypes.
35. Prove no PFG/legacy package dependency still requires AT.
36. Remove AT dependencies from the target Python 3 build.

## Stage 6 — Python 3

37. Port all remaining application code to Python 3.
38. Run syntax/precompiler checks.
39. Run unit/integration tests.
40. Create a fresh Python 3-compatible Plone 5.2 environment.
41. Verify the Python 2 database with `zodbverify`.
42. Pack to zero days as required by `zodbupdate` procedure.
43. Stop Plone completely.
44. Run `zodbupdate` offline.
45. Run `zodbverify` again.
46. Start the Python 3 instance.
47. Run full functional tests.

## Stage 7 — cutover

48. Repeat the migration from a fresh production backup.
49. Perform a final delta/data reconciliation.
50. Put the old system into read-only/maintenance mode.
51. Run final migration.
52. Verify all five sites.
53. Switch traffic.
54. Keep the original 4.3 backup untouched.

---

# 12. Risks and things that must be tested against the real 4.3 database

## Critical risks

### R1 — hidden database-only content

The repository cannot show PFG forms, runtime portal types, workflow assignments, local roles, redirects, relations, portlets, or registry values stored only in ZODB.

**Test:** full database inventory before any migration.

### R2 — duplicate technical type names

Three different `dezurstvo` classes exist. A generic portal-type-name migration is unsafe.

**Test:** migrate by site/package-specific source class, not by the string `dezurstvo` alone.

### R3 — schema/runtime mismatch in `imipreiskava`

Several fields are declared as `StringField` but the importer assigns lists to them.

**Test:** inspect stored values on representative and worst-case objects before designing the DX schema.

### R4 — workflow changes caused by create hooks

Some AT classes publish newly created objects in post-create scripts.

**Test:** migration scripts must not accidentally publish or transition existing objects.

### R5 — old Python Scripts

Scripts run in the skin context and rely on implicit globals such as `context`, `container`, `REQUEST`, `printed` and old traversal behavior.

**Test:** every script needs a behavior-level acceptance test before replacement.

### R6 — binary data

Excel imports, investigation files and other `FileField` data can be lost or altered during AT→DX conversion.

**Test:** compare file count, size, MIME type, filename and SHA-256 hashes.

### R7 — old JavaScript

UI scripts rely on AT-generated markup and old jQuery APIs.

**Test:** every add/edit/view screen in all five sites, especially keyboard-heavy Dežurstvo screens.

### R8 — cross-site dependencies

Kiestra and Nadomeščanja code traverses `dezurstva/seznam_zaposlenih`.

**Test:** run cross-site lookup tests after migration; do not assume each site is isolated.

### R9 — workflow/permission drift

GenericSetup role maps differ between packages, and runtime state may be more complex than the source XML.

**Test:** build a before/after permission matrix and workflow-state count comparison.

### R10 — revisions

Generic AT→DX migration may not preserve revision history.

**Test:** determine whether revision history is a hard requirement. If yes, implement a separate history strategy before cutover.

### R11 — Plone 5.2 end-of-life

Plone 5.2.15 is the final 5.2 release and the series is unsupported. Python 3.8 is also EOL.

**Test/decision:** obtain explicit approval that Plone 5.2 is a required intermediate/final target. Prefer planning the architecture so the next move to Plone 6 is straightforward.

### R12 — ZODB Python 2→3 conversion

A Python 2-created ZODB cannot simply be opened by Python 3. The conversion must be performed offline with `zodbupdate` after the code is Python 3-ready.

**Test:** `zodbverify` before and after conversion, followed by full application tests.

---

# 13. Acceptance test matrix for migration rehearsals

Every rehearsal should produce a machine-readable before/after report with at least:

| Area | Acceptance criterion |
|---|---|
| Sites | all five sites open and render the expected root pages |
| Counts | object counts per type/path match expected migration mapping |
| IDs | all migrated object ids are preserved unless explicitly approved |
| UIDs | UID mapping is complete and all required inbound links resolve |
| Fields | every migrated field passes type/content comparison |
| Rich text | HTML output is equivalent and safe HTML behavior is preserved |
| Files | every required file has matching hash/size/name/MIME type |
| Workflows | chain/state counts match before migration |
| Permissions | effective roles/permissions match required matrix |
| Local roles | no unexpected local role loss |
| Forms | every required PFG form has an EasyForm equivalent |
| Form data | retained submissions are accounted for |
| Search | catalog counts and key searches match |
| Navigation | custom navigation still exposes required content |
| Imports | all required Excel/CSV import workflows operate correctly |
| Exports | Excel exports open in current supported spreadsheet software |
| Browser views | all custom URLs return expected status/content |
| JavaScript | all interactive admin screens work without console errors |
| Python 3 | no Python 2-only imports or string/bytes failures |
| ZODB | `zodbverify` passes after Python 3 conversion |

---

# 14. Concrete implementation backlog after this audit

The next implementation work should be split into independently reviewable changes:

1. `target-buildout`: Plone 5.2.15 Docker/buildout skeleton.
2. `runtime-inventory`: read-only 4.3 database inventory tool.
3. `at-compat`: temporary Plone 5.2/Python 2 compatibility for the existing packages.
4. `dx-types`: Dexterity schemas and GenericSetup for each site-specific type.
5. `migrators`: deterministic AT→DX migration scripts with dry-run/reporting mode.
6. `pfg-easyform`: form inventory and EasyForm recreation/migration.
7. `views`: browser views replacing filesystem Python Scripts.
8. `theme`: Plone 5 theme/resource registry migration.
9. `javascript`: supported JS modules replacing old jQuery/plugin stack.
10. `python3`: final Python 3 port after AT migration.
11. `zodb3`: offline database conversion tooling and verification procedure.
12. `acceptance`: automated before/after migration comparison and end-to-end tests.

Each backlog item should be tested against the real cloned 4.3 database before it is considered production-ready.

---

# 15. Source evidence index

Key source files inspected for this audit include:

- `buildout.cfg`
- `buildout-base.cfg`
- `Dockerfile`
- `docker-compose.yml`
- `src/imiimenik.produkti/imiimenik/produkti/content/produkti.py`
- `src/imiimenik.produkti/imiimenik/produkti/content/uvoz.py`
- `src/dezurstva.produkti/dezurstva/produkti/content/dezurstvo.py`
- `src/dezurstva.produkti/dezurstva/produkti/content/seznam_zaposlenih.py`
- `src/kiestra.produkti/kiestra/produkti/content/dezurstvo.py`
- `src/preiskave.produkti/preiskave/produkti/content/imipreiskava.py`
- `src/preiskave.produkti/preiskave/produkti/content/imiuvozipreiskavo.py`
- `src/nadomescanja.produkti/nadomescanja/produkti/content/laboratorij.py`
- `src/nadomescanja.produkti/nadomescanja/produkti/content/dezurstvo.py`
- `src/nadomescanja.produkti/nadomescanja/produkti/browser/nadomescanja_data.py`
- `src/nadomescanja.produkti/nadomescanja/produkti/browser/nadomescanja_view.py`
- all five `*.podoba` `setuphandlers.py` files
- all five `*.podoba` skin/profile inventories
- custom `rolemap.xml` files
- custom type `types.xml`/`types/*.xml` files
- representative old skin Python Scripts, templates and JavaScript files

No migration implementation was added in the source repository.

---

# 16. Final recommendation

Proceed with a **staged Plone 5.2 migration with an explicit AT→DX boundary**, not a direct rewrite and not a direct Python 3 conversion.

The target architecture should preserve the five site-specific domain models as separate Dexterity types, preserve ids/paths and required binary data, replace PFG with EasyForm only after database form discovery, replace the Plone 4 skin/JS architecture deliberately, and make all migration operations deterministic and repeatable.

The immediate next step is **not** application rewriting. It is obtaining a read-only clone of the real 4.3 `Data.fs` and running the runtime inventory described in this document. That inventory will turn the remaining unknowns—especially PFG, workflows, local permissions, actual field value shapes, relations, and hidden content—into explicit migration inputs.
