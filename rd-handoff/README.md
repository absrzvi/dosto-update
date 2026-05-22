# R&D Handoff — DOSTO NEU v8 Rollout Patch Suite

**Author:** Abbas Rizvi (Nomad Digital, on-board networks)
**Date:** 2026-05-22
**Scope:** All hand-applied patches and runtime workarounds currently keeping the DOSTO NEU v8 rollout viable. Filed together so each owner can route their item to the right repo / Puppet env / template — and so partial acceptance doesn't leave a worse half-state than what we have today.

## Why this suite exists

During the v8 firmware/config rollout across the 4734/4736/4705/4706 fleets (Jan–May 2026), we hit **10 distinct OBN bugs** and **4 deployment-side workarounds** that we now patch by hand on every CCU before any commissioning session. The hand-patch tax is real:

- Every CCU we visit requires SCP-ing fix scripts and entering a btrfs chroot to make patches survive reboot. This is currently encoded in two skills (`dosto-obn-patches`, `dosto-tftp-helper-check`) and a per-train state machine that tracks "is this CCU at 10/10 patches yet, and are they persisted?"
- The fleet currently has trains in three regression states: vanilla (`0/10`), partially-patched (any value `<10/10`), and `10/10 persisted`. Any of the first two will hang or crash on the next `obn update` or `obn report`.
- The auto-update timer (`nd-auto-system-update.timer`, runs nightly 00–04:21 UTC) periodically re-promotes a vanilla snapshot from Puppet env `dostoneu_migration_mar5` and wipes our patches. Our current mitigation is to rename `nd-systemupdate.sh` → `nd-systemupdate.sh.dont` on every commissioning visit. That is obviously not sustainable.

The fix is to **land all 10 OBN patches in the OBN source repo, tag a release, and bump the Puppet env's pin** — then `nd-systemupdate.sh` does what it's supposed to and the hand-patching era ends.

## Severity ranking

Listed worst-first. The first two are the ones that turn a routine commissioning run into a multi-hour recovery.

| # | One-line failure | Class | Affected runs |
|---|---|---|---|
| **10** | `obn report` infinite-loop @ 100% CPU + **27 GB+ RSS leak** when any device is offline or has a duplicate position | hang + leak | every `obn report` on a not-fully-online consist |
| **9** | `IndexError: pop from empty list` from pysnmp dispatcher race in multi-threaded `obn update c sw` | crash mid-batch | every parallel `obn update c sw` on a multi-switch consist |
| **5** | `obn update f all` restart silently fails for not-yet-reached devices (TFTP ipset not pre-populated) | silent partial success | any restarted firmware-batch run |
| **1** | `obn update f` reports success but switch boots old firmware (regex mismatch on the "default image is now" SNMP response) | silent no-op | every firmware push to a switch that has just been flashed once |
| **6** | `AttributeError: 'NoneType' object has no attribute 'type'` in `tree.py` when consist is coupled | crash on start | every `obn update c` on coupled consists |
| **7** | `TypeError: cannot convert 'NoneType' object to bytes` in `vdsrail.reboot()` when SNMP-get hostname returns None mid-reboot | crash mid-batch | most `obn update c all` runs (varies by SNMP timing) |
| **2** | `TypeError: expected string or bytes-like object, got 'NoneType'` in `vdsrail` firmware/config polling loops | crash mid-batch | every `obn update` that touches a rebooting switch |
| **3** | pysnmp `KeyError: 'errorIndication'` propagates out of thread pool | crash mid-batch | switches rebooting mid-SNMP-session |
| **4** | `AttributeError: 'NoneType' object has no attribute 'endswith'` in `device.needs_firmware_update()` | crash on start | any device with `firmware: None` in discovery |
| **8** | `AttributeError` mirror of #4 for `device.needs_configuration_update()` (`self.config` None) | crash on start | any device with `config: None` in discovery |

Bug 10 is the only one in the suite that **hangs rather than crashes**, and it is the only one whose failure mode requires `kill -9` and grows unboundedly. R&D should prioritise it.

## Suite contents

### OBN repo patches (10 bugs)

One markdown doc per bug. Each is self-contained — pick one off, file it as one ticket, the writeup has everything the assignee needs.

| File | Title | File patched |
|---|---|---|
| [`bug-01-vdsrail-firmware-regex.md`](bug-01-vdsrail-firmware-regex.md) | Firmware regex misses "default image is now" SNMP response | `lib/device/vendor/vdsrail.py` |
| [`bug-02-vdsrail-polling-none-guard.md`](bug-02-vdsrail-polling-none-guard.md) | `re.search` crash when SNMP poll returns None | `lib/device/vendor/vdsrail.py` |
| [`bug-03-snmpdevice-keyerror.md`](bug-03-snmpdevice-keyerror.md) | pysnmp `KeyError` propagates from thread pool | `lib/device/snmpdevice.py` |
| [`bug-04-device-firmware-none.md`](bug-04-device-firmware-none.md) | `.endswith()` on None firmware crashes `needs_firmware_update` | `lib/report/device.py` |
| [`bug-05-update-tftp-ipset-prepopulate.md`](bug-05-update-tftp-ipset-prepopulate.md) | `tftp_allowed` ipset not pre-populated → silent restart failure | `cli/update.py` |
| [`bug-06-tree-cross-consist-none-guard.md`](bug-06-tree-cross-consist-none-guard.md) | Crash on LLDP neighbour from coupled consist | `lib/tree.py` |
| [`bug-07-vdsrail-reboot-hostname-none.md`](bug-07-vdsrail-reboot-hostname-none.md) | `reboot()` crashes on None hostname from SNMP-get | `lib/device/vendor/vdsrail.py` |
| [`bug-08-device-config-none.md`](bug-08-device-config-none.md) | `.endswith()` on None config crashes `needs_configuration_update` | `lib/report/device.py` |
| [`bug-09-snmpdevice-pysnmp-thread-safety.md`](bug-09-snmpdevice-pysnmp-thread-safety.md) | pysnmp asyncore dispatcher not thread-safe → `IndexError` race | `lib/device/snmpdevice.py` |
| [`bug-10-report-dosto-neu-bfs-hang.md`](bug-10-report-dosto-neu-bfs-hang.md) | `number_coaches` BFS infinite-loop + RSS leak on missing/duplicate device | `lib/report/report_dosto_neu.py` |

