---
name: dosto-sw-config-update
description: Push a VDS Rail Consist Switch config via OBN's `obn update c <switch-ip>`. Use when pushing config to one consist switch, when an engineer says "obn update c", or when a commissioning stage needs leaf-first switch config rollout. Sequences leaf-first per OBNTree, single-switch-at-a-time. Config push always reboots the switch — that's how OBN persists the new config (TFTP → running-config, then SNMP reboot OID flushes running → startup as part of orderly shutdown). If the switch doesn't reboot within 60s of RRQ, the push didn't take — hard fail. Verifies completion via SNMP through the reboot window plus RSTP convergence check from a neighbour switch. Validation surface for OBN Bugs 2b, 7, and 8 — all exercised cleanly on Fzg 132 / 2026-05-09. Default --prepare mode is read-only diagnostic + recipe print; --execute mode drives one switch through the full push, stopping at gates. Pairs with dosto-tftp-helper-check, dosto-obn-patches, dosto-l2-health.
---

# DOSTO Switch Config Update

This skill pushes config to a single VDS Rail Consist Switch via OBN's `obn update c <switch-ip>` flow. Same single-switch-serial discipline, same OBNTree leaf-first ordering constraint, and same RSTP convergence safety net as [`dosto-sw-firmware-update`](../dosto-sw-firmware-update/SKILL.md), with one key behavioural difference: config push **always triggers a reboot**, and the absence of reboot is itself a failure signal.

This is **switch config push only**. Switch firmware is [`dosto-sw-firmware-update`](../dosto-sw-firmware-update/SKILL.md).

## How OBN's config push actually persists changes

`obn update c <switch-ip>` does **not** call `save running-config` or any CLI command. The flow is:

1. **TFTP transfer**: OBN copies the rendered `dostoneu-obn-<switchmac>.cfg` to the switch via TFTP (handoff lesson 17 — `journalctl -u tftpd-hpa` is the source of truth that this transfer happened).
2. **Auto-apply**: VDS Rail switches automatically apply a TFTP'd config to running-config on receipt (vendor behaviour, analogous to Westermo APs auto-staging LuCI flashops).
3. **SNMP reboot OID**: OBN's `vdsrail.py reboot()` sets the SNMP reboot OID to value `3`. The switch reboots as a result.
4. **Implicit persistence**: VDS Rail switches flush running-config to startup-config as part of orderly SNMP-triggered shutdown — this is what makes the config survive the reboot. There is **no explicit save step**.

Implication: **the reboot is what persists the new config**. If a config push lands via TFTP but the switch doesn't subsequently reboot, the new config exists in running-config but won't survive a power cycle, and worse, the SNMP reboot OID set didn't fire — meaning OBN's polling loop will never see the post-reboot hostname signal it expects. This is a hard fault, not a soft one.

The skill's `verify_reboot_started` stage (described below) enforces this: if ICMP doesn't drop within 60s of RRQ, the push didn't really apply and the skill aborts.

## Why this skill matters for OBN patch validation

Bugs 2b (`vdsrail.py` config-side polling None guard), 7 (`vdsrail.py` reboot hostname guard), and 8 (`device.py` config None guard) all fire on this code path and have been **exercised cleanly on a real consist** (handoff line 195 — F2 / `10.179.10.189` on Fzg 132 / 2026-05-09 — config TFTP + reboot + post-reboot SNMP polling completed cleanly, all neighbours restored). This skill's preconditions verify those three patches are active, but unlike `dosto-sw-firmware-update` (which is the validation surface for the still-unproven Bug 1 + 2a), this skill's job is everyday operations, not patch validation.

## When to use

- **Step 9 of [train-login-checklist.md](../../../train-login-checklist.md)** — after switch firmware update. Config last because firmware updates can reset config to defaults.
- **One switch at a time, in OBNTree leaf-first order** — same single-switch-serial discipline as the other firmware/config update skills.
- **When `obn validate -t sw` shows a `✗` in the config column** — that switch needs config push (the validate cache may be up to 5 min stale; force fresh with `sudo obn discover` first).
- **After a hostname-rebrand** triggered by `dosto-fzg-id-check` re-rendering on an existing train (templates change → switches need re-push to pick up new `train_id`).
- **After a switch firmware update** — some firmware updates reset config to defaults; this skill restores the rendered Nomad config.
- **Never on more than one switch at a time, never on a non-leaf without explicit override.** Same OBNTree leaf-first correctness constraint as `dosto-sw-firmware-update`.

## Preconditions (skill aborts if any are not met)

Same shape as `dosto-sw-firmware-update`, with the OBN bug priority list reordered for the config-push code path:

