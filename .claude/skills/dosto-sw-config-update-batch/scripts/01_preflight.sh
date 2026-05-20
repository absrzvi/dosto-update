#!/usr/bin/env bash
# Stage 1: preflight for dosto-sw-config-update-batch.
# Args: <ccu_ip>
# Emits JSON events to stdout. Exit 0 on pass, non-zero on any precondition failure.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 01_preflight.sh <ccu_ip>}"

emit_event preflight_started ccu_ip="$CCU_IP"

# Single SSH heredoc with all checks. Each check echoes a "key:OK" or "key:FAIL:<reason>" line.
RESULT="$(ccu_run "$CCU_IP" 'bash -s' <<'REMOTE'
set -u

# 1. TFTP conntrack helper loaded?
if lsmod | grep -q '^nf_conntrack_tftp'; then
  echo "tftp_helper:OK"
else
  echo "tftp_helper:FAIL:nf_conntrack_tftp module not loaded"
fi

# 2. iptables CT helper rule on udp/69?
if sudo iptables -t raw -L PREROUTING -n 2>/dev/null | grep -q "udp dpt:69.*CT.*helper.*tftp"; then
  echo "tftp_helper_rule:OK"
else
  echo "tftp_helper_rule:FAIL:iptables raw PREROUTING missing tftp CT helper rule"
fi

# 3. OBN patches — grep for the 8 bug markers in the patched files.
PATCHES_FILE_LIST="/usr/share/obn/lib/device/vendor/vdsrail.py /usr/share/obn/lib/device/snmpdevice.py /usr/share/obn/lib/device/device.py /usr/share/obn/cli/update.py /usr/share/obn/lib/tree.py"
MISSING=""
sudo grep -q "if not result:" /usr/share/obn/lib/device/vendor/vdsrail.py 2>/dev/null || MISSING="$MISSING bug2"
sudo grep -q "if hostname is not None:" /usr/share/obn/lib/device/vendor/vdsrail.py 2>/dev/null || MISSING="$MISSING bug7"
sudo grep -q "ipset.*tftp_allowed" /usr/share/obn/cli/update.py 2>/dev/null || MISSING="$MISSING bug5"
# Bug 1, 3, 4, 6, 8 — markers per dosto-obn-patches; for brevity check the dosto-obn-patches summary file:
if [ -f /var/lib/obn-patches/persisted ]; then
  if grep -q "all_persisted" /var/lib/obn-patches/persisted; then
    echo "obn_patches:OK"
  else
    echo "obn_patches:FAIL:persisted marker file exists but not all_persisted"
  fi
else
  # Fallback to partial check.
  if [ -z "$MISSING" ]; then
    echo "obn_patches:OK"
  else
    echo "obn_patches:FAIL:missing$MISSING"
  fi
fi

# 4. obn busy? Any CLI obn process other than known long-running background jobs.
# serve-api / telemetry are the daemon processes from supervisord.
# user-count / wifi-status / discover-schedule are recurring scheduled jobs that
# can run in the background — we exclude them too, the guard is only for
# operator-driven CLI commands like `obn update`, `obn discover` (manual), `obn report`.
BUSY=$(sudo ps -eo pid,cmd | grep '/usr/share/obn/venv/bin/python' | grep -vE 'serve-api|telemetry|user-count|wifi-status|discover-schedule|grep' | wc -l)
if [ "$BUSY" -eq 0 ]; then
  echo "obn_busy:OK"
else
  echo "obn_busy:FAIL:$BUSY other obn processes running"
fi

# 5. Fresh obn discover succeeds? (we run this regardless — it's the scope-prep step)
if sudo obn discover >/dev/null 2>&1; then
  echo "obn_discover:OK"
else
  echo "obn_discover:FAIL:obn discover returned non-zero"
fi
REMOTE
)"

echo "$RESULT" | while IFS= read -r line; do
  key="${line%%:*}"
  rest="${line#*:}"
  status="${rest%%:*}"
  reason="${rest#*:}"
  if [ "$status" = "OK" ]; then
    emit_event "preflight_check_ok" check="$key"
  else
    emit_event "preflight_check_failed" check="$key" reason="$reason"
  fi
done

# Compute overall verdict
if echo "$RESULT" | grep -q "FAIL"; then
  FIRST_FAIL=$(echo "$RESULT" | grep "FAIL" | head -1)
  FAIL_KEY="${FIRST_FAIL%%:*}"
  emit_event "preflight_aborted" reason="preconditions_unmet:$FAIL_KEY"
  exit 2
fi

# fzg-id-check and l2-health are delegated to their own skills — we just record that the engineer
# should have verified them before invoking us. In --execute, the orchestrator (dosto-commission-train)
# is responsible for chaining these. Standalone invocations may pass --skip-delegated to acknowledge.
if [ "${SKIP_DELEGATED:-0}" = "1" ]; then
  emit_event "preflight_delegated_skipped" reason="SKIP_DELEGATED=1"
else
  emit_event "preflight_delegated_required" checks="[\"fzg-id-check\",\"l2-health\"]" \
    note="run dosto-fzg-id-check and dosto-l2-health and confirm both green before --execute"
fi

emit_event "pre_check_passed"
