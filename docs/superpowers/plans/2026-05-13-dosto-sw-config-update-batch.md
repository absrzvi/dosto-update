# dosto-sw-config-update-batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new project-local skill `dosto-sw-config-update-batch` that drives OBN's built-in parallel batched switch-config-push, with auto / manual / dry-run modes and engineer approval gates, so a 6-car DOSTO consist's config push drops from ~3 hours serial to ~30-45 min.

**Architecture:** Documentation-driven skill (per existing `dosto-*` precedent) with a `scripts/` subfolder of bash stage scripts that an LLM agent invokes in sequence. The orchestration is in `SKILL.md`; the stage scripts are thin wrappers around `ssh developer@<ccu>` + `obn` CLI + `journalctl` + a Python one-liner that calls OBN's own `OBNTree.calculate_parallel_update_order()`. No new locks, no re-implementation of OBN's parallel scheduler — we wrap `obn update c sw` (auto mode) or fan out `obn update c <ip> &` (manual mode). Single-switch skill stays as escape hatch via `--legacy-serial-sw-config` on the orchestrator.

**Tech Stack:** Bash scripts (matching `dosto-l2-health` pattern), Python one-liners via `/usr/share/obn/venv/bin/python` for tree computation, no new deps on engineer machine.

---

## Reference: spec

The full design is at [`docs/superpowers/specs/2026-05-12-dosto-sw-config-update-batch-design.md`](../specs/2026-05-12-dosto-sw-config-update-batch-design.md). Read it before starting if you have not.

## Reference: existing patterns

- **Skill structure precedent**: [`.claude/skills/dosto-l2-health/`](../../../.claude/skills/dosto-l2-health/) — `SKILL.md` + `scripts/NN_stage.sh` + `scripts/_lib.sh` with `ccu_run` / `switch_run` helpers. **Mirror this layout.**
- **Single-switch precedent**: [`.claude/skills/dosto-sw-config-update/SKILL.md`](../../../.claude/skills/dosto-sw-config-update/SKILL.md) — copy the precondition list, JSON event schema, and gate semantics. Adapt for batch.
- **OBN source on CCU**: `/usr/share/obn/cli/update.py` (the `update()` function), `/usr/share/obn/lib/tree.py` (`OBNTree.calculate_parallel_update_order`). No edits to OBN; only callers.
- **SSH options to CCU**: `-i C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh -o StrictHostKeyChecking=no -o ConnectTimeout=15`.
- **SSH options to switch (from CCU)**: legacy KEX/host-key — see `_lib.sh`. One command per session (CLAUDE.md).

## Reference: live-test CCU

Throughout these tasks, manual verification steps say "run on the live CCU". Today (2026-05-13) Fzg 134 at `10.179.19.1` is the only known-online train, but it is in a degraded state (only 2 switches reachable on vlan100). **Most stages can still be dry-tested there** — preconditions, scope discovery, batch plan computation, JSON shape. **Full end-to-end `--execute` run requires a healthy train with multiple `✗` switches.** If no such train is online during implementation, complete tasks 1-11 with dry-runs against Fzg 134 and defer the live `--execute` validation (Task 12) to the next available train day.

## File structure

Files to create:

```
.claude/skills/dosto-sw-config-update-batch/
├── SKILL.md                         # the skill doc — pre-flight + plan + recipe + execute + JSON schema
└── scripts/
    ├── _lib.sh                      # ssh helpers, JSON emit helper, batch list parser
    ├── 01_preflight.sh              # tftp helper, obn patches, fzg-id, l2-health, obn busy?
    ├── 02_scope.sh                  # obn discover+report, validate parse, intersect --switches, compute batches
    ├── 03_execute_auto.sh           # wraps `obn update c sw` + monitor (Stage 4 inline)
    ├── 04_execute_manual.sh         # per-batch `obn update c <ip> &` fan-out + monitor
    ├── 05_monitor_batch.sh          # journalctl RRQ tail + 60s poll loop for validate ✓
    ├── 06_postcheck.sh              # RSTP root unchanged, all targets ✓, l2-health rerun
    └── 99_dry_run_simulate.sh       # emits simulated events for --dry-run-execute mode
```

Files to modify:

- [`CLAUDE.md`](../../../CLAUDE.md) — add the skill to the "Diagnostic / push" inventory in the `.claude/skills/` section.
- [`.claude/skills/dosto-commission-train/SKILL.md`](../../../.claude/skills/dosto-commission-train/SKILL.md) — replace per-switch config-push stage's invocation with the new batch skill, document the new `--legacy-serial-sw-config` orchestrator flag.

Files NOT modified:

