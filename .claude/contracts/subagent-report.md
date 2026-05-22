# Subagent Report Contract

**Status:** v2.1, updated 2026-05-21 (harness enhancements A1/B3/C1/C4/D1). v2.0 locked 2026-05-11 (F2). v1 reports remain accepted with a `schema_version_drift` flag. Changes require all subagents and the orchestrator to be updated together.

**v2.1 changes from v2:**
- `obn_discover_post_sw_config` stage `expected_duration_seconds` updated from 60s → 120s (spot-SSH adds ~60s — see stage-14 detail in `dosto-commission-train` SKILL.md).
- Stage list entry updated: stage 14 now mandates direct SSH spot-check of 3 switches in addition to `obn discover`. Subagents emitting stage 14 without the spot-SSH (i.e. only running `obn discover`) are accepted but flagged as `schema_version_drift`.
- No breaking schema changes — all v2 fields/types preserved.

**v2 changes from v1:**
- `skill_outputs` default semantics tightened: **current-stage only, no historical echo** (was: unspecified). See "Compactness rules" below.
- New top-level "Compactness rules" section codifying token-discipline expectations for every report.
- `fw_reach` field clarification per F9 (see field reference).
- No breaking schema changes — all v1 fields/types preserved.

The shape of the JSON object every per-train subagent emits to the orchestrator. This is the single source of truth — both the orchestrator and the subagent prompts code-generate against it.

## Why this exists

Subagents and orchestrator run as separate Claude sessions with their own contexts. They communicate via JSON because:
- Free-form prose is fragile to parse
- Structured data is easy to merge into `fleet-status.md` rows and Confluence cells
- Schema mistakes surface immediately as JSON parse errors, not subtle misreadings

## Top-level shape

```json
{
  "schema_version": "1",
  "train": {
    "train_number": "4736-104",
    "fzg": 132,
    "ccu_ip": "10.179.10.1",
    "consist": "6-car"
  },
  "report_time": "2026-05-09T06:50:00Z",
  "elapsed_seconds": 540,
  "status": "PUSHING_TO_DEVICES",
  "stage": {
    "id": "push_switch_config",
    "label": "Pushing v8 config to switches",
    "current_step": 3,
    "total_steps": 18,
    "started_at": "2026-05-09T07:14:00Z",
    "expected_duration_seconds": 7560
  },
  "fields": { ... },
  "next_action": "string or null",
  "approval_needed": null,
  "issues": [],
  "skill_outputs": []
}
```

## Field reference

### `schema_version` — string, required

The literal `"2"` for current reports. v1 still accepted (orchestrator flags as `schema_version_drift` in `issues[]` but does not reject). Bumped when fields are added or semantics change.

## Compactness rules (v2, per audit finding F2)

Background: on the 2026-05-11 first-run audit, a single worker turn reached ~166k tokens on a Stage 1 report — most of a Sonnet 4.6 context window for one stage. Root causes were dump-style spawn prompts, full skill-output echo, and re-reading contracts every turn. These rules constrain every subagent report so context grows linearly (not quadratically) with stages traversed.

**The four hard rules every subagent MUST follow:**

1. **`skill_outputs` is current-stage only.** Each report includes outputs for skills the subagent ran *in the current stage transition*. Skills from prior stages are NOT re-emitted. The orchestrator/parent maintains the audit trail externally; the subagent does not.

2. **`skill_outputs[].raw` is bounded.** If a skill's `raw` block exceeds ~500 lines of JSON, the subagent truncates with a sentinel pointer:
   ```json
   {"skill": "dosto-l2-health", "mode": "check", "verdict": "...", "raw": {"_truncated": true, "logged_at": "findings_<ccu>_<ts>.json", "summary_fields": { ...key-fields only... }}}
   ```
   The full data lives on disk; the report carries a pointer.

3. **No historical echo in any field.** Reports describe the *current* stage transition. Prior stages, prior verdicts, prior approvals are NOT restated in subsequent reports. `stage.id` tells the orchestrator where you are; that's enough context.

