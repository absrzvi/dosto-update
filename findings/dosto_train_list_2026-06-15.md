# DOSTO fleet — full train list (live + offline), all fleet types

**Date:** 2026-06-15
**Method:** live sweep of `10.179.<box>.1` (boxes 1–130) reading each CCU's `projectName_21net` fact + vlan7 IP, cross-referenced against fleet-status.md.
**Fzg sources shown side by side:** `Fzg(FS)` = fleet-status documented; `Fzg(v7)` = decoded live from vlan7 (`oct3 = 128 + Fzg//2`, host .2=even / .130=odd). Conflicts flagged.

## Live now (15 boxes)

| Box | Fleet | Train# (FS) | Fzg(FS) | Fzg(v7) | Status |
|---|---|---|---|---|---|
| t8  | nv6 | 4736-108 | 136 | 136 | ok |
| t10 | nv6 | 4736-104 | 132 | 132 | ok |
| t12 | nv6 | 4736-119 | 147 | 147 | ok |
| t21 | nv6 | 4736-118 | 146 | 146 | ok |
| t23 | nv6 | 4736-110 | 138 | 138 | ok |
| t28 | nv6 | 4736-109 | 137 | 137 | ok |
| t15 | nv6 | (FS says 4706-102!) | 190 | 143 | **CONFLICT** — FS attributes box15 to fv6 4706-102; live is nv6, ext_id T4736015. FS box-attribution wrong OR train re-imaged. Needs true Fzg confirmed. |
| t22 | nv6 | (none) | — | 141 | **UNDOCUMENTED** — no fleet-status row for box22; live nv6, vlan7→Fzg 141. ext_id NOT_CONFIGURED. |
| t5  | nv4 | 4734-103 | 3 | 3 | ok |
| t11* | nv4 | — | — | 11 | (box39 live nv4 vlan7→11; see offline note) |
| t12* | nv4 | — | — | 12 | (box37 live nv4 vlan7→12) |
| t14* | nv4 | — | — | 14 | (box44 live nv4 vlan7→14 = 4734-114 ok) |
| t30 | nv4 | 4734-105 | 5 | 30 | **CONFLICT/misimage** — vlan7 decodes to Fzg 30, FS says Fzg 5. Likely misimaged (broken formula). |
| t43 | fv5 | (FS says 4705-102!) | 230 | 171 | **CONFLICT** — FS attributes box43 to 4705-102 (Fzg 230); live is fv5, vlan7→171. FS box-attribution wrong OR re-imaged. |
| t124 | bench | workshop bench | — | (252/garbage) | Bench, not a train — skip. |

*Live nv4 boxes 37/39/44 cross-ref: box44→Fzg14 = 4734-114 (ok); box37→Fzg12 = 4734-112 (FS box=37 ok); box39→Fzg11 = 4734-111 (FS box=39 ok). All three agree with FS.

### Live summary by fleet
- **nv6 (8):** boxes 8, 10, 12, 15, 21, 22, 23, 28
- **nv4 (5):** boxes 5, 30, 37, 39, 44
- **fv5 (1):** box 43
- **bench (1):** box 124

## Conflicts — RESOLVED 2026-06-15 (deep live probe: switch hostnames + OBN literal are authoritative)

**Key lesson:** the **switch hostname** (rendered from the OBN literal) is more authoritative for *intended* Fzg than the vlan7 decode — vlan7 can be separately misimaged. And `128 + box-id` rendering a "Fzg" is the broken-formula fingerprint.

1. **box15 — MISIMAGED, true Fzg UNKNOWN (NOT 4706-102, NOT really 143).**
   - Live: nv6, 18 switches all `nv6-*-v7-143`, OBN line1 = broken `{%- set train_id = 128 + train_id -%}`, ext_id `T4736015`, vlan7 199.130.
   - **Smoking gun: `128 + 15 (box-id) = 143`.** The "143" is the broken formula applied to box-id 15, NOT a real Fzg. Still on **v7** (uncommissioned).
   - Collides with the REAL 4736-115/Fzg143 (documented at box18, v8, commissioned). box15 is a misimaged duplicate; its true physical Fzg is unknown (needs physical inspection).
   - FS fix: box15 is NOT 4706-102 (that attribution removed). Live example of the exact misimage bug the fzg_id fix targets.

2. **box43 — fv5 Fzg 230 = 4705-102 (FS attribution CORRECT).**
   - Switch hostname `fv5-E3-v7-230` confirms Fzg **230**. vlan7 (171) is separately misimaged — ignore it; hostname wins.
   - Uncommissioned (v7). FS box43→4705-102/Fzg230 stands.

3. **box30 — nv4 Fzg 5 = 4734-105 (FS attribution CORRECT).**
   - Switch hostname `nv4-B1-v4-005` confirms Fzg **5**. On old **v4** firmware; vlan7 misimaged to 30. FS box30→4734-105/Fzg5 stands; train just uncommissioned.

4. **box22 — nv6 Fzg 141 = 4736-113 (FS was INCOMPLETE — box was ❓).**
   - OBN literal `train_id = 141` (clean hardcode), hostname `nv6-A3-v8-141`, **v8 commissioned**. This IS 4736-113. FS updated: CCU `10.179.22.1`.

