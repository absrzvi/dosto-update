# DOSTO Commissioning Status — 2026-06-08

**Session:** `/dosto-orchestrate` sess 0900Z · 9 trains · Engineer: Abbas Rizvi

| Train # | Fzg | Switches | OBN / Config | AP Firmware | Status | Outstanding (Stadler) |
|---------|-----|----------|--------------|-------------|--------|----------------------|
| 4736-108 | 136 | 18/18 v8 ✅ | 10/10, vlan7 ✅ | 18/23 (5 deferred) | 🟢 DONE w/ Stadler | A2↔A3 trunk fault + 1 AP absent (cable #7) |
| 4736-109 | 137 | 18/18 v8 ✅ | 10/10, vlan7 ✅ | 12/21 (10 deferred) | 🟢 DONE w/ Stadler | 3 B-coach APs missing (cable #4) |
| 4736-115 | 143 | 18/18 v8 ✅ | 8/8, vlan7 ✅ | 23/24 ✅ | 🟢 DONE w/ Stadler | Coach6 AP4 disconnected (cable #8) |
| 4736-116 | 144 | 18/18 v8 ✅ | 10/10, vlan7 ✅ | 21/24 (3 deferred) | 🟢 DONE | — |
| 4734-112 | 12 | 12/12 v8 ✅ | 9/9, vlan7 ✅ | 8/16 (8 deferred) | 🟢 DONE-PARTIAL | — |
| 4734-114 | 14 | 12/12 v8 ✅ | 10/10, vlan7 ✅ | 7/16 (9 deferred) | 🟢 DONE-PARTIAL | — |
| 4734-115 | 15 | 12/12 v8 ✅ | 8/8, vlan7 ✅ | 9/16 (6 deferred) | 🟢 DONE-PARTIAL | — |
| 4734-122 | 22 | 12/12 v8 ✅ | 10/10, vlan7 ✅ | 10/16 (6 deferred) | 🟢 DONE-PARTIAL | — |
| 4734-109 | 9 | 11/12 v8 | 10/10, vlan7 ✅ | pending | 🟡 DONE-PARTIAL | A1 switch physically absent (cable #10) |

## Legend

- **🟢 DONE** — operationally commissioned, no Nomad action remaining
- **🟢 DONE w/ Stadler** — Nomad work complete; open Stadler cabling item noted
- **🟡 DONE-PARTIAL** — commissioned with deferred AP-firmware items remaining
- **Switches** — count on v8 config at target firmware 7.4.2 (18 expected for 6-car, 12 for 4-car)
- **OBN / Config** — OBN bug-patch count persisted + train_id + vlan7 all verified correct
- **AP Firmware** — count of APs at target 6.11.2-0. "deferred" = firmware staged but partition-swap activation did not complete (m-variant pattern, fleet-wide issue, R&D follow-up)
- **cable #** — reference to Stadler cabling register entry

## Notes

- **All 9 trains have a solid foundation:** switches on v8 config, OBN patched, train identity (train_id) and vlan7 addressing correct.
- **The one systematic gap** is m-variant AP firmware activation ("staged-not-activated" partition-swap wall) — a hardware/firmware issue affecting the fleet, not a per-train failure. Pending R&D.
- **4734-109** switch config required a manual TFTP/SNMP bypass (OBN's standard path could not populate device targets without an NMS connection). Its A1 switch is physically absent from the fabric (Stadler cabling, register #10).
