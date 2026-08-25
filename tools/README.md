# Plone 4.3 read-only database inventory

`plone43_inventory.py` is deliberately a **Plone 4.3 / Python 2.7 tool**. It is not imported by the Plone 5.2 application and is not part of application startup.

It inventories these five sites:

- `/portal` — IMI imenik
- `/dezurstva` — Dežurstva
- `/kiestra` — Kiestra
- `/preiskave` — Preiskave
- `/nadomescanja` — Nadomeščanja

It walks the actual ZODB objects rather than relying only on the catalog. For each portal type it records aggregate counts, runtime classes, type/factory configuration, representative objects, AT schema fields, field values, storage/indexing/searchability/default/vocabulary information, interfaces, workflows, local roles, permissions and references. It also detects PFG objects, records their nested structure/configuration, reports File/Image field counts and sizes, and flags objects without a recognizable portal type.

## Safety model

The script contains no calls to `invokeFactory`, `manage_addProduct`, `setWorkflowState`, `reindexObject`, schema mutation APIs, transaction commit APIs, or other content/workflow/index mutation APIs. It only traverses and reads existing objects/tools and writes two files outside ZODB:

- `plone43_inventory.json`
- `plone43_inventory.md`

**Important:** `bin/instance run` starts a Zope application process and therefore the normal Plone process must not be running against the same `Data.fs`. The safest operational procedure is to stop the source container first, then run a one-shot container using the same image and mounted database volume. This avoids `Data.fs.lock` contention and prevents two Zope processes from opening the storage concurrently.

The inventory itself does not commit a transaction. Do not run it against a database that is simultaneously serving requests.

## Exact procedure with the source Docker setup

The source repository's Compose service is named `instance`, is built from the source `Dockerfile`, and mounts:

- `./var/filestorage` -> `/plone/instance/var/filestorage`
- `./var/blobstorage` -> `/plone/instance/var/blobstorage`
- `./src` -> `/plone/instance/src`

The source image is Python 2.7 / Plone 4.3.20. The source Compose service normally runs `bin/instance console`.

### 1. Stop the running Plone/Zope process

From the **source repository checkout** (the directory containing `docker-compose.yml`):

```sh
docker compose stop instance
```

Verify that no source instance is still running:

```sh
docker compose ps
```

The `instance` service should not be running. Do not use `kill -9` as the normal shutdown procedure; allow Zope to close its ZODB cleanly.

If the installation is managed by another supervisor rather than Compose, stop that supervisor-managed Zope process instead. The requirement is that no process has the source `Data.fs` open when the inventory starts.

### 2. Make a filesystem backup before the first inventory run

The inventory is intended to be read-only, but because this is the real production-era database, make a backup before opening it with a different process:

```sh
tar -C var -czf /safe/backup/plone43-filestorage-$(date +%Y%m%d-%H%M%S).tar.gz filestorage
```

If blobs are required for the inventory's file/image size information, also back up `var/blobstorage`:

```sh
tar -C var -czf /safe/backup/plone43-blobstorage-$(date +%Y%m%d-%H%M%S).tar.gz blobstorage
```

Do not perform this backup while Zope is running.

### 3. Put the target-repository tooling somewhere the source container can read

Do **not** copy the tool into `src/` of the source repository and do not commit it there. Mount the target checkout read-only instead. For example, if the target checkout is `/work/new-plone5` on the Docker host, use:

```sh
mkdir -p inventory-output
```

### 4. Run the one-shot inventory container

From the source repository checkout:

```sh
docker compose run --rm --no-deps \
  -v /work/new-plone5/tools:/migration-tools:ro \
  -v "$PWD/inventory-output:/inventory-output" \
  instance \
  bin/instance run /migration-tools/plone43_inventory.py /inventory-output
```

Replace `/work/new-plone5` with the absolute path of the **target** `travegre/new-plone5` checkout.

The command uses the already-built Plone 4.3 image. It does not start the Compose service's normal long-running `console` command. The source `var/filestorage` and `var/blobstorage` mounts remain the same as the normal service, so the script sees the real source database.

The output will be on the host in:

```text
inventory-output/plone43_inventory.json
inventory-output/plone43_inventory.md
```

### 5. Inspect the result

The JSON is the machine-readable authority for later migration tooling. The Markdown is a human-readable review report. In particular, review:

- every portal type count in all five sites;
- runtime class lists for each type;
- `imipreiskava` samples/classes/schema;
- all `produkti` and `dezurstvo` implementations separately;
- `laboratorij`;
- all PFG objects and their nested children/configuration;
- workflow chains and actual states;
- local-role objects;
- reference/broken-reference sections;
- File/Image field counts and byte totals;
- objects reported as `Unknown` or with no portal type;
- any errors recorded for individual sites.

### 6. Restart the source site only after the inventory is finished

```sh
docker compose up -d instance
```

Do not run the inventory while this service is serving the database.

## If `Data.fs.lock` is present

A lock file means another process may still have the FileStorage open. **Do not delete `Data.fs.lock` while a Zope process might still be using the database.** First identify and stop the process holding the storage. Only after a clean shutdown should an old stale lock be investigated.

A normal `docker compose stop instance` followed by `docker compose run --rm --no-deps ...` avoids the expected lock conflict because the two Zope processes are never concurrent.

## Do not run it from Python 3 / Plone 5.2

The source database contains Python 2-era persistent objects and the source packages are Plone 4.3 code. The inventory must execute inside the **existing Plone 4.3 environment** so that stored classes and Archetypes fields can be imported and inspected correctly.

The tool must not be added to `buildout.cfg`, `configure.zcml`, `profiles`, or any Plone 5.2 startup hook.

## Output characteristics

The inventory intentionally does **not** export all 10,000+ objects. It records complete schema/configuration information available at runtime and up to five representative objects per portal type. Field values are bounded in size. PFG structures are recursively represented to a bounded depth. Binary fields are represented by field type, filename and size, not by their binary contents.

The script reads both declared/type configuration and actual runtime object classes. Therefore a database object whose runtime class differs from the source repository's expected class will show up in the inventory and can be compared against `MIGRATION_AUDIT.md` before any Dexterity work begins.
