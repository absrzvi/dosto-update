# P5 — Replace-vs-Improve Decision Model (OBN origin/master v2.3.12)

Each dimension scored 1–5 with cited evidence. Score semantics: **5 = strong asset / argues to keep & improve;
1 = strong liability / argues to replace.** Weights reflect impact on the decision.

## Scorecard

| # | Dimension | Score | Weight | Evidence |
|---|---|---|---|---|
| 1 | Architectural soundness | **3** | High | Discovery/device/tree layers cleanly layered (P1); **but** report layer has zero shared numbering core — `number_coaches` is `@abstractmethod` + 14 hand-rolled variants (report.py:237). Real weakness, but localized to one layer. |
| 2 | Structural complexity | **5** | High | Avg cyclomatic complexity **A (3.81)**; **every file MI grade A** (P0). Not spaghetti. Hotspots localized to `number_coaches` (VIA F-59, DOSTO F-41). A simple codebase is cheap to harden, expensive to justify rewriting. |
| 3 | Bug density & **class recurrence** | **2** | **Highest** | 15 confirmed + 24 needs-runtime defects (P3) — **but ~22/39 are ONE pattern** (unguarded SNMP-None consumer) and the rest are silent-success/error-masking. Low score on *density*; the recurrence is the rewrite-tempting signal — **except** the recurrence has a *common fix*, which inverts it to an improve signal (one pattern fix retires dozens of bugs). |
| 4 | Test coverage & quality | **3** | High | 1.27:1 test:source; report layer >1:1 and green (280 pass). **But** `tree.py`, `actions.py`, `tipg541`, `tng4500` untested (P4) — and the sweep found 3 high crashes in untested `tree.py`. Solid foundation with named, fillable gaps. |
| 5 | Dependency health / security | **3** | Med-High | pip-audit **clean**; injection-clean; disciplined error handling (P2). Deductions: **S3 (HIGH) — plaintext SNMP/SSH creds committed in vendors.yaml**, S1 unauthenticated GET-mutating REST API, `httpx2` fork provenance, weak SNMPv3 defaults. All fixable in place; S3 is a process/config gap, not a rewrite driver. |
| 6 | Multi-customer blast radius | **2** | High | OBN serves many fleets (TGV/DSB/VIA/CCJPA/ACE/Queensland/DOSTO…) via **14+ report families, each spanning several train-type variants** (DOSTO: nv4/nv6/fv5/fv6; TGV: TGV/Dasye/RBi; CCJPA: WD1/WD2) — so the real layout count is well above 14. A rewrite must re-derive every one of those topology algorithms **+ 11 vendor SNMP drivers** and re-certify against all of them — enormous risk surface. Scores *against replace*, *for* incremental improve. |
| 7 | Cost to improve | **4** | Core | Pattern fixes: a typed SNMP result + guard helper retires the none_deref class; a verify-after-set helper retires silent-success; extract a shared guarded `number_coaches` engine. Bounded, testable, shippable per-deb. Est. **6–10 eng-weeks** to clear confirmed + harden patterns (see below). |
| 8 | Cost to rebuild | **1** | Core | ~12k LOC + 14+ report families (many more real layouts) + 11 vendor drivers + SNMP/MQTT/FastAPI integration + an existing 9.5k-LOC test suite to re-earn, on **in-service trains**. Est. **9–18 eng-months** before parity, with a long dual-run/cutover. |
| 9 | Risk to in-service fleets | **2** | High (tie-break) | OBN runs commissioning + telemetry across a live ÖBB fleet (and others). A rewrite means a high-stakes cutover; incremental hardening ships behind the existing test suite with per-train rollback. Strongly favors improve. |

**Weighted read:** every high/highest-weighted dimension (2,3,4,6,7,8,9) points the same direction once the
*common-fix* nature of the recurrence (3) is accounted for. The only genuine liability is architectural and
**confined to the report layer** (1) — a refactor target, not a rewrite trigger.

## Effort estimate (two methods, report the spread)

