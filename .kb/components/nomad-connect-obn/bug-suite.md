---
type: component-knowledge
title: Nomad Connect / OBN — The 11-Bug Suite
description: The 11 known OBN engine bugs (crashes, hangs, silent no-ops) that break obn update / obn report on DOSTO NEU consists, plus how to detect and apply the fixes.
component: nomad-connect-obn
project: dosto-neu
tags: [obn, bugs, patches, snmp, tftp, firmware, config, hang, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

**OBN** (`nd-obn`, the Nomad onboard-network engine) is the CCU-side tool that discovers,
reports on, and updates the consist's switches and APs (`obn discover / report / update f / update c`).
On DOSTO NEU consists a suite of **11 distinct engine bugs** turns a routine `obn update` or
`obn report` into a crash, a silent no-op, or — in one case — an unbounded hang. Each bug is a
`None`/`KeyError`/regex/race defect that fires **only when a device is missing, rebooting, or on a
coupled foreign consist** — i.e. exactly the conditions of a real rollout. This doc is the reference
for what each bug is and how to detect it.

**The cardinal rule: apply all 11 together, or none.** A partially-patched engine is *worse* than
vanilla — the remaining crash/hang modes still fire mid-run and write partial state to the consist
(mixed firmware/config → RSTP topology storms). With all 11 present, OBN exits *bounded* (clean or
non-zero, but never hangs/leaks) on every known failure mode involving an absent or unresponsive device.

- **Detection is by grep marker**, not by version string. Each fix inserts a deterministic string
  into the target `.py` file. The `dosto-obn-patches --check` skill greps for all 11 and is the
  **single source of truth** for patch state.
- **Fixes are local, not upstream.** The scripts under `scripts/fix_obn*.py` apply them. R&D is
  upstreaming the whole suite under one ticket (see EXAMPLE block) — once shipped, the skill flips
  from "apply" to "verify deployed".

> **Portability note.** File paths, package versions, ticket IDs, and per-train evidence in the
> `EXAMPLE (DOSTO NEU)` block are deployment-specific. The bug *shapes* (None-guard, regex-widen,
> dispatcher-lock, BFS-terminate) are generic to the engine.

# The 11 bugs

Each row: the file, the symptom you'd see, the root cause, and the one-line fix. Grep markers are in
the last section.

| # | File | Symptom | Root cause | Fix |
|---|---|---|---|---|
| 1 | `vdsrail.py` `set_firmware_version` | `obn update f` reports **success but switch boots old firmware** (silent no-op) | Post-flash SNMP status regex matches only the old `"image loaded [X]"` string, not the newer `"default image is now …"` → set-default-boot OID never written | Widen the regex to accept both response formats. |
| 2 | `vdsrail.py` (two polling loops) | `obn update` **crashes mid-batch** when a switch is rebooting | `re.search("Not running", result)` with `result=None` from an SNMP-get timeout → `TypeError` | Add `if not result: continue` guard in **both** the firmware and config polling loops (two sites). |
| 3 | `snmpdevice.py` `_snmp_parse_results` | `obn update` **crashes** on a switch that reboots mid-SNMP-session | pysnmp asyncore drops its `errorIndication` key → `KeyError` propagates out of the thread pool | Wrap the generator drain in `try: … except KeyError: return {}`. |
| 4 | `device.py` `needs_firmware_update` | `obn update f` **crashes on start** if any device has `firmware: None` | `None.endswith(...)` → `AttributeError` during the pre-batch "what needs updating" pass | `return bool(self.firmware) and not self.firmware.endswith(...)`. |
| 5 | `update.py` `update()` | Restarted firmware batch **silently skips** not-yet-reached devices (they never flash, but run reports success) | `tftp_allowed` ipset is populated per-device as processed; a crashed run leaves later devices with no ipset entry → their TFTP fetch is silently dropped | Pre-populate the ipset for **all** target IPs up front (`ipset add … -exist`). |
| 6 | `tree.py` `create_tree` | `obn update c` **crashes on start** when the consist is coupled to another live unit | LLDP neighbour from the foreign consist isn't in local `discovery.json` → `next(..., None)` → `None.type` deref | `if neighbour_device is None: continue` before the `.type` check. |
| 7 | `vdsrail.py` `reboot()` | `obn update c all` **crashes mid-batch** | reboot does SNMP-get-then-set of the hostname; if the switch already started rebooting, get returns `None`, the set of `None` → `TypeError: cannot convert 'NoneType' object to bytes` | `if hostname is not None:` around the hostname re-set; reboot OID still fires. |
| 8 | `device.py` `needs_configuration_update` | `obn update c` **crashes on start** if any device has `config: None` | mirror of Bug 4 for `self.config` | `return bool(self.config) and not self.config.endswith(...)`. |
| 9 | `snmpdevice.py` `_snmp_parse_results` | **Parallel** `obn update c sw` **crashes mid-batch** with `IndexError: pop from empty list` | one shared `SnmpEngine` across `ThreadPoolExecutor` workers; pysnmp's asyncore out-queue is not thread-safe and races on `pop(0)` | Add a module-level `threading.Lock` (`_SNMP_DISPATCH_LOCK`) around the `list(generator)` drain. |
| 10 | `report_dosto_neu.py` `number_coaches` | **`obn report` hangs** at 100% CPU with unbounded RSS growth (27 GB+ observed) when any device is missing or has a duplicate position — needs `kill -9` | BFS unconditionally re-enqueues every neighbour; a device whose topology rule never fired (`coach_number` stays `None`) is re-enqueued forever | Only re-enqueue if `to_device.coach_number is not None`. |
| 11 | `westermo.py` `set_firmware_version` | `obn update f ap` reports **success without verifying activation** — APs stuck on old firmware recorded as updated | Reads only the SNMP SET echo of `rpcFwFlash` (always `2`), declares success the instant the flash is *triggered*, never polls the read-back status | Poll `rpcFwFlash` + uptime up to ~10 min: `True` on reboot/`nop(0)`, `False` on error codes or no-reboot timeout. |

**Family view:** Bugs 2/3/4/7/8 are all "SNMP returned a `None`/missing thing during a device's
reboot window" — a unified `_snmp_get_with_retry()` returning a sentinel would collapse the whole
class, but the surgical per-site guards are what's deployed. Bug 10 is the **only hang** (all others
crash cleanly); it's the highest-priority fix. Bugs 5 and 11 are the **silent no-ops** — the most
dangerous because there is no traceback; you only discover them via a follow-up `obn discover`.