4. **Spawn prompts are pointers, not dumps.** Orchestrators (or whatever spawns the worker) MUST pass: Train# (primary identifier), CCU IP, consist, engineer name, dry-run flag, ip_source — and nothing else. **Fzg is NOT passed in the spawn prompt** — the worker looks it up from the fleet-status row for the Train# (via `scripts/fleet_status_lookup.py`). If the row's Fzg cell is `❓` or the row is missing, the worker halts with `BLOCKED` + `escalation_reason: known_recipe_failed` and a `next_action` telling the engineer to populate the Fzg in fleet-status. Worker also reads `fleet-status.md`, `fleet-journal.md`, and any per-train detail itself. Dumping per-train prose into the spawn prompt costs 2-3k+ tokens per worker, persists for the worker's lifetime, and is forbidden by this rule.

**The status-ping exception** (formalised here, governed in detail by `dosto-train-worker.md`): if the subagent receives a `SendMessage` whose entire body is the single word `status` (or `status?`, `where are you`), it replies with a one-line summary of `stage.id`, `current_step / total_steps`, and `status` — and ends its turn. It does NOT re-load any contracts, files, or skills, and does NOT emit a full JSON report.

**Enforcement.** These rules are not statistical guidelines; they are contract terms. Violations show up as report-size bloat or as suspiciously-large `skill_outputs` arrays — the orchestrator can detect both. Repeat violations should be filed as a subagent-prompt regression and fixed in the next agent definition update.

### `train` — object, required

| Key | Type | Required | Notes |
|---|---|---|---|
| `train_number` | string | yes | **Primary identifier** — Nomad-internal name, e.g. `"4736-104"`, `"4734-120"`, `"4705-103"`, `"4706-101"`. This is what engineers type, what fleet-status rows are keyed by, and what spawn prompts carry. Subagent reads other fields by looking up this row in fleet-status. |
| `fzg` | integer | yes | ÖBB customer-facing Fzg ID. **Derived** at worker startup by looking up the fleet-status row for `train_number` (via `scripts/fleet_status_lookup.py`). If the row's Fzg cell is `❓` or missing, the worker halts with `BLOCKED` rather than guessing from the per-series formula. Once resolved, the worker echoes it in every report so downstream consumers (vlan7 IP math, switch hostname rendering, log keying) don't need to re-look-it-up. |
| `ccu_ip` | string | yes | e.g. `"10.179.10.1"` |
| `consist` | string | yes | `"4-car"` or `"6-car"` |

### `report_time` — ISO 8601 UTC string, required

Time the subagent finished generating this report. The orchestrator uses this for "last touched" in `fleet-status.md`.

### `elapsed_seconds` — integer, required

Wall time since the subagent was spawned. Used in 5-min digests to flag stuck subagents.

### `status` — enum string, required

One of these nine values, exhaustively. Any other value is a contract violation. Status describes *workflow position* — what kind of work is happening — not the specific task. The specific task lives in `stage` (see below).

| Value | Meaning |
|---|---|
| `NOT_STARTED` | Subagent just spawned, hasn't done anything yet. Used in first heartbeat only. |
| `DIAGNOSING` | Read-only checks in progress (initial discovery OR post-change verification). No state changes. |
| `APPLYING_FIXES` | Making local CCU changes outside chroot OR inside the `nd-systemupdate.sh shell` chroot. Edits to `/usr/share/obn/`, `/etc/obn/template/`, `.nmconnection`, AP LuCI factory bypass — all live here. |
| `PUSHING_TO_DEVICES` | Writing config or firmware to one or more switches/APs. The slow, distributed stuff (`obn update c`, `obn update f`). `stage.current_step` / `total_steps` track per-device progress. |
| `NEEDS_APPROVAL` | Hit an approval gate — `approval_needed` field is non-null. Subagent is paused. |
| `DONE` | All work complete, no issues, no further action needed. |
| `PAUSED` | Train powered off mid-work, SSH timeout, or external blocker. Subagent will retry on next cycle. |
| `BLOCKED` | Cannot proceed without external action (Stadler cabling fix, human denied a gate, etc.). Subagent has stopped retrying. |
| `ERROR` | Subagent itself failed. `issues[]` will contain details. Orchestrator should escalate to human. |

**Status buckets for orchestrator logic:**
- *Working autonomously*: `DIAGNOSING`, `APPLYING_FIXES`, `PUSHING_TO_DEVICES` — let it run, check progress at next cycle
- *Awaiting input*: `NEEDS_APPROVAL` — surface to human immediately
- *Will retry*: `PAUSED` — let it self-heal, escalate after 30 min stuck
- *Won't retry*: `BLOCKED`, `ERROR` — surface in next digest, may need human intervention or skill iteration
- *Terminal*: `DONE` — release subagent, do final fleet-status update

