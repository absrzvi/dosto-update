---
type: component-knowledge
title: VDS Rail Consist Switch — Firmware Flashing
description: How the VDS switch takes a firmware image (TFTP fetch + SNMP boot-default OID + SNMP reboot), the regex-match and None-guard traps in the controller that make a flash silently fail, and why current-fleet pushes are mostly no-ops.
component: vds-consist-switch
vendor: VDS Rail
project: dosto-neu
tags: [switch, firmware, tftp, snmp, obn, boot-default, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

A VDS Rail Consist Switch is flashed **over the network** — it fetches its image via TFTP and is
told to boot it via SNMP. There is no CLI flash verb usable from a controller. This document
captures the flash mechanism and the controller-side traps that make a flash **report success while
silently doing nothing**, so an agent can verify by outcome rather than by the tool's own claim.

- **Identify by:** MAC OUI `a0:59:3a`.
- **Firmware family referenced here:** `sw-std-ng` 7.4.x (target build 7.4.2-77411).
- **Controller referenced here:** the Nomad OBN engine's `vdsrail.py` vendor driver.

> **Portability note.** All facts below are generic to this switch family and its OBN driver.
> Deployment-specific values appear only inside the `EXAMPLE (DOSTO NEU)` block.

# The flash mechanism (what actually happens on the wire)

A firmware push is a sequence of SNMP sets against the switch plus a TFTP fetch the switch itself
initiates:

1. **Point the switch at the image.** SNMP-set the firmware-URL OID to
   `tftp://<controller-vlan100-ip>/firmware/<image>.ksi`.
2. **Trigger the fetch.** SNMP-set the firmware update-trigger OID. The switch issues a TFTP RRQ to
   the controller and pulls the image.
3. **Poll the task-status OID** through the transfer. On success it reports the image is now the
   default; on failure it reports `Last error: Connection trouble or invalid URL`.
4. **Set the image as boot-default.** A separate SNMP set — the switch will otherwise boot back into
   the *old* image bank even after a successful download.
5. **Commit + reboot.** The reboot path is **SNMP only** (vendor reboot OID, value `3`). The switch
   also requires the hostname OID to be set to its current value first as OBN's commit-pending
   trigger; the bare reboot OID alone is ignored. (Full manual-bypass OID sequence is in the
   related switch-config bypass note.)

Config pushes use the same shape (TFTP fetch + reboot); the reboot is how OBN persists the config
(TFTP → running-config, then reboot flushes running → startup during orderly shutdown). If the
switch does not reboot within ~60s of the RRQ, the push did not take.

# The controller traps (why a flash silently fails)

These are the failure modes baked into the OBN `vdsrail.py` driver. Each was observed on a live CCU
and patched in-place; they are the reason you must verify a flash by re-reading the running version,
not by OBN's "success" line.

## Trap 1 — the boot-default regex never matches (firmware downloads but never boots)

The driver decides *whether to call the set-boot-default OID* by regex-matching the task-status
string. The original pattern only matched the **post-set** form:

```
Not running. System Firmware image loaded [<name>]
```

But the string the switch returns **during** a flash is:

```
Not running. System Firmware default image is now sw-std-ng_7.4.2-77411.ksi
```

The regex never matches → the set-boot-default OID is never called → the switch downloads the image,
reboots, and comes back on the **old** version. OBN reports success. **Both forms must be handled**
(the `default image is now` form during the flash, and the `image loaded [X]` form afterwards). This
is the class of failure where "obn update f reports Successful but the version never changes."

## Trap 2 — a `None` SNMP read during the reboot window crashes the run

While a switch is rebooting, SNMP gets return `None`. Two spots do `re.search(pattern, result)` on
that `None` and raise `TypeError: expected string or bytes-like object, got 'NoneType'`, killing the
whole update mid-run and leaving the remaining switches unflashed. **Guard every SNMP read with a
`if not result: continue`** before it is fed to a regex — in both the firmware-task poll and the
config-task poll.

## Trap 3 — the reboot round-trip crashes on a `None` hostname

The reboot path SNMP-*gets* the current hostname, then SNMP-*sets* it back (the commit trigger).
If the switch has already begun rebooting, the get returns `None` and the subsequent
`_snmp_set({oid: None})` crashes pyasn1 (`cannot convert 'NoneType' object to bytes`). **Skip the
hostname round-trip when the get returned `None`** — same `None`-guard family as Trap 2.

> All three are the same root lesson: **the reboot window returns `None` from SNMP, and the driver
> must treat every SNMP read as possibly-`None`.** A unified get-with-retry-returning-sentinel helper
> would eliminate the whole class.

# Verify by outcome, not by the tool's claim

The controller declares success at the point the SNMP set is acknowledged, well before the boot has
happened (and, per Trap 1, sometimes when the boot-default was never even set). The only authoritative
completion check is to re-read the running firmware version after the reboot window:

- Fresh discovery/inventory of the switch, read the running version, confirm `running == target`.
- Confirm the switch actually rebooted (uptime reset / it went unreachable then returned) — a
  version that "didn't change" plus "never rebooted" means the trigger or the boot-default step
  failed, not that the flash is slow.
- Cross-check RSTP re-convergence from a neighbour switch before calling the consist healthy again.

# Current-fleet reality: most pushes are no-ops

The entire fleet is already at the target firmware build. A firmware push against an at-target switch
is a **no-op** — nothing to flash. Consequently **Traps 1 and 2 are latent, not routinely
exercised**: they only fire against a *newer* image binary than what is deployed, which does not yet
exist in the field. Do not expect to reproduce them on a healthy current-fleet train; they are
documented here so that when a new switch image ships, the driver is already correct.

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not burn hours re-testing what has already been
> disproven on live hardware.

1. **There is no CLI reboot verb.** `reboot`, `reload`, and `system reboot` are all rejected
   (`Error in command, param is X [wrong]`). The confirmed reboot path is the **SNMP reboot OID**
   (value `3`). Do not go looking for a CLI reboot command.

2. **The SNMP reboot OID alone does NOT reboot the switch.** You must first SNMP-set the hostname OID
   to the switch's current value — that is OBN's commit-pending-config trigger. Without it, the reboot
   set is silently ignored and the switch never restarts.

3. **Do not trust OBN's "Successful" / "update applied" line as proof of a flash.** Per Trap 1 it
   prints success even when the boot-default OID was never set and the switch will boot the old
   image. Always re-read the running version.

4. **Do not push firmware to the head-of-train switch first, and do not batch a whole consist.**
   Flash/config pushes go **leaf-first** in OBNTree order — a parent reboot isolates its children.
   On a bench, the head-of-train switch's reboot can cut the controller's own path to everything
   downstream (a newer config version can also reassign the CCU-facing port). Push leaf switches as
   canaries first, head-of-train last.

5. **You cannot flash a switch whose management VLAN has no path to the controller.** The switch
   sources its TFTP fetch from its (unreachable) vlan100 interface — TFTP/HTTP/SCP all emit zero
   outbound packets. If a switch is only reachable over the native/untagged VLAN (e.g. a coupler
   mis-cable), a remote push is impossible; the fix is physical re-cabling, not a push. (VDS config
   load is network-URL-only — no `file://`/local load except USB.)

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Target firmware across the fleet: `sw-std-ng_7.4.2-77411`. All fleets currently at target →
  firmware pushes are no-ops (Traps 1/2 untestable until a newer binary exists).
- Controller = OBN on the CCU. The three traps are OBN Bugs 1 (regex), 2 (None-guard in both poll
  loops) and 7 (reboot hostname None-guard); the canonical patcher is `scripts/fix_obn.py` (applies
  the whole 1–11 suite idempotently). Reported 2026-05-04 on 4736-120 (CCU 10.179.2.1).
- SNMP for switches: v3, user `snmpadmin`, SHA1/AES128, authPriv, passphrase `NomadStayOut!`
  (the AP model is inverted — user `admin` — see the AP firmware doc).
- Controller vlan100 IP for the TFTP URL is the `.129/25` side of the CCU, not the `bond0 .1/25`.
- Manual per-switch push (bypassing OBN, for benches where `obn report` can't complete): full OID
  sequence and Jinja render recipe in memory `project_manual_tftp_obn_bypass.md`.

# Related

- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)
- [VDS Consist Switch — L2 counters & RSTP](/.kb/components/vds-consist-switch/l2-counters-rstp.md)
- [Nomad Connect / OBN — bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — discover→report→update](/.kb/components/nomad-connect-obn/discover-report-update.md)
- [Westermo AP — firmware activation](/.kb/components/westermo-ap/firmware-activation.md)

# Citations

[1] OBN bug suite reported 2026-05-04, 4736-120 (CCU 10.179.2.1) — Bugs 1/2/7 (regex, None-guards, reboot hostname None-guard); `troubleshooting-runbook.md` §"OBN Firmware & Config Update — Known Bugs".
[2] Manual TFTP/SNMP bypass validated 2026-05-21, Fzg 123 bench (A3+B3) — full OID sequence, commit-trigger requirement, leaf-first / head-of-train-last order.
[3] Config-versions-per-fleet audit 2026-06-01 — whole fleet at V8/target build.