| Precondition | Why | Failure verdict |
|---|---|---|
| `dosto-tftp-helper-check` ∈ {`all_present`, `puppet_persisted`} | Config files transfer via TFTP through the same conntrack path. Without the helper, single-switch pushes silently fail at the data-return-flow stage. | `preconditions_unmet:tftp_helper` 🔴 |
| `dosto-obn-patches` ∈ {`all_patched`, `all_persisted`} | Bug 2b (config-side None guard), Bug 5 (TFTP ipset), Bug 6 (cross-consist tree guard), Bug 7 (reboot hostname guard), Bug 8 (report config None guard) — all required for this path. Bugs 1, 2a (firmware-only) not strictly required, but full 8/8 keeps the surface clean. | `preconditions_unmet:obn_patches` 🔴 |
| `dosto-l2-health` recent verdict is healthy | Pre-existing fabric problems mask the post-reboot RSTP convergence check. | `fabric_unhealthy` 🔴 |
| `obn discover` succeeded recently — OBNTree is buildable | Bug 6 patch must be applied if any neighbour consist is coupled. | `obn_tree_unbuildable` 🔴 |
| Rendered config file `/data/auto-topology/upload/dostoneu-obn-<switchmac>.cfg` exists on CCU | OBN renders these during any `obn update c` attempt. If missing, render with `sudo obn update c <ip>` once (success or failure both render). | `config_file_missing` 🔴 |
| Switch IP is in `dhcp-lease-list` (not stale ARP) | Confirms the switch is alive and addressable. DHCP leases on this fleet are 2-min. | `switch_not_found` 🔴 |
| Switch MAC OUI is `a0:59:3a` | Confirms it's a VDS Rail Consist Switch, not an AP (`00:14:5a`) or Stadler device. | `switch_not_found` 🔴 |
| Switch is a **leaf** of OBNTree, OR engineer passed `--allow-non-leaf` | Pushing to a parent before children isolates the children mid-reboot. Default-deny. | `non_leaf_switch` 🔴 |
| Single switch only — no batch glob | Argument parser. | error before any SSH |

## OBNTree leaf-first sequencing

Same as `dosto-sw-firmware-update`. Topology on a 6-car DOSTO is a chain-of-stars:

```
A1 ─ A2 ─ A3 ── B1 ─ B2 ─ B3 ── C1 ─ C2 ─ C3 ── D1 ─ D2 ─ D3 ── E1 ─ E2 ─ E3 ── F1 ─ F2 ─ F3
```

A switch is a leaf if no other switch in OBNTree lists it as a parent. Push leaves (A1, A3, B1, B3, …, F1, F3) first, then per-coach centres (A2, B2, …, F2) with `--allow-non-leaf`, then the root last.

## Output modes

The skill has **two execution modes** plus the standard `--json` formatter switch — same family shape.

- **`--prepare` (default) — read-only.** Verify preconditions, capture live state, run leaf check, print the equivalent shell recipe. No CCU writes, no switch changes.
- **`--execute` (opt-in) — autonomous driver.** Drives one switch through the full state machine, stopping at four explicit approval gates for irreversible actions.

Both modes support `--json`. In `--execute`, JSON is streamed one event per line.

### Optional flags

| Flag | Effect |
|---|---|
| `--allow-non-leaf` | Override the leaf-only precondition. Use only when all children of this switch are already at target config. Required for pushing per-coach centres and the tree root. |

### `--prepare` `--json` shape

```json
{
  "skill": "dosto-sw-config-update",
  "mode": "prepare",
  "schema_version": "1",
  "verdict": "ready_to_push|already_at_target_config|partial_apply_detected|preconditions_unmet|switch_not_found|non_leaf_switch|fabric_unhealthy|obn_tree_unbuildable|config_file_missing",
  "raw": {
    "ccu_ip": "10.179.10.1",
    "switch_ip": "10.179.10.189",
    "switch_mac": "a0:59:3a:01:23:45",
    "switch_mac_slug": "a0593a012345",
    "switch_hostname": "nv6-F2-v8-132",
    "switch_role": "F2",
    "config_file_path": "/data/auto-topology/upload/dostoneu-obn-a0593a012345.cfg",
    "config_file_exists": true,
    "config_file_mtime": "2026-05-09T11:13:42Z",
    "config_file_size_bytes": 4823,
    "obn_validate_config_state": "x|✓|null",
    "is_leaf": true,
    "downstream_peers": [],
    "upstream_peer": "10.179.10.190",
    "obn_patches_verdict": "all_persisted",
    "tftp_helper_verdict": "all_present",
    "l2_health_recent_verdict": "healthy",
    "rstp_root_mac_pre": "a0:59:3a:aa:bb:cc",
    "stp_state": "Forwarding",
    "trunk_neighbours_visible": true,
    "fix_obn_bug2b_active": true,
    "fix_obn_bug5_active": true,
    "fix_obn_bug6_active": true,
    "fix_obn_bug7_active": true,
    "fix_obn_bug8_active": true,
    "ipset_tftp_allowed_has_switch": true
  },
  "recipe": "..."
}
```

