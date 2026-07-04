---
type: evidence
title: OBN silently drops healthy discovered switches from its report when one switch is cold-bypassed
description: A bench repro (box1-t122, discovery.json fixture) proving that a single cold-bypassed switch mis-numbers its replacement and makes OBN's normalise_devices() delete every switch it couldn't number — 10 healthy SNMP-reachable switches collapse to a 2-row report with no signal of truncation.
project: dosto-neu
tags: [obn, report, number-coaches, cold-bypass, monitoring-false-negative, normalise-devices, bug10, field-validated]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
resource: /findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md
---

# OBN silently drops healthy discovered switches from its report on cold-bypass

## What it proves

When a consist switch is **cold-bypassed** (powered off / failed — the backbone relays through it),
OBN's coach-numbering walk mis-numbers the switch that moves into the gap, then collapses — and
`normalise_devices()` **deletes every device it couldn't number, including healthy, SNMP-reachable
switches.** This is a **monitoring false-negative, not a cosmetic numbering bug**: the dropped switches
never reach the report, the NMS/MQTT payload, or `obn validate`, so NMS/Zabbix can never alarm on them.

Bench evidence (box1-t122, 4122 nv4, nd-obn 2.3.8): 10 switches physically present, powered, forwarding,
answering SNMP; A1 + B3 truly absent (cold-bypassed). OBN's report shows **2** rows (A3 + G1), not "2 up
+ 8 flagged" — just 2, with nothing signalling the report is truncated. A 2-row backbone table on a
12-switch consist reads as "small consist, all present."

Root cause is an **identity shift, not just a gap**: `number_coaches()` is a pure walk over live LLDP
driven by port rules (`e0-0`/`e0-1` → coach ±1) with **no model of the expected topology**. When A1 is
bypassed, the switch now sitting in A1's slot (A3, reachable from G1) is assigned **A1's identity** by
the position-keyed rule; the next hop then matches no rule and the walk dead-ends; `normalise_devices()`
drops everything still unnumbered. The observed "only A3 + G1 numbered, 8 dropped" reproduces the real
`obn validate` output exactly.

The **Bug-10 BFS guard made detection worse**, not better: it converted the loud 100%-CPU hang into a
silent 2-row report — the failure went from "obviously broken" to "looks fine, isn't."

## How it was captured

- Live `/tmp/discovery.json` pulled from bench box1-t122 (A1 + B3 bypassed, 10 switches present),
  committed as a regression fixture.
- The deployed `report_dosto_neu.py` `number_coaches()` walk transcribed into a local harness and run
  against the fixture → reproduces `{G1:(2,1), A3:(1,1)}` and 8 dropped, matching field output.
- Cheap fixes disproven in the harness: injecting a DOWN placeholder for the walk to flow through
  **fails** (the port rule keys on the arriving switch's `device_number`, which the placeholder never
  legitimately earns, and the real arriving switch already holds the wrong number); bumping the coach
  counter past the gap propagates the A3-as-A1 error to the whole coach.
- A working prototype of the fix (validated-hostname anchoring + retain-all-discovered) was built,
  proven against the fixture (happy-path / bypass / three-gap / misimage — 0 mis-numbered in all), then
  persisted to bench box1-t122 via NDSU chroot and **confirmed on the real `obn validate`**: 2-row →
  full 12-row table, all 10 present switches numbered correctly, A1 + B3 as explicit `DOWN` rows.

## Evidence

- Raw: [`RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`](/findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md)
  — the R&D proposal: severity framing, root-cause walk trace, why cheap fixes fail, the two-part fix
  (§5c must-have: never drop a discovered device → surface as `UNPLACED`; §5a/5b: topology-anchored
  numbering + first-class `DOWN` state), 6 suggested regression tests, and the validated-prototype note.
- Raw: [`findings/obn_numbering_repro_4736-110_2026-06-24/discovery.json`](/findings/obn_numbering_repro_4736-110_2026-06-24/discovery.json)
  + [`repro_proven.py`](/findings/obn_numbering_repro_4736-110_2026-06-24/repro_proven.py) — the
  transcribed-walk repro harness for the numbering algorithm.

## So what (dead end / actionable)

- **Never trust a short/collapsed OBN backbone table as "all present."** A discovered, SNMP-reachable
  switch that OBN can't coach-number is currently **deleted** — a 2-row report can mean 10 healthy
  switches erased, not a small consist. Cross-check the report count against the expected consist size.
- **Do NOT try to "fix" numbering by inserting a DOWN placeholder for the walk to flow through, or by
  bumping the coach counter past the gap** — both were prototyped and fail (identity error can't be
  repaired by a phantom node; counter-bump shifts every downstream coach). The root problem is that the
  walk equates *position* with *identity*; the fix is to anchor to expected topology + validated
  hostnames, not to patch the walk.
- **The correctness floor (ships independently of the numbering redesign): a discovered, reachable
  device must NEVER be silently deleted** — keep it as `UNPLACED` (or `DOWN` for a bypass) so monitoring
  can still see it.
- **Interim mitigation already exists ops-side:** `dosto-device-discovery` Step 4b does the
  reciprocal-LLDP bypass classification from the CCU and reports `bypass_status ∈ {cold_bypass,
  dead_link, link_down, miscable}` with a "check power/health of X first" instruction — the DOWN signal
  today, outside OBN.
- **This is a shared-engine, CI-gated change** (`report_dosto_neu.py`, 653-test suite) — goes through the
  normal MR + `make tag` release, not a bench chroot.

# Related

- [Nomad Connect / OBN — bug suite (Bug 10 BFS hang; the guard that masked this)](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — discover → report → update workflow](/.kb/components/nomad-connect-obn/discover-report-update.md)
- [VDS Consist Switch — L2 counters & RSTP (cold-bypass is NOT a re-cabling event)](/.kb/components/vds-consist-switch/l2-counters-rstp.md)
- [OBN numbering fragile to a single lost LLDP edge (evidence)](/.kb/evidence/obn-numbering-fragile-to-single-edge-loss.md)
- [OBN platform codebase review — improve-not-rewrite (evidence)](/.kb/evidence/obn-platform-review-improve-not-rewrite.md)
