#!/usr/bin/env bash
# Stage 2: scope discovery + batch plan for dosto-sw-config-update-batch.
# Args: <ccu_ip> [<comma-sep switch IPs>]
# Emits JSON events; final event is `plan` with the computed batches.

source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: 02_scope.sh <ccu_ip> [comma-sep-ips]}"
SWITCHES_CSV="${2:-}"  # empty = auto mode (all ✗)

emit_event "scope_started" ccu_ip="$CCU_IP" mode="$([ -z "$SWITCHES_CSV" ] && echo auto || echo manual)"

# Refresh discovery + report snapshot. Required for OBNTree to be buildable.
ccu_run "$CCU_IP" 'sudo obn discover >/dev/null 2>&1 && sudo obn report >/dev/null 2>&1' \
  || { emit_event "scope_aborted" reason="obn_discover_or_report_failed"; exit 3; }

# Read validate output for switches.
VALIDATE=$(ccu_run "$CCU_IP" 'sudo obn validate -t sw 2>/dev/null')

# Parse rows: each switch line has IP, MAC, hostname, config column.
# obn validate output is a pipe-delimited table: | COACH | DEVICE | IP <ANSI> | FIRMWARE <ANSI> | CONFIG <ANSI> |
# Lines containing switch data match /\| 10\./ (pipe-space-10-dot).
# The IP is the fourth pipe-delimited field (f[4]); strip spaces and ANSI escapes (ESC[...m sequences).
# ✗ is UTF-8 bytes \xe2\x9c\x97; ✓ is \xe2\x9c\x93. Both may be wrapped in ANSI color escapes.
# We strip ANSI escapes first, then test for the ✗ character.
NEEDING=$(echo "$VALIDATE" | awk '
  /\| 10\./ {
    # Strip ANSI escapes: ESC [ digits ; ... m
    gsub(/\x1b\[[0-9;]*m/, "")
    # Split on pipe, field 4 is IP (| COACH | DEVICE | IP | FIRMWARE | CONFIG |)
    n = split($0, f, "|")
    ip = f[4]
    # Strip leading whitespace, then keep only the first token (the IP address itself)
    gsub(/^[[:space:]]+/, "", ip)
    sub(/[[:space:]].*$/, "", ip)
    line=$0
    if (line ~ /\xe2\x9c\x97/) print ip
  }
')

ALL_SW_IPS=$(echo "$VALIDATE" | awk '
  /\| 10\./ {
    gsub(/\x1b\[[0-9;]*m/, "")
    n = split($0, f, "|")
    ip = f[4]
    gsub(/^[[:space:]]+/, "", ip)
    sub(/[[:space:]].*$/, "", ip)
    print ip
  }
' | sort -u)
TOTAL=$(echo "$ALL_SW_IPS" | grep -c . || true)
NEED_COUNT=$(echo "$NEEDING" | grep -c . || true)

emit_event "scope_inventory" switches_total=$TOTAL switches_needing_push=$NEED_COUNT

# Intersect with engineer-supplied set, if any.
if [ -n "$SWITCHES_CSV" ]; then
  REQUESTED=$(echo "$SWITCHES_CSV" | tr ',' '\n' | sed 's/[[:space:]]//g')
  # Verify each requested IP appears in ALL_SW_IPS.
  UNKNOWN=$(comm -23 <(echo "$REQUESTED" | sort -u) <(echo "$ALL_SW_IPS" | sort -u))
  if [ -n "$UNKNOWN" ]; then
    UNKNOWN_CSV=$(echo "$UNKNOWN" | paste -sd,)
    emit_event "scope_aborted" reason="switch_not_found" unknown="$UNKNOWN_CSV"
    exit 4
  fi
  # Intersect REQUESTED with NEEDING; if a requested IP is already ✓, log it but exclude from scope.
  ALREADY_OK=$(comm -23 <(echo "$REQUESTED" | sort -u) <(echo "$NEEDING" | sort -u))
  TARGETS=$(comm -12 <(echo "$REQUESTED" | sort -u) <(echo "$NEEDING" | sort -u))
  if [ -n "$ALREADY_OK" ]; then
    OK_CSV=$(echo "$ALREADY_OK" | paste -sd,)
    emit_event "scope_already_ok" switches="$OK_CSV"
  fi
else
  TARGETS="$NEEDING"
fi

if [ -z "$TARGETS" ]; then
  emit_event "scope_complete" verdict="already_at_target_config"
  exit 0
fi

TARGETS_CSV=$(echo "$TARGETS" | paste -sd,)
emit_event "scope_targets" switches="$TARGETS_CSV"

# Compute OBN leaf-first batches via OBN's own tree code.
BATCHES_JSON=$(ccu_run "$CCU_IP" "sudo /usr/share/obn/venv/bin/python <<'PY'
import sys, json
sys.path.insert(0, '/usr/share/obn')
from lib.configuration import Configuration
from cli.update import get_devices
from lib.tree import OBNTree
cfg = Configuration()
devices = get_devices(cfg.report_file, include_ccu=True)
tree = OBNTree.create_tree(devices)
batches = []
for batch in tree.calculate_parallel_update_order():
    batches.append(sorted([d.ip for d in batch]))
print(json.dumps(batches))
PY") || { emit_event "scope_aborted" reason="obn_tree_unbuildable"; exit 5; }

# Filter each OBN batch to only target IPs; drop empty batches.
FILTERED=$(python3 -c "
import json, sys
batches = json.loads('''$BATCHES_JSON''')
targets = set('''$TARGETS_CSV'''.split(','))
result = []
for b in batches:
    filt = [ip for ip in b if ip in targets]
    if filt:
        result.append(filt)
print(json.dumps(result))
")

# Capture RSTP root MAC from first target's neighbour (we use the first target's IP as a probe).
FIRST_TARGET=$(echo "$TARGETS" | head -1)
RSTP_ROOT=$(rstp_root_mac "$CCU_IP" "$FIRST_TARGET" || echo "unknown")

emit_event "plan" batches="$FILTERED" rstp_root_mac_pre="$RSTP_ROOT" targets_csv="$TARGETS_CSV"
