# DOSTO Project — Master Status

➡️ **The master status tracker is now [`PROJECT-STATUS.xlsx`](PROJECT-STATUS.xlsx).**

As of 2026-06-20 the project-wide status moved from this Markdown file into an Excel workbook — easier to sort, filter, and update in place. Open `PROJECT-STATUS.xlsx`:

- **Status** sheet — one row per item across all 8 workstreams (Commissioning, SDD, Cabling/HW, OBN bugs, Zabbix/NMS, 6040/GPS, Investigations, Tooling). Columns: Workstream · Item · Owner · Status · Detail · Last updated. Auto-filter is on — filter by Workstream or Status.
- **Summary** sheet — counts by status and by workstream.

**To regenerate** (after editing the source list): `python scripts/gen_project_status_xlsx.py`. The item list lives in that script. Note: LibreOffice is not installed locally, so the recalc tooling can't run here — the Summary counts are written as computed values, not formulas, so they're correct without a recalc.

## Still the editing surface for detail

The Excel tracker is a **derived summary**. The authoritative per-area trackers remain:

| Tracker | Scope |
|---|---|
| [fleet-status.md](fleet-status.md) | v8 rollout, per-train current state |
| [fleet-journal.md](fleet-journal.md) | per-train narrative history |
| [sdd-design-freeze-tasklist.md](sdd-design-freeze-tasklist.md) | SDD-002 freeze + SDD-003 comments |
| [cable-issues-register.md](cable-issues-register.md) | physical cabling / hardware faults |
| `MEMORY.md` (auto-memory) | cross-session facts & lessons |

If the Excel tracker ever contradicts one of these, the scoped tracker wins.
