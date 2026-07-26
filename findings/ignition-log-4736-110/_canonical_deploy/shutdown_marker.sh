#!/bin/bash
# vign-shutdown-marker — writes a GRACEFUL-shutdown breadcrumb to persistent /data
# at the moment systemd runs the shutdown transaction. If the CCU loses power
# HARD (breaker / ignition cut / yanked supply), this NEVER runs, so the ABSENCE
# of a marker after an outage proves a hard cut; its PRESENCE proves a clean stop.
# Installed for 4736-110 / Fzg 138 / box1-t23, 2026-06-18.
set -u
LOGDIR=/data/ignition-log
OUT="$LOGDIR/shutdown.log"
mkdir -p "$LOGDIR" 2>/dev/null
iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Final CMM reading so we capture supply state at the instant of a clean shutdown.
cmm_v=$(i2ctransfer -y 2 w1@0x2d 0x04 r9 2>/dev/null)
cmm_s=$(i2ctransfer -y 2 w1@0x2d 0x01 r3 2>/dev/null)

# Best-effort reason hint: who/what initiated (systemd target), uptime at stop.
up=$(awk '{print int($1)}' /proc/uptime 2>/dev/null)

echo "$iso GRACEFUL_SHUTDOWN uptime_s=$up cmm04=[$cmm_v] cmm01=[$cmm_s]" >> "$OUT"
sync
exit 0
