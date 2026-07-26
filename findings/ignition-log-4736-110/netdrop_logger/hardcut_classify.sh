#!/bin/bash
# hardcut_classify.sh — runs ONCE at boot (oneshot service, after vign-logger has written its
# 'start' row). Classifies the outage that just ended and maintains a persistent hard-cut counter.
#
# DETECTION (ground truth from the CMM logger + shutdown-marker service):
#   A boot follows a HARD CUT if the CCU did NOT shut down cleanly before it — i.e. there is NO
#   GRACEFUL_SHUTDOWN / SCHEDULED_REBOOT_5H marker in shutdown.log within GRACE seconds before the
#   power-loss. A clean/commanded reboot writes such a marker (vign-shutdown-marker.service ExecStop).
#
#   "Hard cut" here = abrupt-power-loss OR a severe hang that froze the box before it could write a
#   shutdown marker. We do NOT claim "vehicle power cut" — that needs the vehicle-side ignition log.
#   (Voltage discharge/recharge across the gap, visible in vign.csv, tends to indicate real power.)
#
# STATE (persistent, on /data): hardcut-state.json
#   { "total": N, "last_event_iso": "...", "last_was_hardcut": 0|1, "last_boot_iso": "..." }
#   total          = monotonic count of hard cuts since deploy (for trend: cuts/week/train)
#   last_was_hardcut = 1 if THIS boot followed a hard cut (per-event flag; Zabbix alarms on it,
#                      and it is cleared to 0 by the Zabbix reader after it has been alarmed — see
#                      check-hardcut.sh, which resets it once read so the alarm is per-event).
#
# Read-only w.r.t. the system. Idempotent per boot (guards on last_boot_iso).
set -u
LOG=/data/ignition-log
VIGN="$LOG/vign.csv"
SHUT="$LOG/shutdown.log"
STATE="$LOG/hardcut-state.json"
GRACE=90   # seconds: a clean-shutdown marker within this window before the gap = NOT a hard cut

epoch(){ date -u -d "${1/Z/}" +%s 2>/dev/null || echo 0; }

# 1. this boot's 'start' time = last 'start' row in vign.csv
boot_iso=$(awk -F, '$NF=="start"{last=$1} END{print last}' "$VIGN" 2>/dev/null)
[ -z "$boot_iso" ] && exit 0
boot_ep=$(epoch "$boot_iso"); [ "$boot_ep" = 0 ] && exit 0

# read existing state
total=0; last_boot=""
if [ -f "$STATE" ]; then
  total=$(grep -oE '"total"[ ]*:[ ]*[0-9]+' "$STATE" | grep -oE '[0-9]+$'); total=${total:-0}
  last_boot=$(grep -oE '"last_boot_iso"[ ]*:[ ]*"[^"]*"' "$STATE" | sed -E 's/.*"([^"]*)"$/\1/')
fi
# idempotent: already classified this boot?
[ "$last_boot" = "$boot_iso" ] && exit 0

# 2. the power-loss time = the last vign row BEFORE this boot's start (the gap start)
prev_iso=$(awk -F, -v b="$boot_iso" '$1<b && $1!="iso_utc"{p=$1} END{print p}' "$VIGN" 2>/dev/null)
prev_ep=$(epoch "$prev_iso"); [ "$prev_ep" = 0 ] && prev_ep=$boot_ep

# 3. was there a clean-shutdown marker within GRACE sec before the power-loss?
clean=0
if [ -f "$SHUT" ]; then
  while read -r line; do
    m_iso=$(echo "$line" | grep -oE '^[0-9T:-]+Z'); [ -z "$m_iso" ] && continue
    echo "$line" | grep -qE "GRACEFUL_SHUTDOWN|SCHEDULED_REBOOT" || continue
    m_ep=$(epoch "$m_iso"); [ "$m_ep" = 0 ] && continue
    # marker must be at or just before the power-loss (within GRACE)
    if [ "$m_ep" -le $((prev_ep+5)) ] && [ "$m_ep" -ge $((prev_ep-GRACE)) ]; then clean=1; break; fi
  done < "$SHUT"
fi

# 4. classify + update state
if [ "$clean" = 1 ]; then
  hardcut=0
else
  hardcut=1; total=$((total+1))
fi

# write state (last_was_hardcut set to 1 only on a hard cut; check-hardcut.sh resets it after reading)
tmp="$STATE.tmp.$$"
printf '{"total":%d,"last_event_iso":"%s","last_was_hardcut":%d,"last_boot_iso":"%s","prev_loss_iso":"%s"}\n' \
  "$total" "$boot_iso" "$hardcut" "$boot_iso" "$prev_iso" > "$tmp" && mv -f "$tmp" "$STATE"

logger -t nd-hardcut "boot $boot_iso classified hardcut=$hardcut (prev_loss=$prev_iso clean_marker=$clean total=$total)"
