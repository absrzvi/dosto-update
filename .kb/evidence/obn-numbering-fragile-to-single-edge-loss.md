---
type: evidence
title: OBN coach-numbering is fragile to a single lost LLDP edge — drops 5 healthy rear switches on a broken intra-coach cable
description: A/B comparison of two live nv6 6-car trains proving that one down inter-switch cable (B3↔B2) removes the sole LLDP entry into the rear numbering chain, so obn report/validate omits 5 healthy switches + 7 APs — with a redundant-path fallback proven a no-op on the healthy train.
project: dosto-neu
tags: [obn, report, number-coaches, lldp, single-edge-fragility, off-expected-wiring, cable-fault, field-validated]
maturity: field-validated
timestamp: 2026-06-25T00:00:00Z
resource: /findings/obn_numbering_repro_4736-119_2026-06-24/PROPOSAL_obn_nv6_numbering_fallback_2026-06-25.md
---

# OBN coach-numbering is fragile to a single lost LLDP edge

## What it proves

OBN's `number_coaches()` numbers the rear coaches (4/5/6) of an nv6 6-car by entering the rear chain
through **one specific LLDP hop, `B3 --e0-1--> B2`**. If that single cable is down, the walk stalls at
B3 and the **entire rear device-2/3 chain (E2, E3, F2, F3, B2) plus their 7 APs is never numbered and
is dropped** from `obn report` / `obn validate` — even though those switches are powered, SNMP-reachable,
and forwarding. This is **fragility to a single missing edge in a physically redundant ring**, not a
missing rule (the rule path exists and is correct).

Proven by an A/B comparison of two live trains, identical schema:

| Train | State | Numbered on primary walk |
|---|---|---|
| **4736-119** (Fzg 147, box1-t12) | B3↔B2 cable down (both ports link-down, clean open — cable register #12) | **13 / 18** (5 dropped) |
| **4736-110** (Fzg 138, box1-t23) | healthy | **18 / 18** |

The safe recovery observation: with B3↔B2 down, the rear switches are **still reachable via other LLDP
SW-SW paths** (the graph stays connected), and each switch's discovery record carries its **own rendered
config string** (`nv6-E2-v8-147`) that encodes its designed position independently of the walk. So a
walk-unreachable switch can still be independently (a) proven reachable and (b) identified — without
guessing from graph shape.

## How it was captured

- Live `obn discover` output pulled from both CCUs (`discovery_live_119.json` = failing fixture,
  `discovery_live_110.json` = healthy no-op fixture).
- Reference implementation `fallback_numbering.py` (PASS 1 = the deployed walk verbatim; PASS 2 = the
  proposed redundant-path fallback) run against both:

  | Train | Primary | Fallback | Unplaced | Shown |
  |---|---|---|---|---|
  | 4736-119 | 13 | 5 | 0 | **18/18** |
  | 4736-110 | 18 | 0 | 0 | **18/18** |

  On 119 the 5 recovered switches match their own hostnames and are flagged `off-expected-wiring`; on
  110 the fallback fires **zero** times — verified no-op on healthy trains.
- `repro_proven.py` additionally records a **disproven** fix: naively adding 4 rear-chain rules numbers
  119 to 18/18 but is the wrong approach — it hardcodes more topology instead of tolerating the gap, and
  is retained precisely to show why "add more rules" is not the fix.

## Evidence

- Raw: [`PROPOSAL_obn_nv6_numbering_fallback_2026-06-25.md`](/findings/obn_numbering_repro_4736-119_2026-06-24/PROPOSAL_obn_nv6_numbering_fallback_2026-06-25.md)
  — the enhancement proposal: why it happens, the primary+fallback design, the mandatory
  `off-expected-wiring` flag propagation to `obn validate` + the NMS payload, and the live A/B proof.
- Raw: [`fallback_numbering.py`](/findings/obn_numbering_repro_4736-119_2026-06-24/fallback_numbering.py)
  (reference impl), [`repro_proven.py`](/findings/obn_numbering_repro_4736-119_2026-06-24/repro_proven.py)
  (13/18 repro + the disproven rule-add), and the two live discovery fixtures
  [`discovery_live_119.json`](/findings/obn_numbering_repro_4736-119_2026-06-24/discovery_live_119.json)
  / [`discovery_live_110.json`](/findings/obn_numbering_repro_4736-119_2026-06-24/discovery_live_110.json).

## So what (dead end / actionable)

- **A short OBN backbone table can mean a single broken cable, not a small/absent-hardware consist.**
  Missing rear-coach switches with everything else present is the signature of a lost rear-chain LLDP
  edge — check the `B3↔B2` (device-3→device-2 rear entry) link before assuming missing hardware.
- **Do NOT "fix" this by adding more hardcoded numbering rules** — proven to work on the one fixture but
  it's the wrong shape (more topology hardcoding); the correct fix is a redundant-path fallback that
  identifies unreachable-but-present switches from their own config string and flags them
  `off-expected-wiring`.
- **The enhancement must surface the fault, not hide it** — the `off-expected-wiring` flag MUST reach
  `obn validate` output and the NMS consist payload, or a fallback-completed consist renders as fully
  healthy while a real cable is down. It is a verified no-op on healthy trains (no regression risk).
- **Separate from the fix:** the underlying cable fault (4736-119, register #12) is real and
  Stadler-side — this makes OBN report it better, it does not remove the need to repair the cable.
- Same class as, and complementary to, the cold-bypass drop (see Related): both stem from
  `number_coaches()` being a bare position-following walk with no expected-topology anchor.

# Related

- [OBN drops healthy switches on cold-bypass (evidence — the identity-shift sibling)](/.kb/evidence/obn-numbering-drops-healthy-switches-on-bypass.md)
- [Nomad Connect / OBN — bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — discover → report → update workflow](/.kb/components/nomad-connect-obn/discover-report-update.md)
- [OBN platform codebase review — improve-not-rewrite (evidence)](/.kb/evidence/obn-platform-review-improve-not-rewrite.md)
