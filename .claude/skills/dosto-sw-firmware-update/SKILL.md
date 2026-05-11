---
name: dosto-sw-firmware-update
description: Push a VDS Rail Consist Switch firmware image via OBN. Use when pushing firmware to one consist switch, when an engineer says "obn update f" against a switch, or when a commissioning stage needs leaf-first switch firmware rollout. Sequences pushes leaf-first per OBNTree (a parent switch reboot would isolate its children), single-switch-at-a-time, with SNMP verification through the reboot window and full RSTP convergence check before declaring done. This is the surface where OBN Bugs 1 (vdsrail.py firmware regex) and 2a (firmware-side polling None guard) exercise — both untestable until a newer switch firmware binary is available; current fleet at target 7.4.2 means most pushes will be no-ops. Default --prepare mode is read-only diagnostic + recipe print; opt-in --execute mode drives one switch through the full push autonomously, stopping at gates for engineer approval. Pairs with dosto-tftp-helper-check, dosto-obn-patches, and dosto-l2-health (preconditions).
---

# DOSTO Switch Firmware Update

This skill pushes firmware to a single VDS Rail Consist Switch via OBN's `obn update f <switch-ip>` flow, with the verification, ordering, and convergence-checking that OBN itself doesn't implement. **Higher blast radius than the AP firmware skill**: a half-flashed switch can take down a coach or even the whole consist, and a switch reboot drops trunks for 60-90s, triggering RSTP topology recalculation across the fabric.

