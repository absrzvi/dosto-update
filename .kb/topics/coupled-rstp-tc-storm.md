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
