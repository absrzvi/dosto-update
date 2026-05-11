# Session Handoff — DOSTO Orchestration Build

**Last session:** 2026-05-10 afternoon (Abbas Rizvi) — **Investigated Jira integration question.** Surveyed the EMEA Jira projects, found `EMEAE` (EMEA E Engineering Team) as the active home for DOSTO work, mapped existing ticket conventions and the native `Site visit` issue type. No code changes — produced findings + three options (A/B/C) for how to integrate, recommended waiting on team coordination before creating any new tickets. Earlier 2026-05-10: skill-audit against the [mattpocock skill-writer rules](https://github.com/mattpocock/skills/blob/main/skills/productivity/write-a-skill/SKILL.md), tiered remediation plan. 2026-05-09: Auto-scanner Phase i built; partial Fzg 132 AP firmware push (2 of 6 stuck APs unblocked, train went offline). 2026-05-09 earlier: all 8 build phases done + Karpathy guardrails + 4 robustness items + stage list v2.

**Next session — four open threads in priority order:**

1. **Jira integration decision (NEW, blocked on team coordination)** — see "Jira integration findings" section below. Don't create any new tickets without first checking with Christopher Kemeter / Bahareh Behnam / Davud Zejnelovic about existing per-train tracking conventions in EMEAE. Recommended starting move: Option A (link existing EMEAE tickets in `fleet-status.md` rows). Option B (per-train `Site visit` tickets) and Option C (cable-register escalation tickets) wait on team input.

2. **Skill-audit remediation (Tier 1 + Tier 2 — recommended)** — see "Skill audit remediation plan" below. Pure documentation edit, ~45 min total, no train needed. Two skills have `description` fields over the 1024-char hard limit (`dosto-commission-train` 1081, `dosto-sw-config-update` 1075) — fix first. Then add explicit "Use when [triggers]" phrasing to all 17 skill descriptions for better agent discovery + engineer searchability. **Skip Tier 3** (progressive-disclosure refactor of the 5 largest SKILL.mds into REFERENCE.md / EXAMPLES.md splits) — token-budget gains aren't worth the maintenance churn for our deterministic-stage-routing usage pattern.

3. **Resume Fzg 132 commissioning** — verify `.231` firmware state, push remaining 3 APs (`.237 .238 .240`). Train was offline at end of evening session; come back when cellular returns.

4. **Validate auto-scanner Tier-1 stub against real online train** — once Fzg 132 is reachable, run `python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 --train-num 4736-104 --json` to confirm SSH heredoc works, then 3 cycles with `--inject-test-signal` to confirm debounce → register-row append path on a real laptop session.

**No commissioning code to build — system is feature-complete on the orchestration side.** Auto-scanner Tier-2 + bootstrap come after Monday's validation.

---

## Jira integration findings (2026-05-10 afternoon)

**Question on the table:** Should we create Jira tickets per train, or keep just the Confluence page?

### Why this came up

The Confluence page (5410684933, exec-view layout) is good for "fleet at a glance" but doesn't give us:
- Per-train state machine with explicit transitions
- Assignees / watchers / @mentions for inline discussion
- JQL queries ("all Fzg blocked by Stadler", "all PAUSED > 7 days")
- Stadler-side notification when they close an item we escalated
- Per-train history / audit log

### What we found in Jira

Two relevant projects on `nomad-digital.atlassian.net`:

| Key | Name | Notes |
|---|---|---|
| **EMEAE** | EMEA E Engineering Team | **The active home for DOSTO work.** All recent DOSTO/ÖBB tickets live here. |
| **EMW** | EMEA West Engineering Team | Same schema; not the relevant one for DOSTO. |

EMEAE issue types: Epic, Story, Task, Investigation, **Site visit**, PE rework, PSE rework. The `Site visit` type is described as *"designed to help engineers prepare for site visits and document finds thereafter"* — that's literally what a per-train commissioning visit is. Not currently used for DOSTO commissioning trains; the existing convention is plain `Task` with `DOSTO - <description>` titles.

### Existing DOSTO tickets in EMEAE (as of 2026-05-10)

Recent activity (top 10 by updated):

| Key | Summary | Status | Assignee | Type |
|---|---|---|---|---|
| EMEAE-5665 | DOSTO - update switches with v3 version part 2 | On Hold | Christopher Kemeter | Task |
| EMEAE-5693 | DOSTO - IBS BLOCK 46 | To Do | Christopher Kemeter | Task |
| EMEAE-5664 | DOSTO - update more trains for NMS fix part 7 | To Do | Christopher Kemeter | Task |
| EMEAE-5694 | ÖBB - QBR | To Do | Michael Fehlau | Task |
| EMEAE-5666 | DOSTO - test client isolation on bench | To Do | Christopher Kemeter | Task |
| EMEAE-5594 | DOSTO - test iobstaff on bench once fixed (ticket in desc) | Blocked | Christopher Kemeter | Task |
| EMEAE-5692 | DOSTO - fix switch on 8633015 | Done | Christopher Kemeter | Task |
| EMEAE-5690 | DoSto Neu: IBS changes to template 4734 117 and 4736 102 | To Do | Bahareh Behnam | Task |
| EMEAE-5395 | DoSto Neu: migrate trains on branch | In Progress | Bahareh Behnam | Task |
| EMEAE-4331 | **DEL-OBB-035: Update Technical Description** (label: `Dosto_Neu_[DEL-OBB-035]`) | In Progress | Davud Zejnelovic | Task |

### What this changed about the recommendation

Earlier session said "create one Jira project for cable-register escalations." That recommendation is **wrong** — `EMEAE` exists and is the right home. Don't create a new project.

**Observations from the existing tickets:**

1. **Naming convention is `DOSTO - <task>` or `DoSto Neu: <task>`** — informal, not per-train. Most are batch operations across the fleet ("update switches with v3 version part 2", "update more trains for NMS fix part 7"). Closer to engineering-task tracking than per-train commissioning state.
2. **Existing label convention `Dosto_Neu_[DEL-OBB-035]`** — same delivery code as the Confluence page. Linkage to Confluence is by label.
3. **`Site visit` issue type exists** but isn't currently used for DOSTO commissioning. Designed for exactly this use case but adoption is zero so far.
4. **Status workflow is richer than fleet-status.md's:** `To Do` → `In Progress` → `On Hold` → `Blocked` → `Done`. `On Hold` ≈ our `PAUSED`.
5. **No per-Fzg tickets** for commissioning runs. Either deliberate (because Confluence + fleet-status.md serve that purpose) or just because no one's done it yet — unclear without asking the team.

### Three options for the next session to consider

| Option | What it does | Cost | Pre-req |
|---|---|---|---|
| **A** | Link existing EMEAE tickets in `fleet-status.md` rows. Add a `Jira:` column or just a free-text reference. Zero new tickets created. | Free, immediately useful | None — go ahead |
| **B** | Use native `Site visit` issue type, one ticket per Fzg per commissioning visit. Title: `DOSTO - Fzg 132 commissioning (4736-104)`. Status mirrors our `Status` column. | ~10 min per train; 40 trains = 6-7 hrs of ticket-creation if backfilling everything | **Coordinate with team first** — would create 40 tickets in someone else's project |
| **C** | One EMEAE ticket per row in `cable-issues-register.md`. Stadler-facing, labelled `Dosto_Neu_[DEL-OBB-035]`. Stadler closes them when they fix the underlying cabling. | ~5 min per cable-register row; 5-10 rows currently | **Coordinate with team first** — same reason as B |

**Recommendation:** Option A only, until the next session can ask the team:

- Do Christopher / Bahareh / Davud already have a per-train tracking convention I'm missing?
- Is the absence of per-train tickets deliberate (Confluence + fleet-status.md serve that purpose), or just because no one's done it yet?
- Would creating 40 `Site visit` tickets be welcomed or noisy?
- Who's the right escalation point for the cable register — Stadler-facing tickets visible to which Stadler engineers?

Without those answers, creating tickets in someone else's project is the kind of thing that creates friction even when technically correct.

### How to start the next session on Jira

```
Read handoff.md "Jira integration findings" section. Pick up at: ask Christopher Kemeter / Bahareh Behnam (or whoever is the right escalation point) about the existing per-train tracking convention in EMEAE before creating any new tickets. Then either:
  - implement Option A (link existing tickets in fleet-status.md), OR
  - implement Option B (per-Fzg Site visit tickets) if the team OKs it, OR
  - implement Option C (cable-register escalation tickets) if the team OKs it.
```

The MCP tools to use are already wired up: `mcp__b29e83b2-...__searchJiraIssuesUsingJql`, `__createJiraIssue`, `__editJiraIssue`, `__transitionJiraIssue`, `__getJiraIssueTypeMetaWithFields`, `__addCommentToJiraIssue`. CloudId is `nomad-digital.atlassian.net`.

---

## Skill audit remediation plan

Audit ran 2026-05-10 against [mattpocock's write-a-skill rules](https://github.com/mattpocock/skills/blob/main/skills/productivity/write-a-skill/SKILL.md). Reference rules (paraphrased):

- **R1** — Frontmatter: `description` ≤ 1024 chars, third person, "Use when [triggers]" phrasing in second sentence
- **R2** — SKILL.md body ≤ 100 lines (split to REFERENCE.md / EXAMPLES.md / scripts/ when exceeded)
- **R3** — Structure: Quick start → Workflows → Advanced features (linked out)
- **R4** — Progressive disclosure (depth lives in linked files, not inline)
- **R5** — Concrete examples included, references one level deep, no time-sensitive info, consistent terminology

### Audit results — all 17 skills

| Skill | Lines | Desc chars | Use-when phrase | Quick-start | REFERENCE.md | Hard violations |
|---|---:|---:|---|---|---|---|
| dosto-obn-patches | 651 | 792 | ✗ | ✗ | ✗ | R2 (6.5×) |
| dosto-commission-train | 535 | **1081** | ✗ | ✗ | ✗ | **R1a** + R2 (5.4×) |
| dosto-sw-config-update | 487 | **1075** | ✗ | ✗ | ✗ | **R1a** + R2 (4.9×) |
| dosto-sw-firmware-update | 463 | 799 | ✗ | ✗ | ✗ | R2 (4.6×) |
| dosto-ap-config-update | 390 | 615 | ✗ | ✗ | ✗ | R2 (3.9×) |
| dosto-confluence-sync | 388 | 452 | ✗ | ✗ | ✗ | R2 (3.9×) |
| dosto-fzg-id-check | 380 | 731 | ✗ | ✗ | ✗ | R2 (3.8×) |
| dosto-ap-firmware-update | 355 | 735 | ✗ | ✗ | ✗ | R2 (3.6×) |
| dosto-extract-train-data | 346 | 661 | ✗ | ✗ | ✗ | R2 (3.5×) |
| dosto-vlan7-config | 313 | 650 | ✗ | ✗ | ✗ | R2 (3.1×) |
| dosto-auto-scan | 300 | 579 | ✗ | ✗ | ✗ | R2 (3.0×) |
| dosto-tftp-helper-check | 273 | 774 | ✗ | ✗ | ✗ | R2 (2.7×) |
| dosto-state-inventory | 242 | 484 | ✗ | ✗ | ✗ | R2 (2.4×) |
| dosto-l2-health | 222 | 871 | ✗ | ✗ | scripts/ | R2 (2.2×) |
| dosto-orchestrate | 220 | 444 | ✗ | ✗ | ✗ | R2 (2.2×) |
| dosto-l2-report | 127 | 764 | ✗ | ✗ | scripts/ | R2 (1.3×) |
| dosto-state-inventory | 242 | 484 | ✗ | ✗ | ✗ | R2 (2.4×) |

**Aggregate findings:**
- **R1a (desc ≤ 1024)** — 15/17 pass. Two over: `dosto-commission-train` (1081), `dosto-sw-config-update` (1075).
- **R1b (third person)** — 17/17 pass.
- **R1c (explicit "Use when" phrase)** — **0/17 pass.** Triggers are implicit in narrative, not in the prescribed format.
- **R2 (≤ 100 lines)** — **0/17 pass.** Smallest is `dosto-l2-report` at 127 (1.3× over). Median 350. Largest is `dosto-obn-patches` at 651 (6.5× over).
- **R3 (Quick start section)** — **0/17 pass.** No SKILL.md has a `## Quick start` header.
- **R4 (progressive disclosure)** — 2/17 partial. Only `dosto-l2-health` and `dosto-l2-report` have a `scripts/` companion; **0/17 have REFERENCE.md or EXAMPLES.md**.
- **R5 (concrete examples)** — 17/17 pass. Content is concrete; problem is verbosity, not abstraction.

### Why we're so far off — and why most of it is intentional

The mattpocock writer optimises for **agent discovery + token budget**: agent reads short descriptions, picks one skill, loads a 100-line SKILL.md, follows links for depth. Our skills optimise for **runbook-completeness**: each SKILL.md is a self-contained operational playbook for a high-stakes irreversible CCU operation, written so an engineer can read top-to-bottom in one pass and execute with confidence on a flaky train cellular connection.

These two models trade off:

| | mattpocock model | DOSTO model |
|---|---|---|
| Per-skill main file | 100 lines, terse | 200-650 lines, dense |
| Triggers | "Use when X, Y, Z" keyword list | Implicit in narrative |
| Depth | Linked out (REFERENCE.md, scripts/) | Inline (one document, top-to-bottom) |
| Audience | Agent + engineer | Engineer first, agent second |
| Failure mode | Agent loads wrong skill, or skill is too vague to execute | Wall of text; agent over-reads tokens; harder to maintain |

**The DOSTO model is the right fit** for what these skills do (irreversible CCU operations where context is safety-critical). But we're paying real costs the writer would flag:
- **Token cost on every invocation.** Median 350 lines × ~4 tokens/line ≈ 1,400 tokens per skill load. A commissioning session with 5-10 skill invocations = 7-14k tokens of skill text alone.
- **Two desc-overruns** (`dosto-commission-train` 1081, `dosto-sw-config-update` 1075). Hard rule, easy fix.
- **Maintenance load.** Every guardrail / Post-Flight / v2-stage-list change rippled through every long skill. A REFERENCE.md split would have isolated those edits.

### Three-tier remediation plan

**Tier 1 — fix hard rule violations (15 min, no judgement)**
- Trim `dosto-commission-train` description: 1081 → ≤ 1024 chars
- Trim `dosto-sw-config-update` description: 1075 → ≤ 1024 chars

**Tier 2 — add explicit trigger phrasing (30 min, helps engineers + agents)**
- Add `Use when the user says <X>, mentions <Y>, or <Z scenario>` to each of the 17 skill descriptions
- Source material: each skill's existing "When to use" section already has the trigger list; just promote it into the description
- Helps when several skills could plausibly apply (e.g. `dosto-ap-firmware-update` vs `dosto-ap-config-update` — both Westermo-AP, both push-shaped); explicit triggers disambiguate
- Validator R1c-style check could be added to `scripts/validate_dosto_workspace.py` later if we want enforcement

**Tier 3 — progressive disclosure refactor (3-5 hours, skip recommended)**
- For the 5 largest skills (`dosto-obn-patches`, `dosto-commission-train`, `dosto-sw-config-update`, `dosto-sw-firmware-update`, `dosto-ap-config-update`):
  - Trim SKILL.md to ~100-150 lines: frontmatter + Quick start (one paragraph) + Workflows (2-3 step checklist) + When to use + What this skill does NOT do
  - Move per-stage detail blocks, JSON-shape examples, edge-case tables, validation history → `REFERENCE.md`
  - Move worked examples (Fzg 132/133 case studies, recipe templates) → `EXAMPLES.md`
- The smaller 8 skills (under 250 lines) stay as-is

**Recommendation: Tier 1 + Tier 2 only.** Skip Tier 3.

Reasoning: the DOSTO skills are not competing with each other in an agent's selection step — they're commissioning-domain skills the orchestrator/subagent stack invokes deterministically based on stage, not on description-keyword match. The writer's "agent decides which skill to load" optimisation doesn't apply to most invocations. Token cost is real but not painful at current usage. The dense one-document runbook shape is genuinely the right model for irreversible CCU operations. Tier 3 is theoretically right but practically a lot of churn for token-budget gains we don't currently feel.

### How to start the next session

```
Read handoff.md "Skill audit remediation plan" section. Apply Tier 1 + Tier 2 to all 17 skills:
  - Tier 1: fix the two desc overruns (dosto-commission-train 1081→≤1024, dosto-sw-config-update 1075→≤1024)
  - Tier 2: add an explicit "Use when..." sentence to each of the 17 skill descriptions
After: run python scripts/validate_dosto_workspace.py to confirm 9/9 still pass, then python scripts/regenerate_bootstrap.py to refresh the bootstrap.
```

That prompt + the audit table above is enough context for a fresh session to do the work mechanically.

---

## What changed in the 2026-05-09 night session (auto-scanner Phase i)

### Goal
Unattended scheduled scanner (default 30 min via Windows Task Scheduler) that probes the fleet for cabling issues and surfaces them to the PM via Confluence for Stadler escalation. Two-tier model: cheap Tier-1 reachability probe every cycle, full Tier-2 diagnostic on transitions or 24h forced rescan. Critical design rule: **scanner is a third writer with strict write boundaries; never auto-promotes auto-detected → confirmed; engineer is the only writer of confirmed cable-register rows.**

### Built (contracts + skills + Python driver + applied fleet-status migration)

| Component | Path | Status |
|---|---|---|
| New contract — write boundaries, signal hashing, debounce, two-section render rule, mutex with orchestrator | `.claude/contracts/auto-scanner-boundary.md` | ✅ Drafted |
| Confluence-sync contract Amendment 1 — `--target {fleet\|cables\|both}`, separate cable-register page lookup via `.claude/state/confluence-pages.json` | `.claude/contracts/confluence-sync.md` | ✅ Updated |
| New skill — runbook for the scanner: tier model, modes, allowlist enforcement, bootstrap mode spec | `.claude/skills/dosto-auto-scan/SKILL.md` | ✅ Drafted |
| Confluence-sync skill — extended with `--target` flag and two-section render rule | `.claude/skills/dosto-confluence-sync/SKILL.md` | ✅ Updated |
| L2-health skill — added `--stadler-trunks-only` scoped mode (~30–60s subset, used by scanner Tier-2) | `.claude/skills/dosto-l2-health/SKILL.md` | ✅ Updated |
| Python driver — Tier-1 reachability + 4-fact SSH state heredoc + signal hashing + 3-scan debounce + atomic-write mtime guard + lockfile mutex | `scripts/dosto_auto_scan.py` | ✅ Built (~400 lines) |
| One-shot helper — extended fleet-status.md with 3 new auto-scanner columns | `scripts/add_auto_scan_columns.py` | ✅ Built and run (44 rows extended on 4736 + 4734 tables) |
| New directory for scanner state | `.claude/state/` | ✅ Created |

### Verified end-to-end with injected test signal

Used `--inject-test-signal "missing_ap=.240/lldp=D3.e1-4"` to exercise the full path without needing a real cable fault:

| Behaviour | Verified |
|---|---|
| Lock file mutex + orchestrator-lock detection | ✅ |
| `--status` mode | ✅ |
| Tier-1 reachability probe (negative case via TEST-NET 192.0.2.1) | ✅ |
| Stable signal hashing across runs | ✅ (sha1 short hash, deterministic) |
| 3-scan debounce graduating to register-row append on cycle #3 (state persists in `auto-scan-state.json`) | ✅ |
| `Auto-detected issues` column flipped from `—` to `1` after register write | ✅ |
| Allowlist enforcement: only target column changed; all 16 other cells in row 132 byte-identical | ✅ |
| Atomic write via `.tmp + rename` | ✅ |
| Append-only to cable-issues-register.md (existing content preserved byte-identical) | ✅ |
| Cleanup — test-injected register row removed; auto-scan-state.json removed; fleet-status.md backup deleted (column extension kept) | ✅ |

### Key contract decisions (locked-in 2026-05-09)

- **3-scan debounce** before drafting a `Status: auto-detected` register row (~90 min from first detection at 30-min cadence)
- **No auto-promote ever** — engineer flips `auto-detected` → `confirmed` manually before Stadler escalation
- **24h forced-rescan** on otherwise-stable trains catches slow-developing CRC trends
- **`--max-tier-2-trains 8`** per cycle to bound budget (selection priority: transitions first, then drift, then forced 24h rescan oldest-first)
- **Mutex with `/dosto-orchestrate`** via `.claude/state/orchestrator.lock` (60-min stale window)
- **Separate Confluence page** for cable register (bootstrap mode creates it; ID stored in `.claude/state/confluence-pages.json`)
- **Two-section Confluence render**: Confirmed faults (PM-actionable, escalates to Stadler) above; Auto-detected anomalies (engineer-review, never seen by Stadler) below
- **fleet-status.md write allowlist**: scanner may write only `Last reachable`, `Last auto-scan`, `Auto-detected issues`. Forbidden writes detected via diff inspection before file replace (raises `AllowlistViolation`).
- **cable-issues-register.md write rule**: append-only, `Status: auto-detected` only; never edits `confirmed` rows; never writes Stadler-instructions block; never deletes; never reorders.

### What's NOT built (deferred — explicitly waiting for Monday's real-train test)

1. Real `dosto-state-inventory` invocation (currently 4-fact heredoc stub: uptime, hostname, vlan7, NDSU rename)
2. Tier 2 diagnostic — `dosto-device-discovery` + `lldp_topology_check.py` + `dosto-l2-health --stadler-trunks-only`
3. Multi-train cycle (single-Fzg per invocation right now; cycle-driver loop deferred)
4. Per-Fzg filtering on `count_auto_detected_for_fzg` (currently total auto-detected count across file — stub note in code)
5. `--bootstrap-confluence-cables` mode (creates the cable-register Confluence page via `createConfluencePage`; needs Claude in the loop for the Atlassian connector)
6. **`BOOTSTRAP_AUTO_SCAN_v1.md` + `scripts/regenerate_bootstrap_auto_scan.py`** — separate-file layered bootstrap with explicit "run BOOTSTRAP_DOSTO_v1.md first" prerequisite. Engineer recommendation chosen but waiting for Monday's test before committing the bootstrap (so it captures the working version, not the theoretical one).
7. `validate_dosto_workspace.py` extension — cross-check that no row in `cable-issues-register.md` was scanner-written with `Status: confirmed`
8. Windows Task Scheduler entry to actually fire the cycle every 30 min

### Files touched this session

**New:**
- `.claude/contracts/auto-scanner-boundary.md`
- `.claude/skills/dosto-auto-scan/SKILL.md`
- `scripts/dosto_auto_scan.py`
- `scripts/add_auto_scan_columns.py`
- `.claude/state/` (new directory)
- auto-memory entry: `project_auto_scanner_build.md` + MEMORY.md row

**Modified:**
- `fleet-status.md` (3 new columns appended to both 4736 and 4734 tables — 44 rows extended; orchestrator-owned and engineer-owned columns untouched)
- `.claude/contracts/confluence-sync.md` (Amendment 1 added at end)
- `.claude/skills/dosto-confluence-sync/SKILL.md` (modes table extended with `--target`)
- `.claude/skills/dosto-l2-health/SKILL.md` (`--stadler-trunks-only` mode added)

### Monday auto-scanner resume command

After Fzg 132 commissioning resumption is complete (or in parallel if it's offline-waiting), validate the scanner against a real CCU:

```bash
# 1. Single live cycle — should report reachable=true and write Last reachable cell
python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 --train-num 4736-104 --json

# 2. Three cycles with injected signal — should append Row #N (auto-detected) on cycle 3
for i in 1 2 3; do
  python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 --train-num 4736-104 --json \
    --inject-test-signal "missing_ap=.240/lldp=D3.e1-4"
done

# 3. Verify
grep "^| 132 " fleet-status.md   # Last reachable + Auto-detected issues should be populated
tail -20 cable-issues-register.md   # should show test-injected Row at the bottom

# 4. Cleanup test artefacts before Monday
# (manually delete the auto-detected test row from cable-issues-register.md
#  and reset Auto-detected issues column in fleet-status.md row 132 to —)
rm -f auto-scan-state.json
```

Things to watch for in the real run that the synthetic test couldn't catch:
- SSH heredoc behaviour on a slow cellular link (may need timeout > 15s)
- Whether `ip -br addr show vlan7` returns clean output or unexpected stderr
- fleet-status.md mtime resolution on Windows (NTFS uses 100ns ticks but Python's `os.stat` may round)
- Whether the `developer` user's SSH session triggers any password prompt despite `BatchMode=yes` (would hang the scanner — should be impossible with key auth, but cellular networks have introduced surprises before)

If those four behave as expected, Tier-2 expansion + bootstrap can be built next session with confidence.

---

## What changed in the 2026-05-09 late evening session

### Per-train work
- **Fzg 132 partial AP firmware push.** Started run via the new `dosto-train-worker` subagent + `dosto-commission-train` skill (full real-run validation). Stage routing worked end-to-end: stage 1 → Gate 5 (`continue_full`) → stage 11 → Gate 4 (`approved`) → stage 17 (was old single-stage AP firmware).
  - ✅ AP `.226` (AP2m-v1): 6.10.0-0 → 6.11.2-0 in 143s
  - ✅ AP `.230` (AP1m-v1): 6.10.0-0 → 6.11.2-0 in 636s (activation reboot at t+334s, completed at t+636s)
  - 🟡 AP `.231` (AP3m-v1): RRQ at t+12s, activation reboot at t+334s, **cellular outage at t+919s, indeterminate state**. `obn validate` last showed `6.10.0-0 (6.11.2-0) ✗` (staged-but-not-activated). May have completed offline.
  - 🔴 AP `.237 .238 .240`: not attempted before train went offline.
- **TFTP CT helper runtime fix applied** (in-memory only) at 15:40 UTC. Validated by 3 consecutive successful RRQs (`.226`, `.230`, `.231`).
- **2 dosto-ap-firmware-update skill bugs found and fixed.** (1) `snmpget` precondition too strict → false-positive factory-config verdict. Fix: trust `obn discover`/`/tmp/discovery.json` instead, fall back to `snmpget -t 8 -r 2`. (2) `journalctl --since` rejects ISO-8601 with `+00:00` offset → false-positive "no RRQ in 60s". Fix: use `date +"%Y-%m-%d %H:%M:%S"` instead.

### System build (all 8 phases complete)

| Phase | Status |
|---|---|
| 1. Contracts (4 files) | ✅ Done — pre-existing |
| 2. Skills + `--json` retrofit | ✅ Done — pre-existing |
| 3. End-to-end manual on box1-t10 | ✅ Done — pre-existing |
| 4. `dosto-train-worker.md` subagent definition | ✅ Done — pre-existing |
| 5. `dosto-orchestrator.md` agent + `dosto-orchestrate` bootstrap skill | ✅ **Built this session** |
| 6. Confluence integration (`dosto-confluence-sync`) + initial population (page 5410684933 v2) | ✅ **Built this session** |
| 7. CLAUDE.md orchestration architecture section | ✅ **Built this session** |
| 8. Bootstrap (`BOOTSTRAP_DOSTO_v1.md` + `scripts/regenerate_bootstrap.py`) | ✅ **Built this session** |

### Karpathy guardrails (4 added)
- **CLAUDE.md "Universal Principles" section** — 5 principles (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution, Parallelize When Independent) as constitutional rules sitting alongside per-train safety rules. Source: https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md
- **MANDATORY PRE-FLIGHT BLOCK** added to both agent definitions (orchestrator emits structured assumptions+open questions+simplicity check+success criteria before spawning; subagent emits a Pre-Flight JSON report before invoking commission-train)
- **Fleet-status fields allowlist** in orchestrator definition (Surgical Changes — orchestrator may write only the 8 enumerated columns; any other field is a contract violation logged to `orchestrator-errors.jsonl`)
- **Per-train success-criteria checkboxes** in orchestrator end-of-day report (Goal-Driven — engineer commits to verifiable criteria at Pre-Flight, must tick ✓/✗/? at end-of-day)

### R1+R3+R4+R5 robustness items
- **R1 — Post-Flight rendered-output verification** added to `dosto-fzg-id-check`, `dosto-vlan7-config`, `dosto-obn-patches --persist`. Each skill now verifies the *rendered output downstream consumers depend on* (rendered switch hostnames via `obn validate -t sw`, live `vlan7@bond0` IP + Stadler FW reach via `nc -zv`, OBN runtime cleanliness via discover-exit-0 + log-traceback-count). Stage 10 `post_reboot_verify` calls `--post-flight` mode of all three. Catches the Fzg 133 cascade class of failure.
- **R3 — `dosto-state-inventory` skill (NEW)** — fast aggregate sanity check (12 facts, one SSH heredoc, ~5s) called at start of stage 1. Detects state drift since last session (TFTP helper rule lost on reboot, btrfs subvol rolled back, train_id template silently regressed, vlan7 changed, NDSU rename undone). Wired into `dosto-commission-train` stage 1 as the first sub-step.
- **R4 — `scripts/validate_dosto_workspace.py` (NEW)** — 9-check cross-reference linter (stage IDs, gate names, fields allowlist, skill references, agent references, Confluence page ID, schema_version in skill-output examples, agent frontmatter, skill frontmatter). Caught two real bugs on first run: (a) `dosto-extract-train-data` had `name: dosto-extract-train-pdf` in its frontmatter (frontmatter ↔ directory mismatch), (b) CLAUDE.md had `dosto-sw-{config,firmware}-update` brace-expansion shorthand (ambiguous). Both fixed. Now 9/9 PASS.
- **R5 — Three engineer-ergonomic guards.** (i) `dosto-commission-train` pre-stage-1 input cross-validation: hostname (`box1-tNN` matches CCU IP) + Fzg ↔ train-number formula match. Catches the "wrong train" footgun. (ii) `dosto-confluence-sync --push` stale-source guard: halts if `fleet-status.md` mtime > 24h, with `--allow-stale` override. (iii) Orchestrator cycle digest emits `⚠️ Approvals waiting > 10 min` line for each approval queued past one cycle.

### Stage list v2 (canonical pipeline reordered)
**Pipeline went from 19 to 21 stages.** Per "highest-value-first under power-off risk" principle:

| # | Stage | Change |
|---|---|---|
| 11 | `obn_discover_initial` | unchanged |
| 12 | Gate 3 (`obn_update_c`) | now covers SW config + final AP config refresh |
| **13** | **`push_switch_config`** | **Highest-value device push — Stadler IPs land first** |
| 14 | `obn_discover_post_sw_config` | renamed from `obn_discover_post_config` |
| 15 | Gate 4 (`obn_update_f`) | now covers SW firmware + AP firmware |
| **16** | **`push_switch_firmware` (NEW)** | split from old combined `push_ap_firmware` two-phase form |
| **17** | **`ap_factory_bypass` (MOVED)** | was after `obn_discover_initial`; now between SW firmware and AP firmware (logically: bypass exists to make factory APs OBN-reachable for the firmware push that follows) |
| **18** | **`push_ap_firmware`** | unchanged conceptually; now stage 18 |
| **19** | **`push_ap_config` (NEW)** | final AP config refresh — catches firmware-induced config drift on Nomad APs |
| 20 | `final_l2_health_check` | renumbered from 18 |
| 21 | `generate_report` | renumbered from 19 |

Migration: subagents emitting v1 stage IDs are still accepted by the orchestrator but flagged as `schema_version_drift`. Validator's `CANONICAL_STAGE_IDS` updated to the v2 list (22 entries including `done` terminal).

### Confluence page (5410684933) layout polished
v2 pushed initial population (markdown 14-column tables, horizontal scroll on standard screens — unreadable). v3 attempted exec-tables + collapsible full table — `<details>` silently stripped by Confluence's markdown renderer; full tables sat flat below the exec tables (worse than v2). v4 settled on **exec-view-only** (5-col tables for both 4736 and 4734 series), with a banner pointing to `fleet-status.md` for full detail. Two findings logged in skill spec:
- `contentFormat: "html"` is rejected at validation despite the connector tool description suggesting it works.
- `<details><summary>` is silently stripped in markdown mode.

If embedded HTML elements ever become a hard requirement, the path is ADF JSON composition, not markdown-with-inline-HTML.

### Files touched this session

**New:**
- `.claude/agents/dosto-orchestrator.md` (Phase 5)
- `.claude/skills/dosto-orchestrate/SKILL.md` (Phase 5 bootstrap)
- `.claude/skills/dosto-confluence-sync/SKILL.md` (Phase 6)
- `.claude/skills/dosto-state-inventory/SKILL.md` (R3)
- `BOOTSTRAP_DOSTO_v1.md` (Phase 8 — generated)
- `scripts/regenerate_bootstrap.py` (Phase 8)
- `scripts/validate_dosto_workspace.py` (R4)
- `.claude/logs/confluence-sync.jsonl` (Phase 6)

**Modified:**
- `CLAUDE.md` (orchestration architecture section, Universal Principles section, bootstrapping section, folder layout updates)
- `.claude/agents/dosto-train-worker.md` (Pre-Flight, stage IDs renumbered for v2)
- `.claude/skills/dosto-fzg-id-check/SKILL.md` (Post-Flight, name in frontmatter unchanged but content references)
- `.claude/skills/dosto-vlan7-config/SKILL.md` (Post-Flight)
- `.claude/skills/dosto-obn-patches/SKILL.md` (Post-Flight)
- `.claude/skills/dosto-commission-train/SKILL.md` (input cross-validation, stage list v2 — 19→21 stages, all per-stage detail blocks renumbered)
- `.claude/skills/dosto-ap-firmware-update/SKILL.md` (snmpget + journalctl fixes)
- `.claude/skills/dosto-extract-train-data/SKILL.md` (name in frontmatter fixed: was `dosto-extract-train-pdf`, now matches directory)
- `.claude/contracts/subagent-report.md` (Commissioning stage list v2)
- `fleet-status.md` (Fzg 132 row + per-train notes updated for end-of-session state)
- `auto-memory entry: project_dosto_ap_firmware_skill_bugs.md` (the two skill bugs)

---

## Monday continuation plan — Fzg 132 + auto-scanner validation

**Two parallel tracks Monday.** Track A (Fzg 132 commissioning resumption) is the primary; Track B (auto-scanner Tier-1 stub validation) piggybacks on Track A using the same online train.

Track B is small (~15 min total, mostly waiting). Run it after Track A's `dosto-state-inventory` confirms the CCU is reachable and stable, before the AP firmware pushes start (so the scanner doesn't see mid-firmware-push state). Cleanup test artefacts before any push.

### Track A — Fzg 132 commissioning resumption

The train is offline as of 2026-05-09 ~16:21 UTC. Resume when cellular returns.

### Step 1 — verify CCU state at start of session

Open a fresh Claude Code session (or the orchestrator). The `dosto-state-inventory` skill is the canonical first probe — it'll surface drift since 2026-05-09:

```
/dosto-commission-train --ccu-ip 10.179.10.1 --fzg 132 --train-number 4736-104 --consist 6-car --resume push_ap_firmware
```

That'll re-run stage 1 (which now includes `dosto-state-inventory` as the first sub-step) and confirm:
- 8/8 OBN patches still persisted
- vlan7, train_id, NDSU rename all intact
- **TFTP CT helper rule presence** — if absent (CCU rebooted during outage), the runtime fix needs re-applying first

### Step 2 — re-apply TFTP helper if needed

If state-inventory reports `tftp_ct_helper_rule: missing`:

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@10.179.10.1
sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp -m comment --comment "TFTP conntrack helper for in.tftpd (runtime fix)"
```

### Step 3 — verify AP `.231`

```
sudo obn discover
sudo jq -r '.[] | select(.ip=="10.179.10.231") | .firmware' /tmp/discovery.json
```

- If output is `6.11.2-0` → AP completed offline, mark `.231` ✅
- If output is `6.10.0-0` → still staged, force-reboot to activate:
  ```bash
  sshpass -p NomadComeIn ssh -o StrictHostKeyChecking=no nomad@10.179.10.231 reboot
  sleep 90
  # then re-poll obn discover after 5 more minutes
  ```

### Step 4 — push remaining 3 APs serially

Use the `dosto-ap-firmware-update --execute` skill (with the snmpget + journalctl fixes that landed this session) one AP at a time:

```
/dosto-ap-firmware-update 10.179.10.1 10.179.10.237 --execute --json
# wait for completion (5-15 min)
/dosto-ap-firmware-update 10.179.10.1 10.179.10.238 --execute --json
# wait for completion
/dosto-ap-firmware-update 10.179.10.1 10.179.10.240 --execute --json
```

If running via the orchestrator, just resume the subagent at `push_ap_firmware` — it'll iterate the remaining-AP list automatically.

### Step 5 — close out

After all 23 visible APs (everything except D4) are at `6.11.2-0`:

1. Update `fleet-status.md` row 49: AP firmware = `23/24 ✅ on 6.11.2-0` (D4 still missing — Stadler item).
2. `/dosto-confluence-sync --push` to refresh team page.
3. Status remains `BLOCKED w/ Stadler` (D4 cable) until Stadler completes register row #5. Don't run `/dosto-l2-health` for the customer baseline yet — it'd capture an incomplete L2 fabric.

Total wall time estimate: 30-60 min depending on cellular stability and whether `.231` needs force-reboot.

### Track B — Auto-scanner Tier-1 stub validation

Run **after** Track A Step 1 (CCU confirmed reachable + state-inventory clean) but **before** any AP firmware push starts. ~15 min wall time. If anything blocks Track A, defer Track B to a later session — it's a build-validation task, not commissioning-critical.

#### Step 1 — single live cycle

```bash
cd C:/Users/AbbasRizvi/Documents/dosto-troubleshooting
python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 --train-num 4736-104 --json
```

Expected JSON output: `reachable: true`, `state_probe_ok: true`, `fleet_status_write: applied`. Then verify:

```bash
grep "^| 132 " fleet-status.md   # 'Last reachable' column should now have a UTC timestamp
cat auto-scan-state.json | python -m json.tool   # should show train 132 with last_reachable_utc set
```

If `state_probe_ok: false`, look at `.claude/logs/auto-scan-errors.jsonl` for the SSH stderr. Most likely cause on a slow cellular link: heredoc timeout > 15s. Bump `ssh_probe(..., timeout=30)` in `dosto_auto_scan.py` if needed.

#### Step 2 — three cycles with injected signal (debounce + register-write path)

```bash
for i in 1 2 3; do
  echo "=== cycle $i ==="
  python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 --train-num 4736-104 --json \
    --inject-test-signal "missing_ap=.240/lldp=D3.e1-4"
done
```

Expected progression:
- Cycle 1: `action: debouncing, scan_count: 1`
- Cycle 2: `action: debouncing, scan_count: 2`
- Cycle 3: `action: appended, scan_count: 3` — and `cable-issues-register.md` should have a new `Row #N — auto-detected` block at the bottom

Verify the file writes:

```bash
tail -20 cable-issues-register.md   # should show test-injected Row at bottom with Status: auto-detected
grep "^| 132 " fleet-status.md      # 'Auto-detected issues' column should now show 1
```

#### Step 3 — cleanup before any further commissioning work

Track A's commissioning will reboot the CCU and might write to fleet-status.md elsewhere. Clear the test artefacts before that runs:

```bash
# Delete the test-injected Row (find the row number from Step 2 verify) — open
# cable-issues-register.md in editor, delete the '---' + '## Row #N — auto-detected ...'
# block at the bottom (and only that block).

# Reset the Auto-detected issues column in row 132 — the easy way is to revert
# auto-scan-state.json and let the next real cycle recompute it:
rm -f auto-scan-state.json

# Optional: hand-edit fleet-status.md row 132 'Auto-detected issues' cell back to '—'
# if you want it visually clean immediately. The next scanner cycle would do this
# automatically after the test row is removed, but Track A doesn't run the scanner.
```

#### Step 4 — what to capture for the next session

Whether Track B passed or failed, note the following for next session's expansion to Tier 2:

- Wall time for the SSH heredoc on real cellular (the synthetic test was instant; cellular reality matters for `--max-tier-2-trains` budget calibration)
- Any unexpected stderr lines from `lightweight_state_probe` (the probe parses raw output naively; surprises here inform whether to bring forward the full `dosto-state-inventory` integration vs. keeping a stub)
- fleet-status.md write durability (any reports of `fleet_status_write_conflict` in `auto-scan-errors.jsonl` would mean the mtime guard needs tuning for Windows NTFS)

Track B success criteria for a green light on Tier-2 + bootstrap build:

- ✅ All three cycles completed cleanly (no SSH timeouts, no allowlist violations, no write conflicts)
- ✅ Cycle 3 appended a register row with the right hash and structured fields
- ✅ Cleanup left fleet-status.md and cable-issues-register.md byte-identical to pre-test state (modulo the column extension which stays)

If any of those fail, fix the bug in `dosto_auto_scan.py` before building Tier 2.

---

## Below this line: state from earlier 2026-05-09 sessions (preserved for context)

The pre-evening-session content of this handoff (Phase 4 dry-run validation on box1-t47, the original "what changed in the morning" sections) has been superseded by the work above. Kept here for forensic reference only.

---

## What changed in the 2026-05-09 evening session

### Built (Phase 4 + parts of Phase 5 of the original plan)

All seven items from the original "What to do next" list are done:

| # | Component | Path |
|---|---|---|
| 1 | Updated `dosto-obn-patches` for `.dont` rename detection + `/var/tmp` chroot bind-mount | `.claude/skills/dosto-obn-patches/SKILL.md` |
| 2 | New `dosto-fzg-id-check` skill | `.claude/skills/dosto-fzg-id-check/SKILL.md` |
| 3 | New `dosto-tftp-helper-check` skill | `.claude/skills/dosto-tftp-helper-check/SKILL.md` |
| 4 | `dosto-obn-patches --persist` fold-in mode (single-promote pattern) | same skill, extended |
| 5a | New `dosto-ap-firmware-update` skill (the trickiest — RRQ verification, stuck-state recovery, 15-min poll) | `.claude/skills/dosto-ap-firmware-update/SKILL.md` |
| 5b | New `dosto-ap-config-update` skill (auto-detects Nomad vs factory, OBN SNMP vs LuCI HTTP) | `.claude/skills/dosto-ap-config-update/SKILL.md` |
| 5c | New `dosto-sw-firmware-update` skill (leaf-first OBNTree, RSTP convergence check) | `.claude/skills/dosto-sw-firmware-update/SKILL.md` |
| 5d | New `dosto-sw-config-update` skill (config push always reboots, verify_reboot_started fail-fast) | `.claude/skills/dosto-sw-config-update/SKILL.md` |
| 6 | New `dosto-commission-train` orchestration skill (19-stage pipeline, gate routing, single-promote fold-in, --resume, --dry-run) | `.claude/skills/dosto-commission-train/SKILL.md` |
| 7 | New `dosto-train-worker` subagent definition (model: claude-sonnet-4-6, strict-JSON output, 4 gates + 1 three-way) | `.claude/agents/dosto-train-worker.md` |

What's NOT built:
- 🔴 **Phase 5 top-level orchestrator** (the thing that spawns N per-train subagents in parallel and aggregates)
- 🔴 **Phase 6 Confluence integration** (page `5410684933` is empty; no programmatic writes yet)
- 🔴 **Automatic fleet-status writer** (orchestrator-side; subagents emit deltas but no code applies them)
- 🔴 **Automatic cable-register-writer** (same shape as fleet-status writer)

### Dry-run validation on box1-t47 / Fzg 130

Ran `dosto-commission-train --dry-run` against `10.179.47.1` to validate the skill stack against a real CCU. Surfaced 2 skill bugs (now fixed) + 1 architectural gap (now closed) + the actual current state of Fzg 130:

**Skill bugs found and fixed:**

1. **`dosto-fzg-id-check` SSH heredoc had a broken awk parser** (`grep -lc | awk -F:`). On this CCU image, `grep -lc` emits filename-only output (no `path:count`), so awk -F: saw `$2` empty and `BROKEN_FILE_COUNT` always reported 0. Real count was 18; reported 0. **Fixed**: switched to `grep -l ... | wc -l` direct pipe.

2. **`dosto-obn-patches` and `dosto-commission-train` NDSU detection used `[ -x ]`** which returns false for the `developer` SSH user on the fleet's `nd-systemupdate.sh.dont` file (mode 0500 owner=root). The file works fine via `sudo` but `-x` returned false. **Fixed**: switched to `[ -f ]` (regular file exists). Validated against box1-t47 — correctly returns `NDSU=/usr/sbin/nd-systemupdate.sh.dont`.

3. **Architectural gap closed**: added `nd_systemupdate_missing` terminal-block verdict to `dosto-commission-train` stage 1 routing, so a future train with both NDSU files genuinely missing halts cleanly at stage 1 instead of trying to enter a chroot that doesn't exist. Validated by the false-alarm scenario above (which the corrected `-f` test now handles).

**Real state of box1-t47 / Fzg 130 (corrected after the `-x` fix):**

- 🔴 OBN 0/8 (vanilla)
- 🔴 broken `train_id` template (`128 + train_id`, all 18 templates), backbone-discovery train_id=47 → renders 175 everywhere
- 🔴 vlan7 wrong (`172.19.215.130/17`, encodes Fzg 175, expected `172.19.193.2/17`)
- 🔴 TFTP helper missing (both module + rule)
- ✅ NDSU=`.dont` (fleet-standard, auto-update blocked) — CHROOT MECHANISM IS FINE
- 🔴 3 switches missing from primary consist (E2, E3, F2) — Stadler issue
- 🟡 Coupled second consist visible (3 v5-man neighbour switches at .187, .189, .195)
- 🟡 24 APs visible but all plain `AP1-v1`/`AP2-v1`/`AP3-v1`/`AP4-v1` (6 each), zero `m-` variants — render anomaly, will resolve post-commissioning

**Fleet-status diff for Fzg 130 prepared but NOT applied** (orchestrator-as-sole-writer; engineer applies by hand):

- Update table row 47 to reflect 15/18 switches (E2,E3,F2 missing), `**PAUSED**` status, "runs at Gate 5 → partial" next-action
- Replace the per-train notes section (lines 106-136) with the 4-issue analysis (3 CCU-side fixable in one chroot fold-in + 1 Stadler-side switches missing + coupled-consist warning)

The full diff text is in the prior session's chat transcript; if you need it regenerated, ask me to run `dosto-commission-train --dry-run --ccu-ip 10.179.47.1 --fzg 130 --train-number 4736-102 --consist 6-car` again.

## Resumption plan — REAL RUN on Fzg 132 / box1-t10

### Why Fzg 132 (not Fzg 130)

Both trains have BLOCKED states, but for different reasons. Fzg 132 is the better real-run validation target because:

- **CCU is fully commissioned** — OBN persisted, vlan7 correct, train_id 132 hardcoded, all 18 switches at 7.4.2 + v8 config. Stages 3-15 all skip because there's nothing to do.
- **Has 6 APs in stuck-state** (per fleet-status row 49: `.237 .240 .238 .231 .230 .226` stuck on 6.10.0-0). Real exercise of `dosto-ap-firmware-update --execute`'s stuck-state detection + SSH-reboot recovery (lessons 13-14).
- **Gate 5 (D4 missing) and Gate 4 (firmware push) both fire** — exercises both binary and three-way gate flows.
- **Failure mode is bounded** — per-AP serial pushes; if one fails, others untouched.

### What you authorised in the 2026-05-09 evening chat

1. ✅ OK with pushing firmware to the 6 stuck APs while D4 missing (mixed-state risk for D4 is acceptable since D4 is just one AP, not a switch).
2. ✅ OK with Gate 5 → `continue_full` (overrides the contract's recommended `partial` default — explicit engineer judgment that AP firmware push doesn't depend on D4).
3. ✅ Subagent does the SSH driving (per `dosto-ap-firmware-update --execute`'s state machine), engineer at gates only.

### Resumption plan structure

**The next Claude session acts as the `dosto-train-worker` subagent.** Single session. No top-level orchestrator (Phase 5 not built — out of scope for this validation).

The next session's job:
1. Load `.claude/agents/dosto-train-worker.md` as its system prompt.
2. Receive the starting prompt (below) which contains the train args.
3. Invoke `/dosto-commission-train --ccu-ip 10.179.10.1 --fzg 132 --train-number 4736-104 --consist 6-car`.
4. Stream the JSON output verbatim to the human (per the subagent's strict-JSON rule).
5. When a gate fires, halt; human reads JSON; human responds with the gate-response JSON shape (`{"response": "approved"}` for binary, `{"response": "continue_full"}` for Gate 5).
6. Subagent re-invokes `/dosto-commission-train --resume <next_stage_id>`.
7. Continue until `status: DONE` or `status: BLOCKED`.

### Expected gate sequence on Fzg 132

| Stage | Gate | Expected response |
|---|---|---|
| 2 | Gate 5: `device_count_mismatch` (D4 AP missing) | `continue_full` (per pre-authorisation) |
| 16 | Gate 4: `obn_update_f` (6 APs need firmware update) | `approved` |

That's it. Stages 3-15 all skip (CCU-side fixes already done; switch firmware/config already at target). Stage 17 iterates the 6 stuck APs serially via `dosto-ap-firmware-update --execute`. Stage 18 final L2 health check. Stage 19 generate report.

Total expected wall time: ~60-90 min (6 APs × 6-15 min each, single-AP serial). Expect at most 2 stuck-state recoveries (Gate 2 within `dosto-ap-firmware-update`'s state machine) needing engineer ack.

### Validation outcomes to look for

- ✅ Subagent loads correctly, JSON-only output, no prose leaks
- ✅ `dosto-commission-train` walks stages cleanly, conditional skips work
- ✅ Gate 5 three-way response handled correctly
- ✅ `dosto-ap-firmware-update --execute` drives a real push end-to-end
- ✅ RRQ verification fires (lesson 12 — journalctl `RRQ from <ap-ip>`)
- ✅ Stuck-state detection + SSH-reboot recovery works on the 6 stuck APs
- ✅ 15-min poll completion (lesson 14)
- ✅ Fresh `obn discover` per push (lesson 15)
- ✅ `--resume` semantics work after each gate ack

If any of those break, the bug stays in the per-train scope and the test is over. **No multi-train concurrency, no Confluence, no automatic file writers** — those come in a future session once the per-train flow is proven.

### After the run

Update fleet-status row for Fzg 132 manually with the new AP firmware status. Add a note about anything that surprised us. The orchestrator-as-sole-writer pattern stays in force — when Phase 5 orchestrator is built, those updates become automatic.

---

## Below this line: state from the 2026-05-09 morning session (preserved for context)

This file tells a new Claude session **where we were**, **what to do next**, and **what's persistent** so you don't have to re-derive context. Read this first, then the bullet-pointed files at the bottom.

## TL;DR — what's happening

We're building a multi-train orchestration system:
- A human tells the orchestrator "do these trains today"
- The orchestrator spawns one subagent per train
- Each subagent runs through a 19-stage commissioning pipeline using project skills
- Subagents emit JSON reports; orchestrator polls every 5 min, updates fleet-status.md, mirrors to a Confluence page
- 5 approval gates exist for irreversible/destructive operations (chroot promotion, reboot, consist-wide pushes, missing-device decisions)

**Phase 3 complete as of 2026-05-09 12:44 UTC.** End-to-end manual commissioning run on Fzg 132 / box1-t10. Two chroot promotes (OBN first, then template + vlan7), then AP firmware push exercise (15/21 done, 6 stuck-state APs remaining), then forced AP+SW config pushes to validate untested code paths. **6 of 8 OBN patches now exercised on a real passenger consist with 0 exceptions** (Bug 1 + Bug 2a still pending — both only fire on switch firmware push, which is untestable without a newer binary). Phase 4 (`.claude/agents/dosto-train-worker.md`) is the immediate next build step.

## Where Fzg 132 / box1-t10 ended up

Train: **Fzg 132 / 4736-104 / CCU `10.179.10.1` / box1-t10**

End-state (as of 2026-05-09 09:46 UTC, after two chroot promotes and two reboots):
- ✅ OBN 8/8 patches persisted in `/.snapshots/run1` (subvol ID 314)
- ✅ `train_id = 132` hardcoded in all 18 nv6-*.cfg templates (mar5-compliant)
- ✅ vlan7 = `172.19.194.2/17` live and persisted
- ✅ Stadler firewall TCP-reachable (port 80 + 22)
- ✅ `nd-systemupdate.sh.dont` rename preserved across both promotes
- 🔴 Coach D AP4 still missing — D3.e1-2 link DOWN. **Train BLOCKED on Stadler for cable replacement before any `obn update c all` / `obn update f all`.** Cable register row #5 has the ordered Stadler instructions.

Full Phase 3 walkthrough (Diagnostic, OBN-apply, Promote-1, Reboot-1, post-reboot regression discovery, Fix-template+vlan7-in-place, Promote-2, Reboot-2, Post-reboot verify) took roughly 90 minutes of human time including investigation of unexpected state.

## Lessons from Phase 3 — must inform Phase 4 subagent design

These are the things we did NOT anticipate before this session that the subagent (or its skill set) must handle. Each is a real friction point we hit during the manual end-to-end. Marked 🔴 if it caused a real failure, 🟡 if it caused inefficiency.

### Firmware/config update mechanics (added 2026-05-09 after AP firmware push attempts)

11. 🔴 **`obn update f ap` with parallel batches > 2-3 is unreliable on this fleet image.** Initial 15-AP parallel push had ~10 stall silently. Root causes: (a) CCU firewall lacks proper TFTP conntrack helper for the data return path; (b) `iptables -t raw -A PREROUTING -p udp --dport 69 -j CT --helper tftp` is silently no-op under iptables-nft compat shim — needs native nftables `ct helper set` syntax; (c) the conntrack expectations table (`/proc/net/nf_conntrack_expect`) stays empty even after applying the rule. **Skill must default to single-AP serial pushes** until R&D fixes the firewall (separate from OBN patch ticket). Single push: ~5-8 min wall time per AP. Parallel-of-2 tested working post-helper-fix but parallel-of-8 still failed.

12. 🔴 **OBN's `extreme.py set_firmware_version` returns success on AP "I'm too busy" responses.** The AP says "Successful: upgrade tftp request initiated" via SSH; OBN parses this as success even when the AP doesn't subsequently send a TFTP RRQ. Validation at the OBN level is fake-positive. **Skill must verify success at the network layer: did the AP actually send an RRQ + transfer the firmware bytes?** Use `journalctl -u tftpd-hpa --since` to grep for `RRQ from <AP-IP>` after each push. If no RRQ within ~60s, the push didn't actually fire — AP is in stuck-state.

13. 🔴 **Failed flashes leave APs in "stuck-state" — subsequent OBN pushes silently fake-succeed.** APs that get a half-failed flash (TFTP RRQ sent, data flow blocked) enter a state where they reject new flash attempts but report "Successful" via SSH. **Workaround**: SSH to AP, `reboot`, wait 90s for boot, then immediate single `obn update f <ip>`. The newly-rebooted AP accepts the flash and the RRQ fires for real. Skill should detect stuck-state and apply this workaround.

14. 🟡 **APs take 6-10 min from "OBN says applied" to "back on new firmware via SNMP".** OBN waits only 5 min internally then declares done — too short. Many APs from the 11:13 batch came back at 6.11.2-0 only at 11:50 (37 min later). **Skill should poll the AP via fresh `obn discover` until firmware version matches target OR a timeout of ~15 min, whichever comes first.** Don't trust OBN's 5-min internal wait.

15. 🟡 **`obn discover` reads from cached `/tmp/discovery.json` produced by the every-5-min `nd-backbone-discovery.timer`** — `obn validate` shows the cache, not live SNMP polls. Forcing fresh data: `sudo obn discover` (overwrites the file). Skill should prefer fresh discover over `validate` immediately after any push. Or read `/tmp/discovery.json` directly with `jq`.

16. 🟡 **`obn validate` shows firmware version like `6.10.0-0 (6.11.2-0) ✗` where the parens are the *staged* image on the inactive partition.** This means a flash *did* upload but didn't activate. To force activation: AP needs a second reboot. The first parens-current-paren mismatch *is* a sign the previous flash partly worked.

17. 🟡 **`/var/log/obn/*.log` does NOT capture in.tftpd activity.** Real diagnostic for failed firmware pushes is `journalctl --since X | grep "in.tftpd|tftp"` — not the OBN logs. Subagent skill must include the system journal in its diagnostic capture.

### Original lessons (chroot persistence and CCU state — from earlier in this session)

1. **Two-promote pattern is mandatory when any per-train hand fix accompanies OBN patches.**
   - The first chroot promote starts from the OLD `release` snapshot. Anything fixed in the live `runN` (e.g. train_id template, vlan7 IP) is not seen by the chroot and is silently lost on first reboot.
   - **Subagent must apply train_id and vlan7 fixes INSIDE the chroot**, not just on the running snapshot. Either fold them into a single chroot session (apply OBN + template + vlan7 all inside one `nd-systemupdate.sh.dont shell`), or accept two-promote pattern (OBN first, regress detection, fix-in-chroot promote second).
   - For the manual cycle we used the two-promote pattern. For the subagent we should fold all three into one chroot session — simpler, faster, and avoids a wasted reboot. The skills `dosto-obn-patches`, `dosto-vlan7-config`, and the missing `dosto-fzg-id-check` should compose into a single `--persist` recipe.

2. **`nd-systemupdate.sh` is renamed `.dont` fleet-wide.** Discovered on box1-t10 and confirmed on box1-t1. The skill recipe assuming canonical `nd-systemupdate.sh shell` fails on every train. Use `sudo /usr/sbin/nd-systemupdate.sh.dont shell`. **Action item**: update [.claude/skills/dosto-obn-patches/SKILL.md](.claude/skills/dosto-obn-patches/SKILL.md) `--persist` mode to detect which file exists and emit the right command.

3. **Chroot's `/var/tmp` IS bind-mounted (per `DIR_TO_MOUNT="boot/grub data dev var/cache var/tmp"`).** `/tmp` is NOT. Stage scripts in `/var/tmp/`, not `/tmp/`. Skill recipe currently says `/tmp/` — wrong.

4. **`/var/tmp` is tmpfs that wipes on reboot.** After the first reboot, scripts staged in `/var/tmp/` are gone. Re-scp them before the second promote. Subagent must not assume staged files persist across reboots.

5. **Chroot needs stdin-fed commands for full automation.** The `shell` command spawns an interactive bash. To run non-interactively, pipe commands via SSH stdin (we used heredoc `<<'EOF' ... EOF`). This works because the chroot inherits stdin from the calling script. Pattern is reusable.

6. **The btrfs somersault recycles snapshot folder names.** First promote went `run1 → run2` (run1 was active, new release became run2). Second promote went `run2 → run1` (run2 was active, run2's old data got recycled, new release became run1 again). Subagent verifies by SUBVOLUME ID (314 here), not by folder name — folder names are unreliable progress indicators.

7. **State sentinel format**: `/.snapshots/state` records `VERSION=<puppet_catalog_hash>_manual_<YYYYMMDDHHMM>` after a hand-driven promote. Subagent can use this as a "did the promote actually happen" gate.

8. **Chroot promote takes ~2 min wall time. Reboot takes 3-5 min.** Plan subagent timeouts accordingly. The polling pattern that worked: SSH probe every 8s with `nc -z`, then a separate full SSH handshake check.

9. **Skill missing**: `dosto-fzg-id-check`. Stage 3 (`apply_train_id_fix`). Builds on the same `--check / --apply / --persist` shape as `dosto-obn-patches` and `dosto-vlan7-config`. Detects `{%- set train_id = 128 + train_id -%}` (broken) vs `{%- set train_id = <Fzg> -%}` (correct), prints sed recipe, applies inside chroot to persist.

10. **box1-t1 (Fzg 133) is currently exposed to auto-update**: it has `nd-systemupdate.sh` at the canonical name (likely a previous engineer forgot to re-rename after their last promote). Sun/weekday-night auto-update timer would clobber its `persisted (run3)` patches. **Re-rename to `.dont` on next visit before doing anything else.**

## What to do next

Phase 3 is complete. Resume on Phase 4: write `.claude/agents/dosto-train-worker.md`. Use the lessons above as the subagent's must-handle list. Suggested order:

### Skill updates / new skills needed

| Skill | Status | Action |
|---|---|---|
| `dosto-obn-patches` | exists | Update for lessons 2, 3, 4, 6 (`.dont` rename detection, `/var/tmp` not `/tmp`, tmpfs scripts wipe on reboot, subvol ID not name) |
| `dosto-vlan7-config` | exists | Already correct shape; just needs to be applied INSIDE chroot (lesson 1) |
| `dosto-fzg-id-check` | **NEW** | Verify `train_id = <Fzg>` hardcoded in all `/etc/obn/template/nv6-*.cfg`. Detect broken `128 + train_id` formula. Apply via sed inside chroot. Same `--check / --apply / --persist` shape. |
| `dosto-tftp-helper-check` | **NEW** | Verify `nf_conntrack_tftp` loaded + working CT helper rule. Apply runtime fix (`modprobe` + iptables) or note "broken under iptables-nft, R&D fix needed". |
| `dosto-ap-firmware-update` | **NEW** | Per-AP firmware push orchestrator. Single-AP-at-a-time default. Verifies with fresh `obn discover` + `journalctl` grep for `RRQ from <AP>`. Auto-detects stuck-state and applies SSH-reboot workaround. Polls up to 15min for AP to come back at target firmware. |
| `dosto-ap-config-update` | **NEW** | Per-AP config push, similar shape. Less risky than firmware. |
| `dosto-sw-firmware-update` | **NEW** | Per-switch firmware push (more delicate — switches reboot affects whole fabric). Sequence by leaf-first per OBNTree. Validates each switch comes back via SNMP before next. |
| `dosto-sw-config-update` | **NEW** | Per-switch config push. Same shape. |
| `dosto-commission-train` | **NEW (orchestration)** | Top-level subagent skill. Runs full sequence: device-discovery → check OBN/vlan7/fzg-id/tftp-helper → if any broken, persist via single chroot session → reboot → AP firmware update (serial) → AP config update (serial) → SW firmware update if needed → SW config update → l2-health verify. Reports JSON status at each gate. |

### Recommended order

1. **Update `dosto-obn-patches`** (small, well-understood) to handle the `.dont` rename detection and `/var/tmp` correctly.
2. **Build `dosto-fzg-id-check`** (small, follows the `dosto-vlan7-config` pattern).
3. **Build `dosto-tftp-helper-check`** (small, mostly diagnostic + warning).
4. **Update `dosto-obn-patches --persist`** to optionally include vlan7 + fzg-id fixes inside the same chroot session (single-promote pattern instead of two-promote).
5. **Build `dosto-ap-firmware-update`** carefully — this is where most of the new failure modes live (lessons 11–17). Must include:
   - Single-AP-at-a-time default
   - Fresh `obn discover` after each push (don't trust validate cache)
   - `journalctl` grep for `RRQ from <ip>` to verify push actually fired
   - Stuck-state detection: if no RRQ within 60s, do SSH-reboot then single retry
   - 15-min poll for AP to return at target firmware (don't trust OBN's 5-min wait)
6. **Build `dosto-sw-firmware-update`** with extra care (a bricked switch on the consist breaks the whole train).
7. **Build the orchestrator `dosto-commission-train`** that calls all of the above in sequence.
8. **Then write the subagent definition** that exposes `dosto-commission-train` as its main entry point.

### Open R&D tickets (keep nagging)

- OBN bugs 1–8 → upstream into `dostoneu_migration_mar5` Puppet env
- CCU firewall TFTP conntrack helper → upstream nftables-native fix into `60-allow-management`
- OBN `extreme.py set_firmware_version` → improve "Successful" parsing to verify TFTP transfer actually happened (count via `iptables -L INPUT | grep tftp_allowed` byte counter, or watch in.tftpd journal)
- Westermo AP "stuck-state after failed flash" — likely a Westermo firmware bug, but workaround is documented

## Where the persistent state lives — read these to get full context

In order of importance:

1. **[fleet-status.md](fleet-status.md)** — single source of truth for every train's state. Open this first. Fzg 132's row is the active one; other rows show context.
2. **[train-login-checklist.md](train-login-checklist.md)** — the 11-step procedure for any train session. Steps 0-3 already done on Fzg 132; we're at step 5+.
3. **[.claude/contracts/](.claude/contracts/)** — 4 contract docs (subagent-report, autonomy-boundary, approval-gates, confluence-sync). Pinned design.
4. **[.claude/skills/](.claude/skills/)** — 6 DOSTO skills, all with `--json` mode:
   - `dosto-extract-train-data` — extract per-series topology from OBN templates + per-train header from PDF
   - `dosto-device-discovery` — count switches/APs vs. expected, localise missing devices
   - `dosto-obn-patches` — verify/apply/persist the 8 OBN bug fixes
   - `dosto-vlan7-config` — verify/fix CCU vlan7 IP
   - `dosto-l2-health` — Layer-2 health check (existing)
   - `dosto-l2-report` — generate customer-ready docx (existing)
5. **[train-ip-allocation-commission/extracted/](train-ip-allocation-commission/extracted/)** — extracted reference data:
   - `_shared/nv4-topology.md` (all 4734 trains)
   - `_shared/nv6-topology.md` (all 4736 trains) ← used during validation
   - `4736-105.md` (per-train header for Fzg 133, the reference example)
6. **[cable-issues-register.md](cable-issues-register.md)** — fleet cabling register. Row #5 added today (D4 missing on Fzg 132, full diagnosis).
7. **[CLAUDE.md](CLAUDE.md)** — project playbook. Architecture, vlan7 formula, folder layout.
8. **[troubleshooting-runbook.md](troubleshooting-runbook.md)** — operational runbook (LLDP cabling check, OBN bug catalogue, AP factory bypass, train_id rules).

## Build plan progress

| Phase | Status | Notes |
|---|---|---|
| 1. Contracts | ✅ Done | 4 contracts at .claude/contracts/. 5 gates defined (incl. device_count_mismatch as three-way). |
| 2. Skills + --json retrofit | ✅ Done | 6 skills, all support `--json` per the contract. |
| 3. End-to-end manual on box1-t10 | ✅ Done 2026-05-09 | Full cycle executed: diagnose → apply OBN → promote-1 → reboot-1 → discover regression → fix template+vlan7 → promote-2 → reboot-2 → verify. 10 lessons captured (see "Lessons from Phase 3"). |
| 4. Subagent definition | ⬜ Not started | `.claude/agents/dosto-train-worker.md` to write |
| 5. Orchestrator | ⬜ Not started | Polls subagents, aggregates, surfaces approvals, writes fleet-status + Confluence |
| 6. Confluence integration | ⬜ Not started | Page ID `5410684933` on `nomad-digital.atlassian.net`, currently empty |
| 7. CLAUDE.md update | ⬜ Not started | Document the orchestration architecture |
| 8. Bootstrap script | ⬜ Not started | One-shot setup for fresh laptop / fresh checkout |

## Things you should NOT do without explicit user confirmation

- **Run any command on the CCU yourself** (other than read-only SSH for verification). The user runs all destructive commands in their own terminal.
- **`obn update c all` or `obn update f all`** on Fzg 132. The train is BLOCKED on Stadler for D4. Doing these would push to 23/24 APs and leave D4 in mixed state when it eventually comes online.
- **Trigger `nd-systemupdate.sh shell`** programmatically. The user runs it; it's irreversible (promotes a new btrfs snapshot as default GRUB target).
- **Trigger `safe_reboot`**. User-driven; affects passenger-carrying train.
- **Touch [fleet-status.md](fleet-status.md) without first reading it** — orchestrator-as-sole-writer pattern. Edit individual rows for the active train, don't bulk-rewrite.
- **Auto-extract from PDFs** for any new train without engineer review. Templates win where they exist; PDFs are header-only.
- **Re-clone the OBN template repos** without checking if they exist at `~/Documents/nomad-obn-template-{nv4,nv6}/`. The host key is in `~/.ssh/known_hosts` already (`SHA256:ICSVce6peLWKgWuxprDLcsIcS6R0Gg+fLdYPd5SykMU`), the user's SSH key is registered with Nomad GitLab, but a fresh clone every session is wasteful.

## Things you SHOULD do without asking

- **Read fleet-status.md, contracts, and the relevant skill SKILL.md files at session start.** Don't ask the user to recap state — it's all in those files.
- **Run read-only SSH** to verify state on a CCU when needed (`dhcp-lease-list`, `grep` markers, `show interface`, etc.) — that's how diagnosis works.
- **Update fleet-status row for the active train** as state changes (last_touched, status, OBN patches column, etc.).
- **Update cable-issues-register.md** when a new physical cabling fault is found, with ordered Stadler-actionable instructions.
- **Update auto-memory** for new persistent facts (reference paths, project conventions, feedback rules).

## OBN patch validation results — for the R&D ticket

Captured 2026-05-09 on Fzg 132 / box1-t10 with all 8 patches applied and persisted via two btrfs promotes (active subvol `/.snapshots/run1`, ID 314, gen 136390). Catalog: `c857b4e490bbea27fca6553b0e14d8aae156e9d1` (env `dostoneu_migration_mar5`). Same OBN code R&D would receive.

**Patches exercised on a real passenger consist:**

| # | Patch | Test method | Result |
|---|---|---|---|
| 1 | `vdsrail.py` firmware regex (`default image is now`) | NOT exercised — only fires on switch firmware push (`obn update f sw`); all 18 switches were already on target firmware `7.4.2`, push would be no-op | ⏸ |
| 2a | `vdsrail.py` firmware-side polling None guard | NOT exercised — fires during switch firmware push polling (same reason as Bug 1) | ⏸ |
| 2b | `vdsrail.py` config-side polling None guard | ✅ Fired during forced switch config push to F2 (`10.179.10.189`) — polls SNMP through reboot | ✅ |
| 3 | `snmpdevice.py` KeyError guard | Every `obn discover` / `validate` / `wifi-status` / `user-count` cycle, plus timer-driven `nd-backbone-discovery` (every 5min) and `nd-backbone-auto-update` (every 10min). ~10+ cycles cumulative | ✅ |
| 4 | `report/device.py` firmware None guard | `obn report` ran cleanly manually + via timer; pre-check before all firmware/config pushes | ✅ |
| 5 | `update.py` TFTP ipset pre-population | **Directly observable** — `ipset list tftp_allowed` showed target IPs populated before each TFTP transfer. Validated on AP firmware (`10.179.10.222`), AP config (`10.179.10.234`), and switch config (`10.179.10.189`) pushes | ✅ |
| 6 | `tree.py` cross-consist guard | `obn discover` builds `OBNTree` internally — runs on every cycle | ✅ |
| 7 | `vdsrail.py` reboot hostname guard | ✅ Fired during forced switch config push to F2 — switch reboot triggers `set_configuration_version`'s hostname-after-reboot polling, hitting the None guard | ✅ |
| 8 | `report/device.py` config None guard | `obn report` + pre-check on AP1.1 config push + F2 switch config push | ✅ |

**Test pushes performed:**
- AP firmware: `10.179.10.222` (single-AP push, baseline) — flashed `6.10.0-0` → `6.11.2-0`
- AP firmware batch (15 APs in parallel): only ~5 succeeded — exposed unrelated TFTP firewall conntrack issue, NOT an OBN bug
- AP firmware batch-of-2: succeeded (2 batches × 2 APs = 4 successful pushes)
- AP config push (forced): `10.179.10.234` (AP1.1) — config TFTP transfer + reboot completed cleanly
- Switch config push (forced): `10.179.10.189` (F2 Coach 5) — config TFTP + reboot + post-reboot SNMP polling completed cleanly, all neighbors restored

**Final score: 6 of 8 patches fully exercised, 2 still pending. Remaining gap (Bug 1 + Bug 2a):** both live in `vdsrail.set_firmware_version`, only fire on switch firmware push. Untestable without either (a) a newer switch firmware binary to push, or (b) artificially downgrading a switch first. Defer to whichever future train R&D wants to ship a switch firmware update on, or have R&D add unit tests to cover these two paths in isolation.

**Cumulative evidence from `/var/log/obn/*.log` since reboot-2 at 2026-05-09 09:39 UTC:**
- Total `Traceback` matches: **0**
- Total `Exception` matches: **0**
- Total `ERROR` matches: **0**
- All marker greps still report expected counts (Bug 1=1, Bug 2=2, Bugs 3–8 each =1)

**Behavioural proof patches don't break OBN:** `obn validate -t sw` shows all 18 switches' hostnames as `nv6-A1-v8-132`, `nv6-A2-v8-132`, … `nv6-B3-v8-132`. These hostnames are produced by the OBN templating layer reading `train_id` from `nv6-*.cfg` template files. Pre-fix vanilla code would produce `nv6-A1-v8-260` (since `128 + train_id` was rendered with train_id=132). Hostnames matching Fzg → patches + template fix are all working in concert.

**Open patch test gap:** Bug 7 (switch reboot hostname guard). Only fires on switch config-push paths, which are higher-risk and unnecessary on this train. Defer to a train where switch config has actually drifted, or where R&D can stage a test push.

**Recommendation for R&D ticket:** merge the 8 patches (or equivalent fixes) into the OBN package shipped via `dostoneu_migration_mar5` Puppet env. Once merged and a snapshot is built, restore `nd-systemupdate.sh` to canonical name on a single test CCU, let the timer fire, verify post-promote that 8/8 markers are still present (proves Puppet is now shipping patched OBN). Then roll the rename-restore across the fleet.

## Open questions / followups for later sessions

- **Other 19 4736 trains and 19 4734 trains** still need per-train extracted files (Mode B of `dosto-extract-train-data`). Run as needed when commissioning each.
- **`dosto-fzg-id-check` skill** — currently Stage 3 (`apply_train_id_fix`) has no dedicated skill. Build before encountering a train with the `128 + train_id` template bug.
- **R&D upstreaming the OBN bug fixes** — once shipped, `dosto-obn-patches` becomes "verify the deployed OBN has these fixes" rather than "apply our private patches". Worth nagging R&D periodically.
- **R&D fixing CCU firewall — TFTP conntrack helper missing** — separate from OBN patches but same R&D ticket. `/etc/21net-security.d/60-allow-management` (Puppet-managed) needs `modprobe nf_conntrack_tftp` and `iptables -t raw -A PREROUTING -p udp --dport 69 -j CT --helper tftp`. Without these, `obn update f ap` silently fails for most APs in any batch push (only ~5/15 succeed by conntrack-race luck). Diagnosed end-to-end on box1-t10 2026-05-09 — see [troubleshooting-runbook.md](troubleshooting-runbook.md) "CCU Firewall — TFTP conntrack helper missing". Runtime fix is loaded in memory now on box1-t10 (will be lost on next reboot until R&D ships the Puppet fix or we persist via chroot).
  - Discovered 2026-05-09 on box1-t10: `nd-systemupdate.sh` is renamed `.dont` on every CCU in the fleet to disable the nightly `nd-auto-system-update.timer` (`OnCalendar=*-*-* 0,1,2,3,4:21:00`) which would otherwise promote a vanilla-OBN snapshot from Puppet env `dostoneu_migration_mar5` and reboot the train, wiping our hand-patches. Puppet *agent* runs continue normally (last successful run on box1-t10: 2026-05-06, catalog `c857b4e4`). The `.dont` blocks only the auto btrfs-promote path, not config sync. **Followup nag for R&D:** merge the 8 OBN patches into the `dostoneu_migration_mar5` Puppet env (or whatever env the rollout uses), then we can restore canonical `nd-systemupdate.sh` and let the timer do its job. Until then, `.dont` stays — on every CCU, after every promote. Also flagged: box1-t1 (Fzg 133) currently has `nd-systemupdate.sh` at the canonical name — exposed to auto-update, will clobber its `persisted (run3)` patches on next Sun/weekday-night cycle. Re-rename to `.dont` on next visit.
- **R&D fixing nv4 template `description` aliasing** — would let `dosto-cabling-check` (when built) trust template descriptions verbatim. Cosmetic for now.
- **Other 4-car CCUs** — fleet-status mostly UNKNOWN for 4734 series. Validate `_shared/nv4-topology.md` against a live 4-car CCU when one's reachable.

## Auto-memory entries worth checking

In `~/.claude/projects/C--Users-AbbasRizvi-Documents-dosto-troubleshooting/memory/`:
- `MEMORY.md` — index, always loaded into context at session start
- `reference_obn_template_clones.md` — paths to the cloned OBN repos
- `feedback_train_id_location.md` — Fzg ID goes only in `nv6-*.cfg`, never `backbone-discovery.yaml` (mar5 workaround, NOT a bug to fix)
- `feedback_train_id_ip_mismatch.md` — DOSTO NEU `train_id` deliberately ≠ Fzg ID; don't flag mismatches as errors
- `project_nd_systemupdate_dont.md` — fleet-wide `.dont` rename convention + chroot procedure
- `project_tftp_conntrack_helper.md` — CCU firewall TFTP conntrack helper missing (R&D nag item)

## How to resume

Phase 3 is done. A good first message in the new Claude session is:

> Resume DOSTO orchestration build at Phase 4. Read handoff.md, fleet-status.md, and the .claude/skills/ inventory. Phase 3 manual commissioning on Fzg 132 was validated end-to-end; 6 of 8 OBN patches fully exercised on a real consist. We need to (a) update `dosto-obn-patches` skill for the `.dont` rename + `/var/tmp` learnings, (b) build the 7 new skills listed in handoff.md "What to do next", (c) write `.claude/agents/dosto-train-worker.md` subagent definition. Start with item (a) — the smallest, lowest-risk update.

That's enough to land the new session in the right place with full context.

---

**File maintained by:** Abbas Rizvi + Claude
**Last meaningful update:** 2026-05-09 12:44 UTC (Phase 3 commissioning + patch validation complete)
