---
schema: nv4
consist: 4-car
applies_to: all 4734-1xx trains
extracted_from: nd-obn-template-dostoneu-nv4 v0.0.19 (commit bf89be7, 2026-04-16)
extracted_at: 2026-05-09
extracted_by: dosto-extract-train-data v1
template_repo: git@git-nc.nomadrail.com:onboard/nd-obn-template-dostoneu-nv4.git
local_clone: C:/Users/AbbasRizvi/Documents/nomad-obn-template-nv4
---

# DOSTO NEU 4-car (nv4) — Topology Reference

This file applies to **every train in the 4734-1xx series**. Topology and AP→port mapping are identical across all 4734 consists; only per-train values (Fzg ID, vlan7 IPs) differ — those live in per-train files (`<train#>.md`).

## ⚠ Description aliasing — read this first

The nv4 templates were forked from nv6 at some point. The **switch hostnames** were renamed (D became G, F removed, etc.) but **`description` strings inside `interface` blocks were not updated** — they still reference nv6-era neighbour names (`Switch C1`, `Switch F1`, etc.) that don't exist on nv4 consists.

| nv4 description string | Actual physical neighbour (LLDP-visible) |
|---|---|
| `Switch C1` | `G1` |
| `Switch C2` | `G2` |
| `Switch C3` | `G3` |
| `Switch D1` | `G1` (the trunks ending in D1 are on G1) |
| `Switch D2` | `G2` |
| `Switch D3` | `G3` |
| `Switch F1` | `B1` |
| `Switch F2` | `B2` |
| `Switch F3` | `B3` |
| `Switch E1`, `E2`, `E3` | `E1`, `E2`, `E3` (no aliasing — E coach exists on both) |
| `Switch A1`, `A2`, `A3` | `A1`, `A2`, `A3` (no aliasing) |
| `Switch B1`, `B2`, `B3` | `B1`, `B2`, `B3` (no aliasing) |
| `Switch G1`, `G2`, `G3` | `G1`, `G2`, `G3` (no aliasing — G is nv4-native) |

**Implication for `dosto-cabling-check`:** when comparing LLDP `live=<peer>` against template-description `expected=<peer>`, apply the aliasing table above to the `expected` value before comparison. The `Inter-coach trunks` table below has aliasing already resolved — use that as the source of truth, not the raw template descriptions.

The same kind of aliasing applies to other description fields (`AP D1`, `OBS D1`, etc. on G-coach switches still reference D — these are cosmetic, the actual hardware function is correct, just labelled with a stale name).

## Switches (12 total)

3 switches per coach × 4 coaches. Coach order from front to back: **A → G → E → B**.

| Coach | Pos | Hostname template | Notes |
|---|---|---|---|
| 1 | A1 | nv4-A1-v8-`<fzg>` | front-coupler trunk on e0-2 |
| 1 | A2 | nv4-A2-v8-`<fzg>` | |
| 1 | A3 | nv4-A3-v8-`<fzg>` | front-coupler on e0-2; **Stadler firewall on e1-4** |
| 2 | G1 | nv4-G1-v8-`<fzg>` | **OBS on e0-2, RDC on e0-3** (G handles role of nv6 D coach) |
| 2 | G2 | nv4-G2-v8-`<fzg>` | OBS/RDC reserves disabled |
| 2 | G3 | nv4-G3-v8-`<fzg>` | **OBS on e0-2, RDC on e0-3** |
| 3 | E1 | nv4-E1-v8-`<fzg>` | |
| 3 | E2 | nv4-E2-v8-`<fzg>` | |
| 3 | E3 | nv4-E3-v8-`<fzg>` | |
| 4 | B1 | nv4-B1-v8-`<fzg>` | front-coupler on e0-2; **ZFR primary on e1-11** |
| 4 | B2 | nv4-B2-v8-`<fzg>` | |
| 4 | B3 | nv4-B3-v8-`<fzg>` | front-coupler on e0-2; **ZFR standby on e1-11** |

