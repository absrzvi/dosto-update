# dosto-sw-config-update-batch — Design

**Date:** 2026-05-12
**Author:** Abbas Rizvi (with Claude)
**Status:** Design — pending review
**Related:** [`.claude/skills/dosto-sw-config-update/SKILL.md`](../../../.claude/skills/dosto-sw-config-update/SKILL.md), OBN `/usr/share/obn/cli/update.py`, OBN `/usr/share/obn/lib/tree.py`

## Problem

Pushing switch configs to a DOSTO consist one-at-a-time takes ~3 hours for ~15 switches (Fzg 132 reference run, 2026-05-12). The dominant per-switch cost is `poll_completion` — waiting for the switch to reboot and OBN to confirm `validate ✓`. Each switch sits idle for ~5-8 min in that stage.

OBN's CLI (`obn update c sw`, `obn update c all`) already implements parallel batching internally — `OBNTree.calculate_parallel_update_order()` yields leaf-sets and `process_batch()` fans them out via `ThreadPoolExecutor`. This batching path has not been used operationally because the team standardised on single-switch-serial after the TFTP conntrack-helper outage (handoff lesson 11). With the TFTP helper now patched (Bug 5 + `nf_conntrack_tftp` loaded), and the RSTP root pinned to the CCU-adjacent switch (so no leaf reboot can trigger root re-election), the safety rationale for serial no longer applies to switch config pushes.

Expected speedup: 3 hours → ~30-45 min for a full 6-car consist.

## Goals

1. Drive switch config pushes in parallel batches using OBN's built-in parallel scheduler — no re-implementation.
2. Discover what needs pushing automatically (`obn validate -t sw`) and present an execution plan for engineer approval.
3. Support two run modes: **auto** (entire fleet via `obn update c sw`) and **manual** (engineer-supplied IP list, scheduled in OBN-leaf-first order).
4. Wrap OBN's run with pre-flight checks, per-batch progress events, and post-run verification — without losing failure attribution.
5. Stop on engineer ack when any switch fails to flip to ✓ within budget.

## Non-goals

- Per-switch `verify_reboot_started` hard-fail. Lost in favour of batch-boundary detection: a switch that TFTP'd config but didn't reboot will still show `✗` in the post-batch `obn validate`. Detection lag is one batch cycle (~10 min) instead of 60 seconds. Engineer accepted this trade-off.
- Capping OBN's `max_workers`. OBN's default (`len(batch)`) is used unmodified — 12 leaves rebooting simultaneously on a 6-car DOSTO is acceptable.
- AP config pushes. Different skill. APs still single-AP-serial.
- Switch firmware pushes. Different skill (`dosto-sw-firmware-update`). Firmware push semantics differ — out of scope.
- Coupled-consist scenarios. Same Bug 6 patch requirement as existing skill applies, but no new logic.

## Architecture

```
                        engineer invokes
                              │
                              ▼
              ┌──────────────────────────────┐
              │  dosto-sw-config-update-batch │
              │       --prepare | --execute   │
              │       [--switches ip,ip,...]  │
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  Stage 1: pre-flight         │  (one SSH heredoc to CCU)
              │   - tftp helper              │
              │   - obn patches (1-8)        │
              │   - fzg-id-check             │
              │   - l2-health verdict        │
              │   - obn discover + obn report│
              └──────────────┬───────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  Stage 2: scope discovery    │
              │   - obn validate -t sw       │
              │   - filter to ✗ rows         │
              │   - if --switches: intersect │
              │   - call OBNTree to compute  │
              │     leaf-first batch plan    │
              │   - capture RSTP root MAC    │
              └──────────────┬───────────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
          --prepare: print          --execute:
          plan + recipe,            GATE 1 ack
          exit 0                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  Stage 3: run                │
                          │   auto: obn update c sw      │
                          │   manual: obn update c <ip>  │
                          │           per OBN-computed   │
                          │           batch              │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  Stage 4: per-batch monitor  │
                          │   - tail journalctl for RRQs │
                          │   - every 60s obn discover + │
                          │     obn validate -t sw       │
                          │   - emit per-switch flip ✓   │
                          │   - 20 min budget per batch  │
                          └──────────────┬───────────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                       all ✓ in batch        any ✗ after 20 min
                              │                     │
                              │                     ▼
                              │            GATE 2: engineer picks
                              │             (a) abort
                              │             (b) extend-poll batch
                              │             (c) retry failed
                              │             (d) skip + continue
                              │                     │
                              └──────────┬──────────┘
                                         ▼
                          ┌──────────────────────────────┐
                          │  Stage 5: next batch or done │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  Stage 6: post-run verify    │
                          │   - rstp root unchanged      │
                          │   - all targeted switches ✓  │
                          │   - dosto-l2-health rerun    │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                                  completed | aborted
```

