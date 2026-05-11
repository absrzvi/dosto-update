---
schema: nv6
consist: 6-car
applies_to: all 4736-1xx trains
extracted_from: nd-obn-template-dostoneu-nv6 v0.0.19 (commit deee326, 2026-04-20)
extracted_at: 2026-05-09
extracted_by: dosto-extract-train-data v1
template_repo: git@git-nc.nomadrail.com:onboard/nd-obn-template-dostoneu-nv6.git
local_clone: C:/Users/AbbasRizvi/Documents/nomad-obn-template-nv6
---

# DOSTO NEU 6-car (nv6) — Topology Reference

This file applies to **every train in the 4736-1xx series**. Topology and AP→port mapping are identical across all 4736 consists; only per-train values (Fzg ID, vlan7 IPs) differ — those live in per-train files (`<train#>.md`).

## Switches (18 total)

3 switches per coach × 6 coaches. Coach order from front to back: **A → C → D → E → F → B**.

| Coach | Pos | Hostname template | Notes |
|---|---|---|---|
| 1 | A1 | nv6-A1-v8-`<fzg>` | front-coupler trunk on e0-2 |
| 1 | A2 | nv6-A2-v8-`<fzg>` | |
| 1 | A3 | nv6-A3-v8-`<fzg>` | front-coupler on e0-2; **Stadler firewall on e1-4** |
| 2 | C1 | nv6-C1-v8-`<fzg>` | |
| 2 | C2 | nv6-C2-v8-`<fzg>` | |
| 2 | C3 | nv6-C3-v8-`<fzg>` | |
| 3 | D1 | nv6-D1-v8-`<fzg>` | **OBS on e0-2, RDC on e0-3** |
| 3 | D2 | nv6-D2-v8-`<fzg>` | OBS/RDC reserves (e0-2/e0-3 disabled) |
| 3 | D3 | nv6-D3-v8-`<fzg>` | **OBS on e0-2, RDC on e0-3** |
| 4 | E1 | nv6-E1-v8-`<fzg>` | |
| 4 | E2 | nv6-E2-v8-`<fzg>` | |
| 4 | E3 | nv6-E3-v8-`<fzg>` | |
| 5 | F1 | nv6-F1-v8-`<fzg>` | |
| 5 | F2 | nv6-F2-v8-`<fzg>` | |
| 5 | F3 | nv6-F3-v8-`<fzg>` | |
| 6 | B1 | nv6-B1-v8-`<fzg>` | front-coupler on e0-2; **ZFR primary on e1-11** |
| 6 | B2 | nv6-B2-v8-`<fzg>` | |
| 6 | B3 | nv6-B3-v8-`<fzg>` | front-coupler on e0-2; **ZFR standby on e1-11** |

`<fzg>` is zero-padded to 3 digits, e.g. `nv6-A1-v8-133` for Fzg 133.

## APs (24 total — 4 per coach)

Every coach has 4 APs. AP1/AP2/AP3 hang off the per-coach switches' `e0-4`; AP4 hangs off the third switch's `e1-2`.

| Coach | Slot | Switch | Port | Config (LuCI side) |
|---|---|---|---|---|
| 1 | AP1 | A1 | e0-4 | AP1-v1 |
| 1 | AP2 | A2 | e0-4 | AP2-v1 |
| 1 | AP3 | A3 | e0-4 | AP3-v1 |
| 1 | AP4 | A3 | e1-2 | AP4-v1 |
| 2 | AP1 | C1 | e0-4 | AP1-v1 |
| 2 | AP2 | C2 | e0-4 | AP2-v1 |
| 2 | AP3 | C3 | e0-4 | AP3-v1 |
| 2 | AP4 | C3 | e1-2 | AP4-v1 |
| 3 | AP1 | D1 | e0-4 | AP1-v1 |
| 3 | AP2 | D2 | e0-4 | AP2-v1 |
| 3 | AP3 | D3 | e0-4 | AP3-v1 |
| 3 | AP4 | D3 | e1-2 | AP4-v1 |
| 4 | AP1 | E1 | e0-4 | AP1m-v1 |
| 4 | AP2 | E2 | e0-4 | AP2m-v1 |
| 4 | AP3 | E3 | e0-4 | AP3m-v1 |
| 4 | AP4 | E3 | e1-2 | AP4m-v1 |
| 5 | AP1 | F1 | e0-4 | AP1m-v1 |
| 5 | AP2 | F2 | e0-4 | AP2m-v1 |
| 5 | AP3 | F3 | e0-4 | AP3m-v1 |
| 5 | AP4 | F3 | e1-2 | AP4m-v1 |
| 6 | AP1 | B1 | e0-4 | AP1m-v1 |
| 6 | AP2 | B2 | e0-4 | AP2m-v1 |
| 6 | AP3 | B3 | e0-4 | AP3m-v1 |
| 6 | AP4 | B3 | e1-2 | AP4m-v1 |

**`m-` config boundary:** coaches 1–3 (A, C, D) use plain `APN-v1`. Coaches 4–6 (E, F, B) use `APNm-v1` (middle-coach variant). The `m-` is in the AP-side LuCI config, not in the OBN switch templates.

