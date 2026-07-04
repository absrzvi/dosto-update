# v9 Switch-Config Deploy Runbook

**Date:** 2026-06-30 · **Author:** AR + Claude · **Status:** EXECUTION runbook (Phase 0 PASSED — runtime validation already done).
**Source of truth for the changes:** [PLAN_v9_switch_config_changelist_2026-06-20.md](PLAN_v9_switch_config_changelist_2026-06-20.md). This runbook is the *how-to-ship*, not the *what* — read the change-list first.
**Repos (all present locally):** `C:/Users/AbbasRizvi/Documents/nomad-obn-template-{nv6,nv4,fv5,fv6}/src/etc/obn/template/`

> **Where we are:** Phase 0 (runtime test on a coupled pair, Option A cost + native-999) is **DONE and PASSED**. This runbook covers Phase 1 → Phase 4: git MR → package → Puppet → `obn update c` → re-verify.

---

## Pipeline at a glance

```
Phase 1  Git MR (4 repos)          ─► GATE A: Davud review (owns the cost formula v0.0.18/19)
Phase 2  Package → .deb → Puppet   ─► GATE B: v9 visible to CCUs from Puppet
Phase 3  obn update c per train    ─► GATE C: per-switch reboot + RSTP converge (leaf-first)
Phase 4  Re-verify coupled pair    ─► clears the Giorgio max-age gate
```

One-shot rule (from the change-list): everything defensible ships in v9 together. Don't split M1/M2/M4 across releases.

---

## Phase 1 — Git MR across the 4 template repos

Work on a branch per repo: `feature/v9-coupled-correctness`. The edits are **anchor-based**, not line-number-based (the change-list line numbers drift by ±2 against the live files — verified 2026-06-30; key off the patterns below instead).

### Per-fleet edits (apply to nv6, nv4, fv5, fv6 — identical intent, per-repo copies)

**M1 — flat symmetric coupler cost.** In each of the 4 coupler files (`*-A1.cfg`, `*-A3.cfg`, `*-B1.cfg`, `*-B3.cfg`), the `e0-2` stanza currently has a two-line `train_id`-derived cost (a `+ 500000` variant and a plain variant, wrapped in a `{%- if train_id < 10 %}`-style branch). **Replace the whole conditional cost block** with a single line:
```
  spanning-tree port-cost 20000
```
Anchor to remove: lines matching `spanning-tree port-cost {{ (train_id * ...`  and their enclosing `{%- if ... -%}` / `{%- endif -%}`.

**M2 — coupler native-VLAN containment.** In the same 4 stanzas, change the coupler trunk line to the **combined form** (never set native alone — that resets the prune set):
```
  switchport mode trunk native vlan 999 prune allow 5,15
```

**M3 — define the blackhole VLAN.** Append to each repo's `vlans.j2`:
```
vlan 999 name blackhole-native
```

**M4 — RSTP timers (order matters: firmware enforces 2×(FwdDelay−1) ≥ MaxAge → 2×19=38 ≥ 38).** Ship via the **S1 shared include** (one STP snippet per fleet, referenced by every `.cfg`, mirroring the `vlans.j2` include pattern):
```
spanning-tree forward-delay 20
spanning-tree max-age 38
```

**S2/S3/S4 (hygiene, same MR):**
- S2 — `fv5-100-A3.cfg`: fix description `"Frontkupplung A2"` → `"Frontkupplung A3"`.
- S3 — comment the `400100` internal-ring tie-break on B1/B3 `e0-0` (deliberate, document only).
- S4 — comment the load-bearing `5,15` coupler allow-set so a future reviewer doesn't "tidy" it.

**Version + README (each repo):** bump `version` → v9; README line:
`v9 - symmetric coupler cost + native-999 containment + RSTP max-age 38 (2x6 envelope)`.

### Pre-merge validations (run from `C:/Users/AbbasRizvi/Documents/`)

