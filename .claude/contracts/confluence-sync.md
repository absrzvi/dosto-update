# Confluence Sync Contract

**Status:** v1, locked 2026-05-09.

How `fleet-status.md` (local source of truth) gets reflected to the Confluence page (team-shared projection). Only the orchestrator does this — subagents never talk to Confluence.

## Target

| Field | Value |
|---|---|
| Cloud ID | `nomad-digital.atlassian.net` |
| Page ID | `5410684933` |
| Page URL | https://nomad-digital.atlassian.net/wiki/spaces/PDD/pages/5410684933 |
| Space | `PDD` |
| Parent page | `3859447840` |

These values are encoded in [CLAUDE.md](../../../CLAUDE.md) (Folder layout / .claude section). They don't go in `settings.local.json` because they're team-shared, not per-engineer.

## Direction

**One-way: local → Confluence.** Confluence is a projection of the local file. Humans editing the Confluence page directly will be **overwritten on the next sync** unless the orchestrator detects manual changes (see "Drift detection" below).

This deliberately matches the orchestration model: orchestrator is sole writer of state. Confluence isn't a multi-writer collaboration tool here — it's a dashboard.

## When the orchestrator pushes

**Event-driven, not time-driven.** A push fires when:

- Any train row's `status` field changes (`IN_PROGRESS` → `DONE`, `RUNNING_DIAGNOSTICS` → `NEEDS_APPROVAL`, etc.)
- Any train row's `vlan7_ok`, `obn_patches`, `switches_v8`, or any other tracked field changes value
- A train row is added (new train brought into rotation)
- A new per-train notes section is added or removed
- Cycle boundary at 5-min checkpoint **only if anything changed since last push**

If nothing changed in a 5-min cycle, **no push happens**. This avoids gratuitous version-bumping the Confluence page.

## What gets pushed

Full table + per-train notes — same content as `fleet-status.md`, all 14 columns. Per your spec ("all 14, it's for engineers too").

The push body is the entire page replacement. Confluence's `updateConfluencePage` is whole-page-replace; there's no field-level patching available.

## Conversion

`fleet-status.md` is markdown with GitHub-flavored markdown tables. The Atlassian connector accepts markdown via `contentFormat: "markdown"`. Tables, headers, links, code blocks all round-trip cleanly. Inline emoji (✅ 🔴 🟡 ⬜) round-trip as Unicode and render natively.

The orchestrator does not need a markdown→HTML conversion step. Pass the raw `.md` file content as the body.

**One exception:** at the top of the Confluence page, prepend a short auto-generated banner:

```markdown
> **Auto-synced from `fleet-status.md` in `dosto-troubleshooting` workspace.**
> Last sync: 2026-05-09 06:55:00 UTC · Page version: 47 · Sync source: orchestrator (Abbas Rizvi)
> Manual edits to this page will be overwritten on next sync. Edit `fleet-status.md` instead, or comment on this page.
```

This is the only difference between the local file body and the pushed page body.

## Version handling

Confluence pages have an integer version number that auto-increments on every update. The orchestrator uses optimistic concurrency:

```
1. Read current page version (call it V_current)
2. Compute new body from current fleet-status.md
3. Call updateConfluencePage(pageId, body, version=V_current + 1)
4. If 409 Conflict (version mismatch):
     a. Re-read page → V_actual
     b. If V_actual > V_current: someone else edited the page (manual edit or another orchestrator)
     c. → Drift detection (see below)
5. Otherwise: log V_current + 1 as the new version
```

## Drift detection

If a manual edit lands on the Confluence page between two orchestrator pushes, V_actual will be > V_current + 1. The orchestrator handles this by:

1. Fetching the current page body
2. Logging `.claude/logs/confluence-drift.jsonl` with the diff vs. last-pushed-body
3. Showing the human a "Confluence has manual edits since last sync" warning
4. Asking the human: pull manual edits into `fleet-status.md`? Or overwrite (drop the manual edits)?
5. Default action on no response within 5 minutes: skip this push, retain local state, retry on next event

This is a **safety mechanism, not a merge engine.** We don't try to three-way merge automatically. The human chooses, the orchestrator acts.

## Authentication

Uses the existing Atlassian connector configured in this workspace (MCP tool `mcp__b29e83b2-87a0-46a4-9f8c-e389232437ac__updateConfluencePage`). The credentials live in the user's MCP config and are not project-specific. No additional setup needed per engineer.

## Rate limiting

Atlassian rate limits Confluence API at the user level (not per page). Our worst case:

- Maximum push cadence: ~1 per 30 seconds (event burst from multiple subagents reporting)
- Sustained push cadence: ~1 per 5 minutes (cycle boundary)
- Both are well under any plausible rate limit

The orchestrator does not need backoff/retry logic for rate limits in v1. If we hit limits in practice, add exponential backoff to push retries.

## What the orchestrator does NOT do

- ❌ Read other Confluence pages, search, or write comments
- ❌ Use Confluence as a queue or message bus
- ❌ Allow subagents to push directly to Confluence
- ❌ Maintain Confluence-specific data not present in `fleet-status.md` (page is a projection only)
- ❌ Push on every subagent JSON report — only on actual fleet-status mutation (event-driven)

## Initial population

The Confluence page is currently empty (version 1, no body, created 2026-05-09 07:11:55 UTC). The first push from the orchestrator will populate it with the current `fleet-status.md` content + the banner. No special bootstrap needed — first push is the same code path as subsequent pushes.

## Failure handling

