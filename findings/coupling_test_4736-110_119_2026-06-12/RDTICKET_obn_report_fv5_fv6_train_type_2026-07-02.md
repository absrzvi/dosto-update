# R&D ticket draft — OBN report: unsupported train_type (fv5, fv6)

**Date:** 2026-07-02 · **Author:** Abbas · **Sibling of:** TRIAG-8585
**Status:** DRAFT for Jira. Plain text below the line.

---

**Summary:** `obn report` is a silent no-op on 4705 (fv5) and 4706 (fv6) — the whole report → consist → validate → NMS pipeline is dead for both fleets.

**Root cause:** `DostoNeuReport.number_coaches()` (`/usr/share/obn/lib/report/report_dosto_neu.py`) only branches on `train_type == "nv4"` / `"nv6"`. On fv5/fv6 no branch matches → the CCU seed gets no coach number → BFS numbers 0 devices → the device list empties → `compare_json()` sees "no changes" → `store_report()` never runs → `discovery.prev.json` is never written. Exit 0, no error. Downstream: `GET /consist` 404 → `obn validate` empty → `consist.yaml` stays an empty stub → NMS consist/report dead for both fleets.

Discover, config push and firmware push are all unaffected — only report → consist → validate is broken.

**Two different fixes:**

1. **fv6 (4706) — alias to nv6.** fv6 is a 6-car A–F consist structurally identical to nv6 (confirmed from `fv6-*.cfg`). Add `or self.train_type == "fv6"` to the nv6 branches, or alias fv6 → nv6.

2. **fv5 (4705) — new branch required.** fv5 is a 5-car consist (the 6-car layout with the D/300 coach removed), so it matches neither nv4 nor nv6 and cannot alias. Needs its own branch. Topology:

   | Property | Value |
   |---|---|
   | Coaches | 5 — labelled A, C, E, F, B (D/300 removed) |
   | Backbone order | A → C → E → F → B |
   | Switches/coach | 3 (X1/X2/X3) → 15 total |
   | Seed coach | A — Firewall/CCU port on A3 |
   | Inter-coach trunks | A1→C1, A2→C3, C1→E1, E1→F1, F1→B1 |

   Seed from coach A, number along A→C→E→F→B, 3 switches per coach. Treat the coach label as opaque (label ≠ position — 300 is skipped).

**Repro:** fv6 on box1-t15 (4706-102, 10.179.15.1, nd-obn 2.2.23), 2026-06-25.

**Note:** fv5 topology above is derived from the `fv5-*.cfg` template switch-to-switch descriptions — please sanity-check against the 4705 IPA schema before implementing.
