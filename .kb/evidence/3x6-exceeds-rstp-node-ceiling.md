---
type: evidence
title: 3×6 triple-traction exceeds the RSTP node/diameter ceiling — proven constraint, no timer fixes it
description: Diameter + node-count modelling grounded in the live nv6 topology and VDS support proves 2×6 (36 switches) is RSTP-viable in all coupling orientations but any triple-traction containing a 6-Teiler (42–54 switches) is over the ceiling and needs a routed/L3 boundary.
project: dosto-neu
tags: [coupled, rstp, multitraction, node-limit, diameter, max-age, l3-boundary, field-validated]
maturity: field-validated
timestamp: 2026-06-30T00:00:00Z
resource: /findings/coupling_test_4736-117_105_2026-06-30/ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md
---

# 3×6 triple-traction exceeds the RSTP node/diameter ceiling

## What it proves

A single RSTP domain has two independent hard walls: a **node ceiling** (~40 bridges for a ring;
undefined and to be worst-cased otherwise — VDS/Giorgio) and a **BPDU message-age diameter wall**
(VDS Max Age 20 s + 1 s/hop ⇒ a 19-hop hard wall; conservative IEEE design diameter = 7).

- **2×6 = 36 switches is viable in ALL coupling orientations** (A-A, B-B, A-B). Worst case is **B-to-B
  at 16 hops** — only **3 hops** below the message-age wall. Every coupled case already exceeds the
  conservative-7 figure, which is why convergence is correct but not fast/robust and why the v9
  max-age/forward-delay relaxation is load-bearing, not cosmetic.
- **Any triple-traction containing a 6-Teiler is over the ceiling** — 4+4+6 = 42, 4+6+6 = 48, 6+6+6 =
  54 switches, all **over ~40** → **cannot run as one flat RSTP domain**. **No max-age value, no cost
  tuning fixes a node-count limit** — you cannot time your way past it. It needs a **routed / L3
  inter-consist boundary** (IEC 61375-2-5 FW-termination preferred; switch-native TCDS Routed Mode as
  a Nomad-owned fallback). The v9 cost work does not rescue triple-traction.
- Corollary proven the same day: the **B1↔B3 e0-0 chord cost (`400100`) is load-bearing** in the solo
  tree (the B-car is a ring, not a branch — RSTP must block one link in it), but it is mistuned for v9
  couplers (200× a coupler) so the coupled active tree is valid-but-not-the-designed one. Keep the
  chord cost; re-tune it just above a single trunk hop for v9.

## How it was captured

- Two models built from the live nv6 template trunk descriptions: `scripts/rstp_sim.py`
  (active-tree / which-link-blocks) and `scripts/rstp_diameter.py` (BPDU message-age / hop budget),
  using VDS factory PortPathCost 200000, Max Age 20 s, +1 s/hop.
- Grounded against the 2026-06-12 harvest: full root-path-cost harvest put the far extremity
  **F2-147 at exactly 20 hops** (on the horizon, margin ≈ 0), a **31-hop network diameter for 2×18** —
  correcting the v1.0 report's 14-hop reading off a partial sample.
- VDS/Giorgio confirmed the ceiling reasoning: node max is **40 for a ring**, undefined otherwise
  ("a deep evaluation of the worst condition should be made"); our coupled fabric is a **chain** (one
  coupler link blocked), max-age 38 (firmware ceiling ≈ 36-hop reach) covers the 31-hop 2×18; a 3×18
  (~50 hops) exceeds it.

## Evidence

- [`ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md`](/findings/coupling_test_4736-117_105_2026-06-30/ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md)
  — Q1 chord-cost analysis, Q2 diameter/node matrix (the composition table), model caveats.
- [`REPORT_coupling_test_2026-06-12.md`](/findings/coupling_test_4736-110_119_2026-06-12/REPORT_coupling_test_2026-06-12.md)
  — F2 (corrected 31-hop diameter, ≈0 margin at the far end), Addendum 3 (VDS node-ceiling answer).
- [`PLAN_3x6_scale_beyond_rstp_2026-06-20.md`](/findings/coupling_test_4736-110_119_2026-06-12/PLAN_3x6_scale_beyond_rstp_2026-06-20.md)
  — the architecture recommendation (route-don't-bridge; FW-termination primary, TCDS Routed fallback)
  with the four stress-tested approaches and the firmware's fatal **no-dynamic-multicast** gap
  (`PIM/DVMRP unsupported`) that would black-hole VLAN-5 CCTV if the coupler is naively routed.

## So what

- **≤2×6 is the supported envelope** — v9 (symmetric cost + native-999 + max-age 38) makes it robust
  and field-proven. The v9 release note must state ≤2×6 is RSTP-supported so nobody reads a timer as a
  3×6 fix.
- **Triple-traction is a separate, later workstream** gated on ÖBB confirming it is operationally
  required. Its L3 boundary must be designed to keep CCTV multicast on the Stadler FW path (the switch
  can't dynamically route multicast) and forces resolution of the VLAN-15 FW↔FW question (June A8).
- **B-B 2×6 is the orientation to watch** — first to break if Max Age is ever lowered or a management
  bridge is added to the path.

# Related

- [Coupled-train RSTP TC-storm (topic)](/.kb/topics/coupled-rstp-tc-storm.md)
- [Coupled 2×6 TC-storm captured + fixed (evidence)](/.kb/evidence/coupled-2x6-tc-storm-captured-and-fixed.md)
- [Native-VLAN-1 coupler bridge breaks switch DHCP (evidence)](/.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp.md)
- [VDS Consist Switch — L2 counters & RSTP](/.kb/components/vds-consist-switch/l2-counters-rstp.md)

## Observed on

- [Coupling pair 4736-117 + 4736-105](/.kb/fleet/4736-117-105-coupling.md) — the multitraction test bed for this finding

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/topics/coupled-rstp-tc-storm|coupled-rstp-tc-storm]]
- [[.kb/evidence/coupled-2x6-tc-storm-captured-and-fixed|coupled-2x6-tc-storm-captured-and-fixed]]
- [[.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp|native-vlan1-coupler-bridge-breaks-dhcp]]
- [[.kb/components/vds-consist-switch/l2-counters-rstp|l2-counters-rstp]]
- [[.kb/fleet/4736-117-105-coupling|4736-117-105-coupling]]
