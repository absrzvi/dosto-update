# RCA repro kit — display "link but no ZFR data" transient (cold-boot capture)

**Date:** 2026-06-24 · **Author:** Abbas Rizvi
**Symptom (reported by Fabian, 4736-120 / 6002, 2026-06-24):** at power-up, passenger displays have link but cannot reach the ZFR; rebooting the switch (F2, A2) restores them.

---
> ## 🟢🟢 2026-06-25: ALL 18 SWITCHES ON 4736-120 (Fzg 148) ARE ARMED — the actual fault train
> **Target:** **4736-120 / Fzg 148** · **CCU** `10.179.2.1` · switches `10.179.2.178–195` (all 18).
> Armed 2026-06-25 (AR): debug tracing `dev,switch,poe,dhcp,lldp,rstp,diag` **persisted to startup-config** on every switch (verified in `show startup-config`), and **persistent log cleared** on every switch (clean slate). This is the train Fabian reported (displays link-up-but-no-ZFR at power-up) — F2 `.188` already logged `KMdev: internal error while setting interface vlan1` on the 2026-06-25 cold boot, and 10 vlan-3 passenger displays are currently link-down (see fleet-status Fzg 148 row).
>
> **Remaining step = the next cold power-cycle (or natural overnight power-down → power-up).**
> 1. After the next power-up, **before any second reboot**, read `show log persistent` on each switch (esp. the 7 with down displays: C1 .180, C2 .179, D1 .182, D2 .178, E1 .193, F2 .188, B2 .194) — the KMdev crash signature lives here briefly and is wiped by the next reboot.
> 2. For a deliberate live capture, stream the poller during the boot:
>    `ssh -i openssh developer@10.179.2.1 'bash -s' < scripts/sw_bootwindow_poll.sh <sw-ip> 300 3 > coldboot_120_<role>_$(date +%Y%m%d_%H%M).txt`
> 3. ⚠️ **Do NOT reboot the down-display switches as a "fix" until the capture is collected** — a reboot is the very thing that wipes the evidence (it also self-recovers the displays, which is why Fabian's reboots "fixed" it without root-causing it).
> ⚠️ The cleared-log slate is consumed by the FIRST reboot for any reason. The debug setting itself persists across reboots.
---
> ## 🟢 (earlier) A 6015 SWITCH WAS PRE-ARMED — superseded by the 4736-120 arming above
> **Target:** 6015 / `nv6-D1-v7-143` (role **D1**) · **CCU** `10.179.15.1` · **switch** `10.179.15.186`.
> Armed 2026-06-24: debug tracing `dev,switch,poe,dhcp,lldp,rstp,diag` is **persisted to startup-config** (survives power-off), and the **persistent log is cleared** (clean slate).
> Display ports expected to bounce on cold boot: **e1-14, e1-15, e2-0, e2-2, e2-3** (up at arm time). e2-1, e2-4 are persistent dead-ports (ignore).
>
> **Remaining step = the cold power-cycle only.** When someone is at the train and the D-car can take a ~1 min outage:
> 1. Start the poller from your laptop (see "The cold cycle" below): `ssh ... 'bash -s' < scripts/sw_bootwindow_poll.sh 10.179.15.186 300 3 > coldboot_poll.txt`
> 2. Have them **physically pull power** on the D-car switch (cold — not a CLI/SNMP reboot), wait ~10 s, restore.
> 3. Collect logs (see "Collect") and read the verdict table.
>
> ⚠️ If the switch reboots for any OTHER reason before the test (e.g. train power-down overnight), the cleared-log slate is consumed — just re-run the two pre-arm commands. The debug setting itself persists.
> ⚠️ Valid debug subsystems on fw 7.4.2: `dev,switch,poe,dhcp,lldp,rstp,diag` — `core` and `mon` are REJECTED (the CLI prints "unknown subsystem" but still keeps the valid ones; set them all in one command).
---

## What the investigation established (so this repro is aimed correctly)

Ruled OUT, with direct evidence:
- **Not a cable / physical-layer fault.** Display ports show `carrier false: 0`, Fast Link Detection `enabled` (not surge-tripped), clean RX/TX once up.
- **Not the VDS Fast-Link-Detection / surge mechanism.** Displays negotiate 100 Mb/s; that mechanism is Gigabit-only.
- **Zabbix `ifOperStatus` history is unreliable for this** — proven by `ifLastChange`: several "synchronized bounces" in the Zabbix data never actually happened (ports were up continuously; the down→up was an SNMP poll artifact). Use the switch's own `ifLastChange` + logs as ground truth, not Zabbix.

Leading root-cause candidate (seen on 6002 F2 persistent log):
- **Boot-time software-module crash.** `KMdev: internal error while setting interface vlan1` plus `KMdev` / `KMdiag` / `snmpd` / `AgentX` module restarts during boot. `KMdev` owns interface + PoE bring-up — a crash there plausibly leaves ports linked-but-not-correctly-forwarding ("link, no data"). A clean reboot re-inits KMdev correctly → displays work.

Why a live cold-boot capture is the only reliable RCA: the crash evidence lives only in the **persistent log**, briefly, and is **wiped by the very reboot that fixes the symptom**. A warm SNMP reboot did NOT reproduce it (6015 R3_SW1 warm-rebooted cleanly). We need a **cold** power-cycle with logging pre-armed and streamed off-box.

## Capture architecture

> ⚠️ **Remote syslog does NOT work on this firmware (7.4.2) — confirmed 2026-06-24.** The switch accepts `configure system logging host <ip>` into its running-config but transmits **zero** syslog packets (verified by tcpdump on the CCU: nothing on UDP/514 even with debug active and real port events firing). Do **not** rely on off-box syslog. The two channels below are what actually work.

Two independent capture channels, both proven 2026-06-24:
1. **On-switch persistent log, cleared-then-captured.** The persistent log survives the power-cycle and is where the crash signature appears (`internal error while setting interface vlan1`). It is short and overwrites, so **clear it before the cold cycle** (`sysadmin delete log persistent`) and read it **immediately after** the switch is back. Pair with `show log` (volatile — full boot trace, but lost if the switch is power-cycled again). Enable debug tracing (`dev,switch,poe,dhcp,lldp,rstp,diag`) saved to startup-config so the volatile log is fully traced from the first boot instant.
2. **CCU-side SNMP boot-window poller** ([`scripts/sw_bootwindow_poll.sh`](../scripts/sw_bootwindow_poll.sh)) — samples `ifOperStatus` + `ifLastChange` + **`ifInOctets`** + `ifOutOctets` per display port every 3 s through the boot. **`ifInOctets` is the key "dataless" tell:** a port that reaches `oper=1` (link UP) but whose `ifInOctets` stays **0 / flat** is *linked-but-not-receiving* = the symptom. On a clean boot the same port's `ifInOctets` climbs. This is the channel that proves the causal link (crash-boot → linked-but-silent port) from the CCU side, since the displays themselves are unreachable behind the Stadler FW.

## Target selection (do FIRST, before anyone touches power)

Pick a switch on a **non-passenger car** (or coordinate an out-of-service window). Confirm what is behind it so the ~1–2 min outage is acceptable. Record:
- Train# / Fzg, CCU IP, switch IP, switch role (e.g. D1).
- `show interface summary` — which display ports are currently UP (these are the ones we expect to bounce).
- Confirm it is NOT a coupler / head-of-train switch that would isolate downstream switches.

> Note observed during investigation: some 6015 switches carry **v7** config/hostnames (`nv6-D1-v7-143`) while 6002 is **v8** (`nv6-*-v8-148`). Capture the hostname (`v7`/`v8`) and firmware (`7.4.2` build) of the target — the RCA needs to know whether the crash correlates with a config/FW version.

## Pre-arm (run from your laptop, against the chosen CCU+switch — BEFORE the cold cycle)

Variables: `CCU=<ccu-ip>`, `SW=<switch-ip>`.

```bash
SSHSW="sshpass -p 'Nom@dCome1n' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no admin@$SW"
```

### 1. Enable debug tracing + persist to startup-config (one cmd per SSH session — CLI cannot chain)
```bash
ssh -i openssh developer@$CCU "$SSHSW 'configure system logging debug dev,switch,poe,dhcp,lldp,rstp,diag'"
ssh -i openssh developer@$CCU "$SSHSW 'save running-config force'"
# verify persisted (must show the debug line):
ssh -i openssh developer@$CCU "$SSHSW 'show startup-config'" | grep -i 'logging debug'
```

### 2. Clear the persistent log so the post-cold-boot capture is clean
```bash
ssh -i openssh developer@$CCU "$SSHSW 'sysadmin delete log persistent'"
```

## The cold cycle

Coordinate with the person at the train: **physically remove power** from the target car/switch (cold — NOT a CLI/SNMP reboot; a warm reboot did not reproduce the crash). Wait ~10 s, restore power. Note wall-clock time of power-off and power-on.

Start the boot-window poller on the CCU **just before** power is restored (captures the linked-but-dataless signature live):
```bash
# from laptop — streams the poller script to the CCU, writes capture locally:
ssh -i openssh developer@$CCU 'bash -s' < scripts/sw_bootwindow_poll.sh $SW 300 3 \
  > coldboot_poll_$(date +%Y%m%d_%H%M).txt 2>&1
# (300s window, 3s interval. For NV4 or a different consist, edit IDXS in the script.)
```

## Collect (after the switch is back ~2–3 min)

```bash
# 1. Persistent log (survives power-off — primary crash-signature source):
ssh -i openssh developer@$CCU "$SSHSW 'show log persistent'" > sw_persistent_$(date +%Y%m%d).txt
# 2. Volatile log (full boot trace WITH debug; lost on next power-cycle so grab it now):
ssh -i openssh developer@$CCU "$SSHSW 'show log'"            > sw_volatile_$(date +%Y%m%d).txt
# 3. Final port state:
ssh -i openssh developer@$CCU "$SSHSW 'show interface summary'"
ssh -i openssh developer@$CCU "$SSHSW 'show poe'"
```

## What to look for (the verdict)

Read the poller output per display port. The three cases are cleanly separable:

| Poller signature | Log signature | Conclusion |
|---|---|---|
| `oper=1` (UP) but **`in=0` / flat** through the whole window | `KMdev: internal error while setting interface vlan1` + `KMdev`/`KMdiag` restarts in boot trace | **CONFIRMED root cause = KMdev boot crash → linked-but-dataless.** This is the symptom. Escalate to VDS Rail / Stadler as a firmware defect; cite FW build + config version (v7/v8). |
| `oper=1` (UP) and **`in=` climbing** (receiving) | Clean boot, no module restarts | Cold boot did NOT reproduce it this time — crash is intermittent. Re-arm and repeat, or use arm-and-wait on natural power-ups. |
| `oper=2` (DOWN), `lc≈boot`, `in=0 out=0` forever | port never links | **Persistent dead-port** (cable/display end), NOT the transient — see cable-issues-register `end-device not connected`. |

(Reference healthy values from a live NV6 switch, 2026-06-24: working display ports read `oper=1 in=~500k–630k out=~90M`; dead ports `oper=2 in=0 out=0`.)

## Teardown (after capture — return switch to baseline)

```bash
ssh -i openssh developer@$CCU "$SSHSW 'no configure system logging debug'"
ssh -i openssh developer@$CCU "$SSHSW 'save running-config force'"
# verify clean (should print 'baseline clean'):
ssh -i openssh developer@$CCU "$SSHSW 'show startup-config'" | grep -i 'logging debug' || echo 'baseline clean'
```

## Safety notes (learned this session)

- Switch CLI takes **one command per SSH session** — never `;`-chain.
- A **warm** reboot (SNMP OID, CLI) may not trigger the cold-boot crash — must be a **cold** power removal.
- The reboot/power-cycle drops the car switch + anything behind it for ~1 min — confirm the car is out of passenger service.
- Empty output from a switch config command is ambiguous (silent success or silent no-op) — always verify via `show running-config` / `show startup-config`.
