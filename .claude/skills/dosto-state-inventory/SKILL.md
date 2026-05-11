---
name: dosto-state-inventory
description: Read a per-train inventory of persistent-state facts from a CCU and compare against expected values. Use when starting a new commissioning session on a known train, when a CCU reboot may have wiped runtime state, or whenever the orchestrator needs a pre-flight drift check before approving destructive ops. Detects state drift between sessions — TFTP CT helper rule lost on reboot, OBN patches wiped by auto-update timer, btrfs subvol rolled back, vlan7 IP changed, NDSU rename undone, etc. Fast read-only probe (~10 SSH round-trips), called by the orchestrator at start of each train's commissioning to surface what changed since the last session before any destructive ops are approved.
---

# DOSTO State Inventory

This skill is the **start-of-session sanity check** for a CCU. It reads a fixed set of persistent-state facts (the things we previously believed should still be true) and compares them against expected values. Anything that drifted since the last session surfaces immediately, before the orchestrator commits to today's plan.

It's the per-train counterpart of [`dosto-confluence-sync --check`](../dosto-confluence-sync/SKILL.md) (which detects drift on the team Confluence page). Both implement the same pattern: validate the world matches what we last saw, halt-and-surface if not.

## Why this exists

Across this rollout we've hit several "state we thought was persistent silently went away" failures:

- TFTP CT helper rule (the runtime fix from `dosto-tftp-helper-check --apply-runtime`) is in-memory only — every CCU reboot wipes it, breaking AP firmware push. **Documented but not enforced.**
- OBN patches reverted on a CCU where `nd-systemupdate.sh` was at the canonical name and the nightly auto-update timer fired (handoff: box1-t1 / Fzg 133 was exposed as of 2026-05-09).
- Two-promote pattern on Fzg 132 because the chroot started from `release` not `runN` and lost in-place edits.
- `train_id` template silently regressing to the broken `128 + train_id` formula after some Puppet runs.

Each of these had a documented "what to check" recipe scattered across SKILL.mds and the runbook. This skill consolidates them into one fast probe + one structured diff against expected, so the orchestrator can flag drift without the engineer remembering 12 things to grep for.

## When to use

- **Orchestrator stage 1 (`initial_diagnostics`)** — invoked as part of the pre-stage-1 inventory probe. Output feeds into the orchestrator's Pre-Flight assumptions.
- **Manual session start** — engineer types `/dosto-state-inventory <ccu-ip> <fzg>` after SSH-ing to the CCU as a "did anything change since last time?" probe.
- **Before approving any irreversible gate** — the orchestrator re-runs this check immediately before relaying an `approved` response to the subagent at Gate 1 (promote) or Gate 4 (firmware push). Catches drift between the engineer reading the gate prompt and pressing y.

## Inputs

