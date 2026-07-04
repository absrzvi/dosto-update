# Bespoke report classes vs the GenericReport safety bar (origin/master v2.3.12)

12 bespoke report classes assessed in parallel against GenericReport (the safe reference), each verified with
exact file:line evidence. Register: `bespoke_vs_generic_register.json`.

**Corrects an earlier grep-based guess:** a shallow grep suggested ~8 classes were loop-vulnerable. The
careful per-class read shows most "unconditional-looking" enqueues are in fact gated by a coach_number
assignment 1–2 lines earlier in the same branch. Only **DOSTO is genuinely loop-vulnerable.**

## Result

| Report class | Loop-safe? | None-guarding | vs Generic | Worst report-layer sev |
|---|---|---|---|---|
| **DostoNeu** | **VULNERABLE** (unconditional re-enqueue :158) | partial | **below bar** | **HIGH** (infinite loop / OOM) |
| **VIA** | safe | **UNGUARDED** — `to_device.type` at :251 with no None check; unbound `box_device` at :144 | **below bar** | **HIGH** (crash/abort) |
| **ACE** | safe | partial — `master_switch` deref at :73 unguarded (+ a port-10 precedence quirk :123) | below bar | MEDIUM |
| **Dani** | safe | partial | below bar | LOW |
| **Luna** | safe | partial | below bar | LOW |
| TGV | safe | guarded | matches_or_better | none |
| TGV2020 | safe | guarded | matches_or_better | none |
| Queensland | safe | guarded | matches_or_better | low |
| CCJPA-WD1 | safe | guarded | matches_or_better | none |
| CCJPA-WD2 | safe | guarded | matches_or_better | low |
| DSB / OTU | safe | partial | matches_or_better | low |
| Daisy-Cybox | safe | guarded | matches_or_better | low |

## Read
- **5 of 12 bespoke classes are below the Generic bar** (DOSTO, VIA, ACE, Dani, Luna); **2 carry HIGH
  report-layer defects** (DOSTO loop; VIA unguarded deref + unbound var).
- **7 of 12 match or beat Generic** (TGV, TGV2020, Queensland, CCJPA-WD1/WD2, DSB, Daisy) — these and
  GenericReport itself are well-guarded.
- All 12 still share the report-agnostic findings (normalise_devices drop, MQTT flap, compare_json
  staleness, tree.py/device.py update-path crashes, credentials S3–S7, API S1) — those are base-class /
  update-path, not per-report.

## Implication for the recommendation (sharpens it)
The fix is **not** "rewrite the report layer" and **not even** "build a new shared engine" — the safe engine
(`GenericReport.fixed_consist_algo` + topology-YAML) already exists in-tree and 7 bespoke classes already
meet it. The work is **consolidation of 5 specific classes** (DOSTO, VIA, ACE, Dani, Luna) onto that
existing pattern — with DOSTO and VIA as the urgent two (HIGH). That is a far smaller, lower-risk, more
concrete change than the report's original "extract a shared engine and migrate all 14" framing, and it
strengthens IMPROVE.
