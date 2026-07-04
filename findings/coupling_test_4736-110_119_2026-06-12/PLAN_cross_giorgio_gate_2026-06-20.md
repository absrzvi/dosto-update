# Plan — clearing the "Giorgio gate" (VDS deeper tcpdump analysis)

**Date:** 2026-06-20 · **Author:** AR + Claude · **Status:** PLAN ONLY — nothing executed.
**Context:** Giorgio (VDS) answered the F3/max-age questions (see REPORT Addendum 3) but **deferred** the deeper loop-vs-duplication read of the tcpdumps: *"a clearer evaluation should therefore be carried out only after these [config mismatch] issues have been resolved."*

## The gate, stated as a goal

> VDS will not analyse the captures while they could be contaminated by our own config mismatches.
> **Done = every known config mismatch on the coupled fabric is fixed, persisted (template-level, survives `obn update c` + power-cycle), re-verified on a coupled pair, and a fresh clean capture is handed to VDS.**

Success criteria (tick all before re-engaging VDS):
- [ ] Coupler port-cost is **symmetric and identical** on both ends of each coupler link, on both trains, value 20000 — confirmed in `show startup-config`, not just running.
- [ ] Coupler trunks carry `native vlan 999 prune allow 5,15` on all four ports (A1/A3/B1/B3), both trains.
- [ ] Odd-Fzg Stadler FW address `.129` corrected in CLAUDE.md + `08_e2e_probe.sh`; odd-Fzg `FW reach` verdicts re-verified.
- [ ] Degraded sub-10G backbone link (B3-147 / F3-147) investigated and resolved or explained.
- [ ] Fixes are in the **v8 templates** (MR merged), not runtime-only.
- [ ] Re-coupled pair shows: single root, one coupler FWD / one ALTR-BLK, **zero TC churn**, clean RSTP debug log.
- [ ] Fresh tcpdumps captured on the clean fabric → sent to VDS with a 1-line ask.

---

## Root causes confirmed at template level (2026-06-20)

Repo: `nomad-obn-template-nv6`, HEAD `deee326 "Fix exceeding rstp costs"` (2026-04-20).
Path: `src/etc/obn/template/nv6-*.cfg`.

### Why F3 (TC churn) happens — by design, not by accident

The coupler `e0-2` stanza computes port-cost **from `train_id`**:

| Switch | Template formula (train_id ≥ 10) |
|---|---|
| A1, B3 | `(train_id * 1000000) - 1` |
| A3, B1 | `(train_id * 2000000) - 1` |

Two coupled trains have **different `train_id`s**, so the two ends of every coupler link get **different costs by design** (e.g. 138 end vs 147 end). That asymmetry on a P2P link is the suspected driver of the never-settling designated-role duel. VDS confirmed the magnitudes are legal (uint32, ≤200M) — **so the bug is the asymmetry, not overflow.** The `deee326` commit reduced the magnitude (was `train_id * 20000002`) but **kept it train_id-dependent**, so it did not fix the asymmetry.

### Why the native-VLAN / rate-limit mismatches persist

- **No `native vlan 999`** in any nv6 template — coupler stanzas are bare `switchport mode trunk prune allow 5,15`. The June runtime retag is therefore reverted by every `obn update c`.
- **No `rate-limit`** in any nv6 template either — same revert problem.
- These confirm the runtime fixes from `RECIPE_loop_fix_4736-109_110_2026-06-11.md` were never templated → they cannot be relied on for the clean re-capture unless re-applied at runtime immediately before, OR (correct fix) templated.

---

## Work items

### Item 1 — Coupler port-cost: make it symmetric (THE F3 FIX) — template MR
- **Problem:** `train_id`-derived cost → asymmetric across coupled trains → role duel → fleet-wide 2s TC churn.
- **Fix:** replace the `train_id`-dependent formula on all four coupler `e0-2` stanzas (A1/A3/B1/B3) with a **fixed constant the same on every train** (proven value: 20000). A coupler link is P2P between two trains; both ends must agree.
- **Open design Q (decide before MR):** do we still want the four coupler ports to carry *different* costs *within one train* (A1/B3 vs A3/B1) to bias which physical coupler wins? If yes, keep a per-port constant (e.g. 20000 / 40000) but make it **train-independent** so both ends of any link still match. If indifferent, one constant everywhere is simplest (Simplicity First).
- **Where:** `src/etc/obn/template/nv6-{100-A1,100-A3,600-B1,600-B3}.cfg`. Mirror into `-nv4`, `-fv5`, `-fv6` if they share the pattern (check first).
- **Persist/verify:** merge MR → `obn update c` per switch (leaf-first) → `show startup-config` shows the constant → re-couple → confirm both ends equal in `show spanning-tree`.

