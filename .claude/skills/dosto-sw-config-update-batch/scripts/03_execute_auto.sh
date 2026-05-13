#!/usr/bin/env bash
# Stage 3 (auto mode): wrap `obn update c sw` and report progress.
# Args: <ccu_ip> <batches_json> <rstp_root_mac_pre>
# Emits batch_started / rrq_seen / flipped_to_target / batch_completed events.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 03_execute_auto.sh <ccu_ip> <batches_json> <rstp_root_mac_pre>}"
BATCHES_JSON="$2"
RSTP_ROOT_PRE="$3"

PRE_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
LOG="/tmp/obn-update-c-sw-$(date -u +%Y%m%dT%H%M%S).log"

emit_event "auto_mode_kickoff" log_file="$LOG" rstp_root_mac_pre="$RSTP_ROOT_PRE"

# Kick off obn update c sw in the background on the CCU via nohup.
# We capture its PID so we can wait for it later.
ccu_run "$CCU_IP" "sudo nohup bash -c 'obn update c sw > $LOG 2>&1' </dev/null >/dev/null 2>&1 & echo \$!" > /tmp/obn_bg_pid.txt
OBN_PID=$(cat /tmp/obn_bg_pid.txt | tr -d '[:space:]')
emit_event "obn_update_started" pid=$OBN_PID

# Iterate through pre-computed batches as our reporting frame.
BATCH_COUNT=$(echo "$BATCHES_JSON" | python3 -c 'import sys, json; print(len(json.load(sys.stdin)))')

for IDX in $(seq 1 "$BATCH_COUNT"); do
  BATCH_IPS=$(echo "$BATCHES_JSON" | python3 -c "import sys, json; print(','.join(json.load(sys.stdin)[$IDX-1]))")
  emit_event "batch_started" batch=$IDX switches="$BATCH_IPS"

  # Monitor this batch (20 min budget per batch).
  set +e
  bash "$(dirname "$0")/05_monitor_batch.sh" "$CCU_IP" "$IDX" "$BATCH_IPS" "$PRE_TS" 1200
  MONITOR_RC=$?
  set -e

  if [ "$MONITOR_RC" -ne 0 ]; then
    # Batch had failures — emit gate_2 and let the calling SKILL.md flow handle engineer choice.
    emit_event "gate_2_awaiting_ack" batch=$IDX
    # In auto mode, default behaviour is wait for engineer ack via stdin sentinel file.
    # The calling agent inspects the event stream and resumes via env var GATE_RESUME.
    if [ "${GATE_RESUME:-}" = "abort" ]; then
      emit_event "auto_aborted" reason="gate_2_abort_chosen"
      ccu_run "$CCU_IP" "sudo kill $OBN_PID 2>/dev/null || true"
      exit 6
    fi
  fi

  # Inter-batch settle: OBN's own 5-min sleep handles this for us. We just emit the marker.
  if [ "$IDX" -lt "$BATCH_COUNT" ]; then
    emit_event "batch_settle" seconds=300
  fi
done

# Wait for OBN's process to finish — should be near-instant since all batches done.
ccu_run "$CCU_IP" "while kill -0 $OBN_PID 2>/dev/null; do sleep 5; done"
emit_event "obn_update_finished"
