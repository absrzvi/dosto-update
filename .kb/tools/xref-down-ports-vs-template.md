---
type: tool
title: Down-port cross-reference — real fault vs expected-down vs config drift
description: Cross-references a switch's live admin-up/oper-down ports against the OBN nv6 template to sort them into real faults, expected-solo couplers, service ports, and config drift.
project: dosto-neu
tags: [switch, ports, obn-template, cabling, config-drift, diagnostic, triage]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
resource: /scripts/xref_6027_ports.py
---

# Down-port cross-reference — real fault vs expected-down vs config drift

## What it does
Takes the set of ports that are **admin-up but oper-DOWN** on each switch (observed live via SNMP)
and joins them to the OBN per-switch template (`enable` flag + port description) to bucket every
down port into one of four verdicts:

- **REAL candidate fault** — template-enabled end-device port (e.g. a Bildschirm), link down → a
  device that should be present isn't.
- **Expected-down (solo)** — coupler / OBS ports that are correctly down on an uncoupled train.
- **Service (e0-5)** — enabled FIS/CCTV service port that may simply have nothing attached.
- **Config drift** — port is admin-up on the switch but **disabled** in the template → the live
  config diverges from design.

This turns a raw "N ports down" number into a triage list you can act on.

## When to reach for it
After a discovery/SNMP sweep of a consist leaves you with a pile of down ports and you need to know
which ones actually matter — separating genuine missing-device faults (for Stadler) from the couplers
and service ports that are down by design. It is the manual, single-train analysis pattern that
`gen_notfound_register.py` later automates fleet-wide from Zabbix.

## Usage
```bash
python scripts/xref_6027_ports.py
```

No args. Both inputs are inline Python dicts you edit for the train under analysis:
`down` (the live admin-up/oper-down ports per switch) and `D` (the nv6 template enable+description
map). Runs anywhere — it is pure local analysis, no network access.

## Output
Four console sections — REAL faults (with a count), expected-down couplers, service ports, and config
drift — each listing `switch port: description`. The REAL-faults count is the headline number.

## Notes / caveats
- **Template, not a one-train tool.** Both dicts are hardcoded to 4736-114 / Fzg 142 (6027),
  captured 2026-06-20. The reusable asset is the **classification logic** (`is_coupler`, the e0-5
  service carve-out, the enabled-vs-disabled drift test). Repopulate `down` from a fresh sweep and
  `D` from the target train's nv6-*.cfg dump.
- Only inspects e0-2 / e0-5 / e2-0..e2-5 (couplers, service, displays/audio) — the ports that carry
  ambiguity. Trunks and AP ports are out of scope here.
- "Expected-down" assumes a **solo** (uncoupled) train; on a coupled consist the coupler ports flip
  to expected-UP.

# Related
- [Not-found device register generator](/.kb/tools/gen-notfound-register.md) — the fleet-wide, Zabbix-sourced automation of this same classification
- [VDS switch — CLI, SNMP & management behaviour](/.kb/components/vds-consist-switch/cli-and-management.md)
- [Fzg-ID two namespaces](/.kb/topics/fzg-id-two-namespaces.md)
