---
type: evidence
title: Two permanent OBN fixes root-caused — coupler STP robustness + Fzg-ID identity (ends vlan7 hand-patching)
description: Live-CCU analysis defining four merge requests across three repos — divide coupler port-cost multipliers 100× and add max-age/forward-delay timers to stop the coupled TC storm; and make one per-box fzg_id the single source of truth feeding both the vlan7 render and the switch-hostname template to end recurring hand-patching.
project: dosto-neu
tags: [obn, coupler, rstp, port-cost, max-age, fzg-id, vlan7, train-id, puppet, templates, field-validated]
maturity: field-validated
timestamp: 2026-06-15T00:00:00Z
resource: /findings/RD_obn_stp_and_fzg_id_permanent_fix_2026-06-15.md
---

# Two permanent OBN fixes — coupler STP robustness + Fzg-ID identity

## What it proves

Two independent, evidenced root causes and their template/Puppet fixes, spanning 3 GitLab repos:

**1. Coupler STP robustness.** Coupler ports (`e0-2` Frontkupplung + the A3 FW port) render
`spanning-tree port-cost` from `train_id * {1,2}000000`, which for fleet Fzg IDs produces values like
`137999999` / `146999999`. Combined with the two coupler ends carrying **different** (asymmetric)
train_id-derived costs, the two ends never agree on the designated role → a continuous
proposal/agreement duel → a TC + "Flushing all entries" storm every ~2 s fleet-wide when coupled.
Separately, **max-age / forward-delay are set nowhere** in the templates, so every switch runs IEEE
defaults (Max-Age 20 / Fwd-Delay 15) — inadequate for a coupled 2×6 = 36-switch diameter that measured
**20 hops** (right at the BPDU horizon). *(Note: the June "port-cost overflows 2^27" hypothesis was
later **refuted** by VDS — the field is uint32; the true driver is the **asymmetry**, not the magnitude
— see the coupled-TC-storm evidence doc. The 100×-divide fix is still correct because it restores a sane
symmetric-shaped cost with the deterministic ×1/×2 split preserved.)*

**2. Fzg-ID identity.** The **box number** (`trainId_21net` / `train_id: 23` from
`backbone-discovery.yaml`) is fed where the **Fzg** number (138) is needed, compounded by an nv6 template
line-1 `{%- set train_id = 128 + train_id -%}` that renders `128 + 23 = 151 ≠ 138`. This is the root
cause of both the recurring **vlan7 hand-patching** (Puppet's `networks.epp` renders vlan7 from the box
fact → wrong octet) and **misimaged switch hostnames**. box→Fzg is a **per-train lookup, not a formula**
(4734: −100; 4736: +28; 4705: +128; 4706: +88), so **no constant offset can be correct fleet-wide** — the
fix must be per-box data. Proven on box1-t23 (Fzg 138): the train "works" only because a human previously
overwrote line 1 of all 18 cfgs with the literal `{%- set train_id = 138 -%}` and hand-set vlan7 — both
**wiped on a fresh image / NDSU pull**, which is why it recurs.

## How it was captured

- Evidence base: the 2026-06-12 coupled-train test (4736-110 Fzg 138 + 4736-119 Fzg 147) + Stadler FW X5
  capture, plus live read-only CCU reads 2026-06-15 on box1-t23 and box1-t12.
- STP storm quantified from the switch event log (the `show spanning-tree` poll is too slow for the
  sub-2s flap): setting cost to `20000` live **froze the TC counter at the exact second**; the Stadler X5
  capture showed packets to the FW drop ~80% (>100 kpps → ~20 kpps) and FW CPU fall (>70% → ~55%).
- Fzg-ID root cause traced by reading the live render chain on box1-t23: `/etc/facter/facts.d/nd.yaml`
  (`trainId_21net: 23`), `/etc/obn/backbone-discovery.yaml` (`train_id: 23`), nv6 template line 1
  (`128 + 23 = 151`), and Puppet `hieradata/files/nd_redundancy/networks.epp` (vlan7 from the box fact).
  The proposed `fzg_id` vlan7 formula was verified against known-good values: Fzg 138 → 172.19.197.2,
  Fzg 147 → 172.19.201.130.
- Read-only analysis only — **no commits/pushes made**; the doc defines the MRs.

## Evidence

- Raw: [`RD_obn_stp_and_fzg_id_permanent_fix_2026-06-15.md`](/findings/RD_obn_stp_and_fzg_id_permanent_fix_2026-06-15.md)
  — the R&D handoff: branch model (env work → `migration_mar5`, template work → `master`), the exact
  per-file/per-line port-cost + timer edits (MR 1 nv6, MR 2 nv4), the per-box `fzg_id` + `obn::train_id`
  data + `networks.epp` vlan7 rewrite (MR 3), the drop-`128+` template change (MR 4, **gated**), the
  dependency/merge order, and the 3 open questions for R&D.
- Source evidence folder: [`findings/coupling_test_4736-110_119_2026-06-12/`](/findings/coupling_test_4736-110_119_2026-06-12/).

## So what (dead end / actionable)

- **Coupler cost fix = restore symmetry, not chase a magnitude bound.** Divide the multipliers 100×
  (`×10000`/`×20000`, keeping the ×1/×2 split that deterministically blocks one coupler link); add
  `forward-delay 20` **then** `max-age 38` (order matters — firmware enforces `2×(FwdDelay−1) ≥ MaxAge`)
  before `spanning-tree enable` in every cfg. MR 1 (nv6) and MR 2 (nv4) are **independent, low-risk, and
  shippable now**. Triple-traction (≥3×6, >36 switches) is out of scope — needs Stadler L2 termination.
- **Do NOT edit `backbone-discovery.yaml`** (`train_id: 23`) — it is the deliberate mar5-migration
  workaround; the fix goes via a new per-box `fzg_id`, not by "correcting" the box number in that file.
- **The Fzg-ID fix is per-box DATA, not a formula** — one `fzg_id` key per box node file feeding both the
  vlan7 render and the switch-hostname template. **Risk: HIGH** (touches train identity on the next Puppet
  run) → staged rollout.
- **MR 4 (drop the `128+` offset in nv6 templates) is GATED** — merge only after MR 3 lands
  `obn::train_id` AND R&D confirms OBN actually consumes `obn::train_id` (open question 1). If OBN ignores
  the Puppet value, MR 4 breaks every train.
- **These templates change nothing on a train until re-rendered** (`obn update c`) / Puppet-run — a fleet
  rollout, not a one-shot. Per-train runtime vlan7/train_id hand-fixes are still needed until then.

# Related

- [Coupled 2×6 RSTP TC-storm — captured & fixed (evidence; the overflow-refuted, symmetry-is-the-fix update)](/.kb/evidence/coupled-2x6-tc-storm-captured-and-fixed.md)
- [Coupled-train RSTP TC-storm (topic)](/.kb/topics/coupled-rstp-tc-storm.md)
- [Fzg-ID two-namespaces (topic — box-id vs Fzg, the vlan7/hostname render split)](/.kb/topics/fzg-id-two-namespaces.md)
- [vlan7 addressing (topic)](/.kb/topics/vlan7-addressing.md)
- [Nomad Connect / OBN — publish → Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)
