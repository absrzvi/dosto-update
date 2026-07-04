---
type: ticket
title: RD-12434 — Upstream v8 OBN hand-patches (engine-key home)
description: Upstream ticket for the v8 OBN hand-patches (11 bugs + 1 infra); the natural home for the OBN engine-key change if R&D takes the fzg_id-in-engine route. Adjacent to SA-2444.
ticket: RD-12434
status: open
project: dosto-neu
tags: [ticket, rd, obn, upstream, fzg-id, engine]
timestamp: 2026-07-04T00:00:00Z
---

# RD-12434 — Upstream v8 OBN hand-patches

- **Jira:** https://nomad-digital.atlassian.net/browse/RD-12434 · **Status:** To Do ·
  **Owner:** Ben Turner.
- **Scope:** upstream the v8 OBN hand-patches (11 bugs + 1 infra). It is the natural home for the
  **OBN engine-key change** if R&D goes the route of carrying the per-train Fzg via the (shared)
  engine line — the only render transport that can carry a per-train Fzg, since per-fleet
  `rules.yaml` static values cannot (the Jinja template sees only `target`).

# Context

- Adjacent to **SA-2444** (the mar5 migration gate). Together they gate the v9 + fzg_id +
  4734-migration execution.
- The engine repo (`onboard/obn`) is **shared across all fleets** and CI-gated, so any fzg_id
  injection on the engine line must be **generic**, not DOSTO-specific.

# Related

- [SA-2444 — mar5 ID migration](SA-2444-mar5-id-migration.md)
- [TRIAG-8585 — OBN bug upstream](TRIAG-8585-obn-bug11.md)
- [Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md)
- [Tickets index](index.md)

# Citations

[1] Memory `project_sa2444_gate_and_v9_migration_tasklist` — RD-12434 as adjacent ticket.
[2] CLAUDE.md — OBN engine shared / CI-gated; fzg_id render transport constraint.
