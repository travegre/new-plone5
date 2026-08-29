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

# Keep the exact production artwork available under the resource names used by
# the 5.2 templates.  Existing files are deliberately overwritten with the
# authoritative 4.3 skin versions.
[ ! -f "$SRC/logo.png" ] || cp -f "$SRC/logo.png" "$DST/logo.png"
[ ! -f "$SRC/search-lab.png" ] || cp -f "$SRC/search-lab.png" "$DST/search-lab.png"
[ ! -f "$SRC/iskanje-hitro.png" ] || cp -f "$SRC/iskanje-hitro.png" "$DST/search-quick.png"
[ ! -f "$SRC/iskanje-podrocja.png" ] || cp -f "$SRC/iskanje-podrocja.png" "$DST/search-podrocja.png"
[ ! -f "$SRC/iskanje-vzorci.png" ] || cp -f "$SRC/iskanje-vzorci.png" "$DST/search-vzorci.png"
[ ! -f "$SRC/fajli_dol_new.png" ] || cp -f "$SRC/fajli_dol_new.png" "$DST/fajli_dol_new.png"
[ ! -f "$SRC/fajli_gor_new.png" ] || cp -f "$SRC/fajli_gor_new.png" "$DST/fajli_gor_new.png"
[ ! -f "$SRC/puscica_velika.png" ] || cp -f "$SRC/puscica_velika.png" "$DST/puscica_velika.png"

count=$(find "$DST/embalazaSlike" -type f | wc -l | tr -d ' ')
echo "Synced $count packaging images plus Preiskave skin artwork from $SRC"