```bash
# M1 done: zero train_id-derived costs left on couplers
grep -rn "train_id \*" nomad-obn-template-*/src/etc/obn/template/*-A1.cfg \
  nomad-obn-template-*/src/etc/obn/template/*-A3.cfg \
  nomad-obn-template-*/src/etc/obn/template/*-B1.cfg \
  nomad-obn-template-*/src/etc/obn/template/*-B3.cfg   # expect 0

# M2 done: combined form present exactly 16× (4 couplers × 4 fleets)
grep -rcn "native vlan 999 prune allow 5,15" nomad-obn-template-*/src/etc/obn/template/   # sum = 16

# M2 trap: no naked prune-reset trunk line on couplers
grep -rn "switchport mode trunk prune allow 5,15" nomad-obn-template-*/src/etc/obn/template/*-{A1,A3,B1,B3}.cfg   # expect 0

# M3 done: one blackhole vlan per fleet
grep -rn "vlan 999 name blackhole-native" nomad-obn-template-*/src/etc/obn/template/vlans.j2   # expect 4

# M4 done: timers present (via include)
grep -rn "max-age 38" nomad-obn-template-*/src/etc/obn/template/   # present in all 4 fleets
```

All five must pass before opening the MR.

### GATE A — review
MR → **Davud** (owns the v0.0.18/0.0.19 cost formula being deleted) → merge. Reference the runtime PASS evidence and the change-list in the MR description.

---

## Phase 2 — Package → Puppet

Standard OBN deploy path (template → `.deb` on OBN GitLab → Puppet → CCU). See memory `reference_obn_gitlab_process`.

**GATE B — verify v9 is reachable from a CCU before touching any switch:**
```bash
# on a target CCU:
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
# confirm the v9 package/template is what OBN will render (check installed nd-obn / template version)
sudo obn discover && sudo obn report     # canonical: never skip report
# spot-check a rendered coupler cfg shows port-cost 20000 (not train_id*N)
```

---

## Phase 3 — `obn update c` per train (leaf-first)

**This is a config change, not a fresh commission — use single-train debug runs, NOT `/dosto-orchestrate`.** Per the v9 change-list deploy reality and CLAUDE.md, drive each train with the per-device skill:

```
/dosto-sw-config-update --execute    # leaf-first per OBNTree, single-switch-at-a-time
```