This is **switch firmware push only**. Switch config push is [`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md).

## Why this skill matters for OBN patch validation

Bug 1 (`vdsrail.py` firmware regex) and Bug 2a (`vdsrail.py` firmware-side polling None guard) are the only two of the 8 OBN patches that have **not** been exercised on a real consist as of 2026-05-09 (handoff OBN patch validation table). Both fire **only** during a real switch firmware push (not a no-op push to an already-on-target switch). Until R&D ships a newer switch firmware binary, this skill will mostly return `already_at_target` and the patches stay theoretically-correct-but-unproven. When a switch firmware update lands (or R&D adds unit tests), this skill becomes the test surface for those two patches.

## When to use

- **Step 8 of [train-login-checklist.md](../../../train-login-checklist.md)** — after AP firmware update is done. Switches are deeper in the fabric tree than APs; APs first, switches second.
- **One switch at a time, in OBNTree leaf-first order** — the skill rejects batch invocation. Orchestrator (or engineer) iterates leaves first, then walks up toward the root.
- **When `obn validate -t sw` shows mismatched firmware on at least one switch** — current fleet at 7.4.2 means most pushes are `already_at_target` no-ops.
- **Never on more than one switch at a time, never on a non-leaf without explicit override.** The leaf-first ordering is a correctness constraint, not a nice-to-have: pushing to a parent before its children isolates the children mid-reboot.

## Preconditions (skill aborts if any are not met)

Stricter preconditions than the AP skills because the blast radius is larger:

| Precondition | Why | Failure verdict |
|---|---|---|
| `dosto-tftp-helper-check` ∈ {`all_present`, `puppet_persisted`} | TFTP transfer goes through the same conntrack path as AP firmware. Without the helper, even a single switch push silently fails at the data-return-flow stage. | `preconditions_unmet:tftp_helper` 🔴 |
| `dosto-obn-patches` ∈ {`all_patched`, `all_persisted`} | Bug 1 (regex), Bug 2a (firmware-side None guard), Bug 5 (TFTP ipset), Bug 6 (cross-consist tree guard), Bug 7 (reboot hostname guard) — all required. Without Bug 1, the switch boots back into the old image bank with no error. Without Bug 2a, `obn update f` crashes on the first None SNMP response during reboot. | `preconditions_unmet:obn_patches` 🔴 |
| `dosto-l2-health` recent verdict is healthy | Pre-existing fabric problems (CRC errors, RSTP root flapping, link flaps) mask the post-reboot RSTP convergence check. Engineer must confirm fabric is clean before adding a switch reboot. | `fabric_unhealthy` 🔴 |
| `obn discover` succeeded recently — OBNTree is buildable | Bug 6 patch must be applied if any neighbour consist is coupled (front-coupler trunks live, second consist seen via LLDP). Without it, `obn discover` crashes with `AttributeError: 'NoneType' object has no attribute 'type'`. | `obn_tree_unbuildable` 🔴 |
| Switch IP is in `dhcp-lease-list` (not stale ARP) | Confirms the switch is alive and addressable. DHCP leases on this fleet are 2-min, so live `dhcp-lease-list` is authoritative; ARP can be stale. | `switch_not_found` 🔴 |
| Switch MAC OUI is `a0:59:3a` | Confirms it's a VDS Rail Consist Switch, not an AP (`00:14:5a`) or Stadler device (`00:90:e8` / others). | `switch_not_found` 🔴 |
| Switch is a **leaf** of OBNTree, OR engineer passed `--allow-non-leaf` | Pushing to a parent before its children isolates the children mid-reboot. Default-deny. | `non_leaf_switch` 🔴 |
| Single switch only — no batch glob | Argument parser. | error before any SSH |

## OBNTree leaf-first sequencing

The OBNTree is built by OBN's `tree.py` (with the Bug 6 patch). Topology on a 6-car DOSTO is a chain-of-stars:

```
A1 ─ A2 ─ A3 ── B1 ─ B2 ─ B3 ── C1 ─ C2 ─ C3 ── D1 ─ D2 ─ D3 ── E1 ─ E2 ─ E3 ── F1 ─ F2 ─ F3
```

Inter-coach trunks `e0-0`/`e0-1` connect adjacent FIS units; the central switch in each coach (A2, B2, C2, …) is the parent of its two siblings (A1 ↔ A2 ↔ A3, etc.). End-of-train switches (A1 and F3 on a 6-car) have an `e0-1` admin-enabled but link DOWN — that's normal, not a fabric problem.

A switch is a **leaf** if no other switch in OBNTree lists it as a parent. In practice on a 6-car:
- A1, A3 are leaves of the A-coach star
- B1, B3 are leaves of the B-coach star
- ... etc.
- A2, B2, C2, ... are intermediate (parents of their A1/A3 siblings, children of inter-coach links)

The skill itself works on **one switch**. Leaf-first ordering is the *orchestrator's* responsibility, but the skill enforces the per-invocation precondition: refuse to push a non-leaf unless `--allow-non-leaf` is passed.

When walking up the tree:
1. Push all per-coach leaves first (A1, A3, B1, B3, ..., F1, F3).
2. After all of those are at target, push the per-coach centres (A2, B2, ..., F2) with `--allow-non-leaf`.
3. The "root" is whichever central switch sits closest to the CCU's vlan100 transit path — typically A2 on the train's CCU coach, but topology-dependent. Push it last with `--allow-non-leaf`.

The skill computes leaf status from `obn discover`'s output (or reads `/tmp/discovery.json` directly per handoff lesson 15, with `jq`).

## Output modes

The skill has **two execution modes** plus the standard `--json` formatter switch — same family shape as `dosto-ap-firmware-update`.

- **`--prepare` (default) — read-only.** Verify preconditions, capture live state, run leaf check, print the equivalent shell recipe. No CCU writes, no switch changes.
- **`--execute` (opt-in) — autonomous driver.** Drives one switch through the full state machine: push, RRQ verification, stuck-state detection + recovery, 20-min completion poll, post-reboot RSTP convergence check, second-reboot decision. Stops at four explicit approval gates for irreversible actions.

Both modes support `--json`. In `--execute`, JSON is streamed one event per line.

### Optional flags

| Flag | Effect |
|---|---|
| `--allow-non-leaf` | Override the leaf-only precondition. Use only when all children of this switch are already at target. Required for pushing the per-coach centres and the tree root. |
| `--target <version>` | Override the target firmware version (default: parsed from `/tmp/discovery.json`). Used when intentionally downgrading or pushing a test build. |

### `--prepare` `--json` shape

```json
{
  "skill": "dosto-sw-firmware-update",
  "mode": "prepare",
  "schema_version": "1",
  "verdict": "ready_to_push|already_at_target|partial_flash_detected|preconditions_unmet|switch_not_found|non_leaf_switch|fabric_unhealthy|obn_tree_unbuildable",
  "raw": {
    "ccu_ip": "10.179.10.1",
    "switch_ip": "10.179.10.180",
    "switch_mac": "a0:59:3a:01:23:45",
    "switch_hostname": "nv6-A1-v8-132",
    "switch_role": "A1",
    "current_firmware": "7.4.2-77411",
    "staged_firmware": null,
    "target_firmware": "7.4.2-77411",
    "is_leaf": true,
    "downstream_peers": [],
    "upstream_peer": "10.179.10.181",
    "obn_patches_verdict": "all_persisted",
    "tftp_helper_verdict": "all_present",
    "l2_health_recent_verdict": "healthy",
    "rstp_root_mac_pre": "a0:59:3a:aa:bb:cc",
    "stp_state": "Forwarding",
    "trunk_neighbours_visible": true,
    "fix_obn_bug1_active": true,
    "fix_obn_bug2a_active": true,
    "fix_obn_bug5_active": true,
    "fix_obn_bug6_active": true,
    "fix_obn_bug7_active": true,
    "ipset_tftp_allowed_has_switch": true
  },
  "recipe": "..."
}
```

`verdict` semantics:

- `ready_to_push` ✅ — preconditions all green, switch is a leaf (or override), current ≠ target, no staged image. Standard fresh push path.
- `already_at_target` ✅ — current == target. **Common case on current fleet (everything at 7.4.2).** No-op.
- `partial_flash_detected` 🟡 — current ≠ target but staged == target. A previous push uploaded but `set_firmware_set_default` didn't activate (likely Bug 1 misfire if patches not active). Force-second-reboot resolves; no fresh push needed.
- `non_leaf_switch` 🔴 — switch has downstream peers and `--allow-non-leaf` was not passed. Engineer pushes children first or passes the override.
- `fabric_unhealthy` 🔴 — `dosto-l2-health` reports problems (CRC errors, RSTP root flapping, link flaps, sustained pause frames). Push would mask the post-reboot convergence signal. Engineer fixes fabric first.
- `obn_tree_unbuildable` 🔴 — `obn discover` failed or returned partial data. Bug 6 patch may be missing if a neighbour consist is coupled (front-coupler trunks live).
- `switch_not_found` 🔴 — switch IP not in DHCP leases or MAC OUI ≠ `a0:59:3a`. Wrong IP / wrong train / not a VDS switch.
- `preconditions_unmet` 🔴 — TFTP helper, OBN patches, or both not in good state.

`recipe` is non-null whenever verdict ∈ {`ready_to_push`, `partial_flash_detected`}.

### `--execute` `--json` event stream

Same one-event-per-line format as the AP firmware skill, with switch-fabric-specific events added:

```json
{"event":"started","timestamp":"...","switch_ip":"10.179.10.180","switch_role":"A1","target_firmware":"7.4.2-77411"}
{"event":"pre_check_passed","timestamp":"...","is_leaf":true,"l2_health":"healthy","rstp_root_mac_pre":"a0:59:3a:aa:bb:cc","stp_state":"Forwarding"}
{"event":"gate_1_awaiting_ack","timestamp":"...","action":"obn update f 10.179.10.180","blast_radius":"this switch will reboot 60-90s; RSTP will recalculate; downstream peers: []"}
{"event":"gate_1_acked","timestamp":"..."}
{"event":"push_command_returned","timestamp":"...","obn_says":"...","push_command_exit":0}
{"event":"rrq_seen","timestamp":"...","journalctl_line":"in.tftpd: RRQ from 10.179.10.180 filename sw-std-ng_..."}
{"event":"polling_completion","timestamp":"...","poll_count":3,"current_firmware":"...","staged_firmware":"...","elapsed_seconds":270}
{"event":"switch_rebooted","timestamp":"...","seconds_since_push":315,"icmp_state":"down"}
{"event":"switch_returned","timestamp":"...","seconds_since_push":402,"icmp_state":"up"}
{"event":"snmp_verify_post_reboot_ok","timestamp":"...","sysDescr":"...","firmware":"7.4.2-NEW"}
{"event":"rstp_convergence_check","timestamp":"...","root_mac_post":"a0:59:3a:aa:bb:cc","root_changed":false,"all_links_forwarding":true,"convergence_seconds":12}
{"event":"completed","timestamp":"...","total_elapsed_seconds":487,"final":true}
```

Failure-mode events:
- `gate_2_awaiting_ack` — no RRQ within 90s. Engineer must approve switch SSH-reboot recovery.
- `gate_3_awaiting_ack` — 20-min poll exhausted. Engineer chooses force-reboot, abort, or extend-poll.
- `gate_4_awaiting_ack` — RSTP root *changed* during reboot, or some links are not forwarding. Engineer reviews fabric state before declaring done.
- `aborted` — terminal failure with `final: true` and `reason` field.

## The state machine

```
                ┌──────────────────────────────┐
                │  pre_check (fabric + tree)   │
                └──────────────┬───────────────┘
                               │
            preconditions OK   ▼
                ┌──────────────────────┐         GATE 1
                │         push         │◄────  engineer acks  (with explicit blast-radius
                └──────────────┬───────┘                       message: trunk drops,
                               │                               RSTP recalc, downstream peers)
              `obn update f`   │
              returned         ▼
                ┌──────────────────────┐
                │     verify_rrq       │  poll journalctl every 5s for 90s
                └──┬─────────────────┬─┘
        RRQ seen   │                 │   no RRQ in 90s
                   │                 └────► GATE 2 (engineer ack: SSH-reboot
                   │                              admin@<sw-ip> "reboot",
                   │                              wait 90s, retry the push exactly once)
                   ▼
            ┌──────────────────────────┐
            │   poll_completion +      │  fresh `obn discover` every 90s, up to 20 min
            │   reboot_detection       │  (longer than AP — switch firmware bigger,
            │                          │   reboot includes RSTP reconvergence)
            └──┬──────────────────────┬┘
   target seen │                      │  20 min elapsed
   AND switch  │                      │
   returned    │                      └────► GATE 3 (force-reboot / extend-poll / abort)
               ▼
        ┌──────────────────────────┐
        │  rstp_convergence_check  │  Compare RSTP root MAC pre vs post,
        └──┬──────────────────────┬┘  all links FWD on neighbours
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

**`pre_check`** — Run all preconditions in one SSH heredoc to the CCU. Includes the SSH-into-a-neighbouring-switch step to capture the **pre-push RSTP root MAC** for later comparison. If any precondition fails, emit `aborted` with `reason: "preconditions_unmet:<which>"` and exit. No further state.

**`push` (Gate 1)** — Emit `gate_1_awaiting_ack` with the exact command and an explicit blast-radius message: how long the switch will be down (~60-90s), that RSTP will recalculate during that window, and which downstream peers (if `--allow-non-leaf`) will be isolated. Wait for ack. On ack, run `sudo obn update f <switch-ip>` over SSH from CCU. Capture stdout/stderr.

**`verify_rrq`** — Capture pre-push timestamp. Loop: every 5s, run `sudo journalctl -u tftpd-hpa --since "<pre_push_timestamp>" --no-pager 2>/dev/null | grep "RRQ from <switch-ip>"`. If a match appears, emit `rrq_seen` and proceed. **Window: 90s for switches** (vs 60s for APs — switch firmware images are larger, switches are slower over the consist fabric). If 90s elapses with no match, emit `gate_2_awaiting_ack`.

**`stuck_recover`** (only after Gate 2 ack) — SSH into the target switch with the legacy KEX/host-key options (CLAUDE.md "Standard SSH-into-switch snippet"):
```bash
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "reboot"
```
Sleep 90s. Re-enter `push` *exactly once*. The switch CLI accepts only one command per session (CLAUDE.md), so `reboot` is the entire command — no chaining. If `verify_rrq` fails again after the recovery push, emit `aborted` with `reason: "stuck_state_recovery_failed"` — engineer territory.

**`poll_completion + reboot_detection`** — Loop: every 90s (handoff lesson 15), run `sudo obn discover` and parse the switch's firmware version. Concurrently track ICMP state for reboot detection: emit `switch_rebooted` when the switch goes DOWN, `switch_returned` when it comes back UP. Loop until either:
- `current_firmware == target_firmware` AND switch returned → emit `snmp_verify_post_reboot_ok` and proceed to RSTP convergence check, OR
- `elapsed_seconds >= 1200` (20 min) → emit `gate_3_awaiting_ack` with current/staged/target tuple.

**Why 20 min, not 15:** switch firmware images are bigger than AP images (~30-50 MB vs ~6-8 MB), reboots take longer (RSTP reconvergence on top of bootloader+kernel+app), and we don't have empirical timing data from a real switch firmware push to anchor a tighter number. Conservative-but-not-absurd.

**`gate_3_awaiting_ack`** — Engineer chooses:
- `force-reboot` → SSH to switch with `admin@<sw-ip> "reboot"`, sleep 90s, re-enter `poll_completion` once with a 5-min budget. Resolves the `staged_firmware == target_firmware` partial-flash case (handoff lesson 16).
- `extend-poll` → re-enter `poll_completion` with another 20-min budget. Use sparingly.
- `abort` → emit `aborted` with `reason: "completion_timeout_20min"` and exit.

**`rstp_convergence_check`** — SSH into a *neighbouring* switch (NOT the one being updated) and run `show spanning-tree`. Capture the RSTP root MAC and per-port state. Compare:
- `root_mac_post == root_mac_pre`? If different → emit `gate_4_awaiting_ack` with both values.
- All neighbouring switches' trunk ports in `Forwarding` state? If any are `Listening`, `Learning`, or `Blocking` after a 60s settle window → emit `gate_4_awaiting_ack`.
- Convergence time: capture how many seconds elapsed between `switch_returned` and "all neighbours forwarding."

If both checks pass: emit `rstp_convergence_check` with `root_changed: false` and proceed to `verify_done`.

**`gate_4_awaiting_ack`** (RSTP anomaly) — Engineer reviews. Possible causes:
- Root election preferred a different switch (benign — RSTP is allowed to elect a new root). Continue with `verify_done`.
- Real fabric instability: a link didn't come back forwarding, or root flapped multiple times. Engineer should run `dosto-l2-health` for full diagnostic.
- Skill defaults to "abort and report" — never auto-continues past Gate 4 without ack.

**`verify_done`** — One final `sudo obn discover` + `sudo obn validate -t sw`. Confirm `current_firmware == target_firmware`. Emit `completed` with the full timing summary.

## The five canonical commands

The skill's `--execute` mode runs exactly these (all from CCU via SSH, except #5 which SSHes into a switch):

```bash
# 1. Force fresh discovery (don't trust the every-5-min cache — handoff lesson 15)
sudo obn discover

# 2. Read switch firmware state from validate output, including (staged) parens form
sudo obn validate -t sw | grep -E "<switch-ip>|<switch-mac>"

# 3. The actual push
sudo obn update f <switch-ip>

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

Stuck-state recovery (Gate 2) and force-reboot (Gate 3) use `sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "reboot"` — single command per session.

No batch flags. No `obn update f all`. No `obn update f sw` (which targets all switches). No glob form.

## `--prepare` recipe shape

When the verdict is `ready_to_push` or `partial_flash_detected`, the skill prints a runnable shell recipe matching what `--execute` would do. Engineer runs it manually, or pipes it through `bash -x` for an audit trail. The recipe includes inline comments at every decision point.

```bash
#!/usr/bin/env bash
# === dosto-sw-firmware-update recipe (manual run) ===
# Switch:     <switch-ip> (<switch-mac>, <switch-hostname>, role=<switch_role>)
# From:       <current_firmware>
# To:         <target_firmware>
# Leaf?       <is_leaf> (downstream peers: <downstream_peers>)
# Pre-flight verdict: ready_to_push

set -euo pipefail

CCU=<ccu-ip>
SW=<switch-ip>
NEIGHBOUR=<upstream_peer-ip>
TARGET=<target_firmware>
KEY="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"
SW_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"

ssh_ccu() { ssh -i "$KEY" developer@$CCU "$@"; }

# === STEP 1: PRE-CHECK ===
echo "[1/6] Pre-check: TFTP helper, OBN patches (1, 2a, 5, 6, 7), L2 health, leaf status..."
ssh_ccu 'lsmod | grep -q nf_conntrack_tftp && echo "tftp_helper:OK" || { echo "tftp_helper:MISSING — abort"; exit 2; }'
# Check Bug 1 marker (the regex variant)
ssh_ccu 'sudo grep -c "default image is now" /usr/share/obn/lib/device/vendor/vdsrail.py >/dev/null && echo "bug1:OK" || { echo "bug1:MISSING — abort"; exit 2; }'
# Check Bug 2a marker (firmware-side polling, distinct from Bug 2b)
ssh_ccu 'sudo grep -c "if not result:" /usr/share/obn/lib/device/vendor/vdsrail.py | grep -q "^[2-9]" && echo "bug2:OK" || { echo "bug2:MISSING — abort"; exit 2; }'

# === STEP 2: CAPTURE PRE-PUSH RSTP ROOT MAC ===
echo "[2/6] Capturing pre-push RSTP root from neighbour $NEIGHBOUR..."
PRE_ROOT=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1)
echo "  RSTP root pre: $PRE_ROOT"