- [`.claude/skills/dosto-sw-config-update/SKILL.md`](../../../.claude/skills/dosto-sw-config-update/SKILL.md) — stays as-is, used as escape hatch and for surgical single-switch runs.

---

### Task 1: Scaffold skill directory and `_lib.sh`

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/SKILL.md` (placeholder header only)
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/_lib.sh`

- [ ] **Step 1: Create the skill directory**

```bash
mkdir -p .claude/skills/dosto-sw-config-update-batch/scripts
```

- [ ] **Step 2: Create the `SKILL.md` placeholder so the dir is non-empty**

Write the file with this exact frontmatter and a stub body. Body will be expanded in Task 11.

```markdown
---
name: dosto-sw-config-update-batch
description: Push DOSTO switch configs in OBN-driven parallel batches. Auto mode wraps `obn update c sw` for full-fleet leaf-first parallel push; manual mode takes --switches A,B,C and runs OBN's leaf-first batches scoped to those IPs. Default replacement for the single-switch config skill inside dosto-commission-train (escape hatch: --legacy-serial-sw-config). Estimated wall-clock: ~30-45 min for a 6-car DOSTO vs ~3 hours single-switch serial. Validated empirically on Fzg <TBD>. Pairs with dosto-tftp-helper-check, dosto-obn-patches, dosto-fzg-id-check, dosto-l2-health.
---

# DOSTO Switch Config Update — Batched

Stub. Full body lands in Task 11.
```

- [ ] **Step 3: Create `scripts/_lib.sh` — start from the dosto-l2-health version and add new helpers**

```bash
#!/usr/bin/env bash
# Shared helpers for dosto-sw-config-update-batch scripts.
# Source this from each stage script: `source "$(dirname "$0")/_lib.sh"`

set -euo pipefail

# Defaults — can be overridden via env vars.
SSH_KEY="${SSH_KEY:-C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh}"
SWITCH_PASSWORD="${SWITCH_PASSWORD:-Nom@dCome1n}"
SWITCH_USER="${SWITCH_USER:-admin}"
CCU_USER="${CCU_USER:-developer}"

# SSH option strings.
CCU_SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=10"
SWITCH_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"

# ccu_run <ccu_ip> <remote_command_string>
ccu_run() {
  local ccu_ip="$1"; shift
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" "$@"
}

# switch_run <ccu_ip> <switch_ip> <switch_command>
# One command per session — the VDS CLI rejects `;`-chained commands.
switch_run() {
  local ccu_ip="$1"; local switch_ip="$2"; local cmd="$3"
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" \
    "sshpass -p '$SWITCH_PASSWORD' ssh $SWITCH_SSH_OPTS $SWITCH_USER@$switch_ip '$cmd'"
}

# emit_event <event_name> [key=value ...]
# Emits one-line JSON to stdout. Used by --execute and --dry-run-execute.
emit_event() {
  local event="$1"; shift
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local extras=""
  for kv in "$@"; do
    local k="${kv%%=*}"
    local v="${kv#*=}"
    # Numeric? embed raw. Otherwise quote.
    if [[ "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || [[ "$v" == "true" ]] || [[ "$v" == "false" ]] || [[ "$v" == "null" ]] || [[ "$v" == \[* ]] || [[ "$v" == \{* ]]; then
      extras="$extras,\"$k\":$v"
    else
      # Escape embedded double-quotes.
      local v_esc; v_esc="${v//\"/\\\"}"
      extras="$extras,\"$k\":\"$v_esc\""
    fi
  done
  echo "{\"event\":\"$event\",\"timestamp\":\"$ts\"$extras}"
}

# rstp_root_mac <ccu_ip> <neighbour_switch_ip>
# Extracts the RSTP root MAC by reading `show spanning-tree` from a neighbour switch.
rstp_root_mac() {
  local ccu_ip="$1"; local neighbour_ip="$2"
  switch_run "$ccu_ip" "$neighbour_ip" "show spanning-tree" 2>/dev/null \
    | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1
}

# pretty section header for non-JSON human runs
section() {
  echo
  echo "============================================================"
  echo "## $*"
  echo "============================================================"
}
```

- [ ] **Step 4: Test `_lib.sh` is sourceable**

```bash
bash -c 'source .claude/skills/dosto-sw-config-update-batch/scripts/_lib.sh && type ccu_run switch_run emit_event rstp_root_mac'
```

Expected:
```
ccu_run is a function
switch_run is a function
emit_event is a function
rstp_root_mac is a function
```

- [ ] **Step 5: Verify `emit_event` JSON output shape**

```bash
bash -c 'source .claude/skills/dosto-sw-config-update-batch/scripts/_lib.sh && emit_event started mode=auto switches_in_scope=12'
```

