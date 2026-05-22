---
name: dosto-confluence-sync
description: Sync fleet-status.md to the team Confluence page (DEL-OBB-035: Train commissioning status, page ID 5410684933). Use when an engineer wraps up a session and wants to push fleet-status to the team page, when the orchestrator hits an approval gate / terminal state / cycle-digest trigger, or when the engineer says "sync confluence" / "push fleet-status to confluence". One-way push from local source-of-truth → team-shared projection per .claude/contracts/confluence-sync.md. Subagents never invoke this — orchestrator-as-sole-writer per the same contract.
---

# DOSTO Confluence Sync

This skill pushes the local [`fleet-status.md`](../../../fleet-status.md) file to the team Confluence page so the rest of the team can see live commissioning status without cloning the workspace. It is the only mechanism that writes to that page — engineers should not edit Confluence directly because the next sync will overwrite manual edits (the skill flags drift but does not merge automatically).

The contract is [`.claude/contracts/confluence-sync.md`](../../contracts/confluence-sync.md). Read that first if you need the rationale; this SKILL.md is the runbook.

## When to use

- **Manual end-of-session sync** — engineer runs `/dosto-confluence-sync --push` after updating their train row in `fleet-status.md` (Step 11 of [train-login-checklist.md](../../../train-login-checklist.md)). Replaces "remember to also paste this into Confluence" with one command.
- **Initial population** — first push after the page was created empty. Same code path as steady-state pushes.
- **Future orchestrator integration** — Phase 5+ orchestrator invokes this skill on every event-driven trigger (status change, row mutation, new train added). Until that orchestrator exists, engineers run it manually.
- **Drift inspection** — `--diff` mode reports what would change without pushing. Useful before a manual push when you're not sure if your local file diverged from someone else's last push.

## Modes

| Mode | What it does | When to use |
|---|---|---|
| `--check` (default) | Read current Confluence page version + size. Compare to local source file size and last-modified time. Print a one-line verdict: in-sync, local-newer, or page-newer. No writes. | Quick sanity check ("is what I see on Confluence the same as local?") |
| `--diff` | Fetch current page body, compute the body that would be pushed, show a unified diff. No writes. | Before pushing — preview the change. |
| `--push` | Fetch current page body, compute new body with banner, push via `updateConfluencePage` with optimistic concurrency. Handle 409 → drift detection per contract. | The real action. Engineer runs at end of session. |
| `--push --force` | Skip drift detection — overwrite whatever is on Confluence. Use only when you've already inspected drift and decided to drop manual edits. | Recovery from a drift state where the manual edits were already pulled into local file by hand. |

All modes support `--json` for machine output. Engineer running interactively gets the human-readable form; orchestrator passes `--json`.

## Targets — `--target {fleet|cables|both}`

Per [confluence-sync.md](../../contracts/confluence-sync.md) Amendment 1, the skill pushes to one of two pages:

| Target | Source file | Page ID lookup | Render |
|---|---|---|---|
| `fleet` (default) | `fleet-status.md` | hardcoded `5410684933` | Existing exec-view-only layout (4736 + 4734 + 4705 + 4706 tables) |
| `cables` | `cable-issues-register.md` | `cable_register_page_id` from `.claude/state/confluence-pages.json` | Two-section render: Confirmed cabling faults, then Auto-detected anomalies |
| `both` | both | both | Sequential pushes — `fleet` first, then `cables`. Independent drift detection per page. |

`--target cables` requires the cable-register page to have been bootstrapped by `/dosto-auto-scan --bootstrap-confluence-cables` (see [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md)). If `confluence-pages.json` is missing or the field is empty, the skill exits with: `cable_register_page_id not found — run /dosto-auto-scan --bootstrap-confluence-cables first`. The sync skill does not create pages itself.

### Two-section render (cables target only)

Parse `cable-issues-register.md` row-by-row. Group by `**Status:**` field value. Render:

