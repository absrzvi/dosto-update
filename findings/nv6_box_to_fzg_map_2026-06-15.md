# nv6 box → Fzg authoritative map (for node-file `fzg_id`)

**Date:** 2026-06-15
**Purpose:** source data for putting the real Fzg in each nv6 node file (`hieradata/nodes/dostoneu-nv6/box1-tNN….yaml: fzg_id`), replacing the broken `128 + train_id` formula. Box→Fzg is an arbitrary physical assignment — NOT computable. This table is the human-maintained source of truth.

## How each row was sourced
- **fleet-status**: Train# → Fzg from fleet-status.md (4736-NNN → Fzg NNN+28, consistent).
- **CCU IP → box-id**: `10.179.<box>.1`.
- **LIVE**: confirmed 2026-06-15 by reading the live CCU's OBN template literal (`{%- set train_id = N -%}`) + vlan7 decode.

## The map

| box (t#) | CCU IP | Train# | **Fzg (`fzg_id`)** | Confidence | Node file today |
|---|---|---|---|---|---|
| t1  | 10.179.1.1  | 4736-105 | **133** | fleet-status (offline at probe) | exists (t1, but external_id wrong) |
| t2  | 10.179.2.1  | 4736-120 | **148** | fleet-status | exists |
| t8  | 10.179.8.1  | 4736-108 | **136** | ✅ LIVE (OBN=136, vlan7=196.2) | **MISSING** |
| t10 | 10.179.10.1 | 4736-104 | **132** | ✅ LIVE (OBN=132, vlan7=194.2) | exists (t10) |
| t11 | 10.179.11.1 | 4736-103 | **131** | fleet-status (offline at probe) | exists |
| t12 | 10.179.12.1 | 4736-119 | **147** | ✅ LIVE (OBN=147, vlan7=201.130) | exists |
| t16 | 10.179.16.1 | 4736-116 | **144** | fleet-status (offline at probe) | exists |
| t18 | 10.179.18.1 | 4736-115 | **143** | fleet-status (offline at probe) | exists |
| t19 | 10.179.19.1 | 4736-106 | **134** | fleet-status (offline at probe) | exists |
| t21 | 10.179.21.1 | 4736-118 | **146** | ✅ LIVE (OBN=146, vlan7=201.2) | **MISSING** |
| t23 | 10.179.23.1 | 4736-110 | **138** | ✅ LIVE (OBN=138, vlan7=197.2) | **MISSING** |
| t24 | 10.179.24.1 | 4736-111 | **139** | fleet-status (offline at probe) | **MISSING** |
| t28 | 10.179.28.1 | 4736-109 | **137** | ✅ LIVE (OBN=137, vlan7=196.130) | **MISSING** |
| t32 | 10.179.32.1 | 4736-117 | **145** | fleet-status | **MISSING** |
| t40 | 10.179.40.1 | 4736-112 | **140** | fleet-status (fixed 2026-06-09) | **MISSING** |
| t47 | 10.179.47.1 | 4736-102 | **130** | fleet-status | **MISSING** |

## Trains with UNKNOWN CCU IP (cannot place yet — need box-id)
From fleet-status, these 4736 trains have `CCU=❓`, so their box-id is unknown and they cannot be added until the CCU IP is identified:

| Train# | Fzg | Status |
|---|---|---|
| 4736-101 | 129 | CCU IP unknown |
| 4736-107 | 135 | CCU IP unknown |
| 4736-113 | 141 | CCU IP unknown |
| 4736-114 | 142 | CCU IP unknown |
| 4736-121 | 149 | CCU IP unknown |
| 4736-122 | 150 | CCU IP unknown |
| 4736-123 | 151 | CCU IP unknown |

## ⚠️ Critical mismatch — existing node files DO NOT match real boxes
The node files `box1-t1 … box1-t20` were created as a contiguous block, but the **real nv6 CCU boxes are scattered** (1, 2, 8, 10, 11, 12, 16, 18, 19, 21, 23, 24, 28, 32, 40, 47). Consequences:
- Node files for **t3, t4, t5, t6, t7, t9, t13, t14, t15, t17, t20** exist but may not correspond to a real deployed nv6 CCU — VERIFY before assigning `fzg_id` (could be stale placeholders).
- Real boxes **t21, t23, t24, t28, t32, t40, t47** have **NO node file** — must be CREATED.
- The existing `external_id: "T4736<box>"` values are box-derived, not real train numbers — they encode the box, not the Fzg.

## Validation rule (must pass before applying)
The set of `fzg_id` values across all node files MUST be unique — no two boxes share a Fzg. (Each physical Fzg exists once; a duplicate = data-entry error.) Assert this after editing.

## Open items
1. Identify CCU IPs for the 7 ❓ trains (then add their boxes).
2. Confirm which t3–t20 node files map to real CCUs vs. are placeholders.
3. Offline rows (t1, t11, t16, t18, t19, t24, t40, t47) are fleet-status-only — re-confirm live when each train is next online before the value is trusted for production render.