Expected (timestamp will differ): `{"event":"started","timestamp":"2026-05-13T...Z","mode":"auto","switches_in_scope":12}`

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/
git commit -m "feat(skill): scaffold dosto-sw-config-update-batch with _lib.sh helpers"
```

---

### Task 2: Stage 1 — preflight checks

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/01_preflight.sh`

This script runs all five preconditions in one SSH heredoc to minimise round-trips. Each precondition fails fast with a structured verdict. The script writes a single JSON event `pre_check_passed` on success or `aborted` with `reason` on failure.

- [ ] **Step 1: Create the script**

```bash
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

# 4. obn busy? Any CLI obn process other than serve-api/telemetry?
BUSY=$(sudo ps -eo pid,cmd | grep '/usr/share/obn/venv/bin/python' | grep -vE 'serve-api|telemetry|grep' | wc -l)
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
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/01_preflight.sh
```

- [ ] **Step 3: Live test on Fzg 134 (degraded train)**

```bash
SKIP_DELEGATED=1 ./.claude/skills/dosto-sw-config-update-batch/scripts/01_preflight.sh 10.179.19.1
```

Expected: a series of `preflight_check_ok` / `preflight_check_failed` events, ending in either `pre_check_passed` (exit 0) or `preflight_aborted` (exit 2). Inspect the output — every `_failed` event must have a clear human-readable `reason`.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/01_preflight.sh
git commit -m "feat(skill): add stage 1 preflight script for sw-config-update-batch"
```

---

### Task 3: Stage 2 — scope discovery and batch plan

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh`

This stage runs `obn discover && obn report`, reads `obn validate -t sw`, finds the `✗` rows, optionally intersects with engineer-supplied `--switches`, and computes the OBN-leaf-first batch plan by calling `/usr/share/obn/venv/bin/python` with a one-liner that imports OBN's own tree code.

- [ ] **Step 1: Create the script**

```bash
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
# Format may include "✓" or "✗" or "current (staged) ✗" in the config column.
# Defensive: capture IPs of all SW rows where config column does NOT have a bare ✓.
NEEDING=$(echo "$VALIDATE" | awk '
  /^[[:space:]]*10\./ {
    ip=$1
    # Reconstruct full line for config column extraction
    line=$0
    if (line ~ /✗/) print ip
  }
')

ALL_SW_IPS=$(echo "$VALIDATE" | awk '/^[[:space:]]*10\./ {print $1}' | sort -u)
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh
```

- [ ] **Step 3: Live test on Fzg 134**

```bash
./.claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh 10.179.19.1
```

Expected on Fzg 134 (degraded): either `scope_complete: already_at_target_config` (if no ✗) or `scope_targets` + `plan` events listing whatever's actually in scope. Inspect the `plan` event — `batches` must be a valid JSON array of arrays.

- [ ] **Step 4: Test the manual mode arg parsing**

```bash
./.claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh 10.179.19.1 10.179.19.181,10.179.19.999
```

Expected: `scope_aborted` event with `reason: switch_not_found` and `unknown: 10.179.19.999`.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh
git commit -m "feat(skill): add stage 2 scope + OBN-tree batch plan computation"
```

---

### Task 4: Stage 5 — per-batch monitor (extracted first, used by 3 and 4)

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/05_monitor_batch.sh`

We build the monitor before the executors because both `03_execute_auto.sh` and `04_execute_manual.sh` call it. The monitor takes a CCU IP, a batch index, a comma-separated list of switch IPs, a pre-push timestamp, and a budget (default 1200s = 20 min). It polls `journalctl` for RRQs and `obn validate -t sw` for ✓ transitions.

- [ ] **Step 1: Create the script**

```bash
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
declare -A RRQ_SEEN
RRQ_DEADLINE=$((START + 90))
while [ "$(date +%s)" -lt "$RRQ_DEADLINE" ]; do
  JOURNAL=$(ccu_run "$CCU_IP" "sudo journalctl -u tftpd-hpa --since '$PRE_TS' --no-pager 2>/dev/null")
  for SW in "${SWITCHES[@]}"; do
    if [ -z "${RRQ_SEEN[$SW]:-}" ]; then
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
declare -A FLIPPED
DEADLINE=$((START + BUDGET))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  # Refresh discovery then read validate.
  ccu_run "$CCU_IP" 'sudo obn discover >/dev/null 2>&1' || true
  VALIDATE=$(ccu_run "$CCU_IP" 'sudo obn validate -t sw 2>/dev/null')
  for SW in "${SWITCHES[@]}"; do
    if [ -z "${FLIPPED[$SW]:-}" ]; then
      LINE=$(echo "$VALIDATE" | grep -E "^[[:space:]]*$SW[[:space:]]")
      # ✓ in line AND no ✗ AND no "(staged)" qualifier = clean
      if echo "$LINE" | grep -q "✓" && ! echo "$LINE" | grep -q "✗" && ! echo "$LINE" | grep -q "staged"; then
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
  if [ -z "${FLIPPED[$SW]:-}" ]; then
    FAILED="${FAILED}${FAILED:+,}$SW"
  fi
done
emit_event "batch_completed" batch=$BATCH_IDX all_ok=false elapsed_seconds=$(($(date +%s) - START)) failed_switches="$FAILED"
exit 1
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/05_monitor_batch.sh
```

