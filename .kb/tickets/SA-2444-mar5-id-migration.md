---
type: ticket
title: SA-2444 — OEBB Dosto NEU migration complete (GitLab clean-up + mar5 backends)
description: SysOps ticket that completes the MAR5 migration and stands up the mar5 backend HAs. It is the GATE for starting the v9 + fzg_id + 4734-migration execution (specifically the 4734 box=Fzg re-IP to 10.178.x).
ticket: SA-2444
status: open
project: dosto-neu
tags: [ticket, sa, sysops, mar5, migration, gate, 4734]
timestamp: 2026-07-04T00:00:00Z
---

# SA-2444 — OEBB Dosto NEU migration complete

- **Jira:** https://nomad-digital.atlassian.net/browse/SA-2444 · **Status:** To Do ·
  **Owner:** Julia Frick (SysOps) · **Reporter:** Abbas.
- **Title:** "OEBB Dosto NEU Migration complete — GitLab Repo clean-up and normalization."

# Why it gates the v9 / fzg_id work

SA-2444 completes the MAR5 migration and stands up the mar5 backend HAs.

- **ID 50 (`10.178.x.x`) = the 4734 4-car trains, still on mar3, must migrate to mar5**
  (3 HAs: `vmmar5be34` / `vmmar5be35` / +1 TBD).
- **ID 51 (`10.179.x.x`) = the 6-car trains, already on mar5.**

The **4734 box-id=Fzg** plan re-IPs 4734s to `10.178.<Fzg>` — that target backend only exists
once SA-2444 lands. So infra (SA-2444) → then config/migration.

# Less-gated

The **6-car fzg_id** workstream (ID 51 backend already serving) can start sooner; only the
**4734 box=Fzg re-IP** is hard-gated on SA-2444.

# Master task list

`findings/coupling_test_4736-110_119_2026-06-12/TASKLIST_v9_fzg_migration_2026-06-30.md` — 5
workstreams (A engine decision / B template push / C Puppet / D 4734 migration / E deploy+verify),
marking what is DONE-locally vs BLOCKED-on-SA-2444. Staged locally: v9+NTP on all 4 fleets (Phase A)
+ fzg_id on 6-car (Phase B); nv4 Phase-B reverted (box=Fzg route).

# Related

- [RD-12434 — OBN engine-key home](RD-12434-obn-engine-key.md)
- [Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md)
- [Phase plan Q2 2026](/.kb/deliverables/phase-plan-q2-2026.md)
- [Tickets index](index.md)

# Citations

[1] Memory `project_sa2444_gate_and_v9_migration_tasklist`.
[2] findings/coupling_test_4736-110_119_2026-06-12/TASKLIST_v9_fzg_migration_2026-06-30.md.
