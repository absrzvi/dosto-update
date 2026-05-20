---
name: dosto-commission-train
description: Orchestrates the full per-train DOSTO commissioning pipeline by sequencing the lower-level per-device skills. Use when commissioning one train end-to-end, when a per-train subagent needs to walk the 19-stage flow, or when resuming a paused mid-rollout train via --resume. Walks the canonical 19-stage pipeline from the subagent-report contract, emits subagent-report-shaped JSON at every stage transition for the orchestrator to consume, and halts at the five contract approval gates (Gate 1 promote_snapshot, Gate 2 safe_reboot, Gate 3 obn_update_c, Gate 4 obn_update_f, Gate 5 device_count_mismatch) for human approval. Single-train scope only — the orchestrator handles multi-train fan-out by spawning one per-train subagent per concurrent train. --resume picks up from a stored stage marker. --dry-run runs every per-device skill in --prepare mode only. Invoked BY the per-train subagent, not directly by the orchestrator.
---

# DOSTO Commission Train

This skill is the **canonical commissioning pipeline** for a single DOSTO train. It sequences the lower-level per-device skills into the 19-stage flow defined by [`subagent-report.md`](../../contracts/subagent-report.md), emits structured JSON reports at every stage transition, and halts at the five contract approval gates so the human-in-the-loop can authorise irreversible actions.

It is **invoked by the per-train subagent** (see [`.claude/agents/dosto-train-worker.md`](../../agents/dosto-train-worker.md)), not directly by the top-level orchestrator. The orchestrator spawns one subagent per train using the `Agent` tool — multiple subagents run in parallel, each driving its own train through this skill independently.

## Architecture

```
You (top-level orchestrator session)
  │
  ├─► Agent(subagent_type=dosto-train-worker, prompt="...Fzg 132...") ─┐
  ├─► Agent(subagent_type=dosto-train-worker, prompt="...Fzg 133...") ─┤  parallel
  ├─► Agent(subagent_type=dosto-train-worker, prompt="...Fzg 148...") ─┤
  └─► Agent(subagent_type=dosto-train-worker, prompt="...Fzg 130...") ─┘
                       │
                       ▼ each subagent runs its own session, invokes:
              /dosto-commission-train --ccu-ip <ip> --fzg <N> ...
                       │
                       ▼ which sequences:
              /dosto-device-discovery → /dosto-obn-patches → /dosto-fzg-id-check
                                       → /dosto-vlan7-config → /dosto-tftp-helper-check
                                       → /dosto-ap-config-update (per AP)
                                       → /dosto-ap-firmware-update (per AP)
                                       → /dosto-sw-firmware-update (per switch, leaf-first)
                                       → /dosto-sw-config-update-batch --execute --auto
                                         (legacy single-switch fallback: --legacy-serial-sw-config)
                                       → /dosto-l2-health
                                       → /dosto-l2-report
```

This skill is **single-train scope**. Multi-train fan-out is the orchestrator's responsibility, achieved by spawning N subagents in a single `Agent` tool message (the SDK runs them concurrently).

## When to use

- **Per-train subagent's main entry point**, every commissioning session.
- **Resume after a train pause** (cellular dropped, train powered off, approval pending) — `--resume <stage_id>`.
- **Engineer dry-run before a real commissioning** — `--dry-run` runs every per-device skill in `--prepare` mode, no state changes.
- **Never invoked directly by the orchestrator** — the orchestrator spawns subagents which invoke this skill. Engineers can invoke it directly for debugging or training.

## Inputs

| Flag | Type | Required | Notes |
|---|---|---|---|
| `--ccu-ip <ip>` | string | yes | e.g. `10.179.10.1` |
| `--fzg <int>` | integer | yes | e.g. `132`. Used by `dosto-fzg-id-check`, `dosto-vlan7-config`, and `dosto-obn-patches --persist` fold-in. |
| `--train-number <str>` | string | yes | e.g. `4736-104`. For fleet-status row identification. |
| `--consist <4-car|6-car>` | enum | yes | Affects expected device counts (12+16 for nv4, 18+24 for nv6). |
| `--resume <stage_id>` | enum | no | Skips ahead to the named stage; assumes prior stages succeeded. Re-runs `initial_diagnostics` to confirm prior post-conditions are met before resuming. |
| `--dry-run` | flag | no | Every per-device skill runs in `--prepare` mode. No CCU writes, no approval gates fire (since nothing destructive is about to happen). Output JSON has `dry_run: true` at top level. |
| `--legacy-serial-sw-config` | flag | no | At stage 13, fall back to per-switch serial config push (`dosto-sw-config-update --execute` looped leaf-first) instead of the default batched parallel path (`dosto-sw-config-update-batch --execute --auto`). Use only when the batch skill has shown problems on the specific train being commissioned. |

### Pre-stage-1 input cross-validation (mandatory)

**Before invoking any skill or even SSHing to the CCU**, validate that `--ccu-ip`, `--fzg`, and `--train-number` are mutually consistent. Three checks, all string-level (no network):

| Check | Logic | Failure verdict |
|---|---|---|
| **CCU IP ↔ box-NN consistency** | The CCU's hostname (read via SSH later) MUST be `box1-t<NN>` where `NN` is the third octet of `--ccu-ip`. Skill caches the *expected* hostname here for state-inventory fact 1. | If hostname mismatches, `BLOCKED` — wrong CCU IP supplied or fleet routing change. |
| **Fzg ↔ train-number consistency** | Apply the per-series formula. `4736-NNN → Fzg = NNN + 28`. `4734-NNN → Fzg = NNN - 100`. If `--fzg` doesn't match the formula result for `--train-number`, halt immediately. | `BLOCKED` with `next_action: "Caller supplied --fzg <X> but --train-number <Y> implies Fzg <Z>. Fix one. If you intended a Fzg/train mismatch (DOSTO NEU train_id ≠ Fzg ID — see auto-memory feedback_train_id_ip_mismatch.md), pass --decoupled to override."` |
| **CCU IP ↔ Fzg consistency (advisory)** | If the CCU IP follows the convention `10.179.<NN>.1` where `NN` matches the train# (e.g. `10.179.10.1` for 4736-104), warn on mismatch. Some trains intentionally use non-aligned IPs — log a warning, don't halt. | Warn in `issues[]`, proceed. |

**Why this matters:** today's footgun shape is "engineer types `--ccu-ip 10.179.47.1 --fzg 132`" — that's Fzg 130's CCU paired with Fzg 132's templates. Without this check, the skill would happily push Fzg 132 hostnames to Fzg 130's switches — a silent fleet-status-corrupting wrong-train commission. The check is one regex + one string compare; the cost of getting it wrong is ~90 minutes of recovery work plus a confused team.

The `--decoupled` flag (option, no value) bypasses the Fzg ↔ train-number check for the documented decoupled trains (currently only Fzg 133 / box1-t1). It does NOT bypass the hostname check — that remains mandatory.

## The 19-stage pipeline