## Components

### 1. Pre-flight (Stage 1)

Same precondition surface as `dosto-sw-config-update`, single-pass SSH heredoc to CCU:

| Check | Failure verdict |
|---|---|
| `nf_conntrack_tftp` loaded + iptables CT helper rule on udp/69 | `preconditions_unmet:tftp_helper` |
| OBN patches 1-8 all present in `/usr/share/obn/lib/...` | `preconditions_unmet:obn_patches` |
| `dosto-fzg-id-check` verdict `all_match` | `preconditions_unmet:fzg_id` |
| `dosto-l2-health` recent verdict healthy | `fabric_unhealthy` |
| `obn discover && obn report` succeed; OBNTree buildable | `obn_tree_unbuildable` |

All aborts are pre-Gate-1, no destructive action yet.

### 2. Scope discovery (Stage 2)

Read `obn validate -t sw` after the fresh `obn discover && obn report` from Stage 1. Build the candidate list:

- Switches with config column `✗` or `current (staged) ✗`.
- If `--switches A,B,C` supplied: intersect with that set. Refuse if any named IP isn't in the validate output (`switch_not_found`).
- If candidate set is empty: emit `verdict: already_at_target_config`, exit 0.

Compute the parallel batch plan by invoking OBN's own `OBNTree.calculate_parallel_update_order()` and filtering to candidate set. We do this via a small Python one-liner shell-out:

```bash
ssh_ccu 'sudo /usr/share/obn/venv/bin/python -c "
import sys, json
sys.path.insert(0, \"/usr/share/obn\")
from lib.configuration import Configuration
from cli.update import get_devices, get_targeted_devices, get_updatable_devices
from lib.tree import OBNTree
cfg = Configuration()
devices = get_devices(cfg.report_file, include_ccu=True)
tree = OBNTree.create_tree(devices)
batches = []
for batch in tree.calculate_parallel_update_order():
    batches.append(sorted([d.ip for d in batch]))
print(json.dumps(batches))
"'
```

If `--switches` was passed, post-filter each batch to the named IPs. Drop empty batches.

Also capture in Stage 2:
- RSTP root MAC, by SSH'ing into one neighbour switch and reading `show spanning-tree`.
- Total switch count, total-needing-push count.

### 3. Run (Stage 3) — two modes

**Auto mode** (no `--switches` flag, all `✗` switches in scope):

```bash
ssh_ccu 'sudo obn update c sw 2>&1 | tee /tmp/obn-update-c-sw-<timestamp>.log'
```

OBN does the batching itself, including the hard-coded `time.sleep(5 * 60)` between batches. The tee log is read by Stage 4 monitor.

**Manual mode** (`--switches A,B,C`):

The batches we computed in Stage 2 are subsets of the full OBN batches but in the same leaf-first order. We drive them one batch at a time:

```bash
# For each batch [ip1, ip2, ip3]:
ssh_ccu '
  ( sudo obn update c '"$ip1"' & PID1=$!
    sudo obn update c '"$ip2"' & PID2=$!
    sudo obn update c '"$ip3"' & PID3=$!
    wait $PID1; wait $PID2; wait $PID3
  ) 2>&1 | tee /tmp/obn-update-c-batch-<n>-<ts>.log'
sleep 300  # match OBN's 5-min inter-batch settle
```

This uses bash backgrounding of independent `obn update c <ip>` invocations from a single SSH session. Each is independent because OBN has no cross-process locks (verified by grep on `/usr/share/obn` 2026-05-12).

We do **not** call `obn update c <ip1>,<ip2>,<ip3>` as a single comma-list — OBN's CLI doesn't accept comma lists for `target`. We do **not** chain with `;` because that's serial. Backgrounding is the only way.

### 4. Per-batch monitor (Stage 4)

Runs in parallel with Stage 3's `tee`. For each in-flight batch:

- Capture `PRE_TS` before `obn update c` invocation.
- Every 5s for the first 90s: grep `journalctl -u tftpd-hpa --since "$PRE_TS"` for `RRQ from <ip>` for each batch member. Emit `rrq_seen` event per switch.
- After RRQs (or 90s elapsed): every 60s run `sudo obn discover && sudo obn validate -t sw` and parse the config column for each batch member. Emit `flipped_to_target` per switch as it transitions to ✓.
- 20-min wall-clock budget per batch (matches existing skill).
- When all batch members are ✓ OR budget exceeded: exit monitor.

The monitor must coexist with OBN's own internal `process_batch` ThreadPoolExecutor — they're not coupled. Our monitor is read-only.

### 5. Gate 2 — failure pause

If any batch finishes its 20-min budget with one or more switches still `✗`:

