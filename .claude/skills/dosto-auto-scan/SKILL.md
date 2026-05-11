---
name: dosto-auto-scan
description: Unattended fleet diagnostic scanner. Use when running the scheduled fleet probe (default 30-min cadence via Windows Task Scheduler), when an engineer wants a one-off `--fzg` Tier-2 diagnostic, or when validating the auto-scanner against a real online train. Tier-1 reachability probe (cheap, all trains, every cycle) plus Tier-2 full diagnostic (per-train, fires on transitions or 24h forced rescan) across all CCUs in 10.179.0.0/16. Read-only against CCUs. Writes only to allowlisted columns of fleet-status.md, appends Status:auto-detected rows to cable-issues-register.md (never auto-promotes), and owns auto-scan-state.json. Strict mutex with /dosto-orchestrate. See .claude/contracts/auto-scanner-boundary.md.
---

# DOSTO Auto-Scan

Unattended Layer-1 + Layer-2 fleet scanner. Runs on a fixed schedule (default 30 min) and produces three outputs: updated reachability columns in `fleet-status.md`, draft `Status: auto-detected` rows in `cable-issues-register.md` (high-confidence cabling signals only), and full state in `auto-scan-state.json`.

The contract is [.claude/contracts/auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md). Read that first for the rationale and the strict write boundaries; this SKILL.md is the runbook.

## Tier model

The scanner runs in two tiers per cycle. Tier 1 is cheap (~10s per CCU candidate). Tier 2 is heavier (~5 min per train) and only fires when there's something worth looking at.

| Tier | Scope | Cost | Triggers |
|---|---|---|---|
| 1 — Reachability + state inventory | All known CCU IPs from `fleet-status.md` + `10.179.0.0/16` sweep for new CCUs | ~10s per CCU (TCP/22 probe + `dosto-state-inventory --json` heredoc) | Every cycle, unconditionally |
| 2 — Full diagnostic | Per-train, only on Tier-2-trigger | ~5 min (device-discovery + lldp-topology-check + l2-health) | See below |

**Tier 2 triggers** (any one fires Tier 2 for that train this cycle):

| Trigger | Why |
|---|---|
| `transition_online` — train was unreachable in last cycle, reachable now | Capture fresh state immediately after train comes online |
| `transition_offline` — train was reachable, unreachable now | Layer 2 is a no-op (no SSH possible); state-only update of `consecutive_unreachable_scans` in `auto-scan-state.json` |
| `state_drift` — `dosto-state-inventory` aggregate verdict is `unexpected_drift` since last scan (TFTP helper, btrfs subvol, vlan7 IP, train_id template, NDSU rename) | Drift = something happened, full scan justified |
| `forced_rescan_24h` — `last_full_diagnostic_utc` for this Fzg is > 24h old | Catches slow-developing CRC trends on otherwise-stable trains |
| `engineer_force` — `--force-tier-2 <fzg>` flag passed | Manual override |

Steady-state on a fully-stable fleet: Tier 1 every cycle (cheap), Tier 2 once per train per day (24h trigger). On a busy commissioning day: Tier 2 fires per-transition (every train that just came online or drifted).

## Modes

| Mode | What it does | When |
|---|---|---|
| `--scan` (default) | Run one full Tier-1 + selective Tier-2 cycle. Update files per allowlist. Default invocation from Task Scheduler. | Scheduled cycles |
| `--dry-run` | Run scan but write outputs to `*.auto-scan.preview` files instead of the real ones. Print a diff. No `auto-scan-state.json` mutation. | Validating before deploying the schedule |
| `--force-tier-2 <fzg>` | Force Tier-2 for a specific Fzg this cycle even if no trigger fires. Comma-separated for multiple. | Manual investigation |
| `--status` | Read-only: print summary of last cycle (reachable count, active signals, last `transition_*` events). No probes, no writes. | Engineer eyeballing scanner state |
| `--bootstrap-confluence-cables` | One-time: create the cable-register Confluence page via `createConfluencePage`, store the returned page ID in `.claude/state/confluence-pages.json`, exit. | First-time setup before any cable-register sync push |