### Net: 2 real FS errors fixed (box15 fleet mis-attribution, box22 missing IP); 2 were misimaged trains where FS attribution was already correct (box30, box43).
### ⚠️ DUPLICATE Fzg 143 IN THE WILD: box15 (misimaged, v7) and box18 (real 4736-115, v8) both render Fzg 143 + vlan7 199.130. If both reach Stadler simultaneously = IP conflict. box15 must be re-imaged to its true Fzg before it is service-coupled or Stadler-reachable.

## Full roster (offline trains, from fleet-status — UNVERIFIED, re-confirm live when online)

### 4736 / nv6 (6-Teiler), Fzg = train# + 28
| Train# | Fzg | Box | Live |
|---|---|---|---|
| 4736-101 | 129 | ? | offline (CCU IP unknown) |
| 4736-102 | 130 | 47 | offline |
| 4736-103 | 131 | 11 | offline |
| 4736-104 | 132 | 10 | **ONLINE** |
| 4736-105 | 133 | 1 | offline |
| 4736-106 | 134 | 19 | offline |
| 4736-107 | 135 | ? | offline (CCU IP unknown) |
| 4736-108 | 136 | 8 | **ONLINE** |
| 4736-109 | 137 | 28 | **ONLINE** |
| 4736-110 | 138 | 23 | **ONLINE** |
| 4736-111 | 139 | 24 | offline |
| 4736-112 | 140 | 40 | offline |
| 4736-113 | 141 | ? | offline (CCU IP unknown — but box22 live = Fzg 141! likely this train) |
| 4736-114 | 142 | ? | offline (CCU IP unknown) |
| 4736-115 | 143 | 18 | offline (but box15 live decodes 143 — see conflict 1) |
| 4736-116 | 144 | 16 | offline |
| 4736-117 | 145 | 32 | offline |
| 4736-118 | 146 | 21 | **ONLINE** |
| 4736-119 | 147 | 12 | **ONLINE** |
| 4736-120 | 148 | 2 | offline |
| 4736-121 | 149 | ? | offline (CCU IP unknown) |
| 4736-122 | 150 | ? | offline (CCU IP unknown) |
| 4736-123 | 151 | ? | offline (CCU IP unknown) |

### 4734 / nv4 (4-Teiler), Fzg = train# − 100
| Train# | Fzg | Box | Live |
|---|---|---|---|
| 4734-101 | 1 | 4 | offline |
| 4734-102 | 2 | ? | offline |
| 4734-103 | 3 | 5 | **ONLINE** |
| 4734-104 | 4 | ? | offline |
| 4734-105 | 5 | 30 | **ONLINE** (CONFLICT — vlan7→30) |
| 4734-106 | 6 | ? | offline |
| 4734-107 | 7 | ? | offline |
| 4734-108 | 8 | 29 | offline |
| 4734-109 | 9 | 38 | offline |
| 4734-110 | 10 | 36 | offline |
| 4734-111 | 11 | 39 | **ONLINE** |
| 4734-112 | 12 | 37 | **ONLINE** |
| 4734-113 | 13 | 46 | offline |
| 4734-114 | 14 | 44 | **ONLINE** |
| 4734-115 | 15 | 61 | offline |
| 4734-116 | 16 | 3 | offline |
| 4734-117 | 17 | 14 | offline |
| 4734-118 | 18 | 48 | offline |
| 4734-119 | 19 | 45 | offline |
| 4734-120 | 20 | 49 | offline |
| 4734-121 | 21 | 50 | offline |
| 4734-122 | 22 | 53 | offline |
| 4734-123 | 23 | 67 | offline |
| 4734-190 | 90 | 54 | offline |

### 4705 / fv5, Fzg = train# + 128
| Train# | Fzg | Box | Live |
|---|---|---|---|
| 4705-101 | 229 | 42 | offline |
| 4705-102 | 230 | 43 | **ONLINE?** (box43 live = fv5 vlan7→171 — CONFLICT 2) |
| 4705-103 | 231 | 41 | offline |

### 4706 / fv6, Fzg = train# + 88
| Train# | Fzg | Box | Live |
|---|---|---|---|
| 4706-101 | 189 | ? | offline |
| 4706-102 | 190 | 15 | offline (but box15 live = nv6! — CONFLICT 1) |
| 4706-103 | 191 | 17 | offline |

## Notes
- vlan7 decode is the most reliable live Fzg source (external_id is mostly `NOT_CONFIGURED`; box fact = box-id not Fzg).
- "Box" = box-id from CCU IP `10.179.<box>.1`. Box→Fzg is an arbitrary physical assignment, not computable.
- 9 trains have unknown CCU IP (`box=?`) — cannot probe until IP identified.
- Offline rows are fleet-status-sourced and UNVERIFIED; re-confirm via vlan7 decode when each train next comes online.
- fv6 (4706, boxes 61-73) and fv5 (4705, boxes 101-103) node-file boxes were all offline this sweep.