Per [`subagent-report.md`](../../contracts/subagent-report.md) → "Commissioning stage list (canonical IDs)". Listed in execution order; conditional skips noted.

| # | `stage.id` | `status` | Conditional? | Underlying skill(s) |
|---|---|---|---|---|
| 1 | `initial_diagnostics` | `DIAGNOSING` | always | `dosto-state-inventory`, `dosto-device-discovery`, `dosto-obn-patches --check`, `dosto-fzg-id-check --check`, `dosto-vlan7-config --check`, `dosto-tftp-helper-check --check` |
| 2 | `await_device_count_mismatch` | `NEEDS_APPROVAL` (Gate 5) | only if missing devices | — |
| 2.5 | `ensure_v8_templates` | `APPLYING_FIXES` | only if `initial_diagnostics` found `nd-obn-template-dostoneu-{nv6,nv4}` dpkg version `< 0.0.19` | `sudo /usr/sbin/nd-systemupdate.sh.dont up` → `sudo systemctl reboot` → TCP/22 probe loop (10s × 30) → re-verify dpkg version `≥ 0.0.19`. **Auto, NO gate** (autonomy-boundary v2 carve-out — runtime state is empty pre-patch). On failure: `status = ISSUE`, halt this worker only. |
| 3 | `apply_obn_patches` | `APPLYING_FIXES` | only if OBN < 8/8 | `dosto-obn-patches --apply` |
| 4 | `apply_train_id_fix` | `APPLYING_FIXES` | only if fzg-id verdict ≠ `all_match` | `dosto-fzg-id-check --apply` *(in-place sed before chroot)* |
| 5 | `apply_vlan7_fix` | `APPLYING_FIXES` | only if vlan7 verdict ≠ `all_match` | `dosto-vlan7-config --apply` *(in-place edit before chroot)* |
| 6 | `await_promote_snapshot` | `NEEDS_APPROVAL` (Gate 1) | only if any of 3-5 ran | — |
| 7 | `promote_snapshot` | `APPLYING_FIXES` | only if Gate 1 approved | `dosto-obn-patches --persist [--with-fzg-id <Fzg>] [--with-vlan7 <Fzg>]` (single-promote fold-in pattern, handoff lesson 1) |
| 8 | `await_safe_reboot` | `NEEDS_APPROVAL` (Gate 2) | only after promote | — |
| 9 | `reboot_and_wait` | `APPLYING_FIXES` | only if Gate 2 approved | `safe_reboot` + SSH wait loop |
| 10 | `post_reboot_verify` | `DIAGNOSING` | only after reboot | re-run `--post-flight` mode of OBN-patches, fzg-id-check, vlan7-config — verifies *rendered output* (hostnames, live IP, FW reach) not just file markers |
| 11 | `obn_discover_initial` | `DIAGNOSING` | always | `sudo obn discover` from CCU, parse `/tmp/discovery.json` for AP factory-state and switch firmware/config state |
| 12 | `await_obn_update_c` | `NEEDS_APPROVAL` (Gate 3) | only if any switch needs config push OR Nomad APs need config refresh | — |
| 13 | `push_switch_config` | `PUSHING_TO_DEVICES` | only if Gate 3 approved AND any switch needs config | **Default**: `dosto-sw-config-update-batch --execute --auto` — OBN-driven parallel leaf-first batches, ~30-45 min wall-clock for a 6-car DOSTO. **Legacy fallback**: with orchestrator flag `--legacy-serial-sw-config`, loops `dosto-sw-config-update --execute` per switch (~3 hours). Same OBNTree leaf-first ordering either way. **Highest-value device push — fires first under power-off risk** because the v8 config carries Stadler-specific switch IPs the customer cares about. |
| 14 | `obn_discover_post_sw_config` | `DIAGNOSING` | only after `push_switch_config` | `sudo obn discover` to verify all switches now show config `✓` (renamed from `obn_discover_post_config` to disambiguate from the AP-config phase later) |
| 15 | `await_obn_update_f` | `NEEDS_APPROVAL` (Gate 4) | only if any device needs firmware push | — |
| 16 | `push_switch_firmware` | `PUSHING_TO_DEVICES` | only if Gate 4 approved AND any switch needs firmware update | `dosto-sw-firmware-update --execute`, one switch at a time, OBNTree leaf-first. **NEW stage** — split from old combined `push_ap_firmware` two-phase form. Runs after switch config so the operational payload (Stadler IPs) is locked in before the maintenance payload (firmware version). |
| 17 | `ap_factory_bypass` | `APPLYING_FIXES` | only if any AP in factory config (per stage 11 inventory) | `dosto-ap-config-update --execute` (Path B: LuCI HTTP), one AP at a time, serially. **MOVED** from old position (was after `obn_discover_initial`) to here, just before AP firmware push. Reason: the bypass exists *to make factory APs OBN-reachable for the firmware push that immediately follows*; doing it earlier interleaves it with switch work it has no dependency on. |
| 18 | `push_ap_firmware` | `PUSHING_TO_DEVICES` | only if Gate 4 approved AND any AP needs firmware update | `dosto-ap-firmware-update --execute`, single-AP serial. After both `ap_factory_bypass` (factory APs now Nomad-form, OBN-reachable) and `push_switch_firmware` (fabric on target FW first). `current_step` / `total_steps` track per-AP. |
| 19 | `push_ap_config` | `PUSHING_TO_DEVICES` | only if any Nomad AP shows config drift after firmware push | `dosto-ap-config-update --execute` (Path A: OBN SNMP, NOT LuCI HTTP — these APs are Nomad-form). **NEW stage** — final config refresh. Catches APs whose Nomad config went stale post-firmware (firmware updates can reset some config fields) or that need the latest cert/network bindings. |
| 20 | `final_l2_health_check` | `DIAGNOSING` | always | `dosto-l2-health --json` |
| 21 | `generate_report` | `APPLYING_FIXES` | always (unless prior stage failed) | `dosto-l2-report --json` |

The `done` terminal stage is reached after stage 21 emits `status: DONE`.

## The orchestration model: skill-as-driver

This skill drives the per-device skills by **invoking them via the Skill tool** in `--execute` mode (normal run) or `--prepare` mode (`--dry-run`). Each per-device skill returns its JSON output; this skill aggregates state and decides the next stage.

Pseudo-flow at each stage transition:

```
for stage in pipeline:
    if stage is conditional and condition_not_met:
        emit_skip_event
        continue

    if stage is an approval gate (status=NEEDS_APPROVAL):
        emit subagent-report with status=NEEDS_APPROVAL, approval_needed populated
        return  # halt; subagent surfaces to orchestrator; orchestrator gets human ack;
                # subagent re-invokes this skill with --resume <next_stage_id>
        continue

    invoke the underlying skill(s) for this stage in --execute or --prepare mode
    parse skill's JSON output
    aggregate into subagent-report.fields and skill_outputs[]

    if any per-device skill returned a hard-fail verdict:
        emit subagent-report with status=BLOCKED or ERROR, populate issues[]
        return  # halt; orchestrator surfaces in next digest

    emit subagent-report with the stage's autonomous status
    proceed to next stage
```

