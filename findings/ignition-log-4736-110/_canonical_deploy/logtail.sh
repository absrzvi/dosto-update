#!/bin/bash
# nd-logtail — periodic flush of volatile kernel/journal tail to persistent /data.
# /var/log, /run/log/journal and dmesg are all tmpfs on this CCU and vanish on
# every boot. This copies a rolling tail so that, after an outage, we still have
# the last kernel messages + high-priority journal lines that preceded it (catches
# thermal, undervoltage, link, OOM, and the tail of a GRACEFUL shutdown sequence).
# Ring-buffered (keeps last N snapshots) so it never fills /data.
# Installed for 4736-110 / Fzg 138 / box1-t23, 2026-06-18.
set -u
LOGDIR=/data/ignition-log/logtail
KEEP=200          # keep last 200 snapshots (~3.3h at 60s cadence)
mkdir -p "$LOGDIR" 2>/dev/null
iso=$(date -u +%Y-%m-%dT%H-%M-%SZ)
SNAP="$LOGDIR/snap_$iso.txt"

{
  echo "##### LOGTAIL SNAPSHOT $iso (boot=$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)) #####"
  echo "----- uptime / loadavg -----"
  cat /proc/uptime; cat /proc/loadavg
  echo "----- dmesg tail (last 40) -----"
  dmesg 2>/dev/null | tail -40
  echo "----- journal priority<=4 (warn+), last 40 this boot -----"
  journalctl -b -p 4 -n 40 --no-pager 2>/dev/null
} > "$SNAP" 2>&1
sync

# Ring-buffer prune: drop oldest beyond KEEP.
ls -1t "$LOGDIR"/snap_*.txt 2>/dev/null | tail -n +$((KEEP+1)) | while read -r f; do rm -f "$f"; done
exit 0
