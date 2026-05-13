#!/usr/bin/env bash
# Stage 3 (manual mode): drive engineer-scoped batches one at a time.
# Args: <ccu_ip> <batches_json> <rstp_root_mac_pre>
# Emits batch_started / rrq_seen / flipped_to_target / batch_completed events.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 04_execute_manual.sh <ccu_ip> <batches_json> <rstp_root_mac_pre>}"
BATCHES_JSON="$2"
RSTP_ROOT_PRE="$3"

emit_event "manual_mode_kickoff" rstp_root_mac_pre="$RSTP_ROOT_PRE"

BATCH_COUNT=$(echo "$BATCHES_JSON" | python3 -c 'import sys, json; print(len(json.load(sys.stdin)))')
CONSECUTIVE_FAILURES=0

for IDX in $(seq 1 "$BATCH_COUNT"); do
  BATCH_IPS=$(echo "$BATCHES_JSON" | python3 -c "import sys, json; print(','.join(json.load(sys.stdin)[$IDX-1]))")
  emit_event "batch_started" batch=$IDX switches="$BATCH_IPS"

  PRE_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  LOG="/tmp/obn-update-c-batch-$IDX-$(date -u +%Y%m%dT%H%M%S).log"

  # Build the multi-background-`obn update c <ip>` command and dispatch via one SSH call.
  IFS=',' read -ra SWS <<< "$BATCH_IPS"
  REMOTE_CMD=""
  for SW in "${SWS[@]}"; do
    REMOTE_CMD="${REMOTE_CMD}sudo obn update c $SW > /tmp/obn-update-c-$SW-$IDX.log 2>&1 &"$'\n'
  done
  REMOTE_CMD="${REMOTE_CMD}wait"

  ccu_run "$CCU_IP" "$REMOTE_CMD" > "$LOG" 2>&1 &
  CCU_BG_PID=$!
  emit_event "batch_dispatched" batch=$IDX local_pid=$CCU_BG_PID

  # Monitor — 20 min budget.
  set +e
  bash "$(dirname "$0")/05_monitor_batch.sh" "$CCU_IP" "$IDX" "$BATCH_IPS" "$PRE_TS" 1200
  MONITOR_RC=$?
  set -e

  # Reap the dispatcher.
  wait "$CCU_BG_PID" 2>/dev/null || true

  if [ "$MONITOR_RC" -ne 0 ]; then
    CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
    emit_event "gate_2_awaiting_ack" batch=$IDX consecutive_failures=$CONSECUTIVE_FAILURES options="[\"abort\",\"extend-poll\",\"retry\",\"skip\"]"

    case "${GATE_RESUME:-}" in
      abort)
        emit_event "manual_aborted" reason="gate_2_abort_chosen"
        exit 6
        ;;
      skip)
        emit_event "batch_skipped" batch=$IDX
        ;;
      retry|extend-poll|"")
        # Default behaviour: extend-poll once with same budget.
        emit_event "batch_extending_poll" batch=$IDX
        set +e
        bash "$(dirname "$0")/05_monitor_batch.sh" "$CCU_IP" "$IDX" "$BATCH_IPS" "$PRE_TS" 1200
        EXT_RC=$?
        set -e
        if [ "$EXT_RC" -ne 0 ]; then
          emit_event "manual_aborted" reason="batch_failed_after_extension" batch=$IDX
          exit 7
        fi
        CONSECUTIVE_FAILURES=0  # extension succeeded
        ;;
    esac

    if [ "$CONSECUTIVE_FAILURES" -ge 3 ]; then
      emit_event "manual_aborted" reason="three_consecutive_batch_failures"
      exit 8
    fi
  else
    CONSECUTIVE_FAILURES=0
  fi

  if [ "$IDX" -lt "$BATCH_COUNT" ]; then
    emit_event "batch_settle" seconds=300
    sleep 300
  fi
done

emit_event "manual_mode_done"
