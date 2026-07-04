---
type: component-knowledge
title: VDS Rail Consist Switch — CLI, SNMP & Management Behaviour
description: How the VDS Rail L2 consist switch behaves over SSH CLI and SNMP — quirks, persistence, reboot, traps, syslog — and what has been proven NOT to work.
component: vds-consist-switch
vendor: VDS Rail
project: dosto-neu
tags: [switch, l2, cli, snmp, rstp, firmware, syslog, traps, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

The **VDS Rail Consist Switch** is a managed industrial L2 Ethernet switch used one-per-FIS-unit
in rail consist backbones. It presents a **custom CLI over SSH** (not a Unix shell) and an
**SNMP** management surface. This document captures observed behaviour so an agent can operate
and troubleshoot the device **without rediscovering the quirks the hard way**.

- **Identify by:** MAC OUI `a0:59:3a`.
- **Management transport:** SSH/TCP-22 (legacy KEX + host-key algorithms required), SNMP.
- **Firmware family referenced here:** `sw-std-ng` 7.4.x (behaviour verified on build 7.4.2-77411).

> **Portability note.** All facts below are generic to this switch family. Deployment-specific
> values (IP subnets, hostnames, VLAN numbers) from the DOSTO NEU project appear only inside
> clearly-marked `EXAMPLE (DOSTO NEU)` blocks and must be re-derived for any other deployment.

# Connecting over SSH

The SSH server only negotiates **legacy algorithms**. A modern client must explicitly re-enable them:

```bash
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"
sshpass -p "<admin-pw>" ssh $SSH_OPTS admin@<switch-ip> "show interface summary"
```

# CLI behaviour — load-bearing quirks

| Behaviour | Detail | Why it matters |
|---|---|---|
| **One command per session** | The CLI accepts exactly ONE command per SSH invocation. `;`-chaining errors with `Error in command, param is "..." [wrong]`. | Loop in the shell — issue N separate SSH sessions. Do NOT build `cmd1; cmd2` strings. |
| **No hostname in `show system`** | `show system` returns no hostname field. | You cannot identify a switch by asking it. Identify by **config fingerprint** (which trunks/access ports are configured) instead. |
| **Pseudo-terminal warning** | `ssh … <command>` prints a PTY warning. | Harmless. Ignore. |
| **Persist with `save running-config force`** | Writes running-config → startup NVRAM. The `force` flag is required for machine-generated (TTCMP/orchestrator) configs. | `save startup-config` is a *different* command (a KAD import/export-activation) that returns silently and does **NOT** persist your edit. Always verify with `show startup-config \| grep <change>`. |
| **`switchport mode trunk <attr>` rewrites the WHOLE trunk def** | Setting one attribute (e.g. `native vlan 999`) resets all *unspecified* attributes to defaults — including the VLAN prune set back to `allow 1-4094`. | Combine every attribute into ONE command. Setting native and prune in two commands momentarily exposes management VLANs. |

**Correct combined trunk command (single line):**
```
configure interface <port> switchport mode trunk native vlan <n> prune allow <vlan-list>
```

# Health / diagnostic commands (read-only)

Canonical L2 health sweep — run per switch:

```
show interface summary          # all ports: up/down, speed, duplex
show interface <port> details   # per-port RX/TX errors, CRC, carrier-false, drops, collisions
show interface trunks           # configured trunks + VLANs carried
show spanning-tree              # RSTP root, port roles, states
show vlans                      # VLAN-to-port map
show log / show log persistent  # event log (see Logging section)
```

**Counter interpretation:** `RX crc errors`, `carrier false`, `Excessive/Late collisions`, and
`pause frames` should all be **0**. A handful of RX errors over millions of packets is noise
(single corrupted frame). Sustained non-zero CRC or carrier-false = physical-layer fault
(cable / SFP / connector / EMI / vibration).

# Reboot

- The reboot path from a controlling host is **SNMP**, not CLI. Set the vendor reboot OID
  (observed value `3`).
- Before an SNMP reboot, an orchestrator that reads-then-writes the hostname OID must guard
  against a `None` read (the switch may already be shutting down) — writing `None` back crashes
  the SNMP layer. (This is the class of the "Bug 7" family, see Related.)

# Logging — what actually captures evidence

| Channel | Works? | Notes |
|---|---|---|
| **On-switch persistent log** (`show log persistent`) | ✅ | Survives power-off. Holds "most important events" incl. boot crash signatures + module restarts. Short + overwrites — clear before a controlled boot, read immediately after. |
| **Volatile log** (`show log`) | ✅ | Full boot trace with `configure system logging debug core,dev,switch,poe,…`. Wiped on next power-cycle — grab before any further reboot. |
| **CCU/controller-side SNMP boot-window poll** | ✅ | Poll `ifOperStatus`/`ifLastChange`/`ifInOctets` per port through the boot window. `ifInOctets=0 while oper=1` = linked-but-dataless symptom. |
| **Remote syslog** (`configure system logging host <ip>`) | ❌ **DEAD END** | See Proven dead ends. |

# Traps

- The firmware has a **dedicated link-flap trap** `KONUENDO-MONITOR-MIB::konLinkFlapping`
  (family `traps-all-if`, token `link-flap`), firing when a link transitions >5×/10s.
- **It is TRAP-ONLY.** There is **no pollable OID** for flap state — the readable MONITOR-MIB
  surface is a single scalar; there is no per-port flap table or counter. You cannot `snmpget`
  flap state. To use native flap detection you must stand up a **trap receiver**; otherwise
  synthesize coarse flap detection by polling `ifOperStatus` transitions in a window
  (misses sub-interval bursts — Nyquist).

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not burn hours re-testing what has already been
> disproven on live hardware.

1. **CLI reboot commands don't exist.** `reboot`, `reload`, and `system reboot` are all rejected
   (`Error in command, param is X [wrong]`). The confirmed reboot path is the **SNMP reboot OID**
   (value `3`), not any CLI verb.
2. **`;`-chaining commands over SSH fails.** One command per session, always. (See CLI quirks.)
3. **`save startup-config` does NOT persist your changes.** It looks successful (silent return)
   but is an import/export-activation command. Use `save running-config force` and verify.
4. **Remote syslog transmits nothing.** `configure system logging host <ip>` is *accepted* and
   appears in `show running-config`, but the switch sends **zero** packets on udp/514 (verified
   by `tcpdump` on the receiving host while toggling debug and bouncing ports; a bound UDP
   listener received nothing). The manual documents no severity/facility/trap-enable knob to gate
   it. **Off-box syslog streaming is not a usable evidence channel** — use the on-switch
   persistent/volatile logs or SNMP polling instead.
5. **You cannot poll `konLinkFlapping`.** It is emitted only as a trap; no readable OID exists.
   Do not attempt `snmpget` against the notification OID — it returns "No Such Object".
6. **Dropping the poll rate to catch fast flaps is futile.** A 30–60s `ifOperStatus` poll cannot
   see a 5-in-10s firmware flap burst regardless of rate (needs sub-3s sampling). Tune the trigger
   threshold, not the poll interval.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Switches sit on the management VLAN `vlan100`; admin password `Nom@dCome1n`.
- Firmware target across the fleet was `sw-std-ng_7.4.2-77411`.
- SNMP v3 credential model for switches: user `snmpadmin`, SHA1/AES128, secret `NomadStayOut!`
  (the AP credential model is *inverted* — see the AP component doc).
- A 6-car consist has ~18 switches (3/car); a 4-car has ~12.
- The remote-syslog dead end was proven on switch `.186` (fw 7.4.2-77411) during a
  display-transient cold-boot RCA (2026-06-24).

# Related

- [Westermo AP — factory vs Nomad config](/.kb/components/westermo-ap/factory-vs-nomad-config.md)
- [Nomad Connect / OBN — bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)
- [Zabbix / NMS monitoring model](/.kb/topics/zabbix-nms-model.md)
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] Consist Switch User Manual v2.0.4 — §14.3.7 (link-flap trap), logging commands.
[2] Field validation, coupled-train loop-containment work, 8 switches (2026-06-11) — CLI persist + trunk-rewrite behaviour.
[3] Field validation, display-transient RCA (2026-06-24) — remote-syslog dead end, persistent-log channel.
[4] Field validation, flap-alarm design walk (2026-06-23/24) — konLinkFlapping trap-only, no pollable OID.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/components/westermo-ap/factory-vs-nomad-config|factory-vs-nomad-config]]
- [[.kb/components/nomad-connect-obn/bug-suite|bug-suite]]
- [[.kb/topics/l2-health-methodology|l2-health-methodology]]
- [[.kb/topics/zabbix-nms-model|zabbix-nms-model]]
- [[.kb/fleet/index|index]]