### `stage` — object, required

What the subagent is currently *doing*. Carries the per-step detail that `status` deliberately doesn't.

```json
{
  "id": "push_switch_config",
  "label": "Pushing v8 config to switches",
  "current_step": 3,
  "total_steps": 18,
  "started_at": "2026-05-09T07:14:00Z",
  "expected_duration_seconds": 7560
}
```

| Key | Type | Required | Notes |
|---|---|---|---|
| `id` | enum string | yes | One of the canonical stage IDs (see "Commissioning stage list" below). Typos = contract violation, orchestrator rejects the report. |
| `label` | string | yes | Human-readable description for the digest. |
| `current_step` | integer\|null | no | For multi-step stages (e.g. pushing config to 18 switches), 1-indexed. `null` for one-shot stages. |
| `total_steps` | integer\|null | no | Set alongside `current_step`. `null` for one-shot stages. |
| `started_at` | ISO 8601 UTC | yes | When this stage began. Helps orchestrator detect "stuck in stage" when wall-clock far exceeds `expected_duration_seconds`. |
| `expected_duration_seconds` | integer\|null | no | Best-effort estimate. `null` if duration is unpredictable (e.g. waiting for human approval). |

### Commissioning stage list (canonical IDs)

These are the stages a per-train commissioning subagent moves through. Listed in typical execution order; many trains skip stages that are already correct (e.g. skip `apply_vlan7_fix` if vlan7 is already right).

**Device-push ordering principle:** highest-value-first under power-off risk. SW-config (Stadler IPs, the operational payload customers care about) lands before SW-firmware (maintenance/bug-fix payload). Same shape for APs: AP-firmware (reliability) lands before the final AP-config refresh. Factory-config APs are bypassed first (only path to make them OBN-reachable for subsequent firmware push). If the train powers off at any stage boundary, the train is more usable than at the prior boundary.

