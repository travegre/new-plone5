#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible wrapper.  The canonical helper knows the actual 4.3 skin
# filenames (iskanje-hitro.png, iskanje-podrocja.png, ...) and maps them to the
# resource names used by the Plone 5 templates.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $# -gt 0 ]]; then
  OLD_REPO="$1"
elif [[ -d "$HOME/my-plone-migration" ]]; then
  OLD_REPO="$HOME/my-plone-migration"
elif [[ -d "$HOME/previous_plone" ]]; then
  OLD_REPO="$HOME/previous_plone"
else
  OLD_REPO="../my-plone-migration"
fi

exec "$ROOT/scripts/sync-preiskave-src-assets.sh" "$OLD_REPO"
