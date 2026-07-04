---
type: tool
title: Switch boot-window poller — the linked-but-dataless detector
description: CCU-side SNMP poller that samples per-port oper/lastChange/octet counters through a switch reboot to catch ports that come up UP but carry no data.
project: dosto-neu
tags: [switch, snmp, boot-window, kmdev-crash, display-transient, l2, diagnostic]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
resource: /scripts/sw_bootwindow_poll.sh
---

# Switch boot-window poller — the linked-but-dataless detector

## What it does
Polls one VDS consist switch over SNMPv3 every few seconds through a reboot window and
records, per port, the four variables that separate a clean boot from a KMdev-crash boot:

- `ifOperStatus` (`.1.3.6.1.2.1.2.2.1.8.<idx>`) — link up (1) / down (2)
- `ifLastChange` (`.1.3.6.1.2.1.2.2.1.9.<idx>`) — when the port last flipped
- `ifInOctets`  (`.1.3.6.1.2.1.2.2.1.10.<idx>`) — is the port actually **receiving**? (the "dataless" tell)
- `ifOutOctets` (`.1.3.6.1.2.1.2.2.1.16.<idx>`) — is the switch sending?

Plus `sysUpTime`, so the boot moment is visible in the trace.

The signature it hunts: a display port reaches `ifOperStatus=1` (UP) but `ifInOctets` stays 0 /
barely moves — link, no data. On a clean boot the same port's `ifInOctets` climbs steadily.

## When to reach for it
A switch reboots and comes back with all links green, yet downstream displays show up but render
no ZFR/FIS data (the KMdev boot-crash → dataless-displays symptom). Green-link dashboards and
`show interface summary` both look healthy — the fault only shows in the octet counters. Reach for
this to capture reboot-window evidence when a display transient is suspected, or to prove a reboot
fixed it.

It is also the sanctioned substitute for off-box syslog: the VDS remote-syslog channel is a proven
dead end (switch emits zero udp/514 regardless of config), so CCU-side SNMP polling through the boot
window is the evidence channel that actually works.

## Usage
Runs **on the CCU** (SNMP reaches the switches on vlan100; a laptop off-VPN does not). Two ways:

```bash
# stream from laptop, script executes on the CCU:
ssh -i openssh developer@<CCU> 'bash -s' < scripts/sw_bootwindow_poll.sh <SW_IP> [DURATION_s] [INTERVAL_s] > capture.txt

# or copy to the CCU and run there:
bash sw_bootwindow_poll.sh <SW_IP> 300 3 > capture.txt
```

Args: `<switch-ip>` (required), duration in seconds (default 300), interval in seconds (default 3).
SNMP creds are baked in as the switch v3 model (`snmpadmin` / SHA / AES / `NomadStayOut!`).

## Output
A timestamped table, one line per port per sample:
`utc  uptime  idx  oper(1up/2down)  lastchange(ticks)  inOctets  outOctets`, bracketed by
`# start` / `# end` marker lines. Read it by watching `in=` on a port that shows `oper=1`: flat at
0 through the window = linked-but-dataless; climbing = healthy. `sysUpTime` resetting marks the boot.

## Notes / caveats
- `IDXS` is hardcoded to the **display-port ifIndexes on a 28-port NV6 7.4.2 switch**
  (`23 24 25 26 27 28 29` = e1-14/e1-15/e2-0..e2-4). For NV4 or a different consist, walk
  `.1.3.6.1.2.1.2.2.1.2` (ifDescr) on the target switch and edit `IDXS` — the pattern is reusable,
  the index set is per-hardware.
- One `snmpget` per OID per port per iteration — it is chatty; keep the port set tight.
- Sub-3s flap bursts are invisible at any practical interval (Nyquist) — this tool is for the
  boot/dataless question, not fast link-flap detection (which is trap-only anyway).

# Related
- [VDS switch — CLI, SNMP & management behaviour](/.kb/components/vds-consist-switch/cli-and-management.md) — the remote-syslog dead end this tool routes around; SNMP boot-poll channel
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)