The skill **always-emits-JSON** — every stage transition produces a subagent-report-shaped JSON object on stdout. The subagent's job is to relay these to the orchestrator and handle the resumption protocol.

## Approval flow (gates 1-5)

When this skill hits a gate stage:
1. Constructs the subagent-report with `status=NEEDS_APPROVAL` and a populated `approval_needed` block.
2. Emits the report on stdout.
3. **Halts** (returns from the skill invocation).

The subagent then:
1. Reads the report from this skill's output.
2. Surfaces `approval_needed` to the orchestrator (per `.claude/contracts/approval-gates.md`).
3. Receives the orchestrator's response (`approved` / `denied`, plus three-way for Gate 5).
4. If `approved`: re-invokes this skill with `--resume <next_stage_id>`.
5. If `denied`: re-invokes with `--resume done` (terminal `BLOCKED` state).

So the skill is structured as **resumable from any stage marker**. State between invocations is recovered from:
- The CCU's actual state (re-discovered at every resume via `initial_diagnostics`).
- The fleet-status row (read-only authoritative for "what was already done").

**No skill-side cache file.** Discovery is cheap relative to the cost of getting state out of sync.

The five gates and their `approval_needed.gate` values:

| Gate | `gate` value | Stage that fires it | Response shape |
|---|---|---|---|
| 1 | `promote_snapshot` | `await_promote_snapshot` | `binary` |
| 2 | `safe_reboot` | `await_safe_reboot` | `binary` |
| 3 | `obn_update_c` | `await_obn_update_c` | `binary` |
| 4 | `obn_update_f` | `await_obn_update_f` | `binary` |
| 5 | `device_count_mismatch` | `await_device_count_mismatch` | `three_way` |

## Single-promote pattern enforcement

When stages 3, 4, 5 (`apply_obn_patches`, `apply_train_id_fix`, `apply_vlan7_fix`) all need to run, this skill **batches them into one chroot session** by invoking `dosto-obn-patches --persist --with-fzg-id <Fzg> --with-vlan7 <Fzg>` (the fold-in mode from step 4 of the build plan).

Logic for fold-in selection at stage 7 (`promote_snapshot`):

```
flags = []
if dosto-fzg-id-check.verdict at stage 1 was not all_match:
    flags += ["--with-fzg-id", str(fzg)]
if dosto-vlan7-config.verdict at stage 1 was not all_match:
    flags += ["--with-vlan7", str(fzg)]
invoke /dosto-obn-patches <ccu-ip> --persist --json {*flags}
```

Result: there's only **one Gate 1 (promote_snapshot) ack** for the whole stages-3-through-7 block, regardless of how many fixes are folded in. Eliminates the two-promote / two-reboot pattern that wasted ~90 minutes on Fzg 132 (handoff lesson 1).

If stages 3-5 are all skipped (everything already correct), stages 6-10 are also skipped — go directly from stage 1 to stage 11 (`obn_discover_initial`).

## Per-stage detailed semantics

### Stage 1: `initial_diagnostics`

**Status:** `DIAGNOSING`. **Conditional:** never (always runs first).

Invokes (in this order, all `--check --json`):

1. **`/dosto-state-inventory <ccu-ip> <fzg> --json`** — fast aggregate sanity check across 12 persistent-state facts. Detects state drift since the last session (TFTP CT helper rule lost on reboot, btrfs subvol rolled back, train_id template silently regressed, vlan7 changed, NDSU rename undone). One SSH heredoc, ~5s. **If aggregate verdict is `unexpected_drift`, halt with `BLOCKED` immediately** and surface the per-fact diff to the engineer — they must ack the drift before any deeper checks fire. `expected_drift` (e.g. TFTP helper rule missing on a fresh reboot) is logged to `issues[]` as a warning but doesn't halt.
2. `/dosto-device-discovery <ccu-ip> --json` — count switches and APs against expected (18+24 for nv6, 12+16 for nv4).
3. `/dosto-obn-patches <ccu-ip> --check --json` — 8 patch markers + cross-checks (NDSU path, train_id template, vlan7 IP).
4. `/dosto-fzg-id-check <fzg> --check --json` — template `train_id` line consistency.
5. `/dosto-vlan7-config <fzg> --check --json` — vlan7 IP triplet diff.
6. `/dosto-tftp-helper-check <ccu-ip> --check --json` — kernel module + iptables rule + Puppet persistence.
7. **v8-template version** — `dpkg-query -W -f='${Version}' nd-obn-template-dostoneu-nv6 2>/dev/null` (or `-nv4` for 4-car consists). If the package version is `< 0.0.19` (or the package is absent), the next stage to fire is `ensure_v8_templates` (stage 2.5) regardless of patches / fzg-id / vlan7 verdicts. v8 templates must be on disk before OBN patches are applied (patches reference template paths). **Note (2026-05-20):** v8 ≠ filename pattern. The 0.0.19 package keeps the flat `nv6-NNN-XN.cfg` / `nv4-NNN-XN.cfg` naming; v8-ness is conveyed by package version and template *content*, not filename. Detecting via filename glob (`*-v8-*.cfg`) is wrong — that pattern doesn't exist in any shipped package version. Discovered when both Fzg 143 and Fzg 144 workers false-alarmed `v8_templates_missing_post_update` after a successful `nd-systemupdate.sh.dont up` to 0.0.19.

