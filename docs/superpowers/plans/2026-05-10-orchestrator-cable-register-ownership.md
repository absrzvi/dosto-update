# Orchestrator Cable-Register Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dosto-orchestrator the sole writer of `cable-issues-register.md`, fed by `cable_findings[]` reports from per-train workers gated by per-finding human approval, and consolidate the team Confluence page (`5410684933`) to render exactly two tables — fleet-status and the cable-issues register.

**Architecture:** A new approval gate (Gate 6, `cable_finding`, three-way) extends the existing autonomy boundary. The `dosto-device-discovery` skill, when run by a train-worker, returns a `cable_findings[]` array in addition to its existing diagnostic output. The worker forwards each finding verbatim to the orchestrator via the standard subagent-report `fields.cable_findings` block. The orchestrator surfaces one approval prompt per finding (sequential, never batched), receives `confirmed` / `auto-detected` / `dismiss <reason>`, and on `confirmed`/`auto-detected` writes a row to `cable-issues-register.md` using the file's existing table schema — never modifies existing rows. Confluence sync is rewritten to render only two tables: the fleet-status exec view and the cable-issues register, on the same page. The dosto-auto-scan skill is shelved (not deleted) — its description prefixed `DISABLED — Phase 2`, its `--target cables` Confluence path removed since cable rows no longer go through that skill.

**Tech Stack:** Markdown contracts and agent prompts (no source code change). Atlassian MCP connector for Confluence push. JSON Lines logs for approval-gate audit and dismissal persistence.

---

## Open questions for the engineer (resolve before execution)

These are surfaced explicitly per Principle 1. **Do not start the plan until each is answered.**

1. **Status vocabulary mapping.** The existing `cable-issues-register.md` uses `Status: OPEN | RESOLVED | WONTFIX` per the file's "Conventions" section. Our gate response is `confirmed` / `auto-detected` / `dismiss`. Proposed mapping:
   - `confirmed` → row written with `Status: OPEN` (Stadler action pending — what `OPEN` already means).
   - `auto-detected` → row written with `Status: OPEN` plus `(auto-detected — verify on-site)` appended to the "What we see" cell.
   - `dismiss <reason>` → no row written; reason logged.

   This keeps the register's existing vocabulary intact (Principle 3 — Surgical Changes). The alternative — adding a parallel `Status: confirmed | auto-detected` field — would fork the file's schema and break human readers expecting `OPEN`/`RESOLVED`/`WONTFIX`. **Confirm this mapping is acceptable before starting Task 2.**

2. **Confluence page consolidation scope.** The current page (per `dosto-confluence-sync` SKILL.md §"Page layout") has banner + status legend + Fzg-ID convention + per-series exec table + per-train notes + "How to update". You said "two tables only." Proposed final page layout: banner, status legend, fleet exec table (one section, both 4736 and 4734 in their existing two sub-tables), cable-issues register table. **Drop:** Fzg-ID convention block, per-train notes section, "How to update" section. **Confirm this set of deletions before starting Task 6.**

