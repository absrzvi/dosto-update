# Coach-numbering merge — adversarial edge-case hunt (verified)

**Date:** 2026-07-04
**Method:** 3 parallel adversarial reviewers (parsing/indexing, topology/logic, feature-interaction) against the real PoC code + real discovery fixtures, then each finding VERIFIED against fixtures/base-class before inclusion. Unverified/false-positive agent findings are listed separately so we don't re-chase them.
**Subject:** `findings/report_dosto_neu_PATCHED_2026-07-04.py` (feature B) and the planned B+A+C merge.

---

## CONFIRMED — real issues to fix in the MR

### 1. 🔴 CCUContext returns coach 3 for nv4/fv5 (SILENT misnumbering) — the big one — VERIFIED on live config
Integrating feature C by swapping `ccu1_coach` → `CCUContext.get_current_ccu_box_and_coach()` misnumbers nv4 and fv5 trains. **Verified against the live Puppet config, NOT inferred:** DOSTO `hieradata/files/obn/topology.yaml` has a single hardcoded `box1_coach_number: 3` and NO `box_coach_numbers` map. CCUContext therefore returns coach **3 for every DOSTO train regardless of type**. But the CCU coach is train-type-specific:

| train_type | CCU coach (`ccu1_coach`) | CCUContext returns | Correct? |
|---|---|---|---|
| nv4 (incl. **the bench**, box1-t122) | **2** | 3 | 🔴 WRONG |
| nv6 | 3 | 3 | ✅ (coincidental) |
| fv5 | 2 | 3 | 🔴 WRONG |
| fv6 | 3 | 3 | ✅ |

`box1_coach_number: 3` is an **nv6-only value with no per-train-type override.** So the swap silently anchors nv4/fv5 one coach too high → the walk seeds at the wrong coach and mis/under-numbers the consist. Not a crash — a silent wrong report on every 4734/nv4 train.
**Fix (BLOCKER before any CCUContext swap):** make `box1_coach_number` per-train-type — either add `box_coach_numbers: {nv4:{box1:2}, nv6:{box1:3}, fv5:{box1:2}, fv6:{box1:3}, default:{box1:1}}` to DOSTO topology, OR have the integration pass the train_type default and refuse a CCUContext value that contradicts the known per-type CCU coach. Until then, KEEP the `ccu1_coach` hardcode. (Corrected in `coach_numbering_ccucontext_integration_2026-07-04.md`.)

### 2. 🟠 `int(pos[1])` / `parts[1][0]` crash on a malformed hostname (code fragility)
`_cd_of` line 51 `int(pos[1])` and `_claimed_pos` line 60 assume a clean `nv6-A3-...` shape. A config like `nv6-A5-` (device digit out of range still parses but numbers wrong), `nv6-Ax-` (non-digit → **ValueError**), or a coach letter + non-digit → crash.
**Verified NOT present in any real fixture** (119, 110, bench all clean) → won't fire on current fleet data, but a genuinely misimaged/corrupt hostname would crash the whole report. **Fix:** make `_claimed_pos` return None unless `parts[1]` is `[A-Za-z][1-9]` (regex), so a malformed claim becomes UNPLACED, not a crash.

### 3. 🟠 `_claimed_pos(None)` AttributeError — guarded NOW, easy to un-guard in the merge
`_claimed_pos(None)` crashes (`None.config` → AttributeError — confirmed). In the PoC all 3 call sites are guarded (lines 171, 196, 258/260) so it's **not currently reachable**. BUT feature A's redundant-path graph traversal adds new lookups; an unguarded `_claimed_pos(by_mac.get(...))` there would crash. **Fix:** make `_claimed_pos` null-safe at the top (`if dev is None or not dev.config: return None`) — one line, removes the whole class.

