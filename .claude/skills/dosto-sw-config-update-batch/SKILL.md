---
name: dosto-sw-config-update-batch
description: Push DOSTO switch configs in OBN-driven parallel batches. Auto mode wraps `obn update c sw` for full-fleet leaf-first parallel push; manual mode takes --switches A,B,C and runs OBN's leaf-first batches scoped to those IPs. Default replacement for the single-switch config skill inside dosto-commission-train (escape hatch: --legacy-serial-sw-config). Estimated wall-clock: ~30-45 min for a 6-car DOSTO vs ~3 hours single-switch serial. Validated empirically on Fzg <TBD>. Pairs with dosto-tftp-helper-check, dosto-obn-patches, dosto-fzg-id-check, dosto-l2-health.
---

# DOSTO Switch Config Update — Batched

This skill drives switch config pushes in OBN-leaf-first parallel batches by wrapping OBN's own built-in parallel scheduler. The single-switch skill ([`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md)) stays available as an escape hatch and for surgical one-switch pushes.

**Why this exists**: a 6-car DOSTO with 15-18 switches takes ~3 hours single-switch-serial for config push. OBN's `obn update c sw` already implements parallel batching: `/usr/share/obn/cli/update.py` calls `OBNTree.calculate_parallel_update_order()` then drives each batch through a `ThreadPoolExecutor(max_workers=len(devices))`. With the TFTP conntrack helper now patched (Bug 5 + `nf_conntrack_tftp`) and the RSTP root pinned to the CCU-adjacent switch (so leaf-batch reboots cannot trigger root re-election), the safety rationale for single-switch-serial no longer applies. Wrapping `obn update c sw` with pre-flight + per-batch monitor + post-run verification gets us to ~30-45 min wall-clock.

## Modes

| Mode | Trigger | Behaviour |
|---|---|---|
| `--prepare` (default) | no other flag | Read-only: preflight + scope discovery + batch plan + recipe. Exit 0. |
| `--dry-run-execute` | `--dry-run-execute` flag | All of `--prepare` plus a simulated event stream from a hypothetical `--execute`. No destructive ops. |
| `--execute --auto` | `--execute` (default sub-mode) | Wraps `obn update c sw`. OBN drives batching. Engineer can opt out via `--switches`. |
| `--execute --switches A,B,C` | `--execute` + `--switches` | Manual mode: filters OBN's leaf-first plan to engineer-named IPs, runs each batch via backgrounded `obn update c <ip> &` calls inside one SSH session. |

## Preconditions (skill aborts if any are not met)

| Precondition | Why | Failure verdict |
|---|---|---|
| `nf_conntrack_tftp` kernel module loaded | TFTP transfer path. | `preconditions_unmet:tftp_helper` |
| iptables raw PREROUTING has CT helper rule on udp/69 | Without it, single-switch and batch pushes silently fail on the data return flow. | `preconditions_unmet:tftp_helper_rule` |
| OBN patches present (Bugs 2, 5, 6, 7, 8 minimum) | All on the config-push code path. | `preconditions_unmet:obn_patches` |
| No active operator-driven `obn` CLI process | Avoid stomping. `serve-api`, `telemetry`, `user-count`, `wifi-status`, `discover-schedule` are background services and don't count. | `preconditions_unmet:obn_busy` |
| `obn discover && obn report` succeed | OBNTree must be buildable. | `preconditions_unmet:obn_discover` or `scope_aborted:obn_tree_unbuildable` |
| **Delegated** — caller must have run `dosto-fzg-id-check` (verdict `all_match`) and `dosto-l2-health` (healthy) | Wrong fzg-id → wrong hostname in rendered cfg. Unhealthy fabric → masks post-batch RSTP convergence check. | enforced by orchestrator (`dosto-commission-train`); standalone runs may pass `SKIP_DELEGATED=1` to acknowledge |
| `--switches` IPs all known to validate | Engineer typo guard. | `scope_aborted:switch_not_found` |

## State machine

```
preflight → scope (compute OBN-leaf-first batches)
   ↓
GATE 1: engineer acks blast radius (N switches across M batches over ~T minutes)
   ↓
for batch in batches:
   batch_started → dispatch (auto: obn update c sw; manual: backgrounded obn update c <ip> &)
       ↓
   monitor: 90s RRQ window then 60s validate poll, 20-min total budget
       ├── all flip ✓ → batch_completed → batch_settle (300s)
       └── budget exhausted → GATE 2 (abort | extend-poll | retry | skip)
                                                ↓
                                  3 consecutive non-success outcomes → auto-abort
   ↓
post-run verify (RSTP root unchanged + all targets ✓)
   ├── ok → post_check_l2_health_required → post_check_passed → completed
   └── anomaly → GATE 4 (engineer reviews)
```