```
[banner — auto-sync banner + "Confirmed faults below — PM section"]

# Confirmed cabling faults — Stadler escalation tracker

[All rows where Status: confirmed, in original register order, with Stadler-instructions blocks rendered in full]

# Auto-detected anomalies — engineer review pending

[All rows where Status: auto-detected, in original register order, showing signal source / first-seen / last-seen / scan count / suggested category. Stadler-instructions block omitted (empty by definition for auto-detected rows).]
```

Rows with any other `Status:` value (typo, manual experiment) are surfaced as a warning to the engineer and excluded from the push. Print to stderr: `WARN: row #N has unrecognised Status: <value>, excluded from push`.

## Inputs

- `--target <fleet|cables|both>` — selects which page(s) to push. Default `fleet`.
- `--page-id <id>` — overrides the page ID derived from `--target`. Use only for testing against a draft/sandbox page.
- `--cloud-id <id>` — defaults to `nomad-digital.atlassian.net`.
- `--source <path>` — defaults to `fleet-status.md` (or `cable-issues-register.md` when `--target cables`). Override only for testing.
- `--force` — only valid with `--push`. Skip drift detection.
- `--json` — machine-readable output.
- `--dry-run` — synonym for `--diff`. Same semantics.

## Page identity (canonical)

| Field | Value |
|---|---|
| Cloud ID | `nomad-digital.atlassian.net` |
| Page ID | `5410684933` |
| Page URL | https://nomad-digital.atlassian.net/wiki/spaces/PDD/pages/5410684933 |
| Title | `DEL-OBB-035: Train commissioning status` |
| Space ID | `3854893184` |
| Parent ID | `3859447840` |

These are constants for the project. Don't hard-code anywhere except this skill and the contract.

## Procedure

### Step 1 — Read the live page state

Call `mcp__b29e83b2-...__getConfluencePage` with `pageId=5410684933`, `contentFormat=markdown`. Parse the response:

```
{
  "version": {"number": <V_current>, "createdAt": <ts>, "authorId": <user>},
  "body": "<current page body>"
}
```

Record `V_current`, `body_current`, and `last_author_id`. The author of the last edit is informational — useful for drift diagnostics.

### Step 2 — Read the local source and compose the body

`Read` the file at `--source` (default `fleet-status.md`). Parse it into an in-memory representation, then compose the Confluence body as **markdown** per the exec-view-only layout below.

#### Why markdown, not HTML

Validated 2026-05-09: the Atlassian connector's `updateConfluencePage` schema accepts only `contentFormat: "markdown"` or `"adf"` — `"html"` is rejected at validation despite the connector tool description suggesting otherwise. Markdown bodies do **NOT** preserve `<details><summary>` collapsibles either — Confluence's markdown renderer silently strips them, leaving the inner content sitting on the page below the rest. So the original two-table-with-collapsible plan can't work via markdown mode.

Two paths considered:
- **(a) Drop the full-detail table from Confluence; exec view only.** Engineers read `fleet-status.md` locally for the wide view. Simple, works today.
- **(b) Switch to ADF (JSON body) which has a native `expand` node.** ~3-4× more plumbing — composing an ADF document tree instead of markdown — and bigger maintenance surface.

Choice: **(a) — exec view only** (Simplicity First). The Confluence page is a dashboard for the team; engineers debugging a specific train work from the local workspace anyway. If a real demand for "full detail on Confluence" emerges, revisit with option (b).

#### Page layout (canonical)

The Confluence page body has these sections in this order:

