# v9 VDS Consist-Switch Template Change-List — Definitive Plan

**Date:** 2026-06-20 · **Author:** AR + Claude (multi-agent audit, 45 agents, 33/36 findings verified) · **Status:** PLAN — decisions resolved; runtime test gates the git MR.
**Scope:** coupled DOSTO-NEU L2 correctness up to 2×6 (3×6 ruled out — see D1), consistency across `nv6 / nv4 / fv5 / fv6`, template hygiene.
**Repos:** `C:/Users/AbbasRizvi/Documents/nomad-obn-template-{nv6,nv4,fv5,fv6}/src/etc/obn/template/`
**Deploy reality:** template → `.deb` (OBN GitLab) → Puppet → CCU → `obn update c` (leaf-first, reboots each switch). One shot — everything defensible ships in v9.

> **Sequencing:** runtime-validate M1 (cost) then M2 (native) on a coupled pair FIRST (see PLAN_runtime_test_option_a_v9). On PASS, make the git changes below and bump to v9.

---

## Decisions (resolved 2026-06-20)

- **D1 — 3×6 viability: NOT RSTP-viable. ≤2×6 is the supported envelope.** VDS (Giorgio): *"the max number of nodes supported by RSTP is 40, so this network is near to the protocol limits... try max-age 37 or 38."* 2×6 = 36 nodes (under 40, viable); **3×6 = 54 nodes (over the 40-node ceiling — no timer value fixes a node-count limit).** v9 sets max-age 38 for 2×6 and explicitly does NOT claim 3×6. Triple-traction needs a different L2 mechanism (terminate L2 at coupler / route via Stadler FWs) — escalate.
- **D2 — Coupled-root determinism: document only, no template change.** Each train presents a priority-0 root; overall root is MAC-tie-break (stable per pairing). With max-age 38 margin the partition concern is removed, so root position no longer matters operationally. No per-consist `is_lead` variable exists in OBN today; revisit only if it causes a real problem.
- **Timer rollout: shared include (S1).** Hoist the global STP block into one included snippet per fleet so all ~54 switches stay identical and can't drift.

---

## MUST-FIX

### M1 — Flat symmetric coupler port-cost (kills the TC storm)
Replace the `train_id`-dependent `{%- if train_id < 10 %} … {%- endif %}` cost block in all 16 coupler `e0-2` stanzas with:
```
  spanning-tree port-cost 20000
```
Why: two coupled trains have distinct `train_id` → both ends of every coupler link get different costs in all 4 orientations → never-settling designated-role duel → ~2s fleet-wide MAC flush. Flat symmetric value ends it (field-validated 2026-06-12; coupler still blocks correctly because the internal 10G ring at 2000/hop is 10× cheaper). The `+500000`/`train_id<10` branch is dead on nv6/fv5/fv6 (line-1 `128+train_id` remap, verified) but potentially live on nv4 (no remap, verified) — deleting the whole branch is correct for both.

### M2 — Coupler native-VLAN containment (combined form — mandatory)
Change the coupler trunk line in all 16 stanzas to:
```
  switchport mode trunk native vlan 999 prune allow 5,15
```
Why: today native defaults to VLAN 1. End-wagon switches carry `interface vlan1 / ip 192.168.1.X` and **all trains share 192.168.1.0/24** → coupling bridges the switch-management subnet between trains with overlapping IPs. Native 999 (a dead VLAN) drains untagged traffic; VLAN 1 is not in the allow set so it never crosses. KEEP VLAN 5 (engineer directive). NEVER set native alone — that rewrites the trunk and resets the prune set (the trap that once exposed VLAN 100 to the FW).

### M3 — Define VLAN 999 blackhole (ships WITH M2)
Append to each fleet's `vlans.j2` (after line 25):
```
vlan 999 name blackhole-native
```
999 confirmed free in all 4 fleets. M2 without M3 risks a firmware-dependent reject of the native assignment.

