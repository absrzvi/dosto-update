---
name: dosto-orchestrate
description: Run a fleet-day commissioning orchestration inline in the engineer's top-level session. Use when starting a multi-train commissioning day, when the engineer says "/dosto-orchestrate trains=...", or when fanning out commissioning across two or more trains in parallel. Engineer invokes this skill with a list of Train# values (the Nomad-internal primary identifier, e.g. 4736-104); the skill resolves each row in fleet-status.md (Fzg ID is looked up from the row, not computed from a formula), emits an input-validation pre-flight block, runs a network-level pre-flight diagnostic (CCU reachability + full expected device count via dosto-device-discovery, in parallel across trains, gated on a single consolidated engineer prompt), then runs the orchestration in-line in the engineer's session — spawning N parallel dosto-train-worker subagents for the trains that passed pre-flight, surfacing approval gates one at a time, batching fleet-status writes per cycle, and pushing Confluence on gates/terminals/digests. The engineer's top-level session IS the orchestrator (per audit finding F5, 2026-05-11 — the platform doesn't allow agents-spawning-agents, so the skill became inline instead of bootstrapping a separate orchestrator agent).
---

# DOSTO Orchestrate

This skill is the engineer's entry point for a multi-train commissioning day. It runs **inline in the engineer's top-level Claude session** — the engineer's session IS the orchestrator. The skill (a) parses + validates the train list, (b) emits a pre-flight block for engineer approval, (c) spawns N `dosto-train-worker` subagents in parallel from the engineer's session, (d) drives the cycle loop (gate prompts, fleet-status writes, Confluence pushes) until every train reaches a terminal state.

**Why inline rather than agent-as-orchestrator** (per audit F5, 2026-05-11): the platform rule "subagents cannot spawn further subagents" means a `dosto-orchestrator` agent spawned via `Agent(subagent_type: ...)` cannot itself call `Agent` to spawn workers. The 2026-05-11 first-run test confirmed this. So the orchestration logic now lives in this skill, executed by the engineer's top-level session (which DOES have `Agent` + `SendMessage`). The `dosto-orchestrator.md` agent definition has been retired.

## When to use