1. **Banner** — auto-sync timestamp, version, sync source, plus a one-line pointer at where to find the full 14-column detail (the local `fleet-status.md`).
2. **Header** — title + last-updated + update-discipline note (from the top of fleet-status.md).
3. **Status legend** — small table mapping the 5 status-lozenge emoji to status names + meanings.
4. **Train#-and-Fzg convention** — series formulas + runtime-lookup warning (unchanged from local; section is named `## Train#-and-Fzg convention` post-2026-05-22 schema reorder, previously `## Fzg-ID convention`).
5. **Per-series exec table** — 6 columns: `Train#`, `Fzg`, `CCU IP`, `Nomad status`, `Stadler status`, `Next action`. **Train# leads** (Nomad-internal primary identifier per the 2026-05-22 schema reorder); Fzg is secondary. One table per series header found in `fleet-status.md` (currently 4736 / 4734 / 4706 / 4705 — discover dynamically, do not hardcode). The `Stadler status` column was added 2026-05-21 so the team can see at a glance which trains are blocked by Stadler-side work (missing APs/switches or open cabling faults) vs which are Nomad-side work still in flight.
6. **Per-train notes** — unchanged from local, rendered as standard markdown headings + lists.
7. **How to update** — engineer-facing reminder (5-step procedure).

#### Banner shape (markdown blockquote)

```markdown
> **Auto-synced from `fleet-status.md` in `dosto-troubleshooting` workspace.**
> Last sync: <ISO-8601 UTC> · Page version: <V_current + 1> · Sync source: <engineer name> (manual) — or — orchestrator (auto)
> Manual edits to this page will be overwritten on next sync. Edit `fleet-status.md` instead, or comment on this page.
>
> 📄 **For full detail** (all 14 columns: OBN patches, switch firmware, AP firmware, vlan7 ok, Stadler cabling, FW reach, health-check date, customer report, last touched), open `fleet-status.md` in the `dosto-troubleshooting` workspace. The exec view below carries the six columns most useful for "where's this train at right now?".
```

This four-line banner doubles as drift detection signal (the exact opening text `> **Auto-synced from` is the detection prefix) AND as the "where to find more" pointer.

#### Status legend shape

A 3-column markdown table for status meanings — replaces the bullet-list legend from local:

```markdown
| Lozenge | Status | Meaning |
|---|---|---|
| 🟢 | **DONE** | All v8 work complete, no Nomad action remaining |
| 🟢 | **DONE w/ Stadler** | Nomad work complete, awaiting Stadler on cabling/FW |
| 🔵 | **IN PROGRESS** | Actively being worked on this session |
| 🟡 | **PAUSED** | Partial work; train powered off mid-run; will resume as-is |
| 🔴 | **BLOCKED** | Stadler cabling fault must be fixed before we can continue |
| ⚪ | **UNKNOWN** | Visited but state not captured here yet, or never visited |
```

The lozenge column uses Unicode coloured-circle emoji for at-a-glance visual scan. Each row maps to one of the values that appears in the per-series exec table's `Status` column.

#### Exec table shape (6 columns)

```markdown
| Train# | Fzg | CCU IP | Nomad status | Stadler status | Next action |
|---|---|---|---|---|---|
| 4736-101 | 129 | ❓ | ⚪ UNKNOWN | ❓ | initial visit |
| 4736-102 | 130 | `10.179.47.1` | 🟡 **PAUSED** | ✅ clear | apply patches + persist + fix train_id + fix vlan7 — see notes |
| 4736-104 | 132 | `10.179.10.1` | 🔴 **BLOCKED w/ Stadler + 6 APs stuck** | 🔴 D4 AP missing (cable reg #5) | Push remaining 3 APs (.237 .238 .240); D4 cable Stadler item — see notes |
| 4736-105 | 133 | `10.179.1.1` | 🟢 **DONE w/ Stadler** | 🔴 Coach 5 AP2 missing | wait for Stadler on Coach5 AP2 + FW path |
```

**Stadler status rule:** 🔴 BLOCKED when any APs/switches are missing OR a cabling fault is open (any open `cable-issues-register.md` entry for the train); ✅ clear otherwise; ❓ when not yet checked / UNKNOWN. Copy the value verbatim from the local `fleet-status.md` row's `Stadler status` column.

Status formatting rule: `<emoji> **<STATUS>**` — emoji first for visual scan, bold status text for hierarchy. The emoji prefix MUST match the legend table above. Mapping:

