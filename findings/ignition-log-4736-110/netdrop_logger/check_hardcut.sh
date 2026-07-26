#!/bin/bash
# check-hardcut.sh — Zabbix UserParameter helper. Two keys via one script + an arg:
#   check-hardcut.sh total   -> monotonic hard-cut count since deploy (for trending)
#   check-hardcut.sh recent  -> 1 if the LAST boot was a hard cut (per-event alarm), else 0.
#                               Reading 'recent' as 1 RESETS the flag to 0 so the alarm is per-event
#                               (fires once per hard cut, then clears on the next poll).
#
# Read-only except the one-shot reset of last_was_hardcut (so the alarm doesn't latch forever).
set -u
STATE=/data/ignition-log/hardcut-state.json
mode="${1:-total}"

[ -f "$STATE" ] || { echo 0; exit 0; }

if [ "$mode" = "total" ]; then
  grep -oE '"total"[ ]*:[ ]*[0-9]+' "$STATE" | grep -oE '[0-9]+$' | head -1
  exit 0
fi

if [ "$mode" = "recent" ]; then
  v=$(grep -oE '"last_was_hardcut"[ ]*:[ ]*[0-9]+' "$STATE" | grep -oE '[0-9]+$' | head -1)
  v=${v:-0}
  echo "$v"
  # reset the per-event flag to 0 after reporting a 1, so the NMS alarm is per-event not latched.
  if [ "$v" = "1" ]; then
    sed -i 's/"last_was_hardcut"[ ]*:[ ]*1/"last_was_hardcut":0/' "$STATE" 2>/dev/null
  fi
  exit 0
fi

echo 0
