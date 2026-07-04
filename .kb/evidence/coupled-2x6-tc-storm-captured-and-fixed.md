---
type: evidence
title: Coupled 2×6 RSTP TC-storm — captured, root-caused to asymmetric coupler cost, and fixed by symmetric cost
description: Two coupling tests (2026-06-12 and 2026-06-30) prove asymmetric coupler port-cost drives a perpetual ~2s FDB-flush storm and that a flat symmetric cost of 20000 stops it — including the finding that the cost fix alone cleared the coupled CCTV latency.
project: dosto-neu
tags: [coupled, rstp, multitraction, topology-change, coupler, port-cost, cctv, field-validated]
maturity: field-validated
timestamp: 2026-06-30T00:00:00Z
resource: /findings/coupling_test_4736-117_105_2026-06-30/costs_before_after.md
---

# Coupled 2×6 RSTP TC-storm — captured, root-caused, and fixed

## What it proves

On a coupled 36-switch (2×6) pair, a **perpetual RSTP topology-change storm** (every switch flushes
its whole FDB roughly every 2 s, continuously) is driven by an **asymmetric coupler port-cost** — the
two ends of the active coupler P2P link carry different `train_id`-derived cost values, sustaining a
never-resolving designated-role proposal duel. A **flat symmetric cost of `20000` on all four coupler
`e0-2` ports of both trains** stops the churn. Two independent tests establish this both ways:

- **2026-06-12 (110+119):** the storm was *present* (asymmetric v8 costs) and stopped **at the exact
  second** cost was reverted to 20000 on the active link.
- **2026-06-30 (117+105):** symmetric cost 20000 was **pre-staged before coupling** → the storm
  **never arose** (TC/flush count frozen at 0 across the coupled window). The mirror-image proof.

A second, higher-value finding from 2026-06-30: **the cost fix alone resolved the coupled CCTV
latency** on the driver's HMI, with no change to VLAN 5 or the firewalls. The continuous FDB flush had
been turning forwarded CCTV into fabric-wide flooding; a stable FDB restored clean forwarding.

## How it was captured

- RSTP/coupled debug logging enabled on cab switches (`configure system logging debug rstp,coupled`)
  before coupling; the `show spanning-tree` poll is too slow to see the sub-2s role flap — the
  evidence lives in the event log, not in a counter.
- The storm signature is the log line `Flushing all entries` recurring every ~2 s on **every** switch;
  the driver is visible as `sending designated proposal` **and** `received designated proposal` in the
  same second on the active coupler port (both ends claim designated).
- Churn was quantified as a TC/flush **count over two samples ~90 s apart**: a *climbing* count = live
  storm; a count *frozen* after a burst = a discrete re-convergence event, not the storm. This
  distinction (frozen-but-elevated = OK; continuously-climbing = flag) is the field alarm rule.
- Control: a **solo** train (Fzg 132/104, same firmware + debug) logged **zero** TC events in 40 s —
  the storm is coupling-specific.
- Coupler live rate + VLAN-5 FDB stability were sampled to prove the CCTV recovery: after the fix, the
  active coupler carried ~95 Mbps symmetric with a **stable 119-MAC VLAN-5 FDB** (identical across
  8-s-apart samples) vs the June "flushed every ~2s" state.

## Evidence

- [`costs_before_after.md`](/findings/coupling_test_4736-117_105_2026-06-30/costs_before_after.md) —
  per-port cost table (before = `144999999`/`132999999` on A1/B3, A3/B1 default; after = flat `20000`
  on all 8), the PART 1 PASS (churn = 0), and the ⭐ CCTV-resolved-by-cost-fix-alone finding.
- [`ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md`](/findings/coupling_test_4736-117_105_2026-06-30/ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md)
  — post-test chord-cost + traction-limit modelling (see the sibling node-ceiling evidence doc).
- [`README_coupling_test_2026-06-30.md`](/findings/coupling_test_4736-117_105_2026-06-30/README_coupling_test_2026-06-30.md)
  — test method, success criteria, Part 2/3 single-FW VLAN-5 plan.
- [`REPORT_coupling_test_2026-06-12.md`](/findings/coupling_test_4736-110_119_2026-06-12/REPORT_coupling_test_2026-06-12.md)
  — the earlier test: F3 (storm found), Addendum A1 (cost revert stops it at the exact second),
  Addendum 3 (VDS Giorgio: cost width is uint32, **overflow refuted** → the driver is asymmetry).
- Raw harvests: `4736-110_fzg138_harvest.txt`, `4736-119_fzg147_harvest.txt`,
  `tc_trace_138.txt`, `tc_trace_147.txt`, `tc_trace_147_solo.txt` (the solo control).

## So what

- **The fix is symmetry, not a magnitude bound.** Do not chase "cost < 2^27" — that came from the
  refuted overflow theory. Set the same sane value (`20000`) on both ends of every coupler port.
- **Ships as v9 M1** (flat symmetric coupler cost) across all four template repos (nv6/nv4/fv5/fv6).
  The 2026-06-30 PASS is the greenlight for the v9 cost MR.
- **Runtime cost changes are wiped by power-cycle / `obn update c` from v8** — must be committed to the
  templates (see the topic's dead-ends). The 2026-06-30 test proved this the hard way: an un-saved
  coupled cold-boot reverted to asymmetric costs and the fabric would not converge.
- **The coupled CCTV latency was a churn symptom, not primarily an FW-routing problem** — this revises
  the June A8 hypothesis and made the Part 2/3 single-FW VLAN-5 redirect confirmatory rather than
  load-bearing.

# Related

- [Coupled-train RSTP TC-storm (topic)](/.kb/topics/coupled-rstp-tc-storm.md)
- [3×6 exceeds the RSTP node/diameter ceiling (evidence)](/.kb/evidence/3x6-exceeds-rstp-node-ceiling.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md) — `save running-config force`, trunk-rewrite quirk
- [VDS Consist Switch — L2 counters & RSTP](/.kb/components/vds-consist-switch/l2-counters-rstp.md)