### Item 2 — Coupler native-VLAN retag — template MR
- **Problem:** no `native vlan 999` in template; runtime retag reverts on `obn update c`. Engineer directive: only VLANs 5+15 may cross the coupler; native-1 cross-talk is not a design feature.
- **Fix:** coupler `e0-2` stanzas → `switchport mode trunk native vlan 999 prune allow 5,15` (combined form — see RECIPE lesson 2; setting native alone resets the prune set). Add `vlan 999 name blackhole-native` to `vlans.j2`.
- **Keep VLAN 5 on the coupler** — do NOT prune it (engineer decision, [[feedback_vlan5_stays_on_frontkupplung]]; the 5↔15 ring was refuted, real fix is Stadler-side).
- **Where:** same four files + `vlans.j2`. Mirror to other fleets.

### Item 3 — (decide) rate-limit broadcast in template — template MR
- **Problem:** `rate-limit broadcast 1M` was runtime-only; reverts on update. VDS confirmed BPDUs are exempt, so it's safe.
- **Decision needed:** is the rate-limit part of the durable design, or just a test-day containment? It only caps the ARP/DHCP flood *symptom*, never the TC churn (Item 1 is the real fix). Recommendation: **include it** as defence-in-depth on coupler `e0-2` + A3 `e1-4`, since it's harmless and BPDU-safe. Confirm with engineer.
- **Where:** four coupler `e0-2` + A3 `e1-4`, all fleets.

### Item 4 — Odd-Fzg Stadler FW address `.129` — docs/scripts (not templates)
- **Problem:** odd-Fzg FW vlan7 host is `.129` (device 1 + 128), not `.1`. CLAUDE.md, skills, and `08_e2e_probe.sh` assume `.1` → false `FW reach` for odd vehicles.
- **Fix:** correct `08_e2e_probe.sh` default + the FW-IP formula in CLAUDE.md Phase 6 / vlan7 section; re-verify every odd-Fzg `FW reach: ✅` in fleet-status.
- **Not gating for VDS** strictly, but it's a known mismatch in the same scope — fix in the same pass so the re-test report is clean.

### Item 5 — Degraded sub-10G backbone link (B3-147 / F3-147) — physical
- **Problem:** B3-147 (root path cost 414100) and F3-147 (418100) each carry one ~200000-cost leg = a ~100 Mbps FE hop where 10G is expected. A degraded inter/intra-coach link on 4736-119.
- **Fix:** identify the link (compare against neighbour costs / `show interface summary` speed on the suspect ports), inspect cable/SFP, log in `cable-issues-register.md`.
- **Why it matters for the gate:** a degraded link is exactly the kind of "config/physical anomaly" Giorgio would point to; clear it before the re-capture.

### Item 6 — C2-147 dead switch — physical (carryover, Stadler)
- From the test: nv6-C2-v8-147 lost power mid-day, cold-bypassed. Not a config mismatch but it perturbs the topology. Confirm it's powered/healthy before the re-test or it re-introduces churn.

---

## Sequencing

```
Phase A — Templates (the durable gate-clearer)
  1. Engineer decisions: Item 1 (one constant vs per-port), Item 3 (rate-limit yes/no)
  2. Author MR on nomad-obn-template-nv6: Items 1, 2, (3) — bump version
  3. Mirror to -nv4 / -fv5 / -fv6 (verify they share the pattern first)
  4. Review + merge (R&D / Davud — he authored deee326)

Phase B — Docs/scripts + physical (parallel with A)
  5. Item 4 — .129 fix in CLAUDE.md + 08_e2e_probe.sh + fleet-status re-verify
  6. Item 5 — locate + fix degraded B3/F3-147 link; cable-issues-register
  7. Item 6 — confirm C2-147 powered/healthy

Phase C — Deploy + verify on a real pair
  8. obn update c (leaf-first) both trains → confirm startup-config carries new costs + native 999
  9. Re-couple 110+119 (or next available pair)
 10. Verify success criteria: single root, one FWD/one BLK, ZERO TC churn in debug log,
     both coupler-link ends show EQUAL cost, native 999 active
 11. Fresh tcpdump capture on the clean fabric (both CCUs, + ask Stadler for X5)

Phase D — Re-engage VDS
 12. Send Giorgio the clean captures + 1-line note: mismatches resolved, here is a
     contamination-free capture; please proceed with the loop-vs-duplication analysis.
     Also close the narrowed open Q: does symmetric cost eliminate the role duel? (we expect yes)
```

## Dependencies / blockers
- **Real coupling window** needed for Phase C (two powered trains, B-to-B). Opportunistic — tie to next planned coupling (Floridsdorf re-test candidate).
- **R&D / Davud** for the template MR review (he owns the cost formula in `deee326`).
- **Engineer decisions** on Item 1 + Item 3 gate the MR — resolve first.
- **Stadler** for Item 6 (C2-147) and X5 capture; the VLAN-15 FW↔FW transit question (separate Stadler gate) is NOT in scope here — this plan only clears the *VDS/RSTP* gate.

## Out of scope (tracked elsewhere)
- VLAN-15 FW↔FW transit / CCTV-ZFR outage root cause → Stadler gate, separate.
- 3-unit multi-traction viability → answered (not RSTP-viable); operational decision for ÖBB.
