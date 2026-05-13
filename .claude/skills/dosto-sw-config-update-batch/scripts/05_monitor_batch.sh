#!/usr/bin/env bash
# Stage 5: per-batch monitor.
# Args: <ccu_ip> <batch_index> <switches_csv> <pre_push_ts> [budget_seconds]
# Emits rrq_seen / flipped_to_target per switch, then batch_completed or gate_2_awaiting_ack.
# Exit 0 = all OK in budget. Exit 1 = budget exhausted (gate_2 will be emitted by caller).

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 05_monitor_batch.sh <ccu_ip> <batch_index> <switches_csv> <pre_push_ts> [budget]}"
BATCH_IDX="$2"
SWITCHES_CSV="$3"
PRE_TS="$4"
BUDGET="${5:-1200}"

IFS=',' read -ra SWITCHES <<< "$SWITCHES_CSV"
START=$(date +%s)

# Phase 1: 90s window to capture RRQs.
declare -A RRQ_SEEN=()
RRQ_DEADLINE=$((START + 90))
while [ "$(date +%s)" -lt "$RRQ_DEADLINE" ]; do
  JOURNAL=$(ccu_run "$CCU_IP" "sudo journalctl -u tftpd-hpa --since '$PRE_TS' --no-pager 2>/dev/null" || true)
  for SW in "${SWITCHES[@]}"; do
    if ! [[ -v RRQ_SEEN[$SW] ]]; then
      if echo "$JOURNAL" | grep -q "RRQ from $SW"; then
        RRQ_SEEN["$SW"]=1
        emit_event "rrq_seen" batch=$BATCH_IDX switch="$SW" seconds_since_batch_start=$(($(date +%s) - START))
      fi
    fi
  done
  # All seen? bail out of RRQ wait early.
  if [ "${#RRQ_SEEN[@]}" -eq "${#SWITCHES[@]}" ]; then break; fi
  sleep 5
done

# Phase 2: poll obn validate -t sw every 60s until all ✓ or budget exhausted.
declare -A FLIPPED=()
DEADLINE=$((START + BUDGET))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  # Refresh discovery then read validate.
  ccu_run "$CCU_IP" 'sudo obn discover >/dev/null 2>&1' || true
  # Strip ANSI escape sequences at source so grep works on plain text.
  VALIDATE=$(ccu_run "$CCU_IP" 'sudo obn validate -t sw 2>/dev/null' | sed 's/\x1b\[[0-9;]*m//g' || true)
  for SW in "${SWITCHES[@]}"; do
    if ! [[ -v FLIPPED[$SW] ]]; then
      # Pipe-table format: rows contain `| <ip> ` after coach/device columns.
      LINE=$(echo "$VALIDATE" | grep -E "\| $SW[[:space:]]" || true)
      # ✓ in line AND no ✗ AND no "(staged)" qualifier = clean flip to target.
      if [ -n "$LINE" ] && echo "$LINE" | grep -q "✓" && ! echo "$LINE" | grep -q "✗" && ! echo "$LINE" | grep -q "staged"; then
        FLIPPED["$SW"]=1
        emit_event "flipped_to_target" batch=$BATCH_IDX switch="$SW" seconds_since_batch_start=$(($(date +%s) - START))
      fi
    fi
  done
  if [ "${#FLIPPED[@]}" -eq "${#SWITCHES[@]}" ]; then
    emit_event "batch_completed" batch=$BATCH_IDX all_ok=true elapsed_seconds=$(($(date +%s) - START))
    exit 0
  fi
  sleep 60
done

# Budget exhausted — list failed switches.
FAILED=""
for SW in "${SWITCHES[@]}"; do
  if ! [[ -v FLIPPED[$SW] ]]; then
    FAILED="${FAILED}${FAILED:+,}$SW"
  fi
done
emit_event "batch_completed" batch=$BATCH_IDX all_ok=false elapsed_seconds=$(($(date +%s) - START)) failed_switches="$FAILED"
exit 1
