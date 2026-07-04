# Plan — IGMP snooping + querier for VLAN-5 CCTV multicast

**Date:** 2026-06-20 (VDS answers folded in 2026-06-23) · **Author:** AR + Claude · **Status:** PLAN — scoped, not started. VDS/Giorgio has answered the design questions (see "VDS answers" below). Separate workstream from v9 and from the 3×6 routed-boundary work.

## Problem
VLAN-5 CCTV multicast is **unsnooped fleet-wide** (no IGMP config in any of the 4 template repos — verified). Every camera stream floods to every port on every switch. Coupling test measured ~3 kpps of VLAN-5 multicast crossing the coupler continuously; report named unsnooped VLAN-5 the prime suspect for the multicast component of the June storm (REPORT §F3, rec #5).

## Goal (success criteria)
- [ ] CCTV multicast confined to ports with active group members (recorders/displays) — NOT flooded fabric-wide.
- [ ] **Zero CCTV stream loss** end-to-end (the failure mode of snooping-without-proper-querier is silent blackholing — must verify streams actually reach recorders/displays, not just counters).
- [ ] Stable on a coupled pair (no querier war, no flap on couple/decouple).
- [ ] RSTP BPDUs (`01:80:C2:*`) unaffected (not caught by snooping/storm-control).

## VDS answers (Giorgio, 2026-06-23)

General guidance: *"Multicast forwarding is a complex task that should be configured based on the specific requirements. You can also consider the possibility to apply a static IGMP configuration or to filter some IGMP messages at coupler level."* → two extra levers on the table: **static IGMP groups** (deterministic, no querier dependency) and **IGMP filtering at the coupler** (contain cross-coupler multicast without snooping the whole fabric).

| # | Question | VDS answer | Consequence for this plan |
|---|---|---|---|
| a | RSTP BPDUs (`01:80:C2:xx`) + reserved control frames exempt from snooping pruning + storm-control? | **Yes** | Risk #2 cleared. BPDUs safe under snooping + storm-control on v2.0.4. |
| b | Snooping ON but no active querier — flooded (safe) or pruned (CCTV loss)? | **Pruned** | **Querier is MANDATORY.** Confirms the blackhole trap (risk #1) is real, not theoretical. Snooping must never ship without a working querier. |
| c | Querier election across a coupled composition — lowest mgmt-IP wins cleanly across both consists, and each train re-elects its own on decouple? | **Yes** | **Option 1 (switch-side querier, lowest-IP election) is viable.** Coupled/decoupled election behaves. Still verify on a real pair (VDS confirms behaviour, not our exact IP layout). |
| d | Interaction with v9 coupler (native VLAN 999, prune allow 5,15) — snooping/querier OK with VLAN 5 carried *tagged* over the coupler? | *"It should work, however I prefer to check this in the lab"* | **Lab gate retained.** This is the one item VDS will not sign off on paper → the coupled-pair lab test (step 4) stays mandatory before fleet rollout. |
| e | Does snooping need an SVI/IP on the snooped VLAN, or L2-only on VLAN 5? | *"IGMP querier requires an IP address configured on interface VLAN1"* | **Querier rides VLAN1 mgmt IP** (which every switch already has). Snooping is L2 on VLAN 5; the querier source does NOT need an SVI on VLAN 5. Matches the firmware §15.4 note. No new IP plumbing needed. |

**Net:** the design is now decided — **global snooping + switch-side querier on VLAN1, lowest-IP election** (Option 1). The only remaining unknown VDS flagged is (d): snooping/querier over a *tagged* VLAN-5 coupler trunk with native-999, which they'll only confirm in the lab. Static IGMP / coupler-level filtering remain as fallbacks if the querier path proves fragile.

## The load-bearing decision: WHO is the querier
Snooping without a querier can **blackhole** multicast (switch prunes streams it never sees joins for) — worse than flooding. So this is **snooping + querier**, and querier placement is the real design choice.

Firmware facts (switch manual §15.3–15.4):
- Snooping is **global**: `configure ip igmp snooping enable` (not per-VLAN). Aging-time 100–1000s.
- Querier uses the **VLAN1 management-interface IP**: `configure ip igmp querier enable`. Query-interval default 125s (must be < join aging timer).
- **Built-in querier election:** "Only one querier should be active at a time. If enabled on more [than one], the **lowest mgmt IP becomes active**, others suspend." → handles the coupled-train duplicate-querier case automatically (lowest-IP wins across both consists).

Options:
1. **Switch-side querier, rely on lowest-IP election** (simplest; firmware-native). On a coupled pair the lowest-IP switch across both trains becomes sole querier. Risk: querier identity changes on couple/decouple — acceptable if election is fast and streams re-converge.
2. **Stadler FW as querier** (if the FW already queries VLAN 5). Avoids switch-side querier entirely. Needs Stadler confirmation. Aligns with the future 3×6 routed-boundary design where CCTV crosses via the FW path anyway.
3. **Designated querier switch per consist** (e.g. the A3/D1 switch) with a deterministic low mgmt IP. More control, more template logic.

## Risks / traps (why this is NOT a v9 line item)
1. **Querier blackhole** — snooping enabled, no/blackholed querier → streams silently dropped. Test end-to-end, not counters.
2. **BPDU interaction** (Giorgio caveat, REPORT rec #5) — confirm `01:80:C2:*` BPDUs bypass any storm-control/snooping logic on build v2.0.4. Verify with VDS.
3. **Coupled querier election** — verify the lowest-IP election actually behaves on a real coupled pair (couple → one querier; decouple → each train re-elects its own).
4. **Fleet-wide blast radius** — snooping is global and changes multicast forwarding for EVERY train, coupled or not. A bad querier config could drop CCTV on a solo train. This is why it must not ride the v9 coupler test.
5. **Interaction with 3×6 routed boundary** — switch has no dynamic multicast routing; once the coupler is routed, CCTV multicast crosses via the Stadler FW path, not the switch fabric. Snooping is a within-consist L2 optimisation — compatible, but design querier placement knowing the boundary may go L3. Don't solve twice.

## Interim lighter lever (if flood load is urgent before this lands)
`rate-limit multicast` on coupler `e0-2` ports (today's coupler rate-limit is broadcast-only — REPORT rec #5). Caps the cross-coupler flood without the querier complexity. Stopgap, not a fix.

## Sequencing
1. ~~**Decide querier strategy**~~ ✅ **DECIDED (VDS 2026-06-23):** Option 1 — global snooping + switch-side querier on VLAN1 mgmt IP, firmware lowest-IP election. Static IGMP / coupler-filtering held as fallbacks.
2. **Bench:** enable snooping + querier on a single consist; verify CCTV streams reach recorders/displays end-to-end; check `show ip igmp`.
3. ~~**VDS gate:** confirm BPDU exemption + snooping behaviour~~ ✅ **DONE (VDS 2026-06-23):** BPDUs exempt (a); no-querier = pruned/blackhole (b); querier on VLAN1 IP (e).
4. **Coupled-pair lab test (VDS-requested, item d):** snooping/querier over the *tagged* VLAN-5 coupler trunk with native-999; verify querier election on couple/decouple, no stream loss, no flap. **VDS will only sign off item (d) in the lab → this gate is mandatory before fleet.**
5. **Template** (4 repos) → `obn update c` → fleet. Possibly v10 or folded into the 3×6 workstream.

## Config sketch (per switch, once strategy decided)
```
configure ip igmp snooping enable
configure ip igmp snooping aging-time 120
configure ip igmp querier enable            # only where querier desired; lowest-IP wins
configure ip igmp querier query-interval 60 # must be < aging-time
# verify:
show ip igmp                                 # snooping enabled, active querier addr/vlan/port
```

## Not in scope here
- The 3×6 routed boundary (separate plan: PLAN_3x6_scale_beyond_rstp).
- v9 coupler-correctness fix (separate: PLAN_v9_switch_config_changelist).