## APs (16 total — 4 per coach)

Same per-coach pattern as nv6. AP1/AP2/AP3 on each coach's switches' `e0-4`; AP4 on the third switch's `e1-2`.

| Coach | Slot | Switch | Port | Config |
|---|---|---|---|---|
| 1 | AP1 | A1 | e0-4 | AP1-v1 |
| 1 | AP2 | A2 | e0-4 | AP2-v1 |
| 1 | AP3 | A3 | e0-4 | AP3-v1 |
| 1 | AP4 | A3 | e1-2 | AP4-v1 |
| 2 | AP1 | G1 | e0-4 | AP1m-v1 |
| 2 | AP2 | G2 | e0-4 | AP2m-v1 |
| 2 | AP3 | G3 | e0-4 | AP3m-v1 |
| 2 | AP4 | G3 | e1-2 | AP4m-v1 |
| 3 | AP1 | E1 | e0-4 | AP1m-v1 |
| 3 | AP2 | E2 | e0-4 | AP2m-v1 |
| 3 | AP3 | E3 | e0-4 | AP3m-v1 |
| 3 | AP4 | E3 | e1-2 | AP4m-v1 |
| 4 | AP1 | B1 | e0-4 | AP1-v1 |
| 4 | AP2 | B2 | e0-4 | AP2-v1 |
| 4 | AP3 | B3 | e0-4 | AP3-v1 |
| 4 | AP4 | B3 | e1-2 | AP4-v1 |

**`m-` config boundary on nv4:** coaches 1, 4 (A, B) use plain `APN-v1`. Coaches 2, 3 (G, E — middle coaches) use `APNm-v1`. Confirm against AP-side LuCI config when bypassing factory mode.

**Note about template description fields:** the G-coach templates show `AP D1`, `AP D2`, `AP D3`, `AP D4` in their description strings (legacy from the nv6 fork). The actual AP slot names per the LuCI configs are `AP G1`, `AP G2`, etc. Treat as cosmetic.

All AP trunks carry VLANs `100, 10, 20, 30, 31, 131, 150, 1`.

## Inter-coach trunks (LLDP topology) — aliasing resolved

This table shows the **actual physical neighbour** an LLDP check should see, with the description-aliasing already corrected.

Source: cross-referenced from corrected mapping in `scripts/lldp_topology_check.py`.

| Switch | Port | Far-end switch | Type | Note |
|---|---|---|---|---|
| A1 | e0-0 | A3 | intra-coach (A) | template description matches |
| A1 | e0-1 | G1 | inter-coach (1↔2) | template says "Switch C1" — **aliased to G1** |
| A2 | e0-0 | A3 | intra-coach (A) | |
| A2 | e0-1 | G3 | inter-coach (1↔2) | template says "Switch C3" — **aliased to G3** |
| A3 | e0-0 | A1 | intra-coach (A) | |
| A3 | e0-1 | A2 | intra-coach (A) | |
| G1 | e0-0 | A1 | inter-coach (2↔1) | template says "Switch C1" — **aliased to A1** (corrected) |
| G1 | e0-1 | E2 | inter-coach (2↔3) | template says "Switch E2" — matches |
| G2 | e0-0 | G3 | intra-coach (G) | template says "Switch D3" — **aliased to G3** |
| G2 | e0-1 | E1 | inter-coach (2↔3) | matches |
| G3 | e0-0 | A2 | inter-coach (2↔1) | template says "Switch C2" — **aliased to A2** (corrected) |
| G3 | e0-1 | G2 | intra-coach (G) | template says "Switch D2" — **aliased to G2** |
| E1 | e0-0 | B1 | inter-coach (3↔4) | template says "Switch F1" — **aliased to B1** |
| E1 | e0-1 | G2 | inter-coach (3↔2) | template says "Switch D2" — **aliased to G2** |
| E2 | e0-0 | E3 | intra-coach (E) | matches |
| E2 | e0-1 | G1 | inter-coach (3↔2) | template says "Switch D1" — **aliased to G1** |
| E3 | e0-0 | B2 | inter-coach (3↔4) | template says "Switch F2" — **aliased to B2** |
| E3 | e0-1 | E2 | intra-coach (E) | matches |
| B1 | e0-0 | B3 | intra-coach (B) | matches |
| B1 | e0-1 | E1 | inter-coach (4↔3) | template says "Switch F1" — **aliased to E1** (corrected) |
| B2 | e0-0 | B3 | intra-coach (B) | matches |
| B2 | e0-1 | E3 | inter-coach (4↔3) | template says "Switch F3" — **aliased to E3** (corrected) |
| B3 | e0-0 | B1 | intra-coach (B) | matches |
| B3 | e0-1 | B2 | intra-coach (B) | matches |