### M4 — RSTP timer widening (via shared include, per S1)
No `max-age`/`forward-delay` exists anywhere today (all 4 fleets at firmware defaults 20/15). Measured 2×18 diameter = 31 hops, far end at exactly 20 = on the horizon, zero margin. Set (order mandatory — firmware enforces `2*(FwdDelay-1) ≥ MaxAge`, i.e. `2*19=38 ≥ 38`):
```
spanning-tree forward-delay 20
spanning-tree max-age 38
```
Identical on every switch, all fleets. Covers 2×6 with margin. Does NOT make 3×6 viable (D1).

---

## SHOULD (consistency / hygiene)

- **S1 — Shared STP include.** Put global STP block (enable + M4 timers) in one included snippet per fleet (mirror the `vlans.j2` include pattern), referenced by every switch `.cfg`. Guarantees identical timers across ~54 switches.
- **S2 — Fix `fv5-100-A3.cfg:34` description** `"Frontkupplung A2"` → `"Frontkupplung A3"`.
- **S3 — Comment the `400100` internal-ring tie-break** on B1/B3 `e0-0` (deliberate deterministic internal-ring break; NOT a bug, independent of coupler cost). Document, no value change.
- **S4 — Comment the load-bearing `5,15` coupler set** so a future reviewer doesn't "tidy" it.

## CONSIDER / guardrails (verify NOT broken)
- Coupler `spanning-tree edge off` — confirmed correct on all 16; KEEP (non-edge so RSTP runs proposal/agreement on a newly coupled link).
- Coupler allowed set stays exactly `5,15` after the M2 combined-form rewrite.

## REJECTED (considered, deliberately excluded)
- "Flat 20000 breaks the loop inside a train" — backwards; internal ring is 10× cheaper, coupler stays the break point (test-confirmed).
- `400100` as a hazard — independent of coupler; downgraded to S3 (document).
- Root-determinism as MUST-FIX — no template fix exists today → D2 (document).

---

## Per-fleet file-edit checklist (MR author)

**vlans.j2 (M3) — each repo's own copy, keep identical:** append `vlan 999 name blackhole-native`.

**Per coupler switch — M1 (cost block→`20000`) + M2 (trunk line→native 999) + S-comments:**

| Fleet | A1 (M2 line / M1 block) | A3 | B1 | B3 |
|---|---|---|---|---|
| nv6 | 36 / 37-41 | 35 / 36-40 | 37 / 38-42 (+S3 L24) | 37 / 38-42 (+S3 L24) |
| nv4 | 35 / 36-40 | 34 / 35-39 | 36 / 37-41 (+S3 L23) | 36 / 37-41 (+S3 L23) |
| fv5 | 36 / 37-41 | 35 / 36-40 (+S2 L34) | 37 / 38-42 (+S3 L24) | 37 / 38-42 (+S3 L24) |
| fv6 | 36 / 37-41 | 36 / 37-41 | 37 / 38-42 (+S3 L24) | 38 / 39-43 (+S3 L25) |

**M4 timers:** add `forward-delay 20` + `max-age 38` via shared include (S1), referenced by every switch `.cfg` in all 4 fleets.

**Pre-merge validations:**
- [ ] `grep -rn "train_id \* "` on couplers → **0 hits** (M1 done).
- [ ] `grep -rn "native vlan 999 prune allow 5,15"` → **exactly 16** (M2 done, combined form).
- [ ] naked `switchport mode trunk prune allow 5,15` on couplers → **0** (no prune reset).
- [ ] `grep -rn "vlan 999 name blackhole-native"` → **4** (one per vlans.j2).
- [ ] firmware constraint `2*(20-1)=38 ≥ 38` ✓.
- [ ] bump each `version`; README line `v9 - symmetric coupler cost + native-999 containment + RSTP max-age 38 (2x6 envelope)`.

**3×6 escalation (D1):** v9 release note + customer/Stadler comms must state ≤2×6 RSTP-supported; 3×6 exceeds the 40-node RSTP ceiling (VDS-confirmed) and requires a different inter-consist L2 mechanism.
