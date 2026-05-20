#!/usr/bin/env bash
# Dry-run-execute simulator.
# Args: <ccu_ip> <batches_json> <rstp_root_mac_pre> <targets_csv>
# Runs the full event flow with simulated timings. No obn update c.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 99_dry_run_simulate.sh <ccu_ip> <batches_json> <rstp_root_mac_pre> <targets_csv>}"
BATCHES_JSON="$2"
RSTP_PRE="$3"
TARGETS_CSV="$4"

emit_event "dry_run_started" mode="dry-run-execute" rstp_root_mac_pre="$RSTP_PRE"
emit_event "gate_1_awaiting_ack" blast_radius="DRY RUN — no destructive ops will be performed" simulated=true

BATCH_COUNT=$(echo "$BATCHES_JSON" | python3 -c 'import sys, json; print(len(json.load(sys.stdin)))')
SIMULATED_RRQ_SECS=15
SIMULATED_FLIP_SECS=540

for IDX in $(seq 1 "$BATCH_COUNT"); do
  BATCH_IPS=$(echo "$BATCHES_JSON" | python3 -c "import sys, json; print(','.join(json.load(sys.stdin)[$IDX-1]))")
  emit_event "batch_started" batch=$IDX switches="$BATCH_IPS" simulated=true

  IFS=',' read -ra SWS <<< "$BATCH_IPS"
  for SW in "${SWS[@]}"; do
    emit_event "rrq_seen" batch=$IDX switch="$SW" seconds_since_batch_start=$SIMULATED_RRQ_SECS simulated=true
  done
  for SW in "${SWS[@]}"; do
    emit_event "flipped_to_target" batch=$IDX switch="$SW" seconds_since_batch_start=$SIMULATED_FLIP_SECS simulated=true
  done
  emit_event "batch_completed" batch=$IDX all_ok=true elapsed_seconds=$SIMULATED_FLIP_SECS simulated=true

  if [ "$IDX" -lt "$BATCH_COUNT" ]; then
    emit_event "batch_settle" seconds=300 simulated=true
  fi
done

emit_event "post_check_passed" simulated=true
TOTAL=$(( BATCH_COUNT * (SIMULATED_FLIP_SECS + 300) ))
emit_event "completed" total_elapsed_seconds=$TOTAL batches_run=$BATCH_COUNT switches_pushed=$(echo "$TARGETS_CSV" | tr ',' '\n' | grep -c .) switches_failed=0 simulated=true final=true