Preconditions per train (don't skip):
- **Fzg-ID template check (`/dosto-fzg-id-check <train#>`) — MANDATORY GATE before `obn update c`.** See "Phase 3a" below — this is the most important precondition and is easy to forget because it's unrelated to the v9 coupler changes.
- OBN patches present (`/dosto-obn-patches --check`) — config push exercises Bugs 2b/7/8.
- `sudo obn discover && sudo obn report` first (report snapshot must be populated, or `obn update c` no-ops).
- TFTP helper not required for config push (that's the firmware-push gap) — but device count must be full (`dosto-device-discovery`) or consist-wide push is unsafe.

### Phase 3a — Fzg-ID re-verify after v9 lands (the easy-to-miss gate)

**Why this matters and is separate from v9:** the v9 MR deliberately does **NOT** touch the hostname `train_id` directive (line 1 of each `*.cfg`). v9 only deletes `train_id` from the *coupler port-cost formula* (M1) — a different use of the same variable. The hostname/port-IP `train_id` is set **per-train, on the CCU**, as a hardcoded Form-1 literal (`{%- set train_id = <Fzg> -%}`) during commissioning, NOT in the shared repo.

**The hazard:** the git repos ship `{%- set train_id = 128 + train_id -%}` on line 1 (confirmed 2026-06-30: nv6, fv5, fv6 all have it; nv4 inlines Form-2). When the **v9 `.deb` / Puppet update rewrites `/etc/obn/template/*.cfg`, it can wipe a previously-hardcoded Form-1 literal and restore this `128 + train_id` formula.** If that formula renders the wrong Fzg, `obn update c all` silently pushes wrong-named configs and wrong switch-port-level IPs to every switch — the **Fzg 133 cascade**.

**So, per train, immediately after v9 lands and BEFORE `obn update c`:**
```
/dosto-fzg-id-check <train#>          # e.g. /dosto-fzg-id-check 4736-110
```
- Verdict `all_match` → proceed to the config push.
- Verdict `broken_formula` / `hardcoded_wrong` / `inconsistent` → run the printed in-chroot recipe (Form 1, hardcoded to the train's Fzg) + `safe_reboot`, THEN re-check `all_match`, THEN push.
- This pairs naturally with `/dosto-obn-patches --persist` if patches were also wiped — fold Fzg-ID + patches + vlan7 into one chroot promote (handoff lesson 1).

> Decoupled trains (currently only Fzg 133 / box1-t1) use Form 2 via `--decoupled` — don't auto-rewrite those to Form 1.

**GATE C — per switch:** config push **always reboots** the switch (that's how OBN persists running→startup). If a switch doesn't reboot within 60s of the TFTP RRQ, the push didn't take — hard fail, stop, investigate. Verify via SNMP through the reboot window + RSTP convergence from a neighbour (the skill does this).

**Rollout order across the fleet:** start with the **coupling-test reference pair** (4736-110 / box1-t23 and 4736-119 / box1-t12) since they're already characterised and you can immediately re-verify coupled behaviour. Then proceed train-by-train. v9 is a 2×6 envelope — single trains take it cleanly; the coupler changes only matter when two are joined.

---

## Phase 4 — Re-verify on a coupled pair (clears the Giorgio gate)

Re-run the Phase 0 success criteria on a v9-deployed coupled pair (now from the *template*, not a runtime hand-edit):
- All 4 coupler ports both trains read `port-cost 20000`, both ends of each link **equal**.
- Single root, one coupler link FWD, twin ALTR/BLK.
- **Zero TC churn** over ≥10 min with `system logging debug rstp,coupled`.
- Native VLAN 999 on couplers; VLAN 1 never crosses; VLAN 5 still carried.
- max-age 38 in effect; coupler CRC/carrier-false stay 0.

Clean capture → attach to the VDS/Giorgio thread → that closes the max-age recommendation gate.

---

## Guard-rails (carried from the plans + field lessons)

- **One command per switch SSH session** — CLI rejects `;` chaining.
- **Never set coupler `native` alone** — combined form only (M2), or the prune set resets and VLAN 100 can leak to the FW (RECIPE lesson 2).
- **v9 is ≤2×6 only.** 3×6 = 54 nodes > RSTP 40-node ceiling — separate routed-boundary workstream (D1 / TT-1). v9 release note + Stadler/ÖBB comms must state this explicitly.
- **Switch IPs rotate on 2-min DHCP leases** — always `sudo dhcp-lease-list`, never reuse IPs.
- **`obn update c` from the OLD package reverts runtime edits** — that's why the durable path is the MR, not a hand-edit. Don't leave trains half-on-v9-runtime.
- **`train_id` only in `/etc/obn/template/nv6-*.cfg`** — M1 deletes the train_id *cost* usage on couplers, but train_id stays as the hostname/Fzg source. Don't over-delete.

---

## Quick status checklist (tick as you go)

- [ ] Phase 0 runtime test PASSED (done — 2026-06-30 confirmed)
- [ ] Phase 1: branches cut in all 4 repos; M1/M2/M3/M4 + S2/S3/S4 applied; 5 pre-merge greps pass; version+README bumped
- [ ] GATE A: Davud review → merged
- [ ] Phase 2: .deb built, Puppet updated; GATE B: CCU renders port-cost 20000
- [ ] Phase 3a: per train, `/dosto-fzg-id-check` → `all_match` (re-hardcode Form-1 if v9 deploy wiped it) BEFORE the config push
- [ ] Phase 3: reference pair (110/119) pushed leaf-first; GATE C passed each switch; then fleet train-by-train
- [ ] Phase 4: coupled re-verify clean; Giorgio gate cleared; VDS comms sent
