---
type: component-knowledge
title: Nomad Connect / OBN — discover → report → update Workflow
description: The canonical OBN operating sequence and why obn report can never be skipped — the discovery.prev.json snapshot and the readonly-devices catch-22.
component: nomad-connect-obn
project: dosto-neu
tags: [obn, discover, report, update, validate, workflow, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

OBN operates on a **snapshot pipeline**, not on live scans. Every mutating or validating command
reads a committed snapshot, not the raw discovery output. Getting the sequence wrong produces
**silent no-ops** — commands that exit 0 having done nothing. The canonical order is:

```
sudo obn discover   →   sudo obn report   →   sudo obn update {c,f} <target>  /  sudo obn validate
```

- **`obn discover`** scans the consist and writes raw results to `/tmp/discovery.json` (the device list).
- **`obn report`** commits that scan into the stable snapshot `discovery.prev.json`, AND runs the rules
  engine (`number_coaches` → `apply_rules`) that assigns each device its coach position and — crucially —
  its **`target`** (the intended firmware/config the device should be at).
- **`obn update` and `obn validate` read `discovery.prev.json`, NOT `discovery.json`.** This is by
  design: `obn report` is the commit step. Skip it and downstream commands see an empty or stale
  snapshot with no `target` set.

> **Portability note.** The `10.179.x` IPs, box hostnames, and per-train dates in the `EXAMPLE` block
> are deployment-specific. The snapshot-pipeline behaviour is generic to the engine.

# Why `obn report` is never optional

Two independent failure modes both trace to a skipped or incomplete `obn report`:

### 1. `obn update c <ip>` — the readonly-devices / `all([])` catch-22

`obn update c` requires each targeted `Device.target` to be set. `target` is populated **only** by the
rules engine during `obn report`. If you skip report (or copy `discovery.json → discovery.prev.json` by
hand as a shortcut), the device list loads but every `target` is `None`:

- `obn update c <ip>` finds no device it can act on. Python's `all([])` on the empty target set is
  `True`, so the guard prints **"Update not supported for readonly devices"** (or a suppressed
  `logger.warning("no devices targeted for update")` with no visible handler) and **exits 0 in ~1 second
  with no TFTP RRQ**. The engineer sees "success" with zero work done.
- `obn validate` shows an **empty table** for the same reason.

**Never trust `obn update c` exit 0.** Verify the switch actually rebooted — a DHCPACK after a gap in
the CCU journal, or `obn discover` showing the new config string — before believing the push landed.

### 2. `obn report` itself can hang (Bug 10)

`obn report` runs `number_coaches()`, whose BFS infinite-loops if any device can't be assigned a coach
position (missing device, duplicate hostname from a misimaged switch). Without the Bug 10 patch this
pins a CPU at 100% and leaks RAM (27 GB+) until OOM-killed. So the prerequisite chain is fragile:

```
obn update c   needs   Device.target
   └─ set by   apply_rules   (rules engine)
        └─ run by   number_coaches   (can HANG without Bug 10)
             └─ during   obn report   (the hard prerequisite)
```

If `obn report` hangs, **do not pile up retries** — each spawns a Python that spins and drives load up
until cellular SSH starts failing. `sudo pkill -9 -f 'obn report'` first, then fix the root cause
(usually a physical/imaging fault — a duplicate or missing switch position — not OBN itself), then retry.

# The workflow, step by step

```bash
# 1. Scan the consist (writes /tmp/discovery.json)
sudo obn discover

# 2. Commit the scan + run the rules engine (writes discovery.prev.json, sets target)
sudo obn report

# 3a. Push firmware, then re-discover, then config (firmware first, always)
sudo obn update f all
sudo obn discover        # re-scan to pick up post-flash state
sudo obn update c all

# 3b. OR validate current state against target
sudo obn validate        # green = at target; empty table = report not run / snapshot empty
```

**Firmware before config.** Config pushes reboot the switch; doing config first then firmware wastes a
reboot cycle and can leave the consist mixed. Re-`discover` between the two so the config pass sees
post-flash firmware strings.

# Ad-hoc device-state view without `obn report`

If you need a quick look at raw device state and don't want to wait for (or risk hanging) `obn report`,
read the raw discovery JSON directly — but understand it has **no `target`** (that's set by report):

```bash
sudo python3 -c "import json; [print(d['ip'], d.get('firmware'), d.get('config')) for d in json.load(open('/tmp/discovery.json'))['devices']]"
```

This is a *view*, not a substitute for `report` — you cannot drive `obn update` from it.

# Proven dead ends — do NOT repeat these

> Approaches tried and disproven on live CCUs.

1. **Do NOT skip `obn report` before `obn update` or `obn validate`.** They read
   `discovery.prev.json` (the report snapshot), not `discovery.json` (raw scan). Skipping it yields a
   silent no-op update ("Update not supported for readonly devices" via `all([]) == True`) and an empty
   `validate` table.
2. **Do NOT `cp discovery.json discovery.prev.json` as a shortcut for `obn report`.** The schema loads
   for the device-list read path, so it *looks* like it worked — but `target` is set by the rules
   engine *during* report, not present in raw discovery. Every device ends up `target: None` and
   `obn update c` silently no-ops. This exact shortcut wasted a session on Fzg 130.
3. **Do NOT read `obn update c` exit 0 as success.** It exits 0 both when it did real work and when it
   found nothing to do. Confirm via a real signal: switch reboot (DHCPACK/journal gap) or a fresh
   `obn discover` showing the new config/firmware string.
4. **Do NOT retry a hanging `obn report` in a loop.** Each retry spawns a spinning Python; they stack,
   load climbs, and the flaky train cellular link drops your SSH. `pkill -9` all of them first.
5. **Do NOT treat a hanging `obn report` as an OBN-only problem.** The trigger is almost always a
   physical/imaging fault — a device that can't be assigned a coach position (missing device, or two
   switches with duplicate hostnames from misimaging). Enumerate switches per position from
   `obn discover`; any position with 0 or 2 entries is the fault to escalate, not something to patch around.
6. **Do NOT trust OBN's "configuration update applied, device rebooting" / "Successful" strings.** OBN
   prints these when the SNMP set is *sent* or the TFTP RRQ *initiated*, not when the change landed.
   Always follow up with `obn validate` or a direct SNMP/discover check.
7. **Do NOT read a short/collapsed backbone table as "all present, small consist."** When
   `number_coaches()` cannot number a switch, `normalise_devices()` **silently deletes it** — a
   discovered, powered, SNMP-reachable switch vanishes from `obn report` / `obn validate` / the NMS
   payload with no truncation signal. Two proven triggers: **(a) a cold-bypassed switch** (one switch
   powered off → the backbone relays through it → the switch that moves into its slot is mis-numbered
   and the walk collapses "downstream," dropping ~8 healthy switches — bench box1-t122: 10 present
   switches shown as 2); **(b) a single lost inter-switch LLDP edge** (e.g. the rear-chain `B3↔B2`
   cable down removes the only entry into the rear numbering walk → 5 healthy rear switches + their APs
   dropped — 4736-119 showed 13/18, healthy 4736-110 showed 18/18). Always **cross-check the report
   count against the expected consist size** (18 for nv6 6-car, 12 for nv4 4-car). This is a monitoring
   false-negative: the dropped switches can never be alarmed on. Do NOT try to "fix" it by inserting a
   DOWN placeholder for the walk to flow through or by bumping the coach counter past the gap — both
   were prototyped and fail (the port rule keys on the arriving switch's own number, so a phantom node
   can't repair the identity error). The correct fix is topology-anchored / validated-hostname numbering
   that **retains every discovered device** (as `UNPLACED`/`DOWN`). Ops-side, `dosto-device-discovery`
   Step 4b already classifies the bypass from the CCU. Detail:
   [drops-on-bypass](/.kb/evidence/obn-numbering-drops-healthy-switches-on-bypass.md),
   [single-edge fragility](/.kb/evidence/obn-numbering-fragile-to-single-edge-loss.md).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- **Snapshot paths:** `/tmp/discovery.json` (raw), `discovery.prev.json` (report snapshot) under the OBN
  working dir on the CCU.
- **The catch-22 was proven** 2026-05-12 on Fzg 130 / box1-t47 (`10.179.47.1`): 5 stuck `obn report`
  processes across sessions (exit 124 on a 60s timeout, zero output), then `obn update c .180` silently
  exited 0 because every device had `target: None`. Root cause was 3 misimaged switches with duplicate
  hostnames (`nv6-{B1,E1,F1}-v5-man` colliding with the real `-v5-130` set) plus 3 missing positions.
  Resolved 2026-05-19 by serially pushing the correct configs so all 18 hostnames became unique.
- **`obn validate` empty-table** confirmed when `consist.yaml` is empty or `obn report` hasn't run —
  not a fault, just an un-committed snapshot.
- Bug 10 (the `obn report` hang) detection/fix:
  [/.kb/components/nomad-connect-obn/bug-suite.md](/.kb/components/nomad-connect-obn/bug-suite.md).

# Related

- [Nomad Connect / OBN — the 11-bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — NDSU chroot persistence](/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)

# Citations

[1] Memory `project_obn_update_target_catch22.md` — silent no-op, `target=None`, prerequisite chain, Fzg 130 resolution.
[2] `.claude/skills/dosto-obn-patches/SKILL.md` — "OBN canonical workflow" note; `obn validate` empty-table; raw JSON view.
[3] `rd-handoff/bug-10-report-dosto-neu-bfs-hang.md` — `number_coaches` hang blocking `obn report`.
[4] `troubleshooting-runbook.md` — discover→update f→discover→update c ordering; "configuration update applied" unreliability.