All modes support `--json` for machine output (default for headless scheduled runs) and `--human` for interactive use.

## Inputs

- `--scan-range <cidr>` — defaults to `10.179.0.0/16`. The management network range to ping-sweep for new CCUs not yet in `fleet-status.md`.
- `--cycle-id <iso8601>` — defaults to `now`. Tagged into `auto-scan-state.json.scan_history[]`.
- `--max-tier-2-trains <N>` — defaults to `8`. Hard cap on how many Tier-2 runs fire in one cycle (overrun protection — see "Cycle budget" below).
- `--state-file <path>` — defaults to `auto-scan-state.json` at workspace root.
- `--errors-log <path>` — defaults to `.claude/logs/auto-scan-errors.jsonl`.
- `--lockfile <path>` — defaults to `.claude/state/auto-scan.lock`. Prevents concurrent scanner runs.

## Mutex with `/dosto-orchestrate`

Per [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md), the scanner must skip its cycle if the orchestrator is active.

**Detection:** read `.claude/state/orchestrator.lock` if present. If the file exists and its mtime is < 60 min old, the orchestrator is considered active.

**Action on detected orchestrator:**
1. Log `cycle_skipped: orchestrator_active` to `auto-scan-errors.jsonl`
2. Exit 0 (not an error — this is intentional yield)
3. Next scheduled cycle re-checks; resumes when the orchestrator lock is gone or stale

The scanner takes its own lock (`auto-scan.lock`, mtime-fresh < cycle-cadence × 2) before doing any work. This prevents two scheduled invocations overlapping if a cycle takes longer than the cadence.

## Cycle budget

Tier-2 has an unbounded cost per train (~5 min) × N candidate trains. To prevent the scanner from overrunning its 30-min cadence, the budget is capped at `--max-tier-2-trains` (default 8). Selection priority when more candidates exist than the cap:

1. `transition_online` — always run (highest value moment)
2. `state_drift` — always run (something happened)
3. `engineer_force` — always run
4. `forced_rescan_24h` — fill remaining budget oldest-first

Trains pushed past the budget are deferred to the next cycle. Logged in `scan_history[].deferred_tier_2[]` so they're picked up promptly. A persistent backlog (same Fzg deferred 3+ cycles in a row) is logged as a warning to `auto-scan-errors.jsonl`.

## File writes — strict allowlist enforcement

### `fleet-status.md`

Three columns the scanner owns. Per [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md) the existing 14 columns are off-limits.

**New columns appended after `Last touched`:**

| Column | Format | Source |
|---|---|---|
| `Last reachable` | `YYYY-MM-DD HH:MM` UTC, or `—` if never | Tier 1 successful TCP/22 probe |
| `Last auto-scan` | `YYYY-MM-DD HH:MM` UTC of last full Tier-2, or `—` | Tier 2 completion |
| `Auto-detected issues` | Integer count of `Status: auto-detected` rows in cable-register that reference this Fzg, or `—` | Recomputed from cable-register on every write |

**Write algorithm:**

1. Read `fleet-status.md` — capture mtime as `read_mtime`
2. Parse fleet table; locate header row; verify the three auto-scanner columns exist; if missing, append column headers (single-cell write, no other content disturbed)
3. For each Fzg row in scan results: locate the row by Fzg ID, update only the three allowlisted cells
4. Write to `fleet-status.md.tmp`, fsync, rename atomically
5. If during step 4 the file's mtime ≠ `read_mtime`, retry from step 1 (max 3 attempts)
6. After 3 failed retries, log `fleet_status_write_conflict` to `auto-scan-errors.jsonl` and skip the write this cycle (state-only)