# Dependencies between fixes

- **Bug 3 before Bug 9.** Bug 9's diff wraps the `gen_items = list(generator)` line that **Bug 3
  introduces**. Apply Bug 3 first; the lock sits *inside* Bug 3's `try` so the `KeyError` is still caught.
- **Bug 5 needs the TFTP conntrack helper** to actually work end-to-end. Bug 5 fills the ipset with
  the right IPs; the CCU firewall's conntrack helper (a *separate* companion fix, not an OBN bug) is
  what lets those IPs' TFTP data flows arrive. Both must be present for reliable AP firmware batches.
  See [/.kb/components/nomad-connect-obn/tftp-conntrack-helper.md](/.kb/components/nomad-connect-obn/tftp-conntrack-helper.md).

# Grep markers (detection)

The check greps each file for a literal the patch inserts. Expected counts in parentheses.

| # | File | Marker | Expected count |
|---|---|---|---|
| 1 | `.../lib/device/vendor/vdsrail.py` | `default image is now` | ≥1 |
| 2 | `.../lib/device/vendor/vdsrail.py` | `if not result:` | **2** (one per loop; 1 = partial) |
| 3 | `.../lib/device/snmpdevice.py` | `except KeyError:` | ≥1 |
| 4 | `.../lib/report/device.py` | `bool(self.firmware) and not self.firmware.endswith` | ≥1 |
| 5 | `.../cli/update.py` | `Bug 5 fix: pre-populate tftp_allowed ipset` | ≥1 |
| 6 | `.../lib/tree.py` | `neighbour not in this consist` | ≥1 |
| 7 | `.../lib/device/vendor/vdsrail.py` | `if hostname is not None:` | ≥1 |
| 8 | `.../lib/report/device.py` | `bool(self.config) and not self.config.endswith` | ≥1 |
| 9 | `.../lib/device/snmpdevice.py` | `_SNMP_DISPATCH_LOCK` | **2** (def + `with` site) |
| 10 | `.../lib/report/report_dosto_neu.py` | `NDP-PATCH-BUG10-BFS-GUARD` | ≥1 |
| 11 | `.../lib/device/vendor/westermo.py` | `NDP-PATCH-BUG11-FW-VERIFY` | ≥1 |

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not re-burn hours on approaches already disproven on live CCUs.

1. **Do NOT decide patch state from the package version string.** `nd-obn 2.2.23` ships in **at least
   two flavours**: an R&D-upstreamed build (Bugs 1–8 native, 9/10 present under *different* code so
   their markers false-negative, Bug 11 absent) AND a **fully-vanilla 2.2.23** (0/11, no native
   equivalents). Same version, opposite state. Always run `--check`, and when a marker reads 0, read
   the live source (BFS guard, `bool()` guards, the Lock) before concluding "native" vs "absent".
2. **Do NOT run `fix_obn.py` blindly on a build that already has native fixes.** On the upstreamed
   2.2.23, Bugs 1–8 live at *new* `lib/` paths and are already correct; the canonical script may
   report `PATTERN NOT FOUND` or, worse, double-touch a file. Grep first; only apply the scripts where
   `--check` shows a genuine 0 and the live source confirms the fix is truly absent. On 2.2.23 the one
   patch that always applies cleanly and is always needed is **Bug 11**.
