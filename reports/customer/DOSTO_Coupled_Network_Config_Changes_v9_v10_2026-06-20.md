# DOSTO-NEU — Planned Consist-Switch Configuration Changes (v9 / v10 / triple-traction)

**Prepared by:** Nomad Digital · **Date:** 2026-06-20 · **For:** VDS Rail Support and ÖBB
**Context:** Outcome of the 2026-06-12 coupled-train test (4736-110 + 4736-119) and a full review of the VDS Consist-Switch configuration templates across all four fleets (nv6 / nv4 / fv5 / fv6).

This table lists every planned change. The **Configuration change** column is the technical detail (for VDS Rail); the **Operational effect / reason** column explains the impact (for ÖBB). The **Status** column shows what is decided versus pending validation or a decision.

---

## Switch-config v9 — coupled-network correctness (2× 6-car envelope)

| # | Change | Configuration change (VDS) | Operational effect / reason (ÖBB) | Status |
|---|---|---|---|---|
| v9-1 | Symmetric coupler port-cost | Replace the `train_id`-derived RSTP port-cost on all four Frontkupplung ports (e0-2 on A1/A3/B1/B3) with a single fixed value `20000`, identical on both ends of every coupler link and on every train. | Eliminates the continuous RSTP topology-change ("flush every ~2 s") condition observed when two trains are coupled. Root cause: the two ends of a coupler link previously had different costs, so RSTP never settled. Field-validated on 2026-06-12 (setting cost = 20000 stopped it instantly). | **Decided** — runtime re-test on a coupled pair before the template release |
| v9-2 | Coupler native-VLAN containment | Change coupler trunk to combined form `switchport mode trunk native vlan 999 prune allow 5,15` (native moved from VLAN 1 to an unused VLAN 999, allowed set unchanged). | Stops untagged / VLAN-1 traffic crossing between coupled trains — including the switch-management subnet (192.168.1.0/24) which is identical on every train. Only the intended VLAN 5 (CCTV) and VLAN 15 (multi-traction transit) cross the coupler. | **Decided** — runtime re-test before release |
| v9-3 | Define VLAN 999 (black-hole) | Add `vlan 999 name blackhole-native` to the VLAN definition file in each fleet template. | Supporting change for v9-2 — the unused "drain" VLAN for untagged traffic. No user-visible effect. | **Decided** |
| v9-4 | RSTP timer widening | Set `spanning-tree forward-delay 20` then `spanning-tree max-age 38` (order required: firmware enforces 2×(FwdDelay−1) ≥ MaxAge), identical on every switch in every fleet. Currently no timers are set (firmware defaults 20 / 15). | Gives the merged 2× 6-car network adequate BPDU "reach". Measured coupled network diameter is 31 hops with the far end sitting exactly on the default 20-hop limit (zero margin). Per VDS guidance (max-age 37–38). Covers 2× 6-car with margin. | **Decided** — value per VDS recommendation |
| v9-5 | Consistency & documentation | Fix `fv5-100-A3` port description typo ("Frontkupplung A2"→"A3"); add explanatory comments on the load-bearing coupler VLAN set (5,15) and the internal-ring tie-break cost (400100). | Housekeeping so the four fleet templates stay consistent and future edits don't undo load-bearing settings. No operational effect. | **Decided** |

**v9 supported envelope:** up to **2× 6-car** (36 switches), under the RSTP 40-node limit.

---

## Switch-config v10 (candidate) — multicast hygiene

