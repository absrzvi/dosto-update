#!/usr/bin/env bash
# Stage 6: post-run verification.
# Args: <ccu_ip> <rstp_root_mac_pre> <targets_csv> <neighbour_ip>
# Emits post_check_passed or gate_4_awaiting_ack.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 06_postcheck.sh <ccu_ip> <rstp_root_mac_pre> <targets_csv> <neighbour_ip>}"
RSTP_PRE="$2"
TARGETS_CSV="$3"
NEIGHBOUR="$4"

# 1. RSTP root MAC unchanged.
RSTP_POST=$(rstp_root_mac "$CCU_IP" "$NEIGHBOUR" || echo "unknown")
if [ "$RSTP_PRE" != "$RSTP_POST" ]; then
  emit_event "gate_4_awaiting_ack" reason="rstp_root_changed" rstp_root_mac_pre="$RSTP_PRE" rstp_root_mac_post="$RSTP_POST"
  exit 10
fi
emit_event "rstp_root_unchanged" rstp_root_mac="$RSTP_POST"

# 2. Final obn discover + report, then validate all targets are ✓.
ccu_run "$CCU_IP" 'sudo obn discover >/dev/null 2>&1 && sudo obn report >/dev/null 2>&1'
# Strip ANSI escapes at the source so all downstream greps work on clean text.
VALIDATE=$(ccu_run "$CCU_IP" 'sudo obn validate -t sw 2>/dev/null' | sed 's/\x1b\[[0-9;]*m//g')

IFS=',' read -ra TARGETS <<< "$TARGETS_CSV"
STILL_BAD=""
for SW in "${TARGETS[@]}"; do
  # Pipe-table format: match `| <ip> ` after the coach/device columns.
  LINE=$(echo "$VALIDATE" | grep -E "\| $SW[[:space:]]" || true)
  # Bad if: no line found, OR line contains ✗, OR line lacks ✓.
  if [ -z "$LINE" ] || echo "$LINE" | grep -q "✗" || ! echo "$LINE" | grep -q "✓"; then
    STILL_BAD="${STILL_BAD}${STILL_BAD:+,}$SW"
  fi
done

if [ -n "$STILL_BAD" ]; then
  emit_event "gate_4_awaiting_ack" reason="targets_still_failing" switches="$STILL_BAD"
  exit 11
fi
emit_event "all_targets_at_target_config" count="${#TARGETS[@]}"

# 3. Delegated l2-health rerun. We don't reimplement; we just note that the orchestrator must rerun it.
emit_event "post_check_l2_health_required" note="orchestrator must rerun dosto-l2-health and confirm healthy"

emit_event "post_check_passed"