**Forbidden cells (validated before every write):** if the diff between current and computed file content shows any change to a non-allowlisted column or to the per-train notes section, abort the write entirely and log `fleet_status_allowlist_violation` with the diff. This is a contract violation — should never happen, but the validation catches bugs early.

### `cable-issues-register.md`

Append-only on `Status: auto-detected` rows. Per the contract, the scanner never edits confirmed rows and never promotes auto-detected → confirmed.

**Write algorithm per detected high-confidence signal:**

1. Compute signal hash per the table in [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md)
2. Read `cable-issues-register.md`; parse all existing rows; build hash → row map
3. If the hash already maps to an existing row:
   - If `Status: confirmed` → log `already_confirmed` to `auto-scan-state.json`, do not touch register
   - If `Status: auto-detected` → bump only the `Last seen` timestamp on that row, write atomically as for fleet-status
4. If the hash is new AND the signal has fired ≥ 3 consecutive scans (debounce, tracked in `auto-scan-state.json.active_signals[].scan_count`):
   - Compose new row in the standard format (see "Row template" below)
   - Append at end of register, with a section break (`---`) above
   - Write atomically (read-modify-write with mtime guard, same as fleet-status)
5. If the hash is new AND scan_count < 3: do not write to register; bump scan_count in `auto-scan-state.json` only

**Row template:**

```markdown
---

## Row #N — auto-detected YYYY-MM-DD HH:MM UTC

**Status:** auto-detected
**Train:** Fzg <NN> / <train#>
**Signal source:** <skill name> (<signal kind>)
**Signal hash:** `<hash string>`
**First seen:** YYYY-MM-DD HH:MM UTC (scan #<N>)
**Last seen:** YYYY-MM-DD HH:MM UTC (scan #<N>)
**Localisation:** <human-readable location, e.g. "AP .240 not in DHCP leases; last LLDP neighbour at switch D3 port e1-4">
**Suggested category:** <e.g. "missing AP — likely cable fault" / "LLDP topology mismatch" / "Stadler-trunk RX CRC degradation">
**Stadler instructions:** _(engineer to fill before promoting to confirmed)_
**Engineer notes:** _(none yet)_
```

Row numbering is strictly sequential — scanner reads the highest existing row number and adds 1. Holes from deletions (which shouldn't happen since the scanner can't delete) are not reused.

**Forbidden writes (validated):** if the diff between current and computed file content shows any change to a row with `Status: confirmed`, OR any change to the Stadler-instructions block of any row, abort and log `cable_register_allowlist_violation`.

### `auto-scan-state.json`

Full ownership. Schema per [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md). Atomic write each cycle. Engineer should not hand-edit.

## Tier-1 detail — what gets probed

For each candidate CCU IP (known + new from sweep):

1. **Reachability:** TCP `nc -zv -w 5 <ip> 22`. Pass = port open within 5s. Fail = unreachable. ~5s wall time per CCU.
2. **State inventory** (only if reachability passed): `/dosto-state-inventory <ccu-ip> <fzg> --json`. Returns the 12-fact verdict. ~5s wall time.

If `<fzg>` is not yet known for a discovered CCU IP, the scanner does **not** invoke state-inventory (it requires fzg). The CCU is logged as `unknown_fzg_at_ip: <ip>` in `auto-scan-state.json` and surfaced for engineer triage. Map a Fzg by hand-editing the row in `fleet-status.md`; next cycle picks it up.

## Tier-2 detail — what gets diagnosed

For each train where Tier-2 fires:

1. **`/dosto-device-discovery <ccu-ip> --json`** — counts switches/APs vs. expected. Output includes per-missing-device localisation (last LLDP neighbour port).
2. **`scripts/lldp_topology_check.py --ccu-ip <ip> --fzg <NN> --json`** — verifies inter-coach trunk peers match expected OBNTree topology.
3. **`/dosto-l2-health <ccu-ip> --stadler-trunks-only --json`** — RX CRC, carrier-false, link-down on Stadler-facing trunks (A3 e1-4, D1/D3 e0-2/e0-3, B1/B3 e1-11). The full L2 sweep takes longer; `--stadler-trunks-only` (skill flag to add — see "Skill changes needed" below) is the cheap subset.