### 4. 🟡 Coupled consist (24 switches, two A1s) → second half all UNPLACED
If a coupled train is scanned as `train_type="nv4"`, positions duplicate; the second A1/A2/... hit the duplicate-claim path → UNPLACED, never numbered; and `for pos in chain` skips the already-anchored slot so no DOWN row for the second consist either. Not a crash; wrong output. Real-world: rare (coupled trains usually discovered per-consist). **Fix:** out of scope for v1 — but log a clear "more switches than chain positions — coupled consist not supported" banner rather than silently UNPLACING half the train.

### 5. 🟡 Misimage duplicate ghosts the real switch
Real A1 + misimaged switch both claim A1 → both UNPLACED (correct: can't trust either), but the healthy A1 is dropped too. Acceptable trade-off (operator sees two UNPLACED rows), but worth a sharper note: "N switches claim A1 — one may be misimaged" so the real one is findable.

## CONFIRMED SAFE — checked, no action (don't re-chase)
- **MAC case mismatch** (reviewer-1 Rank 2): real fixtures are 100% lowercase MACs (0/129, 0/128 uppercase). Non-issue on real data. (Still: a defensive `.lower()` on both sides is cheap insurance for the MR.)
- **`anchored_dev[L]` KeyError** on zero-discovery: guarded by line 255 `if L not in anchored_dev ... return False`. Safe.
- **`scanned {discovered}/{leased}` TypeError** when leased=None: guarded — banner only emits when `scan_incomplete` (requires leased not None). Safe.
- **DOWN devices polluting NMS**: by design they carry a VALID coach/device (real slot) + 7.7.7.7 ip so NMS draws the down box; the junk-host risk (Car 0/99) is the coach-0 banner + coach-90/99 UNPLACED which stay console-only. Correct.
- **`_COACH_OF` module-level dict** (line 35): dead code (every call uses the per-model `coach_of`). Harmless but delete it in the MR to avoid the nv4/nv6 collision confusing a future reader.
- **True-terminus never DOWN**: all nv4 positions have 2 neighbours, so the `len(npos)!=2 → False` early return never fires on nv4; it's defensive for incomplete models. Document the implicit contract.

## Feature-interaction findings (third reviewer, verified)

### 6. 🟠 CCUContext singleton keeps stale state across runs
`CCUContext` is a process-wide singleton (`_initialized` flag, early-return in `__init__`). If OBN numbers two trains (or report+validate) in one process without `CCUContext.reset()`, the second run reuses the first train's coach → silent wrong walk. **Fix:** call `CCUContext.reset()` at the top of `number_coaches()` (or don't cache across train_type). One line. High-likelihood if any automation loops trains in one process.

### 7. 🟠 Merging B as-is silently LOSES A's redundant-path recovery
B (the PoC) has **no redundant-reachability graph** — it only checks live LLDP neighbours vs topology. So the single-broken-cable case (4736-119: switch anchorable + reachable via alternate path but off its expected edge) → B marks it UNPLACED (console-only, dropped from report), whereas A placed it + flagged `off-expected-wiring`. Taking B without explicitly porting A's LLDP-SW-SW reachability graph = a regression vs A. **Fix:** port A's reachability graph (fallback_numbering.py L82–96) into the merge; when a switch is hostname-anchorable AND reachable only via redundant path, PLACE it with `off_expected_wiring=True`, don't UNPLACE it.

### 8. 🟡 Legacy walk rules hardcode "coach 2 is the pivot"
The legacy fallback walk (nv6/fv*) has direction rules like `1 < from.coach <= ccu1_coach`. These assume the CCU pivot; if CCUContext ever legitimately returns a non-default coach (real CCU2), the legacy walk breaks. Latent (no DOSTO CCU2 today) but a bomb when `box_coach_numbers` is added. **Fix:** document the pivot assumption; when CCU2 becomes real, the legacy walk needs the same CCU-relative refactor, not just the anchor swap.

### 9. 🟡 A's config-trust vs B's hostname-validation can both misplace a lucky misimage
If a misimaged switch's stale config claims a position whose expected neighbours happen to match its live neighbours, both A (config-trust) and B (adjacency-validate) anchor it wrong — neither catches it. B is stricter than A so risk is lower, but the merge shouldn't assume the two validation modes compose. **Fix:** add a serial/fingerprint cross-check for anchored switches; add a misimage test fixture (two switches, different positions, overlapping neighbours).