- `<ccu-ip>` — required. e.g. `10.179.10.1`.
- `<fzg>` — required. The Fzg ID, used to compute expected vlan7 IP and template `train_id`.
- `--expected <path>` — optional. Path to a per-train `expected.json` file. If absent, the skill computes expectations from `<fzg>` + the per-series formula (Fzg = train# +28 for 4736, -100 for 4734).
- `--json` — optional. Machine-readable output (default). Engineer-readable with `--human`.

## What it inventories

The 12 facts checked, in this fixed order. Each is one or two SSH round-trips on the CCU.

| # | Fact | Probe | Expected |
|---|---|---|---|
| 1 | CCU hostname | `hostname` | `box1-t<NN>` matching the CCU IP (10.179.NN.1 → box1-t<NN>) |
| 2 | CCU uptime | `uptime` | informational — flags fresh reboots |
| 3 | btrfs active subvolume | `mount \| grep " on / "` | one of `release` / `runN` (subvol ID logged for delta vs prior session) |
| 4 | OBN patches present | grep markers per `dosto-obn-patches --check` | 8/8 |
| 5 | OBN patches persisted | btrfs subvol path indicates non-`work` snapshot | true |
| 6 | nd-systemupdate filename | `[ -f /usr/sbin/nd-systemupdate.sh.dont ] \|\| [ -f /usr/sbin/nd-systemupdate.sh ]` | `.dont` (fleet-standard); canonical name is 🟡 exposed-to-auto-update |
| 7 | train_id template form | `grep -h "^{%- set train_id" /etc/obn/template/nv*-*.cfg \| sort -u` | exactly one line `{%- set train_id = <Fzg> -%}` |
| 8 | vlan7 live IP | `ip -br addr show vlan7` | matches bit-packed formula for Fzg |
| 9 | vlan7 nmconnection | `sudo cat /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection \| grep ^address1=` | matches expected |
| 10 | TFTP module loaded | `lsmod \| grep nf_conntrack_tftp` | present (fleet-default kernel autoloads it; rare to be missing) |
| 11 | TFTP CT helper rule | `sudo iptables -t raw -L PREROUTING -n -v \| grep "helper tftp"` | rule present (in-memory runtime fix; LOST on reboot — fact 2 uptime informs whether to expect this) |
| 12 | tftp_allowed ipset | `sudo ipset list tftp_allowed \| grep "Number of entries"` | non-zero entries (Bug 5 patch active) |

**Probe efficiency:** all 12 facts collected in **one SSH heredoc** to the CCU, ~5 second wall time. The skill's value is in the structured diff, not in fancy probing.

## Verdict logic

After collecting, the skill computes a per-fact verdict (`pass` / `fail` / `warn`) and an aggregate verdict for the whole inventory.

| Aggregate verdict | Meaning |
|---|---|
| `all_match` | All 12 facts pass. Train is in the state we last saw. ✅ |
| `expected_drift` | One or more facts drifted in *expected* ways (e.g. fact 11 TFTP helper rule missing on a fresh reboot — expected because runtime fix is in-memory only). 🟡 — flagged for engineer awareness but not blocking. |
| `unexpected_drift` | One or more facts drifted in *unexpected* ways (e.g. OBN patches went from 8/8 to 0/8 — auto-update fired). 🔴 — orchestrator halts before any destructive op until engineer acks the drift. |
| `error` | A probe failed (CCU unreachable, sudo refused, etc.). 🔴 — investigate. |

**Expected-drift cases** (warn, don't fail):
- Fact 11 missing AND fact 2 (uptime) shows recent reboot — TFTP helper rule lost on reboot is expected; engineer should re-apply via `dosto-tftp-helper-check --apply-runtime` before any AP firmware push.
- Fact 6 == canonical `.sh` AND fact 4 still 8/8 — auto-update timer hasn't fired yet but train is exposed; engineer should re-rename to `.dont` at next opportunity.

**Unexpected-drift cases** (fail):
- Any of facts 4, 7, 8, 9 changed AND fact 3 subvol ID matches last session's — the patches/configs we trusted as persistent silently went away without a btrfs promote. Investigate.
- Any of facts 4, 7, 8, 9 changed AND fact 3 subvol ID is different from last session's — a btrfs promote happened (likely auto-update). Engineer needs to decide whether to re-apply patches or accept the new state.

## `--json` output shape

```json
{
  "skill": "dosto-state-inventory",
  "mode": "check",
  "schema_version": "1",
  "verdict": "all_match|expected_drift|unexpected_drift|error",
  "raw": {
    "ccu_ip": "10.179.10.1",
    "fzg": 132,
    "probe_duration_ms": 4820,
    "facts": [
      {"id": 1, "name": "ccu_hostname", "expected": "box1-t10", "actual": "box1-t10", "verdict": "pass"},
      {"id": 2, "name": "ccu_uptime_seconds", "expected": null, "actual": 21240, "verdict": "pass"},
      {"id": 3, "name": "btrfs_active_subvol", "expected": null, "actual": "/.snapshots/run1 (id 314)", "verdict": "pass"},
      {"id": 4, "name": "obn_patches_count", "expected": 8, "actual": 8, "verdict": "pass"},
      {"id": 5, "name": "obn_patches_persisted", "expected": true, "actual": true, "verdict": "pass"},
      {"id": 6, "name": "nd_systemupdate_filename", "expected": "nd-systemupdate.sh.dont", "actual": "nd-systemupdate.sh.dont", "verdict": "pass"},
      {"id": 7, "name": "train_id_template", "expected": "{%- set train_id = 132 -%}", "actual": "{%- set train_id = 132 -%}", "verdict": "pass"},
      {"id": 8, "name": "vlan7_live_ip", "expected": "172.19.194.2/17", "actual": "172.19.194.2/17", "verdict": "pass"},
      {"id": 9, "name": "vlan7_nmconnection", "expected": "172.19.194.2/17", "actual": "172.19.194.2/17", "verdict": "pass"},
      {"id": 10, "name": "tftp_module_loaded", "expected": true, "actual": true, "verdict": "pass"},
      {"id": 11, "name": "tftp_ct_helper_rule", "expected": true, "actual": false, "verdict": "warn", "reason": "rule missing — fact 2 uptime is recent (5h54m), runtime fix lost on last reboot. Re-apply before AP firmware push."},
      {"id": 12, "name": "tftp_allowed_ipset_entries", "expected": ">0", "actual": 18, "verdict": "pass"}
    ],
    "drift_summary": {
      "facts_passed": 11,
      "facts_warned": 1,
      "facts_failed": 0,
      "is_blocking": false
    },
    "delta_from_last_session": {
      "last_session_ts": "2026-05-09T16:21:00Z",
      "facts_changed": ["tftp_ct_helper_rule"],
      "btrfs_subvol_changed": false
    }
  },
  "next_action": "Re-apply TFTP CT helper runtime fix before any obn update f. Run /dosto-tftp-helper-check 10.179.10.1 --apply-runtime."
}
```

The `delta_from_last_session` block compares against `.claude/logs/state-inventory-<fzg>.jsonl` (one line per session). If no prior log exists, it's `null` and the skill treats this as a fresh visit.

## Procedure

### Step 0 — Read prior log (if exists)

Read `.claude/logs/state-inventory-<fzg>.jsonl` (last line). Capture `last_session_facts` and `last_session_btrfs_subvol_id`. If the file doesn't exist, treat all facts as "no prior baseline" — every value is just informational, no drift detection on this run.

### Step 1 — Probe in one SSH session

```bash
ssh -i "<key>" developer@<ccu-ip> '
echo "=== fact 1: hostname ==="; hostname
echo "=== fact 2: uptime ==="; cat /proc/uptime | awk "{print int(\$1)}"
echo "=== fact 3: btrfs subvol ==="; mount | grep " on / " | head -1
echo "=== fact 4-5: OBN patch markers ==="
for line in \
  "default image is now:/usr/share/obn/lib/device/vendor/vdsrail.py" \
  "if not result::/usr/share/obn/lib/device/vendor/vdsrail.py" \
  "except KeyError::/usr/share/obn/lib/device/snmpdevice.py" \
  "bool(self.firmware) and not self.firmware.endswith:/usr/share/obn/lib/report/device.py" \
  "Bug 5 fix: pre-populate tftp_allowed ipset:/usr/share/obn/cli/update.py" \
  "neighbour not in this consist:/usr/share/obn/lib/tree.py" \
  "if hostname is not None::/usr/share/obn/lib/device/vendor/vdsrail.py" \
  "bool(self.config) and not self.config.endswith:/usr/share/obn/lib/report/device.py"; do
  pattern="${line%:*}"
  file="${line#*:}"
  echo -n "marker:"; sudo grep -c "$pattern" "$file"
done
echo "=== fact 6: NDSU filename ==="
if [ -f /usr/sbin/nd-systemupdate.sh.dont ]; then echo "NDSU=nd-systemupdate.sh.dont"; \
elif [ -f /usr/sbin/nd-systemupdate.sh ]; then echo "NDSU=nd-systemupdate.sh"; \
else echo "NDSU=MISSING"; fi
echo "=== fact 7: train_id template ==="
grep -h "^{%- set train_id" /etc/obn/template/nv*-*.cfg 2>/dev/null | sort -u
echo "=== fact 8: vlan7 live ==="; ip -br addr show vlan7
echo "=== fact 9: vlan7 nmconnection ==="
sudo cat /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection 2>/dev/null | grep "^address1="
echo "=== fact 10: TFTP module ==="; lsmod | grep -c nf_conntrack_tftp
echo "=== fact 11: TFTP CT helper rule ==="
sudo iptables -t raw -L PREROUTING -n -v 2>/dev/null | grep -c "helper tftp"
echo "=== fact 12: tftp_allowed ipset ==="
sudo ipset list tftp_allowed 2>/dev/null | grep "Number of entries" | awk -F: "{print \$2}" | tr -d " "
'
```

### Step 2 — Compute expectations from `<fzg>`

```python
# vlan7 IP formula (from CLAUDE.md)
def expected_vlan7_ip(fzg: int) -> str:
    octet3 = 128 + (fzg // 2)
    octet4 = (128 if fzg % 2 == 1 else 0) + 2
    return f"172.19.{octet3}.{octet4}/17"

# CCU hostname expected (from CCU IP — third octet of IP is the box number)
def expected_ccu_hostname(ccu_ip: str) -> str:
    third_octet = ccu_ip.split(".")[2]
    return f"box1-t{third_octet}"

# train_id template expected
def expected_train_id_line(fzg: int) -> str:
    return f"{{%- set train_id = {fzg} -%}}"
```

### Step 3 — Diff and verdict

For each fact, compute `verdict ∈ {pass, fail, warn}`. Apply the expected-drift rules from "Verdict logic" above. Compute aggregate verdict.

### Step 4 — Append to log

Append one line to `.claude/logs/state-inventory-<fzg>.jsonl`:

```json
{"ts":"<now>","ccu_ip":"<ip>","fzg":<n>,"verdict":"<aggregate>","facts_summary":{"passed":11,"warned":1,"failed":0},"btrfs_subvol_id":314,"drift_from_last_session":["tftp_ct_helper_rule"]}
```

This log feeds the `delta_from_last_session` block on the *next* invocation.

### Step 5 — Emit JSON (or human-readable) output

`--json` output goes to stdout. Engineers running interactively get a table:

```
─── DOSTO State Inventory — Fzg 132 / 10.179.10.1 ───
CCU hostname:           box1-t10  ✓ (matches IP)
Uptime:                 5h 54m
btrfs active subvol:    /.snapshots/run1 (id 314)  ✓ (unchanged from last session)
OBN patches:            8/8 ✓ (persisted)
NDSU filename:          nd-systemupdate.sh.dont  ✓ (auto-update blocked)
train_id template:      {%- set train_id = 132 -%}  ✓
vlan7 live IP:          172.19.194.2/17  ✓
vlan7 nmconnection:     172.19.194.2/17  ✓
TFTP module:            loaded  ✓
TFTP CT helper rule:    🟡 MISSING (re-apply before AP firmware push)
tftp_allowed ipset:     18 entries  ✓

Verdict: 🟡 expected_drift — 11 pass, 1 warn (TFTP helper rule lost on reboot,
runtime fix needed). Not blocking.

Next action: Run /dosto-tftp-helper-check 10.179.10.1 --apply-runtime.
```

## What this skill deliberately does NOT do

- ❌ **Apply any fix.** Read-only — surfaces drift, doesn't remediate. Caller decides.
- ❌ **Compare against a remote reference.** All expectations are computed from `<fzg>` + the per-series formula, OR loaded from `--expected <path>`. No call-home.
- ❌ **Replace `--check` modes of individual skills.** This is a fast aggregate sanity check; it does not do the deep verification a `dosto-obn-patches --check` does (e.g. cross-check A/B/C). Use this for "is the state today the state we expected"; use the per-skill `--check` modes for "what specifically is wrong."
- ❌ **Write to `fleet-status.md`.** Orchestrator-as-sole-writer per the contract.
- ❌ **SSH to anything other than the CCU.** Doesn't probe switches or APs.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — fact 10/11/12 source of truth + the runtime-fix recipe when fact 11 is missing.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — fact 4/5 source of truth.
- [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md) — fact 7 deep-check skill.
- [`dosto-vlan7-config`](../dosto-vlan7-config/SKILL.md) — fact 8/9 deep-check skill.
- [`dosto-commission-train`](../dosto-commission-train/SKILL.md) — calls this skill at the start of stage 1 (`initial_diagnostics`) before invoking the per-skill deep checks.

## Reference

- handoff lessons 11, 13 (TFTP helper, AP stuck-state)
- handoff "Open questions" → R&D nag list (Puppet TFTP fix, OBN upstream)
- `dosto-tftp-helper-check` SKILL.md → "iptables-nft caveat"
- `dosto-obn-patches` SKILL.md → "Cross-checks (always report alongside the bug table)"