### Non-OBN companion items (4)

These don't live in the OBN repo but they're inseparable from the v8 rollout pain — they're the other reasons commissioning currently takes a full session per train instead of an hour.

| File | Title | Likely owner repo |
|---|---|---|
| [`companion-01-tftp-conntrack-helper-puppet.md`](companion-01-tftp-conntrack-helper-puppet.md) | CCU firewall `nf_conntrack_tftp` + raw-PREROUTING CT helper missing → silent `obn update f ap` batch failure | Puppet (`60-allow-management` or equivalent) |
| [`companion-02-factory-ap-snmp-community.md`](companion-02-factory-ap-snmp-community.md) | Factory-config Westermo APs silently reject OBN SNMP (community mismatch) → require LuCI HTTP bypass | AP image / Westermo provisioning |
| [`companion-03-vlan7-networks-yaml-formula.md`](companion-03-vlan7-networks-yaml-formula.md) | `/etc/nd-redundancy/networks.yaml` vlan7 IP formula computes from OBN's `train_id` not Fzg → wrong IP on commissioning | Puppet (`nd-redundancy` module) |
| [`companion-04-fzg-id-template-formula.md`](companion-04-fzg-id-template-formula.md) | `/etc/obn/template/nv*-*.cfg` shipping with broken `{%- set train_id = 128 + train_id -%}` formula → wrong Fzg rendered into switch hostnames | OBN template repo (`nd-obn-template-dostoneu-{nv4,nv6}`) |

### Suite-level docs

- [`repo-plan.md`](repo-plan.md) — recommended branch/commit/MR structure for landing the 10 OBN bugs in `nd-obn`, plus the release-and-Puppet-bump sequence that turns `nd-systemupdate.sh` into the actual fix-delivery vehicle. Includes a per-bug test plan (regression test shape, mock seams, test data).

## How we'd like to work with R&D on this

We don't have push access to `nd-obn` (or to the Puppet env), so this handoff is the most we can do unilaterally. Concretely we'd like:

1. **One R&D engineer assigned as suite owner** to triage the 10 bug docs and route each one (e.g. Bug 10 might be a different module owner than Bugs 1/2/7). A suite owner avoids the "everyone thinks someone else is on it" failure mode that has held this up since 2026-05-13 (when we first owed these tickets).
2. **Accept-or-counter on each fix shape**. Several patches (Bugs 5, 9, 10 especially) are *one* way to fix the underlying issue; R&D may want to do them differently. We'd rather merge a different shape than ship none.
3. **A release tag** once the suite (or any subset) is in. We can bump fleet-status to track "this train is on `nd-obn 2.2.24-v8patches`" instead of grepping for 10 markers in `/usr/share/obn/`.
4. **A Puppet env bump** to that tag. Without this, the patches sit in `nd-obn` and never reach a CCU.

## What we will keep doing in the meantime

Our skill `dosto-obn-patches` will continue to:
- Grep for all 10 markers on every train visit
- Print recipes to apply / persist them via `nd-systemupdate.sh shell`
- Track per-train state in `fleet-status.md`

Once Bugs 1–N land in `nd-obn` and Puppet picks them up, we'll drop the corresponding markers from the skill's check matrix and update `fleet-status.md` to reflect the new baseline. This handoff is not asking R&D to take over our skill — it's asking R&D to make the skill smaller over time.

## Cross-references

- Project workspace: `dosto-troubleshooting/` (this repo)
- Skill source: [`.claude/skills/dosto-obn-patches/SKILL.md`](../.claude/skills/dosto-obn-patches/SKILL.md)
- Existing fix scripts (R&D can adapt these directly): `scripts/fix_obn.py`, `scripts/fix_obn_bug8.py`, `scripts/fix_obn_bug9_pysnmp_thread_safety.py`, `scripts/fix_obn_bug10_report_dosto_neu_bfs.py`, `scripts/fix_obn_bugs67.py`, `scripts/fix_bug1_regex.py`
- Per-train evidence: [`fleet-status.md`](../fleet-status.md), [`fleet-journal.md`](../fleet-journal.md)
- Prior internal writeup: [`troubleshooting-runbook.md`](../troubleshooting-runbook.md) § "OBN Firmware & Config Update — Known Bugs and Fixes" (covers Bugs 1–7 in detail; Bugs 8/9/10 are in their respective fix-script headers)
