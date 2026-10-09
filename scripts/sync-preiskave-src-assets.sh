#!/bin/sh
set -eu

# Copy the original Plone-4 Preiskave skin assets into the Plone-5 resource
# directory.  These are binary source assets, not migrated ZODB content.
#
# Usage:
#   ./scripts/sync-preiskave-src-assets.sh /path/to/my-plone-migration
#
OLD_REPO=${1:-../my-plone-migration}
SRC="$OLD_REPO/src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_custom_images"
DST="src/imi.migration/src/imi/migration/static"

if [ ! -d "$SRC" ]; then
    echo "Preiskave source asset directory not found: $SRC" >&2
    exit 2
fi

mkdir -p "$DST/embalazaSlike"
cp -f "$SRC"/embalazaSlike/* "$DST/embalazaSlike/"

# Use the exact filenames referenced by the Plone 4.3 preiskave_view.pt.
# Do not substitute the separate iskanje-*.png artwork: those are different
# graphics and were the reason the 5.2 catalogue launch icons looked wrong.
[ ! -f "$SRC/logo.png" ] || cp -f "$SRC/logo.png" "$DST/logo.png"
[ ! -f "$SRC/search-quick.png" ] || cp -f "$SRC/search-quick.png" "$DST/search-quick.png"
[ ! -f "$SRC/search-podrocja.png" ] || cp -f "$SRC/search-podrocja.png" "$DST/search-podrocja.png"
[ ! -f "$SRC/search-vzorci.png" ] || cp -f "$SRC/search-vzorci.png" "$DST/search-vzorci.png"
[ ! -f "$SRC/search-lab.png" ] || cp -f "$SRC/search-lab.png" "$DST/search-lab.png"
[ ! -f "$SRC/fajli_dol_new.png" ] || cp -f "$SRC/fajli_dol_new.png" "$DST/fajli_dol_new.png"
[ ! -f "$SRC/fajli_gor_new.png" ] || cp -f "$SRC/fajli_gor_new.png" "$DST/fajli_gor_new.png"
[ ! -f "$SRC/puscica_velika.png" ] || cp -f "$SRC/puscica_velika.png" "$DST/puscica_velika.png"

count=$(find "$DST/embalazaSlike" -type f | wc -l | tr -d ' ')
echo "Synced $count packaging images plus exact Preiskave 4.3 skin artwork from $SRC"