| `stage.id` | `status` during this stage | Expected duration | Notes |
|---|---|---|---|
| `initial_diagnostics` | `DIAGNOSING` | 60s | All `--check` skills + cross-checks (includes `dosto-device-discovery` and `dosto-state-inventory` as first sub-steps); also globs `/etc/obn/template/{nv6,nv4}-*-v8-*.cfg` to gate the next stage |
| `await_device_count_mismatch` | `NEEDS_APPROVAL` | — | Gate 5: `device_count_mismatch` — three-way response. Only fires if `dosto-device-discovery` found missing devices. |
| `ensure_v8_templates` | `APPLYING_FIXES` | 360s | **Auto, no gate** (see autonomy-boundary v2). Conditional — only fires if `initial_diagnostics` found no v8 template files. Runs `sudo /usr/sbin/nd-systemupdate.sh.dont up` (~300s), then `sudo systemctl reboot`, then probes TCP/22 every 10s up to 300s, then re-verifies v8 templates present. On any failure: `status = ISSUE`, halt this worker only. |
| `apply_obn_patches` | `APPLYING_FIXES` | 120s | Run `fix_obn.py` etc. under `btrfs ro=false` |
| `apply_train_id_fix` | `APPLYING_FIXES` | 10s | Sed loop on `nv6-*.cfg` if `128 + train_id` formula present, or wrong hardcoded value |
| `apply_vlan7_fix` | `APPLYING_FIXES` | 10s | Edit `address1=` in nmconnection if mismatched |
| `await_promote_snapshot` | `NEEDS_APPROVAL` | — | Gate 1: `promote_snapshot` |
| `promote_snapshot` | `APPLYING_FIXES` | 120s | Inside `nd-systemupdate.sh shell`, re-apply, exit |
| `await_safe_reboot` | `NEEDS_APPROVAL` | — | Gate 2: `safe_reboot` |
| `reboot_and_wait` | `APPLYING_FIXES` | 180s | `safe_reboot` + wait for SSH to come back |
| `post_reboot_verify` | `DIAGNOSING` | 120s | Run `--post-flight` rendered-output verifications across OBN-patches / fzg-id / vlan7 (input + rendered output match) |
| `obn_discover_initial` | `DIAGNOSING` | 60s | `obn discover` to map switch + AP states |
| `await_obn_update_c` | `NEEDS_APPROVAL` | — | Gate 3: `obn_update_c` (covers both SW-config and the final AP-config) |
| `push_switch_config` | `PUSHING_TO_DEVICES` | 420s × N switches | Stadler IPs land here — highest-value device-push, fires first under power-off risk. `current_step` / `total_steps` track per-switch |
| `obn_discover_post_sw_config` | `DIAGNOSING` | 120s | Verify all switches on target config via `obn discover` AND direct SSH spot-check of 3 switches (leaf, root, random intermediate) — independent evaluator check so OBN's own report doesn't self-validate. 120s budget covers 45s discover + 3×25s SSH probes. |
| `await_obn_update_f` | `NEEDS_APPROVAL` | — | Gate 4: `obn_update_f` (covers both SW-firmware and AP-firmware) |
| `push_switch_firmware` | `PUSHING_TO_DEVICES` | 600s × N switches | SW firmware push, leaf-first OBNTree order. NEW stage — split from old `push_ap_firmware` two-phase form. |
| `ap_factory_bypass` | `APPLYING_FIXES` | 180s × N factory APs | LuCI HTTP push for any AP in `RT610LV-…-v1-FD`. Conditional — only fires if stage 11 found factory APs. **MOVED** from after `obn_discover_initial` to before AP firmware push (where it's actually needed: makes factory APs OBN-reachable so the firmware step can hit them). No separate gate — fix-up step. |
| `push_ap_firmware` | `PUSHING_TO_DEVICES` | 540s × N APs | AP firmware push, single-AP serial. After both `ap_factory_bypass` (so factory APs are now reachable) and `push_switch_firmware` (so the switch fabric is on target firmware first). `current_step` / `total_steps` track per-AP. |
| `push_ap_config` | `PUSHING_TO_DEVICES` | 180s × N APs | NEW stage — final AP config refresh on Nomad-form APs. Catches APs whose Nomad config went stale post-firmware-push or that need the latest Nomad cert/network bindings. Conditional — only fires if any Nomad AP shows config drift after `push_ap_firmware`. |
| `done` | `DONE` | — | Terminal stage — emit final report and exit |

> **Removed 2026-05-21:** the prior terminal stages `final_l2_health_check` (Run `/dosto-l2-health`) and `generate_report` (Run `/dosto-l2-report`) are no longer part of the pipeline. `/dosto-l2-health` and `/dosto-l2-report` remain available as optional engineer-invoked skills but don't gate train completion. Subagents emitting either stage ID are accepted but flagged as `schema_version_drift`.

Other subagent types (cabling investigator, etc.) define their own stage IDs without touching this contract. The orchestrator validates against the union of registered stage namespaces — a stage ID not in any registered list is a contract violation.

**Stage list version:** v3 (2026-05-20) — added `ensure_v8_templates` conditional stage between `await_device_count_mismatch` and `apply_obn_patches`; reboot inside this stage is auto (no Gate-2 prompt) per autonomy-boundary v2. v2 (2026-05-09). v1 had `obn_discover_post_config` (renamed) and a single combined `push_ap_firmware` stage (split into `push_switch_firmware` + `push_ap_firmware`); v1 also placed `ap_factory_bypass` before `await_obn_update_c` (now after `push_switch_firmware`), and lacked the `push_ap_config` final refresh stage. Migration: subagents emitting the v1 stage IDs are still accepted by the orchestrator, but flagged as `schema_version_drift` in `issues[]` until they update.

### `fields` — object, required

Mirrors the columns of the `fleet-status.md` table. The orchestrator uses these to update the row directly. Use `null` for "unknown / not yet checked", not the empty string.

| Key | Type | Example | Maps to fleet-status column |
|---|---|---|---|
| `obn_patches` | string\|null | `"10/10 persisted (run4)"`, `"10/10 (not persisted)"`, `"7/10"`, `"0/10 (vanilla)"` | OBN patches |
| `switches_v8` | string\|null | `"18/18"`, `"mixed v4/v8"`, `"❓"` | Switches v8 |
| `aps` | string\|null | `"20/21"`, `"factory (16/16 to bypass)"` | APs |
| `vlan7_ok` | string\|null | `"✅ 172.19.194.2"`, `"🔴 172.19.215.130 (encodes Fzg 175 — wrong, expected 172.19.193.2)"` | vlan7 ok |
| `stadler_cabling` | string\|null | `"✅ clean"`, `"🔴 C3 swap + D1↔E2 missing"` | Stadler cabling |
| `fw_reach` | string\|null | `"✅ commissioned"`, `"🟡 uncommissioned (Stadler-side pending)"`, `"🔴 path broken"`, `"❓ icmp not tested"` | FW reach. **Per F9: ICMP is the deciding test, not TCP.** Value MUST derive from `fw_commission_state` in the `dosto-vlan7-config` / `dosto-l2-health` skill output, not from TCP probe alone. |
| `health_check_done` | string\|null | `"2026-05-09"`, `null` | Health check |
| `customer_report` | string\|null | `"v1.0"`, `null` | Customer report |

The subagent reports only fields it actually checked this cycle. Fields it didn't touch should be omitted from the JSON object — orchestrator preserves the existing fleet-status value for any omitted field. This avoids accidentally clobbering data with `null`.

### `next_action` — string or null

Concrete next command the human or subagent should run, or `null` if the train is at a steady state. Examples:

- `"Awaiting approval to enter nd-systemupdate.sh shell"`
- `"sudo obn discover && sudo obn update c all"`
- `"Wait for Stadler to fix cable register #2"`
- `null` (when status is `DONE` or `BLOCKED`)

### `approval_needed` — object or null

Non-null only when `status == "NEEDS_APPROVAL"`.

```json
{
  "gate": "promote_snapshot",
  "rationale": "All 8 OBN patches applied outside chroot, verified 8/8 markers present. Need to re-apply inside nd-systemupdate.sh shell so they survive reboot.",
  "destructive": true,
  "reversible": false,
  "command_preview": "sudo /usr/sbin/nd-systemupdate.sh shell\n  # then run fix_obn.py + fix_obn_bug8.py inside\n  # then exit\n  # promotes work → release → run<N>"
}
```

| Key | Type | Notes |
|---|---|---|
| `gate` | enum | One of: `promote_snapshot`, `safe_reboot`, `obn_update_c`, `obn_update_f`, `device_count_mismatch`. The five gates from the autonomy boundary in [autonomy-boundary.md](autonomy-boundary.md). |
| `response_shape` | enum | `binary` (gates 1–4) or `three_way` (gate 5 only). Tells the orchestrator how to format the prompt and parse the response. |
| `rationale` | string | Why this is necessary. Written for the human. |
| `destructive` | bool | Does this make a permanent state change? |
| `reversible` | bool | Can it be reverted from inside the running system? `false` for chroot promotion, `true` for outside-chroot edits. |
| `command_preview` | string | Multi-line preview of what will execute if approved. Human reads this before saying yes. For `device_count_mismatch`, this is the per-response action plan rather than a literal command. |
| `missing_devices` | array | Only present when `gate == device_count_mismatch`. Per-device structured info from `dosto-device-discovery` output (slot, expected_switch, expected_port, stadler_instruction). Orchestrator formats one prompt section per device. |

### `issues` — array of objects, required (may be empty)

```json
{"severity": "warning", "category": "config_mismatch", "description": "..."}
```

| Key | Type | Notes |
|---|---|---|
| `severity` | enum | `info`, `warning`, `error` |
| `category` | enum | `obn_patches`, `train_id`, `vlan7`, `cabling`, `firmware`, `ssh`, `unknown` |
| `description` | string | What was found. |
| `escalation_reason` | enum | **Required when the parent report's `status` is `BLOCKED` or `ERROR` AND this issue's `severity` is `error`.** Otherwise omit. Forces the subagent to classify the failure into one of five buckets before escalating, instead of narrating. The orchestrator routes on this field — engineers see the bucket first, the description second. See enum table below. |

**`escalation_reason` enum** (closed set; any other value is a contract violation):

| Value | Meaning | Subagent action |
|---|---|---|
| `known_recipe_failed` | A documented recipe ran cleanly (skill exited 0) but the underlying state didn't end up where it should — e.g. `fix_obn.py` reported success but `--check` re-run still shows missing markers, or `obn update c` returned 0 with "Successful" but the switch is still on the old config. Distinct from `skill_returned_error` (skill itself blew up). | Emit, halt. Do not retry. Engineer triages CCU/device state. |
| `skill_returned_error` | The skill itself blew up — non-zero exit, stack trace, malformed output, or an error class not enumerated in the skill's SKILL.md. The recipe never got to run cleanly. Distinct from `known_recipe_failed` (skill ran clean but reality didn't match). When ambiguous, prefer this bucket — it routes the engineer to fix the tooling rather than the train. | Emit, halt. Engineer triages skill code. |
| `novel_pattern` | A `--check` skill detected a state not covered by any recipe — e.g. an AP firmware version not in the catalogued set, an unknown `train_id` template form, an unrecognised SSH banner. **Subagents must NOT attempt to diagnose novel patterns** (see `dosto-train-worker.md` "What you NEVER do"). | Emit, halt. Engineer triages. |
| `stadler_blocking` | Cabling fault or missing device — Gate 5 (`device_count_mismatch`) territory, or any condition that requires Stadler-side action before Nomad can proceed. | Emit, halt. Orchestrator surfaces in next digest. |
| `train_offline` | SSH/cellular timeout exceeded the 30-min `PAUSED` budget per the train-worker retry policy. | Emit, halt. Orchestrator re-spawns next cycle. |