| # | Change | Configuration change (VDS) | Operational effect / reason (ÖBB) | Status |
|---|---|---|---|---|
| v10-1 | IGMP snooping + querier for CCTV | Enable `ip igmp snooping` globally and an IGMP querier (querier uses the VLAN-1 management IP; firmware auto-elects the lowest-IP querier across coupled trains). Query-interval < snooping aging-time. | CCTV (VLAN 5) multicast is currently flooded to every port on every switch (~3 kpps continuously across the coupler). Snooping confines each camera stream to ports that requested it, reducing fabric load. | **Proposed** — bench + coupled-pair validation pending. **VDS to confirm, on build v2.0.4:** (a) RSTP BPDUs (01:80:C2:xx) and other reserved control frames are exempt from snooping pruning and storm-control; (b) with snooping on but **no active querier**, is multicast flooded (safe) or pruned/black-holed (CCTV loss)? (c) querier election across a **coupled** composition — does the lowest mgmt-IP win cleanly across both consists, and does each train cleanly re-elect its own on decouple? (d) interaction with the v9 coupler config (native VLAN 999, trunk `prune allow 5,15`) — does snooping/querier behave correctly with VLAN 5 carried tagged over the coupler? (e) does snooping require an SVI / IP on the snooped VLAN, or does it work L2-only on VLAN 5? |
| v10-2 | Coupler multicast rate-limit (interim option) | Add `rate-limit multicast` on coupler e0-2 (today's coupler rate-limit is broadcast-only). | Lighter-weight cap on cross-coupler multicast flood if needed before v10-1 is validated. | **Proposed** — optional stopgap |

---

## Triple-traction (3× 6-car) — separate architecture workstream

Required because ÖBB plan to couple up to **3× 6-car** in service. **3× 6-car = 54 switches, which exceeds the RSTP 40-node protocol limit** (confirmed by VDS) — no timer or cost value can fix a node-count limit. This needs a different mechanism and is **not** part of v9/v10.

| # | Change | Approach (VDS) | Operational effect / reason (ÖBB) | Status |
|---|---|---|---|---|
| TT-1 | Route the inter-consist boundary (do not bridge) | Terminate Layer-2 at the consist boundary and route between consists (IEC 61375-2-5 pattern). **Primary:** Stadler firewalls as the L3 boundary (they already relay inter-consist traffic over VLAN 15). **Fallback:** switch-native TCDS Routed Mode + R-NAT (§21.5) if the firewall path is not adopted. | Each train's switch network stays its own ≤18-node domain regardless of how many trains couple, so the 40-node limit never applies. Enables 3× 6-car (and beyond). | **Decision needed** — see gates below |

**Gates before any triple-traction build:**
1. **ÖBB** — confirm the operational requirement and timeline for 3× 6-car. *(Confirmed in principle 2026-06-20; timeline TBD.)*
2. **Stadler** — characterise firewall behaviour when consists are coupled over VLAN 15 (this is also the prime suspect for the CCTV/display degradation seen at 2× 6-car), and confirm whether they will own the inter-consist L3 boundary.
3. **VDS Rail** — confirm TCDS Routed Mode + R-NAT behaviour on firmware build v2.0.4, the static-only multicast limitation (no PIM/DVMRP), and whether routed mode has been deployed in revenue service elsewhere.

---

## Specific questions for VDS Rail
1. **v9 timers:** confirm `forward-delay 20` / `max-age 38` as the recommended set for the 2× 6-car (36-node) case.
2. **v10-1 IGMP snooping + querier (build v2.0.4):**
   a. Are RSTP BPDUs (01:80:C2:xx) and other reserved control frames exempt from snooping pruning and from storm-control?
   b. With snooping enabled but **no active querier**, is multicast flooded (fail-safe) or pruned/black-holed (CCTV loss)? — this determines our failure mode.
   c. Querier election across a **coupled** composition: does the lowest management-IP win cleanly across both consists, and does each train cleanly re-elect its own querier on decouple?
   d. Interaction with the v9 coupler config (native VLAN 999, trunk `prune allow 5,15`): does snooping/querier behave correctly with VLAN 5 carried tagged across the coupler?
   e. Does snooping require an SVI/IP on the snooped VLAN, or does it operate L2-only on VLAN 5?
3. **Triple-traction:** confirm TCDS Routed Mode + vTBN + R-NAT behaviour on v2.0.4, the static-only multicast routing limitation (no PIM/DVMRP), and whether routed mode has been deployed in revenue service.

## Note for ÖBB
- **v9 makes the confirmed 2× 6-car coupling robust** and is field-validated; it ships first.
- **v10** is multicast hygiene, validated separately.
- **3× 6-car** is a distinct workstream requiring a routed inter-consist design and coordination with Stadler — not deliverable by a switch-config change alone.
