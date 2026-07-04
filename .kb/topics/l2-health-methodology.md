---
type: topic
title: L2 Network Health Methodology — the Seven-Phase Sweep
description: The repeatable playbook for assessing an L2 consist fabric — discovery via live DHCP leases, mapping switches by config fingerprint, the four canonical show commands, Stadler-facing trunks, and the three-question firewall probe.
project: dosto-neu
tags: [l2, health-check, rstp, trunks, discovery, firewall, methodology, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

This is the validated procedure for answering "is the L2 fabric on this consist healthy?"
It exists so results are **repeatable across trains** and so an agent does not re-invent the
sweep ad-hoc (and re-make the same misreadings). The unit under test is a rail consist
backbone: a chain of managed L2 switches (one per FIS unit), inter-coach trunks, Stadler-facing
trunks, and a vlan7 transit link to the Stadler firewall.

Run all seven phases in order. A clean pass across all seven means the L2 fabric is healthy —
so reported user-perceived packet loss is then almost certainly NOT in this fabric (look at the
end host, Stadler-side beyond the firewall, or the PWLAN/cellular path — separate scopes).

> **Portability note.** The phase structure and the interpretation rules are generic. Subnets,
> VLAN numbers, port names, switch counts, and credentials in the `EXAMPLE (DOSTO NEU)` block are
> deployment-specific.

# Phase 1 — Discovery (use live DHCP leases, not ARP)

Devices on the management VLAN hold **short DHCP leases** — every power-cycle reshuffles which
device holds which IP. So the current, correct source of "which device is at which IP right now"
is the CCU's DHCP lease table, **not** ARP and **not** any stored/static list.

```bash
sudo dhcp-lease-list                 # current IP ⇄ hostname ⇄ MAC, authoritative
fping -a -q -g <mgmt-range-start> <mgmt-range-end>   # confirm the expected device count is alive
```

Sanity-check the count against the consist (e.g. 3 switches/car × N cars).

# Phase 2 — Map switches to schema positions by config fingerprint

Live switch IPs are just sequential leases; they carry no position label, and the switch does
**not** expose its hostname over the management CLI (`show system` returns no hostname). So map
each switch to its schema role (A3, B1, D1, …) by **config fingerprint** — which trunks and
access ports it has configured — read from `show interface trunks` / `show vlans`. Fingerprints
identify the special switches (the firewall switch, the ZFR-connected pair, the OBS/RDC switch,
end-of-train switches). Do not try to SSH-discover the hostname; use the fingerprint.

# Phase 3 — The four canonical show commands (per switch)

```text
show interface summary          # all ports: up/down, speed, duplex
show interface <port> details   # per-port RX/TX errors, CRC, carrier-false, drops, collisions
show interface trunks           # configured trunks + VLANs carried
show spanning-tree              # RSTP root, port roles, states (FWD/BLK/LEARN)
show vlans                      # VLAN-to-port map
```

**Counter interpretation:** `RX crc errors`, `carrier false`, `Excessive/Late collisions`,
`pause frames` should all be **0**. A handful of RX errors against millions of packets is noise.
Sustained non-zero CRC or carrier-false = a physical-layer fault (cable / SFP / connector / EMI /
vibration) — cross-check the counter at the *other* end of the same link.

**STP:** expect **one** stable root MAC that every switch agrees on. Multiple roots or a flapping
root = an unstable topology; chase the link generating the topology-change notifications.

# Phase 4 — Stadler-facing trunks

Beyond the inter-coach uplinks, check the trunks that carry Stadler-side traffic (the firewall
trunk, the OBS/RDC trunks, the ZFR access ports, the coupler trunks, the Wi-Fi AP trunks). Run
`show interface <port> details` on each; speed/duplex must match the schema, and error counters
must be 0. Some are expected-DOWN when the consist runs solo (coupler trunks) or idle (RDC) —
that is not a fault.

# Phase 5-7 in brief

- **Phase 5 — throughput/utilization:** sample byte counters on a port twice N seconds apart and
  diff. Confirm the firewall trunk isn't saturating its link.
- **Phase 6 — CCU ↔ Stadler firewall:** the three-question probe (below).
- **Phase 7 — aggregate fabric load:** sample every inter-coach trunk twice 30-60 s apart. Report
  **average per-active-trunk Mbps**, not the sum — summing double-counts multi-hop traffic.

# Phase 6 — the three-question firewall probe

The firewall check is **three separate questions**, each with its own probe. See
[vlan7 addressing](/.kb/topics/vlan7-addressing.md) for the full logic; in brief:

| Q | Probe | Reads |
|---|---|---|
| **Q1 path** | `ip neigh show dev vlan7` | ARP REACHABLE = path OK; FAILED = stop, path broken |
| **Q2 commission** | `ping -c 5 <fw-ip>` | 100 % loss (+ Q1 OK) = **commissioned**; replies = **not yet** |
| **Q3 service** | `nc -zv <fw-ip> <port>` | only tells you a port answers — never commission state |

# Proven dead ends — do NOT repeat these

> Kept so a fresh agent does not re-make these misreadings on live hardware.

1. **Relying on stale ARP (or any stored IP list) for discovery.** Management-VLAN leases are
   short (minutes) and reshuffle on every power-cycle. ARP goes stale immediately. Always read the
   **live DHCP lease table** for current IPs; this is also why Zabbix's static host IPs drift
   (see [Zabbix / NMS model](/.kb/topics/zabbix-nms-model.md)).
2. **Using `ping` past the firewall as a health probe.** ICMP loss to a commissioned Stadler FW
   is *by policy*, not a fault. Reading ping-fail as "network down" is the long-standing trap;
   reading ping-success as "healthy" is the newer one. Ping is a *commission-state* signal, not a
   liveness probe, and only for the FW peer itself.
3. **Using TCP alone to decide firewall commission state.** A TCP OPEN cannot distinguish "FW
   commissioned with a policy that happens to allow this port" from "bare, uncommissioned Westermo
   box answering on its management port." Only the Q2 ICMP test decides commission state.
4. **Trying to identify a switch by asking it its hostname.** `show system` has no hostname field.
   Map by config fingerprint (Phase 2).
5. **Chaining CLI commands over one SSH session.** The switch CLI takes exactly one command per
   session; `;`-chaining errors. Loop in the shell. (See the switch component doc.)
6. **Reporting the sum of all inter-coach trunk rates as fabric load.** It double-counts traffic
   that traverses multiple cars. Report average per-active-trunk instead.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- CCU SSH: `ssh -i openssh developer@<ccu-ip>`; switches on `vlan100`, admin password `Nom@dCome1n`
  with legacy SSH KEX/host-key algorithms.
- 6-car consist ≈ 18 VDS switches (3/car); 4-car ≈ 12. Inter-coach trunks usually `e0-0`/`e0-1`
  (10 Gbps on modern consists).
- Fingerprint examples: firewall switch (A3) has `e1-4` as a multi-VLAN trunk; ZFR pair (B1/B3)
  has `e1-11` access on VLAN 2; OBS/RDC switch (D1/D3) has `e0-2`/`e0-3` trunks.
- vlan7 FW IP per train = `172.19.<128+Fzg//2>.1` for even Fzg (`.129` for odd) — pass it
  explicitly to `08_e2e_probe.sh`.
- Fzg 146 baseline (all ~500 ports 0/0/0/0; ~140 Mbps/active inter-coach trunk ≈ 1.5 % of 10G)
  captured in `.claude/sample1.txt` / `sample2.txt` as the reference output format.

# Related

- [vlan7 bit-packed addressing & FW reachability](/.kb/topics/vlan7-addressing.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)
- [Coupled-train RSTP TC-storm](/.kb/topics/coupled-rstp-tc-storm.md)
- [Zabbix / NMS monitoring model](/.kb/topics/zabbix-nms-model.md) — why static Zabbix IPs drift off the leases
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] CLAUDE.md — Phases 1-8 of the L2 health playbook; "Quick is-this-train-healthy recipe."
[2] Session memory `project_dhcp_lease_discovery` / `project_lldp_topology_check` — short leases, `dhcp-lease-list`, hostname-not-in-`show system`.
[3] Fzg 146 baseline (2026-05-02) — clean-fabric reference.