```
batch 1 incomplete after 20 min:
  ✓ 10.179.19.181 (D1)  flipped at +9m22s
  ✓ 10.179.19.183 (F1)  flipped at +9m48s
  ✗ 10.179.19.185 (B3)  RRQ seen at +12s, switch DOWN at +35s, never returned

Engineer choice:
  (a) abort entire run — leaves remaining batches unrun
  (b) extend-poll this batch by another 20 min
  (c) retry the failed switch only (single SSH-reboot + obn update c re-fire)
  (d) skip the failed switch, continue to next batch (note: marks run as partial)

Three consecutive failures across batches → automatic abort (Gate 3-equivalent).
```

### 6. Post-run verify (Stage 6)

- RSTP root MAC unchanged vs. Stage 2 baseline. By invariant this should always hold — if it doesn't, fabric anomaly, emit `gate_4_awaiting_ack` (engineer reviews).
- All originally-targeted switches now `✓` in `obn validate -t sw` after a final `obn discover && obn report`.
- Run `dosto-l2-health` (quick mode). Verdict must be healthy.
- Emit `completed` with full timing breakdown per batch.

## Output modes

Same family pattern as the existing skills.

### `--prepare --json`

```json
{
  "skill": "dosto-sw-config-update-batch",
  "mode": "prepare",
  "schema_version": "1",
  "verdict": "ready_to_push|already_at_target_config|preconditions_unmet|...",
  "raw": {
    "ccu_ip": "10.179.19.1",
    "fzg": 134,
    "switches_total": 18,
    "switches_needing_push": 12,
    "user_supplied_switches": null,
    "batches": [
      {"index": 1, "switches": ["10.179.19.181", ...], "type": "leaves"},
      {"index": 2, "switches": ["10.179.19.190", ...], "type": "centres"},
      {"index": 3, "switches": ["10.179.19.195"], "type": "root"}
    ],
    "rstp_root_mac_pre": "a0:59:3a:aa:bb:cc",
    "tftp_helper_verdict": "all_present",
    "obn_patches_verdict": "all_persisted",
    "l2_health_verdict": "healthy",
    "estimated_wall_clock_seconds": 2400
  },
  "recipe": "..."
}
```

### `--execute --json` event stream

One event per line. New events vs. single-switch skill:

```json
{"event":"started","timestamp":"...","mode":"auto","switches_in_scope":12}
{"event":"pre_check_passed","timestamp":"...","rstp_root_mac_pre":"..."}
{"event":"plan","timestamp":"...","batches":[...]}
{"event":"gate_1_awaiting_ack","timestamp":"...","blast_radius":"12 switches will reboot in 3 waves over ~35 min; trunk fabric disrupted per wave; RSTP root pinned at <mac> so no root churn expected"}
{"event":"gate_1_acked","timestamp":"..."}
{"event":"batch_started","timestamp":"...","batch":1,"switches":["10.179.19.181","..."]}
{"event":"rrq_seen","timestamp":"...","batch":1,"switch":"10.179.19.181","seconds_since_batch_start":8}
{"event":"flipped_to_target","timestamp":"...","batch":1,"switch":"10.179.19.181","seconds_since_batch_start":562}
{"event":"batch_completed","timestamp":"...","batch":1,"all_ok":true,"elapsed_seconds":598}
{"event":"batch_settle","timestamp":"...","seconds":300}
{"event":"batch_started","timestamp":"...","batch":2,"switches":[...]}
... (repeat) ...
{"event":"gate_2_awaiting_ack","timestamp":"...","batch":2,"failed_switches":["10.179.19.185"],"options":["abort","extend-poll","retry","skip"]}
{"event":"post_check_passed","timestamp":"...","rstp_root_mac_post":"a0:59:3a:aa:bb:cc","root_unchanged":true,"l2_health_post":"healthy"}
{"event":"completed","timestamp":"...","total_elapsed_seconds":2280,"batches_run":3,"switches_pushed":12,"switches_failed":0,"final":true}
```

### `--prepare` shell recipe

When verdict is `ready_to_push`, print a runnable recipe an engineer could execute by hand instead of running `--execute`. Recipe wraps the same Stage 1-6 flow with `set -euo pipefail` and inline error handling, exit codes aligned with verdict taxonomy.

## What this skill deliberately does NOT do

