#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-$HOME/new-plone5/src/imi.migration/src/imi/migration/static}"

candidates=(
  "$HOME/previous_plone/src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_custom_images"
  "$HOME/previous_plone/zeocluster/src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_custom_images"
  "$HOME/my-plone-migration/src/preiskave.podoba/preiskave/podoba/skins/preiskave_podoba_custom_images"
)

SOURCE=""
for candidate in "${candidates[@]}"; do
  if [[ -d "$candidate" ]]; then
    SOURCE="$candidate"
    break
  fi
done

if [[ -z "$SOURCE" ]]; then
  echo "Preiskave legacy image directory was not found." >&2
  echo "Looked in:" >&2
  printf '  %s\n' "${candidates[@]}" >&2
  exit 1
fi

mkdir -p "$TARGET/embalazaSlike"
for file in search-quick.png search-podrocja.png search-vzorci.png search-lab.png fajli_dol_new.png fajli_gor_new.png puscica_velika.png; do
  if [[ -f "$SOURCE/$file" ]]; then
    cp -f "$SOURCE/$file" "$TARGET/$file"
    echo "copied $file"
  fi
done

cp -f "$SOURCE"/embalazaSlike/* "$TARGET/embalazaSlike/"
echo "copied packaging images -> $TARGET/embalazaSlike"
echo "source: $SOURCE"
