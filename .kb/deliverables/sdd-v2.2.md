---
type: deliverable-ref
title: SDD v2.2 — ND-DEL-OBB-035-SDD-002-01 (design-freeze)
description: The matured DOSTO NEU System/Network Design Document (design-freeze artifact). Covers physical topology, VLANs, IP scheme (incl. bit-packed Stadler scheme), network services, firewall policy, and allowed wayside connections.
resource: /ND-DEL-OBB-035-SDD-002-01_v2.2.docx
project: dosto-neu
tags: [deliverable, sdd, design-freeze, topology, vlan, firewall]
timestamp: 2026-07-04T00:00:00Z
---

# SDD v2.2 — ND-DEL-OBB-035-SDD-002-01

**Resource:** `/ND-DEL-OBB-035-SDD-002-01_v2.2.docx` (do not deep-parse the binary here).

The System/Network Design Document is the **PM-04/PM-06-era** design-freeze artifact — the matured
"technische Beschreibung" that PM-04 reviews/accepts and that carries the PM-06 network detail the
bid TD deferred. Per the 2026-06-01 coverage review it **contains everything the design-freeze
milestone chain requires**, with per-device IP values living in the per-train IP-Port-Allocation
plans rather than the SDD itself.

Key sections (per the coverage map): §5 Netzwerkarchitektur incl. §5.2 IP-Schema (Nomad VLANs +
the **Stadler bit-packed octet-derivation** table), §5.4 Backbone (4/5/6-Teiler diagrams), §5.5 RSTP,
§5.7 VLANs (20-row table), §5.9 time-sync, §6.13 Firewalling (DENY-ALL, live-validated against CCU
iptables), §6.18.1 "Erlaubte Verbindungen" (allowed wayside endpoints; RDS / ÖBB SFTP / video IPSec
destination still TBD).

Older versions on disk: `v2.1`, `v2.1_edit`, `v2.1_edit_fixed`. The v2.2 is current.

# Related

- [vlan7 bit-packed addressing](/.kb/topics/vlan7-addressing.md)
- [Bid TD v0.4 (multitraction)](bid-036-multitraction.md)
- [MAR5 tunnel-architecture template](../deliverables/index.md)
- [Deliverables index](index.md)

# Citations

[1] findings/SDD-v2.2_vs_PM-deliverable-chain_20260601.md — coverage map + deliverable-chain analysis.
[2] sdd-design-freeze-tasklist.md — SDD-002 freeze + SDD-003 comment tracking.
