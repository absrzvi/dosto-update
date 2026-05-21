---
name: dosto-orchestrate
description: Run a fleet-day commissioning orchestration inline in the engineer's top-level session. Use when starting a multi-train commissioning day, when the engineer says "/dosto-orchestrate fzg=...", or when fanning out commissioning across two or more trains in parallel. Engineer invokes this skill with a list of trains; the skill validates each train against fleet-status.md and the per-series Fzg formulas, emits an input-validation pre-flight block, runs a network-level pre-flight diagnostic (CCU reachability + full expected device count via dosto-device-discovery, in parallel across trains, gated on a single consolidated engineer prompt), then runs the orchestration in-line in the engineer's session — spawning N parallel dosto-train-worker subagents for the trains that passed pre-flight, surfacing approval gates one at a time, batching fleet-status writes per cycle, and pushing Confluence on gates/terminals/digests. The engineer's top-level session IS the orchestrator (per audit finding F5, 2026-05-11 — the platform doesn't allow agents-spawning-agents, so the skill became inline instead of bootstrapping a separate orchestrator agent).
---

# DOSTO Orchestrate

This skill is the engineer's entry point for a multi-train commissioning day. It runs **inline in the engineer's top-level Claude session** — the engineer's session IS the orchestrator. The skill (a) parses + validates the train list, (b) emits a pre-flight block for engineer approval, (c) spawns N `dosto-train-worker` subagents in parallel from the engineer's session, (d) drives the cycle loop (gate prompts, fleet-status writes, Confluence pushes) until every train reaches a terminal state.

**Why inline rather than agent-as-orchestrator** (per audit F5, 2026-05-11): the platform rule "subagents cannot spawn further subagents" means a `dosto-orchestrator` agent spawned via `Agent(subagent_type: ...)` cannot itself call `Agent` to spawn workers. The 2026-05-11 first-run test confirmed this. So the orchestration logic now lives in this skill, executed by the engineer's top-level session (which DOES have `Agent` + `SendMessage`). The `dosto-orchestrator.md` agent definition has been retired.

## When to use

