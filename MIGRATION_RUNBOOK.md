# Plone 5.2 migration runbook

This repository now contains the target-side migration tooling for the export produced by the Plone 4.3 instance.

## 1. Full export location

The large files remain outside Git. By default Docker Compose mounts:

```
../previous_plone/src/export -> /migration-data/export
```

The mounted directory must contain:

```
manifest.json
objects.jsonl
pfg.jsonl
binaries/
reports/
```

If the export lives elsewhere, set `PLONE43_EXPORT_DIR` to its absolute path before running Docker Compose.

## 2. Build the target

From `new-plone5`:

```bash
git pull
docker-compose build --no-cache
docker-compose up -d
```

Plone listens on port 8070.

## 3. Create the five target sites and install migration profiles

Stop the foreground instance before using `bin/instance run` against the same FileStorage:

```bash
docker-compose stop plone
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_prepare.py
```

This creates/updates these clean target sites:

- `/portal`
- `/dezurstva`
- `/kiestra`
- `/preiskave`
- `/nadomescanja`

and installs `imi.migration`, Dexterity and EasyForm through the GenericSetup profile dependencies.

## 4. Import the non-PFG content

```bash
docker-compose run --rm --no-deps plone \
  bin/instance run tools/plone52_import.py \
  --input-dir=/migration-data/export
```

The exporter writes parent paths before children, and the importer preserves the five-site split and maps ambiguous custom types by `(site, legacy portal_type)`.

Important mappings include:

- `portal/produkti -> imi.directory.person`
- `dezurstva/dezurstvo -> imi.duty.roster_day`
- `kiestra/dezurstvo -> imi.kiestra.work_day`
- `preiskave/imipreiskava -> imi.exams.examination`
- `nadomescanja/dezurstvo -> imi.replacements.day`
- `nadomescanja/laboratorij -> imi.replacements.laboratory`

PloneFormGen records are skipped in this pass and handled separately.

The importer writes target-side errors to:

```
/migration-data/export/reports/plone52-import-errors.json
```

Do not accept the import if this file contains unexplained errors.

## 5. Restart and inspect

```bash
docker-compose up -d
```

Open the five sites on port 8070 and inspect representative records before running parity checks or form conversion.

## 6. Idempotency / reruns

Migration scripts are designed for a disposable clean target. For a full rerun, remove/recreate only the **target** filestorage/blobstorage and repeat preparation/import. Never point Plone 5.2 at the old Plone 4.3 Data.fs.

The old Plone 4.3 database remains authoritative until final cut-over.
