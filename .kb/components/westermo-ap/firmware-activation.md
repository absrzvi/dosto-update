---
type: component-knowledge
title: Westermo AP — Firmware Activation
description: Why a Westermo RT610LV firmware push stages but doesn't always activate — the flash-trigger hang, the download-failure-under-batch case, the fact that the controller never verifies post-reboot, and how to tell "slow-but-fine" from "genuinely hung" via uptime + the rpcFwFlash status code.
component: westermo-ap
vendor: Westermo
project: dosto-neu
tags: [ap, westermo, rt610lv, ibexos, firmware, activation, tftp, snmp, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

Pushing firmware to a Westermo RT610LV is unreliable in a way that is easy to misdiagnose in both
directions — declaring a healthy slow AP "stuck," or declaring a genuinely hung AP "done." The push
mechanism itself is simple; the trap is that **the controller declares success the instant it sends
the SNMP flash trigger, and never re-reads the running version afterward.** This document explains the
activation failure modes and the exact signals (uptime + the flash-status code) that distinguish
recoverable from unrecoverable.

- **Identify by:** MAC OUI `00:14:5a`. Model `RT610LV` (IbexOS; target image family 6.11.x).
- **Push transport:** TFTP fetch (AP pulls the image) + three SNMP sets to trigger the flash.

> **Portability note.** All facts below are generic to this AP family and its OBN driver.
> Deployment-specific values appear only inside the `EXAMPLE (DOSTO NEU)` block.

# The push mechanism (and where it lies)

The controller's Westermo driver (`westermo.py::set_firmware_version`) sends exactly three SNMP sets
and then returns success:

```
setFwFileUrl     = tftp://<controller>/firmware/<image>.img
setFwKeepConfig  = 1   (keep config across flash)
rpcFwFlash       = 2   (trigger flash)   ← the trigger
```

It checks only that the `rpcFwFlash` **SET echo** returned `2`, then returns `True`. Because pysnmp's
SET returns the value you just wrote, that check is `2 != 2` — always false — so **the controller
always reports success, before any download / validation / flash has happened, and never re-reads the
version.** `rpcFwFlash` is actually a **status field on read-back**: `2` = writing, `0` (nop) = done,
`-1` = downloadError, `-2` = flashError. The controller never performs that read-back. This is why a
push can "succeed" and leave the AP on the old version — the first time anyone notices is a later
`obn validate`.

There is **no separate set-default-firmware / boot-bank OID**: `rpcFwFlash=2` is the complete standard
operation (download → validate → flash to filesystem, single-image, not dual-bank). Earlier "OBN must
call a set-default OID" theories were wrong.

# The three post-push states (this is the whole diagnosis)

After a push, "firmware OID still shows the old version" hides three different situations. **Uptime
plus the `rpcFwFlash` read-back tell them apart — firmware version alone cannot.**

| Case | Signal | Meaning | Action |
|---|---|---|---|
| **(a) slow-but-fine** | uptime **reset** to a low value; version flips to target shortly | Flash worked, AP rebooted; the check just read mid-cycle. RT610LV flash→reboot→re-report can take **well over 5 min** under load. | **Wait one more poll.** Do NOT re-push. Counting these as "stuck" and re-pushing a healthy AP is the #1 real-world error. |
| **(b) genuine flash hang** | `rpcFwFlash = 2` (writing), uptime **large/unchanged** (never rebooted) | The AP ACK'd the trigger, took the image, then hung in "writing" forever. A genuine RT610LV flash-trigger defect. | **Not recoverable over SNMP.** A plain reboot just boots the old image again. Needs the LuCI HTTPS firmware-upload bypass or a Westermo firmware fix. A single retry sometimes works (the trigger is flaky-not-dead). |
| **(c) download failure** | `rpcFwFlash = -1` (downloadError), uptime unchanged; look for `in.tftpd: read(ack): Connection refused` | The image never arrived, so there was nothing to flash. Upstream TFTP transfer refused — typically the conntrack-UDP-timeout expiring the helper return-path mid-transfer under batch concurrency. | **Recoverable.** Fix the TFTP conntrack path / reduce concurrency and re-push (`-1` → `2`). Note (c) can sit *underneath* (b): fix the download and the AP may then hit the real hang. |

On uptime alone, (b) and (c) look identical — you must read the `rpcFwFlash` status code to tell them
apart. **Never declare an AP "stuck" without confirming it did NOT reboot (uptime unchanged) AND
reading which status code it carries.**

# Verify by outcome, never by the controller's "Successful"

The controller's success line only means the AP acknowledged the SSH/SNMP command — not that any
firmware bytes transferred. The verification layer the controller lacks:

1. **Confirm the transfer even started** — watch the TFTP daemon for an `RRQ from <ap-ip>`. No RRQ =
   no transfer, regardless of "Successful."
2. **Poll for completion up to ~15 min**, tracking **firmware version AND uptime AND `rpcFwFlash`** —
   not just version. Real completion is 6–10 min typical, up to 15 min worst case; the controller's
   own internal wait is too short.
3. **Only declare failure** once you've confirmed the AP did not reboot and read a real error/`-1`/`-2`
   or a still-`2`-past-budget hang.

The matching controller fix polls `rpcFwFlash` + uptime inside the driver so it returns the honest
boolean (True on reboot/nop, False only on a real `-1`/`-2` or a no-reboot timeout). With it applied,
the push blocks up to ~10 min doing this correctly instead of returning instantly.

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not burn hours re-testing what has already been
> disproven on live hardware.

1. **The "m-variant fails, non-m succeeds" theory is DEAD.** It looked compelling early (coaches 3+4
   were all-m and stuck) but a full-batch test put m AND non-m APs in both the success and failure
   buckets; a plain `AP4-v1` was stuck while m-APs activated. It is **per-AP flash-trigger flakiness**,
   not a variant defect. Stop framing it as "m-variant failure."

2. **A plain reboot does NOT recover a case-(b) hang.** Force-rebooting an AP that ACK'd
   `rpcFwFlash=2` but never flashed just boots it back into the old image (proven: `.226` rebooted
   and came back on the old version). Reboot only helps a case-(a) AP that had already flashed. Don't
   use `ssh reboot` as the fix for a genuine hang.

3. **Retries and force-reboots do not help a genuine hang** because the problem is the AP's internal
   flash-commit, not the controller's wait time or the reboot trigger. A retry occasionally succeeds
   only because the trigger is flaky (sometimes hangs, sometimes takes) — it is not a reliable fix.

4. **Do not count "stuck" before the AP has had time to reboot.** Several "deferred/stuck" APs were
   **false negatives** — the flash succeeded and the AP rebooted onto target, but `obn validate` was
   read before the (slow) reboot completed. On one train, re-validating after a longer settle moved
   the count 12 → 15 at target with no action. Confirm NO reboot happened (uptime unchanged) before
   calling an AP stuck.

5. **Do not batch firmware pushes.** Under many concurrent TFTP transfers the conntrack UDP timeout
   expires the helper return-path mid-transfer → `Connection refused` → case-(c) download failures on
   a chunk of the batch (9/16 in one test), which then masks the underlying case-(b) hangs. Single-AP
   serial (or a small chunk) is the rule; a full batch just needs redoing.

6. **Do not diagnose a stuck AP as "bricked."** Its restricted BusyBox CLI, closed TCP/80, and
   SNMP-timeout-to-CLI are all *normal* — compare a sibling before declaring damage (see the
   factory-vs-Nomad doc's brick dead-end).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Target firmware: `6.11.2-0` (image `IBEX-firmware-6.11.2-0.img`); previous `6.10.0-0`. There is only
  ONE image on the CCU — no separate `-m` image (another reason the m-variant theory is wrong).
- **Direct `rpcFwFlash` read** (when an AP looks stuck): OID `.1.3.6.1.4.1.16177.1.400.1.3.2.1.0`, via
  v3 `admin` / authNoPriv-or-authPriv / SHA / `NomadStayOut!`. Vanilla `snmpget -v2c -c NomadStayOut!`
  and user `snmpadmin` both fail — wrong form. Prefer `obn discover` + LuCI overview over ad-hoc
  `snmpget` (the `admin` user gets `authorizationError` on some OIDs).
- **AP SSH (Nomad):** `nomad`/`NomadComeIn`. `ssh nomad@<ap> reboot` returns before the network tears
  down — sleep the full ~90s, don't infer reboot from connection-close.
- The controller-side fix is **OBN bug #11** (`scripts/fix_obn_bug11_westermo_fw_verify.py`, marker
  `# NDP-PATCH-BUG11-FW-VERIFY`; poll window tuned to ~600s). R&D ticket **TRIAG-8585**: make the
  timeout configurable, drop the hardcoded "RT-610" text, gate the "rebooting" print on the real
  verdict, re-read version post-window before declaring failure.
- TFTP-conntrack-helper gap (the case-(c) cause) is in `dosto-tftp-helper-check`; runtime fix is
  `modprobe nf_conntrack_tftp` + a raw-PREROUTING CT helper rule on udp/69.
- Evidence: 4736-109 (2026-06-08, definitive uptime/`rpcFwFlash` model), 4734-190 / Fzg 90
  (2026-06-09, 16-AP batch — m-theory killed, download-vs-hang layers separated). Skill:
  `dosto-ap-firmware-update`.

# Related

- [Westermo AP — factory vs Nomad config](/.kb/components/westermo-ap/factory-vs-nomad-config.md)
- [Nomad Connect / OBN — bug suite (bug #11)](/.kb/components/nomad-connect-obn/bug-suite.md)
- [VDS Consist Switch — firmware flashing](/.kb/components/vds-consist-switch/firmware-flashing.md)
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)

# Citations

[1] Definitive uptime + `rpcFwFlash` two-case model, 4736-109 .236/.226, 2026-06-08 (live bug #11 test).
[2] 16-AP batch test, 4734-190 / Fzg 90, 2026-06-09 — m-variant theory disproven; case-(c) download-failure-under-batch separated from case-(b) hang; TRIAG-8585 items.
[3] Partial-flash-persists + no-post-reboot-verify, Fzg 8 .229, 2026-05-22.
[4] `westermo.py::set_firmware_version` SET-echo bug + WESTERMO-SW6-MIB `rpcFwFlash` status semantics, 2026-06-08.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/components/westermo-ap/factory-vs-nomad-config|factory-vs-nomad-config]]
- [[.kb/components/nomad-connect-obn/bug-suite|bug-suite]]
- [[.kb/components/vds-consist-switch/firmware-flashing|firmware-flashing]]
- [[.kb/topics/l2-health-methodology|l2-health-methodology]]