`verdict` semantics:

- `ready_to_push` ✅ — preconditions all green, switch is a leaf (or override), config column shows `✗`. Standard fresh push path.
- `already_at_target_config` ✅ — `obn validate -t sw` config column shows `✓` AND no fresh render is pending. No-op.
- `partial_apply_detected` 🟡 — `current (staged) ✗` form on the config column. Rare on switches (the auto-apply path is usually atomic), but if seen, force-reboot resolves it. Likely indicates a previous push where TFTP landed but the SNMP reboot OID didn't fire.
- `non_leaf_switch` 🔴 — engineer must pass `--allow-non-leaf` if intentional.
- `fabric_unhealthy` 🔴 — `dosto-l2-health` reports problems. Engineer fixes fabric first.
- `obn_tree_unbuildable` 🔴 — `obn discover` failed or returned partial data. Bug 6 patch may be missing.
- `switch_not_found` 🔴 — wrong IP / wrong train / not a VDS switch.
- `config_file_missing` 🔴 — recipe says "run `sudo obn update c <ip>` once on CCU to render, then re-invoke."
- `preconditions_unmet` 🔴 — TFTP helper or OBN patches not in good state.

`recipe` is non-null whenever verdict ∈ {`ready_to_push`, `partial_apply_detected`}.

### `--execute` `--json` event stream

Same one-event-per-line format as the firmware skills. New event `verify_reboot_started` between `rrq_seen` and `polling_completion`:

```json
{"event":"started","timestamp":"...","switch_ip":"10.179.10.189","switch_role":"F2"}
{"event":"pre_check_passed","timestamp":"...","is_leaf":true,"l2_health":"healthy","rstp_root_mac_pre":"a0:59:3a:aa:bb:cc","config_file_size":4823}
{"event":"gate_1_awaiting_ack","timestamp":"...","action":"obn update c 10.179.10.189","blast_radius":"this switch will reboot 60-90s after config TFTP; RSTP will recalculate; downstream peers: []"}
{"event":"gate_1_acked","timestamp":"..."}
{"event":"push_command_returned","timestamp":"...","obn_says":"...","push_command_exit":0}
{"event":"rrq_seen","timestamp":"...","journalctl_line":"in.tftpd: RRQ from 10.179.10.189 filename dostoneu-obn-..."}
{"event":"verify_reboot_started","timestamp":"...","outcome":"down","seconds_since_rrq":24}
{"event":"polling_completion","timestamp":"...","poll_count":2,"icmp_state":"down","elapsed_seconds":180}
{"event":"switch_returned","timestamp":"...","seconds_since_push":92,"icmp_state":"up"}
{"event":"snmp_verify_post_reboot_ok","timestamp":"...","sysDescr":"...","config_state":"✓"}
{"event":"rstp_convergence_check","timestamp":"...","root_mac_post":"a0:59:3a:aa:bb:cc","root_changed":false,"all_links_forwarding":true,"convergence_seconds":12}
{"event":"completed","timestamp":"...","total_elapsed_seconds":156,"final":true}
```

