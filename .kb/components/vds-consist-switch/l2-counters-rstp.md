---
type: component-knowledge
title: VDS Rail Consist Switch — L2 Counters & RSTP
description: How to read the VDS switch error counters (RX crc, carrier-false, collisions, pause frames) and RSTP root/roles/states — what "healthy" looks like, the false alarms, and the dead ends already disproven on live hardware.
component: vds-consist-switch
vendor: VDS Rail
project: dosto-neu
tags: [switch, l2, counters, rstp, crc, carrier-false, pause-frames, health, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

The **VDS Rail Consist Switch** is a managed industrial L2 Ethernet switch, one-per-FIS-unit in a
rail consist backbone. This document is about **reading its health surface**: the per-port error
counters, the RSTP topology, and how to tell a real physical-layer fault from the many benign
signatures a rail consist produces. It complements the
[CLI & management](cli-and-management.md) doc (how to talk to the switch) and the
[firmware-flashing](firmware-flashing.md) doc (how to update it).

- **Identify by:** MAC OUI `a0:59:3a`.
- **Firmware family referenced here:** `sw-std-ng` 7.4.x (behaviour verified on build 7.4.2-77411).

> **Portability note.** All facts below are generic to this switch family. Deployment-specific
> values (IP subnets, VLAN numbers, per-train port roles) appear only inside the clearly-marked
> `EXAMPLE (DOSTO NEU)` block and must be re-derived for any other deployment.

# The counter surface

`show interface <port> details` exposes the per-port frame counters. Run it per port on every
switch. Interpret them against these thresholds:

| Counter | Meaning | Healthy threshold |
|---|---|---|
| `RX errors` / `runts` / `giants` / `frag` / `jabber` | Frame-level RX errors | 0. A handful over millions of packets is noise (one corrupted frame on connect, EMI transient). |
| `RX crc errors` | CRC mismatch on receive | **Must be 0.** Any sustained count = bad cable / dirty connector / EMI. |
| `TX crc errors` | CRC on the transmit side | **Must be 0.** |
| `carrier false` | Link-layer instability events / surge-protection trips | **Must be 0.** Non-zero = physical-layer problem (cable, SFP, vibration, surge). |
| `Excessive collisions` / `Late collisions` | Half-duplex contention | **Must be 0** on any full-duplex link (all backbone/trunk links are full-duplex). |
| `pause frames received` / `sent` | 802.3x flow-control pressure | Non-zero = an egress queue is overflowing somewhere upstream — trace the bottleneck. |

**The pairing rule.** RX errors on side A of a link usually pair with a TX-side problem on side B.
When a port shows sustained CRC or carrier-false, always pull `show interface <port> details` on
**the port at the other end of the same physical link** before concluding which end is at fault.

**Reading a rate from counters.** The switch has no live-rate command. Take two
`show interface <port> details` snapshots N seconds apart and diff the byte counters:
`rate_mbps = (rx_bytes_2 - rx_bytes_1) * 8 / (ts2 - ts1) / 1e6`.

# What "healthy" looks like

A clean consist shows **0 / 0 / 0 / 0** across RX-errors / CRC / carrier-false / collisions on
every enabled port of every switch, with a single stable RSTP root that all switches agree on.
On the reference 6-car baseline, ~500 enabled ports across 18 switches were all clean bar a single
RX error on one port against millions of packets — that is noise, not a fault.

Idle/passenger-traffic utilisation is low: active inter-coach backbone trunks run ~1.5% of a 10G
link; the Stadler-firewall trunk runs ~1.5% of 1G. A trunk sitting near 0 with no clients (e.g. a
Wi-Fi-AP trunk on an empty train) is expected, not a fault.

# RSTP — root, roles, states

`show spanning-tree` on each switch. Confirm:

- **One root**, and every switch reports the **same root MAC**. Multiple roots or a root MAC that
  changes between reads = an unstable topology (find the link causing the TCNs).
- **Port roles** (root / designated / alternate) and **states** (FWD / BLK / LEARN) are stable
  across repeated reads. A port cycling FWD↔BLK is churning the topology.
- On a **solo** consist, front-coupler trunk ports are DOWN and therefore not in the STP topology —
  that is expected. STP behaviour changes materially when a **second consist is coupled** (see the
  coupled-train TC-storm topic in Related); asymmetric coupler path-cost can drive a TC storm.

# Real red flags (act on these)

| Observation | Action |
|---|---|
| Sustained `RX crc errors` (any real count) | Replace cable/SFP at the link endpoints; inspect connectors. |
| Sustained `carrier false` | Physical-layer instability — cable / vibration / surge protection tripping. |
| `pause frames received` non-zero | Egress queue overflow on the upstream switch — trace the bottleneck. |
| Multiple STP roots, or root flapping | Topology unstable — find the link generating TCNs. |
| Inter-coach trunk negotiated below expected speed (1G where 10G expected) | Auto-negotiation problem — check both ends. |
| Sustained inter-coach utilisation > 70% | Real capacity issue — find the saturating device. |

# Common false alarms (do NOT escalate these)

| Observation | Why it's benign |
|---|---|
| 100% ICMP loss to the Stadler firewall on vlan7 | A commissioned FW drops ICMP by policy. This is a *commission-state* test, not a fault — see the L2-health methodology (Q1/Q2/Q3). |
| `e0-1` link DOWN on a couple of switches | Those are end-of-train switches; `e0-1` has no neighbour. Expected. |
| Front-coupler trunks (`e0-2`) DOWN on a solo train | No second consist coupled. Expected. |
| One ZFR-side port shows RX = 0 packets | ZFR is a redundant pair sharing one IP; only one is actively transmitting at a time. Expected. |
| RDC trunk RX near 0 | RDC powered off / idle. Usually fine. |
| Single-digit RX errors over millions of packets | Noise — one corrupted frame / EMI transient. Not actionable. |
| Firmware version differs slightly across the fleet | Document for fleet management; not a fault per se. |
| `show system` returns no hostname | The switch does not expose hostname this way — identify by config fingerprint. |

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not burn hours re-testing what has already been
> disproven on live hardware.

1. **Summing every inter-coach trunk to get "train throughput" double-counts.** Traffic that
   traverses multiple cars is counted once per trunk it crosses. The headline figure is
   **average per-active-trunk Mbps**, never the sum across all trunks. (On the reference baseline,
   the correct number was ~140 Mbps average per active trunk → ~1.5% of 10G; the naive sum was
   several times larger and meaningless.)

2. **A switch missing from ARP/leases whose neighbours LLDP-see each other directly is NOT a
   re-cabling event.** VDS switches have **cold-bypass**: a powered-off or failed switch relays its
   backbone trunk ports straight through, so its two neighbours appear directly adjacent in LLDP.
   Diagnose this as "switch unpowered or failed, cold bypass active" and escalate to check
   **power/health of that switch**, NOT to re-patch cables. (APs hanging off the bypassed switch
   stay dark — cold bypass only covers the backbone trunks, not the access ports.)

3. **Do not read "display has link but no data" as a cable fault at the switch.** A boot-time
   software-module crash on the switch (`KMdev: internal error while setting interface vlan1`, plus
   `KMdev`/`KMdiag`/`snmpd`/AgentX module restarts during boot) can leave display ports
   **linked-but-not-forwarding** — `carrier false: 0`, Fast-Link-Detection enabled, but no traffic.
   The observable proxy is `ifInOctets = 0 while ifOperStatus = 1` (linked, receiving nothing). A
   clean reboot re-inits the module and restores the port. This is a **weak, unconfirmed
   hypothesis** — a 126-switch/7-train harvest found the `vlan1` signature ZERO times (the
   persistent logs are near-empty and rotate fast), so seriously consider the symptom is
   **Stadler-side** (display app / ZFR reachability / FW state at power-up), which no switch log
   would show. Do NOT present KMdev as "the cause"; confirm with a controlled cold-boot repro.
   Two things that specifically do NOT work for catching it: a **warm** SNMP/CLI reboot (re-inits the
   module cleanly and does not reproduce it — only a **cold** power removal does), and off-box syslog
   (dead end — see the CLI-management doc). The armed repro kit (pre-arm persistent-log debug → cold
   power-cycle → read `show log persistent` before any second reboot → SNMP-poll `ifInOctets` for
   `oper=1 & in=0`) is the only reliable capture; ⚠️ do NOT reboot the down-display switch as a "fix"
   before collecting — that reboot both self-recovers the symptom and wipes the evidence. Full kit +
   verdict table: [dataless-display cold-boot repro](/.kb/evidence/kmdev-coldboot-dataless-display-repro.md).

4. **Do not trust a Zabbix `ifOperStatus` down→up bounce at face value.** The SNMP subagent
   reinitialises (`AgentX` restart) and briefly returns `ifOperStatus = 2` for *all* ports, producing
   **phantom** port-down→up events in history. Validate any apparent bounce against `ifLastChange`
   before believing a port actually flapped.

5. **Tuning the `ifOperStatus` poll rate does not catch fast flaps.** A 30–60s poll cannot see a
   firmware-level 5-in-10s flap burst regardless of rate (needs sub-3s sampling — Nyquist). The
   native `konLinkFlapping` trap is trap-only with no pollable OID (see the CLI-management doc). Tune
   the *trigger threshold*, not the poll interval.

6. **Off-box syslog is not an evidence channel for boot-crash RCA.** `configure system logging host
   <ip>` is accepted and shows in running-config but the switch transmits **zero** packets on
   udp/514 (verified with a bound listener). Use the on-switch `show log persistent` / `show log`
   plus an SNMP boot-window poll of `ifOperStatus`/`ifLastChange`/`ifInOctets` instead. (Detail in
   the CLI-management doc's dead-ends.)

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- A 6-car consist has ~18 switches (3/car); a 4-car has ~12.
- Management VLAN is `vlan100`; switch admin password `Nom@dCome1n`; SNMP v3 user `snmpadmin`,
  SHA1/AES128, secret `NomadStayOut!`.
- Critical Stadler-facing trunks to check per train (identify by config fingerprint, not hostname):
  - **A3 `e1-4`** — Stadler firewall multi-VLAN trunk; expect 1G full, 0 errors.
  - **D1/D3 `e0-2`** — OBS trunk (VLANs incl. 7/200/202); expect 10G full, 0 errors.
  - **D1/D3 `e0-3`** — RDC trunk (VLANs 200/202); often idle if RDC powered off.
  - **B1/B3 `e1-11`** — ZFR access, VLAN 2; redundant pair, only one transmits.
  - **All `e0-4`** — Wi-Fi AP trunks; near-0 traffic on an empty train.
- Reference clean baseline: Fzg 146 (6-car). Byte-counter snapshots at `.claude/sample1.txt` /
  `.claude/sample2.txt` (54s window) show the expected output format.
- The cold-bypass correction came from Fzg 137 / box1-t28 (2026-06-12): C3 absent, C2↔A2 LLDP-adjacent
  — mis-read as a re-patch, actually a dead switch bypassing.
- The KMdev dataless-display hypothesis came from 4736-120 / Fzg 148 / Train# 6002 (2026-06-24,
  displays link-but-no-ZFR-data, reboot of F2/A2 fixed it).

# Related

- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)
- [VDS Consist Switch — firmware flashing](/.kb/components/vds-consist-switch/firmware-flashing.md)
- [L2 health methodology (the 7-phase sweep, incl. Q1/Q2/Q3 FW commission test)](/.kb/topics/l2-health-methodology.md)
- [Coupled-train RSTP TC-storm](/.kb/topics/coupled-rstp-tc-storm.md)
- [Zabbix / NMS monitoring model (phantom port-down, engineID time-window)](/.kb/topics/zabbix-nms-model.md)

# Citations

[1] Fzg 146 (6-car) clean baseline, 2026-05-02 — 0/0/0/0 across ~500 ports; `.claude/sample1.txt` / `sample2.txt`.
[2] Cold-bypass correction, Fzg 137 / box1-t28, 2026-06-12 — LLDP-adjacent neighbours across a dead switch.
[3] Dataless-display RCA, 4736-120 / Fzg 148 / 6002, 2026-06-24 — KMdev boot-crash hypothesis + 126-switch fleet harvest (signature not reproduced).
[4] Phantom port-down finding — SNMP subagent AgentX reinit returns ifOperStatus=2 for all ports; validate vs ifLastChange.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/evidence/kmdev-coldboot-dataless-display-repro|kmdev-coldboot-dataless-display-repro]]
- [[.kb/components/vds-consist-switch/cli-and-management|cli-and-management]]
- [[.kb/components/vds-consist-switch/firmware-flashing|firmware-flashing]]
- [[.kb/topics/l2-health-methodology|l2-health-methodology]]
- [[.kb/topics/coupled-rstp-tc-storm|coupled-rstp-tc-storm]]
- [[.kb/topics/zabbix-nms-model|zabbix-nms-model]]
