---
type: deliverable-ref
title: Project Status (master) — PROJECT-STATUS.md / .xlsx
description: The project-wide master status front-door across 8 workstreams. A derived summary; the authoritative per-area detail lives in the scoped trackers (fleet-status, cable register, SDD tasklist, memory).
resource: /PROJECT-STATUS.md
project: dosto-neu
tags: [deliverable, project-status, master, workstreams, derived]
timestamp: 2026-07-04T00:00:00Z
---

# Project Status (master)

**Resource:** `/PROJECT-STATUS.md` (front door) → `/PROJECT-STATUS.xlsx` (the actual tracker).

As of 2026-06-20 the project-wide status lives in **`PROJECT-STATUS.xlsx`**:
- **Status** sheet — one row per item across **8 workstreams** (Commissioning, SDD, Cabling/HW,
  OBN bugs, Zabbix/NMS, 6040/GPS, Investigations, Tooling). Columns: Workstream · Item · Owner ·
  Status · Detail · Last updated. Auto-filter on.
- **Summary** sheet — counts by status and by workstream (written as values, not formulas, since
  LibreOffice recalc isn't available locally).

Regenerate with `python scripts/gen_project_status_xlsx.py` (the item list lives in that script).

**It is a derived summary.** The authoritative per-area editing surfaces remain:
[fleet-status.md](/fleet-status.md) (per-train state), [fleet-journal.md](/fleet-journal.md)
(narrative), `sdd-design-freeze-tasklist.md` (SDD), `cable-issues-register.md` (cabling/HW), and the
auto-memory store. **If the xlsx contradicts a scoped tracker, the scoped tracker wins.**

# Related

- [Fleet index](/.kb/fleet/index.md)
- [Tickets index](/.kb/tickets/index.md)
- [Phase Plan Q2 2026](phase-plan-q2-2026.md)
- [Deliverables index](index.md)

# Citations

[1] PROJECT-STATUS.md (2026-06-20 front-door note).
[2] Memory `project_master_status_tracker`.
