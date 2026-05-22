---
name: dosto-morning-brief
description: Engineer-morning briefing for the DOSTO fleet — dry-run reachability scan + recommended "start-first" train. Use when the engineer starts their day and wants a single-page view of which trains are online right now, what their next action is, and which one to start with so it runs autonomously while other trains are attended to. Reuses dosto-auto-scan's Tier-1 reachability probe (TCP/22 sweep of known CCU IPs from fleet-status.md), reads each reachable train's Status + Next action, infers a resume stage from the prose, applies the "next ~3 stages contain no approval gate" recommendation rule (tie-break: longest autonomous runway), and renders morning-brief.html in the dashboard.html dark-theme style. Strictly read-only — does NOT invoke /dosto-orchestrate, does NOT edit fleet-status.md, does NOT push to Confluence. Surfaces the would-be orchestrate command for the engineer to paste manually.
---

# DOSTO Morning Brief

A dry-run, read-only morning dashboard. The engineer types `/dosto-morning-brief` over coffee, gets a single-page HTML view of which trains are reachable today, what the next action is per train, and which train the skill recommends starting first — with the rationale surfaced so the engineer can override.

This is the dry-run companion to `/dosto-orchestrate`. It prints the command that *would* be sent, but does not send it.

## What the skill does

1. **Unified reachability sweep** — TCP/22 probe of every `10.179.X.1` for X in 0..255 (256 candidates, parallel, ~15s wall-clock at default timeout). **The sweep is the source of truth for reachability**, not the fleet-status row list. For each responder: if the IP is already in fleet-status (any series), fold its row data into the "reachable" list; if not, surface it as `needs_assignment` (Train# assignment gate — see below). Known IPs that didn't respond become the "unreachable" list. Disable the unknown-IP discovery aspect with `--no-discover` (the full sweep still runs; unknown responders are silently skipped).

1a. **Cable-issues-register read** — after the reachability sweep, read `cable-issues-register.md` once. For each reachable train, grep for open entries matching its Train# or Fzg. Store as `cable_issues[train_number] = [list of open issue summaries]`. This data flows into Step 5 (HTML output) and Step 6 (would-be orchestrate command block).

### Discovered-CCU gate (engineer assignment required)

Why: on an unvisited CCU, the `train_id` rendered into switch hostnames (`nv6-*-v8-NNN`) and into `/etc/obn/template/nv6-*.cfg` filenames is *the value that commissioning fixes*. The broken `128 + train_id` formula, stale Puppet images, or hand-set wrong values mean these names commonly carry the wrong Train#/Fzg pre-commissioning. Trusting them would lock in wrong identifiers before we ever fix them. Authoritative sources for Train# on an unvisited CCU:

- **Cross-reference against `train-ip-allocation-commission/` PDFs** — match CCU IP / box hostname to the per-train allocation PDF (Train# is in the filename + PDF header `Fahrzeugnummer:`)
- **Physical inspection** of the train (Fzg number painted on the carriage — gives Fzg, then engineer derives Train# via per-series formula)

The brief surfaces each discovered IP and prompts the engineer (via the Claude session) for each:

> Discovered new CCU `10.179.17.1` on TCP/22 — not in fleet-status. What is the Train#? (e.g. "4706-103" or "skip")

Engineer responses:
- `<train#>` (e.g. `4706-103`) → Claude calls `python scripts/dosto_morning_brief.py --assign 10.179.17.1 4706-103`. Script inserts a new row into the matching series table with the Train# filled in and Fzg as `❓` (engineer fills the Fzg cell later, when they look up the PDF). If the engineer also knows the Fzg, they can pass it: `--assign 10.179.17.1 4706-103 --fzg 191`.
- `skip` → Claude calls `python scripts/dosto_morning_brief.py --skip 10.179.17.1`. Script appends to a `## Pending Train# assignment` section so the IP isn't re-prompted next morning.

This is NOT a contract gate (no subagent involvement; subagents never see new CCUs). It's a brief-local gate, handled by the Claude session running the skill. The Python script never prompts directly — it just emits the list, and the skill drives prompts via the Claude harness.
2. **Per-train state lookup** — for each reachable Train#, grab the `Fzg`, `Nomad status`, `Stadler status`, and `Next action` cells from the fleet-status row.
3. **Resume-stage inference** — match the `Next action` prose against the canonical 19-stage list in `.claude/contracts/subagent-report.md`. Mapping is opinionated and visible (see "Stage inference rules" below). When uncertain, the resume stage is `?` and the train cannot be recommended as start-first.
4. **Pick start-first** — the train whose next ~3 stages contain NO approval gate. That train can run autonomously while the engineer attends to others. Tie-break: train with the most stages remaining (longest autonomous runway).
5. **Render `morning-brief.html`** — single-file dark-theme HTML, same palette/lozenges/fonts as `dashboard.html` from `gen_dashboard.py`. Includes header, reachable-trains table (with `Recommended?` column + rationale), would-be orchestrate command in a copyable block, and a collapsed `<details>` block listing unreachable trains for context.
6. **Print** the path to the HTML and the would-be orchestrate command.

The skill does **not** invoke `/dosto-orchestrate` and does **not** push to Confluence. It writes `morning-brief.html` at workspace root and (only when the discovery sweep finds a new CCU) appends rows to a dedicated `## Discovered CCUs` section of `fleet-status.md` — never edits existing rows in any series table.

## Inputs

- No arguments. Reads `fleet-status.md` at the workspace root.
- Honours `--timeout <sec>` (default 5) for the TCP/22 probe.

## Stage inference rules (Next action prose → stage ID)

The mapping is keyword-based and opinionated. Order matters — first match wins. The runner script (`scripts/dosto_morning_brief.py`) encodes the table below. When the engineer disagrees with the inferred stage, they should edit the `Next action` prose in `fleet-status.md` to use one of the canonical phrases below.

| If Next action contains (case-insensitive) | Inferred resume stage | Reasoning |
|---|---|---|
| `v3 config` / `v5 config` / `needs v8 push` / `nd-systemupdate ... up` | `ensure_v8_templates` | Stage 2.5 — auto Puppet `up` + reboot, no gate (autonomy-boundary v2). Trains needing v8 templates can run autonomously through this stage. |
| `fix obn template` / `train_id` / `hardcode` | `apply_train_id_fix` | Template formula needs sed loop |
| `vlan7` (and `fix` / `wrong` / `change`) | `apply_vlan7_fix` | nmconnection edit needed |
| `apply obn patches` / `fix_obn.py` / `8/8` (and `apply`) | `apply_obn_patches` | Vanilla CCU, run patcher |
| `reboot` / `safe_reboot` / `activate run` | `await_safe_reboot` | Gate 2 — needs engineer approval |
| `persist` / `chroot` / `promote` / `nd-systemupdate.sh shell` | `await_promote_snapshot` | Gate 1 — needs engineer approval |
| `push config` / `obn update c` / `update c all` | `await_obn_update_c` | Gate 3 — needs engineer approval |
| `push ap fw` / `push ap firmware` / `obn update f` / `6.11.2-0` | `await_obn_update_f` | Gate 4 — needs engineer approval |
| `factory` / `luci` / `RT610LV` | `ap_factory_bypass` | Factory-config bypass needed |
| `initial visit` / `confirm v8 state` | `initial_diagnostics` | Read-only first pass |
| `wait for stadler` / `stadler` | `BLOCKED` | Cannot proceed — Stadler-dependent |
| (no match) | `?` | Engineer review needed |

## Recommendation rule

A train is **recommended as start-first** iff its inferred stage + the next 2 stages in the canonical pipeline contain **no approval gate** (`await_*` stages) **and** the train is not BLOCKED. That means the orchestrator can run those 3 stages autonomously without interrupting the engineer.

**Tie-break (multiple eligible trains):** pick the one with the most stages remaining to `done`. Longest autonomous runway.

The rationale is rendered into the table cell verbatim — "Next 3 stages (push_switch_config, obn_discover_post_sw_config, await_obn_update_f) — first gate at step 3 → 2 stages autonomous" or "BLOCKED — Stadler-dependent" — so the engineer sees why and can override.

## Output: morning-brief.html

Single-file HTML, no external CDN. Mirrors `gen_dashboard.py` styling exactly: `--bg #0f172a`, `--surface #1e293b`, `--accent #38bdf8`, Segoe UI / system font, Consolas mono, status lozenges with the same five colours. Sections:

1. **Header** — `DOSTO Morning Brief`, date, "N of M trains reachable".
2. **Reachable trains table** — columns: `Train# | Fzg | CCU IP | Nomad status | Stadler status | Next Action | Cable Issues | Resume Stage | Recommended?`. The recommended row is highlighted (left border + subtle row background). The rationale appears in the `Recommended?` cell. **Train# leads** (Nomad-internal primary identifier per the 2026-05-22 schema reorder); Fzg shown alongside as the customer-facing reference.
   - **Cable Issues column:** for each train, render open entries from `cable-issues-register.md` as compact chips (e.g. `🔴 #5 D3.e1-2`). If none, render `—`. A train with open cable issues AND a Nomad status of BLOCKED gets its row highlighted in amber — a distinct visual cue that Stadler action is pending.
3. **Would-be orchestrate command** — copyable code block: `/dosto-orchestrate trains=<comma-separated-train#-list>`. Below it, in muted text: "Dry run — not invoked. Paste manually to dispatch." NEVER auto-execute.
4. **Open cable issues summary** — a collapsed `<details>` block listing all `🔴 OPEN` entries from `cable-issues-register.md` across the whole fleet (not just reachable trains), sorted by Train#. One line per issue: `#N | <train#> | <switch/port> | <fault type>`. Gives the engineer a full Stadler chase-list at a glance.
5. **Unreachable trains** — collapsed `<details>` block listing the Train#s of known-CCU trains that failed the probe. Quick triage list.

## Chat-summary table convention (Claude must follow when relaying the brief)

After running the skill, when Claude relays the morning-brief output to the engineer as a compact chat table (the "Reachable trains at a glance" summary), it MUST include a `Status` column showing in-flight claim state. Engineers running multiple sessions need to know at a glance which trains are already being worked on — a summary missing this column was the explicit gap surfaced 2026-05-22.

**Required columns** (in order):

| Column | Source | Render rules |
|---|---|---|
| Train# | fleet-status row | bare value (e.g. `4736-104`) |
| Fzg | fleet-status row | bare value (e.g. `132`); `❓` if unknown |
| Status | parse Nomad status cell — see below | claim indicator (see below) |
| Stage | inferred resume stage (from stdout) | stage_id or `?` / `BLOCKED` |
| Notes | the brief's existing rationale / next-action one-liner | truncate at ~60 chars |

**Status column values** (load-bearing — engineers scan this first):

| Cell value | When |
|---|---|
| `🔵 in flight (sess <X>, hb <Y>m)` | Row's Nomad status parses as in-flight claim (`parse_in_flight()` returns non-None). Show the session ID and heartbeat age — engineers running multiple sessions need to know which one claimed it. |
| `🔴 STALE (sess <X>, hb <Y>m)` | Heartbeat > 30 min — likely a dead session. Engineer should run `/dosto-morning-brief --clean-stale-claim <TRAIN#>`. |
| `✅ available` | Not in-flight; pre-flight will allow dispatch. |
| `🟡 BLOCKED` | Row's terminal state is BLOCKED. Don't auto-dispatch. |
| `🟢 DONE` | Row's terminal state is DONE. Don't re-dispatch unless engineer explicitly wants to re-verify. |
| `🟡 PAUSED` | Row's terminal state is PAUSED. |

**Recommended-row highlight:** the brief's start-first recommendation (one Train# at most) gets a ⭐ prefix in the Notes column. Only one row carries this marker per run.

**Example chat-summary table** (the engineer sees something like this in chat):

```
Train#     Fzg  Status                          Stage                       Notes
4736-104   132  🔵 in flight (sess 1212Z, hb 2m) push_switch_config (3/18)   active in another session
4736-120   148  ✅ available                    apply_obn_patches           ⭐ RECOMMENDED — E3 power restored
4736-119   147  ✅ available                    await_obn_update_f          Gate 4 — 18/18 sw ✅, 24/24 APs ✅
4706-103   191  🟡 BLOCKED                      BLOCKED                     OBN update c pending
4734-120   20   🔴 STALE (sess 1030Z, hb 47m)   ?                           sw+APs done — review needed; clean stale claim
```

Engineers reading this immediately know:
- 4736-104 is being worked on by session `1212Z` — don't touch.
- 4736-120 is available and the recommended start-first.
- 4734-120 has a stale claim that needs cleanup before re-dispatch.

**This convention applies to ALL chat outputs**, not just the morning-brief. Whenever a Claude session produces a multi-train summary table — orchestrate dispatch preview, status check, cycle digest — include the Status column. The data is already in fleet-status; the discipline is in the rendering.

## What this skill is NOT

- Not an orchestrator. Does not spawn subagents, does not invoke `/dosto-orchestrate`, does not call any per-device skill.
- Not a writer of fleet-status. Read-only on fleet-status.md.
- Not a scheduler. One-shot per invocation. Re-run as needed.
- Not a substitute for `dosto-auto-scan`. The auto-scanner is scheduled, owns `auto-scan-state.json`, and writes back to fleet-status's three allowlisted columns. This skill is the engineer's morning ritual — interactive, dry-run, no state.

## Implementation

The skill is implemented as `scripts/dosto_morning_brief.py` at workspace root. The script:

- Parses fleet-status.md by scanning every `### NNNN series` header dynamically (currently 4736 / 4734 / 4706 / 4705) — does not hardcode series names so future series are picked up automatically.
- Reads cable-issues-register.md once after the sweep. Extracts all `🔴 OPEN` rows by scanning the at-a-glance table (the `| # | Trainset | ... | Status |` table). Matches each row to a reachable train by Train# string match. No writes — read-only.
- Sweeps the full `10.179.X.1` range (X=0..255) with a short TCP/22 connect (Python `socket.create_connection(timeout=...)`) — the sweep is the source of truth for reachability. Each responder is then cross-referenced against fleet-status: known IPs are folded into the reachable list; unknown IPs trigger the Fzg assignment gate. Known IPs that don't respond become the unreachable list.
- Applies the stage-inference table inline.
- Computes the recommendation per the rule above.
- Renders the HTML with the CSS literal copied from `gen_dashboard.py`.
- Prints the absolute path to `morning-brief.html` and the would-be orchestrate command to stdout.

To invoke from the skill, run:

```bash
python scripts/dosto_morning_brief.py
```

No arguments required. Add `--timeout 3` to shorten the probe if the cellular network is flaky.