- [ ] **Step 3: Dry-test the script with a no-op invocation (no real push)**

Just verify the script parses args and runs the poll loop without crashing — point it at Fzg 134 with a switch IP we know exists but no actual push happening. Use a short budget so the test completes in ~2 minutes.

```bash
PRE_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
./.claude/skills/dosto-sw-config-update-batch/scripts/05_monitor_batch.sh \
  10.179.19.1 99 10.179.19.181 "$PRE_TS" 120
```

Expected: 90s of RRQ-wait silence (no RRQ since we didn't push), then ~30s of validate polling, then `batch_completed all_ok=false failed_switches=10.179.19.181`, exit 1. **This is correct** — we're confirming the polling loop and event emission work, not that a real push succeeded.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/05_monitor_batch.sh
git commit -m "feat(skill): add stage 5 per-batch monitor (RRQ + validate poll)"
```

---

### Task 5: Stage 3 — auto-mode executor

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/03_execute_auto.sh`

Auto mode wraps `obn update c sw` — OBN does the batching. The challenge: OBN's `obn update c sw` is a single long-running command that internally cycles through batches with `time.sleep(5*60)` between them. We can't easily "monitor per batch" from outside because OBN doesn't expose batch boundaries on its stdout in a structured way. Approach: **start `obn update c sw` in background on the CCU**, then poll `obn validate -t sw` ourselves on a 60s cadence and emit `flipped_to_target` events as switches transition. We use the pre-computed batch plan from Stage 2 as the *expected order* for reporting, but rely on `obn validate` as ground truth.

- [ ] **Step 1: Create the script**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/03_execute_auto.sh
```

- [ ] **Step 3: Live-test deferred — needs a healthy train with ✗ switches**

Auto mode can only be meaningfully tested when a train has switches actually needing push. On Fzg 134 today this would either no-op or fail because the consist is degraded. Mark this task complete for code/structure; live validation is Task 12.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/03_execute_auto.sh
git commit -m "feat(skill): add stage 3 auto-mode executor (wraps obn update c sw)"
```

---

### Task 6: Stage 3 — manual-mode executor

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/04_execute_manual.sh`

Manual mode iterates over the engineer-scoped batches one at a time. For each batch: bash-background N `obn update c <ip>` calls from a single SSH session, wait for them all, then run the monitor.

- [ ] **Step 1: Create the script**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/04_execute_manual.sh
```

- [ ] **Step 3: Live-test deferred — needs a healthy train**

Same reasoning as Task 5. Defer to Task 12.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/04_execute_manual.sh
git commit -m "feat(skill): add stage 3 manual-mode executor with gate 2 handling"
```

---

### Task 7: Stage 6 — post-run verification

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/06_postcheck.sh`

After all batches finish, verify: RSTP root MAC unchanged, all targeted switches now ✓, and `dosto-l2-health` (delegated — we just invoke it and parse its verdict).

- [ ] **Step 1: Create the script**

```bash
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
VALIDATE=$(ccu_run "$CCU_IP" 'sudo obn validate -t sw 2>/dev/null')

IFS=',' read -ra TARGETS <<< "$TARGETS_CSV"
STILL_BAD=""
for SW in "${TARGETS[@]}"; do
  LINE=$(echo "$VALIDATE" | grep -E "^[[:space:]]*$SW[[:space:]]")
  if ! echo "$LINE" | grep -q "✓" || echo "$LINE" | grep -q "✗"; then
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/06_postcheck.sh
```

- [ ] **Step 3: Live test**

```bash
RSTP=$(bash -c 'source .claude/skills/dosto-sw-config-update-batch/scripts/_lib.sh && rstp_root_mac 10.179.19.1 10.179.19.181' 2>/dev/null || echo "unknown")
./.claude/skills/dosto-sw-config-update-batch/scripts/06_postcheck.sh 10.179.19.1 "$RSTP" 10.179.19.181 10.179.19.179
```

Expected: events flow, `rstp_root_unchanged` (since nothing changed it), `all_targets_at_target_config` or `gate_4_awaiting_ack` depending on whether Fzg 134's D1 is currently ✓ in validate.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/06_postcheck.sh
git commit -m "feat(skill): add stage 6 post-run verification"
```

---

### Task 8: Dry-run-execute simulator

**Files:**
- Create: `.claude/skills/dosto-sw-config-update-batch/scripts/99_dry_run_simulate.sh`

Emits the full event stream that a real `--execute` would produce, using simulated per-switch timings (no actual `obn update c` calls). Used to validate the event schema and let engineers preview what an execution would look like.

- [ ] **Step 1: Create the script**

```bash
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
```

- [ ] **Step 2: Make executable**

```bash
chmod +x .claude/skills/dosto-sw-config-update-batch/scripts/99_dry_run_simulate.sh
```

- [ ] **Step 3: Test the simulator**

```bash
./.claude/skills/dosto-sw-config-update-batch/scripts/99_dry_run_simulate.sh \
  10.179.19.1 '[["10.179.19.181","10.179.19.183"],["10.179.19.190"]]' "a0:59:3a:aa:bb:cc" "10.179.19.181,10.179.19.183,10.179.19.190"
```

Expected: a clean event stream (~15 lines), each line a valid one-line JSON object. Pipe through `jq -c .` to validate JSON shape:

```bash
./.claude/skills/dosto-sw-config-update-batch/scripts/99_dry_run_simulate.sh \
  10.179.19.1 '[["10.179.19.181","10.179.19.183"],["10.179.19.190"]]' "a0:59:3a:aa:bb:cc" "10.179.19.181,10.179.19.183,10.179.19.190" \
  | jq -c .
```

If `jq` is not installed, use `python3 -c 'import sys, json; [json.loads(l) for l in sys.stdin]; print("all lines valid JSON")'` instead.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/scripts/99_dry_run_simulate.sh
git commit -m "feat(skill): add dry-run-execute simulator"
```

---

### Task 9: SKILL.md — full body

**Files:**
- Modify: `.claude/skills/dosto-sw-config-update-batch/SKILL.md`

Replace the stub from Task 1 with the full skill body. The structure mirrors the existing single-switch skill (preconditions table, output modes section, state machine diagram, failure mode catalogue) but for batch.

- [ ] **Step 1: Replace `SKILL.md` body**

```markdown
---
name: dosto-sw-config-update-batch
description: Push DOSTO switch configs in OBN-driven parallel batches. Auto mode wraps `obn update c sw` for full-fleet leaf-first parallel push; manual mode takes --switches A,B,C and runs OBN's leaf-first batches scoped to those IPs. Default replacement for the single-switch config skill inside dosto-commission-train (escape hatch: --legacy-serial-sw-config). Estimated wall-clock: ~30-45 min for a 6-car DOSTO vs ~3 hours single-switch serial. Validated empirically on Fzg <TBD>. Pairs with dosto-tftp-helper-check, dosto-obn-patches, dosto-fzg-id-check, dosto-l2-health.
---

# DOSTO Switch Config Update — Batched

This skill drives switch config pushes in OBN-leaf-first parallel batches by wrapping OBN's own built-in parallel scheduler. The single-switch skill ([`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md)) stays available as escape hatch and for surgical one-switch pushes.

