# Integrating the coach-numbering PoC with RD-12057 (CCU2 failover) — one MR, CCU-context-aware

**Author:** Abbas Rizvi
**Date:** 2026-07-04
**Repo:** `onboard/obn` (package `nd-obn`), file `src/usr/share/obn/lib/report/report_dosto_neu.py`
**Depends on:** RD-12057 (`8e0236b`, "OBN support for Failover to CCU2 (TGVM)", merged to master Feb 2026)
**Companions:** `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md` (the PoC spec), `findings/report_dosto_neu_PATCHED_2026-07-04.py` (the PoC file)

---

## 1. Why these two must be integrated, not just co-merged

Both features write `device.coach_number` in `number_coaches`; they are two halves of the same problem:

- **RD-12057** fixes the **starting anchor** — via `CCUContext` it answers "which CCU am I running on, and what coach does it sit at," so a report built from the **redundant/alternate CCU (CCU2)** numbers correctly. It wired this into the **generic** report (`report_generic.py`) but **not** the DOSTO override.
- **The bypass PoC** fixes the **walk** — topology-anchored, validated-hostname numbering that survives a cold-bypassed switch and never silently drops a discovered switch.

**Both currently hardcode `ccu1_coach = {"nv4": 2, "nv6": 3, ...}`** — the exact "OBN always runs on CCU1" assumption RD-12057 was built to remove. Merging the PoC as-is re-entrenches that assumption in DOSTO. Integrating instead:
- lets the PoC's switch numbering start from **whichever CCU is active** (RD-12057's contribution),
- keeps the bypass/DOWN robustness (the PoC's contribution),
- and finally wires CCU-context into the DOSTO report (closes the latent gap where DOSTO never inherited RD-12057).

⚠️ **CORRECTION (2026-07-04 adversarial review + LIVE CONFIG CHECK — first draft was wrong):** `CCUContext` does NOT fall back to `ccu1_coach`. **Verified on the live Puppet config:** DOSTO `hieradata/files/obn/topology.yaml` sets a single hardcoded `box1_coach_number: 3` and has NO `box_coach_numbers` map. So CCUContext returns coach **3 for EVERY DOSTO train regardless of type**. That is correct for nv6/fv6 (CCU at coach 3) but **WRONG for nv4 and fv5 (CCU at coach 2)** — including the bench (box1-t122, nv4). A naïve `ccu1_coach → get_current_ccu_box_and_coach()` swap silently anchors nv4/fv5 at coach 3 instead of 2 and mis/under-numbers the whole consist — a silent correctness regression on every 4734/nv4 train (worse than a crash). `box1_coach_number: 3` is an nv6-only value with no per-train-type override.

**Required to make the swap safe (do BOTH or the swap regresses):**
1. Add `box1_coach_number: 2` (nv4) / `3` (nv6) / `2` (fv5) / `3` (fv6) to each DOSTO train_type's OBN topology config — so CCUContext returns the correct coach even single-CCU. (Or add full `box_coach_numbers` maps.)
2. Belt-and-braces in the integration: if `get_current_ccu_box_and_coach()` returns the bare default (coach 1) AND train_type expects a different `ccu1_coach`, prefer the train_type default — never silently accept a coach-1 anchor on a train whose CCU is known to sit elsewhere.

Without step 1, do NOT make the swap — keep the `ccu1_coach` hardcode. The CCUContext migration is gated on the topology config carrying the CCU coach.

## 2. The reference pattern (from RD-12057's `report_generic.py`, master)

```python
# RD12057- OBN enabled to run on alternate CCUs
thisCCUBoxId, thisCCUCoachNumber = self.get_current_ccu_box_and_coach()  # base Report helper
for device in self.device_instances.values():
    device.type = self.find_type(device)
    if device.serial and device.serial.startswith(thisCCUBoxId):
        device.coach_number = thisCCUCoachNumber
        device.device_number = 1
        self.thisBox = device
        queue.append(self.thisBox)
```

`get_current_ccu_box_and_coach()` lives on the **base `Report`** class → `DostoNeuReport` inherits it. Anchor keys on `serial.startswith(thisCCUBoxId)`, NOT `type == "BOX"` (so it picks *this* CCU, not just any box).

## 3. The change — replace both hardcodes with CCUContext

### 3a. In `number_coaches` (the anchoring block, ~PoC line 152)

```diff
     def number_coaches(self):
         model = _EXPECTED.get(self.train_type)
         if model is None:
             return self._number_coaches_legacy()

         adj = model["adj"]
         chain = model["chain"]
         coach_of = model["coach_of"]
-        # coach the CCU sits in — same mapping the legacy walk used to seed the BOX.
-        ccu1_coach = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}.get(self.train_type, 2)
+        # RD12057 — anchor on the CCU OBN is ACTUALLY running on (CCU1 or CCU2),
+        # not a hardcoded CCU1. Falls back to box1 @ the legacy coach when no
+        # box_coach_numbers mapping is configured, so single-CCU DOSTO is unchanged.
+        this_ccu_box_id, this_ccu_coach = self.get_current_ccu_box_and_coach()

         for device in self.device_instances.values():
             device.type = self.find_type(device, retype_icl=False)
-            # Number the CCU (BOX) exactly as the legacy walk did: coach = ccu1_coach,
-            # device 1. WITHOUT this the CCU stays unnumbered ...
-            if device.type == "BOX":
-                device.coach_number = ccu1_coach
+            # Anchor THIS CCU (by serial-prefix, per RD12057) at its real coach.
+            if device.serial and device.serial.startswith(this_ccu_box_id):
+                device.coach_number = this_ccu_coach
                 device.device_number = 1
```

Then everywhere the walk consulted `ccu1_coach` to decide direction (the `from_device.coach_number == ccu1_coach`, `ccu1_coach < ... < max_coach`, `1 < ... <= ccu1_coach` comparisons), use `this_ccu_coach` instead — it is the same value on CCU1 and the correct value on CCU2. Mechanical rename `ccu1_coach → this_ccu_coach` across the function body.

### 3b. In `_number_coaches_legacy` (the fallback, ~PoC line 323–325)

Same substitution so the nv6/fv* fallback path is *also* CCU-aware (not just the nv4 anchored path):

```diff
-        ccu1_coach_map = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}
-        ccu1_coach = ccu1_coach_map.get(self.train_type, 2)
+        _this_box, ccu1_coach = self.get_current_ccu_box_and_coach()
```
(keep the local name `ccu1_coach` in the legacy body to minimise churn — only its *source* changes.)

> Note: keep the BOX-anchoring robust — if `serial.startswith(this_ccu_box_id)` matches no device (e.g. discovery didn't capture the BOX), fall back to the old `type == "BOX"` seeding so the CCU is never left unnumbered (the regression the PoC comment warns about). Suggest: try serial-prefix first, then `type == "BOX"` as a belt-and-braces.

## 4. Config dependency — `box_coach_numbers` for DOSTO

`CCUContext` only returns a non-default coach if the topology config has:

```yaml
topology:
  box_coach_numbers:
    nv4: { box1: 2, box2: <coach-of-CCU2> }
    nv6: { box1: 3, box2: <coach-of-CCU2> }
    default: { box1: 1 }
```

- RD-12057 shipped this for **TGVM** only (`tests/resources/ccu2/topology-tgvm945-ccu2.yaml`). **DOSTO has no `box_coach_numbers` yet.**
- **Action:** if/when DOSTO gets a second CCU, add `box_coach_numbers` for nv4/nv6/fv5/fv6 to the DOSTO OBN topology (backbone-discovery / template config). Until then the fallback keeps behaviour identical to today — **so this MR does not block on the config**, it just future-proofs.
- Where the CCU2 coach actually sits per DOSTO consist type must come from the IPA schema / Stadler (which coach the second CCU is installed in). Unknown today — flag for R&D when DOSTO CCU2 is real.

## 5. Test additions (on top of the PoC's 6 fixtures)

7. **CCU2 anchor:** same bypass fixture but discovery captured from CCU2 (BOX serial = box2, `box_coach_numbers` set) → all switches numbered off CCU2's coach, bypass still DOWN. (Mirror RD-12057's `test_report_ccu2.py` shape for the DOSTO report.)
8. **No `box_coach_numbers` (single-CCU DOSTO):** CCUContext falls back → numbering byte-identical to the hardcoded-`ccu1_coach` PoC output. Proves no regression.

## 6. Shared-file discipline (unchanged from the PoC spec §7e)

`report_dosto_neu.py` is DOSTO-only (one of 14 per-fleet report classes) → this change cannot affect other fleets. `get_current_ccu_box_and_coach()` / `CCUContext` are shared but **already in master** (RD-12057) — we are only *calling* them, not modifying them. So the integration adds **no new shared-file risk** beyond what the PoC already carried; it actually *reduces* divergence by adopting the engine's own CCU-context mechanism instead of a parallel hardcode.

## 7. Net effect

One nd-obn MR — "topology-anchored coach numbering + DOWN/UNPLACED, CCU-context-aware" — that:
- ships the bypass/monitoring-false-negative fix (C3/E2 class), and
- makes DOSTO honour RD-12057's CCU2 failover (closing a gap master left open), and
- removes a hardcode instead of duplicating it.

They compose cleanly; the only real-world prerequisite for the *CCU2* benefit (not for merge safety) is a DOSTO `box_coach_numbers` config, which is a separate, later, hieradata/topology change gated on DOSTO actually having a second CCU.