3. **Do NOT assume "Bugs 1–10 native" is a safe blanket.** Bug 6 (`create_tree` cross-consist guard)
   was found **absent** on an upstreamed 2.2.23 CCU and crashed `obn update c` on a coupled train.
   Re-verify Bug 6 per-CCU on any coupled consist before trusting `obn update`.
4. **Do NOT trust the `dosto-state-inventory` skill's `obn_patches_count`.** It uses stale grep
   strings and reports Bugs 2/3/5/7 as *absent* on fully-patched trains (e.g. it read 3/8 or 4/8 where
   the canonical check found all present). For patch state, `dosto-obn-patches --check` is authoritative.
5. **Do NOT trust a fleet-status row that says "OBN persisted".** That is a *point-in-time* claim —
   it means "persisted at the bug count that existed when the chroot promote ran." The suite grew
   8 → 9 → 10 → 11 over time, so any train promoted before a bug existed is silently missing it
   (e.g. a "10/10 persisted" row read live as 9/11). Re-run `--check` live before believing it.
6. **Do NOT patch only one of Bug 2's two sites.** The firmware loop and the config loop each have
   the crash; count must be 2. A count of 1 = the other crash mode is still latent.
7. **Do NOT partially patch and proceed.** Applying *some* fixes leaves crash/hang modes open, so a
   run dies mid-way and writes partial state to the consist. Vanilla-until-11/11 is safer than 6/11.
8. **Do NOT run `obn report` with Bug 10 missing on a not-fully-online consist.** It will pin a core
   at 100% and leak RAM until OOM-killed; `Ctrl-C` is too slow — recovery needs `kill -9`. Confirm
   Bug 10 present *before* any `obn report` when a device may be offline.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- **Engine path:** `/usr/share/obn/…`. On older builds the modules were flat at `/usr/share/obn/*.py`;
  on `nd-obn 2.2.23` they moved under `lib/…` (grep the `lib/` paths — old-path greps and
  `fix_obn.py`'s old anchors won't match the new layout).
- **Fix scripts:** `scripts/fix_obn.py` (Bugs 1–7 canonical), `fix_obn_bugs67.py` (Bug 6/7 partial-state
  fallback), `fix_bug1_regex.py` (Bug 1 partial-state variant), `fix_obn_bug8.py`, `fix_obn_bug9_pysnmp_thread_safety.py`,
  `fix_obn_bug10_report_dosto_neu_bfs.py`, `fix_obn_bug11_westermo_fw_verify.py`.
- **Upstream ticket:** **TRIAG-8585** (Jira, assignee Julia Frick) — covers 11 code bugs (7 files) +
  1 infra fix (the TFTP conntrack helper, which is *section B / infra*, NOT "code bug 11"; code Bug 11
  is the westermo activation verify). Drop-in patch package attached as `findings/TRIAG-8585-patches.zip`.
- **Per-train evidence:** Bugs 1–7 first on 4736-120 (Fzg 148) 2026-05-04. Bug 9 on box1-t16/t18
  2026-05-20. Bug 10 on Fzg 130 (box1-t47) 2026-05-12 (27 GB RSS), recurred Fzg 191 / Fzg 8. Bug 11 on
  4736-109 (.236 activated, .226-class hang correctly reported) 2026-06-08. Vanilla-2.2.23 on box1-t27
  (Fzg 142) 2026-06-19; upstreamed-2.2.23 on box1-t67 (4734-123) 2026-06-10; Bug 6 absent on box1-t38
  (4734-109) 2026-06-17.
- **Runtime vs persistent:** applying scripts via `btrfs property set / ro false` is a runtime fix that
  a reboot wipes; durable persistence is via the NDSU chroot promote. See
  [/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md](/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md).

# Related

- [Nomad Connect / OBN — discover → report → update workflow](/.kb/components/nomad-connect-obn/discover-report-update.md)
- [Nomad Connect / OBN — NDSU chroot persistence](/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md)
- [Nomad Connect / OBN — TFTP conntrack helper gap](/.kb/components/nomad-connect-obn/tftp-conntrack-helper.md)
- [Nomad Connect / OBN — publish → Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)

# Citations

[1] `rd-handoff/README.md` + `rd-handoff/bug-01..bug-10.md` — per-bug writeups, root cause, patch, evidence.
[2] `.claude/skills/dosto-obn-patches/SKILL.md` — canonical 11-marker check matrix, grep strings, counts.
[3] Memory `project_ndobn_2223_native_fixes.md` — 2.2.23 two-flavour finding; version-string dead end.
[4] Memory `project_state_inventory_marker_false_negative.md` — state-inventory false-negative dead end.
[5] Memory `project_obn_persisted_baseline_drift.md` — "persisted" row is point-in-time, not live.
[6] Memory `project_triag8585_obn_bug11_upstream.md` — TRIAG-8585 scope + numbering trap.
