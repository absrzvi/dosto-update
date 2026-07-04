---
type: topic-index
title: DOSTO NEU Topics — Cross-Cutting Subjects
description: Index of system-level topic docs that span multiple device types — addressing, health methodology, coupled-train RSTP, the Fzg-ID namespace problem, and the Zabbix/NMS monitoring model.
project: dosto-neu
tags: [index, topics]
timestamp: 2026-07-04T00:00:00Z
---

# Topics — cross-cutting subjects

These docs teach the system-level knowledge that spans devices — the things you need to
troubleshoot a whole consist (or a whole fleet) rather than a single box. Each carries a
`Proven dead ends` section so you don't repeat an approach the field has already disproven.

* [vlan7 bit-packed addressing & FW reachability](vlan7-addressing.md) — how the per-train vlan7
  IP is derived from the Fzg ID, why the on-CCU formula is wrong, and how to read the ICMP result
  to the Stadler firewall as a *commission-state* signal (loss = commissioned) rather than a fault.

* [L2 network health methodology](l2-health-methodology.md) — the seven-phase sweep: discovery via
  live DHCP leases (not ARP), mapping switches by config fingerprint, the four canonical `show`
  commands, Stadler-facing trunks, and the three-question firewall probe (Q1 ARP / Q2 ICMP / Q3
  TCP).

* [Coupled-train RSTP TC-storm](coupled-rstp-tc-storm.md) — why coupling two consists into one
  RSTP domain produces a perpetual topology-change storm (asymmetric coupler port-cost), the v9
  fix (symmetric cost + blackhole native VLAN + relaxed timers, ≤2×6 only), and why 3×6
  triple-traction exceeds the ~40-node RSTP ceiling and needs a routed boundary.

* [Fzg-ID vs Nomad-internal train_id — two namespaces](fzg-id-two-namespaces.md) — why OBN's
  `train_id` carries two conflicting values (internal box ID that builds CCU/OSPF IPs vs the ÖBB
  Fzg that builds switch hostnames), the cascade the conflation caused (wrong subnet, dead NTP),
  the location-discipline rule, and the box=Fzg resolution.

* [Zabbix / NMS monitoring model](zabbix-nms-model.md) — the SNMP credential model (inverted SW/AP
  usernames), how NMS drives Zabbix host IPs, the `50_6<box>` host-naming formula, and a catalogue
  of monitoring failure modes with their many disproven diagnoses.

# Related

* [Knowledge base index](/.kb/index.md)
* [Components — how each device behaves](/.kb/index.md#components--how-each-device-type-behaves)
* [Fleet — per-train records](/.kb/fleet/index.md)
