---
type: tool
title: Zabbix polling-health checker — why aren't a train's alarms clearing?
description: Read-only Zabbix API probe that reports a train's host availability, proxy assignment + last-seen, and stuck-trigger recovery state.
project: dosto-neu
tags: [zabbix, nms, snmp, proxy, monitoring, diagnostic, api]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
resource: /scripts/zbx_check_4736_119_polling.py
---

# Zabbix polling-health checker — why aren't a train's alarms clearing?

## What it does
Logs into the ÖBB-Alpin Zabbix over the JSON-RPC API and, for all hosts of one train (matched by
fleet number, e.g. `6012`), prints:

1. **Proxy assignment + freshness** — which proxy each host is bound to and when that proxy last
   reported (`lastaccess`). A never-connected or dead proxy is the classic cause of an all-red,
   never-clearing NMS panel.
2. **Per-host availability** — ICMP and SNMP `available` flags plus any interface error string.
3. **Active problems on the named stuck hosts** — the currently-open trigger events, so you can see
   whether a problem is genuinely active or just failed to auto-resolve.

Entirely read-only — it diagnoses, it does not touch problem state.

## When to reach for it
A train's alarms won't auto-resolve even though the devices are known-good, or the NMS shows a wall
of red with "Last online Unknown". Run this first to decide **why**: dead/wrong proxy vs. genuinely
stale trigger vs. host IPs drifted from DHCP. It answers the question the clearer tool
(`zbx_clear_*`) then acts on — check before you clear.

## Usage
Runs anywhere with reachability to the Zabbix host (no train VPN needed — it is a cloud API):

```bash
python scripts/zbx_check_4736_119_polling.py
```

No args. The train (`6012`), the ZBX URL, and the `okapi` read credential are constants at the top
of the file.

## Output
Console sections: host count, proxy-assignment summary (with per-proxy last-seen timestamps),
per-host ICMP/SNMP availability with error flags, and active problems on the hard-coded stuck-switch
list (`R4_SW2, R4_SW3, R5_SW2, R5_SW3, R6_SW2`). A proxy last-seen far in the past, or hosts on a
proxy that says "never", is the smoking gun.

## Notes / caveats
- **Template, not a one-train tool.** `6012`, the ZBX URL, and the stuck-host list are hardcoded for
  the 4736-119 investigation. To reuse: change the `search` fleet number and the `stuck` list. The
  reusable pattern is *host.get → proxy.get(lastaccess) → problem.get(recent=False)*.
- Zabbix host naming is `50_6<box-id>` — the fleet number (`6012`) is what `host.get search` matches,
  not the Train#. See the Zabbix/NMS model doc for the naming formula.
- Credentials (`okapi`) are Zabbix-read-only and live in-repo; safe for diagnosis, no write scope.

# Related
- [Zabbix / NMS monitoring model](/.kb/topics/zabbix-nms-model.md) — host-naming formula, proxy model, dead-proxy symptom
- [Zabbix alarm/problem clearer](/.kb/tools/zbx-clear-stale-problems.md) — the action tool that consumes this diagnosis