The point of the enum is not differentiated handling — most values terminate the subagent. The point is **forcing classification before escalation**. A subagent cannot emit `BLOCKED`/`ERROR` with a freeform error description; it must pick a bucket. This keeps subagent context thin (no troubleshooting reasoning in-line) and gives engineers a one-glance triage signal.

### `skill_outputs` — array of objects, required (may be empty)

Captures what each skill said **during the current stage transition**, with raw data the orchestrator can use for cross-validation. **Current-stage only — see "Compactness rules" above.** Prior stages' skill outputs are not re-emitted; the orchestrator/parent maintains the audit trail externally.

Default is `[]` for any report that doesn't have new skill output this cycle (e.g. status pings, gate-approval awaits, simple stage transitions that didn't run a skill).

```json
{
  "skill": "dosto-obn-patches",
  "mode": "check",
  "verdict": "vanilla",
  "raw": {
    "bug1_count": 0,
    "bug2_count": 0,
    "bug3_count": 0,
    "bug4_count": 0,
    "bug5_count": 0,
    "bug6_count": 0,
    "bug7_count": 0,
    "bug8_count": 0,
    "btrfs_subvol": "/.snapshots/run1",
    "uptime_seconds": 1440,
    "train_id_template": "{%- set train_id = 132 -%}",
    "vlan7_live": "172.19.194.2/17"
  }
}
```

