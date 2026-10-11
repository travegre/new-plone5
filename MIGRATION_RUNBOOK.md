# Plone 5.2 migration runbook

This repository contains the target-side migration tooling for the export produced by the Plone 4.3 instance.

## 1. Full export location

The large payload stays outside Git. Docker Compose mounts, by default:

```
../previous_plone/src/export -> /migration-data/export
```

The mounted directory currently contains:

```
manifest.json
objects.jsonl
pfg.jsonl
binaries/
reports/
```

If the export lives elsewhere, set `PLONE43_EXPORT_DIR` to its absolute path before running Docker Compose.

## 2. Final export from the authoritative Plone 4.3 database

Freeze editorial changes first and take verified backups of both `Data.fs` and
blobstorage. Stop the normal 4.3 instance; never run a second Zope process
against the live FileStorage.

Run the source-side exporters in the old Python-2/Plone-4.3 environment:

```bash
bin/instance run src/plone43_export.py \
  --output-dir=/plone/instance/src/export

bin/instance run src/plone43_export_security_settings.py \
  --output-dir=/plone/instance/src/export

bin/instance run src/plone43_export_easyforms.py \
  --output-dir=/plone/instance/src/export
```

A production export is incomplete unless it contains at least:

```text
manifest.json
objects.jsonl
security-settings.json
pfg.jsonl
pfg-easyform.jsonl
binaries/
reports/
```

Review the source export error reports before touching the target. In particular
review `reports/uncataloged-zodb.json`: the normal content import intentionally
uses cataloged/active content, but the hardened exporter now enumerates
contained ZODB objects absent from the catalog so archive/stale/business data
cannot disappear silently. Decide explicitly whether any such path must be
added to migration policy before cut-over. The source remains authoritative
until all target parity gates pass.

The hardened source exporter also records each object's owner. Use the
`migration-cutover-hardening` branch of `travegre/my-plone-migration` (or
merge/cherry-pick its exporter hardening) for the final export.

## 3. Build the pinned Plone 5.2 target

From `new-plone5`:

```bash
git pull
docker-compose build --no-cache
```

The image is pinned to Plone 5.2.15 / Python 3.8 and now includes the migration runners under `/plone/instance/tools`.

## 4. Create the five clean target sites and install migration profiles

Do this before starting the normal foreground instance:

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_create_sites.py
```

This creates these clean Slovenian target sites with no sample content:

- `/portal`
- `/dezurstva`
- `/kiestra`
- `/preiskave`
- `/nadomescanja`

and installs `imi.migration`, Dexterity and EasyForm through the GenericSetup dependencies.

## 5. Import users, groups, roles and compatible site settings

Do this **before content import** so object ownership can be restored to real
target principals:

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_import_security_settings.py \
  --input-dir=/migration-data/export

docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_verify_security_settings.py \
  --input-dir=/migration-data/export
```

Review both:

```text
reports/plone52-security-settings-import.json
reports/plone52-security-settings-parity.json
```

The migration preserves users, member properties, real groups, group
memberships, site-wide user/group roles and site-root local roles. PAS virtual
groups are deliberately not recreated.

User password material and SMTP passwords are deliberately not exported.
Newly-created local users therefore require password reset unless a separate,
plugin-specific credential migration is designed and tested. Do not copy PAS
password hashes into the normal JSON export.

## 6. Import standard and custom content

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_import.py \
  --input-dir=/migration-data/export
```

The 4.3 exporter writes parent paths before children, so the streaming importer can recreate the hierarchy without loading the 284 MB JSONL file into memory.

Important site-aware mappings include:

- `portal/produkti -> imi.directory.person`
- `dezurstva/dezurstvo -> imi.duty.roster_day`
- `dezurstva/seznam_zaposlenih -> imi.staff.directory`
- employee folders beneath the staff directory -> `imi.staff.employee`
- `kiestra/dezurstvo -> imi.kiestra.work_day`
- `preiskave/imipreiskava -> imi.exams.examination`
- `nadomescanja/dezurstvo -> imi.replacements.day`
- `nadomescanja/laboratorij -> imi.replacements.laboratory`
- `Topic -> Collection`

Import/upload helper objects such as `uvoz` are intentionally skipped. PloneFormGen records are skipped here and handled in the EasyForm pass.

The importer writes:

```
/migration-data/export/reports/plone52-import-errors.json
```

Do not accept the import if this contains unexplained errors.

## 7. PFG export note

The raw `pfg.jsonl` is retained as audit evidence, but the actual conversion uses EasyForm's own Plone-4 PFG migration helpers so we do not invent XML model semantics.

The final source-export step above already runs the EasyForm migration helper. It adds:

```
pfg-easyform.jsonl
reports/pfg-easyform-errors.json
```

The source database remains read-only; EasyForm itself does not need to be installed into the old Plone site.

## 8. Import EasyForms on Plone 5.2

After `pfg-easyform.jsonl` exists in the mounted export directory:

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_import_easyforms.py \
  --input-dir=/migration-data/export
```

This creates/updates `EasyForm` objects at the original relative paths and assigns the canonical `fields_model` and `actions_model` generated by EasyForm's migration code. It also preserves the exported thank-you configuration where supported by EasyForm 3.2.1.

Review:

```
/migration-data/export/reports/plone52-easyform-import-errors.json
```

## 9. Finalize site layouts/admin presentation

After content and EasyForm import:

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_finalize_other_sites.py
```

This restores the five site root layouts, Barceloneta/admin-host presentation,
legacy public layouts and required application roots. It is presentation
finalization, not a data migration substitute.

## 10. Run parity checks

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_parity.py \
  --input-dir=/migration-data/export
```

Review:

```
/migration-data/export/reports/plone52-parity.json
```

Parity, not mere completion, is the acceptance gate. Investigate count, path,
field, binary, workflow, local-role, ownership, creator, timestamp and form
mismatches before cut-over. Also require the security/settings parity report to
have zero unexplained differences.

## 11. Start Plone for manual inspection

```bash
docker-compose up -d
```

Plone listens on port 8070. Inspect representative objects in all five sites, especially one record for every custom type and both migrated forms.

## 12. Reruns

Treat the Plone 5.2 target as disposable during migration development. For a clean rerun, remove/recreate only the **target** `var/filestorage` and `var/blobstorage` directories, then repeat create-sites/import/easyform/parity.

Never point Plone 5.2 at the old Plone 4.3 Data.fs. The old Plone 4.3 database remains authoritative until the final migration freeze and cut-over.


## 13. Production cut-over acceptance checklist

Do not switch production traffic until all of these are true:

- source `Data.fs` and blobstorage backups are verified and retained;
- source export reports contain no unexplained errors;
- `plone52-import-errors.json` contains no unexplained errors;
- EasyForm import/verification passes;
- security/settings parity has zero unexplained differences;
- content parity has zero unexplained differences for every object intended by policy;
- binary SHA-256 checks pass;
- workflow states and object local roles match;
- owners, creators and source timestamps match;
- representative anonymous/public and authenticated/admin URLs work on all five sites;
- migrated local users have a documented password-reset path;
- SMTP credentials are configured separately from migration artifacts;
- the old 4.3 database remains untouched and available for rollback until acceptance.

### Deliberate non-goals / items requiring explicit policy

The normal migration export does not contain passwords or SMTP secrets.
References/relations and source UUID reuse must not be assumed merely because
the import completed. If the final source inventory shows business-relevant
`relatedItems`, UID-based references, non-cataloged/archive content, or
external PAS/LDAP principals, treat those as explicit migration work and add
a parity gate before cut-over rather than silently dropping or inventing them.
