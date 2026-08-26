# Plone 4.3 → Plone 5.2 migration plan

This plan is based on the real Plone 4.3 database inventory in `tools/plone43_inventory.json` / `.md` and the source tree in `travegre/my-plone-migration`.

## Target platform

- Plone **5.2.15**
- Python **3.8**
- Dexterity for all custom content
- `collective.easyform==3.2.1` for forms migrated from PloneFormGen
- One ZODB containing five independent Plone sites, preserving the current site split:
  - `portal`
  - `dezurstva`
  - `kiestra`
  - `preiskave`
  - `nadomescanja`

The target will be built from a pinned Python 3.8 image and Plone 5.2.15 constraints instead of relying on the deprecated mutable Plone 5 Docker image.

## Migration principle

Do **not** attempt an in-place Python-2 ZODB conversion followed by ad-hoc Archetypes conversion. Export application content and metadata from the stopped/read-only Plone 4.3 database, then import into clean Plone 5.2 sites using explicit site/type mappings. This makes the transformation reproducible and lets us distinguish active content from stale/archive trees.

The old source remains authoritative until cut-over. Migration scripts must be rerunnable and idempotent against a fresh target.

## Custom type mappings

Legacy portal type names are deliberately not reused where they are ambiguous. The three `dezurstvo` classes are different applications and must remain different types.

| Source site | Legacy type | Target Dexterity type | Notes |
|---|---|---|---|
| `portal` | `produkti` | `imi.directory.person` | Directory/person record. Preserve all legacy contact/organizational fields. |
| `portal` | `uvoz` | no content type | Import/upload helper only. Replace with an admin import utility; do not migrate as business content unless inventory shows meaningful stored state. |
| `dezurstva` | `dezurstvo` | `imi.duty.roster_day` | Folderish duty/on-call roster with its own roster fields and staff vocabulary. |
| `dezurstva` | `seznam_zaposlenih` | `imi.staff.directory` | Container/import utility. Child employee folders become `imi.staff.employee`. Uploaded source files are operational inputs, not canonical business data. |
| `kiestra` | `dezurstvo` | `imi.kiestra.work_day` | Completely different schema from Dežurstva: work-station assignments, notes and permanent text. |
| `preiskave` | `imipreiskava` | `imi.exams.examination` | Folderish examination record. Preserve RichText, list fields, raw legacy string fields and binary attachment. |
| `nadomescanja` | `dezurstvo` | `imi.replacements.day` | Preserve `nadomescanja_json` losslessly first; expose parsed rows through Python helpers/views. |
| `nadomescanja` | `laboratorij` | `imi.replacements.laboratory` | Laboratory metadata, abbreviation and default leader references. |

Standard `Document`, `Folder`, `File`, `Image`, `Link`, `News Item`, etc. are migrated to their Plone 5.2 Dexterity equivalents.

## `portal` / IMI imenik

The source `produkti` schema contains these custom string fields and they remain first-class target fields:

`predime`, `ime`, `priimek`, `zaime`, `oddelek`, `telefon`, `vuporabi`, `maticna`, `opis`, `enota`, `lokacija`, `dodatna`, `dect`, `fax`, `multitone`, `mobilna`, `zunanja`, `enaslov`, `zenaslov`, `star`.

`maticna` and `star` were not searchable in Archetypes and should remain non-search indexes unless the application requires otherwise. The other legacy searchable fields will be represented by catalog indexes or a combined SearchableText adapter rather than creating 18 unnecessary standalone indexes.

The database inventory shows more ZODB objects than the earlier catalog-only counts, including old/archive directory trees. We will **not blindly migrate every traversable object**. The exporter records `cataloged=true/false` and source path. Active cataloged content is the default migration set. Non-cataloged/archive trees are exported to a separate manifest and only imported when explicitly allowed by a migration policy file.

## `dezurstva`

The `dezurstvo` source class is folderish and contains many list-valued roster assignments (for example `dezurni_zdravnik`, `nadzorni_zdravnik`, `specializant`, `sarsifon`, laboratory/team fields), a phone field and a Boolean `klukca` flag. Its vocabulary is derived from `dezurstva/seznam_zaposlenih`.

The target therefore has:

- `imi.duty.roster_day`: Dexterity container; list fields store stable employee IDs.
- `imi.staff.directory`: Dexterity container.
- `imi.staff.employee`: non-folderish record with source employee ID, title/name, contact and email parsed from the old folder title/description convention.

The old `seznam_zaposlenih` Excel uploads are not the canonical employee records; the generated child objects are. The migration preserves the child records and replaces Excel ingestion with a Python-3 import utility after cut-over.

## `kiestra`

This site's `dezurstvo` is **not** the Dežurstva schema. It becomes `imi.kiestra.work_day` with separate fields:

- assignment lists: `priprava_vzorcev`, `cepljenje_vzorcev`, `odcitavanje`, `identifikacija`, `antibiogram`, `izolacija`, `odpad`, `ciscenje`
- note strings: the corresponding `*_text` fields
- `stalni_tekst` as RichText/text content

Employee choices continue to reference the migrated staff directory by stable source ID.

## `nadomescanja`

The current implementation has deliberately diverged from the other `dezurstvo` types. Its business state is `nadomescanja_json`, a JSON array of replacement rows. The first migration version preserves that exact raw value. A parser exposes the rows as Python dictionaries; normalization into relation/list subobjects can be considered later only after parity is established.