`raw` is skill-specific. The contract for what each skill puts in `raw` lives in that skill's SKILL.md, not here.

## Examples

### Initial diagnostics, vanilla CCU

```json
{
  "schema_version": "1",
  "train": {"train_number": "4736-104", "fzg": 132, "ccu_ip": "10.179.10.1", "consist": "6-car"},
  "report_time": "2026-05-09T06:51:00Z",
  "elapsed_seconds": 60,
  "status": "DIAGNOSING",
  "stage": {
    "id": "initial_diagnostics",
    "label": "Reading CCU state",
    "current_step": null,
    "total_steps": null,
    "started_at": "2026-05-09T06:50:00Z",
    "expected_duration_seconds": 60
  },
  "fields": {
    "obn_patches": "0/8 (vanilla)",
    "vlan7_ok": "✅ 172.19.194.2"
  },
  "next_action": "Apply OBN patches outside chroot, then request promote_snapshot approval",
  "approval_needed": null,
  "issues": [],
  "skill_outputs": [
    {"skill": "dosto-obn-patches", "mode": "check", "verdict": "vanilla", "raw": {"bug1_count": 0, "bug2_count": 0, "bug3_count": 0, "bug4_count": 0, "bug5_count": 0, "bug6_count": 0, "bug7_count": 0, "bug8_count": 0, "btrfs_subvol": "/.snapshots/run1", "uptime_seconds": 1440, "train_id_template": "{%- set train_id = 132 -%}", "vlan7_live": "172.19.194.2/17"}},
    {"skill": "dosto-vlan7-config", "mode": "check", "verdict": "all_match", "raw": {"expected": "172.19.194.2/17", "live": "172.19.194.2/17", "nmconnection": "172.19.194.2/17"}}
  ]
}
```

### Approval gate hit (Gate 1: promote_snapshot)

