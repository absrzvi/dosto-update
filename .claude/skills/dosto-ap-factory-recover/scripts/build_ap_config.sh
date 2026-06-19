#!/bin/bash
# build_ap_config.sh — build a recovering factory AP's config by cloning a
# same-variant commissioned sibling, swapping ONLY the hostname.
#
# Runs ON THE CCU. Refuses if the resulting diff is more than the hostname line(s),
# so you can never accidentally push a sibling's full identity to the wrong AP.
#
# Usage:  build_ap_config.sh <target_mac_slug> <sibling_mac_slug>
#   target_mac_slug   = recovering AP MAC, lowercase no colons, e.g. 00145a0479b6
#   sibling_mac_slug  = commissioned same-variant sibling MAC slug, e.g. 00145a04792f
#
# Output: /tmp/dostoneu-obn-<target_mac_slug>.cfg  (ready for LuCI import)
#
# Validated on 4736-115 (box 6018) AP4m, 2026-06-08.
set -euo pipefail

UPLOAD_DIR=/data/auto-topology/upload

if [ $# -ne 2 ]; then
  echo "usage: $0 <target_mac_slug> <sibling_mac_slug>" >&2
  echo "  slugs are lowercase, no colons, e.g. 00145a0479b6" >&2
  exit 2
fi
TGT="$1"; SIB="$2"
SRC="$UPLOAD_DIR/dostoneu-obn-${SIB}.cfg"
DST="/tmp/dostoneu-obn-${TGT}.cfg"

if [ ! -f "$SRC" ]; then
  echo "FAIL: sibling config not found: $SRC" >&2
  echo "  -> the sibling must be a COMMISSIONED AP whose config OBN already rendered." >&2
  echo "  -> list candidates: ls $UPLOAD_DIR/dostoneu-obn-*.cfg" >&2
  exit 1
fi

# Discover the sibling's hostname token (e.g. AP4m-v1-00145a04792f) from its cfg.
SIB_HOST=$(grep -m1 -oE 'AP[0-9]+m?-v[0-9]+-[0-9a-f]{12}' "$SRC" || true)
if [ -z "$SIB_HOST" ]; then
  echo "FAIL: could not find an 'AP..-v.-<mac>' hostname token in $SRC" >&2
  exit 1
fi
# Build the target hostname: same role/variant prefix, target MAC slug.
TGT_HOST="${SIB_HOST%-*}-${TGT}"

echo "sibling cfg : $SRC"
echo "sibling host: $SIB_HOST"
echo "target host : $TGT_HOST"

# Swap ONLY the hostname token.
sed "s/${SIB_HOST}/${TGT_HOST}/g" "$SRC" > "$DST"

# Safety gate: the only diff (ignoring nothing) must be the hostname line(s).
NONHOST_DIFF=$(diff "$SRC" "$DST" | grep -E '^[<>]' | grep -vE "${SIB_HOST}|${TGT_HOST}" | wc -l | tr -d ' ')
if [ "$NONHOST_DIFF" != "0" ]; then
  echo "FAIL: built config differs from sibling by MORE than the hostname:" >&2
  diff "$SRC" "$DST" >&2
  rm -f "$DST"
  exit 1
fi

echo "--- diff (sibling -> target), should be hostname only ---"
diff "$SRC" "$DST" || true
echo "OK: wrote $DST ($(wc -l < "$DST") lines). Safe to LuCI-import to the factory AP."