## Verified CCU-coach table (ground truth — "which coach is the CCU really in")

Established by live LLDP (CCU→switch), OBN's own live report (BOX coach=N), topology order, and engineer confirmation. This is the authoritative source for any anchor value — NOT `box1_coach_number` (which is a single train-type-blind scalar).

| train_type | CCU coach | letter | how verified | OBN config today | matches? |
|---|---|---|---|---|---|
| nv4 | **2** | G | live bench: CCU→G1, OBN report BOX coach=2, G1 coach=2 | PoC hardcode 2 ✓ / `box1_coach_number:3` ✗ | code OK, config wrong-but-unread |
| nv6 | **3** | D | live: CCU→D1/D3 (4736-119/110), D=coach 3 | PoC hardcode 3 ✓ / `box1_coach_number:3` ✓ | ✓ |
| fv5 | **2** | C | engineer-confirmed 2026-07-04; CCU cabled C1/C3 | 🔴 `box1_coach_number:3` (d300 wagon at slot 3) ✗ + PoC hardcode `fv5:2` ✓ | **CONFIG WRONG — see below** |
| fv6 | **3** | D | engineer-confirmed 2026-07-04 | 3 ✓ | ✓ |

### 🟡 fv5 config-vs-reality mismatch — VERIFIED MASKED (latent, not a current bug)
For fv5 the CCU is physically in coach **2 (C)** — engineer-confirmed AND verified against the live NMS train-layout template (`findings/coupling_test_4736-110_119_2026-06-12/NMS_fv5_template_2026-07-03.json`): `trainLayout.devices` has exactly one BOX at **`coachId: 2`** (device[10]), 5 coaches, alongside the coach-2 switches. So the NMS diagram/monitoring correctly place the fv5 CCU at coach 2.

BUT OBN's topology.yaml (pulled live from box1-t41, saved as `fv5_topology_t41.yaml`) has `box1_coach_number: 3` and puts the BOX wagon (`d300`) at assembly slot 3 (fv5 reuses `dostoneu6` with the D-wagon absent — there is no fv5-specific assembly). So the **discovery-side** value is 3, the **NMS-layer** value is 2 — reconciled at the NMS template, exactly like nv4's wrong `box1_coach_number:3` is masked by the PoC's `ccu1_coach={"nv4":2}` hardcode.

**Conclusion:** fv5 is NOT currently mis-reporting the CCU coach — the NMS template overrides to 2. `box1_coach_number:3` is a latent wrong value read only by `CCUContext` (RD-12057) and shared `report_tgv.py`, neither of which drives fv5's NMS coach today. It only becomes a live bug if the CCUContext swap is done without fixing the per-type value — same conclusion as nv4. No separate fv5 fix needed now; it's the same deferred CCUContext-engine work.

## Consolidated MR action items (verified, ranked)
1. **BLOCKER** — per-train-type `box1_coach_number` (or `box_coach_numbers`) in DOSTO topology BEFORE any CCUContext swap; else keep the `ccu1_coach` hardcode. (#1)
2. Null-guard `_claimed_pos` (`if dev is None or not dev.config`) + regex-guard the position parse (`[A-Za-z][1-9]`). Kills #2 and #3 in one helper. (#2, #3)
3. `CCUContext.reset()` at top of `number_coaches()`. (#6)
4. Port A's redundant-reachability graph → place+flag `off_expected_wiring` instead of UNPLACED. (#7)
5. Coupled-consist banner ("more switches than chain positions"); don't silently UNPLACE half. (#4)
6. Delete dead `_COACH_OF` module dict; add `.lower()` on MAC lookups as cheap insurance. (safe-list)
7. Test fixtures: CCU2 anchor, misimage-with-lucky-neighbours, single-broken-cable (A's case), coupled. (#5, #8)