## Front-coupler trunks

| Switch | Port | Description | Carries |
|---|---|---|---|
| A1 | e0-2 | Frontkupplung A1 | VLANs 5, 15 |
| A3 | e0-2 | Frontkupplung A3 | VLANs 5, 15 |
| B1 | e0-2 | Frontkupplung B1 | VLANs 5, 15 |
| B3 | e0-2 | Frontkupplung B3 | VLANs 5, 15 |

DOWN when train is solo — expected.

## Critical Stadler-facing trunks

Same logical layout as nv6, but on G coach (replacing nv6's D coach):

| Switch | Port | Carries | VLANs |
|---|---|---|---|
| A3 | e1-4 | Stadler firewall | 2, 3, 5, 6, 7, 8, 9, 12, 15 |
| G1 | e0-2 | OBS (description: "OBS D1") | 100, 10, 20, 21, 22, 23, 24, 30, 31, 46, 48, 90, 131, 150, 200, 202, 7 |
| G1 | e0-3 | RDC (description: "RDC D1") | 200, 202 |
| G3 | e0-2 | OBS (description: "OBS D3") | 100, 10, 20, 21, 22, 23, 24, 30, 31, 46, 48, 90, 131, 150, 200, 202, 7 |
| G3 | e0-3 | RDC (description: "RDC D3") | 200, 202 |
| B1 | e1-11 | ZFR R (primary) | 2 |
| B3 | e1-11 | ZFR (standby) | 2 |

## Reserved / disabled ports

- G2 e0-2 (`OBS D2 Reserved`), G2 e0-3 (`RDC D2 Reserved`) — admin-disabled
- G3 e1-10 (`OBS D3 Reserved`), G3 e1-11 (`RDC D3 Reserved`) — admin-disabled
- E1 e1-10 (`Sprechstelle PRM E1`), E1 e1-11 (`Sprechstelle PRM WCR`) — PRM-specific accessibility (not on nv6)
- E2 e1-10 (`Sprechstelle PRM E2`), E2 e1-11 (`Sprechstelle PRM E1R`)
- E3 e1-10 (`Sprechstelle PRM WC`), E3 e1-11 (`Sprechstelle PRM E2R`)
- E3 e2-0 (`Energiezaehler E`) — energy meter on E coach (nv4 puts this on E; nv6 doesn't have one in templates I parsed)

## Cross-references

- `dosto-cabling-check` reads this file's "Inter-coach trunks (aliasing resolved)" table — the resolved column is authoritative, **not** the raw template descriptions.
- `dosto-device-discovery` reads "Switches" + "APs" tables for count + missing-device localisation.
- `dosto-l2-health` reads "Critical Stadler-facing trunks" for Phase 4.
- Per-train files (`<train#>.md`) reference this file via `topology_ref: _shared/nv4-topology.md`.

## Action item for R&D

The nv4 templates have multiple stale `description` strings (referencing C, D, F coaches that don't exist on 4-car). Worth a GitLab issue to scrub all `interface` block description fields to match actual nv4 layout. This is cosmetic-only as long as downstream consumers (this file, `dosto-cabling-check`) account for the aliasing — but it's the kind of thing that bites a future engineer reading the templates expecting them to be authoritative.