Each skill is invoked with `--json` and the parsed output feeds the signal-classification logic.

## Signal classification — high vs. medium vs. low

Per [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md). Implementation:

```
For each signal in tier_2_output:
  hash = compute_hash(signal)
  tier = classify(signal)
  match tier:
    case "high":
      bump active_signals[hash].scan_count
      if scan_count >= 3 and no register row exists:
        append register row (Status: auto-detected)
      elif scan_count >= 3 and register row exists with Status: auto-detected:
        bump Last seen timestamp on that row
      # if confirmed row exists, do nothing (per contract)
    case "medium":
      bump active_signals[hash].scan_count
      if signal.metric crosses threshold (e.g. crc_count > 100):
        promote to high tier next cycle
    case "low":
      log to scan_history only, do not track in active_signals
```

**Classification table:**

| Signal | Tier | Threshold for high promotion |
|---|---|---|
| Missing device, LLDP-localised | high | n/a — high immediately |
| LLDP topology mismatch on inter-coach trunk | high | n/a |
| Stadler-trunk RX CRC errors, sustained > 100 across 3 scans | high | crc_count > 100 |
| Stadler-trunk RX CRC errors, 1–100 | medium | promote when crc_count > 100 |
| `carrier_false` count climbing slowly (delta > 5 per scan) | medium | promote when delta > 50 across 5 scans |
| Stadler-trunk speed degraded (1G when expected 10G) | high | n/a |
| Single-scan anomaly | low | discarded after that scan |
| End-of-train e0-1 down | low | known false alarm per CLAUDE.md |
| Train-wide silence | low | reachable=false → tier-1 already captured this |

Thresholds live in `auto-scan-state.json.thresholds:{}` so they can be tuned without rebuilding.

## Bootstrap mode (`--bootstrap-confluence-cables`)

One-time setup before any cable-register Confluence sync. Creates the cable-register page via the Atlassian connector's `createConfluencePage` tool.

**Algorithm:**

1. Read `.claude/state/confluence-pages.json` if it exists; if it already contains `cable_register_page_id`, exit with "already bootstrapped" message.
2. Call `createConfluencePage` with:
   - `cloudId: nomad-digital.atlassian.net`
   - `spaceId: 3854893184` (same as fleet-status page)
   - `parentId: 3859447840` (same parent — sibling of fleet-status)
   - `title: "DEL-OBB-035: Train cabling issues register — Stadler escalation tracker"`
   - `body:` initial empty-state body with the two-section structure (Confirmed faults / Auto-detected anomalies under review)
3. Capture returned `pageId`
4. Write to `.claude/state/confluence-pages.json`:
   ```json
   {
     "fleet_status_page_id": "5410684933",
     "cable_register_page_id": "<new-id>",
     "bootstrapped_utc": "<now>"
   }
   ```
5. Exit with success and the new page URL printed for the engineer to bookmark.

`/dosto-confluence-sync --target cables --push` reads `cable_register_page_id` from this state file. If the file is missing or the field is missing, the sync skill instructs the engineer to run `/dosto-auto-scan --bootstrap-confluence-cables` first.

## `--json` output shape

```json
{
  "skill": "dosto-auto-scan",
  "schema_version": 1,
  "cycle_id": "2026-05-09T14:30:00Z",
  "tier_1_summary": {
    "candidates_scanned": 40,
    "reachable": 7,
    "newly_online": 1,
    "newly_offline": 0,
    "unknown_fzg_at_ip": []
  },
  "tier_2_summary": {
    "fired_for_fzg": [132, 130],
    "deferred_to_next_cycle": [],
    "high_signals_new": 0,
    "high_signals_bumped": 1,
    "medium_signals_active": 2,
    "register_rows_appended": 0
  },
  "writes": {
    "fleet_status_md": "applied",
    "cable_issues_register_md": "no_changes",
    "auto_scan_state_json": "applied"
  },
  "errors": [],
  "duration_seconds": 287
}
```

