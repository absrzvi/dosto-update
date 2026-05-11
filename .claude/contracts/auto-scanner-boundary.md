# Auto-Scanner Boundary

**Status:** v1, drafted 2026-05-09. Companion to [autonomy-boundary.md](autonomy-boundary.md) and [confluence-sync.md](confluence-sync.md).

What the scheduled auto-scanner (Layer 1 + Layer 2 of the unattended-discovery system) may do without human supervision, and what it must never touch. The scanner runs on a fixed schedule (default: every 30 min via Windows Task Scheduler on the engineer's laptop) and is **read-only against CCUs** — it never invokes a destructive skill or hits an approval gate.

## TL;DR

> **Diagnostic-only across the fleet, with strict file-write boundaries. Never auto-promotes draft signals to confirmed. Engineer is the only writer of `Status: confirmed` rows.**

## Where this fits in the architecture

```
Windows Task Scheduler (every 30 min)
       │
       ▼
[Layer 1 — Discovery]  cheap probe of 10.179.x.x, build candidate list
       │
       ▼
[Layer 2 — Diagnostic]  for each reachable train: device-discovery, lldp-topology-check, l2-health
       │
       ├─► writes to fleet-status.md          (allowlisted columns only)
       ├─► appends to cable-issues-register.md (Status: auto-detected only)
       └─► writes auto-scan-state.json        (full ownership)

       ↓  engineer reviews periodically, promotes auto-detected → confirmed manually

[/dosto-confluence-sync --push]  reflects current state to Confluence (existing path)
       │
       ▼
[Confluence page 5410684933]  PM reads, escalates confirmed rows to Stadler
```

The auto-scanner is **a third writer** alongside the engineer (existing) and the orchestrator (existing). To stay non-conflicting with the orchestrator-as-sole-writer pattern from [autonomy-boundary.md](autonomy-boundary.md), the auto-scanner has a strict column allowlist on `fleet-status.md` and an append-only / status-gated write rule on `cable-issues-register.md`.

## What the auto-scanner does without asking

### Read-only network operations

- ICMP ping sweep of management ranges (`10.179.0.0/16`)
- TCP/22 reachability probe to candidate CCUs
- SSH to reachable CCUs using the project key (`openssh`)
- All `--check` / `--json` modes of read-only project skills:
  - `dosto-state-inventory` (12-fact CCU inventory, ~5s SSH heredoc)
  - `dosto-device-discovery` (count switches/APs vs expected, localise missing devices)
  - `dosto-l2-health` (RX CRC, carrier-false, link-down counters on Stadler-facing trunks)
  - `scripts/lldp_topology_check.py` (inter-coach trunk peer verification)

### Local file writes — `fleet-status.md`

**Allowlist of columns the auto-scanner may write:**

| Column (NEW) | Meaning | Write rule |
|---|---|---|
| `Last reachable` | UTC timestamp of last successful TCP/22 probe | Update on every successful probe |
| `Last auto-scan` | UTC timestamp of last full diagnostic pass | Update on every full Layer 2 run |
| `Auto-detected issues` | Integer count of `Status: auto-detected` rows in cable register that reference this Fzg | Recompute and update on every cable-register write |

**Forbidden — auto-scanner must NEVER touch these existing columns:**

- `OBN patches`, `Switches v8`, `APs`, `vlan7 ok`, `Stadler cabling`, `FW reach` (orchestrator-owned per [autonomy-boundary.md](autonomy-boundary.md))
- `Health check`, `Customer report` (engineer-owned)
- `Status`, `Next action`, `Last touched` (engineer-owned, optionally orchestrator)
- The per-train notes section beneath the fleet table (engineer-owned)

If the auto-scanner sees that one of its own columns is missing from the table header, it adds the column header rather than guessing — but it does **not** modify the existing 14 column headers.

**Write semantics:** atomic file replacement (write to `.tmp`, rename). Not a 3-way merge. If the file's mtime advanced since the auto-scanner read it, the scanner re-reads, re-applies its allowlisted updates, and tries again. After 3 conflicts in a row, it logs to `auto-scan-state.json` and skips that cycle's `fleet-status.md` write — it does not block.

### Local file writes — `cable-issues-register.md`

**Append-only on `Status: auto-detected` rows:**

The auto-scanner may **append a new row** if and only if:

1. The signal it detected has a stable hash (see "Signal hashing" below)
2. No existing row in the register matches that hash, regardless of the existing row's status
3. The signal has fired on at least 3 consecutive scans (debounce — prevents transient cellular outages from spamming the register)

The appended row is always `Status: auto-detected` with empty Stadler-instructions and empty engineer-notes blocks.

**Forbidden:**

- ❌ Writing or modifying any row where `Status: confirmed`
- ❌ Modifying any row where `Status: auto-detected` *content* (the signal source, localisation, first-seen) — only the `Last seen` timestamp may be bumped
- ❌ Deleting any row, ever
- ❌ Reordering rows
- ❌ Writing the Stadler-instructions block (engineer responsibility, period)
- ❌ Promoting `Status: auto-detected` → `Status: confirmed` (engineer responsibility, period)

If the auto-scanner detects a signal that already has a confirmed row matching its hash, it logs `already_confirmed: row #N` to `auto-scan-state.json` and stays silent. No new row, no `Last seen` bump.

### Local file writes — `.claude/state/confluence-pages.json` (NEW, scanner-bootstrapped, sync-skill-readonly-after)

The scanner's `--bootstrap-confluence-cables` mode creates the cable-register Confluence page on first run and writes the returned page ID here. After bootstrap, only the scanner ever rewrites the file (e.g. on `--bootstrap-confluence-cables --recreate` if the page is deleted). The `dosto-confluence-sync` skill reads this file to know which page to push to for `--target cables`.

```json
{
  "fleet_status_page_id": "5410684933",
  "cable_register_page_id": "<assigned on first bootstrap>",
  "bootstrapped_utc": "<iso8601>"
}
```

The fleet-status page ID is preserved for backwards compatibility with the existing `dosto-confluence-sync` skill which currently reads it from CLAUDE.md / contract constants. Both sources should match.

### Local file writes — `auto-scan-state.json` (NEW, full ownership)

This file is exclusively owned by the auto-scanner. Schema (illustrative — finalise during build):

```json
{
  "schema_version": 1,
  "last_full_scan_utc": "2026-05-09T14:30:00Z",
  "trains": {
    "132": {
      "ccu_ip": "10.179.10.1",
      "last_reachable_utc": "2026-05-09T14:30:00Z",
      "last_state_inventory_utc": "2026-05-09T14:30:05Z",
      "last_full_diagnostic_utc": "2026-05-09T14:30:45Z",
      "consecutive_unreachable_scans": 0,
      "active_signals": [
        {
          "hash": "fzg=132/missing_ap=.240/lldp=D3.e1-4",
          "first_seen_utc": "2026-05-08T09:00:00Z",
          "last_seen_utc": "2026-05-09T14:30:45Z",
          "scan_count": 14,
          "register_row": 5,
          "register_status": "confirmed"
        }
      ]
    }
  },
  "scan_history": [
    {"utc": "2026-05-09T14:30:00Z", "reachable": 7, "signals_new": 0, "signals_active": 12, "duration_seconds": 287}
  ]
}
```

The engineer should not edit this file by hand — it is a machine-managed log.

### What the auto-scanner does NOT do

- ❌ Run any destructive skill (`dosto-obn-patches --apply` or `--persist`, `dosto-vlan7-config --apply`, `dosto-fzg-id-check --apply`, anything `--execute`)
- ❌ Run any `obn update c` or `obn update f` command
- ❌ SSH into switches or APs (only the CCU; switches/APs reached transitively via `obn discover` data only)
- ❌ Trigger an approval gate (the auto-scanner has no human in the loop — it just doesn't reach states that need approval)
- ❌ Spawn a subagent or invoke `dosto-orchestrate` / `dosto-commission-train`
- ❌ Push to Confluence directly (use the existing `/dosto-confluence-sync` skill, engineer-triggered)
- ❌ Promote `auto-detected` → `confirmed` rows under any circumstance
- ❌ Delete or modify confirmed rows in `cable-issues-register.md`
- ❌ Touch `.claude/contracts/`, `.claude/agents/`, or `.claude/skills/` — the auto-scanner does not modify its own rules
- ❌ Send notifications (Slack/email/toast) in v1 — passive review model, engineer reads the register at session start

## Signal hashing — what counts as "the same problem"

The auto-scanner must dedupe so a persistent fault doesn't spawn a new register row every 30 min. Each signal computes a stable hash from its semantic identity, not from timestamps or counter values:

| Signal source | Hash inputs |
|---|---|
| Missing device (from `dosto-device-discovery`) | `fzg`, `device_role` (e.g. `AP_D4`, `SW_C3`), `last_lldp_neighbour_port` (e.g. `D3.e1-4`) |
| LLDP topology mismatch (from `lldp_topology_check.py`) | `fzg`, `local_switch_ip`, `local_port`, `expected_peer`, `actual_peer` |
| Stadler-trunk CRC errors (from `dosto-l2-health`) | `fzg`, `switch_ip`, `port`, `error_kind` (e.g. `rx_crc`, `carrier_false`) |
| Stadler-trunk speed degradation | `fzg`, `switch_ip`, `port`, `expected_speed`, `actual_speed` |

Two scans 30 min apart that produce the same hash mean "still the same problem". The auto-scanner bumps `Last seen`. Two scans that produce different hashes mean "different problem" — they get separate register rows.

## Confidence threshold — what gets a register row vs a state-only log

Not every diagnostic anomaly justifies a Stadler-bound register row. The auto-scanner classifies signals into three tiers:

| Tier | Examples | Action |
|---|---|---|
| **High confidence** | Missing device localised via LLDP last-seen; LLDP topology mismatch on inter-coach trunk; sustained RX CRC > 100 on Stadler-facing trunk | After 3 consecutive scans confirming the signal: append `Status: auto-detected` row to `cable-issues-register.md` |
| **Medium confidence** | RX CRC errors 1–100 on a Stadler-facing trunk; `carrier_false` count climbing slowly | Log to `auto-scan-state.json` `active_signals[]` with `register_row: null`. Engineer can see in the JSON; not auto-drafted to register. Promote to high-confidence and draft a row only if the count crosses threshold. |
| **Low confidence** | Single-scan anomaly; end-of-train e0-1 down (expected per CLAUDE.md "common false alarms"); train-wide silence (probably powered off) | Logged in scan history but not tracked as a signal. Discarded after that scan. |

The thresholds (3-scan debounce, CRC>100) are defaults — they live in `auto-scan-state.json` schema as `thresholds: {...}` and can be tuned without rebuilding the scanner.

## Confluence reflection — two-section rendering

The auto-scanner does not push to Confluence directly (per [confluence-sync.md](confluence-sync.md), only the orchestrator and engineer-triggered `/dosto-confluence-sync` push). But it owns the *content shape* that the sync skill must render.

The cable-issues Confluence page (or section) must render in **two ordered blocks**:

1. **Confirmed cabling faults — PM to escalate to Stadler.** All rows where `Status: confirmed`. Ordered Stadler-actionable instructions are the actionable artefact. This is the section the PM links in their Stadler email.

2. **Auto-detected anomalies — engineer review pending.** All rows where `Status: auto-detected`. Shows signal source, first-seen, scan count, suggested category. This is internal-visibility only — Stadler does not see it.

If `/dosto-confluence-sync` is extended to push the cable register, this two-section split is the contract. Mixing the rows breaks the PM's escalation workflow.

## Schedule and execution model

- **Trigger:** Windows Task Scheduler on the engineer's laptop, fixed cadence (default 30 min).
- **Headless invocation:** `claude -p "/dosto-auto-scan"` (skill to be built).
- **Execution scope:** single laptop — no shared infrastructure. If the laptop is asleep / off / off-VPN, scans don't run. Confluence stays at last-pushed state.
- **Stale-source protection:** if `auto-scan-state.json.last_full_scan_utc` is > 4 hours old, the next `/dosto-confluence-sync --push` warns the engineer ("auto-scan data is stale, freshness > 4h") but does not refuse the push (engineer override).
- **Mutual exclusion with the orchestrator:** if a `/dosto-orchestrate` session is active (detect via lockfile or process check), the auto-scanner skips that cycle entirely. Orchestrator changes state too fast for the scanner's read-modify-write loop to be safe alongside it.

## What is NEVER autonomous, even with future relaxation

- Promoting `Status: auto-detected` → `Status: confirmed` — engineer-only, forever
- Writing or editing the Stadler-instructions block on any register row — engineer-only, forever
- Modifying the orchestrator-owned columns of `fleet-status.md` — orchestrator-only, forever
- Sending anything to Stadler (email, ticket, escalation) — PM responsibility, outside this entire system

## Why this boundary, not tighter or looser

**Tighter (no register writes at all, only `auto-scan-state.json`) loses the PM workflow.** The PM reads `cable-issues-register.md` (via Confluence) to know what to escalate. If auto-detected signals never land there, the PM can't see them and the engineer has to manually transcribe — which defeats the point of a 30-min scanner.

**Looser (auto-promote to `confirmed` on high-confidence signals) risks Stadler reputation.** One false-positive register row sent to Stadler undermines the credibility of the whole register. Even a 99% confidence signal should sit in `auto-detected` until a human acks it. Stadler is an external party; the cost of one bad escalation is much higher than the cost of a 5-minute engineer review per cycle.

**Specifically: the 3-scan debounce is deliberate.** A single scan with a missing device could be a transient cellular outage, a temporarily-rebooting AP, or the engineer mid-test. Three consecutive 30-min-apart scans is ~90 min of persistent fault — well beyond any legitimate transient.

## Validating compliance

The auto-scanner skill prompt should explicitly enumerate the boundaries above and require:

- Every `fleet-status.md` write is preceded by reading the file, validating the column allowlist, and writing only those cells.
- Every `cable-issues-register.md` write is preceded by reading the file, computing existing-row hashes, and verifying the new row's hash is unique AND the new row's `Status:` field is `auto-detected`.
- An auto-scanner SSH command log captured (similar to the orchestrator's), grepped for forbidden patterns: `obn update`, `safe_reboot`, `nd-systemupdate.sh`, `--apply`, `--persist`, `--execute`. Any match is a contract violation logged to `auto-scan-errors.jsonl`.

A future `scripts/validate_dosto_workspace.py` extension should add a check that `auto-scan-state.json` is parseable and that no row in `cable-issues-register.md` was written by the scanner with `Status: confirmed` (cross-check against `auto-scan-state.json.active_signals[].register_row` matching only `register_status: auto-detected` writes).