Failure-mode events:
- `gate_2_awaiting_ack` — no RRQ within 90s. Engineer must approve switch SSH-reboot recovery (legacy SSH options).
- **`aborted: config_did_not_trigger_reboot`** — RRQ seen but switch stayed UP for 60s after. **No engineer ack option** — this is a hard fail because the SNMP reboot OID didn't fire and the new config won't persist a power cycle. Skill captures full diagnostic context (OBN stdout/stderr, switch's `show running-config` first 50 lines via SSH, `mtime` of the rendered cfg) and exits.
- `gate_3_awaiting_ack` — 20-min poll exhausted. Engineer chooses force-reboot via SSH, abort, or extend-poll.
- `gate_4_awaiting_ack` — RSTP root changed during reboot, or some links not forwarding. Engineer reviews.
- `aborted` — terminal failure with `final: true` and `reason` field.

## The state machine

```
                ┌──────────────────────────────┐
                │  pre_check (fabric + tree)   │
                └──────────────┬───────────────┘
                               │
            preconditions OK   ▼
                ┌──────────────────────┐         GATE 1
                │         push         │◄────  engineer acks (with explicit blast-radius
                └──────────────┬───────┘                       message: switch will reboot,
                               │                                RSTP recalc, downstream peers)
              `obn update c`   │
              returned         ▼
                ┌──────────────────────┐
                │     verify_rrq       │  poll journalctl every 5s for 90s
                └──┬─────────────────┬─┘
        RRQ seen   │                 │   no RRQ in 90s
                   │                 └────► GATE 2 (engineer ack: SSH-reboot via legacy
                   │                              SSH options, retry the push exactly once)
                   ▼
            ┌──────────────────────────┐
            │ verify_reboot_started    │  ICMP-monitor for 60s after RRQ
            └──┬──────────────────────┬┘
   switch DOWN │                      │  switch stayed UP for 60s
   in window   │                      │
               │                      └────► aborted:
               │                              config_did_not_trigger_reboot
               │                              (HARD FAIL — no engineer ack)
               ▼
            ┌──────────────────────────┐
            │   poll_completion +      │  20-min budget, 90s cadence
            │   reboot_detection       │
            └──┬──────────────────────┬┘
   target seen │                      │  20 min elapsed
   AND switch  │                      │
   returned    │                      └────► GATE 3 (force-reboot / extend-poll / abort)
               ▼
        ┌──────────────────────────┐
        │  rstp_convergence_check  │  Compare RSTP root MAC pre vs post,
        └──┬──────────────────────┬┘  all neighbour links FWD
   stable   │                      │   root changed OR links not all forwarding
            │                      │
            │                      └────► GATE 4 (engineer reviews; may need
            │                                     `dosto-l2-health` rerun)
            ▼
        ┌──────────────┐
        │ verify_done  │  one final `obn discover` + `obn validate -t sw`
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │   completed  │  (final: true)
        └──────────────┘
```

### Stage details

Stages mirror `dosto-sw-firmware-update` closely. The only structural addition is `verify_reboot_started`, described in detail below.

**`pre_check`** — Run all preconditions in one SSH heredoc to the CCU. Includes the SSH-into-a-neighbouring-switch step to capture the **pre-push RSTP root MAC** for later comparison. Also confirms the rendered `dostoneu-obn-<mac>.cfg` exists on the CCU.

**`push` (Gate 1)** — Emit `gate_1_awaiting_ack` with the exact command and an explicit blast-radius message: this switch **will reboot 60-90s** after config TFTP, RSTP will recalculate, downstream peers (if `--allow-non-leaf`) will be isolated for that window. On ack, run `sudo obn update c <switch-ip>` over SSH from CCU. Capture stdout/stderr.

**`verify_rrq`** — Capture pre-push timestamp. Loop: every 5s, run `sudo journalctl -u tftpd-hpa --since "<pre_push_timestamp>" --no-pager 2>/dev/null | grep "RRQ from <switch-ip>"`. **90s window** (config files are small but the switch's TFTP request initiation takes a moment over the consist fabric). If no match in 90s → `gate_2_awaiting_ack`.

**`verify_reboot_started` (NEW — fail-fast stage unique to config push)** — After RRQ confirmed, ICMP-poll the switch every 5s for 60s. Expected outcome: switch goes DOWN within that window (the SNMP reboot OID firing, switch starting orderly shutdown). If switch goes DOWN: emit `verify_reboot_started` event with `outcome:"down"` and proceed to `poll_completion`. If switch stays UP for the full 60s: emit `aborted: config_did_not_trigger_reboot` with full diagnostic context — **no engineer ack option, no retry**.

The diagnostic context captured on this hard fail:
- OBN stdout/stderr from the push command (exit code, full text)
- Switch's `show running-config` first 50 lines via SSH (legacy options) — captures whether the new config is in running-config but persistence didn't fire, vs. config never landed at all
- `mtime` and `size` of `/data/auto-topology/upload/dostoneu-obn-<mac>.cfg`
- Whether journal shows the RRQ but no subsequent reboot-related log lines on the CCU side
- `obn discover` output for the switch (does the switch still respond to SNMP? what hostname does it report?)

This hard-fail is the right outcome because the only causes are: (a) OBN's SNMP reboot OID set silently failed, (b) the switch rejected the TFTP'd config and ignored the reboot OID, or (c) Bug 7 patch is somehow misfiring. None of these are recoverable by retry — they need engineer investigation.

**`stuck_recover`** (only after Gate 2 ack) — SSH into the target switch with the legacy KEX/host-key options (CLAUDE.md "Standard SSH-into-switch snippet"):
```bash
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "reboot"
```
Sleep 90s. Re-enter `push` *exactly once*. Switch CLI accepts only one command per SSH session (CLAUDE.md). If `verify_rrq` fails again after recovery push, emit `aborted: stuck_state_recovery_failed`.

**`poll_completion + reboot_detection`** — Loop: every 90s (handoff lesson 15), `sudo obn discover` + parse switch's config column. Concurrently track ICMP for `switch_returned` event. Loop until:
- `obn validate -t sw` shows config `✓` AND switch returned → emit `snmp_verify_post_reboot_ok` and proceed to RSTP check, OR
- `elapsed_seconds >= 1200` (20 min) → `gate_3_awaiting_ack`.

**`gate_3_awaiting_ack`** — Engineer chooses:
- `force-reboot` → SSH to switch with `admin@<sw-ip> "reboot"`, sleep 90s, re-enter `poll_completion` once with a 5-min budget.
- `extend-poll` → re-enter `poll_completion` with another 20-min budget.
- `abort` → emit `aborted: completion_timeout_20min`.

**`rstp_convergence_check`** — SSH into a *neighbouring* switch (NOT the one being updated). Compare RSTP root MAC pre vs post; check all neighbour trunk ports in `Forwarding` after a 60s settle window. If anomaly → `gate_4_awaiting_ack`.

**`verify_done`** — One final `sudo obn discover` + `sudo obn validate -t sw`. Confirm config `✓`. Emit `completed`.

## The five canonical commands

The skill's `--execute` mode runs exactly these (all from CCU via SSH, except #5 which SSHes into a switch):

```bash
# 1. Force fresh discovery (don't trust the every-5-min cache — handoff lesson 15)
sudo obn discover

# 2. Read switch config state from validate output, including (staged) parens form
sudo obn validate -t sw | grep -E "<switch-ip>|<switch-mac>"

# 3. The actual push (TFTP + SNMP reboot OID — one command from OBN's perspective)
sudo obn update c <switch-ip>

# 4. RRQ verification (handoff lesson 17 — journalctl, not /var/log/obn)
sudo journalctl -u tftpd-hpa --since "<timestamp>" --no-pager 2>/dev/null \
  | grep "RRQ from <switch-ip>"

# 5. RSTP convergence check from a neighbouring switch (legacy KEX/host-key options)
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<neighbour-ip> "show spanning-tree"
```

Stuck-state recovery (Gate 2) and force-reboot (Gate 3) use `sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "reboot"` — single command per SSH session.

No batch flags. No `obn update c all`. No `obn update c sw`. No glob form.

## `--prepare` recipe shape

When the verdict is `ready_to_push` or `partial_apply_detected`, the skill prints a runnable shell recipe. The new `verify_reboot_started` stage maps to a short ICMP loop after RRQ confirmation.

```bash
#!/usr/bin/env bash
# === dosto-sw-config-update recipe (manual run) ===
# Switch:     <switch-ip> (<switch-mac>, <switch-hostname>, role=<switch_role>)
# Config:     <config_file_path> (<config_file_size> bytes, mtime <config_file_mtime>)
# Leaf?       <is_leaf> (downstream peers: <downstream_peers>)
# Pre-flight verdict: ready_to_push

set -euo pipefail

CCU=<ccu-ip>
SW=<switch-ip>
NEIGHBOUR=<upstream_peer-ip>
KEY="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"
SW_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"

ssh_ccu() { ssh -i "$KEY" developer@$CCU "$@"; }

# === STEP 1: PRE-CHECK ===
echo "[1/7] Pre-check: TFTP helper, OBN patches (2b, 5, 6, 7, 8), L2 health, leaf status, config file..."
ssh_ccu 'lsmod | grep -q nf_conntrack_tftp && echo "tftp_helper:OK" || { echo "tftp_helper:MISSING — abort"; exit 2; }'
ssh_ccu 'sudo grep -c "if not result:" /usr/share/obn/lib/device/vendor/vdsrail.py | grep -q "^[2-9]" && echo "bug2b:OK" || { echo "bug2b:MISSING — abort"; exit 2; }'
ssh_ccu 'sudo grep -c "if hostname is not None:" /usr/share/obn/lib/device/vendor/vdsrail.py >/dev/null && echo "bug7:OK" || { echo "bug7:MISSING — abort"; exit 2; }'
ssh_ccu "ls /data/auto-topology/upload/dostoneu-obn-${SW_MAC_SLUG}.cfg" >/dev/null \
  || { echo "🔴 config file missing — run 'sudo obn update c $SW' once on CCU to render"; exit 7; }

# === STEP 2: CAPTURE PRE-PUSH RSTP ROOT MAC ===
echo "[2/7] Capturing pre-push RSTP root from neighbour $NEIGHBOUR..."
PRE_ROOT=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1)
echo "  RSTP root pre: $PRE_ROOT"

# === STEP 3: PUSH ===
echo "[3/7] Pushing config (switch will reboot 60-90s, RSTP will recalculate)..."
PRE_TS=$(ssh_ccu 'date --iso-8601=seconds')
ssh_ccu "sudo obn update c $SW"

# === STEP 4: VERIFY RRQ (90s window) ===
echo "[4/7] Watching journalctl for RRQ from $SW..."
for i in {1..18}; do
  if ssh_ccu "sudo journalctl -u tftpd-hpa --since '$PRE_TS' --no-pager 2>/dev/null | grep -q 'RRQ from $SW'"; then
    echo "  RRQ seen at second $((i*5))"
    break
  fi
  sleep 5
  if [ $i -eq 18 ]; then
    echo "🔴 NO RRQ IN 90s — switch is in stuck-state"
    echo "Recovery: sshpass -p Nom@dCome1n ssh $SW_OPTS admin@$SW 'reboot' && sleep 90, then retry the push once"
    exit 4
  fi
done

# === STEP 5: VERIFY REBOOT STARTED (60s window) ===
echo "[5/7] Verifying switch reboots after RRQ..."
REBOOT_DETECTED=0
for i in {1..12}; do
  if ! ssh_ccu "ping -c 1 -W 2 $SW >/dev/null 2>&1"; then
    echo "  switch went DOWN at second $((i*5)) — reboot started"
    REBOOT_DETECTED=1
    break
  fi
  sleep 5
done
if [ "$REBOOT_DETECTED" = "0" ]; then
  echo "🔴 SWITCH STAYED UP FOR 60s AFTER RRQ — config_did_not_trigger_reboot"
  echo "The new config landed via TFTP but the SNMP reboot OID didn't fire."
  echo "Diagnostic capture:"
  ssh_ccu "sudo cat /data/auto-topology/upload/dostoneu-obn-*.cfg | head -5" || true
  ssh_ccu "sshpass -p Nom@dCome1n ssh $SW_OPTS admin@$SW 'show running-config' 2>&1 | head -50" || true
  echo "Engineer must investigate — do NOT retry without diagnosis."
  exit 8
fi

# === STEP 6: POLL COMPLETION (up to 20 min) ===
echo "[6/7] Polling for completion (up to 20 min)..."
START=$(date +%s)
DEADLINE=$((START + 1200))
while [ $(date +%s) -lt $DEADLINE ]; do
  sleep 90
  ssh_ccu 'sudo obn discover >/dev/null 2>&1'
  STATE=$(ssh_ccu "sudo obn validate -t sw 2>/dev/null | grep $SW")
  PING=$(ssh_ccu "ping -c 1 -W 2 $SW >/dev/null 2>&1 && echo up || echo down")
  echo "  poll @ $(($(date +%s) - START))s: $STATE icmp=$PING"
  if echo "$STATE" | grep -q "✓" && [ "$PING" = "up" ]; then
    echo "✅ Config column ✓, switch returned"
    break
  fi
done
[ "$PING" != "up" ] && { echo "🔴 20 MIN ELAPSED, switch not returned"; exit 5; }

# === STEP 7: RSTP CONVERGENCE CHECK + VERIFY DONE ===
echo "[7/7] Checking RSTP convergence from neighbour $NEIGHBOUR..."
sleep 30  # let RSTP settle
POST_ROOT=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1)
echo "  RSTP root post: $POST_ROOT (pre was $PRE_ROOT)"
if [ "$PRE_ROOT" != "$POST_ROOT" ]; then
  echo "🟡 RSTP root changed — review fabric state. Run /dosto-l2-health for diagnostic."
  exit 6
fi
NON_FWD=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -E 'Listening|Learning|Blocking' | wc -l)
[ "$NON_FWD" = "0" ] && echo "✅ RSTP converged cleanly" \
  || { echo "🟡 $NON_FWD ports not forwarding on neighbour — review fabric"; exit 6; }

# Final verification
ssh_ccu 'sudo obn discover >/dev/null 2>&1'
ssh_ccu "sudo obn validate -t sw 2>/dev/null | grep $SW | grep -q '✓'" \
  && echo "✅ Switch $SW config push complete" \
  || { echo "🔴 verify_done: validate still shows ✗"; exit 9; }
```

Exit codes 2-9 align with the verdict / event taxonomy:
- 2 = `preconditions_unmet`
- 4 = `gate_2_awaiting_ack` (no RRQ)
- 5 = `gate_3_awaiting_ack` (completion timeout)
- 6 = `gate_4_awaiting_ack` (RSTP anomaly)
- 7 = `config_file_missing`
- **8 = `aborted: config_did_not_trigger_reboot`** (the new hard fail unique to config push)
- 9 = `aborted: verify_done_disagrees`

## Failure mode catalogue

| Symptom | Verdict / event | Skill behaviour |
|---|---|---|
| `nf_conntrack_tftp` not loaded | `preconditions_unmet:tftp_helper` 🔴 | Abort. Run `dosto-tftp-helper-check --apply-runtime`. |
| OBN patches < 8/8 (especially missing Bug 2b, 5, 6, 7, 8) | `preconditions_unmet:obn_patches` 🔴 | Abort. Run `dosto-obn-patches`. |
| `dosto-l2-health` reports fabric problems | `fabric_unhealthy` 🔴 | Abort. Engineer fixes fabric first. |
| `obn discover` fails or returns partial | `obn_tree_unbuildable` 🔴 | Abort. Bug 6 patch likely missing if coupled consist. |
| Rendered cfg file missing | `config_file_missing` 🔴 | Abort. Recipe says: `sudo obn update c <ip>` once on CCU to render, then re-invoke. |
| Switch IP not in DHCP leases / wrong OUI | `switch_not_found` 🔴 | Abort. Re-check `dosto-device-discovery`. |
| `obn validate` config column shows `✓` | `already_at_target_config` ✅ | Skip cleanly. |
| `current (staged) ✗` on config column | `partial_apply_detected` 🟡 | Recommend force-reboot only via Gate 3-style flow. Indicates previous push where TFTP landed but SNMP reboot OID didn't fire. |
| Switch is non-leaf, no `--allow-non-leaf` | `non_leaf_switch` 🔴 | Abort. Engineer pushes children first or passes override. |
| `obn update c` exited non-zero | `aborted: push_command_failed` 🔴 | Capture stderr. Could be Bug 2b, 7, or 8 path issue if patches missing — escalate. |
| Push reported "Successful" but no RRQ in 90s | `gate_2_awaiting_ack` 🔴 | Engineer acks → SSH-reboot the switch (legacy options), retry once. If second `verify_rrq` fails, abort. |
| **RRQ seen but switch stayed UP for 60s after** | **`aborted: config_did_not_trigger_reboot` 🔴** | **HARD FAIL — no retry, no engineer ack.** Capture diagnostic context (OBN output, switch's `show running-config`, cfg file mtime). Possible causes: SNMP reboot OID set failed, switch rejected TFTP'd config, Bug 7 patch misfire. |
| RRQ seen, reboot started, but config column never goes to ✓ in 20 min | `gate_3_awaiting_ack` 🔴 | Engineer chooses: force-reboot / extend-poll / abort. |
| RSTP root MAC changed during reboot window | `gate_4_awaiting_ack` 🟡 | Engineer reviews. May be benign root election or real fabric instability. |
| Some links non-forwarding 60s after switch returned | `gate_4_awaiting_ack` 🟡 | Run `dosto-l2-health` for full diagnostic. |

## What this skill deliberately does NOT do

- ❌ Push more than one switch per invocation
- ❌ Push to a non-leaf switch without explicit `--allow-non-leaf` override
- ❌ Skip the `verify_reboot_started` check — that's the safety net that catches "config TFTP'd but reboot OID didn't fire"
- ❌ Allow engineer override of `verify_reboot_started` failure — config push without reboot leaves the switch in a state where the new config exists in running-config but won't survive a power cycle. Engineer must investigate, not bypass.
- ❌ Skip the RSTP convergence check after reboot
- ❌ Use `obn update c all`, `obn update c sw`, or any glob/batch form
- ❌ Force-reboot switches without explicit Gate 2 / Gate 3 / Gate 4 ack
- ❌ Run if `dosto-l2-health` reports fabric problems
- ❌ Mix switch and AP pushes — caller iterates one device class at a time
- ❌ Trust OBN's "Successful" parsing alone (handoff lesson 12 applies to switches)
- ❌ Trust `obn validate`'s 5-min cache (always force fresh `obn discover` after a push) — handoff lesson 15
- ❌ Issue an explicit CLI `save running-config` step — OBN's flow is TFTP + SNMP reboot OID, with persistence implicit in the switch's orderly-shutdown behaviour. The `verify_reboot_started` stage is what enforces this implicit contract.
- ❌ Touch config on switches with active passenger services that depend on them — engineer's responsibility to schedule

## Edge cases / gotchas

- 🔴 **Reboot is mandatory, not optional.** OBN's `obn update c` flow relies on the switch rebooting to persist the new config (running-config → startup-config flush is implicit in orderly SNMP-triggered shutdown). If the switch doesn't reboot within 60s of RRQ, the `verify_reboot_started` stage fails hard — no retry, no override.
- 🔴 **`dostoneu-obn-<switchmac>.cfg` rendering depends on `train_id` template state.** If `dosto-fzg-id-check` shows broken or inconsistent templates, the rendered config files contain the wrong hostname (the Fzg 133 cascade pattern). Fix templates upstream before pushing config.
- 🟡 **Switch reboot drops trunks for 60-90s.** Same fabric impact as `dosto-sw-firmware-update`. Schedule pushes during maintenance windows for non-leaf switches.
- 🟡 **End-of-train switches (A1, F3 on a 6-car) are leaves** — their `e0-1` shows DOWN as normal, not a fabric problem.
- 🟡 **Coupled-consist case** (front coupler trunks live, second consist seen via LLDP): Bug 6 patch must be active or `obn discover` crashes.
- 🟡 **Switch CLI accepts only one command per SSH session** (CLAUDE.md). Recovery uses `sshpass ... admin@<sw-ip> "reboot"` — single command. No `;`-chaining.
- 🟡 **Switch SSH requires legacy KEX/host-key algorithms** (CLAUDE.md). All recipe templates include the full `-o` option set.
- 🟡 **`a0:59:3a` is the VDS switch MAC OUI**, not Westermo `00:14:5a`. Precondition uses OUI to refuse mistakenly pushing config to an AP IP.
- 🟡 **Bug 7 fires every config push** (handoff line 195 + line 187) — switch reboot triggers `set_configuration_version`'s hostname-after-reboot polling, hitting the None guard. The patch is what makes config push survive without crashing OBN. This is why Bug 7 is a strict precondition.
- 🟡 **The RSTP root MAC may legitimately change** during the reboot window — RSTP allowed to elect a new root if the elected one becomes unreachable. Gate 4 surfaces this for review rather than auto-judging.
- 🟡 **`obn validate -t sw` parens form is rare for config column** — switch config push is more linear than firmware (no two-partition flash). If you see `current (staged) ✗`, the previous push's TFTP landed but the SNMP reboot OID didn't fire — the `partial_apply_detected` verdict captures this. Force-reboot resolves it.
- 🟡 **The skill doesn't issue `save running-config`.** That CLI command exists and would persist running-config explicitly, but OBN's flow doesn't use it — and adding it would require an extra SSH session into the switch (one command per session per CLAUDE.md), bypassing OBN's `vdsrail.py reboot()` SNMP path and breaking Bug 7's exercise. Trust the implicit save-via-SNMP-reboot contract; verify it via `verify_reboot_started`.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — precondition. Without it, even single-switch pushes risk silent failure on the data return path.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — precondition. Bugs 2b, 5, 6, 7, 8 all relevant. All five validated on this code path on Fzg 132 / 2026-05-09.
- [`dosto-l2-health`](../dosto-l2-health/SKILL.md) — precondition (fabric must be clean before adding a switch reboot) AND post-update reference (rerun if Gate 4 fires).
- [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md) — must be `all_match` before config push, otherwise rendered config files contain the wrong hostname.
- [`dosto-sw-firmware-update`](../dosto-sw-firmware-update/SKILL.md) — runs *before* this skill on a full commissioning pass. Firmware first because firmware updates can reset config to defaults.
- [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md), [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md) — AP-side equivalents. APs first, switches second on a full commissioning pass.
- [`dosto-device-discovery`](../dosto-device-discovery/SKILL.md) — produces the switch IP list to iterate.
- `dosto-commission-train` (orchestrator, not yet built) — drives this skill switch-by-switch in OBNTree leaf-first order.

## Reference

- handoff lessons 11–17 (apply equally to switch config via TFTP)
- handoff line 195 — F2 / `10.179.10.189` config push validated cleanly on Fzg 132 / 2026-05-09 (this skill's empirical validation)
- handoff OBN patch validation table — Bug 2b, 7, 8 all fire on this code path and have been exercised
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "OBN Firmware & Config Update — Known Bugs and Fixes" → Bug 2 (config-side polling), Bug 6, Bug 7 (the canonical reboot path), Bug 8
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → Bug 7 patch source code (the `vdsrail.py reboot()` function — TFTP + SNMP reboot OID, no explicit save)
- [CLAUDE.md](../../../CLAUDE.md) → "Standard SSH-into-switch snippet" (legacy KEX/host-key options)
- auto-memory `project_obn_vdsrail_bug.md` — Bug 2b, 7, 8 context
