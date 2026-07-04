---
type: evidence
title: Dataless-display transient — cold-boot repro kit isolating a KMdev boot crash (not cable, not surge)
description: A controlled cold-power-cycle repro kit that captures the "display links but carries no ZFR data" transient, ruling out cabling/surge and pinning the leading cause to a KMdev module boot crash — plus the 126-switch/7-train persistent-log harvest that failed to reproduce the signature.
project: dosto-neu
tags: [switch, kmdev, cold-boot, displays, zfr, dataless, boot-crash, repro, syslog-dead-end, field-validated]
maturity: field-validated
timestamp: 2026-06-24T00:00:00Z
resource: /findings/display_transient_rca_coldboot_repro_2026-06-24.md
---

# Dataless-display transient — cold-boot repro kit isolating a KMdev boot crash

## What it proves

A VDS consist switch can bring a display port to **link-up while forwarding no data** after a **cold**
power-up — the reported "display has link but can't reach the ZFR, a reboot fixes it" symptom. The
investigation **rules out** the obvious physical causes and points at a **boot-time software-module
crash** as the leading candidate:

- **Not a cable / physical-layer fault** — the affected display ports read `carrier false: 0`, Fast
  Link Detection enabled (not surge-tripped), clean RX/TX once up.
- **Not the VDS Fast-Link-Detection / surge mechanism** — displays negotiate 100 Mb/s and that
  mechanism is Gigabit-only.
- **Leading cause = KMdev boot crash.** On the reported train the persistent log carried
  `KMdev: internal error while setting interface vlan1` plus `KMdev`/`KMdiag`/`snmpd`/AgentX module
  restarts during boot. KMdev owns interface + PoE bring-up, so a crash there plausibly leaves ports
  linked-but-not-forwarding. A clean reboot re-inits KMdev and restores the display — which is exactly
  why field reboots "fix" it without root-causing it.
- **A warm reboot does NOT reproduce it** — only a real cold power removal does. The reboot that fixes
  the symptom is also the event that **wipes the persistent-log evidence**, so the RCA needs the log
  pre-armed and streamed off-box before the cold cycle.

The observable proxy for "linked-but-dataless" from the CCU side is **`ifInOctets = 0 / flat while
ifOperStatus = 1`** through the boot window (a clean boot shows `ifInOctets` climbing).

**Caveat (important):** a follow-on 126-switch / 7-train persistent-log harvest found the exact
`setting interface vlan1` signature **zero** times — the persistent logs are near-empty and rotate
fast. So KMdev remains a **strong-but-unconfirmed** hypothesis; the symptom could equally be
Stadler-side (display app / ZFR reachability / FW state at power-up), which no switch log would show.
Do not present KMdev as "the cause" without a controlled cold-boot repro that actually catches it.

## How it was captured

Two independent capture channels, both proven 2026-06-24 (off-box syslog is a dead end — see below):

1. **On-switch persistent log, cleared-then-captured.** Pre-arm the target switch with full debug
   tracing persisted to startup-config so the first boot instant is traced, then clear the persistent
   log for a clean slate:
   ```
   configure system logging debug dev,switch,poe,dhcp,lldp,rstp,diag   # one cmd/session — CLI can't chain
   save running-config force                                            # verify via show startup-config | grep 'logging debug'
   sysadmin delete log persistent
   ```
   (`core` and `mon` are rejected on fw 7.4.2 — the CLI keeps the valid subsystems and warns.)
   After the cold cycle, read `show log persistent` (survives power-off, holds the crash signature)
   **before any second reboot**, plus `show log` (volatile full boot trace, lost on next power-cycle).
2. **CCU-side SNMP boot-window poller** (`scripts/sw_bootwindow_poll.sh`) — samples
   `ifOperStatus` + `ifLastChange` + **`ifInOctets`** + `ifOutOctets` per display port every 3 s
   through the boot (`ssh -i openssh developer@<ccu> 'bash -s' < scripts/sw_bootwindow_poll.sh <sw-ip> 300 3`).
   This is the channel that proves the causal link from the CCU side, since the displays are
   unreachable behind the Stadler FW.

The cold cycle itself is a **physical power removal** of the target car/switch (~10 s off), coordinated
so the ~1–2 min outage lands on an out-of-service car. Verdict table in the kit separates the three
cases cleanly: `oper=1 & in=0/flat` + KMdev restarts = confirmed; `oper=1 & in climbing` = didn't
reproduce this cycle; `oper=2 forever` = a persistent dead-port, not the transient.

## Evidence

- Raw: [`display_transient_rca_coldboot_repro_2026-06-24.md`](/findings/display_transient_rca_coldboot_repro_2026-06-24.md)
  — the full repro kit: ruled-out list, capture architecture, pre-arm / cold-cycle / collect / teardown
  commands, and the verdict table. Includes the arming state for the actual fault train
  (4736-120 / Fzg 148, all 18 switches armed 2026-06-25).
- Raw: [`plog_crash_harvest_20260624.txt`](/findings/plog_crash_harvest_20260624.txt) — the 7-train
  persistent-log harvest. Shows the *background* crash-signature noise that IS present fleet-wide
  (`KMdiag: "snmpd" agent restarted`, `SWcore: "KMkon" module restarted`) but **no** `setting interface
  vlan1` line — the reason KMdev stays unconfirmed.
- Raw: [`kmdev_crash_sweep_20260624.tsv`](/findings/kmdev_crash_sweep_20260624.tsv) — per-switch crash
  tallies (train, IP, hostname, fw, and restart counts) used to rank suspect switches.

## So what (dead end / actionable)

- **Do NOT read "display link but no data" as a switch cabling fault** — check `carrier false` (0 here)
  before touching cables; the fault is above the physical layer.
- **Do NOT rely on off-box syslog to catch it** — the switch accepts `configure system logging host
  <ip>` but transmits **zero** packets on udp/514 (tcpdump-confirmed, even with debug + real events).
  Use the on-switch persistent/volatile logs + the SNMP boot poll.
- **Do NOT warm-reboot to reproduce, and do NOT reboot the down-display switch as a "fix" until the
  capture is collected** — the reboot both self-recovers the symptom and destroys the evidence.
- **Do NOT trust a Zabbix `ifOperStatus` bounce as ground truth** — `ifLastChange` proved several
  "synchronized bounces" in the Zabbix data never physically happened (SNMP poll artifact). Use the
  switch's own `ifLastChange` + logs.
- **Actionable next step:** catch the signature on a real cold boot (train armed) before escalating to
  VDS Rail / Stadler as a firmware defect — cite FW build + config version (v7 vs v8).

# Related

- [VDS Consist Switch — L2 counters & RSTP (dead-end #3: dataless display = possible KMdev boot crash)](/.kb/components/vds-consist-switch/l2-counters-rstp.md)
- [VDS Consist Switch — CLI & management (logging channels + remote-syslog dead end)](/.kb/components/vds-consist-switch/cli-and-management.md)
- [Zabbix / NMS monitoring model (phantom port-down / ifOperStatus artifact)](/.kb/topics/zabbix-nms-model.md)