The state inventory check (#1) runs first because it's the fastest to fail. If something silently changed since the last session — auto-update fired, someone hand-edited the CCU, the fleet rebooted — we want to know before spending 30s on the per-skill deep checks. The deep checks (#2-#6) still run if the inventory is clean or only `expected_drift`; they catch issues the inventory doesn't (e.g. AP factory config, missing devices, deep diff on vlan7 nmconnection).

Aggregates into the subagent-report:

```json
"fields": {
  "obn_patches": "<from dosto-obn-patches.verdict>",
  "vlan7_ok": "<from dosto-vlan7-config.verdict>",
  "switches_v8": "<from dosto-device-discovery — switches counted>",
  "aps": "<from dosto-device-discovery — APs counted, with factory/nomad split if visible>"
}
```

Stage outcome routing:

| Found at stage 1 | Next stage |
|---|---|
| **`dosto-obn-patches` reports `nd_systemupdate_path: null`** (NDSU=MISSING — neither `.sh` nor `.sh.dont` exists, after the `-f` probe) | **Skill emits terminal `BLOCKED` immediately** with `next_action: "engineer must investigate missing /usr/sbin/nd-systemupdate.sh on this CCU before any commissioning — chroot mechanism does not exist on this image"`. No further stages run. This is a hard fail because every persistence path (stages 7, 12, 14, 17) requires the chroot mechanism. **Caveat: only emit this if the probe used `[ -f ]` not `[ -x ]`.** On the fleet, `nd-systemupdate.sh.dont` is mode 0500 owner=root and `[ -x ]` returns false for the `developer` SSH user even though the file is fully usable via `sudo`. Validated 2026-05-09 on box1-t47 — false-positive `-x` detection initially mis-flagged this CCU as NDSU=MISSING. |
| Missing devices (`dosto-device-discovery` reports any) | Stage 2 (`await_device_count_mismatch`) |
| **v8 template package `< 0.0.19` or absent** | Stage 2.5 (`ensure_v8_templates`) — auto, no gate. After it completes, re-enter stage 1 (post-reboot state may have changed everything). |
| All preconditions clean (8/8 patches persisted, fzg ✓, vlan7 ✓, tftp helper ✓, v8 template package `≥ 0.0.19`) | Skip to stage 11 (`obn_discover_initial`) |
| Any of patches/fzg/vlan7 needs fix (and v8 templates present) | Stage 3-7 block runs (with single-promote fold-in at stage 7) |
| TFTP helper missing | Skill emits `BLOCKED` with `next_action: /dosto-tftp-helper-check <ccu-ip> --apply-runtime` — engineer must fix before resuming |

### Stage 2: `await_device_count_mismatch` (Gate 5)

**Status:** `NEEDS_APPROVAL`. **Conditional:** only if `dosto-device-discovery` found missing devices.

`approval_needed.gate = "device_count_mismatch"`, `response_shape = "three_way"`. Engineer chooses:
- `proceed` — push to discovered devices only, document missing as Stadler-side cabling issue
- `pause` — halt; train is `BLOCKED` on cabling
- `abort` — terminal `BLOCKED`

`approval_needed.missing_devices` carries the per-device structured info from `dosto-device-discovery` output (slot, expected_switch, expected_port, stadler_instruction). Orchestrator formats one prompt section per missing device per `.claude/contracts/approval-gates.md`.

### Stage 2.5: `ensure_v8_templates`

**Status:** `APPLYING_FIXES`. **Conditional:** only if `initial_diagnostics` found `dpkg-query -W -f='${Version}' nd-obn-template-dostoneu-{nv6,nv4}` returned a version `< 0.0.19` (or the package was absent).

**Auto, no gate.** Per autonomy-boundary v2 (2026-05-20), this stage's reboot is carved out from Gate 2. Reasoning: stage runs before any OBN patches or runtime fixes are applied, so reboot wipes nothing valuable.

**Recipe:**

```bash
# Step 1: pull v8 templates from Puppet via chroot. Expected ~300s.
sudo /usr/sbin/nd-systemupdate.sh.dont up

# Step 2: only if exit 0 — reboot immediately (don't wait for the script's "reboot?" prompt).
sudo systemctl reboot

# Step 3: from orchestrator side, probe TCP/22 every 10s for up to 300s.
# Once SSH returns, re-verify the dpkg version on the active root:
dpkg-query -W -f='${Version}\n' nd-obn-template-dostoneu-nv6   # expect ≥ 0.0.19 for 6-car
dpkg-query -W -f='${Version}\n' nd-obn-template-dostoneu-nv4   # expect ≥ 0.0.19 for 4-car
```

**Detection of "v8 missing":** dpkg package version — `nd-obn-template-dostoneu-nv6` (or `-nv4`) `< 0.0.19`. The 0.0.19 package retains the flat `nv6-NNN-XN.cfg` / `nv4-NNN-XN.cfg` naming convention from prior versions; v8-ness is encoded in template *content* (new VLAN/port assignments) and the package version, NOT in filename. Trains on pre-0.0.19 versions (Fzg 139 / 140 / 12 / 13 currently on v3) trigger this stage. **Do NOT detect via filename glob like `*-v8-*.cfg`** — that pattern doesn't exist in any shipped package version (regression caught 2026-05-20 on Fzg 143 + Fzg 144 — both false-alarmed post-`up` because the worker globbed for filenames the package never produces).

**Failure modes (all → `status = ISSUE`, halt this worker only, no engineer gate):**
- `nd-systemupdate.sh.dont up` exits non-zero → halt with stderr captured in `issues[]`
- Reboot triggers but SSH doesn't return within 300s → halt with `ssh_recovery_timeout`
- Post-reboot, `nd-obn-template-dostoneu-{nv6,nv4}` dpkg version still `< 0.0.19` → halt with `v8_templates_missing_post_update`

Other workers in the cycle keep running. Engineer picks the halted train back up manually next session.

**Why no gate:** spec 2026-05-20 — engineer doesn't want to be interrupted for this reboot; pre-patch CCU has no runtime state worth preserving.

### Stage 3: `apply_obn_patches`

**Status:** `APPLYING_FIXES`. **Conditional:** only if stage-1 OBN patches verdict was `vanilla` or `partial`.

Invokes `/dosto-obn-patches <ccu-ip> --apply --json`. The `--apply` mode prints the recipe; in `--execute` semantics for this orchestrator, the skill SSHes from the CCU and runs the recipe (under `btrfs ro=false`, then re-locks). Captures stdout/stderr for diagnostic context if any patch fails.

If `dosto-obn-patches` returns verdict `all_patched` after running, proceed. If still `partial`, halt with `BLOCKED`.

**Subagent-driven invocation (audit finding F1-B, 2026-05-11):** Step 1 of `dosto-obn-patches --apply` requires SCP to stage the fix scripts on the CCU at `/var/tmp/`. **The harness denies SCP from spawned subagents** (verified on the 2026-05-11 first-run test). When this stage is driven by a `dosto-train-worker` subagent rather than the engineer directly, the SCP step MUST be handed off to the parent (orchestrator / top-level session) per the F1-C handoff-on-Bash-denial protocol in `dosto-train-worker.md`:

1. Subagent runs `dosto-obn-patches --check` and confirms patches needed.
2. Subagent attempts the SCP one-liner. On the expected denial, it emits `status: ERROR` with `next_action: "Parent: SCP the 4 fix scripts to /var/tmp/ on <ccu-ip> and confirm so I can resume Stage 3 from STEP 2 of the recipe."` and ends its turn.
3. Parent SCPs the scripts (the engineer-facing recipe in `dosto-obn-patches/SKILL.md` STEP 1 works fine from the parent context).
4. Parent `SendMessage`s the worker: `{"response": "scripts_staged", "paths": ["/var/tmp/fix_obn.py", ...]}`.
5. Worker resumes with `/dosto-commission-train --resume apply_obn_patches --skip-step1 ...` — the resume flag tells `dosto-obn-patches --apply` that STEP 1 (SCP) is already done; it picks up at STEP 2 (run scripts via plain SSH one-liners, which subagents CAN do).

This is not a workaround — it's the documented division of responsibility. SCP staging is parent-layer; recipe execution is worker-layer. Both work; only the boundary needs to be explicit. The `--skip-step1` flag on `dosto-obn-patches --apply` must be supported by that skill's CLI (F1-B follow-up — currently OPEN as a small CLI flag addition in `dosto-obn-patches`).

Until `--skip-step1` ships, the subagent can simply emit the handoff JSON and trust that parent + the manual resume cycle will work end-to-end. The 2026-05-11 test run executed exactly this pattern successfully on Fzg 130.

### Stage 4: `apply_train_id_fix`

**Status:** `APPLYING_FIXES`. **Conditional:** only if stage-1 fzg-id verdict was `broken_formula`, `hardcoded_wrong`, or `inconsistent`.

This stage **does not run a separate sed loop**. Instead, the fix is folded into stage 7 (`promote_snapshot`) via the `--with-fzg-id <Fzg>` flag on `dosto-obn-patches --persist`. Stage 4's job here is purely to flag the fold-in flag.

The contract calls this stage `APPLYING_FIXES` for consistency with the original two-promote design. With the single-promote fold-in, this stage is a no-op marker — it emits a status report to keep the contract semantics honest, but no actual CCU change happens here.

### Stage 5: `apply_vlan7_fix`

**Status:** `APPLYING_FIXES`. **Conditional:** only if stage-1 vlan7 verdict was `both_wrong`.

Same pattern as stage 4 — flags the `--with-vlan7 <Fzg>` flag for stage 7's fold-in. No standalone work here.

(Verdicts `nmconnection_correct_live_wrong` and `live_correct_nmconnection_wrong` are transient/cosmetic per `dosto-vlan7-config`'s diff matrix; only `both_wrong` triggers the fold-in.)

### Stage 6: `await_promote_snapshot` (Gate 1)

**Status:** `NEEDS_APPROVAL`. **Conditional:** only if any of stages 3-5 flagged work for fold-in.

`approval_needed.gate = "promote_snapshot"`, `response_shape = "binary"`. `command_preview` is the literal `dosto-obn-patches --persist` recipe with the `--with-*` flags substituted, so the engineer sees exactly what will execute inside the chroot.

`destructive: true`, `reversible: false` per the contract.

### Stage 7: `promote_snapshot`

**Status:** `APPLYING_FIXES`. **Conditional:** only if Gate 1 approved.

Invokes `/dosto-obn-patches <ccu-ip> --persist --json [--with-fzg-id <Fzg>] [--with-vlan7 <Fzg>]`. The skill internally drives the chroot session via SSH. Captures the final btrfs subvolume ID (per handoff lesson 6 — folder names recycle, subvol IDs don't).

If `--persist` returns verdict `recipe_ready` but the subagent observes the subvol ID didn't change after the chroot exit, halt with `ERROR` (the promote silently failed).

### Stage 8: `await_safe_reboot` (Gate 2)

**Status:** `NEEDS_APPROVAL`. **Conditional:** always after `promote_snapshot`.

`approval_needed.gate = "safe_reboot"`, `response_shape = "binary"`. `command_preview = "sudo /usr/local/sbin/safe_reboot"`. Engineer ack required because `safe_reboot` affects passenger services.

### Stage 9: `reboot_and_wait`

**Status:** `APPLYING_FIXES`. **Conditional:** only if Gate 2 approved.

Triggers `sudo /usr/local/sbin/safe_reboot` over SSH. Then SSH-probes every 8s (with `nc -z`) until port 22 responds (handoff lesson 8 — full SSH handshake takes longer than TCP probe). Total budget: 5 min. If exceeded, halt with `BLOCKED` (train didn't return — likely engineer hand-investigation needed).

### Stage 10: `post_reboot_verify`

**Status:** `DIAGNOSING`. **Conditional:** only after `reboot_and_wait` succeeded.

This stage runs the **rendered-output Post-Flight verifications** — Karpathy Principle 4 in concrete form. Pre-Flight (and the `--apply`/`--persist` recipes) state intent; Post-Flight verifies the *rendered output downstream consumers depend on* matches that intent. Pure file-marker checks are necessary but not sufficient — they would not catch the Fzg 133 cascade, where the *templates* changed correctly but the *rendered hostnames* were still wrong.

Invokes (in order — fail-fast on the first regression):

1. **`/dosto-obn-patches <ccu-ip> --post-flight --json`** — verifies all 4 OBN assertions:
   - A: 8/8 grep markers present
   - B: btrfs subvol ID changed from pre-promote (handoff lesson 6)
   - C: `obn discover` exits 0 with no Traceback / ERROR / Exception in `/var/log/obn/*.log`
   - D: Bug 5 ipset pre-population observable (non-zero entries in `tftp_allowed`)
2. **`/dosto-fzg-id-check <fzg> --post-flight --json`** — verifies all 3 fzg-id assertions:
   - A: template line single-unique = `{%- set train_id = <Fzg> -%}`
   - B: `obn validate -t sw` shows all switches with rendered hostnames `<variant>-X-v8-<Fzg>` (force-fresh discover first to bypass the every-5-min cache, lesson 15)
   - C: `dosto-obn-patches --check` reports `train_id_template_consistent == true`
3. **`/dosto-vlan7-config <fzg> --post-flight --json`** — verifies all 3 vlan7 assertions:
   - A: nmconnection `address1=` matches expected
   - B: `ip -br addr show vlan7` matches expected (NetworkManager applied)
   - C: `nc -zv` to Stadler FW peer (port 80 + 22) succeeds (with the `ccu_ok_stadler_unreachable` exception still passing for our scope — flag in fleet-status, don't halt)

Aggregated post-flight verdict logic:
- All three skills return `all_match` (or `ccu_ok_stadler_unreachable` for vlan7) → stage passes; proceed to stage 11.
- Any skill returns `input_only` / `markers_only` / a partial-success verdict → halt with `BLOCKED`. Capture full diagnostic context including the post-flight `raw` blocks. Engineer must investigate the silent regression.
- Any skill returns `runtime_failure` / `both_mismatch` → halt with `ERROR`. The promote completed structurally but didn't take effect; this is the canonical "looks fine but isn't" failure.

**Why this matters:** during the original Fzg 133 cascade (May 2026), engineers verified the input templates after the chroot-promote. Templates looked right. But they used the wrong template form (`128 + train_id`) and pushed wrong hostnames to the entire consist. A rendered-output check on `obn validate -t sw` would have caught it before any switch was touched. This stage is the structural enforcement of that lesson.

The `expected_duration_seconds` for stage 10 is now ~120s (was 60s) — the `obn discover` force-fresh poll on a 6-car consist takes 30-45s by itself.

### Stage 11: `obn_discover_initial`

**Status:** `DIAGNOSING`. **Conditional:** always.

Runs `sudo obn discover` from the CCU (handoff lesson 15 — force fresh, don't trust the every-5-min cache). Parses `/tmp/discovery.json` to build an inventory of:
- Per-AP: IP, MAC, current firmware version, current config state (Nomad / factory / unknown)
- Per-switch: IP, MAC, current firmware version, current config state, OBNTree position (leaf vs intermediate)

Aggregates inventory into the subagent's internal state. No fleet-status update from this stage alone.

Stage outcome routing:

| Inventory at stage 11 | Next stage |
|---|---|
| All switches on target config AND target firmware AND all APs at target firmware AND no Nomad AP config drift AND no factory APs | Skip to stage 20 (`final_l2_health_check`) |
| Any switch needs config update | Stage 12 (`await_obn_update_c`) — Gate 3 covers SW config + final AP config refresh |
| Switches OK on config, but any switch needs firmware update OR any AP needs firmware update | Skip to stage 15 (`await_obn_update_f`) — Gate 4 covers SW firmware + AP firmware |
| Switches OK on config and firmware, but factory APs present | Skip to stage 17 (`ap_factory_bypass`) — no gate needed (fix-up step) |
| Switches OK on config and firmware, no factory APs, but any AP needs firmware update | Skip to stage 15 (`await_obn_update_f`) |
| Switches OK on everything, all APs Nomad and at target firmware, but Nomad AP config drift | Skip to stage 12 (`await_obn_update_c`) — Gate 3 only covers stage 19 (the `push_ap_config` refresh); stages 13/14/16/17/18 all skip |

### Stage 12: `await_obn_update_c` (Gate 3)

**Status:** `NEEDS_APPROVAL`. **Conditional:** only if any switch needs config push OR any Nomad AP needs config refresh.

`approval_needed.gate = "obn_update_c"`, `response_shape = "binary"`. `command_preview` is a multi-line listing of every device that will receive a config push (per-switch in stage 13, per-AP in stage 19 — both covered by this single Gate 3 approval).

The Gate 3 approval covers BOTH the switch-config push (stage 13) AND the eventual AP-config refresh (stage 19), since both write config via OBN. One approval, two stages — keeps the approval cost flat as the pipeline grows.

### Stage 13: `push_switch_config`

**Status:** `PUSHING_TO_DEVICES`. **Conditional:** only if Gate 3 approved AND stage 11 inventory found any switch with config drift.

**This is the highest-value device push.** The v8 config carries Stadler-specific switch IPs the customer cares about, and is fully tested as the next step after CCU commissioning. Power-off-risk principle: if the train powers off after this stage, the operational payload (Stadler IPs on every switch) is locked in, regardless of whether subsequent firmware/AP work completes.

**Default path — parallel batched** (`dosto-sw-config-update-batch --execute --auto`):

Wraps OBN's built-in parallel batcher (`obn update c sw` → `OBNTree.calculate_parallel_update_order` → `ThreadPoolExecutor`). Same OBNTree leaf-first ordering as the legacy path, but multiple sibling leaves reboot concurrently rather than one-at-a-time. ~30-45 min wall-clock on a 6-car DOSTO vs. ~3 hours legacy. `stage.current_step` / `total_steps` track per-batch progress (e.g. batch 2/5). Gate 2 surfaces per-batch failures with engineer choice (abort / extend-poll / retry / skip); 3 consecutive non-success outcomes auto-abort. See [`dosto-sw-config-update-batch`](../dosto-sw-config-update-batch/SKILL.md) for full event schema and gate semantics.

**Legacy serial path** (`--legacy-serial-sw-config` orchestrator flag):

Iterates switches in OBNTree leaf-first order. For each switch, invokes `/dosto-sw-config-update <ccu-ip> <switch-ip> --execute --json`. The per-switch skill enforces the leaf check; non-leaves require `--allow-non-leaf` which this stage passes only when iterating up the tree after all children of that switch are done. `stage.current_step` / `total_steps` track per-switch progress. Use only when the batch skill has a known issue on the specific train (e.g. surfaced during a previous failed run).

If any push fails (`config_did_not_trigger_reboot` from `dosto-sw-config-update`, `gate_4:targets_still_failing` from `dosto-sw-config-update-batch`, or any unhandled abort), halt with `BLOCKED`. Capture the failed switches and full diagnostic context.

### Stage 14: `obn_discover_post_sw_config`

**Status:** `DIAGNOSING`. **Conditional:** only after `push_switch_config`.

Force-fresh `sudo obn discover` to verify all switches now show config `✓` AND the rendered hostnames match `<variant>-X-v8-<Fzg>` (rendered-output Post-Flight check, Karpathy Principle 4). If any still show `✗`, this is a regression — halt with `ERROR`.

Stage renamed from old `obn_discover_post_config` to disambiguate from the AP-config phase that comes much later. (The validator's C7 checks renamed-stage-IDs are referenced consistently.)

### Stage 15: `await_obn_update_f` (Gate 4)

**Status:** `NEEDS_APPROVAL`. **Conditional:** only if any device's firmware column shows `✗` after stage 11 or 14.

`approval_needed.gate = "obn_update_f"`, `response_shape = "binary"`. `command_preview` lists every device that will receive a firmware push (switches in stage 16, APs in stage 18 — both covered by this single Gate 4 approval).

### Stage 16: `push_switch_firmware`

**Status:** `PUSHING_TO_DEVICES`. **Conditional:** only if Gate 4 approved AND stage 11 inventory found any switch with firmware drift.

**Switches first, before APs.** Switches are deeper in the fabric tree; pushing firmware to switches after APs would risk APs disconnecting mid-update during switch reboots. Empirically: AP firmware push handles transient connectivity well (handoff lesson 14 — 6-15min completion budget includes reboot + return); switch firmware push is more sensitive (RSTP convergence after each switch reboot).

Iterates switches in **OBNTree leaf-first order** (parent reboots after a child push must not isolate that child's children). For each switch, invokes `/dosto-sw-firmware-update <ccu-ip> <switch-ip> --execute --json`. Validates each switch returns to SNMP-responsive AND RSTP convergent before moving to the next.

`stage.current_step` / `total_steps` track per-switch progress.

Per-switch hard fails (stuck flash, switch doesn't return after firmware reboot, RSTP storm) halt the stage with `BLOCKED`. The fabric is still operational (config from stage 13 is locked in) — the failure is in the *maintenance* layer, not the *operational* layer.

### Stage 17: `ap_factory_bypass`

**Status:** `APPLYING_FIXES`. **Conditional:** only if stage 11 inventory found any AP in factory config (`RT610LV-…-v1-FD`).

**MOVED** from old position (was right after `obn_discover_initial`). Reason: the bypass exists *to make factory APs OBN-reachable for the firmware push that immediately follows*; doing it earlier interleaves it with switch work it has no dependency on. Now it lives directly between `push_switch_firmware` (which has no dependency on AP state) and `push_ap_firmware` (which absolutely depends on every AP being OBN-reachable, which Path B accomplishes).

Iterates the factory-config AP list serially. For each AP, invokes `/dosto-ap-config-update <ccu-ip> <ap-ip> --execute --json`. The per-AP skill auto-detects factory state and runs Path B (LuCI HTTP login → flashops upload → rpcCfgApply → reboot → SNMP verify).

**No separate fleet-level gate** — this is treated as a fix-up step, not a destructive consist-wide push. The per-device skill's internal gates (login, apply) are auto-acknowledged.

If any AP fails Path B, halt the stage with `BLOCKED`, capture which AP and the failure verdict in `issues[]`. Subsequent stages (firmware, config refresh) cannot run on a factory AP without bypass.

`stage.current_step` / `total_steps` track per-AP progress (e.g. 3/16 done, 13 remaining).

### Stage 18: `push_ap_firmware`

**Status:** `PUSHING_TO_DEVICES`. **Conditional:** only if Gate 4 approved AND any AP needs firmware update.

After both `ap_factory_bypass` (factory APs are now Nomad-form, OBN-reachable) and `push_switch_firmware` (the fabric is on target firmware, no mid-update reboots while we're hitting APs).

**Single-AP serial only** — handoff lesson 11. Parallel batches > 2-3 are unreliable on the current fleet image until R&D ships the CCU firewall TFTP-helper Puppet fix.

For each AP needing firmware update, invokes `/dosto-ap-firmware-update <ccu-ip> <ap-ip> --execute --json`. The per-AP skill drives the full state machine: push → RRQ verification → stuck-state SSH-reboot recovery (single retry budget) → 15-minute completion poll.

`stage.current_step` / `total_steps` track per-AP progress (e.g. 12/24 done, 12 remaining).

Per-AP hard fails (stuck-state recovery exhausted, completion timeout) halt the stage with `BLOCKED`.

### Stage 19: `push_ap_config`

**Status:** `PUSHING_TO_DEVICES`. **Conditional:** only if any Nomad AP shows config drift after stage 18.

**NEW stage** — the final AP config refresh. Catches APs whose Nomad config went stale post-firmware-push (some firmware updates reset config fields like NTP servers, log targets, or `wifi.country`) or that need the latest cert/network bindings from the v1 config baseline.

Iterates the drifted AP list serially. For each AP, invokes `/dosto-ap-config-update <ccu-ip> <ap-ip> --execute --json`. **Path A (OBN SNMP), NOT Path B (LuCI HTTP)** — at this stage every AP is Nomad-form (factory APs were bypassed in stage 17, then firmware-pushed in stage 18, both of which leave them on Nomad config). Forcing Path A here is the correct answer for the post-commissioning steady-state config push.

Covered by Gate 3 (already approved at stage 12) — no new approval needed.

If any per-AP push fails, halt with `BLOCKED`. The fabric is operational (configs and firmware all landed); the failure is in the maintenance/refresh layer.

`stage.current_step` / `total_steps` track per-AP progress.

### Stage 20: `final_l2_health_check`

**Status:** `DIAGNOSING`. **Conditional:** always (unless prior stage halted with `BLOCKED` or `ERROR`).

Invokes `/dosto-l2-health <ccu-ip> --json`. Captures full L2 fabric state (per-switch error counters, RSTP root, trunk states, end-to-end Stadler firewall reachability).

If any L2 health verdict is non-clean, populate `issues[]` with the findings but don't halt — generate the report anyway (engineer reads it and decides next steps).

### Stage 21: `generate_report`

**Status:** `APPLYING_FIXES` *(per the contract — generating a docx is technically a write, even though it's local-only)*. **Conditional:** always (unless prior stage was `BLOCKED` or `ERROR`).

Invokes `/dosto-l2-report <findings.json from stage 20> --json`. Emits the path to the generated docx in the final report's `next_action` field.

After this stage, emit terminal `status: DONE` and exit.

## `--resume <stage_id>` semantics

`--resume <stage_id>` skips ahead. Skill verifies the resume is valid:

1. Reads the fleet-status row for `--train-number`.
2. Re-runs `initial_diagnostics` (stage 1) **always** — even when resuming a late stage. State can change between invocations (auto-update fired, engineer hand-fixed something, train was power-cycled) and silently proceeding with stale assumptions is the original sin that caused the Fzg 133 cascade. ~60s extra per resume; cheap relative to consequences.
3. Confirms post-conditions of all stages prior to `<stage_id>` are met:
   - For resuming `push_switch_config` (stage 13): patches persisted, vlan7 ✓, fzg-id ✓ (factory APs do NOT need to be bypassed yet — that happens at stage 17).
   - For resuming `push_switch_firmware` (stage 16): all of the above + all switches show config `✓` after stage 14.
   - For resuming `ap_factory_bypass` (stage 17): all of the above + all switches show firmware on target after stage 16.
   - For resuming `push_ap_firmware` (stage 18): all of the above + no APs remain in factory config (every entry in stage 11 inventory is now Nomad-form).
   - For resuming `push_ap_config` (stage 19): all of the above + all APs at target firmware.
   - For resuming `final_l2_health_check` (stage 20): all of the above + all device pushes complete.
4. If post-conditions not satisfied, refuses to resume; emits `ERROR` with explanation in `issues[]`.
5. If satisfied, jumps to `<stage_id>` and continues.

**State diff between fleet-status and live state** is logged as `issues[].severity=warning` but doesn't halt resume — the orchestrator surfaces these as digest items.

## `--dry-run` mode

Runs every per-device skill in `--prepare` mode only. No `--execute`. No CCU writes. Approval gates emit reports but the subagent treats them as informational — no orchestrator interaction expected.

JSON output adds a top-level field `"dry_run": true`. Orchestrator should treat dry-run reports as informational only and never persist to `fleet-status.md`.

Used for:
- Engineer training — walks through the skill flow safely.
- Pre-flight check — see what a real run would do without committing.
- Change control — generate a "what would happen" report for review.

## `--json` output stream

The skill **always emits JSON**, one report per stage transition. Each report is the complete subagent-report shape (per `.claude/contracts/subagent-report.md`), not a delta.

There is no human-readable mode by default. The orchestrator/subagent layers consume the structured stream.

**Exception for engineer-direct invocation**: when invoked outside subagent context (engineer typing `/dosto-commission-train ...` in a Claude Code session manually for debugging or training), append a final summary table at end-of-run for ergonomics. The structured JSON stream is always present regardless.

## Failure modes and BLOCKED states

| Failure source | Skill behaviour |
|---|---|
| **Both `/usr/sbin/nd-systemupdate.sh` and `.sh.dont` missing** (verified via `[ -f ]` test, NOT `[ -x ]`) | **Halt at stage 1 with `status=BLOCKED`**, `issues[]={"severity":"error","category":"unknown","description":"chroot promotion mechanism missing on CCU — neither nd-systemupdate.sh nor .sh.dont exists. Pipeline cannot proceed."}`. Outside skill scope to remediate. **Note**: the original `[ -x ]` probe in `dosto-obn-patches` initially returned false-positive MISSING on box1-t47 (mode 0500 owner=root) — fixed 2026-05-09 to use `[ -f ]`. |
| Hard fail from any precondition skill (`dosto-tftp-helper-check` 🔴, etc.) | Halt with `status=BLOCKED`, `issues[]` populated, `next_action` pointing at the unblocking skill |
| Hard fail from any per-device push (e.g. `config_did_not_trigger_reboot` from `dosto-sw-config-update`) | Halt with `status=BLOCKED`, capture full diagnostic context in `issues[]` |
| Engineer denies a gate | Halt with `status=BLOCKED`, mark train as needing human follow-up |
| SSH timeout to CCU | Emit `status=PAUSED`. Subagent retries on next cycle (autonomous). After 30 min stuck per the contract, orchestrator escalates to `BLOCKED`. |
| JSON parse failure on a per-device skill output | Halt with `status=ERROR`, mark as a contract violation (subagent or skill bug). |
| Invariant violated mid-run (e.g. fleet-status says vlan7 OK but live state shows wrong) | Halt with `status=ERROR`, capture the disagreement in `issues[]` |
| `--resume <stage_id>` post-conditions not met | Refuse to resume; emit `ERROR` with explanation. |
| Concurrent invocation on the same train | Detect via CCU-side lock file (`/tmp/dosto-commission-train.lock`). Refuse second invocation with `ERROR`. |
| Per-device skill schema-version mismatch | Refuse to proceed; emit `ERROR`. Each per-device skill includes `schema_version: "1"` in its JSON; this skill validates. |

## What this skill deliberately does NOT do

- ❌ Define new low-level CCU operations — every action goes through a per-device skill.
- ❌ Talk to the orchestrator directly — emits JSON reports; the subagent surfaces them.
- ❌ Fan out across multiple trains — single-train scope only. Multi-train fan-out is the orchestrator's `Agent` tool calls (one per train, in parallel).
- ❌ Modify `fleet-status.md` — orchestrator-as-sole-writer per `.claude/contracts/confluence-sync.md`.
- ❌ Push to Confluence — orchestrator-as-sole-writer.
- ❌ Persist any state between invocations on its own — re-discovers from CCU at every resume.
- ❌ Skip the approval gates — even with `--dry-run`, gate stages still emit `NEEDS_APPROVAL` reports (informational); in normal mode, they are contract-mandated halts.
- ❌ Allow the engineer to bypass per-device skill preconditions (e.g. push firmware before TFTP helper is in place).
- ❌ Run more than one device's `--execute` push at a time — strict serialisation per the per-device skills' single-device discipline (handoff lesson 11).
- ❌ Write any non-CCU files. Only the orchestrator writes fleet-status / Confluence / docx reports (the latter via `dosto-l2-report` invoked at stage 21 — the report file is the output, not an orchestration artefact).

## Edge cases and gotchas

- 🟡 **Dry-run on a vanilla CCU still produces all 19 stage reports.** Conditional skips are only suppressed in real runs; dry-run shows the full theoretical pipeline so engineer can review.
- 🟡 **Approval gate denial vs no-response.** Contract says orchestrator returns either `approved` or `denied`. If neither comes within a contract-defined timeout, subagent treats as `PAUSED` and re-emits the gate request next cycle.
- 🟡 **`--resume` after a long pause.** Re-runs `initial_diagnostics` always — train state may have changed (auto-update fired, engineer hand-fixed). State diff between fleet-status and live is logged as `issues[].severity=warning` but doesn't halt resume.
- 🟡 **Concurrent invocation on the same train.** CCU-side lock file prevents this. The orchestrator should not spawn two subagents for the same train; this skill enforces it as a defensive backstop.
- 🟡 **Per-device skill version skew.** This skill assumes all per-device JSON output schemas are `schema_version: "1"`. If any per-device skill bumps its schema, this skill must be updated alongside (per the contract — "Changes require all subagents and the orchestrator to be updated together").
- 🟡 **Device-push ordering is value-driven, not technically required.** Stages 13 (SW config) → 16 (SW firmware) → 17 (AP factory bypass) → 18 (AP firmware) → 19 (AP config) embody a "highest-value-first under power-off risk" principle: the v8 SW config carries Stadler IPs the customer cares about, so it lands first; AP-firmware-then-config orders maintenance before refresh. If a future fleet image proves a different order works better (e.g. switch firmware actually does reset config and so firmware must come first), revisit the stage list — but keep the pipeline expressing the chosen order as a sequence of explicit stages, not as a hidden two-phase block (the way old `push_ap_firmware` was).
- 🟡 **Stage 4 and 5 are no-op markers.** Per the single-promote fold-in pattern, fzg-id and vlan7 fixes happen inside stage 7's chroot. Stages 4 and 5 emit reports for contract consistency but do no actual work. Engineers reviewing the JSON stream should not be surprised by their brief duration.
- 🟡 **Stage 11's inventory determines the rest of the pipeline.** If `obn discover` returns partial or stale data (e.g. a switch is mid-reboot from earlier work), the inventory may miss devices. Skill mitigates by re-running `obn discover` until two consecutive runs agree, with a 5-min budget.
- 🟡 **Gate 5 is three-way, all others are binary.** The contract is explicit. Subagent must format Gate 5 prompts with three options (proceed/pause/abort), not yes/no.
- 🟡 **Engineer-direct invocation outside subagent context.** Useful for debugging. Skill detects "no subagent wrapper" via heuristic (e.g. invoked without `--json` from an interactive Skill call) and appends final summary table for ergonomics. Structured JSON stream is always present regardless.
- 🟡 **`--dry-run` does not protect against approval gate halts.** Dry-run still emits `NEEDS_APPROVAL` reports at gate stages. Engineer running dry-run interactively must mentally pretend to ack each gate to walk past it; otherwise the dry-run halts at the first gate. (This is intentional — the dry-run is showing the full pipeline including gate semantics.)

## Pairs with

- [`.claude/agents/dosto-train-worker.md`](../../agents/dosto-train-worker.md) — the per-train subagent definition that invokes this skill. Built in step 7 of the build plan.
- [`.claude/contracts/subagent-report.md`](../../contracts/subagent-report.md) — output JSON shape (canonical).
- [`.claude/contracts/autonomy-boundary.md`](../../contracts/autonomy-boundary.md) — gate definitions.
- [`.claude/contracts/approval-gates.md`](../../contracts/approval-gates.md) — gate response shapes.
- [`.claude/contracts/confluence-sync.md`](../../contracts/confluence-sync.md) — orchestrator-side contract (this skill doesn't touch directly).
- All step 1-5 skills — invoked at appropriate stages. See per-stage detail above.
- [fleet-status.md](../../../fleet-status.md) — read-only authoritative state for `--resume` post-condition checks.
- [train-login-checklist.md](../../../train-login-checklist.md) — the manual analog of this skill (engineer drives the same 19 stages by hand).

## Reference

- The four contract docs in `.claude/contracts/`
- handoff lessons 1-17 — foundational lessons every per-device skill encodes
- handoff "What to do next" → original step 6 spec for this skill
- All existing `dosto-*` skills' SKILL.md docs (the underlying skill behaviours encoded here)
- handoff line 195 — F2 / `10.179.10.189` config push validated cleanly on Fzg 132 (validates the stage 13 `push_switch_config` path)
- handoff OBN patch validation table — Bugs 1, 2a still unproven (will be validated by stage 16 `push_switch_firmware` when a newer firmware lands)
