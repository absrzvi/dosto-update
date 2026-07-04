# Three related coach-numbering features — how the June-24 fallback, the July-4 bypass PoC, and RD-12057 relate

**Date:** 2026-07-04
**Context:** all three touch `DostoNeuReport.number_coaches()` (or its generic cousin). This maps them so we don't ship overlapping/conflicting versions.

---

## The three

| # | Name | Where | Date | What it solves |
|---|---|---|---|---|
| A | **Numbering FALLBACK (redundant-path)** | `findings/obn_numbering_repro_4736-119_2026-06-24/fallback_numbering.py` + `PROPOSAL_...2026-06-25.md` | 2026-06-24/25 | A switch the hardcoded walk can't reach **on its expected wiring** — but that IS reachable via a **redundant LLDP SW-SW path** — is recovered using its own config-string identity, flagged `off-expected-wiring`, instead of being dropped. Surfaced on 4736-119 (a broken B3↔B2 cable stalled the rear-chain walk, dropping 5 switches). |
| B | **Bypass → DOWN/UNPLACED PoC** | `findings/report_dosto_neu_PATCHED_2026-07-04.py` + `RD_obn_coach_numbering_bypass_downstate_2026-07-04.md` | 2026-07-04 | Topology-anchored (validated-hostname) numbering + never-drop-discovered (`UNPLACED`) + emit `DOWN` for a **cold-bypassed/absent** switch. Surfaced on bench (A1/B3 bypassed) and 4736-109 (E2 bypass, C3 unmanaged). |
| C | **RD-12057 CCU2 failover** | `onboard/obn` master (`8e0236b`), `lib/context.py::CCUContext` | 2026-02 (merged) | OBN run from the **alternate CCU** numbers from that CCU's real coach, via `box_coach_numbers` map. TGVM-validated; not wired into the DOSTO report. |

## What they have in common

All three are about **making `number_coaches` robust when reality diverges from the hardcoded "primary path from CCU1" assumption.** They attack different divergences:

- **A** — the *expected wiring* is broken but an *alternate path* exists (single-link fault → use the redundant path).
- **B** — a switch on the path is *absent/bypassed* (identity-shift → anchor by validated hostname, mark DOWN).
- **C** — OBN is running from a *different CCU* (wrong start anchor → use CCUContext).

A and B are **the same family** (recover/repair the switch-side walk); C is the **anchor** (where the walk starts).

## A vs B — near-duplicates that must be merged, not both shipped

A (June fallback) and B (July bypass PoC) overlap heavily and were written **8 days apart for the same subsystem**:

| | A — fallback | B — bypass PoC |
|---|---|---|
| Trigger | broken *cable* (link down, switch fine) → walk stalls | *bypassed/absent* switch → walk mislabels + dead-ends |
| Recovery | 2nd pass: redundant LLDP-graph reachability + **config-string identity** | topology-anchored **validated-hostname** numbering + completeness gate |
| Dropped-switch fix | recovers as `off-expected-wiring` | retains as `UNPLACED`; absent → `DOWN` |
| Identity source | switch's own config string, flagged if graph disagrees | hostname claim, **validated against expected adjacency** (misimage-safe) |
| Shared idea | *don't drop a discovered switch; identify it from its self-reported name; flag the wiring fault* | same |

**They are two iterations of one idea.** B is the strictly more advanced version — it adds: validated-hostname anchoring (misimage-safe, where A's raw config-trust is weaker), a DHCP-lease completeness gate (no false DOWN on under-scan), explicit DOWN vs UNKNOWN vs UNPLACED states, and the NMS-consumption split (§7d) A never addressed. **B subsumes A's capability** — A's "redundant-path reachable → recover by identity" is exactly B's `UNPLACED`-retention + anchoring, done more safely.

**BUT A carries one idea B should absorb:** A's framing is *"the expected wiring is down but a redundant path exists → place the switch, flag `off-expected-wiring`."* B currently treats a switch it can't anchor as `UNPLACED` (console-only). For the **single-broken-cable** case (A's 4736-119 scenario) that's a regression vs A — the switch IS identifiable (valid hostname, reciprocal-clean redundant path) and should be **placed with an off-expected-wiring flag**, not just parked UNPLACED. So the merged version should: anchor by validated hostname (B), and when a switch is anchorable but its *expected inter-coach edge* is missing while a redundant path carries it, **place it + flag off-expected-wiring** (A's contribution) rather than UNPLACED.

## Recommendation — one MR, three ideas folded

The nd-obn MR for DOSTO coach-numbering should be **B (bypass PoC) as the base**, plus:
1. **From A:** the `off-expected-wiring` placement for switches that are anchorable + redundant-path-reachable but off their expected inter-coach edge (single-cable-fault case) — don't UNPLACED a switch you can actually identify and reach.
2. **From C (RD-12057):** replace the hardcoded `ccu1_coach` anchor with `CCUContext` so it's CCU2-correct (see `coach_numbering_ccucontext_integration_2026-07-04.md`).

Net: **anchor** correct on either CCU (C), **number** correct past a bypass (B), **recover+flag** correct under a single-cable fault (A). All three divergences handled, one algorithm, one MR. A and B do NOT both ship — A folds into B.

## Cross-refs
- A: `findings/obn_numbering_repro_4736-119_2026-06-24/` (fallback_numbering.py, PROPOSAL, live discovery_119/110 json)
- B: `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`, `report_dosto_neu_PATCHED_2026-07-04.py`
- C: `findings/coach_numbering_ccucontext_integration_2026-07-04.md`; nd-obn `8e0236b`
- Field cases: 4736-119 (A / broken B3↔B2 cable, reg #12), bench box1-t122 + 4736-109 (B / bypass)