| Status text | Emoji prefix |
|---|---|
| `DONE` / `DONE w/ Stadler` | 🟢 |
| `IN PROGRESS` | 🔵 |
| `PAUSED` | 🟡 |
| `BLOCKED` (any variant) | 🔴 |
| `UNKNOWN` / `NOT STARTED` | ⚪ |

`Next action` column carries the text verbatim from the local `fleet-status.md` row's `Next action` column. Truncation is NOT applied — Confluence wraps long text within the cell. If the truncated form is preferred, append "— see notes" and let the per-train notes section below carry the full detail.

CCU IPs in the table use `code` formatting (backticks) so they render as monospace. Empty / unknown IPs render as `❓`.

#### Per-train notes section

Render verbatim from the local `## Per-train notes` section. Markdown code blocks, inline `code`, bold, italic, and ✅/🔴/🟡/⬜/❓ emoji all round-trip cleanly through markdown mode.

Confluence will reformat markdown bullets `-` to `*` and may auto-promote bare `.md` filenames in inline links to `http://*.md` smart-card links. These are cosmetic round-trip artefacts; not blocking.

#### Engineer name resolution

In `--push` mode, default to `git config user.name` if available, else the system username. Orchestrator-driven pushes set `Sync source: orchestrator (auto)` instead.

### Step 3 — Mode-specific behaviour

#### `--check` mode

