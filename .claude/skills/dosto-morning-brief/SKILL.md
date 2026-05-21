---
name: dosto-morning-brief
description: Engineer-morning briefing for the DOSTO fleet — dry-run reachability scan + recommended "start-first" train. Use when the engineer starts their day and wants a single-page view of which trains are online right now, what their next action is, and which one to start with so it runs autonomously while other trains are attended to. Reuses dosto-auto-scan's Tier-1 reachability probe (TCP/22 sweep of known CCU IPs from fleet-status.md), reads each reachable train's Status + Next action, infers a resume stage from the prose, applies the "next ~3 stages contain no approval gate" recommendation rule (tie-break: longest autonomous runway), and renders morning-brief.html in the dashboard.html dark-theme style. Strictly read-only — does NOT invoke /dosto-orchestrate, does NOT edit fleet-status.md, does NOT push to Confluence. Surfaces the would-be orchestrate command for the engineer to paste manually.
---

# DOSTO Morning Brief

A dry-run, read-only morning dashboard. The engineer types `/dosto-morning-brief` over coffee, gets a single-page HTML view of which trains are reachable today, what the next action is per train, and which train the skill recommends starting first — with the rationale surfaced so the engineer can override.

This is the dry-run companion to `/dosto-orchestrate`. It prints the command that *would* be sent, but does not send it.

## What the skill does

1. **Tier-1 reachability probe** — TCP/22 sweep of every known CCU IP listed in `fleet-status.md` (the "Fleet at a glance" table). Same logic as `dosto-auto-scan` Tier 1, scoped to CCUs already mapped to a Fzg ID.
1b. **Discovery sweep** — TCP/22 probe of every `10.179.X.1` for X in 0..255 (256 candidates, parallel, ~15s wall-clock at default timeout) minus IPs already present anywhere in `fleet-status.md` (series tables OR Pending section). Any responder NOT already known surfaces as `needs_assignment` and the brief halts on a **Fzg assignment gate** (see "Discovered-CCU gate" below) — the brief does NOT auto-write a row, because the Fzg ID cannot be reliably inferred from anything on the CCU. Disable with `--no-discover`.

### Discovered-CCU gate (engineer assignment required)

Why: on an unvisited CCU, the `train_id` rendered into switch hostnames (`nv6-*-v8-NNN`) and into `/etc/obn/template/nv6-*.cfg` filenames is *the value that commissioning fixes*. The broken `128 + train_id` formula, stale Puppet images, or hand-set wrong values mean these names commonly carry the wrong Fzg pre-commissioning. Trusting them would lock in a wrong Fzg before we ever fix it. Authoritative sources for Fzg ID on an unvisited CCU:

- **Physical inspection** of the train (Fzg number painted on the carriage)
- **Cross-reference against `train-ip-allocation-commission/` PDFs** — match CCU IP / box hostname to the per-train allocation PDF

The brief surfaces each discovered IP and prompts the engineer (via the Claude session) for each:

> Discovered new CCU `10.179.17.1` on TCP/22 — not in fleet-status. What is the Fzg ID and series? (e.g. "145 4736" or "skip")

Engineer responses:
- `<fzg> <series>` (e.g. `145 4736`) → Claude calls `python scripts/dosto_morning_brief.py --assign 10.179.17.1 145 4736`. Script inserts a new row into the matching series table.
- `skip` → Claude calls `python scripts/dosto_morning_brief.py --skip 10.179.17.1`. Script appends to a `## Pending Fzg assignment` section so the IP isn't re-prompted next morning.

This is NOT a contract gate (no subagent involvement; subagents never see new CCUs). It's a brief-local gate, handled by the Claude session running the skill. The Python script never prompts directly — it just emits the list, and the skill drives prompts via the Claude harness.
2. **Per-train state lookup** — for each reachable Fzg, grab the `Status` and `Next action` cells from the fleet-status table.
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
2. **Reachable trains table** — columns: `Fzg | CCU IP | Status | Next Action | Resume Stage | Recommended?`. The recommended row is highlighted (left border + subtle row background). The rationale appears in the `Recommended?` cell.
3. **Would-be orchestrate command** — copyable code block: `/dosto-orchestrate fzg=<comma-separated-reachable-list>`. Below it, in muted text: "Dry run — not invoked. Paste manually to dispatch." NEVER auto-execute.
4. **Unreachable trains** — collapsed `<details>` block listing the Fzg IDs of known-CCU trains that failed the probe. Quick triage list.

## What this skill is NOT

- Not an orchestrator. Does not spawn subagents, does not invoke `/dosto-orchestrate`, does not call any per-device skill.
- Not a writer of fleet-status. Read-only on fleet-status.md.
- Not a scheduler. One-shot per invocation. Re-run as needed.
- Not a substitute for `dosto-auto-scan`. The auto-scanner is scheduled, owns `auto-scan-state.json`, and writes back to fleet-status's three allowlisted columns. This skill is the engineer's morning ritual — interactive, dry-run, no state.

## Implementation

The skill is implemented as `scripts/dosto_morning_brief.py` at workspace root. The script:

- Parses fleet-status.md by re-using the same regex shape as `gen_dashboard.py` (`parse_table` for `### 4736 series` and `### 4734 series`).
- Probes each known CCU IP with a short TCP/22 connect (Python `socket.create_connection(timeout=...)`) — no external `nc` dependency for cross-platform reliability.
- Applies the stage-inference table inline.
- Computes the recommendation per the rule above.
- Renders the HTML with the CSS literal copied from `gen_dashboard.py`.
- Prints the absolute path to `morning-brief.html` and the would-be orchestrate command to stdout.

To invoke from the skill, run:

```bash
python scripts/dosto_morning_brief.py
```

No arguments required. Add `--timeout 3` to shorten the probe if the cellular network is flaky.