There is no Gate 3. The single-switch skill's `verify_reboot_started` hard-fail is intentionally NOT replicated here — failures surface at batch boundary (≤10 min lag) instead of per-switch (60s lag). This was an explicit trade-off when the spec was approved.

## Output (`--execute --json` event stream)

One JSON event per line. Schema mirrors the single-switch skill where possible. Key events:

| Event | Phase | Notable fields |
|---|---|---|
| `preflight_started` | 1 | `ccu_ip` |
| `preflight_check_ok` / `preflight_check_failed` | 1 | `check`, `reason` |
| `pre_check_passed` / `preflight_aborted` | 1 | `reason` (if aborted) |
| `scope_started` | 2 | `mode` (auto / manual) |
| `scope_inventory` | 2 | `switches_total`, `switches_needing_push` |
| `scope_targets` | 2 | `switches` (csv) |
| `plan` | 2 | `batches` (JSON array of arrays), `rstp_root_mac_pre`, `targets_csv` |
| `scope_aborted` | 2 | `reason` (`obn_discover_or_report_failed`, `switch_not_found`, `obn_tree_unbuildable`) |
| `gate_1_awaiting_ack` | 3 | `blast_radius` |
| `auto_mode_kickoff` / `manual_mode_kickoff` | 3 | `log_file`, `rstp_root_mac_pre` |
| `obn_update_started` (auto only) | 3 | `pid` (remote OBN process) |
| `batch_started` | 3 | `batch`, `switches` |
| `batch_dispatched` (manual only) | 3 | `batch`, `local_pid` |
| `rrq_seen` | 5 | `batch`, `switch`, `seconds_since_batch_start` |
| `flipped_to_target` | 5 | `batch`, `switch`, `seconds_since_batch_start` |
| `batch_completed` | 5 | `batch`, `all_ok` (true/false), `elapsed_seconds`, `failed_switches` (if any) |
| `gate_2_awaiting_ack` | 5 | `batch`, `consecutive_failures`, `options` |
| `batch_skipped` / `batch_extending_poll` | 5 | `batch` |
| `batch_settle` | 5 | `seconds` |
| `manual_aborted` / `auto_aborted` | 5 | `reason` |
| `rstp_root_unchanged` | 6 | `rstp_root_mac` |
| `all_targets_at_target_config` | 6 | `count` |
| `post_check_l2_health_required` | 6 | `note` |
| `post_check_passed` | 6 | — |
| `gate_4_awaiting_ack` | 6 | `reason` (`rstp_root_changed`, `targets_still_failing`), `switches` (if applicable) |
| `completed` | — | `total_elapsed_seconds`, `batches_run`, `switches_pushed`, `switches_failed`, `final: true` |

## Scripts

| Script | Stage | Purpose |
|---|---|---|
| `scripts/_lib.sh` | shared | SSH wrappers, JSON event emitter, RSTP MAC probe. Sourcing sets `set -euo pipefail`. |
| `scripts/01_preflight.sh` | 1 | TFTP helper module + iptables rule, OBN patch markers (Bug 2/5/7), `obn busy` check, fresh `obn discover` |
| `scripts/02_scope.sh` | 2 | `obn discover && obn report`, parse pipe-table `obn validate -t sw` (ANSI-strip first), filter ✗ rows, intersect with `--switches`, compute OBN-leaf-first batch plan via shell-out to `OBNTree.calculate_parallel_update_order()` |
| `scripts/03_execute_auto.sh` | 3 (auto) | Kicks off `obn update c sw` via `nohup` on the CCU; iterates pre-computed batches as the monitor reporting frame |
| `scripts/04_execute_manual.sh` | 3 (manual) | Per-batch, backgrounds N `obn update c <ip> &` inside one SSH session; Gate 2 handling with engineer choice via `GATE_RESUME` env var |
| `scripts/05_monitor_batch.sh` | 5 (shared) | 90s journalctl RRQ window + 60s `obn validate -t sw` poll cadence (20-min budget); emits per-switch flipped events |
| `scripts/06_postcheck.sh` | 6 | RSTP root MAC unchanged check, final `obn discover && obn report && validate`, gate_4 if any target still ✗ |
| `scripts/99_dry_run_simulate.sh` | dry-run | Emits the full simulated event stream — no destructive ops, no `obn update c`, no CCU writes |

## Invocation flow (what the calling agent does)

**For `--prepare`:**
1. Run `01_preflight.sh <ccu>`.
2. If `pre_check_passed`, run `02_scope.sh <ccu> [<switches_csv>]`.
3. Capture the `plan` event. Print human-readable summary (switch count, batch table, estimated wall-clock = `BATCH_COUNT × (avg_flip_secs + 300)`).
4. Exit. No Gate 1 ack required.