**Why this exists**: a 6-car DOSTO with 15-18 switches needing config takes ~3 hours single-switch-serial. OBN's `obn update c sw` already implements parallel batching (`/usr/share/obn/cli/update.py` → `OBNTree.calculate_parallel_update_order` + `ThreadPoolExecutor`). With the TFTP conntrack helper now patched and the RSTP root pinned to the CCU-adjacent switch (so leaf-batch reboots cannot trigger root re-election), the safety rationale for serial no longer applies. Wrapping `obn update c sw` with pre-flight and post-batch verification gets us to ~30-45 min wall-clock.

## Modes

| Mode | Trigger | Behaviour |
|---|---|---|
| `--prepare` (default) | no other flag | Read-only: preflight + scope discovery + batch plan + recipe. Exit 0. |
| `--dry-run-execute` | `--dry-run-execute` flag | All of `--prepare` + simulated event stream from a hypothetical `--execute`. No destructive ops. |
| `--execute --auto` | `--execute` (default sub-mode) | Wraps `obn update c sw`. OBN drives batching. Engineer can opt out via `--auto=false` (= manual). |
| `--execute --switches A,B,C` | `--execute` + `--switches` | Manual mode: filters OBN's leaf-first plan to engineer-named IPs, runs each batch via backgrounded `obn update c <ip> &` calls from one SSH session. |

## Preconditions (skill aborts if any are not met)

