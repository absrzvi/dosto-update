---
type: topic
title: Coupled-Train RSTP Topology-Change Storm & the Node-Count Ceiling
description: Why coupling two consists into one RSTP domain produces a perpetual topology-change storm (asymmetric coupler port-cost), the v9 fix (symmetric cost + blackhole native VLAN + relaxed timers), and why triple-traction exceeds RSTP entirely and needs a routed boundary.
project: dosto-neu
tags: [rstp, coupled-train, multitraction, topology-change, coupler, node-limit, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

When two consists are physically coupled, their backbone switch fabrics bridge across the
coupler trunks and merge into **one RSTP domain**. This is where two distinct problems appear:

1. A **perpetual topology-change (TC) storm** — a continuous fleet-wide FDB flush caused by an
   asymmetric coupler port-cost driving a never-resolving designated-role duel on the active
   coupler link.
2. A hard **node-count ceiling** — RSTP tops out around 40 bridges. Two 6-car consists (~36
   switches) fit under a relaxed max-age; three (~54) do not, at any timer value.

Both are properties of stretching a single spanning-tree domain across couplers. The fix for (1)
is a config change; the fix for (2) is architectural (a routed inter-consist boundary).

> **Portability note.** The mechanism (asymmetric P2P cost → role duel → TC churn) and the
> node-count reasoning are generic RSTP. The exact cost values, VLAN numbers, timer values, hop
> counts, and the "v9" template label in the `EXAMPLE (DOSTO NEU)` block are deployment-specific.

# Problem 1 — the perpetual TC storm

**Symptom.** On a coupled pair, every switch logs "Flushing all entries" roughly every 2 s,
continuously. A solo control consist shows zero such events. The constant FDB flush produces
permanent unknown-unicast flooding across the coupler and floods unsnooped multicast both ways.

**Mechanism.** Both ends of the *active* coupler link keep sending each other a designated
"proposal" every hello → sync/agreement → a topology change → flush — and then repeat, forever.
The driver is an **asymmetric port-cost**: the two ends of the same point-to-point coupler link
carry different (large) cost values, and the mismatch sustains the role duel. (An overflow theory
was **refuted** — the switch accepts costs well above the values in play; asymmetry is the
driver, not overflow.)

**Fix — symmetric coupler cost.** Set the same sane cost on **both** ends of every coupler port.
This stops the churn at the exact moment it is applied. Do not chase a "cost < 2^N" bound — that
framing came from the refuted overflow theory. The requirement is **symmetry**, plus a small
value that keeps the coupler a low-preference path.

**Companion fixes that ship with it:**
- **Blackhole native VLAN on coupler trunks.** End-wagon switches carry a management SVI on a
  shared `192.168.1.0/24`; if the coupler trunk's native VLAN is VLAN 1, coupling *bridges the
  switch-management subnet between the two trains*. Set the coupler native to an unused,
  named "blackhole" VLAN, and set native + prune in **one** command (setting native alone resets
  the prune set). Keep the CCTV VLAN on the coupler — do not prune it (that is a Stadler-side FW
  matter, not an L2 prune).
- **Relaxed STP timers** to cover the coupled diameter: raise forward-delay first, then max-age
  (the firmware enforces `2×(fwd_delay − 1) ≥ max_age`, so order matters). Persist explicitly.

**Observing it.** `show spanning-tree` polling *misses* the role flap — it is too fast. Enable
RSTP/coupled debug logging and read the event log; there is no RSTP counter command.

# Problem 2 — the node-count ceiling

RSTP has a practical limit around **40 bridges** in one domain (ring limit; non-ring behaviour is
undefined and should be evaluated worst-case). Under this:

- **2×6 ≈ 36 switches — viable.** Measured diameter ~31 hops; a relaxed max-age covers it (with
  margin ≈ 0 at the far end before the fix, so the timer relaxation is load-bearing, not
  cosmetic).
- **3×6 ≈ 54 switches — NOT viable.** This is over the 40-node ceiling. **No max-age value fixes a
  node-count limit** — you cannot time your way past it. Triple-traction therefore requires a
  **routed inter-consist boundary** (an L3 / IEC-61375-style separation at the coupler that also
  resolves the shared `192.168.1.0/24` management overlap), not stretched RSTP.

Triple-traction is a real service requirement, so the routed-boundary solution is a required
deliverable — a separate, larger workstream from the coupler-config fix. The coupler-config fix
must not foreclose that migration.

# Proven dead ends — do NOT repeat these

> Kept so a fresh agent does not re-test these on a coupled pair.

1. **Asymmetric coupler port-cost.** Different large cost values on the two ends of a coupler P2P
   link sustain the designated-role duel → perpetual TC churn. The template that made cost a
   function of `train_id` (so each train's end got a different number) is the root cause. Use a
   **symmetric** cost on both ends.
2. **Scaling RSTP past ~40 nodes (i.e. 3×6).** No timer, no cost tuning, no max-age value makes a
   54-node single domain converge stably. It needs a routed boundary. Stop trying to make RSTP
   span triple-traction.
3. **Pruning the CCTV VLAN off the coupler to "fix" a coupled-service outage.** During a coupling
   test, pruning the camera VLAN cleared cross-train FDB contamination but did **nothing** for the
   actual service outage — service only recovered on full physical decouple. The outage is
   coupled-L2-wide (prime suspect: the FW↔FW transit VLAN poisoning Stadler routing state), not
   the camera-VLAN bridge. Pruning that VLAN is not a fix and there is no service reason to do it.
4. **Believing "cables removed" means the coupler link is down.** A flapping/still-live coupler
   cable keeps a merged RSTP domain (and its churn) alive even after someone says the train is
   decoupled. Always verify the coupler port **link-state** before concluding the domains have
   separated.
5. **Setting the timers in the wrong order.** `max-age` before `forward-delay` is rejected — the
   firmware enforces `2×(fwd_delay − 1) ≥ max_age`. Raise forward-delay first.
6. **Fixing it at runtime and leaving it there.** Every coupled fix (symmetric cost, native-999,
   debug logging, prunes) is **runtime-only** and is **WIPED by a power-cycle or by `obn update c`
   from a v8 package** — which reverts the coupler cost to the asymmetric `train_id`-derived value and
   re-arms the storm. Proven the hard way 2026-06-30: an un-saved coupled cold-boot reverted to
   asymmetric costs and the fabric would not converge. The durable fix is the **template change** (v9
   MR across all four repos); until then, `save running-config force` per switch is mandatory and only
   survives until the next `obn update c`.
7. **Applying the cost fix ONLY and calling the coupled fabric healthy.** The TC-storm fix (symmetric
   cost) and the switch-DHCP fix (native-999) are **independent**. With cost fixed but the coupler
   still at **native VLAN 1**, the two trains' shared `192.168.1.0/24` switch-management segments
   bridge across the coupler, switch DORA dies at OFFER (never REQUEST), and half the fabric can't
   hold a lease. A cost-only test leaves this DHCP break live. Apply **both** M1 (cost) and M2
   (native-999).
8. **Reading "half the switches vanished from the lease list" as a fabric/power outage.** On a coupled
   pair under active testing, switches sit on a **dynamic DHCP pool**; every fabric disruption (a
   Stadler port bounce, a TC re-convergence burst, or the native-VLAN-1 bridge above) interrupts a
   switch's renewal and it loops on the next DISCOVER — so IPs rotate and only ~9/18 hold a completed
   lease at once. The switches are alive and forwarding (ARP + a stable RSTP root prove it); it is a
   **management-plane** DHCP problem, not a data-plane outage. (Note: a *persistent* same-9-missing set
   that stays absent from **ARP** — not just the lease list — after a clean cold boot is a separate
   hardware/power issue, e.g. 117 on 2026-06-30, not a coupling problem.)

# Evidence

Field-captured proofs behind this topic (raw harvests + traces link from each):

- [Coupled 2×6 RSTP TC-storm — captured, root-caused, and fixed](/.kb/evidence/coupled-2x6-tc-storm-captured-and-fixed.md)
  — the storm present under asymmetric cost (2026-06-12, stopped at the exact second by reverting to
  20000) and the mirror proof (2026-06-30, symmetric cost pre-staged → storm never arose); plus the
  cost-fix-alone CCTV-latency recovery that revised the June A8 FW-routing hypothesis.
- [3×6 triple-traction exceeds the RSTP node/diameter ceiling](/.kb/evidence/3x6-exceeds-rstp-node-ceiling.md)
  — diameter + node-count modelling (31-hop 2×18, B-B worst at 16 hops, ≈0 margin at the far end) and
  the VDS node-ceiling answer; why 42/48/54-switch triple-traction needs a routed boundary.
- [Native-VLAN-1 coupler bridge breaks switch DHCP](/.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp.md)
  — the DISCOVER→OFFER→loop break, the 57-MAC cross-train VLAN-1 leak FDB smoking gun, and the
  native-999 fix (leak 57→39→10, 9→18/18 recovery).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Test: 4736-110 (Fzg 138) + 4736-119 (Fzg 147), B-to-B coupled, 2026-06-12. Crossed coupler
  links B1↔B3 (normal).
- The asymmetric costs in play were `137999999` (Fzg 138 end) vs `146999999` (Fzg 147 end) —
  the `train_id`-derived formula. **Symmetric cost `20000` on both ends stopped the churn at the
  exact second.**
- Coupler trunk fix (combined): `switchport mode trunk native vlan 999 prune allow 5,15`; add
  `vlan 999 name blackhole-native`; VLAN 5 (CCTV) kept.
- Timers: `configure spanning-tree forward-delay 20` **then** `max-age 38`; persist with
  `save running-config force`. Measured coupled diameter 31 hops; max-age 38 ≈ 36-hop reach.
- These ship in the **v9** switch-config templates (all four repos: nv6/nv4/fv5/fv6),
  covering the **≤2×6 envelope only**. 3×6 (54 switches) is over the ~40-node RSTP ceiling and is
  routed to the separate routed-boundary workstream (candidate: VDS firmware TCDS routed mode,
  switch-manual §21.5).
- Runtime coupled changes (debug logging, prunes, cost overrides) all clear on power-cycle.

# Related

- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md) — trunk-rewrite quirk, `save running-config force`
- [Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md) — the `train_id`-derived cost formula is the same class of `train_id` misuse
- [vlan7 addressing](/.kb/topics/vlan7-addressing.md) — odd-Fzg FW IP found during the same coupling test
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] Session memory `project_coupled_rstp_tc_storm` — coupling test 4736-110+119 (2026-06-12); asymmetric-cost driver proven by intervention; VLAN-5 prune refuted; odd-Fzg FW IP; v9 change-list.
[2] Session memory `project_3x6_triple_traction_required` — 3×6 = 54 switches > RSTP 40-node ceiling; routed-boundary requirement (2026-06-20).
[3] Coupling test report `findings/coupling_test_4736-110_119_2026-06-12/` and v9 change-list `PLAN_v9_switch_config_changelist_2026-06-20.md`.
[4] Coupling test 4736-117+105 (2026-06-30): `costs_before_after.md` (symmetric-cost PASS, CCTV-resolved-by-cost-alone, native-VLAN-1 DHCP root cause + native-999 fix) and `ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md` (chord cost, diameter/node matrix). Distilled into `/.kb/evidence/`.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/evidence/coupled-2x6-tc-storm-captured-and-fixed|coupled-2x6-tc-storm-captured-and-fixed]]
- [[.kb/evidence/3x6-exceeds-rstp-node-ceiling|3x6-exceeds-rstp-node-ceiling]]
- [[.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp|native-vlan1-coupler-bridge-breaks-dhcp]]
- [[.kb/components/vds-consist-switch/cli-and-management|cli-and-management]]
- [[.kb/topics/fzg-id-two-namespaces|fzg-id-two-namespaces]]
- [[.kb/topics/vlan7-addressing|vlan7-addressing]]
- [[.kb/topics/l2-health-methodology|l2-health-methodology]]
- [[.kb/fleet/index|index]]