# === STEP 3: PUSH ===
echo "[3/6] Pushing firmware (switch will reboot 60-90s, RSTP will recalculate)..."
PRE_TS=$(ssh_ccu 'date --iso-8601=seconds')
ssh_ccu "sudo obn update f $SW"

# === STEP 4: VERIFY RRQ (90s window) ===
echo "[4/6] Watching journalctl for RRQ from $SW..."
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

# === STEP 5: POLL COMPLETION (up to 20 min) + REBOOT DETECTION ===
echo "[5/6] Polling for completion (up to 20 min)..."
START=$(date +%s)
DEADLINE=$((START + 1200))
SWITCH_REBOOTED=0
while [ $(date +%s) -lt $DEADLINE ]; do
  sleep 90
  ssh_ccu 'sudo obn discover >/dev/null 2>&1'
  CUR=$(ssh_ccu "sudo obn validate -t sw 2>/dev/null | grep $SW | grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+' | head -1")
  PING=$(ssh_ccu "ping -c 1 -W 2 $SW >/dev/null 2>&1 && echo up || echo down")
  echo "  poll @ $(($(date +%s) - START))s: current=$CUR target=$TARGET icmp=$PING"
  if [ "$PING" = "down" ] && [ "$SWITCH_REBOOTED" = "0" ]; then
    echo "    switch is rebooting"
    SWITCH_REBOOTED=1
  fi
  if [ "$CUR" = "$TARGET" ] && [ "$PING" = "up" ]; then
    echo "✅ Target firmware reached, switch returned"
    break
  fi
