# GitLab change-set: coach-numbering survives miswire / switch-down / alternate-path

**Repo:** `onboard/obn` (package `nd-obn`) — engine, CI-gated (653-test suite), `make tag` release. NOT a hieradata edit, NOT a bench chroot.
**Goal:** `number_coaches` must never drop a discovered switch. Three conditions to survive:
1. **switch down / cold-bypassed** → emit a `DOWN` row (don't dead-end + delete downstream).
2. **alternate LLDP path up, primary edge down** (single broken cable, switch fine) → place the switch via its config identity, flag `off-expected-wiring` (don't UNPLACE it).
3. **genuine miswire** → surface it as a fault (UNPLACED / off-expected-wiring with the observed vs expected peer), never silently mis-number.

Scope note: this is features **B + A** from the analysis. The **CCUContext / CCU2 (feature C)** work is DELIBERATELY EXCLUDED — verified it's currently correct via the hardcode and the config fix has a per-hostname-key trap (see `coach_numbering_edge_cases_2026-07-04.md`). Keep the `ccu1_coach` hardcode.

---

## What goes in the MR (4 files) + which are shared

| File | Repo path | Shared? | Change |
|---|---|---|---|
| **report_dosto_neu.py** | `src/usr/share/obn/lib/report/` | **DOSTO-only** (1 of 14 per-fleet report classes) | The whole new `number_coaches`: topology-anchored numbering + never-drop + DOWN/UNPLACED + off-expected-wiring. Bulk of the MR. |
| **device.py** | `src/usr/share/obn/lib/report/` | **SHARED base Device (all fleets)** | Add one additive dataclass field `status: str = field(default="UP", compare=False)`. Default keeps every other fleet unchanged. |
| **backbone_validate.py** | `src/usr/share/obn/` | **SHARED — every fleet's `obn validate`** | In `load_devices`, merge the DOSTO console side-file — GUARDED `if cfg.get("report_module") != "DostoNeuReport": return devices`. Provably inert for non-DOSTO. |
| **tests/** | `tests/lib/report/` | test-only | Regression fixtures (below). |

Rule (from the RD doc §7e): every shared-file change must be **provably inert for non-DOSTO** (guard on `report_module`), not just incidentally inert.

---

## The three behaviours, mapped to code

### Condition 1 — switch down / bypassed → `DOWN` row (feature B, already prototyped)
- Anchor each switch by **validated hostname** (its config-string position, validated against expected adjacency — misimage-safe).
- For an absent expected chain position whose two expected neighbours are BOTH anchored AND LLDP-reciprocate across it → emit a `DOWN` Device with the real (coach, device) slot + `status="DOWN"` + a not-found ip. It IS published to NMS (so the consist diagram draws the down box).
- **Completeness gate:** compare discovered-switch count to DHCP-lease positions; if under-scanned, absences are `UNKNOWN` not `DOWN` (no false DOWN on a flaky scan).

### Condition 2 — alternate path up, primary edge down → `off-expected-wiring` (feature A, TO ADD to the PoC)
This is the piece the PoC (B) is MISSING. Port A's redundant-reachability pass:
- Build the undirected LLDP SW–SW graph from all discovered switches.
- A switch that hostname-anchors to a valid position BUT is not reachable on its *expected* inter-coach edge, yet IS reachable via some other SW–SW path → **place it at its claimed (coach, device)** with `status="OFF_EXPECTED_WIRING"` (numbered + in the report, not UNPLACED).
- Only fall to UNPLACED if it's neither on the expected edge NOR reachable via any redundant path (genuinely isolated) — OR its hostname claim is contradicted by its neighbours (misimage).

Precedence when B and A both apply to one switch (edge case #7 from the review): **anchorable-by-hostname wins** — place it; then classify the *edge* (expected → normal; redundant-only → off-expected-wiring). Never both place AND emit a placeholder for the same switch.

### Condition 3 — genuine miswire → surfaced, never mis-numbered (feature B)
- A switch whose hostname claim is contradicted by its live neighbours (peer that's not in the acceptable set) → **UNPLACED** with the observed-vs-expected note, console-only. Not numbered, not an NMS junk host.
- Distinguish from bypass: DOWN requires positive reciprocal evidence on the expected toward-X ports; a peer seen on the *wrong* port leans miswire.

---

## Confirmed hardening the MR MUST bake in (from the adversarial review — verified)

These are the edge cases the reviewers found + I verified. Fold them into the MR or it ships with known crash/regression surface:

1. **Null/format-guard `_claimed_pos`** — `if dev is None or not dev.config: return None`, and only accept a position matching `^[A-Za-z][1-9]$` (regex). Kills the `int(pos[1])` ValueError on a malformed hostname AND the `_claimed_pos(None)` AttributeError that feature A's new graph traversal would otherwise reintroduce. One helper, two crash-classes gone.
2. **Coupled-consist banner** — if discovered switches > chain positions (two A1s etc.), emit a loud "coupled consist not supported by single-chain numbering" row rather than silently UNPLACING the second half.
3. **Lowercase MAC on both sides** of `by_mac` lookups (`d.mac.lower()` / `nb["mac"].lower()`) — cheap insurance; real fixtures are lowercase today but a mixed-case discovery would silently orphan every neighbour.
4. **Delete dead `_COACH_OF` module dict** — it has the nv4/nv6 collision and is never used (every call passes the per-model `coach_of`). Remove to avoid a future reader trusting it.
5. **Keep `ccu1_coach` hardcode** (`{"nv4":2,"nv6":3,"fv5":2,"fv6":3}`) — verified correct for all four types. Do NOT swap to CCUContext in this MR (that's the deferred feature-C engine work with the per-hostname-key trap).
6. **Load `_EXPECTED` from templates/schema, not hardcoded** — the PoC hardcodes nv4 only; productionise by loading the expected adjacency per train_type (nv4/nv6 known; fv5/fv6 confirm chains first). Until a train_type has a model, it falls to the legacy walk (no regression).

## NMS-consumption discipline (learned the hard way, RD doc §7d — don't regress)
- DOWN/UNKNOWN devices for **real chain slots** go IN `device_instances` (valid coach/device + not-found ip) so NMS draws the down box and matches the right host.
- The **coach-0 INCOMPLETE banner** and **UNPLACED unnumberable** rows stay **console-only** (side-file) — they have no valid slot, so publishing them makes junk Zabbix hosts (Car 0 / Car 99). `backbone_validate.load_devices` merges the side-file (guarded) so `obn validate` still shows everything.

---

## Test fixtures to commit (tests/)
1. **Floor:** one switch bypassed → all discovered switches still present (numbered + DOWN), 0 dropped. (must-pass; fails on master today)
2. Full consist present → numbering unchanged (no regression).
3. Mid-chain switch absent + neighbours reciprocal → that switch DOWN, others correct.
4. **Alternate-path (A's case, 4736-119):** single broken inter-coach cable, switch reachable via redundant path → placed + `off-expected-wiring`, NOT UNPLACED.
5. Genuine miswire (switch wired to unexpected peer) → UNPLACED with observed-vs-expected, NOT DOWN.
6. Incomplete scan (discovered < leased) → banner + UNKNOWN (no false DOWN).
7. Misimage: two switches claim same position → both UNPLACED, real one not silently mis-placed.
8. Malformed hostname (`nv4-A-`, `nv4-Ax-`) → UNPLACED, NO crash.
9. Non-DOSTO report (ace/generic) → `backbone_validate` side-file merge is a no-op (shared-file guard proof).

Existing real fixtures to reuse: `findings/fixture_bench_box1-t122_discovery_2026-07-04.json` (bypass), `findings/obn_numbering_repro_4736-119_2026-06-24/discovery_live_119.json` (broken-cable/alternate-path), `discovery_live_110.json` (healthy).

---

## Release path
1. Branch off `origin/master` (repo `onboard/obn`).
2. Commits (team style, RD-prefix, no Claude co-author): (a) `device.py` status field; (b) `report_dosto_neu.py` new number_coaches; (c) `backbone_validate.py` guarded side-file merge; (d) tests; (e) version bump.
3. MR → CI (653 tests + the 9 new) → review (flag it as a shared-file change on device.py + backbone_validate.py, both guarded).
4. `make tag` → CI builds+publishes the .deb. Do NOT hand-build the engine.
5. Deploy to trains via the normal Puppet pin → `nd-update-puppetenv.sh` → CCU `ndsu up` + reboot (nd-obn is `/usr/share/obn/**`, package-owned, so it lands on upgrade).

## What is NOT in this MR (deferred, documented)
- CCUContext / CCU2 anchor (feature C) — current hardcode is correct; per-type config fix has a per-hostname-key trap. Separate engine MR when DOSTO gets a 2nd CCU.
- fv5 `box1_coach_number:3` config value — latent, masked at NMS today; folds into the deferred C work.
