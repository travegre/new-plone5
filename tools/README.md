# Plone 4.3 read-only database inventory

`plone43_inventory.py` is a self-contained **Plone 4.3 / Python 2.7** tool. It is not imported by the Plone 5.2 application and is not part of application startup.

It inventories:

- `/portal` — IMI imenik
- `/dezurstva` — Dežurstva
- `/kiestra` — Kiestra
- `/preiskave` — Preiskave
- `/nadomescanja` — Nadomeščanja

It walks actual ZODB objects and records portal-type counts, runtime classes/inheritance/interfaces, Archetypes schemas where `Schema()` is actually available, field configuration and values, persistent attributes, workflows/states, local roles, permissions, references, PloneFormGen structures, and File/Image information. Objects without an Archetypes schema are explicitly retained and marked as such.

## Read-only safety

The script contains no content/workflow/schema/index mutation calls and does not commit a ZODB transaction. It only reads the existing database and writes these files outside ZODB:

- `plone43_inventory.json`
- `plone43_inventory.md`

Inspection is fault tolerant. Object-, field-, schema-, vocabulary-, workflow-, reference-, and similar failures are recorded with site, path, portal type, runtime class, operation, field, exception type and message, then processing continues.

## Run command

Copy **only this one file** into the Plone 4.3 container, for example:

```sh
cp /path/to/new-plone5/tools/plone43_inventory.py src/plone43_inventory.py
```

Then run:

```sh
bin/instance run src/plone43_inventory.py --output-dir=/plone/instance/src
```

The alternative form is also supported:

```sh
bin/instance run src/plone43_inventory.py --output-dir /plone/instance/src
```

The output is:

```text
/plone/instance/src/plone43_inventory.json
/plone/instance/src/plone43_inventory.md
```

## Plone 4.3 `instance run` argv handling

The inventory does **not** use `__file__` to determine its script name. Under the affected Zope 2.13 runner, `__file__` can refer to the generated interpreter rather than the requested script.

Instead, the script knows its own basename (`plone43_inventory.py`) and finds the final occurrence of that exact script name in `sys.argv`. This handles the launcher forms observed in Plone 4.3, including Python's `-c` marker and duplicate script-name bookkeeping. Only launcher bookkeeping is removed; genuine unknown inventory arguments are still rejected.

For example, a launcher shape such as:

```text
[interpreter, '-c', 'src/plone43_inventory.py', '--output-dir=/inventory]
```

is normalized to the inventory arguments:

```text
['--output-dir=/inventory']
```

An unrelated argument such as `other.py` or `--bogus` is not silently ignored.

## Stopping the source Zope process

Do **not** run a second Zope process against the same `Data.fs` while the normal Plone 4.3 process is serving it.

Stop the source container first:

```sh
docker compose stop instance
```

Verify it is stopped:

```sh
docker compose ps
```

Do not delete `Data.fs.lock` while a Zope process may still have the database open.

Then run the inventory in the existing Plone 4.3 environment:

```sh
bin/instance run src/plone43_inventory.py --output-dir=/plone/instance/src
```

A one-shot container can also be used, provided it uses the same Plone 4.3 image and the same database/blob mounts, with the target repository's `tools` directory mounted read-only:

```sh
docker compose run --rm --no-deps \
  -v /work/new-plone5/tools:/migration-tools:ro \
  -v "$PWD/inventory-output:/inventory-output" \
  instance \
  bin/instance run /migration-tools/plone43_inventory.py --output-dir=/inventory-output
```

Replace `/work/new-plone5` with the absolute path of the target checkout.

## What to review

The resulting inventory should be treated as the database authority for the later migration work. Review especially:

- all five site inventories and actual portal-type counts;
- runtime classes for similarly named types in different sites;
- `produkti`, `dezurstvo`, `imipreiskava`, `laboratorij`, `seznam_zaposlenih`, and `uvoz`;
- `imipreiskava` runtime/schema discrepancies;
- Archetypes fields versus persistent attributes not represented by the schema;
- workflows and actual states;
- local roles and permission declarations;
- references and unresolved references;
- PloneFormGen objects and nested field/configuration objects;
- File/Image field types, filenames and sizes;
- unknown/no-portal-type objects;
- the inspection-error list.

The inventory uses representative samples rather than dumping every object. It retains complete field/schema configuration for sampled Archetypes objects and bounded representative stored values. It never invents schema or migration information.

## Compatibility

Run this tool **inside the actual Plone 4.3 / Python 2.7 environment**. Do not execute it with the system Python or from the Plone 5.2 application.