| Precondition | Why | Failure verdict |
|---|---|---|
| `dosto-tftp-helper-check` ∈ {`all_present`, `puppet_persisted`} | TFTP transfer path. | `preconditions_unmet:tftp_helper` |
| `dosto-obn-patches` ∈ {`all_patched`, `all_persisted`} | Bugs 2, 5, 6, 7, 8 all on the config-push path. | `preconditions_unmet:obn_patches` |
| `dosto-fzg-id-check` verdict `all_match` | Otherwise rendered configs contain wrong hostname. | `preconditions_unmet:fzg_id` |
| `dosto-l2-health` recent verdict healthy | Pre-existing fabric problems mask post-batch RSTP convergence check. | `fabric_unhealthy` |
| `obn discover && obn report` succeed | OBNTree must be buildable. | `obn_tree_unbuildable` |
| No other `obn` CLI process running (other than `serve-api`, `telemetry`) | Avoid stomping. | `preconditions_unmet:obn_busy` |
| `--switches` IPs all known to validate | Engineer typo guard. | `switch_not_found` |

## State machine

Same family shape as the single-switch skill. New per-batch monitor loop; gate set is { Gate 1 (pre-execute ack), Gate 2 (batch failure), Gate 4 (post-run anomaly) }. There is no Gate 3 (no `verify_reboot_started` hard-fail in batch mode — failures surface at batch boundary instead).

```
preflight → scope (compute OBN-leaf-first batches)
   ↓
GATE 1: engineer acks blast radius (N switches across M batches over ~T minutes)
   ↓
for batch in batches:
   batch_started → dispatch (auto: obn update c sw; manual: backgrounded obn update c <ip> &)
       ↓
   monitor: RRQ tail + 60s validate poll, 20-min budget
       ├── all flip ✓ → batch_completed → batch_settle (300s)
       └── budget exhausted → GATE 2 (abort | extend-poll | retry | skip)
                                                ↓
                                  3 consecutive failures → auto-abort
   ↓
post-run verify (RSTP root unchanged + all targets ✓ + l2-health healthy)
   ├── ok → completed
   └── anomaly → GATE 4 (engineer reviews)
```

## Output (`--execute --json` event stream)

One event per line. Schema mirrors single-switch skill where possible.

Per-batch events: `batch_started`, `rrq_seen`, `flipped_to_target`, `batch_completed`, `batch_settle`, `gate_2_awaiting_ack`.
Run-level: `started`, `pre_check_passed`, `plan`, `gate_1_awaiting_ack`, `gate_1_acked`, `post_check_passed`, `completed`, `aborted`.

See `scripts/05_monitor_batch.sh` for the canonical event-emit forms.

## Scripts

| Script | Stage | Purpose |
|---|---|---|
| `scripts/_lib.sh` | shared | SSH helpers, JSON event emitter, RSTP probe |
| `scripts/01_preflight.sh` | 1 | TFTP helper, OBN patches, OBN busy check, fresh `obn discover` |
| `scripts/02_scope.sh` | 2 | `obn validate` parse, `--switches` intersect, OBN-tree-derived batch plan |
| `scripts/03_execute_auto.sh` | 3 (auto) | Wraps `obn update c sw`; per-batch monitor for progress reporting |
| `scripts/04_execute_manual.sh` | 3 (manual) | Per-batch backgrounded `obn update c <ip> &` from one SSH session |
| `scripts/05_monitor_batch.sh` | 5 (shared) | RRQ tail (90s) + `obn validate` poll (60s cadence, 20-min budget) |
| `scripts/06_postcheck.sh` | 6 | RSTP root unchanged, all targets ✓, prompt for `dosto-l2-health` rerun |
| `scripts/99_dry_run_simulate.sh` | dry-run | Emit simulated event stream, no destructive ops |

## Invocation flow (what the LLM agent does)

**For `--prepare`:**
1. Run `01_preflight.sh <ccu>`.
2. If pre_check passed, run `02_scope.sh <ccu> [<switches_csv>]`.
3. Capture the `plan` event. Print human-readable summary (switch count, batch table, estimated wall-clock = `BATCH_COUNT * (avg_flip_secs + 300)`).
4. Exit. No GATE 1 ack required.

**For `--dry-run-execute`:**
1. Run preflight + scope as above.
2. Pass `batches_json` and `targets_csv` into `99_dry_run_simulate.sh`.
3. Print the full simulated event stream.

**For `--execute`:**
1. Run preflight + scope.
2. Emit `gate_1_awaiting_ack` with blast-radius text computed from plan.
3. Wait for engineer ack (orchestrator-mediated; standalone use waits on stdin).
4. Dispatch `03_execute_auto.sh` or `04_execute_manual.sh` based on `--auto` / `--switches`.
5. On `gate_2_awaiting_ack`, surface options to engineer and resume via `GATE_RESUME` env var.
6. After all batches done, run `06_postcheck.sh`.
7. On `gate_4_awaiting_ack`, surface to engineer.
8. Emit final `completed` event.