**Top-down (LOC/complexity heuristic):** 12k LOC, low complexity, good test base. Industry hardening-pass
rates (~1–2k LOC reviewed+hardened/eng-week with tests) → **~6–12 eng-weeks** for a systematic
None/silent-success/report-extract pass. Rebuild at parity for a 12k-LOC multi-protocol tool with 14
variants → typically **6–12× the improve cost → ~9–18 eng-months**.

**Bottom-up (per-workstream improve):**
- Typed SNMP result + guard-or-default helper, retrofit none_deref sites: ~2–3 wks
- Verify-after-set helper + apply to vdsrail/lantech/tng4500/westermo + post-reboot verify: ~1–2 wks
- Extract shared guarded `number_coaches` engine (visited-set + None-guards), migrate DOSTO+VIA+ACE+DSB
  first: ~2–3 wks
- Fix actions.py (auth + POST + correct HTTPException) + tests for tree.py/actions.py: ~1 wk
- Add mypy strict-optional to CI + clear the type debt it surfaces: ~1 wk
→ **~7–10 eng-weeks.** Both methods agree: improve ≈ **2 eng-months**; rebuild ≈ **10–15× that**.

## Decision rule (stated in advance)
> **Rebuild** iff (architecture ≤ 2 AND complexity ≤ 2) OR (bug recurrence has no common fix) OR
> (cost-to-improve ≈ cost-to-rebuild). **Otherwise improve.**

Applied: architecture = 3 (not ≤2), complexity = 5, the recurrence **has** a common fix, and improve is
~10–15× cheaper than rebuild. **No rebuild condition is met → the rule yields IMPROVE.**

## Recommendation: **IMPROVE** — with a targeted, structured hardening programme
1. **Kill the root cause, not the symptoms.** Introduce a typed SNMP-result type (or `Optional[...]` +
   mypy strict-optional in CI) so the none_deref class is caught at build time, not on a live train.
2. **Verify-after-set.** A shared helper that confirms an SNMP SET/firmware/config/reboot actually took,
   replacing every `return True # TODO`.
3. **Extract a shared `number_coaches` engine** (visited-set termination + None-guards) and migrate the
   14 variants onto it — retiring the infinite-loop + unguarded-deref class platform-wide. This is the one
   real architectural change and it is contained.
4. **Fix the API** (auth + POST for mutations + correct HTTPException) and **backfill tests** for
   `tree.py`, `actions.py`, and the two untested drivers.
5. **Process:** add mypy to CI; keep the field-proven patches (TRIAG-8585) flowing upstream via the
   existing GitLab→deb→Puppet path rather than hand-patching CCUs.

## Counter-case (and rebuttal)
**The strongest argument to replace:** "The same bug keeps recurring across 14 hand-rolled report variants
and the SNMP layer leaks None everywhere — that's a design that *generates* bugs; rebuild it right with a
typed core and a single numbering engine." This is real and is exactly why the report layer scored low.

**Rebuttal:** a rewrite doesn't escape the hard parts — it must re-implement the same 14 customer topologies
and 11 vendor SNMP dialects, the precise places the bugs live, now without the 9.5k-LOC regression net and
against in-service trains. The defects are **pattern defects with pattern fixes**; you capture ~80% of the
"rebuild it right" benefit (typed core, shared numbering engine, verify-after-set) via items 1–3 above at
~10% of the cost and a fraction of the fleet risk. Rebuild only becomes rational if a *new* requirement
(e.g. a protocol or scale OBN structurally can't support) appears — none surfaced in this review.

## AI-leverage note (Hicham asked "with Claude support")
The recommended programme is unusually well-suited to AI-assisted execution: the fixes are
*pattern-replications* (guard every none_deref site, apply verify-after-set to each setter, migrate each
variant to the shared engine) verifiable against an existing test suite — exactly the shape this very review
used (multi-agent sweep → adversarial verification). A Claude-assisted hardening sprint could clear the
confirmed register and the pattern classes in materially less than the 7–10 eng-week human estimate, with
each change gated by the existing tests + new mypy checks.