done
if [ "$CUR" != "$TARGET" ]; then
  echo "🔴 20 MIN ELAPSED, current=$CUR != target=$TARGET"
  echo "Decisions:"
  echo "  - force-reboot:  sshpass -p Nom@dCome1n ssh $SW_OPTS admin@$SW 'reboot' && wait 5 min"
  echo "  - extend-poll:   re-run STEP 5 for another 20 min"
  echo "  - abort:         leave switch at $CUR and document"
  exit 5
fi

# === STEP 6: RSTP CONVERGENCE CHECK ===
echo "[6/6] Checking RSTP convergence from neighbour $NEIGHBOUR..."
sleep 30  # let RSTP settle
POST_ROOT=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1)
echo "  RSTP root post: $POST_ROOT (pre was $PRE_ROOT)"
if [ "$PRE_ROOT" != "$POST_ROOT" ]; then
  echo "🟡 RSTP root changed — review fabric state. Run /dosto-l2-health for diagnostic."
  exit 6
fi
# Check all neighbour ports forwarding
NON_FWD=$(ssh_ccu "sshpass -p 'Nom@dCome1n' ssh $SW_OPTS admin@$NEIGHBOUR 'show spanning-tree'" \
  | grep -E 'Listening|Learning|Blocking' | wc -l)
