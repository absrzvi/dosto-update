# DOSTO SDD v2.2 vs the PM-02 → PM-04 → PM-06 design-freeze deliverable chain

**Date:** 2026-06-01
**Question:** does the design-freeze SDD (`ND-DEL-OBB-035-SDD-002-01 v2.2`) contain everything the Angebot's design-freeze milestone chain requires, and which Stadler inputs are still open?
**Sources:** SDD v2.2 (`design freeze/`); DOSTO Angebot 28.09.2023 (milestone table); bid TD `ND-BID-OBB-036 v0.4` ch.6 (scope + required-info + target dates).

> Note: the Angebot/bid use project code **ND-BID-OBB-036 / -033**; the live SDD is **ND-DEL-OBB-035 / -002**. The `-035` (DEL = delivery) docs are the project-phase successors of the `-036/-033` (BID) docs. Same project, post-sale phase.

## The deliverable chain (from Angebot §3.1 + payment table)

| PM | Deliverable (Lieferobjekt) | Role in freeze |
|---|---|---|
| **PM-02** | IP-Schema + **draft** technical design; pre-info for Stadler | Inputs feed the freeze |
| **PM-03** | **Technical Description (concept design)** = the bid TD `ND-BID-OBB-036 v0.4` | Pre-freeze concept |
| **PM-04** | **DESIGN FREEZE** → *"Review und Abnahme der technischen Beschreibung"* (€56,443.63) | The freeze itself |
| **PM-06** | **Technical Design Document – Network** incl. 3rd-party integration + Functional Test Description | Detailed network design |

The SDD v2.2 is the **PM-04/PM-06-era artifact** — it is the matured "technische Beschreibung" that PM-04 reviews/accepts and that carries the PM-06 network detail the bid TD deferred.

## Coverage map — does the SDD contain what the freeze requires?

| Freeze requirement (bid TD ch.6 "required information") | SDD v2.2 coverage | Verdict |
|---|---|---|
| Physical topology (ring, switch counts, coupler) | §5 Netzwerkarchitektur, §5.4 Backbone (4/5/6-Teiler diagrams), RSTP §5.5 | ✅ frozen |
| VLAN list + purpose + owner | §5.7 VLANs (20-row table), vlans.j2 names | ✅ frozen |
| IP scheme (Nomad VLANs) | §5.2 IP-Schema Nomad VLAN + ranges | ✅ frozen |
| IP scheme (Stadler VLANs, bit-packed) | §5.2 Stadler VLAN octet-derivation table | ✅ frozen (formula); per-device values in per-train IP-Port-Allocation plans |
| Network services (DHCP/DNS/NTP/Radius/routing) | §5.9 Zeitsync, §4.x Server, dhcp_groups | ✅ frozen |
| Firewall policy | §6.13 Firewalling (DENY-ALL) + network-planning 'Firewall' tab + **live CCU iptables** | ✅ frozen & live-validated |
| Stadler-facing allowed wayside connections | §6.18.1 'Erlaubte Verbindungen' (4 endpoints) | ✅ (RDS, ÖBB SFTP, video IPSec dest still TBD) |
| Switchport assignment | §5.3 Switchportbelegung — **states Stadler provides the plan per train type** | ◐ by reference (per-train PDFs), not inlined |
| Multi-traction network design | §5.x Multitraktion + Anforderungen | ◐ **explicitly Variation Order**, gated on 15-June Stadler inputs |
| **QoS / DSCP / 802.1p per VLAN** | only a switch **datasheet capability** line ("DSCP/802.1p Dienstklasse"); network-planning QoS column = `tbd` | ⚠ **GAP — not frozen** |
| **Expected throughput per 3rd-party subsystem** (CCTV/FIS…) | capacity plan = 120 Mbit/s/CCU aggregate only; no per-subsystem figures | ⚠ **GAP — not frozen** |
| 3rd-party VLAN IP/port allocation (for multi-traction sharing) | references IP-Port-Allocation plan; not consolidated in SDD | ⚠ **open (Stadler, 15-June)** |
| Stadler IM / SNMP integration (MIB→MQTT) | §2.11 mentions it | ❌ **DESCOPED — EXT1 PM-16, never ordered** |
| Shared switch-config-mgmt for VDSRail | §6.x Netzwerkkonfigurationsmanagement (OBN) | ◐ Nomad side covered; Stadler-shared part = descoped |
| Detailed **Zone descriptions** (multi-traction) | not present in SDD | ❌ **DESCOPED — relates to EXT1 scope** |

Legend: ✅ frozen · ◐ covered-by-reference / partial · ⚠ in-scope gap · ❌ descoped (EXT1, never ordered).

## ⛔ Scope correction (2026-06-01): multi-traction & 3rd-party integration were descoped into EXT1, never ordered

The extended/3rd-party/multi-traction work was carved out of the base order into the **supplementary offer `ND-BID-OBB-036-TEN-001-EXT1` v2 (07.02.2024)** — milestones **PM-13 → PM-19** + IBS PM-30/31. That offer was **binding only until 01.03.2024** and is **invoiced only after ÖBB orders + acceptance** (§4, §5.2). **ÖBB never ordered it.** Therefore these are NOT contractual obligations and are **out of scope for the PM-04 design freeze**:

| EXT1 milestone | Descoped item | (was previously listed as a "gap/open input") |
|---|---|---|
| PM-14 | RTPI/OBN dynamic-content config | — |
| PM-15 | Engineering Pages for **3rd-party devices** | yes |
| PM-16 | **Zabbix SNMP integration with Stadler IM** (MIB→MQTT) | yes |
| PM-17 | Portal deployment on RDC/Atos | — |
| PM-18 | **3rd-party devices configuration for NMS** | yes |
| PM-19 | **Passenger routing to local CCUs (multi-traction)** | yes |
| PM-30/31 | IBS on-site/remote support | — |

So every "⚠ open Stadler input / 15-June / Variation Order" item from the first pass that relates to **multi-traction, 3rd-party VLAN sharing, 3rd-party throughput, Stadler-IM, or zone descriptions for shared consists** is **descoped, not pending**. The bid TD ch.6 already tagged these "Extended" with a 15-June date — EXT1 is where they went, and the order never followed.

## Conclusion (revised)

**The SDD v2.2 is freeze-ready for the ordered (STANDARD) scope.** Topology, VLANs, IP scheme, network services, and firewall are all present and frozen — and the firewall is **live-validated against real CCUs** (stronger than a paper freeze). PM-04 "review & acceptance of the technical description" is supportable on the standard scope as it stands.

**Remaining in-scope gap is essentially ONE item:**

1. ⚠ **QoS / DSCP-per-VLAN policy** — still only a switch *datasheet capability* line in the SDD; network-planning QoS column = `tbd`. This is a **standard-scope** concern (passenger/staff/management prioritisation), independent of multi-traction, so it does NOT descope with EXT1. The *live CCUs already implement it* (mgmt 0xe0, staff 0xc0, gold 0x40, silver 0x20 — see `iptables-validation_box1-t21`). **Easy win: fold the live DSCP scheme into the SDD → gap closed.**

**Descoped (no longer freeze obligations, per EXT1-never-ordered):** per-subsystem 3rd-party throughput, 3rd-party VLAN IP/port allocation for multi-traction, multi-traction VLAN sharing definition, Stadler-IM SNMP/MIB integration, detailed zone descriptions for shared consists.

**Net:** with multi-traction/3rd-party out of scope, the SDD has **no material design-freeze gap for the ordered scope** except the QoS/DSCP write-back (#1), which is a documentation task using values we already hold from the live fleet. PM-04 can proceed.
