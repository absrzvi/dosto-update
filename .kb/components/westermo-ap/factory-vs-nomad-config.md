---
type: component-knowledge
title: Westermo AP — Factory vs Nomad Config
description: How a Westermo RT610LV AP behaves in factory vs Nomad config — why factory config silently blocks controller SNMP, the LuCI HTTP import bypass, how to tell the two forms apart from the DHCP hostname (never from SNMP silence), and how to read live radio state.
component: westermo-ap
vendor: Westermo
project: dosto-neu
tags: [ap, westermo, rt610lv, luci, snmp, factory-config, radio, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

The **Westermo RT610LV** is the industrial Wi-Fi access point used in the consist. It has two config
"forms" with very different management surfaces: **factory** (as shipped / factory-reset) and
**Nomad** (commissioned). The single biggest source of wasted time on this device is misreading its
normal behaviour — SNMP silence, a closed TCP/80, a minimal `/etc/` — as damage or as proof of one
form when it is actually the other. This document pins down how each form behaves and how to move an
AP from factory to Nomad without chasing false faults.

- **Identify by:** MAC OUI `00:14:5a`. Model `RT610LV` (IbexOS).
- **Management surfaces:** SNMP (v3), SSH CLI (jailed BusyBox), LuCI web (HTTPS/443).

> **Portability note.** All facts below are generic to this AP family. Deployment-specific values
> (IPs, passwords, VLANs, config-file paths) appear only inside the `EXAMPLE (DOSTO NEU)` block.

# The two config forms

| | Factory | Nomad (commissioned) |
|---|---|---|
| DHCP hostname | `RT610LV-<mac>-v1-FD` (IbexOS factory variant may title itself `Rmodem`) | `AP<n>-v1-<mac>` (non-m) or `AP<n>m-v1-<mac>` (m/dual-radio) |
| SNMP community/user | community `admin-community` — controller SNMP (v3 `admin`/`NomadStayOut!`) is silently dropped | responds to v3 `admin` / SHA / AES / authPriv / `NomadStayOut!` |
| LuCI login | `admin` / `admin`, or `admin` / `Nom@dCome1n` (try both) | `admin` / `Nom@dCome1n` (web); SSH CLI `nomad` / `NomadComeIn` |
| Reachability | often on factory `192.168.1.x` (native VLAN) if never commissioned; may hold a `10.179.x` lease if partly set up | `10.179.x` management-VLAN lease |

# The factory-SNMP silent-block trap

A factory-config AP **drops all controller SNMP** — its community is `admin-community`, not the Nomad
passphrase, and source-IP restriction is also suspected. ICMP works fine; only SNMP is dropped.
**The controller (OBN) prints "configuration update applied, device rebooting" regardless** — it does
not check the SNMP return value before printing success. So `obn update c <ap>` against a factory AP
looks like it worked and did nothing. The authoritative signal that a config push is needed is
`obn validate -t ap` showing a `✗` in the config column, and the authoritative form check is the DHCP
hostname (below), never the "update applied" line.

# Determine the form from the DHCP hostname — NEVER from SNMP silence

This is the load-bearing rule. **SNMP-timeout is NORMAL on a healthy commissioned AP** (see the
brick dead-end below), so "SNMP `NomadStayOut!` didn't answer" is **not** evidence of factory config.
Read the config form from the DHCP lease hostname suffix:

- `RT610LV-*-FD` → factory. Only this justifies the LuCI bypass.
- `AP*-v1` / `AP*m-v1` → already Nomad. If SNMP is silent here, the gap is something else — do not
  re-push factory config onto a commissioned consist.

A real incident: a worker read "SNMP no-response" as factory and proposed a 22-AP LuCI bypass on an
already-commissioned train; the hostnames were all `AP*-v1`. Running it would have re-pushed factory
config over a working consist. Always `dhcp-lease-list | grep 00:14:5a` and read the hostname first.

The `AP*-v1` (non-m) vs `AP*m-v1` (m/dual-radio) distinction matters when cloning a config for
recovery — clone only from a **same-variant** sibling (m configs carry a second radio).

# Moving an AP factory → Nomad: the LuCI HTTP import bypass

When SNMP is blocked (genuine factory AP), push the Nomad config via LuCI's web import instead of
SNMP. It is a **two-step candidate-config flow** — upload stages it, a second call commits it:

1. **Login** — POST `luci_username=admin&luci_password=<pw>` to `/cgi-bin/luci/` → expect HTTP 302.
2. **Upload (stages pending)** — POST the rendered config to
   `/cgi-bin/luci/admin/system/flashops` as `config=@<file>` + `Import=Import Configuration`
   → expect HTTP 200. The AP now shows "Config Alert" (pending) in LuCI.
3. **Apply (reboots ~60–90s)** — POST `{"key":"rpcCfgApply","value":1}` to
   `/cgi-bin/luci/admin/rpc` → expect HTTP 200. (The flashops `config_apply=1` form is an
   equivalent apply on some images.)

Key behaviours:

- **Upload without apply leaves the AP in "Config Alert" and the config is reverted on next reboot.**
  You must call the apply step. If you find an AP already showing Config Alert, a prior session
  uploaded but never applied — just re-login and apply.
- **The apply call causes an immediate reboot**; the HTTP response often returns (or the connection
  drops) before the reboot completes. Treat 200-then-connection-close, or a follow-up call returning
  HTTP `000` (connection refused = rebooting), as success. Do **not** trust the apply page text — it
  can show `Config apply failed!` and `applying now` simultaneously. **Verify by outcome.**
- **After Nomad config applies, the LuCI password may change** (the config sets a hashed admin
  password) and SSH CLI becomes `nomad`/`NomadComeIn`. So verify the result by SNMP (deterministic:
  v3 `admin`/`NomadStayOut!`) or by the DHCP hostname flipping to `AP*-v1`, not by re-logging into
  LuCI with the old password.
- **Never batch this in parallel** — one AP at a time. Parallel reboots wedge fabric STP recalculation.

An AP that is factory **and unreachable on the management VLAN** (still on `192.168.1.x`, invisible to
the controller so no config was ever rendered for it) needs the factory-recovery path: reach it via a
temporary untagged `192.168.1.2/24` on the CCU `bond0` (native VLAN), clone a same-variant sibling's
rendered config swapping only the hostname line, then LuCI-push as above.

# Reading live radio / SSID state

The controller cannot read an AP's live radio state over SNMP or SSH (both restricted). The one
read-only path is LuCI: after a form login, `GET
/cgi-bin/luci/admin/status/general/data?view=wireless` returns the WLAN-interfaces table (per virtual
radio: Status operating/disabled/down, Frequency, Bandwidth, SSID, BSSID; `Frequency > 5000` = 5 GHz).
Each AP has multiple virtual radios (`wlan0..wlan5`) — an m-variant runs both a 5 GHz and a 2.4 GHz
radio, a non-m runs one. Use this to settle "is this AP actually broadcasting" questions that the
CCU-side files cannot answer.

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not burn hours re-testing what has already been
> disproven on live hardware.

1. **Do not read SNMP silence as factory config.** A healthy Nomad AP times out to a naive
   `snmpget` too. Determine the form from the **DHCP hostname suffix** (`RT610LV-*-FD` = factory;
   `AP*-v1` / `AP*m-v1` = Nomad). Acting on SNMP silence risks re-pushing factory config onto a
   commissioned train.

2. **Do not diagnose an AP as "bricked" / "in recovery mode" without comparing a sibling.** Nomad
   APs *naturally* have a minimal BusyBox `/etc/`, *naturally* keep TCP/80 closed (only 443 open),
   and *naturally* don't answer a standalone CLI `snmpget` — while the controller's own SNMP polls
   them fine. Before declaring damage, run the exact same probe set against a known-untouched sibling
   AP on the same train. If they match, your probes are wrong, not the AP. (Real case: an AP declared
   "bricked / recovery mode" after a firmware push turned out identical to an untouched sibling — the
   real issue was a partial-flash, not damage.)

3. **`coach_ap_mappings.yaml` showing every radio `updown: DOWN` does NOT mean the radios are off.**
   That file is a **report-label source only** — read solely by the report layer to print a "floor"
   string in the Wi-Fi MAC-address report. It is a stale default, has no control over whether an AP
   broadcasts, and shows `DOWN` on perfectly healthy commissioned trains. Do not report it as a fault
   or edit it to "fix coverage." Radio TX/SSID state lives on the AP (WeOS/LuCI `/etc/config/wireless`)
   — read it via the LuCI status endpoint above.

4. **Standalone `snmpget -v2c -c NomadStayOut!` always times out — it is the wrong form, not a
   fault.** `NomadStayOut!` is the SNMP **v3 passphrase**, not a v2c community, and the AP user is
   `admin` (not `snmpadmin` — that's the switch). The correct probe is
   `snmpget -v3 -u admin -l authPriv -a SHA -A NomadStayOut! -x AES -X NomadStayOut!`. Prefer trusting
   `obn discover` over any ad-hoc `snmpget`.

5. **A "missing AP" with a link-UP switch port is not a port-down / cable fault.** A factory AP on
   `192.168.1.x` has link + power (port reads `ifOperStatus = up`) but is unreachable on the
   management IP — that signature is an *uncommissioned* AP, not a broken one. Recover it, don't
   escalate a cable fault. (A genuinely link-DOWN port is the physical problem — that one *is* a
   cable/hardware issue.)

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- APs sit on management VLAN `vlan100` (`10.179.x`); factory APs on `192.168.1.x` (native VLAN),
  factory address typically `192.168.1.20`.
- **Passwords:** LuCI web `admin`/`Nom@dCome1n` (factory may also be `admin`/`admin`); post-Nomad SSH
  CLI `nomad`/`NomadComeIn`. URL-encode `Nom@dCome1n` → `Nom%40dCome1n` in HTTP POST bodies.
- **SNMP:** v3, user `admin`, SHA1 auth + AES128 priv, authPriv, passphrase `NomadStayOut!` (both).
  Inverted vs the switch (`snmpadmin`). `NomadComeIn` must NEVER appear in an SNMP field.
- **Rendered configs:** `/data/auto-topology/upload/dostoneu-obn-<mac-slug>.cfg` (MAC lowercase, no
  colons). OBN renders these during any `obn update c` attempt (even one that fails at SNMP).
- Factory-SNMP block confirmed on 4734-120 (CCU 10.179.49.1), 2026-05-05 — all 16 APs factory after
  commissioning. SNMP-silence-≠-factory correction: 4736-109, 2026-06-08. Live radio readout method:
  Fzg 138, 2026-06-03. Factory-recovery (temp bond0 / sibling clone): 4736-115 AP4m, 2026-06-08.
- Bypass scripts: `scripts/push_ap_config.sh` (login+upload), `scripts/apply_ap_configs.sh`
  (Config-Alert apply), `scripts/push_remaining_aps.sh`. Skills: `dosto-ap-config-update`,
  `dosto-ap-factory-recover`. Full manual procedure: `troubleshooting-runbook.md` → "Westermo AP
  Config Push".

# Related

- [Westermo AP — firmware activation](/.kb/components/westermo-ap/firmware-activation.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)
- [Nomad Connect / OBN — bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Zabbix / NMS monitoring model (SNMP cred model, DHCP-float host IPs)](/.kb/topics/zabbix-nms-model.md)
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)

# Citations

[1] Factory-SNMP silent-block + LuCI two-step bypass, 4734-120 (CCU 10.179.49.1), 2026-05-05; `troubleshooting-runbook.md` §"Westermo AP Config Push".
[2] SNMP-silence-≠-factory correction (DHCP-hostname is authoritative), 4736-109, 2026-06-08.
[3] Don't-diagnose-brick-too-fast (sibling comparison), Fzg 8, 2026-05-22.
[4] `coach_ap_mappings.yaml` red-herring + LuCI wireless readout, Fzg 138 / 4736-110, 2026-06-03.
[5] Factory-recovery via temp bond0 native-VLAN + same-variant clone, 4736-115 AP4m (box 6018), 2026-06-08.