[ "$NON_FWD" = "0" ] && echo "✅ RSTP converged cleanly" \
  || { echo "🟡 $NON_FWD ports not forwarding on neighbour — review fabric"; exit 6; }

# Final verification
ssh_ccu 'sudo obn discover >/dev/null 2>&1'
FINAL=$(ssh_ccu "sudo obn validate -t sw 2>/dev/null | grep $SW | grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+' | head -1")
[ "$FINAL" = "$TARGET" ] && echo "✅ Switch $SW at $FINAL" || { echo "🔴 verify_done disagrees: $FINAL"; exit 7; }
```

Exit codes 2-7 align with the verdict / event taxonomy:
- 2 = `preconditions_unmet`
- 4 = `gate_2_awaiting_ack` (no RRQ)
- 5 = `gate_3_awaiting_ack` (completion timeout)
- 6 = `gate_4_awaiting_ack` (RSTP anomaly)
- 7 = `aborted: verify_done_disagrees`

## Failure mode catalogue

| Symptom | Verdict / event | Skill behaviour |
|---|---|---|
| `nf_conntrack_tftp` not loaded | `preconditions_unmet:tftp_helper` 🔴 | Abort. Run `dosto-tftp-helper-check --apply-runtime`. |
| OBN patches < 8/8 (especially missing Bug 1, 2a, 5, 6, 7) | `preconditions_unmet:obn_patches` 🔴 | Abort. Run `dosto-obn-patches --apply` then `--persist`. |
| `dosto-l2-health` reports fabric problems | `fabric_unhealthy` 🔴 | Abort. Engineer fixes fabric first. |
| `obn discover` fails or returns partial | `obn_tree_unbuildable` 🔴 | Abort. Bug 6 patch likely missing if coupled consist. |
| Switch IP not in DHCP leases | `switch_not_found` 🔴 | Abort. Re-check `dosto-device-discovery`. |
| Switch MAC OUI ≠ `a0:59:3a` | `switch_not_found` 🔴 | Abort. The IP isn't a VDS switch — could be an AP or wrong train. |
| `current == target` | `already_at_target` ✅ | Skip cleanly. Common case on current fleet. |
| `current ≠ target` AND `staged == target` | `partial_flash_detected` 🟡 | `--prepare` recommends force-reboot only. `--execute` jumps to Gate 3 with `force-reboot` pre-suggested. Likely Bug 1 misfire if patches not active. |
| Switch is non-leaf, no `--allow-non-leaf` | `non_leaf_switch` 🔴 | Abort. Engineer pushes children first or passes override. |
| `obn update f` exited non-zero | `aborted: push_command_failed` 🔴 | Capture stderr verbatim. Could be Bug 1 or Bug 2a if patches missing — escalate, do not auto-retry. |
| Push reported "Successful" but no RRQ in 90s | `gate_2_awaiting_ack` 🔴 | Engineer acks → SSH-reboot the switch (legacy SSH options), retry once. If second `verify_rrq` fails, abort. |
| RRQ seen, transfer started, but firmware unchanged after 20 min | `gate_3_awaiting_ack` 🔴 | Engineer chooses: force-reboot / extend-poll / abort. |
| Switch returned but firmware string still old | Likely Bug 1 path — `set_firmware_set_default` was never called. | Capture full diagnostic. Verify Bug 1 patch is applied; re-push only after confirming. |
| RSTP root MAC changed during reboot window | `gate_4_awaiting_ack` 🟡 | Engineer reviews. May be benign root election or real instability. |
| Some links non-forwarding 60s after switch returned | `gate_4_awaiting_ack` 🟡 | Run `dosto-l2-health` for full diagnostic before continuing. |

## What this skill deliberately does NOT do

- ❌ Push more than one switch per invocation
- ❌ Push to a non-leaf switch without explicit `--allow-non-leaf` override
- ❌ Use `obn update f all`, `obn update f sw`, or any glob/batch form
- ❌ Skip the RSTP convergence check after reboot — that's the fabric-level safety net
- ❌ Force-reboot switches without explicit Gate 2 / Gate 3 / Gate 4 ack
- ❌ Run if `dosto-l2-health` reports fabric problems — masks the convergence signal
- ❌ Mix switch and AP pushes — caller iterates one device class at a time
- ❌ Trust OBN's "Successful" parsing alone (handoff lesson 12 applies to switches)
- ❌ Trust `obn validate`'s 5-min cache (always force fresh `obn discover` after a push) — handoff lesson 15
- ❌ Touch firmware on switches with active passenger services that depend on them — engineer's responsibility to schedule the push during a maintenance window
- ❌ Update a switch the orchestrator hasn't already updated all children of — the leaf-first walk is the orchestrator's discipline, the skill's precondition just enforces it per-invocation

## Edge cases / gotchas

- 🔴 **Switch reboot drops trunks for 60-90s.** Adjacent switches see this as link-down and start RSTP recalculation. If the target switch is in the active forwarding path for any service, that service drops during the reboot window. Engineer must schedule pushes during maintenance windows, especially for non-leaf switches.
- 🔴 **Bug 1 + Bug 2a only fire here.** Without these patches, switch firmware push silently fails (Bug 1: switch boots back into old image bank with no error reported; Bug 2a: `obn update f` crashes on the first None SNMP response during reboot). The skill's preconditions verify both.
- 🟡 **End-of-train switches (A1, F3 on a 6-car) appear to have only one upstream neighbour.** They are leaves by topology. Their `e0-1` shows DOWN — that's normal (no further switch beyond them). Don't flag this as a fabric problem.
- 🟡 **Coupled-consist case** (front coupler trunks live, second consist seen via LLDP): Bug 6 patch must be active or `obn discover` crashes. The skill's `obn_tree_unbuildable` verdict catches this. The skill itself doesn't try to handle coupled consists differently — refuses to proceed if Bug 6 patch is missing.
- 🟡 **Switch CLI accepts only one command per SSH session** (CLAUDE.md). Recovery uses `sshpass ... admin@<sw-ip> "reboot"` — single command. No `;`-chaining.
- 🟡 **Switch SSH requires legacy KEX/host-key algorithms** (CLAUDE.md). All recipe templates include the full `-o` option set.
- 🟡 **`a0:59:3a` is the VDS switch MAC OUI**, not the Westermo `00:14:5a`. The precondition uses OUI to refuse mistakenly pushing firmware to an AP IP.
- 🟡 **Bug 1 patch behaviour: works for both old and new switch firmware status formats.** The patched regex `(?:default image is now|image loaded \[)(.*?)\]?` matches both. So even if a future firmware reverts to the old format, the patch is forward-compatible.
- 🟡 **Bug 2a's None guard fires multiple times during a normal push** — every poll cycle while the switch is rebooting will get `None` from SNMP. The patch is what *prevents* the crash; without it, every push crashes. With it, every push survives. This is why the skill needs the patch active before any push runs.
- 🟡 **`obn validate -t sw` parens form is rare for switches** — most switches don't reach the staged-but-not-activated state because the push flow is more linear than for APs (no two-partition flash). If you see it, it's probably Bug 1 having silently failed `set_firmware_set_default` — re-check that the patch is applied and re-push.
- 🟡 **The RSTP root MAC may legitimately change** even with a clean push — RSTP is allowed to elect a new root if the elected one becomes unreachable during the reboot window. Gate 4 surfaces this for engineer review rather than auto-judging.
- 🟡 **Bug 7 fires on the post-reboot hostname polling.** It's been validated (handoff OBN patch validation, fired during forced switch config push to F2 on Fzg 132). For firmware push, Bug 7 fires for the same reason — switch reboots and SNMP polling hits the None case during the boot window.
- 🟡 **Some switches in the fleet may be running a non-target firmware as deliberate test state.** Don't assume `current ≠ target` always means "needs update" — the engineer is the source of truth.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — precondition. Without it, even single-switch pushes risk silent failure on the data return path.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — precondition. Bugs 1, 2a, 5, 6, 7 all relevant. Bug 1 + 2a are the unproven patches this skill validates.
- [`dosto-l2-health`](../dosto-l2-health/SKILL.md) — precondition (fabric must be clean before adding a switch reboot) AND post-update reference (rerun if Gate 4 fires).
- [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md) — runs *before* this skill on a full commissioning pass. APs first, switches second.
- [`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md) — same family shape, different command path.
- [`dosto-device-discovery`](../dosto-device-discovery/SKILL.md) — produces the switch IP list to iterate.
- `dosto-commission-train` (orchestrator, not yet built) — drives this skill switch-by-switch in OBNTree leaf-first order, surfacing each gate to the engineer.

## Reference

- handoff lessons 11–17 (apply equally to switch firmware via TFTP)
- handoff OBN patch validation table — Bug 1 and Bug 2a still pending; this skill is their validation surface
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "OBN Firmware & Config Update — Known Bugs and Fixes" → Bug 1, Bug 2, Bug 6, Bug 7
- [CLAUDE.md](../../../CLAUDE.md) → "Standard SSH-into-switch snippet" (legacy KEX/host-key options)
- [CLAUDE.md](../../../CLAUDE.md) → "Phase 2 — Map switch IPs to schema positions" (leaf vs non-leaf identification)
- auto-memory `project_obn_vdsrail_bug.md` — Bug 1 and 2a context
- `dosto-l2-health` SKILL.md — what counts as "fabric healthy" (the precondition definition)