- Push to non-leaf switches without going through the OBN-computed batch order (OBN handles leaf-first naturally; engineer can't pass `--allow-non-leaf`).
- Skip pre-flight (the 5 checks are not optional).
- Cap OBN's parallelism. OBN decides batch width.
- Wrap firmware pushes. Different skill.
- Auto-retry failed switches. Engineer ack required (Gate 2).
- Continue after 3 consecutive failures.
- Run if `dosto-l2-health` is unhealthy.

## Failure mode catalogue

| Symptom | Verdict / event | Behaviour |
|---|---|---|
| TFTP helper missing | `preconditions_unmet:tftp_helper` | Abort before any push |
| OBN patches not all-present | `preconditions_unmet:obn_patches` | Abort |
| fzg-id-check fails | `preconditions_unmet:fzg_id` | Abort — rendered cfgs would be wrong |
| l2-health unhealthy | `fabric_unhealthy` | Abort |
| `obn discover` fails | `obn_tree_unbuildable` | Abort — possible Bug 6 if coupled |
| `--switches` lists IP not in validate | `switch_not_found` | Abort, name the offender |
| All target switches already ✓ | `already_at_target_config` | No-op, exit 0 |
| Batch has 1+ ✗ after 20 min | `gate_2_awaiting_ack` | Engineer picks (a/b/c/d) |
| 3 consecutive batch failures | `aborted:repeated_failures` | Auto-abort |
| RSTP root MAC changed post-run | `gate_4_awaiting_ack` | Engineer reviews — should not happen by invariant |
| Post-run l2-health unhealthy | `gate_4_awaiting_ack` | Engineer reviews |

## Risks

1. **OBN's internal `process_batch` ThreadPoolExecutor crashes mid-batch** — losing some thread results. Our Stage 4 monitor is the only source of truth; OBN's exit code is supplementary. Mitigation: we trust `obn validate` post-batch, not OBN's stdout.
2. **The 5-min hardcoded inter-batch sleep is too short** for switches that reboot slowly. Mitigation: our 20-min budget per batch is the actual gate, OBN's sleep is just a floor.
3. **`obn discover` running concurrently with OBN's own internal flow** could race. Mitigation: there are no locks (verified) and `obn discover` is idempotent. Worst case the post-batch read is slightly stale; the next 60s poll re-reads.
4. **Manual mode bash backgrounding swallows individual command exit codes** unless we capture `$?` per `wait`. Mitigation: capture them explicitly.
5. **Engineer runs this while another OBN operation is in flight from another SSH session** — race. Mitigation: Stage 1 pre-flight checks for any `obn` process other than the API/telemetry daemons; if found, abort with `preconditions_unmet:obn_busy`.

## Testing strategy

Validation must happen on a real consist with multiple `✗` switches. Three-phase rollout:

1. **First run: small manual batch on a known-good train**, 2-3 leaves. Confirms the parallel mechanism works, RSTP stays pinned, no surprises.
2. **Second run: auto mode on a different known-good train**, full fleet. Confirms `obn update c sw` end-to-end vs. our wrapper's verification matches.
3. **Third run: production use during a real commissioning day.** Compare wall-clock vs. historical serial baseline.

Each run captures: total wall-clock, per-batch timing, RRQ-to-flip latency per switch, RSTP root MAC pre/post, l2-health pre/post.

## Integration with `dosto-commission-train`

This skill **replaces the per-switch loop at the config-push stage of `dosto-commission-train`** as the default path. The single-switch skill (`dosto-sw-config-update`) stays in the tree — not deprecated, not removed — for two reasons:

1. **Escape hatch**: `dosto-commission-train` accepts a new flag `--legacy-serial-sw-config` that falls back to looping the single-switch skill leaf-by-leaf. Use when a specific train shows pathological parallel-batch behaviour, or as a temporary mitigation before a bug-fix is rolled out.
2. **Surgical use**: when scope is genuinely one switch (e.g. "I just re-imaged D2, push config to that one"), the engineer invokes `dosto-sw-config-update` directly. The batch skill would be overkill — pre-flight + tree-compute + monitor scaffolding for a 1-switch run is wasted overhead.

The skill lives at `.claude/skills/dosto-sw-config-update-batch/SKILL.md`, sibling to the single-switch skill.

## Dry-run mode

In addition to `--prepare` (read-only, prints plan + recipe) and `--execute` (drives the run), the skill supports `--dry-run-execute`:

- Runs all of Stage 1 (pre-flight) and Stage 2 (scope discovery + batch plan) for real.
- Emits the **full JSON event stream** that Stage 3-6 *would* produce, with simulated timings (mean per-batch budget, no per-switch RRQ events, no actual `obn update c` invocation).
- Asks for Gate 1 ack the same way `--execute` does — but on ack, prints "would invoke `obn update c sw` here" and skips to the simulated post-run summary.
- Useful for: first-pass review of the plan before committing to a real run, regression-testing the event schema, and training new engineers on what the event stream looks like.

`--dry-run-execute` is non-destructive — no `obn update c`, no SSH-into-switch reboots, no `obn discover` after the initial Stage 1 freshening.

## Open questions

None remaining for the design phase. Implementation will surface its own.
