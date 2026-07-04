---
type: tool-index
title: DOSTO NEU Tools — reusable diagnostic instruments
description: Index of purpose-built scripts harvested as reusable test/diagnostic instruments — what each measures, when to reach for it, and where the raw script lives.
project: dosto-neu
tags: [index, tools, diagnostic, scripts]
timestamp: 2026-07-04T00:00:00Z
---

# Tools — reusable diagnostic instruments

Each doc here describes a purpose-built script that is worth reaching for again as a **measurement
instrument**: what it measures, its inputs/outputs, and the situation that calls for it. The raw
script stays under `/scripts/`; the doc points at it via `resource:`. Several were written for one
train (hardcoded IDs) — the docs describe the **reusable pattern**, and call out what to
re-parameterise.

* [Switch boot-window poller](sw-bootwindow-poll.md) — CCU-side SNMP poller that samples per-port
  oper/lastChange/in-octet counters through a switch reboot to catch ports that come up UP but carry
  no data (the KMdev-crash "linked-but-dataless" symptom). The sanctioned substitute for the dead
  remote-syslog channel. `scripts/sw_bootwindow_poll.sh`.

* [Zabbix polling-health checker](zbx-polling-check.md) — read-only Zabbix API probe that reports a
  train's host availability, proxy assignment + last-seen, and stuck-trigger recovery state. Run it
  to answer *why* a train's alarms won't clear before touching anything.
  `scripts/zbx_check_4736_119_polling.py`.

* [Zabbix stale-problem clearer](zbx-clear-stale-problems.md) — finds a train's active "unreachable"
  problems, filters to the verified-stale ones, and ack+messages them (read-only unless `--close`).
  The action step after the polling checker confirms the alarms are false.
  `scripts/zbx_clear_4736_119.py`.

* [Down-port cross-reference](xref-down-ports-vs-template.md) — joins a switch's live admin-up/
  oper-down ports to the OBN template to sort them into real faults, expected-solo couplers, service
  ports, and config drift. The single-train triage pattern. `scripts/xref_6027_ports.py`.

* [Not-found device register generator](gen-notfound-register.md) — builds the fleet-wide Stadler
  "devices not found" xlsx from currently-open Zabbix port-down problems joined to the OBN template
  and classified per device category. The fleet-scale automation of the cross-reference above.
  `scripts/gen_notfound_register.py`.

# Related

* [Knowledge base index](/.kb/index.md)
* [Topics — cross-cutting subjects](/.kb/topics/index.md)
* [Components — how each device behaves](/.kb/index.md#components--how-each-device-type-behaves)
* [Maintaining this knowledge base](/.kb/MAINTENANCE.md)