All AP trunks carry VLANs `100, 10, 20, 30, 31, 131, 150, 1` (the trailing `,1` may be absent on AP4 of C3 and F3 — minor template inconsistency, treat as cosmetic).

## Inter-coach trunks (LLDP topology)

For each switch's `e0-0` and `e0-1`, the **expected far-end switch** is what LLDP should show. The `description` strings in the templates match — nv6 templates have no aliasing issues.

Source: `description` fields of `e0-0` and `e0-1` in every nv6 `.cfg` template.

| Switch | Port | Far-end switch | Type |
|---|---|---|---|
| A1 | e0-0 | A3 | intra-coach (A) |
| A1 | e0-1 | C1 | inter-coach (1↔2) |
| A2 | e0-0 | A3 | intra-coach (A) |
| A2 | e0-1 | C3 | inter-coach (1↔2) |
| A3 | e0-0 | A1 | intra-coach (A) |
| A3 | e0-1 | A2 | intra-coach (A) |
| C1 | e0-0 | A1 | inter-coach (2↔1) |
| C1 | e0-1 | D1 | inter-coach (2↔3) |
| C2 | e0-0 | C3 | intra-coach (C) |
| C2 | e0-1 | D3 | inter-coach (2↔3) |
| C3 | e0-0 | A2 | inter-coach (2↔1) |
| C3 | e0-1 | C2 | intra-coach (C) |
| D1 | e0-0 | C1 | inter-coach (3↔2) |
| D1 | e0-1 | E2 | inter-coach (3↔4) |
| D2 | e0-0 | D3 | intra-coach (D) |
| D2 | e0-1 | E1 | inter-coach (3↔4) |
| D3 | e0-0 | C2 | inter-coach (3↔2) |
| D3 | e0-1 | D2 | intra-coach (D) |
| E1 | e0-0 | F1 | inter-coach (4↔5) |
| E1 | e0-1 | D2 | inter-coach (4↔3) |
| E2 | e0-0 | E3 | intra-coach (E) |
| E2 | e0-1 | D1 | inter-coach (4↔3) |
| E3 | e0-0 | F2 | inter-coach (4↔5) |
| E3 | e0-1 | E2 | intra-coach (E) |
| F1 | e0-0 | B1 | inter-coach (5↔6) |
| F1 | e0-1 | E1 | inter-coach (5↔4) |
| F2 | e0-0 | F3 | intra-coach (F) |
| F2 | e0-1 | E3 | inter-coach (5↔4) |
| F3 | e0-0 | B2 | inter-coach (5↔6) |
| F3 | e0-1 | F2 | intra-coach (F) |
| B1 | e0-0 | B3 | intra-coach (B) |
| B1 | e0-1 | F1 | inter-coach (6↔5) |
| B2 | e0-0 | B3 | intra-coach (B) |
| B2 | e0-1 | F3 | inter-coach (6↔5) |
| B3 | e0-0 | B1 | intra-coach (B) |
| B3 | e0-1 | B2 | intra-coach (B) |

## Front-coupler trunks (e0-2 of A1, A3, B1, B3)

Connect to the next consist when coupled. **DOWN when train is solo** — expected.

| Switch | Port | Description | Carries |
|---|---|---|---|
| A1 | e0-2 | Frontkupplung A1 | VLANs 5, 15 |
| A3 | e0-2 | Frontkupplung A3 | VLANs 5, 15 |
| B1 | e0-2 | Frontkupplung B1 | VLANs 5, 15 |
| B3 | e0-2 | Frontkupplung B3 | VLANs 5, 15 |

## Critical Stadler-facing trunks

| Switch | Port | Carries | VLANs |
|---|---|---|---|
| A3 | e1-4 | Stadler firewall | 2, 3, 5, 6, 7, 8, 9, 12, 15 |
| D1 | e0-2 | OBS D1 | 100, 10, 20, 21, 22, 23, 24, 30, 31, 46, 48, 90, 131, 150, 200, 202, 7 |
| D1 | e0-3 | RDC D1 | 200, 202 |
| D3 | e0-2 | OBS D3 | 100, 10, 20, 21, 22, 23, 24, 30, 31, 46, 48, 90, 131, 150, 200, 202, 7 |
| D3 | e0-3 | RDC D3 | 200, 202 |
| B1 | e1-11 | ZFR R (primary) | 2 |
| B3 | e1-11 | ZFR (standby) | 2 |

## Reserved / disabled ports of note

- D2 e0-2 (`OBS D2 Reserved`), D2 e0-3 (`RDC D2 Reserved`) — admin-disabled in template.
- D3 e1-10 (`OBS D3 Reserved`), D3 e1-11 (`RDC D3 Reserved`) — admin-disabled.
- D1, D3 active OBS/RDC trunks are e0-2/e0-3.

## Cross-references

- `dosto-cabling-check` reads this file's "Inter-coach trunks" table for LLDP comparison.
- `dosto-device-discovery` reads "Switches" + "APs" tables for count + missing-device localisation.
- `dosto-l2-health` reads "Critical Stadler-facing trunks" for Phase 4 of the health check.
- Per-train files (`<train#>.md`) reference this file via `topology_ref: _shared/nv6-topology.md`.