Compute:
- `body_local_size` (chars), `body_local_mtime` (file mtime as UTC)
- `body_current_size` (chars from page body), `body_current_version_ts` (page version createdAt)
- Banner-stripped current body for diff (the banner from a previous push is the only line set we can subtract; if the body doesn't start with the banner, treat it as drift)

Verdicts:
- `in_sync` — body_current minus banner == body_local
- `local_newer` — body_local differs from banner-stripped body_current AND `body_local_mtime > body_current_version_ts`
- `page_newer` — banner-stripped body_current differs from body_local AND `body_current_version_ts > body_local_mtime` (drift signal — someone edited Confluence directly, OR another orchestrator session pushed)
- `divergent` — both sides changed since the last common state (rare; flag for human)

Print:
```
Local:    fleet-status.md (4823 chars, modified 2026-05-09 17:02 UTC)
Remote:   page 5410684933 v47 (5012 chars, last edited 2026-05-09 16:55 UTC by Abbas Rizvi)
Verdict:  local_newer — local has 1 new train row, push to sync.
```

#### `--diff` mode

Same fetch + compute as `--check`, plus:

1. Strip the banner from `body_current` (lines 1-3 of body if they start with `> **Auto-synced from`).
2. Run a unified diff between stripped `body_current` and `body_local`.
3. Print the diff with `+++` and `---` markers.
4. Show no further action prompt — `--diff` is read-only.

#### `--push` mode

1. Fetch live page state (same as `--check`).
2. **Stale-source guard (unless `--allow-stale`):** stat `<source>` (default `fleet-status.md`) for its mtime. If `now - mtime > 24h`, halt and warn:
   ```
   🟡 Stale source warning.
   <source> was last modified <X hours/days> ago (mtime: 2026-05-08 14:32 UTC).
   You're about to push that as the current fleet state to Confluence.

   This usually means:
     (a) You forgot to update fleet-status.md after a recent train session
     (b) You're deliberately re-pushing an old version (use --allow-stale)

   Options:
     (a) Cancel; update fleet-status.md first, then re-run --push
     (b) Re-run with --allow-stale to push anyway

   Halting — no push fired.
   ```
   This catches the "I forgot to update locally" footgun. The 24h threshold is the rough lower bound of "definitely stale" — fleet-day commissioning sessions update the file at least daily; anything older almost always reflects forgotten updates rather than deliberate state.
3. **Drift check (unless `--force`):** if `body_current` is non-empty AND doesn't start with the banner OR the banner version doesn't match what we last pushed, treat as drift:
   - Read `.claude/logs/confluence-sync.jsonl` for the last successful push entry.
   - If the banner version on the page > the version we last pushed, someone else edited.
   - Print drift warning, write a `confluence-drift.jsonl` log entry with the unified diff vs. last-pushed body, and **halt**:
     ```
     🟡 Drift detected on page 5410684933.
     Last push (this workspace):  v46 at 2026-05-09 16:55 UTC
     Live page version:           v47 at 2026-05-09 17:02 UTC by [other user]

     A diff has been written to .claude/logs/confluence-drift.jsonl.

     Options:
       (a) Pull the manual edits into fleet-status.md, then re-run --push
       (b) Run --push --force to overwrite (drops the manual edits)
       (c) Cancel and investigate
     ```
4. Compute the markdown body per Step 2's exec-view layout. Banner uses `V_current + 1` for the version number.
5. Call `mcp__b29e83b2-...__updateConfluencePage` with:
   - `pageId=5410684933`
   - `cloudId=nomad-digital.atlassian.net`
   - `contentFormat=markdown` (the only format that actually works — see Step 2 "Why markdown, not HTML")
   - `title="DEL-OBB-035: Train commissioning status"` (must be re-passed; the connector requires it on update)
   - `spaceId=3854893184`
   - `parentId=3859447840`
   - `body=<banner + status legend + per-series exec tables + per-train notes>`
   - `versionMessage="dosto-confluence-sync: <engineer or orchestrator>, <ISO ts>"`
6. On success: log to `.claude/logs/confluence-sync.jsonl`:
   ```json
   {"ts":"2026-05-09T17:05:00Z","action":"push","page_id":"5410684933","prev_version":46,"new_version":47,"source":"manual:Abbas Rizvi","body_size":4823,"banner_version":47,"sha256":"..."}
   ```
7. On 409 (version mismatch): re-fetch, follow drift detection. One automatic retry is acceptable if the new V_actual == V_current + 1 (race with our own banner increment); beyond that, escalate.
8. Print success line:
   ```
   ✅ Pushed v46 → v47 (4823 chars). https://nomad-digital.atlassian.net/wiki/spaces/PDD/pages/5410684933
   ```

### Step 4 — Logging

Two log files in `.claude/logs/` (create the directory if absent):

| File | Purpose |
|---|---|
| `confluence-sync.jsonl` | One JSON line per successful push. Used by drift detection to know "what we last pushed". |
| `confluence-drift.jsonl` | One JSON line per detected drift event. Includes diff, previous-pushed body hash, current body hash, and timestamps. |

Both are append-only. No log rotation needed for v1 — fleet rollout is bounded (40 trains, ~1 push per train per session). If logs grow large, rotate by year.

## `--json` output

`--check`:
```json
{
  "skill": "dosto-confluence-sync",
  "mode": "check",
  "schema_version": "1",
  "verdict": "in_sync|local_newer|page_newer|divergent",
  "raw": {
    "page_id": "5410684933",
    "page_version": 47,
    "page_size_chars": 5012,
    "page_last_edit_ts": "2026-05-09T16:55:00Z",
    "page_last_author_id": "5d5186cdf0f22a0da2d6dad7",
    "local_path": "fleet-status.md",
    "local_size_chars": 4823,
    "local_mtime": "2026-05-09T17:02:13Z",
    "banner_present_on_page": true,
    "banner_version": 46,
    "last_logged_push_version": 46
  }
}
```

`--diff`:
```json
{
  "skill": "dosto-confluence-sync",
  "mode": "diff",
  "schema_version": "1",
  "verdict": "in_sync|differs",
  "raw": {
    ... same as --check ...,
    "diff_lines_added": 1,
    "diff_lines_removed": 0,
    "diff_unified": "--- page\n+++ local\n@@ -49,1 +49,1 @@\n- ... old row\n+ ... new row"
  }
}
```

`--push`:
```json
{
  "skill": "dosto-confluence-sync",
  "mode": "push",
  "schema_version": "1",
  "verdict": "pushed|drift_detected|push_failed",
  "raw": {
    "prev_version": 46,
    "new_version": 47,
    "page_url": "https://nomad-digital.atlassian.net/wiki/spaces/PDD/pages/5410684933",
    "body_size": 4823,
    "duration_ms": 1240
  },
  "drift_details": null
}
```

## Failure modes

| Failure | Skill behaviour |
|---|---|
| MCP connector unreachable / auth failed | Print error, halt. Don't retry — engineer or orchestrator handles. |
| Page version conflict (409) on push | Re-fetch, check drift; one automatic retry if pure race; otherwise halt with drift report. |
| Drift detected (banner version mismatch or banner missing on non-empty page) | Halt. Print options. Don't auto-merge. Write `confluence-drift.jsonl`. |
| `fleet-status.md` doesn't exist | Halt with clear error. |
| `fleet-status.md` is empty (0 bytes) | Halt — refuse to push an empty page. |
| `fleet-status.md` is suspiciously short (<500 chars when historical was >3000) | Warn but still allow push — engineer might be doing a deliberate truncation. |
| Page title or parent has changed externally | Re-pass them on update; if connector errors on parent mismatch, halt and ask engineer. |

## What this skill deliberately does NOT do

- ❌ Two-way merge — drift detection halts, doesn't merge.
- ❌ Push partial fields — full-page replacement only (per contract).
- ❌ Edit `fleet-status.md` — read-only on the source.
- ❌ Push other Confluence pages — only the canonical page ID.
- ❌ Read or write Confluence comments.
- ❌ Auto-rotate logs.
- ❌ Run on a schedule (Phase 5 orchestrator triggers — but the trigger logic lives there, not here).

## Edge cases / gotchas

- 🟡 **Banner is an in-band marker.** The banner is how we tell "what's been pushed by this skill" vs "what was edited manually". If a human edits the banner itself, drift detection will fire. That's intentional — the banner is part of the body the skill controls.
- 🟡 **Confluence renders Unicode emoji natively** (✅ 🔴 🟡 ⏸️ ⬜ ❓). The contract claims this round-trips cleanly — validated by initial population test (2026-05-09).
- 🟡 **GitHub-flavored markdown tables** — Confluence's markdown renderer accepts the `|---|` syntax. The 14-column local fleet-status table forced horizontal scroll, which is why this skill renders only the 5-column exec view (Step 2 layout). Engineers needing all 14 columns open the local `fleet-status.md`.
- 🔴 **`contentFormat: "html"` is rejected at validation** despite the connector tool description showing HTML examples. The schema enum is `markdown | adf` only. If a future need for embedded HTML (panels, status lozenges, `<details>` collapsibles) appears, switch to ADF (composing the JSON document tree) — not markdown-with-inline-HTML, which Confluence silently strips.
- 🔴 **`<details><summary>` is stripped in markdown mode** — Confluence's markdown renderer drops the collapsible boundary, leaving inner content sitting flat on the page below the rest. Validated 2026-05-09 with v3 push. Don't use markdown-embedded HTML elements.
- 🟡 **Page version numbers are monotonic and connector-managed.** We pass `versionMessage` for the audit trail; the connector auto-bumps `version.number`. Don't try to set `version.number` directly.
- 🟡 **Rate limit unlikely.** Worst-case manual rate is one push per session (1-3 per day). Orchestrator-driven max one per 30s during burst. Both well under Atlassian's per-user rate limit.
- 🟡 **First push has no `V_current` to compare** — the page exists at v1 with empty body. Treat empty-body as "fresh, no drift possible", push as v2.

## Pairs with

- [`.claude/contracts/confluence-sync.md`](../../contracts/confluence-sync.md) — contract (read first)
- [fleet-status.md](../../../fleet-status.md) — source file
- [train-login-checklist.md](../../../train-login-checklist.md) — Step 11 should reference this skill
- Future: top-level orchestrator (Phase 5) will invoke this skill on events

## Reference

- Atlassian connector tools: `mcp__b29e83b2-87a0-46a4-9f8c-e389232437ac__getConfluencePage`, `...__updateConfluencePage`
- Contract test plan (5 steps) — see `.claude/contracts/confluence-sync.md` § "Test plan"