## Skill changes needed elsewhere

This skill assumes the following extensions exist or will be built:

- **`/dosto-l2-health --stadler-trunks-only`** — flag on the existing skill to scope the L2 sweep to Stadler-facing trunks (A3 e1-4, D1/D3 e0-2/e0-3, B1/B3 e1-11) only. Currently the skill does the full fabric. Adding the flag avoids the auto-scanner doing a full L2 sweep every Tier-2 trigger.
- **`/dosto-confluence-sync --target {fleet|cables|both}`** — flag on the existing sync skill to select which page to push. Default `fleet` (preserves existing behaviour). `cables` reads `cable_register_page_id` from `.claude/state/confluence-pages.json` and pushes the two-section render of `cable-issues-register.md`. `both` does fleet then cables.
- **`scripts/validate_dosto_workspace.py`** — add a check that no row in `cable-issues-register.md` was written by the scanner with `Status: confirmed` (cross-reference `auto-scan-state.json.active_signals[].register_row` against the row's `Status:` field — every scanner-tracked row must have status `auto-detected`).

These are noted but not blocking — the auto-scan skill works without them in degraded modes (full L2 sweep instead of Stadler-only; manual cable register sync instead of orchestrated; no automated compliance check).

## Failure handling

| Failure | Action |
|---|---|
| Cellular outage mid-cycle (SSH dies on Train X) | Mark Train X reachable=false, log Tier-2-aborted, continue with other trains |
| `dosto-state-inventory` exits non-zero | Log to `auto-scan-errors.jsonl`, don't update Train X's state, continue |
| `fleet-status.md` write conflict (mtime changed mid-write, 3 retries failed) | Log `fleet_status_write_conflict`, skip the file write this cycle, retry next cycle |
| `cable-issues-register.md` allowlist violation detected (scanner attempted to touch confirmed row) | Abort the write, log `cable_register_allowlist_violation` with the diff, alert engineer (write to a dedicated `URGENT.md` at workspace root) |
| Confluence bootstrap fails (createConfluencePage error) | Log error, exit 1, instruct engineer to retry or fall back to manual page creation |
| Lockfile already taken by another scanner instance | Exit 0 without scanning (next cycle retries) |
| Orchestrator lockfile detected | Exit 0 (intentional yield) |

The scanner is best-effort. A failed cycle is not an emergency — the next cycle in 30 min retries. Sustained failures (5+ cycles failing on the same fault) escalate by writing to `URGENT.md` at workspace root.

## Test plan

Before deploying the schedule:

1. **`--dry-run` against a known-stable train.** Verify Tier-1 produces clean output, no Tier-2 fires (no transitions), no file writes, preview diff is empty.
2. **`--dry-run` after manually toggling a Fzg row in `fleet-status.md` from reachable to unreachable.** Verify scanner detects the transition and includes Train X in Tier-2.
3. **`--dry-run` with a fabricated `dosto-device-discovery` output showing a missing AP.** Verify signal hashed correctly, scan_count=1 in preview, no register row appended (debounce).
4. **Three consecutive `--dry-run`** with the same fabricated missing-AP output. Verify scan_count reaches 3 on cycle 3 and a register row is appended in the preview.
5. **Allowlist violation test.** Force the scanner to attempt writing a non-allowlisted column (test mode). Verify abort + log entry.
6. **Mutex test.** Touch `.claude/state/orchestrator.lock`. Verify scanner exits 0 without scanning.
7. **Bootstrap test.** Run `--bootstrap-confluence-cables` against a sandbox space. Verify page created, ID stored, idempotent on second run.

After the test plan passes, schedule via Windows Task Scheduler with the action `claude -p "/dosto-auto-scan"` and trigger every 30 min.