**For `--dry-run-execute`:**
1. Run preflight + scope as above.
2. Pass `batches_json`, `rstp_root_mac_pre`, `targets_csv` into `99_dry_run_simulate.sh`.
3. Print the full simulated event stream.

**For `--execute`:**
1. Run `01_preflight.sh`. Abort if not `pre_check_passed`.
2. Run `02_scope.sh`. Abort if `scope_aborted`; no-op if `scope_complete:already_at_target_config`.
3. Emit `gate_1_awaiting_ack` with blast-radius text built from the plan (N switches across M batches over ~T minutes; RSTP root MAC pinned at `<mac>`). **Wait for engineer ack.**
4. Dispatch `03_execute_auto.sh` (auto) or `04_execute_manual.sh` (manual). The dispatched script invokes `05_monitor_batch.sh` per batch.
5. On `gate_2_awaiting_ack`: surface to engineer with the four options. Re-dispatch with `GATE_RESUME` env set to engineer's choice. (Standalone shell use can `export GATE_RESUME=...` before invoking.)
6. After all batches done: run `06_postcheck.sh`.
7. On `gate_4_awaiting_ack`: surface to engineer for review.
8. Emit final `completed` event.

## Gate 2 — failure semantics

When a batch finishes its 20-min budget with one or more switches still ✗:

| Engineer choice | Behaviour | Counts toward 3-strike auto-abort? |
|---|---|---|
| `abort` | Skill exits 6 immediately, no further batches | n/a (already exiting) |
| `extend-poll` (default if `GATE_RESUME` unset) | Re-run the monitor with another 20-min budget. If still fails: skill exits 7. If succeeds: counter resets. | Success resets; failure exits |
| `retry` | Treated the same as `extend-poll` in this implementation (extension only — no re-firing of `obn update c`) | Same as extend-poll |
| `skip` | Move on to next batch. Skipped switches will be reported as `failed` in the final `completed` event. | **Yes** — counts toward 3 |

**3 consecutive non-success outcomes → auto-abort with `manual_aborted:reason=three_consecutive_batch_failures`.** A `skip` counts here: three skipped batches in a row will trip the abort. Engineer-chosen skips remain a deliberate choice for the next two; the third one moves the run into auto-abort territory.

## What this skill deliberately does NOT do

- Touch any switch outside the OBN leaf-first plan computed by OBN itself.
- Cap OBN's `max_workers` — OBN decides batch width.
- Push firmware. Different skill (`dosto-sw-firmware-update`).
- Push APs. Different skill family.
- Auto-retry by re-firing `obn update c` — only an extend-poll on the original RRQ window.
- Continue after 3 consecutive batch failures.
- Implement `verify_reboot_started` per switch. Detected at batch boundary instead.
- Re-implement OBN's parallel scheduler. We wrap it.
- Modify any OBN source. The hand-patches are managed by `dosto-obn-patches`.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — precondition.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — precondition. Bugs 2, 5, 6, 7, 8 relevant.
- [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md) — delegated precondition (orchestrator-enforced).
- [`dosto-l2-health`](../dosto-l2-health/SKILL.md) — delegated precondition + post-run rerun (orchestrator-enforced).
- [`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md) — escape hatch / surgical-one-switch tool.
- [`dosto-commission-train`](../dosto-commission-train/SKILL.md) — orchestrator. Calls this skill by default at the switch-config-push stage. Engineer flag `--legacy-serial-sw-config` falls back to looping the single-switch skill.

## Reference

- **Spec**: [`docs/superpowers/specs/2026-05-12-dosto-sw-config-update-batch-design.md`](../../../docs/superpowers/specs/2026-05-12-dosto-sw-config-update-batch-design.md)
- **Plan**: [`docs/superpowers/plans/2026-05-13-dosto-sw-config-update-batch.md`](../../../docs/superpowers/plans/2026-05-13-dosto-sw-config-update-batch.md)
- **OBN source**: `/usr/share/obn/cli/update.py:212-263` (`update()` function with leaf-peel + `ThreadPoolExecutor`), `/usr/share/obn/lib/tree.py` (`OBNTree.calculate_parallel_update_order`).
- **Verified 2026-05-12 (Fzg 134 / box1-t19)**: no locks in OBN (`grep -rn 'flock|FileLock|threading.Lock' /usr/share/obn` returned 0); only `serve-api` and `telemetry` processes resident as foreground OBN; `cli/update.py` already uses `ThreadPoolExecutor(max_workers=len(devices))` per batch with `time.sleep(5 * 60)` inter-batch.
- **Validated end-to-end on Fzg <TBD>**: pending Task 12 of the implementation plan, awaiting a patched train.
