# R&D Handoff — Two permanent OBN fixes: coupler STP robustness + Fzg-ID identity

**Date:** 2026-06-15
**Author:** Abbas Rizvi (Nomad Digital)
**Source evidence:** 2026-06-12 coupled-train test (4736-110 Fzg 138 + 4736-119 Fzg 147), Stadler FW X5 capture, live CCU reads 2026-06-15 (box1-t23, box1-t12). See `findings/coupling_test_4736-110_119_2026-06-12/`.
**Status:** read-only analysis. No commits/pushes made. This doc defines the merge requests.

---

## TL;DR

Two independent, permanent fixes, spanning 3 GitLab repos on `git-nc.nomadrail.com`:

1. **Coupler STP robustness** — coupler port-cost overflows 2^27 → fleet-wide RSTP topology-change storm; and max-age/forward-delay are never set (defaults too small for coupled diameter). Template-only fix.
2. **Fzg-ID identity** — the box number (`trainid_21net`) is fed where the Fzg number is needed; a wrong `128 + train_id` offset compounds it. This is the root cause of the recurring vlan7 hand-patching and misimaged switch hostnames. Fix spans the Puppet env repo + the OBN template repos.

Both are evidenced and root-caused. Some cross-repo wiring needs R&D confirmation (flagged below) before the Fzg MRs are merge-ready.

---

## Branch model (CRITICAL — confirmed 2026-06-15)

| Repo | Live/target branch | Notes |
|---|---|---|
| `env/environment-dostoneu` | **`migration_mar5`** | NOT `master`. mar5 is 3+ wks ahead; the entire `hieradata/nodes/dostoneu-nv6/` tree exists ONLY on mar5. **migration_mar5 will merge to master when the mar5 migration completes** — so target mar5 and it flows to master automatically; no separate master backport needed. |
| `onboard/nd-obn-template-dostoneu-nv6` | `master` | Only branch. No mar5 branch. |
| `onboard/nd-obn-template-dostoneu-nv4` | `master` | Only branch. No mar5 branch. |

Asymmetry to keep in mind: env work lands on `migration_mar5`; template work lands on `master`. A given train's config is consistent only if both land — coordinate the rollout.

---

## FIX 1 — Coupler STP robustness

### Root cause (proven)
- Coupler ports (`e0-2` Frontkupplung, + A3 FW port) carry `spanning-tree port-cost {{ (train_id * {1,2}000000) - 1 [+500000] }}`.
- For fleet Fzg IDs this renders e.g. **137999999** (Fzg 138) / **146999999** (Fzg 147) — both exceed **2^27 = 134,217,728** → suspected VDS firmware port-cost field overflow → the two coupler ends never agree on the designated role → continuous proposal/agreement duel → TC + "Flushing all entries" every ~2 s fleet-wide.
- Evidence: setting cost to 20000 live froze the TC counter at the exact second; Stadler X5 capture showed packets to the FW drop ~80% (>100 kpps → ~20 kpps) and FW CPU fall (was >70% on other DT vehicles → ~55%).
- Separately: **max-age / forward-delay are set nowhere** in the templates → every switch runs IEEE defaults (Max-Age 20 / Fwd-Delay 15). Measured radius hit **20 hops** on a 2×(6+6)=36-switch coupling — already at the BPDU horizon. Max-Age 20 is inadequate for double-traction.

### The fix
**Port-cost:** divide the multipliers by 100× (preserves the ×1/×2 split that deterministically blocks one coupler link, the per-train ordering, and the +offset second value; caps worst-case render ~5.1M for Fzg 255 — 26× under 2^27).

