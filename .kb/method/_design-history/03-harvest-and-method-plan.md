---
type: guide
title: Backlog harvest + portable method plan
description: Plan for harvesting the June–July backlog into evidence/tools and building the portable method.
project: dosto-neu
tags: [design-history, planning, meta]
timestamp: 2026-07-04T00:00:00Z
---

# Plan: Harvest the backlog + build a portable KB method

**Date:** 2026-07-04 · **Decisions locked:** harvest into KB (keep raw files as evidence) · portable template + written method (no automation yet) · build here, extract later.

---

## Part 1 — Get the backlog safely committed (nothing at risk)

68 files, all pre-existing project work, dirty before this session. Commit in **themed groups** (not one blob) so history is legible. Raw files stay — they're the evidence.

**Secret check done:** SYSOPS ticket holds only the *public* key + fingerprint (safe). Other flagged files contain `Nom@dCome1n` / okapi pw — but those are *already* committed throughout this private repo, so no new exposure. ⚠️ Standing (non-blocking) issue: hardcoded creds are scattered across tracked files — a future cleanup if this repo ever goes public. Out of scope today.

Commit groups:
1. **evidence + repros** — `findings/*harvest*.txt/.tsv`, `EVIDENCE_raw_harvests`, `*_repro_*.md`, `fixture_bench_*.json`, `RD_obn_coach_numbering_bypass_downstate`, coupling-test subfolder.
2. **tools** — `scripts/sw_bootwindow_poll.sh`, `zbx_check/clear_*.py`, `xref_6027_ports.py`, `gen_*` report/status generators.
3. **deliverables** — customer/internal reports (docx/pdf), topology svg/png.
4. **status/planning** — PROJECT-STATUS, phase plan, tasklists, interdependency review, SYSOPS ticket.
5. **modified tracked** — cable-issues-register (+65), troubleshooting-runbook (+54), the coupling REPORT + gen_report_docx.js, dosto-device-discovery SKILL. Commit separately (they're edits to existing tracked docs). **fleet-status.md: leave for the engineer** — it's the live-state file with its own update discipline; I won't commit a hand-edited fleet-status without confirmation.

## Part 2 — Harvest reusable knowledge into `.kb/`

The raw files are evidence; the KB is the distillate. Add two categories + fold findings into existing docs:

- **`.kb/evidence/`** (new, `type: evidence`) — one stub per significant harvest/repro: what it proves, how it was captured, `resource:` link to the raw file. E.g. the KMdev cold-boot crash repro, the coupled-RSTP storm capture, the OBN BFS-loop harvest.
- **`.kb/tools/`** (new, `type: tool`) — one stub per reusable instrument: what it measures, inputs/outputs, when to reach for it. E.g. `sw_bootwindow_poll.sh` (SNMP boot-window poller), the Zabbix polling checkers, the port xref.
- **Fold into existing dead-ends** — any *newly disproven* thing from these files goes into the relevant component/topic `# Proven dead ends` (e.g. the coach-numbering-bypass downstate, display-transient RCA conclusions).

Each harvest doc = a few lines: claim → method → evidence link → related. Re-run conformance after.

## Part 3 — The portable method (build here, extract later)

Create **`.kb/method/`** — project-agnostic, the thing you copy to the next project:

- **`METHOD.md`** — the written methodology. The transferable engineering discipline:
  1. **Evidence-first** — capture raw harvests before conclusions; keep them as proof.
  2. **Repro-driven** — a fault isn't understood until you can trigger it on demand.
  3. **Proven dead ends** — record what *didn't* work; it's rarer and more valuable than what did.
  4. **KB-as-distillate** — component-organised, generic-core, OKF-conformant.
  5. **Capture ritual** — when you prove/disprove something, it lands in the KB before you move on.
- **`_TEMPLATE/`** — an empty OKF skeleton to copy: `index.md`, `HOW-TO-USE.md`, `MAINTENANCE.md`, `check_conformance.py`, empty `components/ topics/ evidence/ tools/`, and a `frontmatter-cheatsheet.md`. Stripped of all DOSTO specifics.

When the next project starts: copy `_TEMPLATE/` → its repo as `.kb/`, and follow `METHOD.md`.

## Order of operations

1. Commit backlog (Part 1) — safety first.
2. Harvest (Part 2) — adds KB docs pointing at now-committed evidence.
3. Method + template (Part 3).
4. Conformance check + commit KB additions.

## What I will NOT do
- Touch `fleet-status.md` (engineer-owned live state).
- Delete or move any raw file (evidence stays).
- Fix the standing hardcoded-creds exposure (separate, flagged).
- Build automation/skills (you chose written-method-first).