- **Start of a multi-train commissioning day.** Engineer types `/dosto-orchestrate <trains>` to kick off the day's run.
- **One per fleet-day.** The skill runs for the duration of the day in the engineer's session — they're orchestrating from the same chat thread. If the session crashes or ends, re-invoke this skill with the same args and it offers `--resume` per train (resume state is on disk: `fleet-status.md`, `.claude/logs/orchestrator.jsonl`, and each CCU's btrfs snapshots).
- **NOT for single-train debug runs.** Engineers debugging one train should invoke `/dosto-commission-train` directly (no subagent, no orchestration overhead).

## Inputs

The skill accepts a flexible argument string. Train# (the Nomad-internal primary identifier) is the only required value; CCU IPs can be supplied with `@<ip>` or omitted — when omitted, the skill auto-resolves from `fleet-status.md` with a one-line confirmation per train. Common forms:

```
/dosto-orchestrate trains=4736-111,4736-119,4736-120,4734-119,4734-121     # auto-resolve IPs from fleet-status
/dosto-orchestrate trains=4736-102@10.179.47.1,4736-104@10.179.10.1        # explicit IPs (typo-catch mode)
/dosto-orchestrate trains=4736-111,4736-119@10.179.12.1                    # mixed: first auto-resolved, second explicit
/dosto-orchestrate trains=4736-102,4736-104 dry-run
/dosto-orchestrate trains=4736-102,4736-104 cycle=3
```

Recognised tokens:

| Token | Meaning |
|---|---|
| `trains=<train#>[@<ip>]` or `trains=<train#>[@<ip>],<train#>[@<ip>],...` | **Train# list** (Nomad-internal primary identifier, e.g. `4736-104`, `4734-119`, `4705-103`, `4706-101`). `@<ip>` is optional — when omitted the skill looks up the CCU IP from `fleet-status.md` and emits a one-line confirmation (Case E in Step 2). The skill resolves `fzg` and `consist` from the fleet-status row for each Train#. |
| `dry-run` | Pass `--dry-run` to all subagents. Read-only; every per-device skill runs in `--prepare` mode. |
| `cycle=N` | Override default 5-min digest cadence. Range 1-30 (clamped). |
| `no-confluence` | Skip Confluence pushes for this run (rare — local-only mode). |
| `engineer=NAME` | Override the auto-detected engineer name. Used in fleet-status `Last touched` and Confluence banner. |

**Why Train# is the primary identifier:** Train# (e.g. `4736-104`) is the Nomad-internal name engineers use day-to-day. Fzg ID is the ÖBB customer-facing number that maps to a Train# via the per-series formula, but pre-commissioning the rendered Fzg in switch hostnames and config templates is often wrong (misimaged CCUs, stale Puppet images, hand-set values) — that's literally what commissioning fixes. Routing by Train# means the orchestrator and workers never trust a "Fzg" value pulled from a CCU as authoritative; the authoritative Fzg comes from the fleet-status row, which the engineer curates.

**The retired `fzg=` form:** earlier versions of this skill accepted `fzg=132,133,148` syntax. As of the 2026-05-22 Train#-primary schema reorder, that form is **no longer supported**. The skill errors out with a usage hint pointing to the equivalent `trains=...` form: `Usage: trains=<train#>[,<train#>...] — fzg= form retired 2026-05-22.`

**Why `@<ip>` remains supported as opt-in:** trains move in and out of service, CCUs get re-imaged, and stale `fleet-status.md` rows have caused incorrect-target outages in past sessions. The explicit-IP form is the typo-catch / drift-catch mode — use it when you've just re-imaged a CCU or when you're not confident fleet-status is current. The auto-resolve form (no `@<ip>`) is the common case for a returning engineer whose fleet-status rows are already filed correctly; Case E below adds a per-train confirmation that keeps the same safety property with far less typing.

## Procedure

### Step 1 — Parse and normalise the train list

Tokenise the argument string. Only the `trains=` form is supported (as of 2026-05-22 — see Inputs section). If the engineer typed `fzg=`, halt immediately with `ERROR: fzg= form retired 2026-05-22; use trains=<train#>[,<train#>...] instead.`

Each `trains=<train#>` token MAY include `@<ip>` (explicit IP) or omit it (auto-resolve from fleet-status in Step 2 Case E). When `@<ip>` is present, validate it's a syntactically valid IPv4 address (four dotted octets, each 0-255). Reject malformed IPs at parse time — don't wait until reconciliation.

Validate each Train# matches a known series pattern:

| Series | Pattern | Formula (reference only — runtime Fzg comes from fleet-status row) |
|---|---|---|
| 4734-NNN | `^4734-\d{3}$` | `Fzg = NNN - 100`  (e.g. 4734-119 → Fzg 19) |
| 4736-NNN | `^4736-\d{3}$` | `Fzg = NNN + 28`   (e.g. 4736-104 → Fzg 132) |
| 4705-NNN | `^4705-\d{3}$` | `Fzg = NNN + 128`  (e.g. 4705-103 → Fzg 231) |
| 4706-NNN | `^4706-\d{3}$` | `Fzg = NNN + 88`   (e.g. 4706-103 → Fzg 191) |

Reject any train number that doesn't match one of these four series.

The result of this step is a list of `(train_number, supplied_ip_or_none)` tuples. Step 2 reconciles them with `fleet-status.md` and resolves the Fzg ID per train from the row (NOT from the formula — see [`scripts/fleet_status_lookup.py`](../../../scripts/fleet_status_lookup.py)).

### Step 2 — Reconcile each (Train#, IP) against `fleet-status.md`

This is the IP-and-Fzg reconciliation pass. For each `(train_number, supplied_ip_or_none)`:

1. Look up the Train# row in `fleet-status.md` (via `scripts/fleet_status_lookup.py lookup <train#> --require-fzg`).
2. If the row exists and the Fzg cell is `❓`, halt: `ERROR: <train#> has no Fzg ID in fleet-status — populate the Fzg column (look up via train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP-Port-Allocation.pdf header) before commissioning.`
3. **If `supplied_ip` is None** (engineer omitted `@<ip>`), branch to Case E first.
4. Otherwise, branch on what's there (Cases A-D).

The resolved Fzg from this step is stored alongside each train tuple and passed downstream to the worker spawn prompts AS A POINTER (the worker re-looks-it-up from fleet-status to verify), but the orchestrator's own log entries, fleet-status writes, and Confluence pushes all key off Train# (primary identifier).

**Case A — Row exists, CCU IP recorded, matches `supplied_ip`:** ✅ Proceed silently. Track `ip_source = "fleet-status (matched)"` for the plan summary.

**Case B — Row exists, CCU IP recorded, disagrees with `supplied_ip`:** ⚠️ Stop and prompt the engineer interactively:

```
⚠️ <train#> (Fzg <NN>) CCU IP mismatch.
   fleet-status.md:  <fleet_ip>     (last touched: <YYYY-MM-DD AR>)
   You supplied:     <supplied_ip>

This usually means the CCU was re-imaged or fleet-status is stale.

Options:
  [f] Use fleet-status IP <fleet_ip> for this run (no file change)
  [s] Use your supplied IP <supplied_ip> AND update fleet-status to match
  [a] Abort the whole day's plan

Choice [f/s/a]:
```

- `f` → use `fleet_ip`, mark `ip_source = "fleet-status (overrode supplied)"`.
- `s` → use `supplied_ip`, **edit the row in `fleet-status.md` in place** to set `CCU IP = <supplied_ip>`, mark `ip_source = "supplied (fleet-status updated)"`.
- `a` → exit cleanly, no spawns, no file changes.
- Anything else → re-prompt.

**Case C — Row exists but `CCU IP` is `❓`:** auto-fill silently. Edit the row in `fleet-status.md` to set `CCU IP = <supplied_ip>`. Mark `ip_source = "supplied (filled in fleet-status)"`. Print a one-line confirmation in the plan summary so the engineer sees what was filled.

**Case D — No row exists for this Train#:** ⚠️ Stop and prompt the engineer interactively:

```
⚠️ <train#> has no row in fleet-status.md.
   Train#:     <train_number>   (engineer input)
   Series:     <4734 / 4736 / 4705 / 4706>    (consist: <4-car / 6-car / 4705 / 4706>)
   CCU IP:     <supplied_ip>    (your input)
   Fzg ID:     ❓ (you'll need to provide this — physical inspection or IP-Port-Allocation PDF)

Options:
  [c] Create a fresh row in fleet-status.md and proceed
       (Status: NOT STARTED, all v8 columns ⬜/❓ except CCU IP; Fzg ❓ until you supply)
  [a] Abort the whole day's plan

Choice [c/a]:
```

- `c` → append a new row to the appropriate series section (4736, 4734, 4706, or 4705), populate Train#, leave Fzg as `❓` (engineer fills via PDF lookup before any destructive ops), populate CCU IP, set Status=`NOT STARTED`, all other columns = `⬜` or `❓` per the legend, set `Last touched = <today> <engineer initials>`. Mark `ip_source = "supplied (new row created)"`. Then proceed to Step 5.5 — the worker spawn will halt at its own Fzg lookup if the engineer hasn't backfilled by then. Encourage the engineer to populate Fzg before reaching Stage 4 (apply_train_id_fix), which needs it.
- `a` → exit cleanly.

**Case E — Engineer omitted `@<ip>`, auto-resolve from fleet-status:**

| Fleet-status state | Action |
|---|---|
| Row exists with non-`❓` CCU IP | Use that IP. Emit one-line confirmation: `ℹ️  <train#> (Fzg <NN>): using IP <fleet_ip> from fleet-status (no @<ip> supplied) — correct? [Y/n]` Default Y. Engineer types `n` → halt with usage error asking for explicit `@<ip>`. Mark `ip_source = "fleet-status (auto-resolved)"`. |
| Row exists with `❓` CCU IP | Halt: `ERROR: <train#> has no IP recorded in fleet-status — supply explicitly with trains=<train#>@<ip>`. Cannot proceed without an IP. |
| No row exists for this Train# | Halt: `ERROR: <train#> has no row in fleet-status — supply IP explicitly with trains=<train#>@<ip> to create the row.` (Drops the engineer into Case D's `[c]/[a]` prompt on retry.) |

When multiple trains need confirmation, batch the prompt into a single block:

```
ℹ️  Auto-resolved IPs from fleet-status:
    4736-111 (Fzg 139) → 10.179.24.1   (last touched 2026-05-21 AR)
    4736-119 (Fzg 147) → 10.179.12.1   (last touched 2026-05-21 AR)
    4734-119 (Fzg 19)  → 10.179.45.1   (last touched 2026-05-21 AR)
Proceed with these? [Y/n]:
```

Default Y. Engineer types `n` → halt and ask for explicit `@<ip>` on next invocation.

**After the reconcile loop**, build the full per-train spec:

| Field | Source |
|---|---|
| `train_number` | from input (primary identifier) |
| `fzg` | from `fleet-status.md` row's Fzg cell (looked up by Train#). If `❓`, the reconcile loop halted earlier — never reach this step with unknown Fzg. |
| `ccu_ip` | from reconciled value (Case A/B/C/D logic above) |
| `consist` | infer from series — `nv6 → 6-car`, `nv4 → 4-car`, 4705/4706 series consist is documented per train |
| `ip_source` | tracked per case above, used in Step 4 plan summary |

**Status: DONE** trains get a context-aware prompt — read the train's `Next action` column from fleet-status first, then branch:

**Sub-case DONE-1 — Other outstanding items** (Next action contains anything substantive — e.g. "wait for Stadler", "verify .231"):

```
⚠️ <train#> (Fzg <NN>) is DONE but has outstanding work: <next_action_text>
   Including will re-validate state via the full 19-stage pipeline.

Options:
  [s] Skip this train
  [i] Include anyway
  [a] Abort

Choice [s/i/a]:
```

**Sub-case DONE-2 — No outstanding work** (Next action is empty or `—`):

```
⚠️ <train#> (Fzg <NN>) is already DONE with no outstanding work in fleet-status.
   Including would re-run all 19 stages on a healthy train.

Options:
  [s] Skip (recommended)
  [i] Include anyway
  [a] Abort

Choice [s/i/a]:
```

Default for DONE-2 and DONE-3 is `s`.

**Surgical-edit discipline when writing to `fleet-status.md`** (per CLAUDE.md Principle 3): in Cases B/C/D the skill modifies **only** the cells it owns for this reconcile (`CCU IP`, and for Case D the entire new row). Engineer hand-edits in other columns (Customer report, Health check date, Stadler cabling notes) MUST survive untouched. Read the file, edit the targeted cells, write back — do not re-render the whole table.

**IP conflict detection across the full file** (after the reconcile loop, before building the per-train spec): for each resolved `ccu_ip`, grep the full `fleet-status.md` for that IP literal. If it appears in any detail-block header (`**CCU:** \`<ip>\``) for a **different** Fzg than the one you've resolved it to, halt with:

```
⚠️ IP conflict — <ip> appears in multiple places:
    <train#-X> (current resolve, at-a-glance row)
    <train#-Y> detail block header
Confirm which train owns this IP before proceeding.
  [x] Use <train#-X>, treat <train#-Y> detail block as stale (engineer cleans up later)
  [y] Use <train#-Y> instead (re-prompt at Step 2 for <train#-X>)
  [a] Abort
```

This catches reconciliation drift between at-a-glance rows and detail blocks at reconcile time, not after a worker has been spawned. Confirmed engineer-visible during 2026-05-21 (`10.179.12.1` listed for both 4736-112 (Fzg 140) detail block and 4736-119 (Fzg 147) at-a-glance row).

**Pending-section cleanup** (post-reconcile, after each train's IP is confirmed): check the `## Pending Fzg assignment` section. If the resolved `ccu_ip` appears in that table, remove that row from Pending (surgical: delete only that one row, preserve all others). Print a one-line note:

```
ℹ️  Removed 10.179.45.1 from Pending Fzg assignment section (now confirmed to 4734-119 / Fzg 19).
```

This is housekeeping for the morning-brief discovery sweep — once an IP is confirmed assigned, the Pending row is stale.

### Step 3 — Build the train list array

```json
{
  "trains": [
    {"train_number": "4736-102", "fzg": 130, "ccu_ip": "10.179.47.1", "consist": "6-car"},
    {"train_number": "4736-104", "fzg": 132, "ccu_ip": "10.179.10.1", "consist": "6-car"},
    {"train_number": "4736-120", "fzg": 148, "ccu_ip": "10.179.2.1", "consist": "6-car"}
  ],
  "engineer_name": "Abbas Rizvi",
  "dry_run": false,
  "cycle_minutes": 5,
  "confluence_sync": true
}
```

Engineer name resolution order:
1. `engineer=NAME` from args
2. `git config user.name`
3. `$USER` / `$USERNAME` env var
4. Fallback: `"unknown"`

### Step 3.5 — Read cable-issues-register.md for each train in the plan

Before printing the plan, grep `cable-issues-register.md` for each resolved Train# (and its Fzg). For each match, extract any rows whose `Status` is `🔴 OPEN`.

Store this as `cable_issues[train_number] = [list of open issue summaries]`.

This is a **read-only** step — the register is never written here. Writes happen in Step 7.5 (new fault detection) and via `dosto-device-discovery` output.

### Step 4 — Print the plan and confirm

Show the engineer a summary before spawning anything. For each train, include any open cable-register issues inline so the engineer sees the full picture before approving dispatch:

```
─── DOSTO Orchestrate — fleet day plan ─────────────
Engineer:    Abbas Rizvi
Cycle:       5 min digest
Dry run:     no
Confluence:  push enabled (page 5410684933)

Trains to commission (3 — all in parallel):
  • 4736-102 / Fzg 130 / 10.179.47.1 / 6-car
    IP source:     fleet-status (matched)
    Current state: PAUSED — apply patches + persist + fix train_id template + fix vlan7 — see notes
    Last touched:  2026-05-09 AR
    Cable issues:  none on file
  • 4736-104 / Fzg 132 / 10.179.10.1 / 6-car
    IP source:     supplied (fleet-status updated — was 10.179.10.99)
    Current state: BLOCKED w/ Stadler (D4) + 6 APs stuck — push remaining 3 APs (.237 .238 .240), verify .231
    Last touched:  2026-05-09 AR
    Cable issues:  🔴 #5 — D3 e1-2 physical-layer fault (D4 AP missing)
  • 4736-120 / Fzg 148 / 10.179.2.1 / 6-car
    IP source:     supplied (filled in fleet-status — was ❓)
    Current state: PAUSED — sudo obn discover && sudo obn update c all
    Last touched:  2026-05-04 AR
    Cable issues:  none on file

This session will then:
  1. Spawn one dosto-train-worker subagent per train (N parallel) via Agent
  2. Surface approval gates one at a time as they fire
  3. Write fleet-status.md and push Confluence at end of each cycle
  4. Run until all subagents reach terminal state (DONE / BLOCKED / ERROR)

Confirm? [Y/n]:
```

Default is **Y** (proceed). Engineer types `n` to abort cleanly. Anything else → re-prompt.

### Step 5 — Emit MANDATORY PRE-FLIGHT BLOCK

This is the constitutional Principle 1 forcing function — before spawning anything, surface assumptions and open questions in writing:

```
─── DOSTO Orchestrate — Pre-Flight ─────────────
Engineer:    Abbas Rizvi
Cycle:       5 min digest
Dry run:     no
Confluence:  push enabled (page 5410684933)

Trains to commission (3):
  • 4736-102 / Fzg 130 / 10.179.47.1 / 6-car
    Current state: PAUSED — apply patches + persist + fix train_id template + fix vlan7
  • 4736-104 / Fzg 132 / 10.179.10.1 / 6-car
    Current state: BLOCKED w/ Stadler — 6 APs stuck (.237 .240 .238 .231 .230 .226)
  • 4736-120 / Fzg 148 / 10.179.2.1 / 6-car
    Current state: PAUSED — sudo obn discover && sudo obn update c all

▼ Known cable issues (from cable-issues-register.md):
  4736-102 (Fzg 130): none on file
  4736-104 (Fzg 132): 🔴 #5 — D3 e1-2 PHY fault — D4 AP missing (OPEN)
  4736-120 (Fzg 148): none on file

▼ Assumptions (specific, disprovable):
  • fleet-status.md rows are current as of last engineer save
  • cable-issues-register.md is current as of last Stadler contact
  • Each CCU is reachable via the project key at the IPs listed above
  • The Atlassian Confluence MCP connector is configured and working
  • The TFTP CT helper runtime fix (if previously applied) does NOT survive
    a CCU reboot — first stage of each subagent will re-check and re-apply if needed

▼ Open questions: <none / list them here>

▼ Simplicity check:
  Spawning N parallel subagents per the contract. No batching, no custom
  ordering. Each subagent runs the canonical 19-stage pipeline.

▼ Per-train success criteria (will be checked at end of day):
  4736-102 (Fzg 130): 8/8 OBN persisted, train_id=130 hardcoded, vlan7=172.19.193.2,
           all switches/APs at target, customer report on disk
  ... (one block per train, derived from fleet-status + per-train goals)

Confirm? [Y/n]:
```

Rules for the Pre-Flight:
- Assumptions list MUST be specific and disprovable. "Each CCU is reachable" is good; "everything is fine" is not.
- Open questions: if non-empty, halt regardless of the engineer's [Y/n] — open questions resolve before destructive ops.
- Simplicity check is one paragraph: are you taking the simplest path, or deviating? If deviating, name the evidence forcing the deviation.
- Per-train success criteria MUST be verifiable at end-of-day from skill outputs or fleet-status fields.

**vlan7 IP auto-computation:** the per-train success criteria block MUST list the expected vlan7 IP, computed inline using the canonical formula (no manual math). For each train in the plan, compute:

```python
octet3 = 128 + (fzg // 2)
octet4 = (128 if fzg % 2 == 1 else 0) + 2
expected_vlan7 = f"172.19.{octet3}.{octet4}/17"
```

Render into the success-criteria block as `vlan7=<expected_vlan7>`. The engineer never has to verify the bit-packing math at pre-flight time. Exception: trains where fleet-status records a non-formula vlan7 (e.g. Fzg 19's `172.19.150.130/17` per Nomad-internal train_id 45 convention) — use the fleet-status value and append `(per detail block convention)`.

Default is **Y** (proceed). Engineer types `n` to abort cleanly.

### Step 5.5 — Network pre-flight diagnostic (gated dispatch)

After Step 5's text pre-flight is approved, run a **real network-level diagnostic** against each train in parallel BEFORE spawning any commissioning worker. Purpose: confirm every accepted train has CCU reachability AND the full expected device count visible (18 sw + 24 AP for nv6, 12 sw + 16 AP for nv4). Trains that fail this gate are surfaced separately and excluded from dispatch unless the engineer explicitly opts to proceed.

**Why this exists:** the text pre-flight (Step 5) validates the engineer's *input* (Fzg formula, fleet-status row exists, CCU IP populated). It does NOT touch the network. Going straight from input-validation to spawning 19-stage commissioning workers means the workers' Stage 1 (`initial_diagnostics`) is the first time we see actual device state — and if multiple trains have missing devices, the engineer gets bombarded with Gate 5 prompts in parallel. Better: do the discovery once, up front, in parallel, with a single consolidated engineer prompt.

**Procedure:**

1. For each accepted train, in **parallel** (single Agent message with N tool-uses OR direct parallel SSH from the orchestrator session if no Agent fan-out is needed):
   - TCP/22 probe to the CCU (5s timeout) — `reachable: bool`
   - If reachable: device count via fping + ARP OUI match (NOT DHCP):
     ```bash
     # Compute the management subnet from CCU IP (third octet)
     fping -a -q -g 10.179.<X>.128 10.179.<X>.255 2>/dev/null   # refresh ARP
     ip neigh show dev vlan100 | grep -c 'a0:59:3a'             # VDS switches (a0:59:3a OUI)
     ip neigh show dev vlan100 | grep -c '00:14:5a'             # Westermo APs (00:14:5a OUI)
     ```
     DHCP-based discovery (`sudo dhcp-lease-list`) is **wrong** here — VDS switches have 2-minute DHCP lease lifetimes and any that haven't recently renewed are invisible, causing false-FAIL sw=0 readings (observed 2026-05-21). fping wakes the ARP cache, OUI grep counts what's physically reachable. Same ~15s wall-clock, no DHCP timing dependency.
   - Expected counts: `nv6 → 18 sw + 24 AP`, `nv4 → 12 sw + 16 AP`. Compute from `consist` field.
   - Total wall-clock: ~30–60s for the whole batch regardless of N
2. Classify each train into a **three-tier** verdict:

| Condition | Tier |
|---|---|
| `reachable: true` AND all devices present | ✅ PASS |
| `reachable: true` AND 1-2 APs missing on an otherwise healthy train | 🟡 SOFT-WARN |
| `reachable: true` AND ≥1 switch missing OR ≥3 APs missing (≥20% absent) | 🔴 HARD-FAIL |
| CCU unreachable on TCP/22 | 🔴 HARD-FAIL |

Soft-warn is for plausible-timing shortfalls (AP mid-reboot, DHCP not yet renewed). Hard-FAIL is for genuinely-can't-proceed states (cable fault, CCU offline, coach powered off). The distinction was added 2026-05-21 after 4736-119 (Fzg 147, 1 AP missing) and 4736-120 (Fzg 148, 1 sw + 2 APs absent) were over-classified as FAIL alongside genuine unreachables.

3. **Pre-stage fix scripts on every reachable CCU** (Enhancement #8/#12 — workers cannot SCP). For each train classified PASS or SOFT-WARN, in parallel:
   ```bash
   scp -i <key> scripts/fix_obn.py scripts/fix_obn_bug8.py scripts/fix_obn_bug9_pysnmp_thread_safety.py developer@<ccu>:/tmp/
   ssh -i <key> developer@<ccu> "sudo cp /tmp/fix_obn*.py /var/tmp/ && echo STAGED"
   ```
   The chroot bind-mounts `/var/tmp/`, NOT `/tmp/` — scripts at `/tmp/` are invisible inside the chroot, so the `cp` to `/var/tmp/` is mandatory. Both paths get the file (host-side via `/tmp`, chroot-side via `/var/tmp`).

   Track `scripts_staged: true/false` per train. If staging fails (network blip, perms denial, etc.) for a train that was PASS, **demote to SOFT-WARN** with reason `script staging failed: <err>` — worker can still start but will need to escalate when it needs the scripts. If staging fails for a SOFT-WARN train, it stays SOFT-WARN with both reasons listed.

   Wall-clock: ~5-10s per CCU in parallel.

4. Emit a consolidated result block:

```
─── Network Pre-Flight Results ──────────────────
Trains passing pre-flight (N):
  ✅ 4736-115 / Fzg 143 / 10.179.18.1 — 18/18 sw + 24/24 AP visible — scripts staged
  ✅ 4736-116 / Fzg 144 / 10.179.16.1 — 18/18 sw + 24/24 AP visible — scripts staged

Soft-warn (will dispatch with note — Gate 5 may fire in Stage 2 if count doesn't improve):
  🟡 4736-119 / Fzg 147 / 10.179.12.1 — 18/18 sw + 23/24 AP — 1 AP plausibly mid-reboot — scripts staged
  🟡 4736-120 / Fzg 148 / 10.179.2.1 — 17/18 sw + 22/24 AP — E3 coach + 2 APs absent — scripts staged

Hard-FAIL (will NOT dispatch):
  🔴 4736-104 / Fzg 132 / 10.179.10.1 — 18/18 sw + 21/24 AP — 3 APs missing (>20% threshold)
  🔴 4734-109 / Fzg 9   / 10.179.38.1 — UNREACHABLE on TCP/22
```

5. **Engineer prompt** — only when ≥1 hard-FAIL exists. Soft-warn alone dispatches automatically:

| Pre-flight result | Behaviour |
|---|---|
| All trains PASS | Print block + "All N trains passed; dispatching." No prompt. Proceed to Step 6. |
| Mix of PASS + SOFT-WARN, no HARD-FAIL | Print block + "All N trains passed pre-flight (M with soft warnings — see above). Dispatching." No prompt. Proceed to Step 6. |
| ≥1 HARD-FAIL | Print block + the prompt below. |
| All trains HARD-FAIL | Print block + "0 trains passed pre-flight; nothing to dispatch." Exit cleanly. |

Prompt (only when ≥1 hard-FAIL):

```
Dispatch the N passing + M soft-warn trains?
Hard-FAIL trains stay in fleet-status as-is.
[Y/n/all]:
```

- `Y` (default) → dispatch PASS + SOFT-WARN subset; HARD-FAIL trains skipped this run with a one-line note appended to their fleet-status `Next action` (`pre-flight YYYY-MM-DD: <reason>`)
- `n` → abort the whole orchestration; no workers spawn
- `all` → dispatch all trains including HARD-FAIL; those workers will hit Gate 5 (device_count_mismatch) in Stage 2 as normal — engineer accepts the duplicate prompting

**Logging:** append a JSON line per pre-flight run to `.claude/logs/orchestrate-preflight.jsonl` — `{cycle_id, run_at, trains: [{fzg, ccu_ip, reachable, switches: "n/m", aps: "n/m", verdict: "PASS|SOFT_WARN|HARD_FAIL", failure_reason, scripts_staged}]}` — useful for diagnosing recurring failures (same train fails pre-flight 3 days in a row → escalate).

### Step 6 — Claim trains in fleet-status, then spawn workers

#### Step 6.0 — Concurrency check (claim-already-held detection)

**Before spawning any worker**, re-read `fleet-status.md` row for each train in the dispatch set. If the row's `Nomad status` cell currently parses as an in-flight claim (via `scripts/fleet_status_lookup.py parse_in_flight()`) AND the claim's heartbeat age is `< 30 min` (per the stale-claim threshold), the train is **already claimed by another session**. Halt the dispatch for that train with:

```
⚠️  4736-104 (Fzg 132) is already claimed by another orchestrator session.
    Current claim: stage push_switch_config (3/18), hb 2026-05-22T14:32Z (4 min ago), sess 1428Z
    Options for this train:
      [s] Skip this train (other session keeps working it)
      [r] Force-reclaim (assumes other session is dead; flips claim to this session)
      [a] Abort the whole dispatch
    Choice [s/r/a]:
```

- `s` (default for stale-but-fresh claims) → drop this train from the dispatch set; continue with the rest.
- `r` → overwrite the claim with this session's. Use only when you're certain the other session is dead (e.g. you crashed it).
- `a` → exit cleanly with no dispatch and no claims written.

If the heartbeat age is `≥ 30 min`, the claim is **stale** — the previous session likely died. Auto-emit a one-line warning (`ℹ️  4736-104: reclaiming stale claim from sess 1428Z, last heartbeat 47 min ago`) and proceed with the dispatch. No engineer prompt needed for stale claims (the morning-brief stale-claim gate is the engineer-facing surface for these; the orchestrator at dispatch time just reclaims).

#### Step 6.1 — Write the initial claim to fleet-status

For each train surviving Step 6.0, write the in-flight claim to its `Nomad status` cell using `format_in_flight()` from the lookup helper:

```python
from scripts.fleet_status_lookup import format_in_flight
claim = format_in_flight(
    stage='initial_diagnostics',
    step=None, total=None,
    elapsed_seconds=0,
    heartbeat_iso=utcnow_iso(),
    session_id=cycle_id_short(),   # last 4 chars of cycle_id, e.g. '1212Z'
)
# Write to the row's Nomad status cell via the orchestrator's standard
# fleet-status writer (surgical, only the cells it owns — see "Fleet-status
# writer" section below).
```

This is the at-a-glance signal for any other engineer / session reading fleet-status: "this train is being worked on right now." The whole format is canonical and consumed by `parse_in_flight()` in `morning-brief.py` and any future tool that wants to render in-flight visibility.

#### Step 6.2 — Spawn workers

Use the `Agent` tool with one tool-use block per train, **all in a single message** so the harness runs them concurrently. Each gets:

- `subagent_type: "dosto-train-worker"`
- `name: "train-<train_number>"` (e.g. `train-4736-104` — so you can `SendMessage` it later)
- `description: "DOSTO per-train worker for <train_number>"`
- `prompt`: **pointer-not-dump** per the F2 contract — pass Train#, CCU IP, consist, engineer name, dry-run flag, ip_source, `scripts_staged: true/false` (from Step 5.5 staging result — tells the worker whether `/var/tmp/fix_obn*.py` is guaranteed present or whether it must request the orchestrator to SCP), `session_id` (so the worker can echo it into its reports for cross-correlation), and nothing else. The worker reads `fleet-status.md`, `fleet-journal.md`, the four contracts, and the per-device skills itself. Do NOT inline per-train prose, recovery sequences, or historical context — those bloat the worker's context window for its entire lifetime.

After spawning, **start the cycle clock**. Cycle 1 runs for `cycle_minutes` (default 5).

### Heartbeat protocol (claim refresh and stage updates)

The in-flight claim in each row's `Nomad status` cell is the orchestrator's **liveness signal**. Other engineers, other sessions, and `morning-brief` rely on it to answer "is this train being worked on, and is the session still alive?"

The orchestrator MUST update the claim on **all four** of the following triggers:

| Trigger | What gets refreshed |
|---|---|
| **Worker spawn (Step 6.1)** | Initial claim written with `stage=initial_diagnostics`, `elapsed=0`. |
| **Stage-transition report** (worker emits a report with a new `stage.id`) | `stage`, `step`, `total`, `elapsed_seconds`, `heartbeat_iso` all updated to match the report. Inline write — do NOT wait for cycle end. |
| **Step-within-stage report** (worker emits a report with same stage but new `current_step` / `total_steps`) | `step`, `total`, `elapsed_seconds`, `heartbeat_iso` updated. Same inline write semantics — engineers checking the at-a-glance row should see "3/18 → 4/18" almost immediately when the worker reports it. |
| **Cycle digest boundary** (every 5 min wall-clock, even if no worker reports arrived) | `heartbeat_iso` refreshed to `utcnow()` for every active train. `elapsed_seconds` recomputed against the stage's `started_at` (still echoed by the worker in its latest report). Stage/step unchanged. This is the **pure liveness ping** — proves the orchestrator session is still alive even when a worker is mid-long-running stage (e.g. a 45-min AP firmware push). |

**Why all four:** the first three give engineers stage-accurate progress; the fourth proves the session itself hasn't died between worker reports. Stale-claim detection (in `morning-brief`) relies on this cycle-boundary ping — without it, a healthy session running a 1-hour AP firmware push would look stale after 30 min.

**Terminal-state cleanup:** when a worker reports `DONE`, `BLOCKED`, or `ERROR`, the orchestrator removes the in-flight claim from the `Nomad status` cell and writes the appropriate terminal status:

| Terminal | New `Nomad status` cell |
|---|---|
| `DONE` (no Stadler issues) | `🟢 DONE` |
| `DONE` (with Stadler-blocking `issues[]`) | `🟢 DONE w/ Stadler — <issue summary>` |
| `BLOCKED` | `🔴 BLOCKED — <escalation_reason>` |
| `ERROR` | Keep prior status from before the in-flight claim; append a note to the per-train detail block. Engineer triages. |
| `PAUSED` (no worker recovery within 30-min budget) | `🟡 PAUSED — <reason from final report>` |

The terminal write is the orchestrator's responsibility — workers never write fleet-status themselves (per the orchestrator-as-sole-writer rule). After a terminal write, the row's `Nomad status` no longer parses as an in-flight claim, freeing it for future dispatch.

**Crash recovery:** if the orchestrator session itself crashes mid-flight, the claims remain in fleet-status with their last-known heartbeats. Next morning, `/dosto-morning-brief` surfaces them as stale claims (heartbeat > 30 min). Engineer chooses per-train: clean to PAUSED, or reclaim with a new orchestration.

## Runtime — the cycle loop

After Step 6, you (the engineer's session) are now the running orchestrator. The skill body from here is the cycle loop, executed turn-by-turn as workers report back via `<task-notification>` events.

### Per cycle (default 5 min wall-clock; not strictly time-bounded — cycles end at terminal-state convergence or engineer abort)

1. **Listen for subagent notifications.** When a `<task-notification>` arrives:
   a. Validate the JSON payload is shaped per `.claude/contracts/subagent-report.md` (v2). Accept `schema_version: "1"` with a `schema_version_drift` flag; reject anything else as `ERROR` and log to `.claude/logs/orchestrator-errors.jsonl`.
   b. Branch on `status`:
      - `NEEDS_APPROVAL` → **immediately** surface the gate prompt to the engineer per `.claude/contracts/approval-gates.md` v2 (compact form, expandable on `?`). Don't wait for cycle end.
      - `DONE` / `BLOCKED` / `ERROR` → **immediately** push Confluence via `Skill: dosto-confluence-sync --push --json`. Stage out the worker for the end-of-cycle digest.
      - `DIAGNOSING` / `APPLYING_FIXES` / `PUSHING_TO_DEVICES` / `PAUSED` → buffer in your in-memory per-train state. **Then immediately check stage duration budget (see below).** No other immediate action.
   c. Update in-memory per-train state: latest report, latest stage, latest fields (per the F2 contract, you only see *current-stage* `skill_outputs`; you maintain the audit trail externally via the log).
   d. **Stage duration budget check (C4 — fires on every notification, not just at cycle end):**
      - Compute `stage_elapsed = now - stage.started_at`.
      - If `stage.expected_duration_seconds` is non-null AND `stage_elapsed > stage.expected_duration_seconds * 1.5`:
        - Emit inline to the engineer **immediately** (do NOT wait for cycle digest):
          ```
          ⚠️  Fzg <NN> — stage <stage_id> over budget.
              Expected: <expected>s   Elapsed: <actual>s   (<ratio>× budget)
              Current step: <current_step>/<total_steps> (if set)
              Last issue: <issues[-1].description or "none">
          ```
        - Log `over_budget: true` in the per-turn event written to `orchestrator.jsonl`.
        - Do NOT halt the worker. The warning is informational — the engineer may choose to `abort` or let it run. Over-budget alone is not a gate.
      - Threshold of 1.5× (not 2×): chosen to surface a warning while the stage is still recoverable, not after it has already failed silently.

2. **Handle engineer input between notifications:**
   - `status` / `status?` / `where are you` → print a per-train one-line summary table (compact, scannable in <5s). Do NOT re-fetch from workers — use your in-memory state.
   - `y` / `n` / `w` / `p` / `c` / `defer` / `?` → response to the most recently surfaced gate. Parse per `approval-gates.md` v2; `SendMessage` the worker; log to `.claude/logs/approval-gates.jsonl`; trigger Confluence push.
   - `abort` → halt cleanly: `SendMessage` shutdown_request to each worker, do NOT write fleet-status, exit the skill.
   - Anything else → engineer may be doing other work in the same session; treat as out-of-band, continue waiting for the next notification.

3. **At cycle boundary** (5-min wall-clock or convergence to terminal states):
   a. **Compute the cycle digest** — per-train summary of what changed since last cycle: status transitions, stage progress (`current_step` / `total_steps`), new issues, terminal events.
   b. **Print the digest** to the engineer (see format below).
   c. **Write `fleet-status.md`** if any field changed (per the `fields` block of incoming reports). Use the row-merge rules in "Fleet-status writer" below.
   d. **Push Confluence** via `Skill: dosto-confluence-sync --push --json` if fleet-status changed.
   e. **Append to `.claude/logs/orchestrator.jsonl`** — one entry per cycle with the per-train state snapshot.

4. **Loop until all workers terminal.** When every worker reports `DONE` / `BLOCKED` / `ERROR`, emit the end-of-day report (see "End of day" below) and stop the skill.

### Cycle digest format

```
─── Cycle 7 — 2026-05-09 14:35 UTC (elapsed 35:00) ───

4736-102 / Fzg 130: 🟡 APPLYING_FIXES (apply_obn_patches, t+220s, exp 120s — over budget, watch)
  • Bug 5 patch applied; bug 6 marker still missing — investigating
  • OBN patches: 7/8 (was 0/8)

4736-104 / Fzg 132: ✅ DONE (t+34:12)
  • All 6 stuck APs unblocked: .226 .230 .231 .237 .238 .240 → 6.11.2-0
  • Final L2 health: clean (1 known cable issue: D4 missing — Stadler item)
  • Customer report: reports/customer/OBB_Fzg132_v1.0.docx

4736-120 / Fzg 148: 🔵 NEEDS_APPROVAL (await_obn_update_c — queued 12 min, see prompt below)

────────────────────────────────────────────────────
Approvals queued: 1   Blocked: 0   Errors: 0   Done: 1   Working: 1
⚠️  Approvals waiting > 10 min: 1 (4736-120, await_obn_update_c, 12 min)
Confluence push: queued for end of cycle.
fleet-status.md: 2 rows updated (132, 148).
```

**Pending-approval visibility rule:** for every approval in the queue at digest time, compute `now - <queued_at>`. If any single approval > 10 min, emit `⚠️  Approvals waiting > 10 min: N (Fzg X, gate Y, Z min)` after the totals line. Engineers stepping away from the keyboard then notice on return that they have unanswered acks blocking work.

If multiple approvals are over threshold, list them comma-separated. Don't truncate.

**SSH flap visibility rule:** for every active train, include its `ssh_flap_count` and `paused_seconds_total` in the digest line when either is non-zero. Format: `(flaps: N, paused: Xs total)`. If any train has `ssh_flap_count ≥ 3`, flag it with `⚠️  high connectivity noise` in the digest and suggest `--legacy-serial-sw-config` if the train is in a device-push stage.

## Approval flow

When a worker emits `status: NEEDS_APPROVAL`:

1. **Buffer immediately** in `pending_approvals`. Don't wait for cycle end.
2. **At the next safe boundary** (between notification handles, or right after a cycle digest), surface the next pending approval to the engineer in the compact form per `approval-gates.md` v2:

   ```
   [Gate 1] promote_snapshot — 4736-104 (Fzg 132) — 8/8 OBN patches confirmed; persisting via chroot promote
     destructive: ✅   reversible: ❌   command: sudo /usr/sbin/nd-systemupdate.sh shell + fix_obn.py + exit
   Options: y | n | defer | ?
   ```

3. **End your turn.** The engineer's next message is the response.
4. **Parse the response** per the gate's `response_shape`:
   - Binary: `y` → approved; `n`/empty → denied; `defer` → re-queue; `?` → expand to verbose form
   - Three-way (Gate 5 only): `w` → wait; `p`/empty → partial; `c` → continue_full; `defer` → re-queue; `?` → expand
5. **`SendMessage` the response to the worker** by name (`train-fzg-132`). Response JSON per `approval-gates.md` v2 (e.g. `{"approval": "approved", "approved_by": "<engineer>", "approved_at": "<now>"}`).
6. **Log the gate** to `.claude/logs/approval-gates.jsonl` (one JSON line per decision).
7. **Trigger immediate Confluence push** — gates are state-changing events worth syncing.
8. **If multiple approvals are queued**, surface the next one. Show `(N of M)` labels.

### Concurrent approvals

Queue, show one at a time. Never batch into "approve all 3" — exactly the rubber-stamp pattern the contract forbids.

## Fleet-status writer (orchestrator-as-sole-writer)

You are the only entity that writes `fleet-status.md` during the day. Per cycle:

1. Compute the diff between (a) last-known fleet-status row for each active train and (b) the merged `fields` block from all reports received this cycle for that train.
2. For each train with any field changed, edit the relevant row in-place. Use the column mapping from `subagent-report.md` § "fields".
3. Update `Last touched` to today's UTC date + engineer's initials.
4. Update `Nomad status` to the most informative current value:
   - Worker terminal `DONE` → `🟢 DONE` (or `🟢 DONE w/ Stadler — <summary>` if any `BLOCKED` issues remain — infer from `issues[]`). **Clears the in-flight claim.**
   - Worker terminal `BLOCKED` → `🔴 BLOCKED — <escalation_reason>`. **Clears the in-flight claim.**
   - Worker terminal `ERROR` → keep prior `Nomad status` from before the claim, add note in per-train detail block. **Clears the in-flight claim.**
   - Worker terminal `PAUSED` (after the 30-min retry budget exhausted) → `🟡 PAUSED — <reason>`. **Clears the in-flight claim.**
   - Worker in `NEEDS_APPROVAL` → **keep the in-flight claim with the await_* stage**, do NOT swap to a separate status. The claim format already conveys the await state via its stage_id (e.g. `stage await_promote_snapshot`). Engineers reading fleet-status can tell "this train is waiting for a gate" from the stage prefix `await_`.
   - Worker in working state (`DIAGNOSING` / `APPLYING_FIXES` / `PUSHING_TO_DEVICES` / `PAUSED`) → **refresh the in-flight claim** via `format_in_flight()` with the latest stage / step / total / elapsed / heartbeat. See "Heartbeat protocol" above.
5. Update `Next action` to the worker's last reported `next_action`, or compute from terminal state.

**Hand-edit preservation:** if between cycles the engineer hand-edits fields you don't manage (`Customer report`, `Health check date`), preserve them. Only overwrite the columns in the `fields` block.

### Step 7.5 — Auto-append new faults to cable-issues-register.md

After each cycle's fleet-status write, inspect the `ap_missing` and `switches_missing` arrays from any `dosto-device-discovery` skill output received this cycle. For each missing device:

1. Check `cable-issues-register.md` for an existing open entry matching this Train# AND the same switch+port. If a matching `🔴 OPEN` row already exists — **do nothing** (no duplicate rows).
2. If no match exists, append a new row to the "Open issues" at-a-glance table and a corresponding `###` detail block. Use the `stadler_instruction` text from the skill output as the "Required action" body. Template:

```markdown
| N  | <train#>  | <switch> <port>  | <fault_type>   | 🔴 OPEN |
```

```markdown
### #N — <train#> (<consist>) — <switch> <port> <fault summary>

**What we see:** <live_state description from skill output>
**Expected:** <switch> port <port> hosts <AP/switch> per nv{4,6} topology.

**Required action:** <stadler_instruction from skill output>

**Status:** 🔴 OPEN
```

Set `fault_type` based on the `verdict` from device-discovery:
- `ap_missing` where `live_state.speed == "Auto"` AND `live_state.rx_bytes == 0` → `AP not connected`
- `missing_switches` → `missing trunk` (switch absent — escalate to Stadler)
- `ap_missing` where `live_state.rx_bytes > 0` but no LLDP peer → `physical-layer`

3. After writing, print a one-line note in the cycle digest:
   ```
   ℹ️  cable-issues-register.md: appended #N (4736-104 / D3 e1-2 AP not connected)
   ```

**Surgical-edit discipline:** append only — never edit or delete existing rows. The register is append-only. Only the engineer (or a future `/cable-register-resolve` skill) marks entries `RESOLVED`.

**Atomicity:** read the file once, compute all row changes, write once. Don't write partial state.

### Surgical-Changes allowlist (Principle 3)

You may write to **only these columns** when merging worker `fields` blocks:

| Allowed field | Maps to fleet-status column |
|---|---|
| `obn_patches` | OBN patches |
| `switches_v8` | Switches v8 |
| `aps` | APs |
| `vlan7_ok` | vlan7 ok |
| `stadler_cabling` | Stadler cabling |
| `fw_reach` | FW reach (per F9: derived from `fw_commission_state`, not raw TCP probe) |
| `health_check_done` | Health check |
| `customer_report` | Customer report |

Any other key in a worker's `fields` block is a **contract violation**:
1. Log to `.claude/logs/orchestrator-errors.jsonl` with `action: "unknown_field"`.
2. Do NOT write the unknown field.
3. Surface in next cycle digest under "Contract violations".
4. Do NOT shut down the worker — it may have other valid fields.

`Status`, `Next action`, `Last touched` are computed by you per the rules above, not pulled from worker fields.

## Confluence push policy

| Trigger | Action |
|---|---|
| Any worker transitions to `NEEDS_APPROVAL` | Push immediately |
| Any worker transitions to `DONE` / `BLOCKED` / `ERROR` | Push immediately |
| End-of-cycle digest if `fleet-status.md` changed | Push at cycle end |
| End-of-cycle digest if nothing changed | Skip — no version bump |

Push via `Skill: dosto-confluence-sync --push --json`. The skill handles drift detection. If it returns `verdict: drift_detected`, surface the drift report to the engineer and ask whether to `--push --force` or pull the manual edits into local. Don't auto-resolve.

## Logging

Four append-only files in `.claude/logs/`:

| File | One entry per |
|---|---|
| `orchestrator.jsonl` | Per-turn event AND cycle digest. See schema below. |
| `approval-gates.jsonl` | Each gate decision (approved / denied / deferred / auto_blocked_defer_limit). Includes `defer_count`. |
| `orchestrator-errors.jsonl` | Each schema-version mismatch, malformed JSON, or contract violation. |
| `orchestrate-preflight.jsonl` | Each pre-flight run — per-train device counts, verdict, scripts_staged result. |

Existing files: `confluence-sync.jsonl` and `confluence-drift.jsonl` (both managed by the sync skill).

### `orchestrator.jsonl` per-turn event schema

Every inbound subagent notification (not just cycle digests) appends one JSON line. This enables crash recovery to replay state without re-running diagnostics — the orchestrator reads the last `cycle_digest` event and re-spawns workers at `--resume <stage_id>`, skipping full re-diagnosis unless the last recorded stage was `initial_diagnostics` or `pre_flight`.

**Per-turn event** (one per `<task-notification>` received):

```json
{
  "event": "subagent_report",
  "cycle_id": 7,
  "recorded_at": "2026-05-09T14:32:11Z",
  "train": {"train_number": "4736-104", "fzg": 132, "ccu_ip": "10.179.10.1"},
  "stage_id": "push_switch_config",
  "status": "PUSHING_TO_DEVICES",
  "elapsed_seconds": 1980,
  "current_step": 7,
  "total_steps": 18,
  "issues_count": 0,
  "report_hash": "sha256:<first-8-chars-of-sha256-of-raw-report-JSON>",
  "ssh_flap_count": 0,
  "paused_seconds_total": 0
}
```

**Cycle digest event** (one per cycle boundary):

```json
{
  "event": "cycle_digest",
  "cycle_id": 7,
  "recorded_at": "2026-05-09T14:35:00Z",
  "elapsed_minutes": 35,
  "per_train": [
    {
      "fzg": 132,
      "status": "DONE",
      "stage_id": "done",
      "ssh_flap_count": 0,
      "paused_seconds_total": 0,
      "issues": []
    },
    {
      "fzg": 130,
      "status": "APPLYING_FIXES",
      "stage_id": "apply_obn_patches",
      "elapsed_stage_seconds": 220,
      "expected_stage_seconds": 120,
      "over_budget": true,
      "ssh_flap_count": 1,
      "paused_seconds_total": 60,
      "issues": [{"severity": "warning", "description": "bug 6 marker still missing"}]
    }
  ],
  "gates_approved": 3,
  "gates_denied": 0,
  "gates_deferred": 0,
  "gates_auto_blocked": 0,
  "fleet_status_changed": true,
  "confluence_pushed": true
}
```

**`report_hash`** is `sha256(raw_json_string)[:8]` — cheap fingerprint for deduplication on crash replay. If two consecutive per-turn events share the same `(fzg, stage_id, report_hash)`, skip the second write.

**Crash recovery:** on re-invoke, read the last `cycle_digest` event to determine which trains were in-flight and at which stage, then spawn fresh workers with `--resume <stage_id>`. Defer counter state is NOT recoverable from `orchestrator.jsonl` — defer counters reset on session restart, which is the correct behaviour (a new session is a fresh chance to approve).

## End of day

When every worker has reached terminal state:

1. Final cycle digest with the day's totals: trains commissioned, gates approved/denied, blockers, elapsed time.
2. Final `fleet-status.md` write.
3. Final Confluence push (with banner reflecting the day's last-sync timestamp).
4. **Per-train success-criteria check (Principle 4 — Goal-Driven Execution).** Recall the success criteria you committed to in your Pre-Flight at startup. For each train, verify each criterion against the latest fleet-status row + the worker's terminal report + on-disk artefacts. Tick what passed, ✗ what didn't. Don't claim DONE without ticking every criterion you committed to.

   ```
   ─── Day complete — 2026-05-09 18:42 UTC (elapsed 04:12) ───
   Engineer:  Abbas Rizvi
   Trains:    3 spawned · 2 DONE · 1 BLOCKED · 0 ERROR
   Gates:     7 approved · 0 denied · 0 deferred

   ▼ 4736-102 / Fzg 130 — DONE
     ✓ OBN patches 8/8 persisted (run5)
     ✓ train_id = 130 hardcoded in all 18 nv6-*.cfg
     ✓ vlan7 = 172.19.193.2/17 (live + persisted)
     ✓ All 18 switches at target firmware + config
     ✓ All 24 APs at target firmware
     ✓ Customer report: reports/customer/OBB_Fzg130_v1.0.docx

   ▼ 4736-104 / Fzg 132 — DONE w/ Stadler
     ✓ OBN patches 8/8 persisted (run1)
     ✓ All 23 visible APs at target firmware 6.11.2-0
     ✗ All 24 APs at target — D4 still missing (Stadler item, register #5)
     ✓ vlan7 reachable to Stadler FW (commissioned per F9: ICMP filtered)
     ✓ Customer report: reports/customer/OBB_Fzg132_v1.0.docx

   ▼ 4736-120 / Fzg 148 — BLOCKED
     ✓ OBN patches 8/8 persisted
     ✗ Switch config push completed — RSTP convergence failed on F2
     ✗ Customer report — pipeline halted before stage 21
     Next: investigate F2 (10.179.2.189) — see issues[] in last worker report

   Reports filed:  2 (4736-102, 4736-104)
   Blockers open:  4736-104 — Stadler register #5 (D4 cable)
                   4736-120 — F2 RSTP, internal investigation needed

   fleet-status.md updated · Confluence v52
   ```

   Rules:
   - One ✓ or ✗ per criterion you stated at Pre-Flight.
   - "DONE" means every criterion ticked. Any ✗ → `DONE w/ <caveat>` or `BLOCKED`, never plain `DONE`.
   - If a criterion can't be checked (e.g. "L2 health clean" but worker didn't reach that stage), report `?` and surface as an open item.

5. Engineer can re-invoke `/dosto-orchestrate` tomorrow with a new train list.

## Crash recovery

If the engineer's session crashes mid-day:
- All running workers die with it (workers are spawned from this session).
- Engineer re-invokes `/dosto-orchestrate` with the same train list.
- The skill reads `fleet-status.md` for current state, reads `.claude/logs/orchestrator.jsonl` last entry to know which trains were in flight.
- Asks the engineer: "Resume 4736-102 / 4736-104 / 4736-120 with `--resume`? [Y/n]"
- On Y, spawns fresh workers for each, each invoking `/dosto-commission-train --resume <last_known_stage_id>` per train. The skill's `--resume` always re-runs `initial_diagnostics` so state drift since the crash is detected.

This is lossless because:
- All persistent state lives on the CCU (btrfs snapshots, applied patches).
- The skill recovers from CCU state every resume.
- The orchestrator-as-sole-writer pattern means no fleet-status / Confluence writes are mid-flight at crash time.

## Engineer mid-run controls

While the runtime loop is active, the engineer can:
- **Type approval responses** (`y` / `n` / `w` / `p` / `c` / `defer` / `?`) when prompts appear
- **Hand-edit `fleet-status.md`** fields the skill doesn't manage (Customer report, Health check date, etc.) — these survive every cycle write per Surgical-Changes
- **Type "status"** any time for a current per-train one-line summary (one of the cheap operations — does NOT wake any worker; reads from in-memory state)
- **Type "abort"** to halt the day cleanly (`SendMessage` shutdown to all workers, no fleet-status writes, exit skill)

## Failure handling — runtime-side

| Situation | Action |
|---|---|
| Worker emits malformed JSON | Log to `orchestrator-errors.jsonl`. Treat that report as `ERROR`. Don't kill the worker — wait for next report; it may recover. After 3 consecutive malformed reports, `SendMessage` shutdown_request and surface to engineer. |
| Worker goes silent > 30 min | Treat as `PAUSED`. Surface in next digest. After 60 min silent, kill and surface as `BLOCKED`. |
| Worker emits `PAUSED` (SSH timeout) | Increment `ssh_flap_count` for that train in in-memory state. After **3 consecutive `PAUSED` reports on the same stage** (train kept dropping before completing the stage), emit inline immediately: `⚠️  Fzg <NN> — 3 consecutive SSH flaps on <stage_id>. Consider switching to --legacy-serial-sw-config or deferring this train. [k=keep running / s=suggest serial / d=defer train]`. Log `ssh_flap_count` and `paused_seconds_total` in the per-turn `orchestrator.jsonl` event. Accumulated per-train `ssh_flap_count` across the session is surfaced in the cycle digest and end-of-day summary. |
| Confluence push fails | Log to `confluence-sync.jsonl`. Surface in next digest. Local file remains source of truth. Retry on next push trigger. |
| Drift detected on Confluence | Halt the push. Surface to engineer. Ask whether to `--force` or pull-then-push. |
| Engineer types nonsense in approval prompt | Treat per contract: binary → deny + warning, three-way → partial + warning. Re-show with `(treating as denied; type 'y' to override)` hint. |
| Two trains reconciled to the same CCU IP | This is an engineer-input bug. Halt before spawning. Don't spawn anything until conflict resolved. |
| Train list > 8 concurrent | Spawn anyway per the engineer's spec — but warn at startup: "Spawning N concurrent workers; train cellular SSH-flap rate may degrade. Continue? [y/N]" |

## Validation rules (run before spawning anything)

| Rule | Failure action |
|---|---|
| At least one train specified | Halt: "No trains supplied. Pass `fzg=NN@<ip>[,NN@<ip>,...]` or `trains=NNN@<ip>[,...]`." |
| Every Fzg/train token has a `@<ip>` suffix | Halt with usage error per Step 1. |
| Every supplied IP is syntactically valid IPv4 | Halt: "Fzg <NN>: '<bad_ip>' is not a valid IPv4 address." |
| Every train resolves to a known Fzg+train_number+CCU IP after Step 2 reconcile | Engineer aborted at a Case B/D prompt → exit cleanly with no spawns. |
| No duplicate Fzg in the list | Halt: "Fzg <NN> appears twice in the train list." |
| No two trains share a CCU IP (after reconcile) | Halt: "Fzg <NN> and Fzg <MM> both reconciled to CCU IP <ip>. Check fleet-status and your input." |
| `cycle_minutes` ∈ [1, 30] | Clamp silently with a warning. |
| For each `Status: DONE` train, engineer confirmed inclusion | Per Step 2 prompt. |

## Output

This skill prints human-readable status. It does NOT support `--json` output — there's no orchestrator-of-orchestrators that would consume it. Future Phase 7+ might add a `--json` mode if a higher-level driver gets built.

## What this skill deliberately does NOT do

- ❌ **Run CCU commands directly.** All CCU work goes through workers → per-device skills. The skill (and the engineer's session running it) NEVER SSHes to a CCU.
- ❌ **Auto-approve a gate.** Even on a third-time-this-day same-gate, ask. The 30-second cost is the feature.
- ❌ **Batch approvals into one prompt.** Sequential per the `approval-gates.md` v2 contract.
- ❌ **Skip the Confluence push on a gate hit or terminal state.** Those are the moments the team most wants visibility.
- ❌ **Write to `fleet-status.md` more than once per cycle.** Atomic batched writes only.
- ❌ **Spawn workers serially "for safety."** Engineer chose parallel; honour it via a single multi-block `Agent` call.
- ❌ **Hold an open SSH session to any CCU.** Workers do that, and they should be short-lived.
- ❌ **Call `Skill: dosto-commission-train` directly.** That's the per-train worker's job; you spawn the worker which calls the skill.
- ❌ **Push to Confluence without going through `dosto-confluence-sync`.** That skill owns drift detection and logging.
- ❌ **Modify worker, contract, skill, or agent files.** Skill body is the engineer-driven runtime; don't self-modify the workflow.

**`fleet-status.md` write boundaries:**

- **During Step 2 reconciliation:** writes ONLY to the cells the skill owns (CCU IP for Cases B/C; full new row for Case D). Single-shot, before any worker spawn.
- **During the runtime cycle loop:** writes to the eight Surgical-Changes columns listed in the writer section, once per cycle, batched. Engineer hand-edits to any other column survive every cycle.

## Edge cases

- 🟡 **Engineer passes a single train.** Skill works fine — orchestrator with one subagent is just a fancy wrapper. Suggest using `/dosto-commission-train` directly for single-train work, but don't refuse.
- 🟡 **Engineer passes >8 trains.** Spawn anyway, but warn at the plan step about cellular SSH-flap rate degrading at high concurrency.
- 🟡 **Mixed series in one day.** 4734, 4736, 4705, and 4706 in the same train list is fine — the orchestrator handles per-train consist correctly.
- 🟡 **Engineer passes the same train twice.** Caught at validation; halt.
- 🟡 **Train list with all `DONE` trains.** All fail the include-anyway prompt → effective abort. Skill exits cleanly.
- 🟡 **`fleet-status.md` doesn't exist or is unreadable.** Halt with a clear file-not-found error. The orchestrator can't operate without the source file.
- 🟡 **Engineer omits `@<ip>` for one Fzg in a list.** Halt at parse time per Step 1. Don't try to half-resolve from fleet-status — the contract is that IP is required for every Fzg.
- 🟡 **Engineer types an IP that doesn't ping.** Caught at Step 5.5 network pre-flight (added 2026-05-20) — the TCP/22 probe + device-discovery happens before any worker spawns, and unreachable CCUs land in the FAIL list with a consolidated engineer prompt rather than blocking individual subagents at their Stage 1.
- 🟡 **Two engineers reconciling the same train file simultaneously.** Skill reads + edits + writes `fleet-status.md` non-atomically. Two `/dosto-orchestrate` invocations racing on the same file CAN drop one engineer's edit. Mitigation: this is a one-engineer-per-day workflow by convention; if multiple engineers are working in parallel, coordinate verbally before invoking.
- 🟡 **Case D row creation lands the new row in the wrong series section.** Skill must write under the right `### 4734 series` / `### 4736 series` / `### 4705 series` / `### 4706 series` header. If the file structure has been modified (new sections, renamed headers), the safest fall-back is to halt with a clear error rather than guess where to insert.

## Pairs with

- [`.claude/agents/dosto-train-worker.md`](../../agents/dosto-train-worker.md) — what this skill spawns (N parallel per fleet day)
- [`.claude/skills/dosto-confluence-sync/SKILL.md`](../dosto-confluence-sync/SKILL.md) — what this skill calls for Confluence push
- [`.claude/skills/dosto-commission-train/SKILL.md`](../dosto-commission-train/SKILL.md) — what the per-train worker invokes
- [`fleet-status.md`](../../../fleet-status.md) — the source-of-truth file (sole writer during runtime)
- [`cable-issues-register.md`](../../../cable-issues-register.md) — read at Step 3.5 (pre-flight); appended at Step 7.5 (new fault auto-append)
- All four contracts in `.claude/contracts/` — `subagent-report.md` v2, `autonomy-boundary.md`, `approval-gates.md` v2, `confluence-sync.md`

## Reference / design history

- handoff line 30: "Phase 5 top-level orchestrator (the thing that spawns N per-train subagents in parallel and aggregates)" — this skill closes that gap.
- **2026-05-09 design decisions** (initial v1 architecture):
  - Architecture: agent definition + bootstrap skill (option b)
  - Concurrency: parallel-all
  - Cycle: 5-min digest
  - Fleet-status: batched writes per cycle
  - Confluence: push on gates + terminal states + cycle digests
  - Approvals: print prompt, end turn, parse next user message
  - Crash recovery: workers die with orchestrator; restart re-spawns with `--resume`
- **2026-05-11 v2 redesign (audit finding F5):**
  - The 2026-05-09 architecture was invalidated by the Claude Code platform rule "subagents cannot spawn further subagents." A `dosto-orchestrator` agent spawned via `Agent` could not itself call `Agent` to spawn workers.
  - The first-run test on 2026-05-11 worked end-to-end only because the engineer's top-level session played the orchestrator role directly (it has `Agent` + `SendMessage`).
  - This skill was rewritten to make that pattern the documented architecture: the orchestration logic runs *inline in the engineer's top-level session*, spawning workers from that session's tool access.
  - `.claude/agents/dosto-orchestrator.md` was deleted as part of this change. All operational detail folded into this skill body.
  - See [`handoff-bootstrap-audit-2026-05-11.md`](../../../handoff-bootstrap-audit-2026-05-11.md) §F5 for the full rationale and Option A vs B comparison.