- **Start of a multi-train commissioning day.** Engineer types `/dosto-orchestrate <trains>` to kick off the day's run.
- **One per fleet-day.** The skill runs for the duration of the day in the engineer's session — they're orchestrating from the same chat thread. If the session crashes or ends, re-invoke this skill with the same args and it offers `--resume` per train (resume state is on disk: `fleet-status.md`, `.claude/logs/orchestrator.jsonl`, and each CCU's btrfs snapshots).
- **NOT for single-train debug runs.** Engineers debugging one train should invoke `/dosto-commission-train` directly (no subagent, no orchestration overhead).

## Inputs

The skill accepts a flexible argument string. CCU IPs can be supplied with `@<ip>` or omitted — when omitted, the skill auto-resolves from `fleet-status.md` with a one-line confirmation per train. Common forms:

```
/dosto-orchestrate fzg=139,147,148,19,21                                # auto-resolve IPs from fleet-status
/dosto-orchestrate fzg=130@10.179.47.1,132@10.179.10.1,148@10.179.2.1   # explicit IPs (typo-catch mode)
/dosto-orchestrate fzg=139,147@10.179.12.1                              # mixed: 139 auto-resolved, 147 explicit
/dosto-orchestrate trains=4736-102,4736-104                             # train numbers, IPs auto-resolved
/dosto-orchestrate fzg=130,132 dry-run
/dosto-orchestrate fzg=130,132 cycle=3
```

Recognised tokens:

| Token | Meaning |
|---|---|
| `fzg=NN[@<ip>]` or `fzg=NN[@<ip>],NN[@<ip>],...` | Fzg ID list. `@<ip>` is optional — when omitted the skill looks up the CCU IP from `fleet-status.md` and emits a one-line confirmation (Case E in Step 2). The skill resolves `train_number` and `consist` from the file. |
| `trains=NNN[@<ip>],...` or `trains=4736-102[@<ip>],...` | Alternative form: train numbers + optional CCU IPs. Skill computes Fzg via per-series formula. |
| `dry-run` | Pass `--dry-run` to all subagents. Read-only; every per-device skill runs in `--prepare` mode. |
| `cycle=N` | Override default 5-min digest cadence. Range 1-30 (clamped). |
| `no-confluence` | Skip Confluence pushes for this run (rare — local-only mode). |
| `engineer=NAME` | Override the auto-detected engineer name. Used in fleet-status `Last touched` and Confluence banner. |

**Why `@<ip>` remains supported as opt-in:** trains move in and out of service, CCUs get re-imaged, and stale `fleet-status.md` rows have caused incorrect-target outages in past sessions. The explicit-IP form is the typo-catch / drift-catch mode — use it when you've just re-imaged a CCU or when you're not confident fleet-status is current. The auto-resolve form (no `@<ip>`) is the common case for a returning engineer whose fleet-status rows are already filed correctly; Case E below adds a per-train confirmation that keeps the same safety property with far less typing.

## Procedure

### Step 1 — Parse and normalise the train list

Tokenise the argument string. Each `fzg=` / `trains=` token MAY include `@<ip>` (explicit IP) or omit it (auto-resolve from fleet-status in Step 2 Case E). When `@<ip>` is present, validate it's a syntactically valid IPv4 address (four dotted octets, each 0-255). Reject malformed IPs at parse time — don't wait until reconciliation.

For `trains=` form, compute the Fzg via per-series formula:

| Series | Formula |
|---|---|
| 4734-NNN | `Fzg = NNN - 100` |
| 4736-NNN | `Fzg = NNN + 28` |

Reject any train number that doesn't match these series (4705 / 4706 are out of scope per CLAUDE.md).

If the engineer supplied both `fzg=` and `trains=`, validate they agree on **both** Fzg and (where both are explicit) IP per train. Mismatches halt the skill — typo guard.

The result of this step is a list of `(fzg, supplied_ip_or_none)` tuples. Step 2 reconciles them with `fleet-status.md`.

### Step 2 — Reconcile each (Fzg, IP) against `fleet-status.md`

This is the IP-reconciliation pass. For each `(fzg, supplied_ip_or_none)`:

1. Look up the Fzg row in `fleet-status.md`.
2. **If `supplied_ip` is None** (engineer omitted `@<ip>`), branch to Case E first.
3. Otherwise, branch on what's there (Cases A-D).

**Case A — Row exists, CCU IP recorded, matches `supplied_ip`:** ✅ Proceed silently. Track `ip_source = "fleet-status (matched)"` for the plan summary.

**Case B — Row exists, CCU IP recorded, disagrees with `supplied_ip`:** ⚠️ Stop and prompt the engineer interactively:

```
⚠️ Fzg <NN> CCU IP mismatch.
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

**Case D — No row exists for this Fzg:** ⚠️ Stop and prompt the engineer interactively:

```
⚠️ Fzg <NN> has no row in fleet-status.md.
   Train#:     <train_number>   (computed from per-series formula)
   CCU IP:     <supplied_ip>    (your input)
   Series:     <4734 / 4736>    (consist: <4-car / 6-car>)

Options:
  [c] Create a fresh row in fleet-status.md and proceed
       (Status: NOT STARTED, all v8 columns ⬜/❓ except CCU IP)
  [a] Abort the whole day's plan

Choice [c/a]:
```

- `c` → append a new row to the appropriate series section (4736 or 4734), populate Fzg, Train#, CCU IP, set Status=`NOT STARTED`, all other columns = `⬜` or `❓` per the legend, set `Last touched = <today> <engineer initials>`. Mark `ip_source = "supplied (new row created)"`. Then proceed.
- `a` → exit cleanly.

**Case E — Engineer omitted `@<ip>`, auto-resolve from fleet-status:**

| Fleet-status state | Action |
|---|---|
| Row exists with non-`❓` CCU IP | Use that IP. Emit one-line confirmation: `ℹ️  Fzg <NN>: using IP <fleet_ip> from fleet-status (no @<ip> supplied) — correct? [Y/n]` Default Y. Engineer types `n` → halt with usage error asking for explicit `@<ip>`. Mark `ip_source = "fleet-status (auto-resolved)"`. |
| Row exists with `❓` CCU IP | Halt: `ERROR: Fzg <NN> has no IP recorded in fleet-status — supply explicitly with fzg=<NN>@<ip>`. Cannot proceed without an IP. |
| No row exists for this Fzg | Halt: `ERROR: Fzg <NN> has no row in fleet-status — supply IP explicitly with fzg=<NN>@<ip> to create the row.` (Drops the engineer into Case D's `[c]/[a]` prompt on retry.) |

When multiple trains need confirmation, batch the prompt into a single block:

```
ℹ️  Auto-resolved IPs from fleet-status:
    Fzg 139 → 10.179.24.1   (last touched 2026-05-21 AR)
    Fzg 147 → 10.179.12.1   (last touched 2026-05-21 AR)
    Fzg 19  → 10.179.45.1   (last touched 2026-05-21 AR)
Proceed with these? [Y/n]:
```

Default Y. Engineer types `n` → halt and ask for explicit `@<ip>` on next invocation.

**After the reconcile loop**, build the full per-train spec:

| Field | Source |
|---|---|
| `fzg` | from input |
| `train_number` | from `fleet-status.md` row (now guaranteed to exist) |
| `ccu_ip` | from reconciled value (Case A/B/C/D logic above) |
| `consist` | infer from series — `nv6 → 6-car`, `nv4 → 4-car` |
| `ip_source` | tracked per case above, used in Step 4 plan summary |

**Status: DONE** trains get a context-aware prompt — read the train's `Next action` column from fleet-status first, then branch:

**Sub-case DONE-1 — Customer-report-only remaining** (Next action contains `customer report only` / `report v1` / `generate_report`):

```
⚠️ Fzg <NN> is DONE but has Customer report: ⬜.
   Next action per fleet-status: <next_action_text>
   Including will run report generation only (skip stages 1-19, run stage 20).

Options:
  [Y] Include for report generation
  [s] Skip
  [a] Abort

Choice [Y/s/a]:
```

Default Y — generating a report on a healthy train is the obvious next step.

**Sub-case DONE-2 — Other outstanding items** (Next action contains anything else — e.g. "wait for Stadler", "verify .231"):

```
⚠️ Fzg <NN> is DONE but has outstanding work: <next_action_text>
   Including will re-validate state via the full 19-stage pipeline.

Options:
  [s] Skip this train
  [i] Include anyway
  [a] Abort

Choice [s/i/a]:
```

**Sub-case DONE-3 — No outstanding work** (Next action is empty or `—`):

```
⚠️ Fzg <NN> is already DONE with no outstanding work in fleet-status.
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
    Fzg <X> (current resolve, at-a-glance row)
    Fzg <Y> detail block header
Confirm which train owns this IP before proceeding.
  [x] Use Fzg <X>, treat Fzg <Y> detail block as stale (engineer cleans up later)
  [y] Use Fzg <Y> instead (re-prompt at Step 2 for Fzg <X>)
  [a] Abort
```

This catches reconciliation drift between at-a-glance rows and detail blocks at reconcile time, not after a worker has been spawned. Confirmed engineer-visible during 2026-05-21 (`10.179.12.1` listed for both Fzg 140 detail block and Fzg 147 at-a-glance row).

**Pending-section cleanup** (post-reconcile, after each train's IP is confirmed): check the `## Pending Fzg assignment` section. If the resolved `ccu_ip` appears in that table, remove that row from Pending (surgical: delete only that one row, preserve all others). Print a one-line note:

```
ℹ️  Removed 10.179.45.1 from Pending Fzg assignment section (now confirmed to Fzg 19).
```

This is housekeeping for the morning-brief discovery sweep — once an IP is confirmed assigned, the Pending row is stale.

### Step 3 — Build the train list array

```json
{
  "trains": [
    {"fzg": 130, "train_number": "4736-102", "ccu_ip": "10.179.47.1", "consist": "6-car"},
    {"fzg": 132, "train_number": "4736-104", "ccu_ip": "10.179.10.1", "consist": "6-car"},
    {"fzg": 148, "train_number": "4736-120", "ccu_ip": "10.179.2.1", "consist": "6-car"}
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

### Step 4 — Print the plan and confirm

Show the engineer a summary before spawning anything:

```
─── DOSTO Orchestrate — fleet day plan ─────────────
Engineer:    Abbas Rizvi
Cycle:       5 min digest
Dry run:     no
Confluence:  push enabled (page 5410684933)

Trains to commission (3 — all in parallel):
  • Fzg 130 / 4736-102 / 10.179.47.1 / 6-car
    IP source:     fleet-status (matched)
    Current state: PAUSED — apply patches + persist + fix train_id template + fix vlan7 — see notes
    Last touched:  2026-05-09 AR
  • Fzg 132 / 4736-104 / 10.179.10.1 / 6-car
    IP source:     supplied (fleet-status updated — was 10.179.10.99)
    Current state: BLOCKED w/ Stadler (D4) + 6 APs stuck — push remaining 3 APs (.237 .238 .240), verify .231
    Last touched:  2026-05-09 AR
  • Fzg 148 / 4736-120 / 10.179.2.1 / 6-car
    IP source:     supplied (filled in fleet-status — was ❓)
    Current state: PAUSED — sudo obn discover && sudo obn update c all
    Last touched:  2026-05-04 AR

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
  • Fzg 130 / 4736-102 / 10.179.47.1 / 6-car
    Current state: PAUSED — apply patches + persist + fix train_id template + fix vlan7
  • Fzg 132 / 4736-104 / 10.179.10.1 / 6-car
    Current state: BLOCKED w/ Stadler — 6 APs stuck (.237 .240 .238 .231 .230 .226)
  • Fzg 148 / 4736-120 / 10.179.2.1 / 6-car
    Current state: PAUSED — sudo obn discover && sudo obn update c all

▼ Assumptions (specific, disprovable):
  • fleet-status.md rows are current as of last engineer save
  • Each CCU is reachable via the project key at the IPs listed above
  • The Atlassian Confluence MCP connector is configured and working
  • The TFTP CT helper runtime fix (if previously applied) does NOT survive
    a CCU reboot — first stage of each subagent will re-check and re-apply if needed

▼ Open questions: <none / list them here>

▼ Simplicity check:
  Spawning N parallel subagents per the contract. No batching, no custom
  ordering. Each subagent runs the canonical 19-stage pipeline.

▼ Per-train success criteria (will be checked at end of day):
  Fzg 130: 8/8 OBN persisted, train_id=130 hardcoded, vlan7=172.19.193.2,
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

Soft-warn is for plausible-timing shortfalls (AP mid-reboot, DHCP not yet renewed). Hard-FAIL is for genuinely-can't-proceed states (cable fault, CCU offline, coach powered off). The distinction was added 2026-05-21 after Fzg 147 (1 AP missing) and Fzg 148 (1 sw + 2 APs absent) were over-classified as FAIL alongside genuine unreachables.

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
  ✅ Fzg 143 / 4736-115 / 10.179.18.1 — 18/18 sw + 24/24 AP visible — scripts staged
  ✅ Fzg 144 / 4736-116 / 10.179.16.1 — 18/18 sw + 24/24 AP visible — scripts staged

Soft-warn (will dispatch with note — Gate 5 may fire in Stage 2 if count doesn't improve):
  🟡 Fzg 147 / 4736-119 / 10.179.12.1 — 18/18 sw + 23/24 AP — 1 AP plausibly mid-reboot — scripts staged
  🟡 Fzg 148 / 4736-120 / 10.179.2.1 — 17/18 sw + 22/24 AP — E3 coach + 2 APs absent — scripts staged

Hard-FAIL (will NOT dispatch):
  🔴 Fzg 132 / 4736-104 / 10.179.10.1 — 18/18 sw + 21/24 AP — 3 APs missing (>20% threshold)
  🔴 Fzg 9   / 4734-109 / 10.179.38.1 — UNREACHABLE on TCP/22
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

### Step 6 — Spawn all train-worker subagents in parallel

Use the `Agent` tool with one tool-use block per train, **all in a single message** so the harness runs them concurrently. Each gets:

- `subagent_type: "dosto-train-worker"`
- `name: "train-fzg-<NN>"` (so you can `SendMessage` it later)
- `description: "DOSTO per-train worker for Fzg <NN>"`
- `prompt`: **pointer-not-dump** per the F2 contract — pass Fzg ID, CCU IP, consist, engineer name, dry-run flag, ip_source, `scripts_staged: true/false` (from Step 5.5 staging result — tells the worker whether `/var/tmp/fix_obn*.py` is guaranteed present or whether it must request the orchestrator to SCP), and nothing else. The worker reads `fleet-status.md`, `fleet-journal.md`, the four contracts, and the per-device skills itself. Do NOT inline per-train prose, recovery sequences, or historical context — those bloat the worker's context window for its entire lifetime.

After spawning, **start the cycle clock**. Cycle 1 runs for `cycle_minutes` (default 5).

## Runtime — the cycle loop

After Step 6, you (the engineer's session) are now the running orchestrator. The skill body from here is the cycle loop, executed turn-by-turn as workers report back via `<task-notification>` events.

### Per cycle (default 5 min wall-clock; not strictly time-bounded — cycles end at terminal-state convergence or engineer abort)

1. **Listen for subagent notifications.** When a `<task-notification>` arrives:
   a. Validate the JSON payload is shaped per `.claude/contracts/subagent-report.md` (v2). Accept `schema_version: "1"` with a `schema_version_drift` flag; reject anything else as `ERROR` and log to `.claude/logs/orchestrator-errors.jsonl`.
   b. Branch on `status`:
      - `NEEDS_APPROVAL` → **immediately** surface the gate prompt to the engineer per `.claude/contracts/approval-gates.md` v2 (compact form, expandable on `?`). Don't wait for cycle end.
      - `DONE` / `BLOCKED` / `ERROR` → **immediately** push Confluence via `Skill: dosto-confluence-sync --push --json`. Stage out the worker for the end-of-cycle digest.
      - `DIAGNOSING` / `APPLYING_FIXES` / `PUSHING_TO_DEVICES` / `PAUSED` → buffer in your in-memory per-train state. No immediate action.
   c. Update in-memory per-train state: latest report, latest stage, latest fields (per the F2 contract, you only see *current-stage* `skill_outputs`; you maintain the audit trail externally via the log).

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

Fzg 130 / 4736-102: 🟡 APPLYING_FIXES (apply_obn_patches, t+220s, exp 120s — over budget, watch)
  • Bug 5 patch applied; bug 6 marker still missing — investigating
  • OBN patches: 7/8 (was 0/8)

Fzg 132 / 4736-104: ✅ DONE (t+34:12)
  • All 6 stuck APs unblocked: .226 .230 .231 .237 .238 .240 → 6.11.2-0
  • Final L2 health: clean (1 known cable issue: D4 missing — Stadler item)
  • Customer report: reports/customer/OBB_Fzg132_v1.0.docx

Fzg 148 / 4736-120: 🔵 NEEDS_APPROVAL (await_obn_update_c — queued 12 min, see prompt below)

────────────────────────────────────────────────────
Approvals queued: 1   Blocked: 0   Errors: 0   Done: 1   Working: 1
⚠️  Approvals waiting > 10 min: 1 (Fzg 148, await_obn_update_c, 12 min)
Confluence push: queued for end of cycle.
fleet-status.md: 2 rows updated (132, 148).
```

**Pending-approval visibility rule:** for every approval in the queue at digest time, compute `now - <queued_at>`. If any single approval > 10 min, emit `⚠️  Approvals waiting > 10 min: N (Fzg X, gate Y, Z min)` after the totals line. Engineers stepping away from the keyboard then notice on return that they have unanswered acks blocking work.

If multiple approvals are over threshold, list them comma-separated. Don't truncate.

## Approval flow

When a worker emits `status: NEEDS_APPROVAL`:

1. **Buffer immediately** in `pending_approvals`. Don't wait for cycle end.
2. **At the next safe boundary** (between notification handles, or right after a cycle digest), surface the next pending approval to the engineer in the compact form per `approval-gates.md` v2:

   ```
   [Gate 1] promote_snapshot — Fzg 132 — 8/8 OBN patches confirmed; persisting via chroot promote
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
4. Update `Status` to the most informative current value:
   - Worker terminal `DONE` → `DONE` (or `DONE w/ Stadler` if any `BLOCKED` issues remain — infer from `issues[]`)
   - Worker terminal `BLOCKED` → `BLOCKED`
   - Worker terminal `ERROR` → keep prior `Status`, add note in per-train detail block
   - Worker in `NEEDS_APPROVAL` → keep prior `Status` (transient state, not worth pushing to fleet-status)
   - Worker in working state → `IN PROGRESS`
   - Worker in `PAUSED` → `PAUSED`
5. Update `Next action` to the worker's last reported `next_action`, or compute from terminal state.

**Hand-edit preservation:** if between cycles the engineer hand-edits fields you don't manage (`Customer report`, `Health check date`), preserve them. Only overwrite the columns in the `fields` block.

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

Three append-only files in `.claude/logs/`:

| File | One entry per |
|---|---|
| `orchestrator.jsonl` | Cycle digest. Includes per-train snapshot + cycle metadata. |
| `approval-gates.jsonl` | Each gate decision (approved / denied / deferred / wait / partial / continue_full). |
| `orchestrator-errors.jsonl` | Each schema-version mismatch, malformed JSON, or contract violation. |

Existing files: `confluence-sync.jsonl` and `confluence-drift.jsonl` (both managed by the sync skill).

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

   ▼ Fzg 130 / 4736-102 — DONE
     ✓ OBN patches 8/8 persisted (run5)
     ✓ train_id = 130 hardcoded in all 18 nv6-*.cfg
     ✓ vlan7 = 172.19.193.2/17 (live + persisted)
     ✓ All 18 switches at target firmware + config
     ✓ All 24 APs at target firmware
     ✓ Customer report: reports/customer/OBB_Fzg130_v1.0.docx

   ▼ Fzg 132 / 4736-104 — DONE w/ Stadler
     ✓ OBN patches 8/8 persisted (run1)
     ✓ All 23 visible APs at target firmware 6.11.2-0
     ✗ All 24 APs at target — D4 still missing (Stadler item, register #5)
     ✓ vlan7 reachable to Stadler FW (commissioned per F9: ICMP filtered)
     ✓ Customer report: reports/customer/OBB_Fzg132_v1.0.docx

   ▼ Fzg 148 / 4736-120 — BLOCKED
     ✓ OBN patches 8/8 persisted
     ✗ Switch config push completed — RSTP convergence failed on F2
     ✗ Customer report — pipeline halted before stage 21
     Next: investigate F2 (10.179.2.189) — see issues[] in last worker report

   Reports filed:  2 (Fzg 130, Fzg 132)
   Blockers open:  Fzg 132 — Stadler register #5 (D4 cable)
                   Fzg 148 — F2 RSTP, internal investigation needed

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
- Asks the engineer: "Resume Fzg 130 / 132 / 148 with `--resume`? [Y/n]"
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
- 🟡 **Mixed series in one day.** 4734 and 4736 in the same train list is fine — the orchestrator handles per-train consist correctly.
- 🟡 **Engineer passes the same train twice.** Caught at validation; halt.
- 🟡 **Train list with all `DONE` trains.** All fail the include-anyway prompt → effective abort. Skill exits cleanly.
- 🟡 **`fleet-status.md` doesn't exist or is unreadable.** Halt with a clear file-not-found error. The orchestrator can't operate without the source file.
- 🟡 **Engineer omits `@<ip>` for one Fzg in a list.** Halt at parse time per Step 1. Don't try to half-resolve from fleet-status — the contract is that IP is required for every Fzg.
- 🟡 **Engineer types an IP that doesn't ping.** Caught at Step 5.5 network pre-flight (added 2026-05-20) — the TCP/22 probe + device-discovery happens before any worker spawns, and unreachable CCUs land in the FAIL list with a consolidated engineer prompt rather than blocking individual subagents at their Stage 1.
- 🟡 **Two engineers reconciling the same train file simultaneously.** Skill reads + edits + writes `fleet-status.md` non-atomically. Two `/dosto-orchestrate` invocations racing on the same file CAN drop one engineer's edit. Mitigation: this is a one-engineer-per-day workflow by convention; if multiple engineers are working in parallel, coordinate verbally before invoking.
- 🟡 **Case D row creation lands the new row in the wrong series section.** Skill must write under the right `### 4734 series` / `### 4736 series` header. If the file structure has been modified (new sections, renamed headers), the safest fall-back is to halt with a clear error rather than guess where to insert.

## Pairs with

- [`.claude/agents/dosto-train-worker.md`](../../agents/dosto-train-worker.md) — what this skill spawns (N parallel per fleet day)
- [`.claude/skills/dosto-confluence-sync/SKILL.md`](../dosto-confluence-sync/SKILL.md) — what this skill calls for Confluence push
- [`.claude/skills/dosto-commission-train/SKILL.md`](../dosto-commission-train/SKILL.md) — what the per-train worker invokes
- [`fleet-status.md`](../../../fleet-status.md) — the source-of-truth file (sole writer during runtime)
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
