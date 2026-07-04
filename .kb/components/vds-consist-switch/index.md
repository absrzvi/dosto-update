---
type: component-index
title: VDS Rail Consist Switch — component knowledge
description: How the VDS Rail L2 consist switch behaves — CLI/SNMP/management, error counters and RSTP, and firmware flashing — with the dead ends already disproven on live hardware.
component: vds-consist-switch
vendor: VDS Rail
project: dosto-neu
---

# VDS Rail Consist Switch

Managed industrial L2 Ethernet switch, one-per-FIS-unit in a rail consist backbone. Custom CLI over
legacy-algorithm SSH plus an SNMP management surface. Identify on the wire by MAC OUI `a0:59:3a`.

## Management & control

* [CLI & management](cli-and-management.md) — SSH legacy-algorithm connect, the one-command-per-session CLI, `save running-config force` persistence, the trunk-rewrite trap, SNMP reboot OID, traps, and why remote syslog is a dead end.

## Health & diagnostics

* [L2 counters & RSTP](l2-counters-rstp.md) — reading RX-crc / carrier-false / collisions / pause-frame counters and their thresholds, RSTP root/roles/states, what "healthy" looks like, the benign false alarms (cold bypass, dataless displays, phantom port-down), and the double-counting trap.

## Firmware

* [Firmware flashing](firmware-flashing.md) — the TFTP-fetch + SNMP boot-default-OID + SNMP-reboot mechanism, the regex-match and None-guard traps that make a flash silently fail, and why current-fleet pushes are no-ops.
