---
type: topic
title: Zabbix / NMS Monitoring Model — Cred Model, Host Naming & Failure Modes
description: The DOSTO SNMP credential model (inverted SW/AP usernames), how NMS drives Zabbix host IPs, the host-naming formula, and a catalogue of the many monitoring failure modes with their disproven diagnoses.
project: dosto-neu
tags: [zabbix, nms, snmp, monitoring, proxy, lld, host-naming, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

DOSTO trains are monitored by a central Zabbix (behind the NMS). Each CCU runs a **zabbix-proxy**
(data collection only — it PULLS config from the server and forwards metrics; it never creates or
IPs hosts) plus a zabbix-agent. Host records and their interface IPs are written **centrally by
NMS**, fed from OBN discovery on the CCU over MQTT. Nothing on the CCU writes Zabbix host IPs — so
most host-level fixes are server-side (Zabbix API), not CCU-side.

A train tile reading "online" in NMS is driven by ICMP + the CCU agent — **not** by the switch/AP
SNMP interfaces. So a train can show green while every SNMP interface underneath collects nothing.
Do not read tile-green as "monitoring healthy."

This topic is dense with **disproven diagnoses** — the monitoring stack has repeatedly looked
broken in one layer while the real fault was in another. The dead-ends section is the point.

> **Portability note.** The layered pipeline reasoning is generic. Credentials, OIDs, host-name
> formulas, template IDs, and server hostnames in the `EXAMPLE` block are DOSTO-NEU-specific.

# The SNMP credential model

SNMPv3, authPriv, SHA1 auth + AES128 priv, on both device types. The **usernames are inverted**
between switches and APs — counter-intuitive, proven mutually exclusive on live devices:

| Device | SNMPv3 user | auth/priv | passphrase (auth = priv) |
|---|---|---|---|
| **Switch** | `snmpadmin` | SHA1 / AES128 | `NomadStayOut!` |
| **AP (Westermo)** | `admin` | SHA1 / AES128 | `NomadStayOut!` |
| CCU / media devices | — | — | agent/ICMP only (`snmp:false`) |

- The **SSH/LuCI login** password (`NomadComeIn` / `Nom@dCome1n`) is **not** the SNMP passphrase.
  Confusing the two is the documentation error that made the fleet SNMP-blind.
- Zabbix-6 enum gotcha: `authprotocol` `1 = SHA1` (not `2`, which is SHA224); `privprotocol`
  `1 = AES128`. net-snmp `-a SHA` = SHA1 = enum 1.
- Creds live on the **templates**, inherited by hosts (host macros are empty even on working
  hosts) — so a "cred problem" is almost always a template/provisioning problem, not per-host.

**After fixing creds, restart the proxy — a config-cache reload is NOT enough.** Devices stuck in
long SNMP-auth-fail backoff hold stale SNMPv3 engine state that `config_cache_reload` does not
flush. `systemctl restart zabbix-proxy` clears it (or let it self-heal on the next CCU
power-cycle, which restarts the proxy). Verify with a fast SNMP item showing a fresh `lastclock`,
not just interface `available=1`.

# Host naming

```
host group = <rtl_project_id>_<rtl_train_id>_<role>        e.g. 50_6027_MAR3-B1
SNMP host  = <group>_R<coach>_<SW|AP><n>                   e.g. 50_6018_R1_SW1
```

- `rtl_project_id = 50` for the **entire** DOSTO fleet — both internal project 50 (4-car) and
  internal project 51 (6-car). 50 is the NMS-facing namespace; **there is no Zabbix project 51.**
- `rtl_train_id = 6000 + train_id` (= 6000 + box ID). box t27 → 6027.
- `R<coach>` maps by physical chain, not alphabetically (e.g. NV6 R1..R6 = cars A,C,D,E,F,B).

Because the name embeds the box ID, the **box=Fzg migration renames every host** (`50_6<box>` →
`50_6<Fzg>`) and changes every interface IP — Zabbix will not auto-rename; it is API-driven work.

# Failure-mode catalogue

Each of these presents as "monitoring broken" but has a distinct root cause and fix.

| Presentation | Root cause | Fix |
|---|---|---|
| Tile green, all SNMP `lastclock=NEVER` fleet-wide | Wrong SNMP creds (SW passphrase drifted to the SSH password; AP user set to `snmpadmin`) | API `hostinterface.update` creds + proxy restart |
| Whole train all-red, "Last online: Unknown" | Hosts assigned to a **dead proxy** that never connected (phantom `nv4-zproxy` name) | Reassign hosts to the live proxyid + `config_cache_reload` |
| SNMP-dead but ICMP-green, IPs never worked | Host interface IPs are **stale provisioning-template values** the live DHCP devices never take | Seed inventory MACs from OBN discovery, then MAC-keyed reconcile |
| Mass "unavailable by ICMP" after a power-cycle | **DHCP lease drift** — 18 switches contend for one small pool; static Zabbix IPs go stale until NMS→Zabbix re-sync catches up | Lengthen the ICMP trigger window (`for: 15m`) to wait out convergence; durable fix = DHCP reservations (R&D) |
| Proxy crash-loops / no SNMP items collect | **LLD over-discovery** → CacheSize OOM (~14.8k items/train from an unfiltered `ifDescr` LLD) | Add an `{#IFDESCR}`/`{#SNMPVALUE}` regex filter to the LLD rule (backend self-heal) |
| Switch port-status / firmware items never collect | Template polls **wrong OIDs** (bogus ifIndex `1000001`, wrong vendor enterprise) — dead legacy static items superseded by a mis-macro'd LLD | Fix the LLD filter macro; disable the dead static items |
| Synchronous multi-port down→up "bounce" | **Phantom** — SNMP AgentX subagent reinit returns `ifOperStatus=2` for all ports at once; one bad poll recorded as a bounce | Validate against `ifLastChange`; add a 2-consecutive-sample trigger guard |
| Random switches "Timeout" while `snmpget` works from CLI | **Duplicate SNMP engineID** across switches + per-device engineTime drift >150s → proxy rejects as `usmStatsNotInTimeWindows` | Escalate (firmware unique engineID); switch reboot re-lands it in-window |

# Proven dead ends — do NOT repeat these

> This is the highest-value section: the monitoring stack has many convincing wrong answers.

1. **Using the SSH/LuCI password (`NomadComeIn`) as the SNMP passphrase.** It is not. The SNMP
   passphrase is `NomadStayOut!`. This doc error made the whole fleet SNMP-blind.
2. **Using the same SNMP username for switches and APs.** They are inverted: SW=`snmpadmin`,
   AP=`admin`, and each rejects the other's username as "Unknown user name."
3. **Expecting `config_cache_reload` to recover SNMP-auth-stuck devices.** It updates config but
   does not flush per-interface SNMPv3 engine state or reset backoff. Restart the proxy.
4. **Treating stale/drifted Zabbix host IPs as a Zabbix bug fixable in Zabbix.** The IPs are
   written by central NMS provisioning from OBN discovery; nothing on the CCU writes them, and
   there is **no self-service NMS re-sync endpoint** (`updateTrain` updates metadata only, tested).
   The clean fix is server-side re-sync on power-up (R&D) or MAC-keyed reconcile; the window fix
   (`for: 15m`) just waits out the convergence lag.
5. **Believing NMS holds a fresh IP you can copy into Zabbix.** For drifted devices NMS shows
   `None` and Zabbix shows the `7.7.7.7` sentinel — NMS is a *parallel frozen snapshot*, no better
   than Zabbix. Only **OBN's live `discovery.json` on the CCU** has the current IP.
6. **Setting the ICMP trigger window to 4-5 min to stop the power-cycle flood.** Measured
   convergence lag is p90 ≈ 16 min; 4-5 min still leaks the majority. `for: 15m` covers p90.
7. **Trusting Zabbix `ifOperStatus` history alone for a port event.** A synchronous multi-port
   down→up in the same minute is an SNMP subagent-reinit artifact, not a link event — real faults
   are independent per-port. Cross-check `ifLastChange` and the switch persistent log.
8. **Re-diagnosing a "Timeout" switch as an IP / cred / path problem when `snmpget` succeeds from
   the CLI.** If CLI `snmpget` works but the proxy times out, it is the shared-engineID
   time-window rejection — proven by `tcpdump` showing a `usmStatsNotInTimeWindows` Report loop
   with `0 packets dropped`. Neither server reboot, `config_cache_reload`, `restart`, nor `bulk:0`
   clears it.
9. **Splitting Zabbix to match internal project_id (making 6-car hosts `51_*`).** There is no NMS
   project 51 — publishing 6-car as 51 makes the trains go dark in NMS. The entire fleet keys on
   `rtl_project_id = 50`.
10. **Setting RTL-project-ID = 51 at `factory up` to "match" the internal project.** Same failure:
    NMS auto-creates `51_*` hosts with no project 51 to receive them → dark train. RTL-project-ID =
    50 for all DOSTO.
11. **Running the drift reconciler on the engineer's laptop.** Built, proven, then rejected — a
    fleet-wide production dependency cannot live on a laptop that sleeps/leaves. It must run on an
    always-on host or be solved natively (DHCP reservations).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Zabbix API: `https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php`, user `okapi`.
  **Auth token must go in the in-body `"auth"` field** — the reverse proxy strips the
  `Authorization: Bearer` header, which looks exactly like "not authorized / hosts missing."
- Run API calls **from a CCU** (a laptop can't reach the server).
- Switch template `Template VDS Switch - DOSTO NEU` (id 10723) is shared by all ~702 project-50
  switch hosts (all consist types). Correct switch OIDs: firmware `.1.3.6.1.4.1.33658.1.10.2.0`
  (returns `7.4.2`); ports via standard IF-MIB `ifOperStatus` on sequential ifIndex (LLD
  auto-discovers). The device's real enterprise is `33658`, not the template's `31988`.
- LLD filter fix: switch `^e[0-9]`; AP `^(eth|wlan|wifi)[0-9]`. Editing an LLD filter or trigger
  prototype does **not** update already-instantiated items until the LLD re-runs — force with
  `task.create {type:6}` per host or wait the ~1h LLD cadence.
- ICMP windows: SW trigger 21325 (`Template ICMP Ping Congested Switch`) already 15m; AP trigger
  21310 (`Template Eltec AP - NC`) fixed 2026-06-10 from ~5m to 15m.
- Shared duplicate engineID observed: `…0000a0593a212121` on every switch (2026-06-16, 6040).
- Bench trains (2123, 4122, 4124) suppressed — near-all ports admin-up-but-down by nature.

# Related

- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md) — SNMP engineID, IF-MIB, the switch side of these OIDs
- [Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md) — host names key off the box ID; box=Fzg renames every host
- [L2 health methodology](/.kb/topics/l2-health-methodology.md) — the DHCP-lease drift that makes static Zabbix IPs stale
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] Session memory `project_nms_zabbix_snmp_cred_model` — inverted cred model, the doc-error root cause, the fleet-wide fix (2026-06-08).
[2] Session memory `feedback_zabbix_proxy_restart_for_stuck_snmp` — proxy restart vs config_cache_reload.
[3] Session memory `reference_zabbix_host_naming_rtl_formula` — `50_6<box>` formula, rtl_project_id=50, no project 51.
[4] Session memories `project_zabbix_dead_proxy_nms_blank`, `project_zabbix_stale_template_ip_never_reconciled`, `project_zabbix_switch_icmp_dhcp_drift`, `project_zabbix_proxy_cachesize_lld_bloat`, `project_zabbix_switch_template_wrong_oids`, `project_zabbix_phantom_port_down_snmp_subagent`, `project_vds_duplicate_snmp_engineid_timewindow` — the failure-mode catalogue.