`laboratorij` becomes a separate Dexterity container with:

- `okrajsava` (required text line)
- `privzeti_vodja` (list of employee IDs)

## `preiskave`

`imipreiskava` becomes a folderish Dexterity type. Field mapping is intentionally conservative because the old class mixes `StringField` storage with `LinesWidget` presentation on several properties.

- true Archetypes `LinesField` values (`podrocje`, `preiskava_vzorec_nujno`) become tuple/list fields.
- rich text fields (`sklop`, `sinonim`, `metode`, `opis`, `opombe`, `trajanje`, `urnik`) become `RichText`.
- fields implemented as `StringField` despite Lines widgets (`vzorci`, `vzorci_lab`, `vzorci_lab_tel`, `vzorci_odvzem`, `vzorci_odvzem_video_sifra`, `vzorci_kolicina`, `embalaza_slika_sifra`, `vzorci_transport`, `vzorci_opomba`, `vzorci_nivo1` ... `vzorci_nivo6`) are initially preserved as text exactly as stored. We do not coerce them to lists unless the runtime export proves the stored value is list-like.
- `datoteka` becomes a Dexterity named file field.
- child `datoteke` content and any special child type are migrated separately rather than recreated implicitly by an `at_post_create_script`.

This is specifically designed to avoid losing the source/runtime schema differences already seen during the audit.

## PloneFormGen → EasyForm

PFG exists in `dezurstva` and `nadomescanja`. The exporter must serialize each FormFolder recursively, including fields, labels, required flags, defaults, vocabularies, validators, thanks page settings and mailer adapter configuration.

The target importer creates `collective.easyform` forms and constructs EasyForm field/action XML from the exported PFG configuration. PFG content is not copied as generic folders.

Known source portal types include `FormFolder`, `FormMailerAdapter`, `FormSelectionField`, `FormStringField`, `FormTextField` and `FormThanksPage`. Mapping:

- `FormStringField` → EasyForm text line
- `FormTextField` → EasyForm text area
- `FormSelectionField` → EasyForm choice field with preserved vocabulary/items
- `FormMailerAdapter` → EasyForm mailer action
- `FormThanksPage` → form thanks-page/message settings

The migration test suite must submit each migrated form in a disposable target and verify validation and mail-action configuration without sending real mail.

## Metadata preserved for all content

The exporter/importer preserves, where present:

- source site and source path
- ID and title/description
- portal type and runtime class
- creation/modification dates
- effective/expiration dates
- creators / owner where resolvable
- UUID/UID where safe; otherwise an explicit `legacy_uid` mapping table
- workflow state
- local roles and local-role blocking
- exclude-from-navigation and related standard behaviors
- references/relations via a second pass after all target objects exist
- file/image filename, content type and bytes

## Export format

Do not produce one enormous in-memory JSON document. The migration exporter writes:

```
export/
  manifest.json
  objects.jsonl
  pfg.jsonl
  binaries/
  reports/
    cataloged-vs-zodb.json
    skipped.json
    errors.json
```

Each `objects.jsonl` record is independent. Binary payloads are stored as files and referenced by relative path. This avoids Python-2 Unicode/memory problems and permits restart/checkpoint behavior.

## Import passes

1. Create five clean Plone sites and install the site-specific migration profile.
2. Create containers and standard content in path order.
3. Create custom Dexterity records and copy scalar/list/rich-text fields.
4. Copy binaries.
5. Convert employee-folder records.
6. Convert PFG forms to EasyForm.
7. Resolve references/relations using the source-path/UID map.
8. Apply workflow states and local roles.
9. Reindex.
10. Run parity reports.

## Parity gates before cut-over

Migration is not accepted merely because import completes. For each site compare:

- content counts by source type and target type
- path/ID manifest
- custom field hashes/normalized values
- binary count and SHA-256
- workflow-state counts
- local-role counts
- unresolved references
- PFG/EasyForm count and field/action signatures

For `portal`, report active/cataloged records separately from archive/non-cataloged records. No archive tree is silently discarded: it must appear either in the migrated manifest or the explicit skipped/archive report.

## What must be done in Plone 4.3 before cut-over

No add-on conversion should be performed destructively in the live Plone 4.3 database. Before the final export:

1. Take verified copies of `Data.fs` and blobstorage.
2. Freeze editorial changes for the final migration window.
3. Run the inventory and migration exporter against the stopped database.
4. Review the cataloged-vs-ZODB/archive report.
5. Review PFG export and unresolved-reference reports.
6. Do not uninstall Archetypes, PFG, themes or custom products before export; they are needed to deserialize and interpret the source objects.

## Implementation order in this repository

1. Pinned Plone 5.2.15 Docker/buildout environment.
2. `imi.migration` Dexterity package and site-specific profiles.
3. Python-2-compatible 4.3 exporter.
4. Python-3 target importer.
5. PFG → EasyForm transformer.
6. Parity checker.
7. Theme/browser-view porting after data parity is proven.

The old skin packages, resource registries, jQuery-era JavaScript and Archetypes classes are **not copied verbatim** into Plone 5.2. Business behavior is ported into Python 3 browser views/services and modern static resources after the data model is stable.