**Timers:** add `forward-delay 20` then `max-age 38` (order matters — firmware enforces 2×(FwdDelay−1) ≥ MaxAge, so fwd-delay 20 must precede max-age 38) before `spanning-tree enable` in every switch cfg. Covers all single + double traction (≤36 sw). Triple-traction stays out of scope (needs Stadler L2 termination — see coupling report rec #4).

### MR 1 — `onboard/nd-obn-template-dostoneu-nv6` → `master`
Branch: `fix/coupler-rstp-portcost-and-maxage`

Port-cost (4 files):
| File | Lines | From | To |
|---|---|---|---|
| `nv6-100-A1.cfg` | 38 / 40 | `(train_id*1000000)-1+500000` / `(train_id*1000000)-1` | `(train_id*10000)-1+5000` / `(train_id*10000)-1` |
| `nv6-100-A3.cfg` | 37 / 39 | `(train_id*2000000)-1+500000` / `(train_id*2000000)-1` | `(train_id*20000)-1+5000` / `(train_id*20000)-1` |
| `nv6-600-B1.cfg` | 39 / 41 | `(train_id*2000000)-1+500000` / `(train_id*2000000)-1` | `(train_id*20000)-1+5000` / `(train_id*20000)-1` |
| `nv6-600-B3.cfg` | 39 / 41 | `(train_id*1000000)-1+500000` / `(train_id*1000000)-1` | `(train_id*10000)-1+5000` / `(train_id*10000)-1` |

Timers (all 18 `nv6-*.cfg`): insert before `spanning-tree enable`:
```
spanning-tree forward-delay 20
spanning-tree max-age 38
```

### MR 2 — `onboard/nd-obn-template-dostoneu-nv4` → `master`
Branch: `fix/coupler-rstp-portcost-and-maxage`
Identical defect, identical fix. 4-Teiler couples too (4+4, 4+6). Line numbers (verified 2026-06-15):
| File | Lines |
|---|---|
| `nv4-100-A1.cfg` | 37 / 39 |
| `nv4-100-A3.cfg` | 36 / 38 |
| `nv4-600-B1.cfg` | 38 / 40 |
| `nv4-600-B3.cfg` | 38 / 40 |
Timers: all 12 `nv4-*.cfg` (root switch is **G1** priority 0 / G3 priority 4096).

**Risk:** low — coupling-only behaviour; solo trains unaffected at runtime. MR 1 & MR 2 are independent and shippable now. No cross-repo dependency.

**Open question for VDS (Giorgio):** confirm the exact firmware port-cost field bit-width (is it 27 bits?). Our ×10000/×20000 is safe under any plausible answer (all <6M), so this does not block the MR — but the true ceiling should be documented.

---

## FIX 2 — Fzg-ID identity (ends vlan7 + train_id hand-patching)

### Root cause (proven on box1-t23 / Fzg 138, 2026-06-15)
- `/etc/facter/facts.d/nd.yaml` sets `trainId_21net: 23` — this is the **box number**, not the Fzg (138). It correctly drives the management plane (`10.179.23.x`).
- `/etc/obn/backbone-discovery.yaml` feeds OBN `train_id: 23` (the box number). **Do NOT edit this** — it is the deliberate mar5-migration workaround (CLAUDE.md directive).
- nv6 template line 1 does `{%- set train_id = 128 + train_id -%}` → `128 + 23 = 151` ≠ 138. **This is the misimage generator** (same class as the Fzg 130/140 "168" cases).
- vlan7 is rendered by Puppet (`environment-dostoneu/hieradata/files/nd_redundancy/networks.epp`, ~line 191) from the box fact → wrong octet → wrong vlan7 → engineer patches `ndrd-vlan-vlan7.nmconnection` by hand every time.
- box→Fzg is a **per-train lookup**, not a formula (4734: −100; 4736: +28; 4705: +128; 4706: +88) — so no constant offset can be correct fleet-wide. The fix MUST be per-box data.
- Why Fzg 138 currently works: a human previously overwrote line 1 of all 18 cfgs with the literal `{%- set train_id = 138 -%}` and persisted vlan7 197.2 by hand. Wiped on fresh image / NDSU pull → recurs.

### The fix: one per-box `fzg_id` as the single source of truth, feeding both render paths.

### MR 3 — `env/environment-dostoneu` → **`migration_mar5`**
Branch: `fix/fzg-id-per-box-vlan7`

(a) Add per-box keys to each node file `hieradata/nodes/dostoneu-nv6/box1-tNN.dostoneu-nv6.21net.com.yaml`:
```yaml
fzg_id: <Fzg>
obn::train_id: <Fzg>
```
Examples (from fleet-status): box1-t23 → 138 (**file must be CREATED — absent today**); box1-t12 → 147 (file exists, add 2 lines). Repeat for every box; Fzg per box from the fleet table / IPA PDFs. One-time data-entry pass.

(b) `hieradata/files/nd_redundancy/networks.epp` vlan7 block — switch from the `trainid_21net` fact to `fzg_id`:
```
even Fzg: ipaddress 172.19.<128 + fzg_id/2>.2
odd  Fzg: ipaddress 172.19.<128 + (fzg_id-1)/2>.130
```
(Verified against known-good: Fzg 138 → 172.19.197.2 ✅; Fzg 147 → 172.19.201.130 ✅.)

**Do NOT touch `backbone-discovery.yaml`** (mar5 workaround). Note in MR.

**Risk: HIGH** — touches train identity for every box on the next Puppet run. Needs staged rollout + careful review.

### MR 4 — `onboard/nd-obn-template-dostoneu-nv6` → `master`
Branch: `fix/fzg-id-drop-128-offset`
All 18 `nv6-*.cfg` line 1: `{%- set train_id = 128 + train_id -%}` → use the supplied Fzg directly (drop the `128 +` offset), consuming `obn::train_id` from MR 3.

**GATED:** merge ONLY after MR 3 lands `obn::train_id` AND after R&D confirms OBN consumes `obn::train_id` (see open question 1). If OBN ignores the Puppet value, this MR breaks every train.

### nv4 Fzg note (separate handling — NOT the same as nv6)
nv4 templates have **no `{%- set train_id = … -%}` directive line** (line 1 is `system hostname …`). Per the nv4 commissioning convention, the Form-1 directive `{%- set train_id = <Fzg> -%}` is added manually as line 1. The permanent nv4 fix is to have OBN supply Fzg (via `obn::train_id`) and the template reference it directly, OR bake the directive injection into the package — to be designed once the nv6 mechanism (open question 1) is confirmed. Tracked, not yet specced.

---

## Dependency & merge order

```
MR 1 (nv6 STP)  → onboard/nv6 : master          ✅ independent, ship now
MR 2 (nv4 STP)  → onboard/nv4 : master          ✅ independent, ship now

MR 3 (env Fzg)  → env : migration_mar5          ⚠️ HIGH risk, staged rollout
      └─► MR 4 (nv6 Fzg offset) → onboard/nv6 : master
            ⛔ gated on MR3 + "OBN reads obn::train_id" confirmation
```

---

## Open questions for R&D (block only the Fzg MRs, not the STP MRs)

1. **Does OBN consume `obn::train_id` from Puppet hieradata as its template `train_id`, or only `backbone-discovery.yaml`?** Determines whether MR 4 works as written or needs different wiring. Live OBN currently reads `train_id: 23` from `backbone-discovery.yaml`.
2. **Does `lookup('fzg_id')` work inside the file-served `networks.epp`, or must `fzg_id` be passed as an EPP parameter from the rendering manifest?** A 10-min render-test settles MR 3's exact form.
3. **VDS:** confirm coupler port-cost field bit-width (informational; does not block MR 1/2).

---

## What does NOT change
- `backbone-discovery.yaml` (`train_id: 23`) — deliberate mar5 workaround.
- Per-train runtime fixes are still needed until these MRs land + each train is re-rendered (`obn update c`) / Puppet-run. These templates change nothing on a train until then. This is a fleet rollout, not a one-shot.