```json
{
  "schema_version": "1",
  "train": {"train_number": "4736-104", "fzg": 132, "ccu_ip": "10.179.10.1", "consist": "6-car"},
  "report_time": "2026-05-09T06:55:00Z",
  "elapsed_seconds": 360,
  "status": "NEEDS_APPROVAL",
  "stage": {
    "id": "await_promote_snapshot",
    "label": "Awaiting approval to enter nd-systemupdate.sh shell",
    "current_step": null,
    "total_steps": null,
    "started_at": "2026-05-09T06:55:00Z",
    "expected_duration_seconds": null
  },
  "fields": {
    "obn_patches": "8/8 (not persisted)",
    "vlan7_ok": "✅ 172.19.194.2"
  },
  "next_action": "Awaiting approval to enter nd-systemupdate.sh shell",
  "approval_needed": {
    "gate": "promote_snapshot",
    "rationale": "All 8 OBN patches applied outside chroot. Re-running --check confirms 8/8 markers present. Promote to btrfs snapshot so they survive reboot.",
    "destructive": true,
    "reversible": false,
    "command_preview": "sudo /usr/sbin/nd-systemupdate.sh shell\n# inside chroot: sudo python3 /tmp/fix_obn.py && sudo python3 /tmp/fix_obn_bug8.py\n# inside chroot: exit\n# promotes work → release → run<N>"
  },
  "issues": [],
  "skill_outputs": [
    {"skill": "dosto-obn-patches", "mode": "check (post-fix)", "verdict": "all_patched", "raw": {"bug1_count": 1, "bug2_count": 2, "bug3_count": 1, "bug4_count": 1, "bug5_count": 1, "bug6_count": 1, "bug7_count": 1, "bug8_count": 1, "btrfs_subvol": "/.snapshots/run1", "uptime_seconds": 1500, "train_id_template": "{%- set train_id = 132 -%}", "vlan7_live": "172.19.194.2/17"}}
  ]
}
```

### Mid-flight pushing config to switches

```json
{
  "schema_version": "1",
  "train": {"train_number": "4736-120", "fzg": 148, "ccu_ip": "10.179.2.1", "consist": "6-car"},
  "report_time": "2026-05-09T07:32:00Z",
  "elapsed_seconds": 1620,
  "status": "PUSHING_TO_DEVICES",
  "stage": {
    "id": "push_switch_config",
    "label": "Pushing v8-148 config to switches",
    "current_step": 7,
    "total_steps": 18,
    "started_at": "2026-05-09T07:14:00Z",
    "expected_duration_seconds": 7560
  },
  "fields": {
    "obn_patches": "8/8 persisted (run5)",
    "switches_v8": "7/18 done, 11 remaining",
    "vlan7_ok": "✅ 172.19.202.2"
  },
  "next_action": "Continuing obn update c per straggler",
  "approval_needed": null,
  "issues": [],
  "skill_outputs": []
}
```

### Done

```json
{
  "schema_version": "1",
  "train": {"train_number": "4736-104", "fzg": 132, "ccu_ip": "10.179.10.1", "consist": "6-car"},
  "report_time": "2026-05-09T07:06:00Z",
  "elapsed_seconds": 1080,
  "status": "DONE",
  "stage": {
    "id": "done",
    "label": "All commissioning complete",
    "current_step": null,
    "total_steps": null,
    "started_at": "2026-05-09T07:06:00Z",
    "expected_duration_seconds": null
  },
  "fields": {
    "obn_patches": "8/8 persisted (run4)",
    "vlan7_ok": "✅ 172.19.194.2",
    "switches_v8": "18/18",
    "aps": "21/21"
  },
  "next_action": null,
  "approval_needed": null,
  "issues": [],
  "skill_outputs": []
}
```

## What this contract does NOT do

- ❌ Define skills' internal output format. Each SKILL.md owns its `raw` keys.
- ❌ Define how the orchestrator pushes to Confluence. See [confluence-sync.md](confluence-sync.md).
- ❌ Define the approval flow protocol. See [approval-gates.md](approval-gates.md) and [autonomy-boundary.md](autonomy-boundary.md).

## Schema validation

The orchestrator should JSON-parse every subagent message and reject any that don't match this shape. A malformed report from a subagent is treated as `status: ERROR` with `issues: [{"severity": "error", "category": "unknown", "description": "subagent emitted invalid JSON"}]` and surfaced to the human.