3. **Existing register rows on first push.** The register currently has 5 rows (#1–#5) all written manually by you. They use `Status: OPEN`. After this change ships, the orchestrator will append to that file. The plan does NOT migrate or rewrite existing rows. **Confirm the orchestrator should leave rows #1–#5 byte-identical, only appending new rows after the last existing one.**

If any answer is unexpected (e.g. you want a separate `Status` field, or you want different page sections dropped), the contract changes in Tasks 2–4 need adjustment before they're written. Halt and discuss.

---

## File structure — what changes, what doesn't

**Boundary principle (Principle 3):** every change traces directly to "orchestrator owns cable register" or "page renders two tables." Nothing else moves.

| File | Change type | Why |
|---|---|---|
| `.claude/contracts/autonomy-boundary.md` | Edit | Add Gate 6 (`cable_finding`, three-way). Add cable-register to "Local file writes" allowlist. Update gate count (5→6) wherever the contract enumerates them. |
| `.claude/contracts/subagent-report.md` | Edit | Add `cable_findings[]` array to the `fields` block schema. Add new gate to the `approval_needed.gate` enum. Add `response_shape: three_way_cable` (distinct from the existing `three_way` because the response value vocabulary differs — `confirmed`/`auto-detected`/`dismiss` vs. `wait`/`partial`/`continue_full`). Add the canonical `cable_finding` stage IDs (`await_cable_finding`, `cable_finding_resolved`). |
| `.claude/contracts/approval-gates.md` | Edit | Add Gate 6 prompt format and three-way response (`c`/`a`/`d <reason>`). Add the dismissal-log file path (`.claude/logs/cable-dismissals.jsonl`). |
| `.claude/contracts/confluence-sync.md` | Edit | Replace Amendment 1 (separate cables page) with single-page-two-tables semantics. Remove `--target` flag references. Add the "drop these sections" list per Open Question 2. |
| `.claude/contracts/auto-scanner-boundary.md` | Edit | Prepend `**Status: DISABLED — Phase 2 deferred.**` notice. No logic changes; contract preserved for future re-enablement. |
| `.claude/agents/dosto-orchestrator.md` | Edit | Add cable-register writer logic: read register, format new row, append after last row, preserve byte-identical existing content. Add Gate 6 handler. Add register to "what you write" / "what you NEVER do" lists. Add cable-finding success-criteria check to end-of-day digest. |
| `.claude/agents/dosto-train-worker.md` | Edit | Document `cable_findings[]` emission. Add Gate 6 to the gates table. Document the `--resume <stage>` behaviour after a cable-finding gate. |
| `.claude/skills/dosto-device-discovery/SKILL.md` | Edit | Add `cable_findings[]` to the `--json` output schema. Each finding carries the evidence block specified in the conversation transcript (link state, PoE draw, LLDP last-seen, MAC table, DHCP leases, RX bytes, cross-checks, suggested register row). |
| `.claude/skills/dosto-confluence-sync/SKILL.md` | Edit | Rewrite §"Page layout (canonical)" to two-tables-only. Drop `--target` flag. Add cable-register parser + renderer. Drop `--target cables` page bootstrap dependency on auto-scan. |
| `.claude/skills/dosto-auto-scan/SKILL.md` | Edit (description only) | Prepend `DISABLED — Phase 2 deferred. Cable register is now orchestrator-owned per autonomy-boundary.md Gate 6.` to the skill description. No procedural changes. |
| `CLAUDE.md` | Edit | Update "orchestration architecture" section to show orchestrator writing both files. Add Gate 6 to the contracts/gates summary. |
| `cable-issues-register.md` | Untouched | Existing rows #1–#5 remain byte-identical (Principle 3). Future rows appended by orchestrator follow the existing 9-column table schema. |
| Workspace `.claude/logs/cable-dismissals.jsonl` | New file (created on first dismissal) | One JSON-Lines entry per dismissed finding. Used by future workers to skip re-prompting on already-dismissed findings. |
| `scripts/regenerate_bootstrap.py` | Untouched in this plan | Re-run by engineer post-merge to refresh `BOOTSTRAP_DOSTO_v1.md`. Not a plan task because it's mechanical. |

---

## Task 1: Confirm open questions and freeze contract direction

**Files:**
- Read: `docs/superpowers/plans/2026-05-10-orchestrator-cable-register-ownership.md` (this file)

- [ ] **Step 1: Read the three open questions at the top of this plan**

- [ ] **Step 2: Engineer answers each one (yes / no / variant) in chat or as edits to this plan**

- [ ] **Step 3: If any answer is "no" or "variant," halt and re-plan**

Goal-driven success criterion: this plan is unambiguous and the engineer's answers are recorded. If you cannot point to an explicit answer for each of the three open questions, do not proceed to Task 2.

---

## Task 2: Add Gate 6 to autonomy-boundary.md

**Files:**
- Modify: `.claude/contracts/autonomy-boundary.md`

- [ ] **Step 1: Update the gate count in §"TL;DR" and §"Approval gates"**

Edit `.claude/contracts/autonomy-boundary.md`:

Replace the line that reads:

```
There are exactly **five** gates. Hitting any of them sets `status = NEEDS_APPROVAL` in the JSON report, sets `stage.id` to the corresponding `await_*` value, and pauses the subagent until a response is relayed back.
```

With:

```
There are exactly **six** gates. Hitting any of them sets `status = NEEDS_APPROVAL` in the JSON report, sets `stage.id` to the corresponding `await_*` value, and pauses the subagent until a response is relayed back.
```

- [ ] **Step 2: Append Gate 6 row to the gates summary table**

Find the table (currently lines 43–49) and add a new row after the `device_count_mismatch` row:

```markdown
| `cable_finding` | `await_cable_finding` | **three-way** (`confirmed` / `auto-detected` / `dismiss <reason>`) |
```

- [ ] **Step 3: Add §"Gate 6: cable_finding — three-way, not binary" section after §"Gate 5"**

Insert this content after the existing Gate 5 section (after the line "What approval costs the human: ~30 seconds reading the per-device Stadler-actionable instructions and choosing the default (`partial`) or one of the alternatives.") and before "### What about AP factory-config bypass?":

```markdown
### Gate 6: `cable_finding` — three-way, not binary

**Trigger:** subagent's `dosto-device-discovery` skill localised one or more missing devices (AP or switch) to a specific switch+port AND the per-port evidence rules out the non-cable explanations (factory-config AP, deliberately-omitted coach). Each finding fires its own gate — never batched. A train with 3 missing APs produces 3 sequential gates.

**Why approval needed:**
- Each row appended to `cable-issues-register.md` is the basis for an EMEAE Stadler ticket. The register is what the PM reads to escalate. A wrongly-written row sends Stadler to the wrong port.
- The register's `Status: OPEN` field already implies "Stadler action pending." Writing without engineer eyes-on means we may escalate things that aren't actually Stadler's responsibility (e.g. an AP that's powered off pending factory-config bypass — Nomad's job, not Stadler's).
- The engineer is the only one with full context — sometimes a missing device is known to be deliberately removed (coach out of service), in which case the row should not be written at all.

**Three-way response options:**

| Response | What the orchestrator does next |
|---|---|
| `confirmed` | Append row to `cable-issues-register.md` with `Status: OPEN`. The "What we see" cell carries the evidence verbatim from the worker's report. The "Required action" cell carries the worker-drafted Stadler instruction (engineer hand-edits later if wording needs tightening — Principle 3). The subagent resumes at `cable_finding_resolved`. |
| `auto-detected` | Append row with `Status: OPEN` and the literal suffix `(auto-detected — verify on-site)` appended to the "What we see" cell. Used when the evidence is suspicious but the engineer hasn't been on the train recently and doesn't want to escalate to Stadler until physical verification. Subagent resumes at `cable_finding_resolved`. |
| `dismiss <reason>` | Do not write to register. Append a JSON Lines entry to `.claude/logs/cable-dismissals.jsonl` with `{ts, train, finding_hash, reason, engineer}`. The hash is computed by the worker over the (train, slot, expected_switch, expected_port) tuple — future workers grep this file before emitting an identical finding, suppressing the gate. Subagent resumes at `cable_finding_resolved`. |
| `defer` | Re-prompt at next 5-min cycle. Subagent stays at `await_cable_finding`. |

**What the subagent has done before this gate:**
- Run `dosto-device-discovery` with localisation step (Step 7 in the skill)
- Localised every missing device to a specific switch + port
- Gathered the evidence block (link state, PoE draw, LLDP last-seen, MAC table, DHCP leases on the port, RX bytes, cross-check that adjacent ports are healthy)
- Drafted a suggested register row including the Stadler-actionable instruction
- Computed the finding hash
- Grepped `.claude/logs/cable-dismissals.jsonl` for that hash — skipped emission if already dismissed

**Per-finding (not per-train) granularity:** if a 6-car train has 3 missing devices, the worker emits 3 separate `await_cable_finding` reports in sequence (one resolves before the next is emitted). This deliberately makes the engineer say `confirmed` / `auto-detected` / `dismiss` 3 times. The gate cost is high precisely because each row sent to Stadler must be deliberate. Batched-per-train would be faster but would produce rubber-stamping — exactly the pattern we forbid for the existing 5 gates.

**What approval costs the human:** ~30 seconds per finding reading the evidence block and choosing one of the three responses.
```

- [ ] **Step 4: Add cable-register to §"Local file writes"**

Find this line (currently line 36):

```markdown
- Append/update rows in local `fleet-status.md` (orchestrator only — subagents emit JSON reports, never write the file)
```

Add immediately after it:

```markdown
- Append rows to local `cable-issues-register.md` (orchestrator only, on `confirmed`/`auto-detected` resolution of Gate 6 — subagents emit `cable_findings[]` in their JSON reports, never write the file). Existing rows are never modified or deleted.
```

- [ ] **Step 5: Update §"Validating compliance" to enumerate six patterns**

Find the bulleted list (currently lines 171–174) and append:

```markdown
- Direct edits to `cable-issues-register.md` outside an approved Gate 6 resolution
```

- [ ] **Step 6: Verify the contract reads cleanly**

Run: `Grep -n "cable_finding\|six gates\|Gate 6" .claude/contracts/autonomy-boundary.md`

Expected: each phrase appears in the right section. The "five" wording from the previous version no longer appears anywhere in the file (use `Grep -n "exactly \*\*five\*\*"` to confirm zero matches).

- [ ] **Step 7: Commit**

```bash
git add .claude/contracts/autonomy-boundary.md
git commit -m "contracts: add Gate 6 cable_finding to autonomy-boundary"
```

---

## Task 3: Add cable_findings schema to subagent-report.md

**Files:**
- Modify: `.claude/contracts/subagent-report.md`

- [ ] **Step 1: Add `cable_findings` to §"fields" reference table**

Find the fields table (currently lines 152–162) and append a new row at the end:

```markdown
| `cable_findings` | array\|null | see schema below | (no fleet-status mapping — feeds cable-issues-register.md via Gate 6) |
```

- [ ] **Step 2: Add the cable_findings schema sub-section after §"fields"**

Add this content immediately after the line "The subagent reports only fields it actually checked this cycle. Fields it didn't touch should be omitted from the JSON object — orchestrator preserves the existing fleet-status value for any omitted field. This avoids accidentally clobbering data with `null`.":

````markdown
#### `cable_findings` — array of objects (within `fields`)

Emitted by `dosto-device-discovery` when localisation pinpoints a missing device to a specific switch+port AND the evidence rules out non-cable explanations. Each element triggers one Gate 6 (`cable_finding`) approval. The orchestrator iterates the array sequentially.

```json
{
  "finding_hash": "sha256:f3ab12...",
  "slot": "D4",
  "coach": "D",
  "expected_switch": "D3",
  "expected_switch_ip": "10.179.10.193",
  "expected_port": "e1-2",
  "evidence": {
    "link_state": "UP, 1 Gbps full-duplex",
    "poe_draw_watts": 0.0,
    "poe_expected_watts_min": 5.0,
    "lldp_last_seen": "never (since switch boot 14d ago)",
    "mac_table_on_port": [],
    "dhcp_leases_on_port": [],
    "rx_bytes_total": 312,
    "rx_bytes_window_seconds": 1209600,
    "adjacent_ports_health": "e0-0/e0-1 UP, RX CRC 0, carrier-false 0"
  },
  "cross_checks": {
    "other_devices_on_consist": "23/24 APs reachable",
    "port_config_matches_schema": true,
    "port_error_counters_clean": true,
    "factory_config_ap_ruled_out": true
  },
  "pattern_match": "Link UP but no AP seen — Stadler cable issue (per train-login-checklist.md row 3)",
  "suggested_register_row": {
    "trainset": "4736-104",
    "consist": "6-car",
    "switch": "D3",
    "ports": "e1-2 (AP D4 trunk)",
    "fault_type": "AP not connected",
    "what_we_see_vs_plan": "Link UP at 1G, zero PoE, no LLDP, no MAC learned. Plan: AP D4 visible.",
    "required_action": "Verify AP D4 physically present in coach D FIS-4; verify Cat6A patch from D3:e1-2 to AP D4 is seated both ends; confirm AP power LED.",
    "status": "OPEN"
  }
}
```

| Key | Type | Required | Notes |
|---|---|---|---|
| `finding_hash` | string | yes | SHA-256 over `<train_number>:<slot>:<expected_switch>:<expected_port>` (no spaces, lowercase). Used to dedupe against `.claude/logs/cable-dismissals.jsonl` — if a worker computes a hash already dismissed, it MUST omit the finding from `cable_findings[]`. |
| `slot` | string | yes | e.g. `"D4"` for AP4 in coach D. For missing switches, the position label (`"E2"`). |
| `coach` | string | yes | First letter of slot. |
| `expected_switch` | string | yes | Generic switch ID (no IP). |
| `expected_switch_ip` | string | yes | Live management IP from `dhcp-lease-list`. |
| `expected_port` | string | yes | Port label (`"e1-2"`, `"e0-4"`). |
| `evidence` | object | yes | Free-form per the example above. The orchestrator includes the entire `evidence` object verbatim in the gate prompt. |
| `cross_checks` | object | yes | The four boolean checks shown above plus any skill-specific extras. |
| `pattern_match` | string | yes | One sentence naming the pattern, with reference to a known doc (train-login-checklist row, CLAUDE.md pitfall, etc.). |
| `suggested_register_row` | object | yes | The eight columns of `cable-issues-register.md` (all except the leading `#` which the orchestrator assigns). On `confirmed`/`auto-detected`, the orchestrator writes these values into the row. |

**Hashing rule (canonical):** `sha256(f"{train_number}:{slot}:{expected_switch}:{expected_port}".encode()).hexdigest()` — the prefix `sha256:` is added when the hash is emitted in JSON for readability; the `.jsonl` file stores the same prefixed form.
````

- [ ] **Step 3: Add the new gate to the §"approval_needed" enum**

Find the row in the table (currently lines 191) that reads:

```markdown
| `gate` | enum | One of: `promote_snapshot`, `safe_reboot`, `obn_update_c`, `obn_update_f`, `device_count_mismatch`. The five gates from the autonomy boundary in [autonomy-boundary.md](autonomy-boundary.md). |
```

Replace with:

```markdown
| `gate` | enum | One of: `promote_snapshot`, `safe_reboot`, `obn_update_c`, `obn_update_f`, `device_count_mismatch`, `cable_finding`. The six gates from the autonomy boundary in [autonomy-boundary.md](autonomy-boundary.md). |
```

Find the row that reads:

```markdown
| `response_shape` | enum | `binary` (gates 1–4) or `three_way` (gate 5 only). Tells the orchestrator how to format the prompt and parse the response. |
```

Replace with:

```markdown
| `response_shape` | enum | `binary` (gates 1–4), `three_way` (gate 5: `wait`/`partial`/`continue_full`), or `three_way_cable` (gate 6: `confirmed`/`auto-detected`/`dismiss`). Tells the orchestrator how to format the prompt and parse the response. |
```

Find the row that reads:

```markdown
| `missing_devices` | array | Only present when `gate == device_count_mismatch`. Per-device structured info from `dosto-device-discovery` output (slot, expected_switch, expected_port, stadler_instruction). Orchestrator formats one prompt section per device. |
```

Add immediately after it:

```markdown
| `cable_finding` | object | Only present when `gate == cable_finding`. The single `cable_findings[]` element being approved this gate (per-finding granularity, not batched). Contains all keys from the `cable_findings` schema above. |
```

- [ ] **Step 4: Add the canonical stage IDs**

Find the canonical stage list table (currently lines 120–143) and add two new rows after the `await_device_count_mismatch` row:

```markdown
| `await_cable_finding` | `NEEDS_APPROVAL` | — | Gate 6: `cable_finding` — three-way response. Fired once per element of `cable_findings[]`. The orchestrator iterates the array; the worker re-emits this stage with the next finding after each resolution. |
| `cable_finding_resolved` | `DIAGNOSING` | 5s | Transient stage between resolutions. Worker emits one report at this stage with `cable_findings[]` reduced by the resolved element, then immediately emits the next `await_cable_finding` if more remain, or transitions to whatever stage was running before the first cable finding. |
```

- [ ] **Step 5: Verify schema is cleanly added**

Run: `Grep -n "cable_finding\|cable_findings" .claude/contracts/subagent-report.md`

Expected: appears in (a) fields reference table, (b) cable_findings schema sub-section, (c) approval_needed gate enum, (d) approval_needed response_shape enum, (e) approval_needed cable_finding row, (f) two stage rows. Six locations total.

- [ ] **Step 6: Commit**

```bash
git add .claude/contracts/subagent-report.md
git commit -m "contracts: add cable_findings schema and Gate 6 stages to subagent-report"
```

---

## Task 4: Add Gate 6 prompt format to approval-gates.md

**Files:**
- Modify: `.claude/contracts/approval-gates.md`

- [ ] **Step 1: Add §"Three-way cable gate (`cable_finding` only)" after §"Three-way gate (`device_count_mismatch` only)"**

After the current §"Three-way gate" subsection (currently ending around line 87 with "Note that the three-way default is `partial` (the safest middle path), not deny — different from binary gates where empty input means deny."), add this new sub-section:

````markdown
### Three-way cable gate (`cable_finding` only)

| Input | Meaning |
|---|---|
| `c` or `confirmed` | Append row to `cable-issues-register.md` with `Status: OPEN`. Treat as Stadler-actionable. Subagent resumes at `cable_finding_resolved`. |
| `a` or `auto-detected` | Append row with `Status: OPEN` AND the suffix `(auto-detected — verify on-site)` appended to the "What we see" cell. Subagent resumes at `cable_finding_resolved`. |
| `d <reason>` or `dismiss <reason>` | Do not write row. Append `{ts, train, finding_hash, reason, engineer}` to `.claude/logs/cable-dismissals.jsonl`. Subagent resumes at `cable_finding_resolved`. **Reason is mandatory** — typing `d` alone or `dismiss` alone is treated as malformed (re-prompt with hint). |
| `defer` or *(empty)* | Defer for later. Subagent stays at `await_cable_finding`, re-prompts next cycle. |

There is no default — empty input maps to `defer`, NOT to one of the three actions. The reason: the existing default-on-empty rule for Gate 5 is justified because `partial` is genuinely the safest action; for Gate 6 the safest action depends on the engineer's external knowledge (have they been on the train recently? is Stadler already aware?), so any default would be wrong half the time.

The dismissal reason is free-form string up to 200 chars. Examples that are useful: `"coach D out of service per ÖBB notice 2026-04-30"`, `"AP-D4 awaiting factory replacement, register row #5 already covers this"`, `"false positive — switch was rebooting during scan"`. A reason of `"."` or empty is rejected.

#### Prompt format

When `gate == cable_finding`, the orchestrator formats the prompt using the worker's `evidence`, `cross_checks`, `pattern_match`, and `suggested_register_row` fields:

```
═══════════════════════════════════════════════════════════════
  CABLE FINDING — Fzg <NNN> (<train_number>) — train-worker
  Stage: <previous_stage> → device-discovery
═══════════════════════════════════════════════════════════════

Missing device: <slot> (expected at coach <coach>, FIS unit <slot_digit>)
Expected MAC OUI: <00:14:5a if AP, a0:59:3a if switch>
Expected from schema: ND-DEL-OBB-035-IPA-<NNN>_NV_<consist>.pdf

Localised to: switch <expected_switch> (<expected_switch_ip>) port <expected_port>
  ├─ Link state:        <evidence.link_state>
  ├─ PoE draw:          <evidence.poe_draw_watts> W   (expected ~<evidence.poe_expected_watts_min> W minimum)
  ├─ LLDP neighbour:    <evidence.lldp_last_seen>
  ├─ MAC table on <port>: <evidence.mac_table_on_port or "empty">
  ├─ DHCP leases:       <evidence.dhcp_leases_on_port or "no matching lease">
  └─ RX bytes:          <evidence.rx_bytes_total> B in <evidence.rx_bytes_window_seconds/86400> days

Cross-checks:
  ├─ <cross_checks formatted as bullet list>

Pattern match: <pattern_match>

Suggested register row:
  Trainset:     <suggested_register_row.trainset>
  Consist:      <suggested_register_row.consist>
  Switch+port:  <suggested_register_row.switch> <suggested_register_row.ports>
  Fault type:   <suggested_register_row.fault_type>
  What we see:  <suggested_register_row.what_we_see_vs_plan>
  Action:       <suggested_register_row.required_action>

═══════════════════════════════════════════════════════════════
Respond with one of:
  c | confirmed         — write Status: OPEN, escalate to Stadler
  a | auto-detected     — write Status: OPEN with "(auto-detected — verify on-site)" suffix
  d <reason> | dismiss <reason>  — don't write; log reason for future scans
  defer                 — re-prompt next cycle
═══════════════════════════════════════════════════════════════
```

The default is **defer** (empty input). There is no positive default for Gate 6.
````

- [ ] **Step 2: Update §"What the subagent gets back" with the new gate**

After the current §"Three-way gate (`device_count_mismatch`)" subsection (ending around line 107 with "Anything malformed = treat as `partial` (the safest middle option, not deny)."), add:

````markdown
### Three-way cable gate (`cable_finding`)

```
{"approval": "confirmed" | "auto-detected" | "dismiss", "approved_by": "human-cli", "approved_at": "2026-05-09T06:55:30Z", "dismiss_reason": "<string, only when approval==dismiss>"}
```

Anything malformed = treat as `defer` (re-prompt next cycle). Empty `dismiss_reason` when `approval==dismiss` is malformed.
````

- [ ] **Step 3: Update §"Logging" to mention the new log file**

Find the existing logging section (currently around lines 142–152) and add to the bullet list of "Useful for":

```markdown
- Cable-finding dismissals are persisted to `.claude/logs/cable-dismissals.jsonl` (separate file) so future workers don't re-prompt on already-dismissed findings — finding-hash dedup.
```

- [ ] **Step 4: Verify**

Run: `Grep -n "cable_finding\|three_way_cable\|cable-dismissals" .claude/contracts/approval-gates.md`

Expected: each phrase appears in the right sub-section. Sub-section order: existing 3-way, then 3-way-cable.

- [ ] **Step 5: Commit**

```bash
git add .claude/contracts/approval-gates.md
git commit -m "contracts: add Gate 6 cable_finding prompt format and three-way response"
```

---

## Task 5: Update auto-scanner-boundary.md to DISABLED status

**Files:**
- Modify: `.claude/contracts/auto-scanner-boundary.md`

- [ ] **Step 1: Prepend DISABLED notice at the top of the file**

After the existing `# Auto-Scanner Boundary` header and the `**Status:**` line (currently line 3), insert:

```markdown
> **⚠️ DISABLED — Phase 2 deferred (2026-05-10).**
> The auto-scanner is not running. Cable register rows are now written exclusively by the orchestrator via the [Gate 6 `cable_finding`](autonomy-boundary.md) approval flow, fed by `cable_findings[]` in subagent reports. This contract is preserved for the future Phase 2 re-enablement (passive 30-min fleet scan), but has zero current effect on the workflow.
>
> When re-enabling: this contract MUST be reconciled with autonomy-boundary.md Gate 6 — pick one writer or define explicit lane separation. Two writers to `cable-issues-register.md` is a contract violation per autonomy-boundary §"Local file writes".
```

- [ ] **Step 2: Verify**

Run: `Read .claude/contracts/auto-scanner-boundary.md` — confirm the DISABLED block appears between line 3 and the existing "What the scheduled auto-scanner..." paragraph.

- [ ] **Step 3: Commit**

```bash
git add .claude/contracts/auto-scanner-boundary.md
git commit -m "contracts: mark auto-scanner-boundary DISABLED — Phase 2 deferred"
```

---

## Task 6: Rewrite confluence-sync.md for single-page-two-tables

**Files:**
- Modify: `.claude/contracts/confluence-sync.md`

- [ ] **Step 1: Update §"What gets pushed" to specify two tables only**

Find the current §"What gets pushed" content (lines 38–42) and replace with:

```markdown
## What gets pushed

The Confluence page renders **exactly two tables**:

1. **Fleet status exec view** — derived from `fleet-status.md`, columns: `Fzg`, `Train#`, `CCU IP`, `Status`, `Next action`. Two sub-tables (4736 series and 4734 series) per the existing layout.
2. **Cable-issues register** — derived from `cable-issues-register.md`, all 9 columns: `#`, `Trainset`, `Consist`, `Switch`, `Port(s)`, `Fault type`, `What we see vs. what plan says`, `Required action`, `Status`. Both `OPEN` and `RESOLVED` rows render; `WONTFIX` rows render with strikethrough.

Sections explicitly **NOT** rendered to the page (deliberately — Principle 2 Simplicity First, dropped per engineer instruction 2026-05-10):

- Fzg-ID convention block (engineers know the formula; it's in CLAUDE.md)
- Per-train notes section (large, redundant with `fleet-status.md` notes; engineers debugging a specific train work from the local workspace)
- "How to update" section (engineers update `fleet-status.md` and run the sync skill — no Confluence-side update path)
- Status legend (small enough to keep, kept by default per the existing skill, but trimmed to the 5 actually-used statuses if any are no longer in use)
- Banner (kept — drift detection signal AND timestamp, per the existing contract)

The push body is the entire page replacement. Confluence's `updateConfluencePage` is whole-page-replace; there's no field-level patching.
```

- [ ] **Step 2: Update §"When the orchestrator pushes" to mention cable-register triggers**

Find the trigger list (currently lines 27–33) and add:

```markdown
- Any `cable_findings[]` resolution that resulted in a row append (Gate 6 `confirmed` or `auto-detected`)
- Any engineer hand-edit to `cable-issues-register.md` detected at cycle boundary (mtime newer than last push)
```

- [ ] **Step 3: Replace Amendment 1 entirely**

Remove the existing §"Amendment 1 — Cable register sync (`--target cables`)" section (currently lines 135–209) and replace with:

````markdown
## Amendment 1 — Cable register on the same page

**Status:** v1.2, replaces the v1.1 separate-page design (2026-05-10).

The cable-issues register renders below the fleet-status exec table on the same page (`5410684933`). There is no separate cables page. The auto-scanner's `--bootstrap-confluence-cables` flow is no longer relevant (auto-scanner is DISABLED — see [auto-scanner-boundary.md](auto-scanner-boundary.md)).

### Page layout (canonical)

```
[Banner — auto-sync timestamp + version]

[Status legend — 5-row table]

# Fleet status

[4736 series exec table]

[4734 series exec table]

# Cable-issues register

[9-column table — all OPEN rows first, then RESOLVED rows, WONTFIX rows last with strikethrough]
```

### Cable-register render rules

- Parse `cable-issues-register.md` row-by-row. The file's "Open issues" table and "Resolved issues" section are merged into one rendered table on Confluence, sorted: `OPEN` rows first (by `#`), then `RESOLVED` rows (by `#`), then `WONTFIX` rows (by `#`).
- Row `#` numbering preserved exactly from local file.
- `Status` column rendered with emoji prefix for visual scan: `🔴 OPEN`, `✅ RESOLVED`, `⬜ WONTFIX`.
- `WONTFIX` rows rendered with `~~strikethrough~~` on the entire row content (markdown supports this; round-trips through Confluence as struck text).
- Long cells (especially "What we see" and "Required action") wrap natively. No truncation.
- If the file has no rows (empty register), render `*(no cabling issues currently logged)*` instead of an empty table.

### Drift detection — same semantics

The page version counter applies to the whole page. A manual edit to either the fleet section or the cable-register section produces the same drift event. The drift log entry `target` field is no longer used (only one page).

### Push trigger

Orchestrator-driven (per the main contract trigger list above). The engineer can also invoke `/dosto-confluence-sync --push` manually.
````

- [ ] **Step 4: Verify**

Run: `Grep -n "Amendment 1\|cable-issues register\|two tables" .claude/contracts/confluence-sync.md`

Expected: Amendment 1 exists with v1.2 status, references "two tables" and "same page", no longer references `--target cables` or `confluence-pages.json`.

- [ ] **Step 5: Commit**

```bash
git add .claude/contracts/confluence-sync.md
git commit -m "contracts: confluence sync renders one page, two tables (fleet + cables)"
```

---

## Task 7: Update dosto-orchestrator.md with cable-register writer logic

**Files:**
- Modify: `.claude/agents/dosto-orchestrator.md`

- [ ] **Step 1: Update §"You are the only entity that:" to include the cable register**

Find the current bullet list (lines 13–17) and replace:

```markdown
- Writes `fleet-status.md` (orchestrator-as-sole-writer per `.claude/contracts/confluence-sync.md`)
```

With:

```markdown
- Writes `fleet-status.md` (orchestrator-as-sole-writer per `.claude/contracts/autonomy-boundary.md`)
- Appends rows to `cable-issues-register.md` on Gate 6 (`cable_finding`) `confirmed` / `auto-detected` resolution (orchestrator-as-sole-writer per `.claude/contracts/autonomy-boundary.md`)
```

- [ ] **Step 2: Add a new §"Cable register writer" section after §"Fleet-status writer"**

Insert this content after the existing §"Fleet-status writer" section (after the "This is Principle 3 (Surgical Changes) in concrete form: the orchestrator owns exactly the eight columns above and nothing else." line):

````markdown
## Cable register writer

You also own `cable-issues-register.md`. The discipline mirrors fleet-status: read once, append rows from approved findings, write once, never modify existing rows.

### When to write

You append exactly one row per `confirmed` or `auto-detected` resolution of Gate 6 (`cable_finding`). On `dismiss` you write nothing to the register — the dismissal goes to `.claude/logs/cable-dismissals.jsonl` instead.

### Append procedure

1. Read `cable-issues-register.md`.
2. Find the largest existing `#` value in the "Open issues" table.
3. Compute new row's `#` = max existing + 1.
4. Format the new row using the worker's `suggested_register_row` from the gate's `approval_needed.cable_finding` block:

   ```markdown
   | <new_#> | <trainset> | <consist> | <switch> | <ports> | <fault_type> | <what_we_see_or_with_auto-detected_suffix> | <required_action> | OPEN |
   ```

   For `auto-detected` resolution, the `what_we_see_vs_plan` cell gets the literal suffix ` (auto-detected — verify on-site)` appended.

5. Edit the file in place, inserting the new row immediately after the last existing row in the "Open issues" table (i.e., after the row with the largest `#`).
6. Existing rows are byte-identical to before the edit. **Do not** re-format whitespace, re-align columns, or "tidy" anything else in the file (Principle 3).

### What you NEVER write to the register

- ❌ Modifications to existing rows (engineer hand-edits these, you don't)
- ❌ Status changes from `OPEN` → `RESOLVED` (engineer does this manually after Stadler confirms fix)
- ❌ Row deletions
- ❌ Edits to "Conventions", "Resolved issues", "How to add a new entry", or "Related artefacts" sections
- ❌ Rows on `dismiss` resolution

### Dismissal log

On `dismiss <reason>` resolution, append a single line to `.claude/logs/cable-dismissals.jsonl`:

```json
{"ts":"2026-05-10T14:32:00Z","train":"4736-104","fzg":132,"finding_hash":"sha256:...","slot":"D4","expected_switch":"D3","expected_port":"e1-2","reason":"AP awaiting factory replacement, register row #5 already covers this","engineer":"Abbas Rizvi","subagent":"train-fzg-132"}
```

The file is created on first dismissal if it doesn't exist. Workers grep this file at the start of every device-discovery run to suppress already-dismissed findings.

### Atomicity

Read the register once, compute the row, write once. If you're processing a queue of resolved cable findings, batch the writes (one read, append all approved rows, one write). Don't write partial state.

### Hand-edit preservation

If between cycles the engineer hand-edits the register (e.g. moves a row from "Open" to "Resolved", adds a `Report:` link in the action cell, or fixes typos in your appended row), preserve those edits byte-identically on the next cycle. Your only operation is **append** — never re-emit existing rows.
````

- [ ] **Step 3: Add Gate 6 to the approval flow**

Find §"Approval flow" (currently around lines 156–212). Update the "parse the response" sub-step (currently mentioning binary and three-way gates) to add a third sub-bullet:

```markdown
   - **Three-way cable gate** (`cable_finding`):
     - `c` / `confirmed` → `{"response": "confirmed"}`
     - `a` / `auto-detected` → `{"response": "auto-detected"}`
     - `d <reason>` / `dismiss <reason>` → `{"response": "dismiss", "dismiss_reason": "<reason>"}`
     - `defer` / *(empty)* → keep in queue, re-prompt next cycle
     - `dismiss` with empty reason → treat as defer with warning "dismissal requires a reason"
```

- [ ] **Step 4: Add Gate 6 prompt formatter to "What the orchestrator shows the human"**

After the existing approval prompt example (currently around lines 163–183), add:

````markdown
For Gate 6 (`cable_finding`), the prompt uses the format from [`approval-gates.md`](../contracts/approval-gates.md) §"Three-way cable gate". You compose it from `approval_needed.cable_finding.evidence`, `cross_checks`, `pattern_match`, and `suggested_register_row`. Each finding gets its own prompt — never batch multiple findings into one prompt.

If a worker emits a report with `cable_findings.length > 1`, surface them sequentially: present finding 1, get response, write or dismiss, then present finding 2. The worker holds at `await_cable_finding` until the entire array is resolved.
````

- [ ] **Step 5: Add Gate 6 to the §"Logging" entries**

The existing approval-gates.jsonl already covers Gate 6 (it was generic to all gates). Add a single line to the file table:

```markdown
| `.claude/logs/cable-dismissals.jsonl` | Each `dismiss <reason>` resolution of Gate 6. Read by future workers to suppress duplicate findings. |
```

- [ ] **Step 6: Update Confluence push triggers**

Find the trigger table (currently around lines 270–276) and add a row:

```markdown
| Any cable-issues-register.md row appended (Gate 6 confirmed/auto-detected) | Push immediately |
```

- [ ] **Step 7: Add cable-register success criteria to end-of-day digest**

Find the §"End of day" / per-train success criteria block (currently around lines 298–337) and after the existing per-train ✓/✗ examples, add a guidance paragraph:

```markdown
### Cable-register additions during the day

In the end-of-day digest, list every row appended to `cable-issues-register.md` during this session:

```
▼ Cable register additions (this session): 2
  • Row #6 (Fzg 132 / 4736-104 / D3 e1-2) — confirmed at 13:14, suggested action: replace patch cable
  • Row #7 (Fzg 130 / 4736-102 / B1 e1-11) — auto-detected at 16:02, needs on-site verification
```

If zero rows were appended, omit the section entirely. If one or more rows were dismissed (Gate 6 `dismiss`), list them under "Cable findings dismissed (this session): N" with reasons.
```

- [ ] **Step 8: Update §"What you NEVER do" with cable-register guards**

Find the bullet list (currently lines 367–378) and add:

```markdown
- ❌ **Modify existing rows in `cable-issues-register.md`.** Append-only. Engineer manages row state transitions (OPEN → RESOLVED, etc.).
- ❌ **Skip the gate on a cable finding.** Even when the evidence looks unambiguous. The 30-second cost per finding is the feature.
- ❌ **Batch multiple cable findings into one prompt.** One gate per finding.
```

- [ ] **Step 9: Verify**

Run: `Grep -n "cable_finding\|cable-issues-register\|Gate 6" .claude/agents/dosto-orchestrator.md`

Expected: appears in (a) "you are the only entity" list, (b) approval flow parser, (c) prompt format note, (d) logging table, (e) Confluence push triggers, (f) end-of-day digest, (g) "what you NEVER do", (h) new §"Cable register writer" section.

- [ ] **Step 10: Commit**

```bash
git add .claude/agents/dosto-orchestrator.md
git commit -m "orchestrator: add cable-register writer and Gate 6 handler"
```

---

## Task 8: Update dosto-train-worker.md to emit cable_findings

**Files:**
- Modify: `.claude/agents/dosto-train-worker.md`

- [ ] **Step 1: Add Gate 6 to the gates table**

Find the table (currently lines 142–149) and append:

```markdown
| 6 — `cable_finding` | Triggered by `dosto-device-discovery` finding missing devices localised to a switch+port AND ruling out non-cable causes | three-way (`confirmed` / `auto-detected` / `dismiss <reason>`) |
```

- [ ] **Step 2: Add cable_findings emission discipline to §"What you do without asking"**

After the existing read-only operations list, add a new sub-section:

````markdown
### Cable-findings emission

When `dosto-device-discovery --json` returns `verdict: missing_devices_recoverable` or `missing_devices_severe`, the skill output includes a `cable_findings[]` array (per [.claude/skills/dosto-device-discovery/SKILL.md](../skills/dosto-device-discovery/SKILL.md) §"Output formats"). Forward this array verbatim into your next subagent-report at `fields.cable_findings`.

**Before forwarding,** dedupe against `.claude/logs/cable-dismissals.jsonl`:

1. Read the file (skip if missing).
2. For each `cable_findings[]` element, compute `finding_hash` per the canonical hashing rule (`sha256(f"{train_number}:{slot}:{expected_switch}:{expected_port}".encode()).hexdigest()`).
3. If the hash already appears in the log file, omit that element from the array. Add an entry to your `issues[]`: `{"severity":"info","category":"cabling","description":"Suppressed duplicate cable finding D4 — previously dismissed (hash sha256:...)"}`.

Findings that survive dedup are emitted in the report. The orchestrator will then surface Gate 6 prompts one finding at a time. Your loop:

1. Emit report with `fields.cable_findings: [<all surviving findings>]` and `status: NEEDS_APPROVAL`, `stage.id: await_cable_finding`, `approval_needed.gate: cable_finding`, `approval_needed.cable_finding: <first element>`.
2. Wait for `SendMessage` from orchestrator with response.
3. On `confirmed` or `auto-detected`: emit one report at `stage.id: cable_finding_resolved` with `cable_findings[]` reduced by the resolved element. If more remain, immediately emit the next `await_cable_finding` with the next element. If zero remain, transition to whatever stage was running before the first cable finding (typically the next stage after `initial_diagnostics`).
4. On `dismiss`: same as above. The worker does not write the dismissal log — the orchestrator does.
5. On `defer`: stay at `await_cable_finding` with the same `approval_needed.cable_finding` element. Re-emit the report at next cycle.

**You never write to `cable-issues-register.md` or `.claude/logs/cable-dismissals.jsonl`.** The orchestrator does both. Your role is to discover, hash, dedupe, and surface — same as every other gate.
````

- [ ] **Step 3: Add a third example flow showing Gate 6 to §"Example flows"**

After Example 3 (currently around line 242), add:

````markdown
### Example 4 — Cable findings (Gate 6, sequential per-finding)

```
Skill emits stage 1 report (DIAGNOSING).
Skill output includes cable_findings: [
  {finding_hash: "sha256:abc...", slot: "D4", ...},
  {finding_hash: "sha256:def...", slot: "B1-AP", ...}
]
Subagent reads cable-dismissals.jsonl — neither hash present.
Subagent emits report with status: NEEDS_APPROVAL, stage.id: await_cable_finding,
  approval_needed.cable_finding = first element (D4).
Halts.

Orchestrator gets human response: "confirmed"
Orchestrator writes row to cable-issues-register.md, sends SendMessage.

Subagent emits report at stage.id: cable_finding_resolved, cable_findings[] now has 1 element.
Subagent immediately emits next report: status: NEEDS_APPROVAL, stage.id: await_cable_finding,
  approval_needed.cable_finding = second element (B1-AP).
Halts.

Orchestrator gets human response: "dismiss B1-AP is a known factory bypass, not a cable issue"
Orchestrator writes to cable-dismissals.jsonl (NOT to register), sends SendMessage.

Subagent emits report at stage.id: cable_finding_resolved, cable_findings[] now has 0 elements.
Subagent transitions to next pipeline stage (e.g. apply_obn_patches).
```
````

- [ ] **Step 4: Update §"What you NEVER do"**

Add to the existing list:

```markdown
- ❌ **Write to `cable-issues-register.md` or `.claude/logs/cable-dismissals.jsonl`.** Orchestrator-as-sole-writer. You emit `cable_findings[]` and let the orchestrator do the writes.
- ❌ **Re-emit a cable finding that was previously dismissed.** Always check `.claude/logs/cable-dismissals.jsonl` first. The hash dedup is mandatory.
```

- [ ] **Step 5: Verify**

Run: `Grep -n "cable_finding\|cable-dismissals\|Gate 6" .claude/agents/dosto-train-worker.md`

Expected: appears in (a) gates table, (b) new "cable-findings emission" sub-section, (c) Example 4, (d) "what you NEVER do" entries.

- [ ] **Step 6: Commit**

```bash
git add .claude/agents/dosto-train-worker.md
git commit -m "train-worker: emit cable_findings with dedup against dismissals log"
```

---

## Task 9: Add cable_findings to dosto-device-discovery skill output

**Files:**
- Modify: `.claude/skills/dosto-device-discovery/SKILL.md`

- [ ] **Step 1: Update §"--json mode (subagent consumption)" example**

Find the existing example JSON (currently lines 252–288) and replace `ap_missing` array entries with the new richer shape. Each missing AP element becomes (the existing keys plus the new ones):

```json
{
  "slot": "AP4",
  "config": "AP4-v1",
  "candidate_coaches": ["A", "C", "D"],
  "localised_to_coach": "D",
  "expected_switch": "D3",
  "expected_switch_ip": "10.179.10.193",
  "expected_port": "e1-2",
  "live_state": {"speed": "Auto", "rx_bytes": 0, "tx_bytes": 0, "lldp_peer": null},
  "stadler_instruction": "Install/connect AP at coach D position 4 to switch D3 port e1-2.",
  "cable_finding": {
    "finding_hash": "sha256:f3ab12...",
    "slot": "D4",
    "coach": "D",
    "expected_switch": "D3",
    "expected_switch_ip": "10.179.10.193",
    "expected_port": "e1-2",
    "evidence": {
      "link_state": "UP, 1 Gbps full-duplex",
      "poe_draw_watts": 0.0,
      "poe_expected_watts_min": 5.0,
      "lldp_last_seen": "never (since switch boot 14d ago)",
      "mac_table_on_port": [],
      "dhcp_leases_on_port": [],
      "rx_bytes_total": 312,
      "rx_bytes_window_seconds": 1209600,
      "adjacent_ports_health": "e0-0/e0-1 UP, RX CRC 0, carrier-false 0"
    },
    "cross_checks": {
      "other_devices_on_consist": "23/24 APs reachable",
      "port_config_matches_schema": true,
      "port_error_counters_clean": true,
      "factory_config_ap_ruled_out": true
    },
    "pattern_match": "Link UP but no AP seen — Stadler cable issue (per train-login-checklist.md row 3)",
    "suggested_register_row": {
      "trainset": "4736-104",
      "consist": "6-car",
      "switch": "D3",
      "ports": "e1-2 (AP D4 trunk)",
      "fault_type": "AP not connected",
      "what_we_see_vs_plan": "Link UP at 1G, zero PoE, no LLDP, no MAC learned. Plan: AP D4 visible.",
      "required_action": "Verify AP D4 physically present in coach D FIS-4; verify Cat6A patch from D3:e1-2 to AP D4 is seated both ends; confirm AP power LED.",
      "status": "OPEN"
    }
  }
}
```

- [ ] **Step 2: Add a "Cable-findings extraction" sub-section**

After the §"Step 9: Three-way prompt" section (currently around line 211), insert:

````markdown
### Step 10: Build cable_findings[] for the worker

For every `ap_missing[]` and `switches_missing[]` element produced by Steps 4–8, the skill MUST attach a `cable_finding` sub-object containing the evidence required by Gate 6 (per [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md) §"cable_findings"). Skip elements where the missing-device cause is **not** a cable issue:

- **Skip if the AP is in factory config** (config name matches `RT610LV-…-v1-FD`). That's a Nomad-side issue, fixed by `dosto-ap-config-update` Path B (LuCI HTTP). The factory bypass step handles it.
- **Skip if the engineer has dismissed this exact finding before.** The worker does the dismissal-log dedup, but the skill SHOULD also support a `--ignore-dismissals` flag for testing — default is to include all findings and let the worker dedupe.

For every NOT-skipped finding, gather:

1. **Link state** — from `show interface <port> details` "Line protocol" + speed/duplex.
2. **PoE draw** — from `show power inline interface <port>` (if PoE-capable port).
3. **LLDP last seen** — from `show counters protocol lldp interface <port>` (RX age) or `show lldp neighbour interface <port>` (current).
4. **MAC table on port** — from `show mac-address-table interface <port>`.
5. **DHCP leases on port** — grep `dhcp-lease-list` on CCU for any MAC matching that switch's per-port LLDP TX history (or simply pass empty list if none — common case for a missing AP).
6. **RX bytes total + window** — from two `show interface <port> details` snapshots OR from the switch's uptime (RX total since boot).
7. **Adjacent ports** — `show interface e0-0/e0-1 details` summary, error counters.
8. **Cross-checks** — count of other devices on consist (from your own discovery output), port config validation (compare to topology file), error counters (zero = clean).
9. **Pattern match** — string-match against the known patterns in `train-login-checklist.md` and CLAUDE.md "Common false alarms"/"Real red flags" sections. Pick the closest match.
10. **Suggested register row** — generate a 9-column row per the cable-issues-register.md format. The worker forwards this verbatim; the orchestrator either commits it or dismisses it.

The hash is computed per the canonical rule:

```python
import hashlib
finding_hash = "sha256:" + hashlib.sha256(
    f"{train_number}:{slot}:{expected_switch}:{expected_port}".encode()
).hexdigest()
```

If the skill cannot gather one of items 1–7 (e.g. PoE not supported on that port type), set the field to `null` and continue. The orchestrator's prompt formatter handles null gracefully.
````

- [ ] **Step 3: Update §"What this skill deliberately does NOT do"**

Find the existing list (currently around lines 296–302) and update one bullet:

```markdown
- ❌ Auto-edit fleet-status or cable register — emits the data, the orchestrator commits
```

Add a new bullet:

```markdown
- ❌ Decide whether a finding is a cable issue or factory-config or dismissed-prior — emits all candidate findings tagged with `cable_finding`, lets the worker dedup and the engineer decide via Gate 6
```

- [ ] **Step 4: Verify**

Run: `Grep -n "cable_finding\|finding_hash\|Step 10" .claude/skills/dosto-device-discovery/SKILL.md`

Expected: cable_finding schema in JSON example, Step 10 procedure, hashing rule, "what this skill does NOT do" updated.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/dosto-device-discovery/SKILL.md
git commit -m "device-discovery: emit cable_findings with evidence + suggested row"
```

---

## Task 10: Rewrite dosto-confluence-sync skill for two-tables-only

**Files:**
- Modify: `.claude/skills/dosto-confluence-sync/SKILL.md`

- [ ] **Step 1: Remove `--target {fleet|cables|both}` flag**

Find the §"Targets — `--target {fleet|cables|both}`" section (currently lines 30–58) and replace with:

````markdown
## What gets pushed (canonical)

The page renders **exactly two tables on one page**: fleet exec view + cable-issues register. Both are derived from local files:

| Source | Section title | Render |
|---|---|---|
| `fleet-status.md` | `# Fleet status` | Two sub-tables: 4736 series, 4734 series. 5 columns each: Fzg, Train#, CCU IP, Status, Next action. |
| `cable-issues-register.md` | `# Cable-issues register` | Single 9-column table — all OPEN rows first (sorted by `#`), then RESOLVED, then WONTFIX (struck-through). |

Sections explicitly **NOT** rendered to the page (per [confluence-sync.md](../../contracts/confluence-sync.md) Amendment 1, dropped 2026-05-10):

- Fzg-ID convention block
- Per-train notes section
- "How to update" section

The skill does NOT support `--target` selection — there is one page, one body, both tables always. Earlier `--target {fleet|cables|both}` semantics removed.
````

- [ ] **Step 2: Update inputs list**

Find the current §"Inputs" (lines 61–68) and remove `--target` and `--cloud-id` redundancy with `--target`. Keep:

```markdown
## Inputs

- `--page-id <id>` — overrides the canonical page ID. Use only for testing against a draft/sandbox page.
- `--cloud-id <id>` — defaults to `nomad-digital.atlassian.net`.
- `--source-fleet <path>` — defaults to `fleet-status.md`. Override only for testing.
- `--source-cables <path>` — defaults to `cable-issues-register.md`. Override only for testing.
- `--force` — only valid with `--push`. Skip drift detection.
- `--allow-stale` — skip the 24h-stale-source guard.
- `--json` — machine-readable output.
- `--dry-run` — synonym for `--diff`.
```

- [ ] **Step 3: Replace §"Page layout (canonical)"**

Find the current §"Page layout (canonical)" (currently lines 113–122) and replace with:

````markdown
#### Page layout (canonical)

The Confluence page body has these sections in this order:

1. **Banner** — auto-sync timestamp, version, sync source. Also drift-detection signal.
2. **Status legend** — 5-row table mapping the status emoji to status names.
3. **`# Fleet status`** — 4736 series exec table, then 4734 series exec table. 5 columns each.
4. **`# Cable-issues register`** — single 9-column table.

That's the entire page. No other sections. Engineers wanting full detail (per-train notes, history, OBN patch counts, etc.) read the local `fleet-status.md` directly.
````

- [ ] **Step 4: Add a §"Cable-register render" sub-section after the existing exec-table render**

After the §"Exec table shape (5 columns)" block (currently around lines 155–177), insert:

````markdown
#### Cable-register render

Parse `cable-issues-register.md`. Extract the "Open issues" table rows AND the "Resolved issues" rows (if any) into a single in-memory list. Sort:

1. All `OPEN` rows first, ordered by `#` ascending.
2. All `RESOLVED` rows next, ordered by `#`.
3. All `WONTFIX` rows last, ordered by `#`.

Render as a single 9-column markdown table with `Status` cell prefixed by emoji:

| Status text | Emoji prefix | Row formatting |
|---|---|---|
| `OPEN` | 🔴 | normal |
| `OPEN` with `(auto-detected — verify on-site)` suffix in "What we see" | 🟡 | normal |
| `RESOLVED` | ✅ | normal |
| `WONTFIX` | ⬜ | entire row wrapped in `~~strikethrough~~` |

If the register has zero rows, render `*(no cabling issues currently logged)*` instead of an empty table.

Cell content is verbatim from the local file. Do not truncate, reformat, or edit. Long cells wrap in Confluence — that's fine.

Rows whose Status field is none of `OPEN | RESOLVED | WONTFIX` (typo) are surfaced as a warning to the engineer (`WARN: register row #N has unrecognised Status: <value>, excluded from push`) and excluded from the push body.
````

- [ ] **Step 5: Update §"Stale-source guard" to cover both files**

Find the current "Stale-source guard" sub-step (currently around line 222) and update to:

```markdown
2. **Stale-source guard (unless `--allow-stale`):** stat both `fleet-status.md` AND `cable-issues-register.md`. If `now - max(mtime_fleet, mtime_cables) > 24h`, halt and warn — same prompt as before, but mention both files. The 24h threshold is the rough lower bound of "definitely stale" — at least one of the two files should be touched per fleet day.
```

- [ ] **Step 6: Verify**

Run: `Grep -n "target\|cable-issues\|two tables" .claude/skills/dosto-confluence-sync/SKILL.md`

Expected: zero remaining references to `--target cables` / `--target fleet` / `--target both`. The cable-register render section exists. "Two tables" appears in the canonical layout.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/dosto-confluence-sync/SKILL.md
git commit -m "confluence-sync: render one page with two tables, drop --target flag"
```

---

## Task 11: Mark dosto-auto-scan as DISABLED in skill description

**Files:**
- Modify: `.claude/skills/dosto-auto-scan/SKILL.md`

- [ ] **Step 1: Prefix the skill description in YAML frontmatter**

Find the current `description:` field (line 3) and prefix the value with the disabled notice. The new line reads:

```yaml
description: '**DISABLED — Phase 2 deferred (2026-05-10).** Cable register is now orchestrator-owned per autonomy-boundary.md Gate 6 (cable_finding). DO NOT INVOKE. This skill description is preserved for future Phase 2 re-enablement; current invocation is a contract violation. Original description follows: Unattended fleet diagnostic scanner. Use when running the scheduled fleet probe (default 30-min cadence via Windows Task Scheduler), when an engineer wants a one-off `--fzg` Tier-2 diagnostic, or when validating the auto-scanner against a real online train. Tier-1 reachability probe (cheap, all trains, every cycle) plus Tier-2 full diagnostic (per-train, fires on transitions or 24h forced rescan) across all CCUs in 10.179.0.0/16. Read-only against CCUs. Writes only to allowlisted columns of fleet-status.md, appends Status:auto-detected rows to cable-issues-register.md (never auto-promotes), and owns auto-scan-state.json. Strict mutex with /dosto-orchestrate. See .claude/contracts/auto-scanner-boundary.md.'
```

- [ ] **Step 2: Add a DISABLED block at the top of the skill body**

After the `---` closing the YAML frontmatter (around line 5), and before any existing body content, insert:

```markdown
> **⚠️ DISABLED — Phase 2 deferred (2026-05-10).**
> This skill is not currently invoked by any agent or scheduled task. Cable-issues register rows are written exclusively by the orchestrator via the [Gate 6 `cable_finding`](../../contracts/autonomy-boundary.md) approval flow, fed by `cable_findings[]` in subagent reports.
>
> **Do not invoke this skill.** If you find a code path that invokes it, that's a bug.
>
> The procedure below is preserved verbatim for the future Phase 2 re-enablement (passive 30-min fleet scan). When re-enabling: reconcile with autonomy-boundary.md Gate 6 first — pick one writer for `cable-issues-register.md`, or define explicit lane separation. Two writers is a contract violation.
```

- [ ] **Step 3: Verify**

Run: `Read .claude/skills/dosto-auto-scan/SKILL.md` (first 30 lines). Confirm the DISABLED block appears at the top of the body and the description is prefixed.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/dosto-auto-scan/SKILL.md
git commit -m "auto-scan: mark DISABLED — Phase 2 deferred, orchestrator owns cable register"
```

---

## Task 12: Update CLAUDE.md to reflect new architecture

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the orchestration architecture diagram**

Find the diagram block (currently around lines 26–55, the `[dosto-orchestrator agent]` section). After the line that reads:

```
       └─► writes fleet-status.md (orchestrator-as-sole-writer)
```

Add immediately above it:

```
       ├─► writes cable-issues-register.md (orchestrator-as-sole-writer, on Gate 6 confirmed/auto-detected)
       ├─► writes .claude/logs/cable-dismissals.jsonl (on Gate 6 dismiss)
```

So the orchestrator's outputs become a 4-bullet list (Confluence sync, fleet-status writer, cable register writer, dismissal log writer).

- [ ] **Step 2: Update the contracts table**

Find the "four contracts" table (currently around lines 71–77). Update the `autonomy-boundary.md` row to mention 6 gates:

```markdown
| [`.claude/contracts/autonomy-boundary.md`](.claude/contracts/autonomy-boundary.md) | Six approval gates and what subagents may do without asking |
```

Update the `confluence-sync.md` row:

```markdown
| [`.claude/contracts/confluence-sync.md`](.claude/contracts/confluence-sync.md) | One-way local → Confluence push policy (one page, two tables: fleet + cables) + drift detection |
```

- [ ] **Step 3: Add a note about the disabled auto-scanner**

Find the §"Folder layout" → `.claude/skills/` block listing the 13 project-local skills (currently around line 461). Update the `dosto-auto-scan` mention (which currently doesn't exist in that list explicitly, but the skill exists). Add a note to the existing list:

```markdown
- `dosto-auto-scan` — **DISABLED — Phase 2 deferred (2026-05-10).** Was the auto-scanner; now superseded by orchestrator-owned Gate 6 cable-finding flow. Do not invoke.
```

If `dosto-auto-scan` is already in the list, change its line to the above format instead of adding a new one. Run `Grep -n "dosto-auto-scan" CLAUDE.md` first to check.

- [ ] **Step 4: Verify**

Run: `Grep -n "Gate 6\|cable_finding\|six approval\|cable-issues-register" CLAUDE.md`

Expected: appears in (a) architecture diagram, (b) contracts table, (c) skill list note.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "CLAUDE.md: orchestrator owns cable register; auto-scanner disabled"
```

---

## Task 13: Smoke-test the new contracts (no CCU required)

**Files:**
- Read: all modified files
- Verify: schema consistency, link integrity

This is verification-before-completion (Principle 4 — Goal-Driven Execution). Don't claim done without evidence.

- [ ] **Step 1: Cross-reference Gate 6 mentions across all contracts**

Run: `Grep -rn "Gate 6\|cable_finding\|cable_findings" .claude/`

Expected: appears in every contract file (autonomy-boundary, subagent-report, approval-gates, confluence-sync), both agent definitions (orchestrator, train-worker), one skill (device-discovery), and the CLAUDE.md. Count should be at least 30 hits across these files. Zero hits in any of them = the edit was missed.

- [ ] **Step 2: Verify the canonical hashing rule appears identically in all three places**

The hashing rule `sha256(f"{train_number}:{slot}:{expected_switch}:{expected_port}".encode()).hexdigest()` must appear in:
- `.claude/contracts/subagent-report.md`
- `.claude/agents/dosto-train-worker.md`
- `.claude/skills/dosto-device-discovery/SKILL.md`

Run: `Grep -n "sha256.*train_number.*slot.*expected_switch.*expected_port" .claude/`

Expected: 3 hits, identical strings. If the strings differ between files, that's a bug — fix to match.

- [ ] **Step 3: Confirm no broken contract links**

For each contract reference like `[autonomy-boundary.md](autonomy-boundary.md)`, verify the link target exists.

Run: `Grep -rn "\[.*\]\(.*\.md\)" .claude/contracts/ .claude/agents/ | grep -v "http"`

Eyeball the output for typos in filenames. The directory has a small fixed set of files — any reference to `.md` files outside that set is a broken link.

- [ ] **Step 4: Confirm the three "open questions" from Task 1 are resolved**

Re-read the open questions section of this plan. Each must have an explicit answer documented either inline in this file or in the conversation. If any is still unresolved, halt and resolve before claiming done.

- [ ] **Step 5: Manual dry-run of the gate prompt format**

Compose the exact prompt the orchestrator would emit for a synthetic finding (Fzg 132, slot D4, switch D3 port e1-2). Use a real evidence block from the existing register row #5 (already present in `cable-issues-register.md`). Compare the prompt format against the §"Three-way cable gate" §"Prompt format" in approval-gates.md. The output should be byte-for-byte composable — every placeholder in the format has a source field.

If any placeholder doesn't have a source, the schema is incomplete — go back and fix the schema in `subagent-report.md` Task 3.

- [ ] **Step 6: Manual dry-run of a register-row append**

Take the existing register's last row (#5) and the synthetic finding from Step 5. Compose the new row #6 the orchestrator would append. The new row must:
- Use `#` = 6 (one more than max existing).
- Use the existing 9-column pipe format.
- Have `OPEN` in the Status column.
- Have all column separators (`|`) aligned with adjacent rows in count (9 cells per row).

If the format breaks the existing table, fix the orchestrator agent's "Append procedure" in Task 7.

- [ ] **Step 7: Commit verification artefacts (if any) and the plan completion marker**

If you created a sample `proposed-row.md` or `proposed-prompt.md` for steps 5 and 6, decide whether to keep them. If they're worth keeping as test fixtures, put them under `.claude/contracts/examples/` and commit. Otherwise discard.

```bash
git status   # should show only intentional changes
git log --oneline -15   # should show 12 commits, one per task 2-12
```

- [ ] **Step 8: Final commit (only if there are accumulated changes)**

```bash
git add -A
git commit -m "verification: contracts cross-reference and dry-run pass"
```

If there are no changes, no commit. The plan is complete.

---

## Self-review (per Principle 1 forcing function)

After writing this plan, I checked:

**Spec coverage** — every requirement from the conversation maps to a task:
- Orchestrator becomes sole writer of cable-issues-register: Tasks 2 (autonomy-boundary), 7 (orchestrator agent), 13 (verification).
- Train-worker emits `cable_findings[]`: Tasks 3 (schema), 8 (worker), 9 (skill).
- Per-finding approval gate (3-way `confirmed`/`auto-detected`/`dismiss <reason>`): Tasks 2, 3, 4, 7.
- Confluence consolidates to two tables on one page: Tasks 6 (contract), 10 (skill), 12 (CLAUDE.md).
- Auto-scanner shelved: Tasks 5 (contract), 11 (skill), 12 (CLAUDE.md).

**Placeholder scan** — searched for "TBD", "TODO", "implement later", "fill in" — zero hits in this plan. Every step has either exact text to add or exact verification command.

**Type consistency** — the `cable_findings[]` element schema appears in `subagent-report.md` (Task 3), `dosto-train-worker.md` (Task 8), `dosto-device-discovery/SKILL.md` (Task 9). All three reference the same 10 keys (`finding_hash`, `slot`, `coach`, `expected_switch`, `expected_switch_ip`, `expected_port`, `evidence`, `cross_checks`, `pattern_match`, `suggested_register_row`). The hashing rule is canonical and identical in all three places. Verified in Task 13 Step 2.

**Karpathy principles applied throughout:**
- **Think before coding (Principle 1):** Plan starts with three open questions for the engineer to resolve before any task. Task 13 Step 4 forces re-confirmation. Each ambiguous decision is surfaced explicitly with the alternative.
- **Simplicity first (Principle 2):** No new file format. Reuses existing register's `OPEN`/`RESOLVED`/`WONTFIX` vocabulary. Drops `--target` flag from sync skill. Auto-scanner shelved instead of refactored. Contracts grow by one gate, not by a new framework.
- **Surgical changes (Principle 3):** Every task lists exact lines and exact text. No drive-by improvements. Existing register rows untouched. Auto-scanner not deleted (description prefixed only).
- **Goal-driven execution (Principle 4):** Every task ends with a `Verify` step using `Grep` or `Read`. Task 13 is end-to-end smoke-test before claiming done. Success criteria for the whole plan: all 6 verifications in Task 13 pass.