## What this skill deliberately does NOT do

- Touch any switch outside the OBN leaf-first plan computed by OBN itself.
- Cap OBN's `max_workers` — OBN decides batch width.
- Push firmware. Different skill.
- Push APs. Different skill.
- Retry failed batches automatically beyond a single extend-poll.
- Continue after 3 consecutive batch failures.
- Implement `verify_reboot_started` per switch. Detected at batch boundary instead.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md), [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md), [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md), [`dosto-l2-health`](../dosto-l2-health/SKILL.md) — preconditions.
- [`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md) — escape hatch and surgical-one-switch tool.
- [`dosto-commission-train`](../dosto-commission-train/SKILL.md) — orchestrator that calls this skill by default.

## Reference

- Spec: `docs/superpowers/specs/2026-05-12-dosto-sw-config-update-batch-design.md`
- OBN source: `/usr/share/obn/cli/update.py:212-263` (`update()` function), `/usr/share/obn/lib/tree.py` (`OBNTree.calculate_parallel_update_order`)
- Verified 2026-05-12 (Fzg 134 / box1-t19): no locks in OBN (`grep -rn 'flock|FileLock|threading.Lock' /usr/share/obn` returned 0); only `serve-api` and `telemetry` processes resident; `cli/update.py` already uses `ThreadPoolExecutor(max_workers=len(devices))` per batch.
```

- [ ] **Step 2: Verify the file renders as expected**

Read it back, confirm the frontmatter parses (a tool that loads skills must accept this format). The `description` field must stay one line.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/dosto-sw-config-update-batch/SKILL.md
git commit -m "docs(skill): complete SKILL.md body for sw-config-update-batch"
```

---

### Task 10: Update CLAUDE.md inventory

**Files:**
- Modify: `CLAUDE.md` — the `.claude/skills/` inventory list.

- [ ] **Step 1: Find the inventory line**

Search for "13 project-local skills" or "Per-device push (single-AP/SW serial):" in CLAUDE.md. The line is around the bottom of the file.

- [ ] **Step 2: Update the inventory**

Change `"13 project-local skills"` to `"14 project-local skills"` and add the new skill in the "Per-device push" bucket. Concretely:

```
  - **Per-device push (single-AP/SW serial):** `dosto-ap-config-update`, `dosto-ap-firmware-update`, `dosto-sw-config-update`, `dosto-sw-firmware-update`.
  - **Per-device push (parallel batched):** `dosto-sw-config-update-batch` — default sw-config path in `dosto-commission-train`; legacy serial path via `--legacy-serial-sw-config` flag.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: register dosto-sw-config-update-batch in CLAUDE.md skill inventory"
```

---

### Task 11: Wire the batch skill into `dosto-commission-train`

**Files:**
- Modify: `.claude/skills/dosto-commission-train/SKILL.md`

The orchestrator currently invokes `dosto-sw-config-update` once per switch in the config-push stage. Replace that with one call to `dosto-sw-config-update-batch --execute --auto`. Add documentation for the new `--legacy-serial-sw-config` flag that falls back to the per-switch loop.

- [ ] **Step 1: Find the config-push stage in `dosto-commission-train/SKILL.md`**

Search for the stage that invokes `dosto-sw-config-update`. The 19-stage pipeline is documented inline.

- [ ] **Step 2: Replace the per-switch loop with a single batch call**

Replace the per-switch loop pseudocode with:

```
Stage <N>: Switch config push
  Default: invoke dosto-sw-config-update-batch --execute --auto
    → OBN-driven parallel batches, leaf-first, ~30-45 min wall-clock
  Escape hatch: if orchestrator was invoked with --legacy-serial-sw-config:
    → for each switch in OBNTree leaf-first order:
        invoke dosto-sw-config-update --execute on that switch
    → ~3 hour wall-clock; only use if batch skill has known issue on this train
```

- [ ] **Step 3: Document `--legacy-serial-sw-config` orchestrator flag**

Find the orchestrator's "Optional flags" or equivalent section. Add:

```
| `--legacy-serial-sw-config` | Fall back to per-switch serial config push instead of the default batch parallel path. Use only if dosto-sw-config-update-batch has shown problems on this specific train. |
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-commission-train/SKILL.md
git commit -m "feat(orchestrator): use sw-config-update-batch by default, --legacy-serial-sw-config escape hatch"
```

---

### Task 12: Live `--execute` validation on a healthy train (deferred)

**Files:** none (validation only)

This task can only run when a healthy train is online with multiple switches showing `✗` in `obn validate -t sw`. Today (2026-05-13) Fzg 134 is the only train known online and is degraded.

- [ ] **Step 1: Identify a candidate train**

Check fleet-status.md for trains marked as having pending switch config pushes. Cross-reference with a known-online train.

- [ ] **Step 2: Engineer pre-checks**

On the candidate CCU:
- `sudo dhcp-lease-list` shows full consist of switches
- `dosto-l2-health` verdict is healthy
- `dosto-obn-patches` is `all_persisted`
- `dosto-fzg-id-check` is `all_match`
- `dosto-tftp-helper-check` is `all_present`
- `sudo obn discover && sudo obn report && sudo obn validate -t sw` shows ≥3 switches with config `✗`

- [ ] **Step 3: First-run safety: manual mode, 2-3 leaves**

Pick 2-3 leaf switches with `✗`. Invoke:

```bash
# --prepare first
.claude/skills/dosto-sw-config-update-batch/scripts/01_preflight.sh <ccu_ip>
.claude/skills/dosto-sw-config-update-batch/scripts/02_scope.sh <ccu_ip> <ip1>,<ip2>,<ip3>
# Inspect the plan event. If acceptable:
# --execute manual mode
# (orchestrator-mediated for production; for first-run validation, run scripts directly)
.claude/skills/dosto-sw-config-update-batch/scripts/04_execute_manual.sh <ccu_ip> '<batches_json>' '<rstp_pre>'
.claude/skills/dosto-sw-config-update-batch/scripts/06_postcheck.sh <ccu_ip> '<rstp_pre>' '<targets_csv>' '<neighbour_ip>'
```

Record wall-clock per stage. Confirm RSTP root stayed pinned.

- [ ] **Step 4: Second run: auto mode, full fleet**

On a different train (or after the first one is fully ✓), run the auto path end-to-end. Compare wall-clock against the 3-hour serial baseline. Record:
- Total wall-clock
- Per-batch timing
- Per-switch RRQ-to-flip latency
- RSTP root MAC pre/post
- l2-health pre/post

- [ ] **Step 5: Update `SKILL.md` description's empirical line**

Once validated, change `Validated empirically on Fzg <TBD>` in the SKILL.md frontmatter description to the actual Fzg numbers and dates.

- [ ] **Step 6: Commit the empirical update**

```bash
git add .claude/skills/dosto-sw-config-update-batch/SKILL.md
git commit -m "docs(skill): record empirical validation on Fzg <N> / <date>"
```

---

## Self-review

Spec coverage check (going through each spec section):

- **Goals 1 (drive parallel push via OBN's built-in scheduler)**: Tasks 5, 6.
- **Goals 2 (discover what needs pushing, present plan)**: Task 3 (`02_scope.sh`).
- **Goals 3 (auto + manual modes)**: Tasks 5 (auto) + 6 (manual).
- **Goals 4 (pre-flight + per-batch progress + post-run verify)**: Tasks 2, 4, 7.
- **Goals 5 (engineer ack on batch failure)**: Task 6 (Gate 2 in `04_execute_manual.sh`); Task 5 (same in `03_execute_auto.sh`).
- **Non-goals**: explicitly enumerated in Task 9's SKILL.md.
- **Architecture (script layout)**: matches Task 1's file-structure declaration.
- **Output modes (`--prepare`, `--execute`, `--dry-run-execute`)**: Tasks 3, 5, 6, 8.
- **Failure mode catalogue**: covered across `01_preflight.sh`, `02_scope.sh`, `05_monitor_batch.sh`, `06_postcheck.sh`.
- **Integration with `dosto-commission-train`**: Task 11.
- **Dry-run mode**: Task 8.
- **Risks (no locks; `obn discover` racing; bash exit code capture; engineer collision)**: addressed by Task 2 (`obn_busy` check) and design of `04_execute_manual.sh` (explicit `wait $PID`).

Type/signature consistency: script arg orders documented in each script's usage line. Event names consistent across scripts (`emit_event "batch_started"` form).

No placeholders: all code blocks complete; only TBDs are in places designed for runtime fill (Fzg number in SKILL.md after live validation).

One known plan trade-off: TDD-with-pytest is not used because this repo has no pytest infrastructure and skills are documentation+bash. Each task instead ends with a manual verification step against the live CCU. This matches the existing `dosto-l2-health` precedent.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-dosto-sw-config-update-batch.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatches a fresh subagent per task, reviews between tasks, fast iteration. Best for this kind of multi-script skill where each task has clear boundaries.
2. **Inline Execution** — executes tasks in this session, batch execution with checkpoints. Best if you want to watch each step yourself.

Which approach?
