---
type: evidence-index
title: DOSTO NEU Evidence — Field-Captured Proofs
description: Index of evidence docs that distil raw field-test harvests (captures, traces, before/after tables) into "what it proves / how captured / so what" records, each linking back to the raw files.
project: dosto-neu
tags: [index, evidence]
timestamp: 2026-07-04T00:00:00Z
---

# Evidence — field-captured proofs

Each doc distils a distinct proven finding from raw field evidence (captures, tc-traces,
before/after tables) into a portable record that links back to the raw files under `findings/`.
Where a finding also strengthens a topic, the topic's `# Evidence` section links here.

* [Coupled 2×6 RSTP TC-storm — captured, root-caused, and fixed](coupled-2x6-tc-storm-captured-and-fixed.md) —
  asymmetric coupler cost drives a perpetual ~2s FDB-flush storm; flat symmetric cost 20000 stops it
  (proven both ways across the 2026-06-12 and 2026-06-30 tests); the cost fix alone cleared coupled CCTV latency.

* [3×6 triple-traction exceeds the RSTP node/diameter ceiling](3x6-exceeds-rstp-node-ceiling.md) —
  2×6 (36 switches) is viable in all orientations (B-B worst at 16 hops); any triple-traction with a
  6-Teiler (42–54 switches) is over the ~40-node ceiling and needs a routed/L3 boundary — no timer fixes it.

* [Native-VLAN-1 coupler bridge breaks switch DHCP](native-vlan1-coupler-bridge-breaks-dhcp.md) —
  coupler still at native VLAN 1 bridges the shared 192.168.1.0/24 management segments; switch DORA
  dies at OFFER and half the fabric can't hold a lease; fixed by v9 M2 native-999.

* [Dataless-display transient — cold-boot repro kit](kmdev-coldboot-dataless-display-repro.md) —
  a controlled cold-power-cycle kit that captures "display links but carries no ZFR data", rules out
  cabling/surge, and pins the leading cause to a KMdev module boot crash.

* [OBN silently drops healthy switches from its report on cold-bypass](obn-numbering-drops-healthy-switches-on-bypass.md) —
  a bench repro proving one cold-bypassed switch makes OBN's `normalise_devices()` delete every switch
  it couldn't number — 10 healthy switches collapse to a 2-row report with no truncation signal.

* [OBN coach-numbering is fragile to a single lost LLDP edge](obn-numbering-fragile-to-single-edge-loss.md) —
  A/B of two live nv6 trains: one down `B3↔B2` cable drops 5 healthy rear switches + 7 APs (13/18 vs
  18/18 healthy); a redundant-path fallback recovers them `off-expected-wiring`, no-op on the healthy train.

* [Two permanent OBN fixes — coupler STP robustness + Fzg-ID identity](obn-coupler-stp-and-fzg-id-permanent-fix.md) —
  live-CCU analysis defining 4 MRs: 100×-divide coupler port-cost + add max-age/forward-delay to stop the
  coupled TC storm; one per-box `fzg_id` as single source of truth to end vlan7 + hostname hand-patching.

* [OBN platform codebase review — improve, not rewrite](obn-platform-review-improve-not-rewrite.md) —
  adversarially-verified multi-agent review (v2.3.12): the defect load is two systemic common-fix patterns
  (unguarded SNMP-None + silent-success), a hand-rolled-14× report layer, and a committed-plaintext-creds cluster.

# Related

* [Knowledge base index](/.kb/index.md)
* [Coupled-train RSTP TC-storm (topic)](/.kb/topics/coupled-rstp-tc-storm.md)
* [Components — how each device behaves](/.kb/index.md#components--how-each-device-type-behaves)