If the Confluence push fails for any reason (network, auth, server error), the orchestrator:

- Logs to `.claude/logs/confluence-sync.jsonl`
- Continues operating against local `fleet-status.md` only
- Surfaces "Confluence sync failed: <reason>" in the next 5-min digest
- Retries on the next event-driven push trigger

Confluence sync is best-effort. The local file is the source of truth and can never be blocked by Confluence being unreachable.

## Test plan

Before the orchestrator goes live for real trains:

1. Push initial population — confirm the page renders correctly
2. Trigger a fake event (edit fleet-status.md by hand, change one cell) — confirm next push reflects it
3. Make a manual edit on Confluence between pushes — confirm drift detection fires and the human gets a prompt
4. Disconnect from network — confirm orchestrator continues operating against local file and queues the push
5. Reconnect — confirm queued push completes

---

## Amendment 1 — Cable register sync (`--target cables`)

**Status:** v1.1, added 2026-05-09. Companion to [auto-scanner-boundary.md](auto-scanner-boundary.md).

The auto-scanner appends `Status: auto-detected` rows to `cable-issues-register.md`. Engineers promote selected rows to `Status: confirmed` and fill the Stadler-instructions block. The PM reads the resulting register on Confluence to escalate confirmed rows to Stadler. This amendment specifies how that file gets to Confluence.

### Target

The cable register lives on a **separate Confluence page** from the fleet-status page. Page identity:

| Field | Value |
|---|---|
| Cloud ID | `nomad-digital.atlassian.net` |
| Page ID | Stored in `.claude/state/confluence-pages.json` field `cable_register_page_id` |
| Title | `DEL-OBB-035: Train cabling issues register — Stadler escalation tracker` |
| Space ID | `3854893184` (same as fleet-status page) |
| Parent ID | `3859447840` (sibling of fleet-status page) |

The page ID is **not hardcoded** because the page is created on first run by `/dosto-auto-scan --bootstrap-confluence-cables` (see [auto-scanner-boundary.md](auto-scanner-boundary.md) → "Local file writes — `.claude/state/confluence-pages.json`"). All readers of the page ID look up the JSON file.

### `dosto-confluence-sync --target {fleet|cables|both}`

The skill grows a `--target` flag. Default `fleet` preserves existing semantics.

| Target | Source file | Page ID source | Render |
|---|---|---|---|
| `fleet` (default) | `fleet-status.md` | hardcoded `5410684933` (existing) | Existing — full markdown body |
| `cables` | `cable-issues-register.md` | `cable_register_page_id` from `confluence-pages.json` | Two-section render — see below |
| `both` | both | both | Fleet first, then cables. Each is a separate API call with independent drift detection. |

If `--target cables` is invoked and `confluence-pages.json` is missing or has no `cable_register_page_id`, the skill exits with instructions to run `/dosto-auto-scan --bootstrap-confluence-cables` first. It does not attempt to create the page itself — bootstrapping is the auto-scanner's responsibility, not the sync skill's.

### Two-section render for the cable register

The cable register is a flat markdown file with row sections delimited by `---`. The Confluence projection must split rows into two ordered sections by `Status:` field value:

```
[Banner — same auto-sync banner as fleet, plus "PM section: confirmed faults below"]

# Confirmed cabling faults — Stadler escalation tracker

[All rows where Status: confirmed, in original register order, with their Stadler-instructions blocks rendered]

# Auto-detected anomalies — engineer review pending

[All rows where Status: auto-detected, in original register order, showing signal source / first-seen / last-seen / scan count / suggested category. Stadler-instructions block omitted (it's empty by definition).]
```

The split is performed in the sync skill before pushing, by parsing each row's `**Status:**` line. Rows with any other status value (typo, manual experiment) are surfaced as a warning to the engineer and excluded from the push.

### Drift detection — same semantics

Optimistic concurrency, version-mismatch handling, drift logging — all identical to the fleet-status sync per the main contract. The cable-register page has its own version counter independent of the fleet page. Drift on either page is logged separately to `.claude/logs/confluence-drift.jsonl` with a `target: "cables"` field for filtering.

### Push trigger

Unlike the fleet page (orchestrator-driven, event-driven on every cycle), the cable register is **engineer-triggered only** in v1:

- Engineer runs `/dosto-confluence-sync --target cables --push` after promoting `auto-detected` → `confirmed` rows or after writing Stadler-instructions on confirmed rows
- Engineer runs `/dosto-confluence-sync --target both --push` end-of-day to refresh both pages

The auto-scanner does **not** invoke the sync skill — it only writes the local file. This preserves the rule from the main contract: subagents and the auto-scanner never push to Confluence; only the engineer (or future orchestrator) does.

### Failure handling

Same as fleet — best-effort, log to `confluence-sync.jsonl`, continue against local file, retry on next manual invocation. A failed cable-register push does not block the fleet-status push (or vice versa) when `--target both` is used.

### Test plan additions

Beyond the existing 5-step test plan:

6. Bootstrap test — `/dosto-auto-scan --bootstrap-confluence-cables` creates the page, writes the ID to `confluence-pages.json`, second invocation is idempotent (says "already bootstrapped").
7. Two-section render — manually create a register with one `confirmed` row and one `auto-detected` row. Run `--target cables --diff`. Verify the diff shows two sections in the right order.
8. Status-typo handling — manually edit a register row to `Status: investigating` (not in {confirmed, auto-detected}). Run `--target cables --diff`. Verify the row is surfaced as a warning and excluded from the push.
