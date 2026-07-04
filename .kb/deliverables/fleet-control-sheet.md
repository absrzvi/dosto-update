---
type: deliverable-ref
title: Fleet Control Sheet — ND-DEL-OBB-035-CFG-001-01 (2026-02-11)
description: Master control sheet listing every DOSTO trainset with its CCU IP, commissioning state, config/firmware versions, and Nomad Connect version. Source of the CCU-IP attributions used to seed fleet-status rows.
resource: /ND-DEL-OBB-035-CFG-001-01 OBB Fleet Control Sheet 20260211.xlsx
project: dosto-neu
tags: [deliverable, control-sheet, ccu-ip, fleet, versions]
timestamp: 2026-07-04T00:00:00Z
---

# Fleet Control Sheet — ND-DEL-OBB-035-CFG-001-01 (2026-02-11)

**Resource:** `/ND-DEL-OBB-035-CFG-001-01 OBB Fleet Control Sheet 20260211.xlsx`
(also cached under `docs/`; do not deep-parse the binary here).

The customer-shared fleet control sheet — one row per trainset with CCU IP, per-train status
(`Done` / `Investigate` / …), config + firmware versions (e.g. `v6` / `v7` / `6.10.0`), and the
Nomad Connect version (e.g. `NC 2025.2.1`). Snapshot dated **2026-02-11**.

Several `⚪ UNKNOWN` initial-visit rows in `fleet-status.md` were **seeded from this sheet** (CCU IP
+ sheet status) before any live probe — e.g. the 4734-110/116/117/118 rows. **Treat the sheet as a
starting hint, not live truth:** where it disagrees with a live reading, the live reading and the
scoped tracker win (it had at least one typo — 4705-103's `.42.1` duplicated 4705-101; the live CCU
is `.41.1`).

# Related

- [Fleet current state (do not edit)](/fleet-status.md)
- [Fleet index](/.kb/fleet/index.md)
- [Deliverables index](index.md)

# Citations

[1] fleet-status.md — rows annotated "CCU IP from control sheet 2026-05-21".
[2] fleet-status.md — 4705-103 `.42.1` typo note.
