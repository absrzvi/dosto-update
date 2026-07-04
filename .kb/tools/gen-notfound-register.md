---
type: tool
title: Not-found device register — fleet-wide Stadler missing-device report
description: Builds the Stadler "devices not found" xlsx register from currently-open Zabbix port-down problems, joined to the OBN template and classified per device category.
project: dosto-neu
tags: [zabbix, nms, obn-template, stadler, register, report, xlsx, fleet, diagnostic]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
resource: /scripts/gen_notfound_register.py
---

# Not-found device register — fleet-wide Stadler missing-device report

## What it does
Pulls **currently-open** Zabbix problems (the same source as the NMS open-problems view, not raw
event history) across the whole fleet, keeps only port-DOWN problems on **template-enabled** ports,
joins each to the OBN template device + description, categorises it (Display, Audio/ADU, Camera, AFZ,
Intercom, Energy meter, AP, trunk, …), and writes a two-sheet xlsx register (6-Teiler nv6 /
4-Teiler nv4) with per-train and per-category summaries plus an infrastructure-priority callout.

Each row is classified **expected-down** (coupler / service / inter-coach trunk) vs **MISSING device**
so Stadler can see at a glance what is a real gap. It is the fleet-scale automation of the
single-train logic in [`xref_6027_ports.py`](/.kb/tools/xref-down-ports-vs-template.md).

## When to reach for it
When you need a customer-facing, fleet-wide answer to "which devices are Stadler missing?" — a
periodic deliverable, or a snapshot after a commissioning push. Reach for it over the per-switch
cross-reference when the scope is the whole fleet and the output must be a shareable register.

## Usage
```bash
python scripts/gen_notfound_register.py
```

No args. Requires `openpyxl`. Reads from disk: `fleet-status.md` (for the octet→Train# map) and the
port maps `findings/nv6_port_map_20260620.txt` / `findings/nv4_port_map_20260620.txt`. Hits the cloud
Zabbix API with the in-repo `okapi` read credential. Runs anywhere with API reachability.

## Output
`reports/stadler/Stadler_DOSTO_Devices_Not_Found_Register_v1.1.xlsx` — two data sheets + two summary
sheets. Console prints row/missing/train counts per fleet. Amber rows = missing end-device, grey =
expected-down. Placeholder `7.7.7.7` alarms are excluded.

## Notes / caveats
- The port-map input files (`findings/nv*_port_map_20260620.txt`) are a **snapshot** — regenerate
  them from current nv6/nv4 template dumps before a fresh run, or the join is stale.
- **Offline trains** contribute *last-known* open problems; the register flags these "re-verify when
  online" — don't treat them as confirmed live faults. Note the 4734-101/190 mass-down caveat baked
  into `NOTES_4`.
- "Not found" is deliberately ambiguous: a genuine fault OR a device not yet fitted — Stadler
  verifies. The tool classifies, it does not adjudicate.
- Coach-position → letter maps (`COACH_NV6`, `COACH_NV4`) and the output version string are constants;
  bump the version on a new issue.

# Related
- [Down-port cross-reference (single train)](/.kb/tools/xref-down-ports-vs-template.md) — the per-train logic this generalises
- [Zabbix / NMS monitoring model](/.kb/topics/zabbix-nms-model.md) — host-naming formula, open-problems-vs-event-history distinction
