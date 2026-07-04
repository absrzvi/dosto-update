# OBN enhancement proposal — coach-numbering fallback for redundant-path-reachable switches

**Author:** Abbas Rizvi
**Date:** 2026-06-25
**Component:** `nd-obn` — `lib/report/report_dosto_neu.py` (`DostoNeuReport.number_coaches()`)
**Type:** Robustness enhancement (not a bug fix — the existing algorithm is correct for healthy wiring)
**Surfaced on:** 4736-119 (Fzg 147), box1-t12; compared against healthy 4736-110 (Fzg 138), box1-t23

---

## Summary

`obn validate` / `obn report` on 4736-119 omitted 5 of 18 backbone switches (E2, E3, F2, F3, B2)
and their 7 APs, reporting them under `couldn't assign coach number`. The switches are powered,
reachable, and forwarding traffic. Root cause is a single broken intra-coach-6 cable
(B3 e0-1 ↔ B2 e0-0) that removes the one LLDP edge `number_coaches()` uses to enter the rear-coach
numbering walk. An identical healthy train (4736-110) numbers all 18 correctly.

The hardcoded topology walk is **correct** and should stay authoritative. We propose adding a
**fallback pass**: when a switch cannot be reached on its expected wiring but is still reachable via
some redundant LLDP path and self-reports a valid identity, place it in the inventory with an
explicit "off expected wiring" flag rather than dropping it.

This makes the inventory complete under single-link faults while *surfacing* the fault more clearly
than today. It is a verified no-op on healthy trains.

---

## The ask (1–2 lines)

Add a second pass to `number_coaches()` that recovers redundant-path-reachable switches using their
own rendered config string for identity, flagged as `off-expected-wiring`. Propagate the flag to
`obn validate` output and the NMS consist payload. Reference implementation and live proof attached.

---

## Why it happens

`number_coaches()` derives each switch's (coach, device) by walking LLDP neighbours with a table of
hardcoded `(from-device, from-coach, port) -> (to-device, to-coach)` rules. On a 6-car the rear
coaches (4/5/6) are numbered by entering at the **rear** of the train via the chain:

```
B1 --e0-0--> B3 --e0-1--> B2 --e0-1--> F3 --...--> F2 --...--> E3 --...--> E2
```

The `B3 --e0-1--> B2` hop is the **only** entry into that rear chain. On 4736-119 the B3↔B2 cable is
down (both ports link-down, no LLDP, clean open — confirmed by port bounce, see cable register #12),
so the walk stalls at B3 and the entire rear device-2/3 chain (E2, E3, F2, F3, B2) is never numbered.
4736-110, with an intact B3↔B2 link, numbers all 18.

This is **not** a missing rule (the rule path exists and is correct); it is **fragility to a single
missing edge** in a topology that is physically a redundant ring.

---

## Key observation that makes the fallback safe

With the B3↔B2 cable down, the rear switches are still reachable via the LLDP SW-SW graph — the graph
remains fully connected (e.g. E2 is one hop from D1; B2 is one hop from F3). And every switch's
discovery record carries its **own rendered config string** (`nv6-E2-v8-147`), which encodes its
designed position independently of the walk. So a switch the walk can't reach can still be (a) proven
present/reachable and (b) identified — without guessing from graph shape.

---

## Proposed design (primary + fallback)

```
PASS 1 (unchanged): run number_coaches() exactly as today          -> authoritative
PASS 2 (new): for each switch still unnumbered after PASS 1:
   - reachable via ANY LLDP SW-SW path from the numbered set?
       no  -> leave unplaced; report as missing/dead (as today)
       yes -> parse identity from the switch's own config string
                parse ok  -> place at that (coach, device), flag = "off-expected-wiring"
                parse fail -> leave unplaced; report as today
```

Design notes:
- **Primary stays authoritative.** A switch on its expected wiring is numbered the normal way, no flag.
- **Fallback fires only for the gap**, and only when reachability + identity are both independently
  confirmed.
- **Identity from self-reported config, not graph inference** — robust when the graph is ambiguous.
  Caveat: a mis-imaged switch can carry a wrong config; PASS 2 should flag any config/graph
  disagreement rather than silently trust either (mis-image is a known fleet condition).
- **The fault is surfaced, not hidden.** The `off-expected-wiring` flag is a *better* fault signal
  than today's vague "couldn't assign coach number" — it says the device is fine but its wiring isn't.

---

## Flag-propagation requirement (important)

The enhancement must not trade a loud-but-vague failure for a silent-but-wrong success. The
`off-expected-wiring` flag MUST propagate to:
1. `obn validate` switch-overview output (a visible marker per affected row + a summary warning line).
2. The NMS consist payload (`create_nms_report` / `publish_consist_to_mqtt`) so the dashboard does not
   render a fallback-completed consist as fully healthy.

Acceptance: on 4736-119 (current state) `obn validate` shows 18/18 switches WITH 5 rows flagged and a
warning naming the suspected wiring gap; once the B3↔B2 cable is repaired, all flags clear and all 18
number via the primary path.

---

## Proof on real data (live, 2026-06-25)

Reference implementation `fallback_numbering.py` run against live `obn discover` output from both
trains:

| Train | State | Primary | Fallback | Unplaced | Shown |
|---|---|---|---|---|---|
| 4736-119 (Fzg 147) | B3↔B2 cable down | 13 | 5 | 0 | **18/18** |
| 4736-110 (Fzg 138) | healthy | 18 | 0 | 0 | **18/18** |

- On 119 the 5 recovered switches (E2/E3/F2/F3/B2) are identified correctly (match their hostnames)
  and flagged `off-expected-wiring`.
- On 110 the fallback fires **zero** times — the change is a **no-op on healthy trains** (no
  regression risk to the normal case).

---

## Attachments (this folder)

- `fallback_numbering.py` — reference implementation (PASS 1 verbatim + PASS 2 fallback). Run:
  `python fallback_numbering.py <discovery.json>`.
- `repro_proven.py` — minimal repro of the primary-only behaviour (13/18 vs an over-broad rule-add
  experiment that 110 disproved; retained to show why the naive "add more rules" fix is wrong).
- `discovery_live_119.json` — live discovery from box1-t12 with B3↔B2 down (the failing fixture).
- `discovery_live_110.json` — live discovery from box1-t23, healthy (the no-op fixture).
- `report_dosto_neu.py`, `report_base.py` — the exact deployed source the repro transcribes.

---

## Scope / not in scope

- **In scope:** graceful degradation of the inventory under single-LLDP-edge loss on nv6 6-car. The
  same pattern applies to nv4 4-car and should be added there too (not yet reproduced).
- **Not in scope / separate action:** the underlying cable fault on 4736-119 is real and Stadler-side
  (cable register #12). This enhancement makes OBN report it better; it does not remove the need to
  fix the cable.
