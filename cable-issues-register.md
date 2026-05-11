# DOSTO Fleet — Cable Issues Register

Consolidated log of physical cabling and port-assignment faults found on DOSTO trainsets during Nomad Digital L2 health checks. Add a new row whenever LLDP topology verification or per-port checks reveal a fault that requires Stadler to re-cable, re-patch, or install a missing cable.

This register uses **generic switch IDs only** (A1, A2, A3, B1…B3, C1…C3, D1…D3, E1…E3, F1…F3, G1…G3) and **port labels** (e0-0, e0-1, e0-2, …) — no IPs, no live hostnames, no MACs. The expected topology is whatever the IP-allocation plan / OBN templates define for that consist type.

## Conventions

- **Consist type** — 4-car (A/G/E/B) or 6-car (A/B/C/D/E/F).
- **Status** — `OPEN` (Stadler action pending) · `RESOLVED` (re-verified clean) · `WONTFIX` (accepted as-is, e.g. AP physically not installed).
- **Fault type** —
  - `cable swap` — both cables present but plugged into wrong ports on the same switch
  - `wrong neighbour` — cable goes to the wrong far-end switch
  - `missing trunk` — no LLDP either end, cable absent or unplugged
  - `AP not connected` — AP trunk port admin-enabled but no link / no PoE draw
  - `wrong far-end port` — cable lands on the correct switch but wrong port number

## Open issues — at a glance

| #  | Trainset  | Switch / Port      | Fault type        | Status   |
|----|-----------|--------------------|-------------------|----------|
| 1  | 4734-101  | E2 ↔ B1            | wrong neighbour   | 🔴 OPEN |
| 2  | 4736-108  | C3 e0-0 / e0-1     | cable swap        | 🔴 OPEN |
| 3  | 4736-108  | D1 ↔ E2            | missing trunk     | 🔴 OPEN |
| 4  | 4736-109  | B3 e0-4            | AP not connected  | 🔴 OPEN |
| 5  | 4736-104  | D3 e1-2            | physical-layer    | 🔴 OPEN |

---

### #1 — 4734-101 (4-car) — E2 ↔ B1 wrong neighbour

**What we see:** E2.e0-0 reaches B1 (and B1.e0-1 reaches E2).
**Plan:** E2.e0-0 ↔ E3 (intra-E coach), and B1.e0-1 ↔ E1 (inter-coach E↔B).
**Diagnosis:** the intra-E-coach trunk and the E↔B inter-coach trunk are cross-wired.

**Required action:** re-patch the E-coach end so E2.e0-0 lands on E3, and the inter-coach E↔B trunk lands on E1.e0-0 ↔ B1.e0-1.

**Status:** 🔴 OPEN

---

### #2 — 4736-108 (6-car) — C3 cable swap

**What we see:** C3.e0-0 → C2 and C3.e0-1 → A2.
**Plan:** C3.e0-0 ↔ A2 and C3.e0-1 ↔ C2.
**Diagnosis:** the two trunk cables on C3 are swapped.

**Required action:** swap the two trunk cables on C3. After swap, `show lldp neighbours` on C3 should show e0-0=A2, e0-1=C2.

**Status:** 🔴 OPEN

---

### #3 — 4736-108 (6-car) — D1 ↔ E2 missing trunk

**What we see:** no LLDP peer on either end. Both switches reachable on management VLAN; only this inter-coach link is dark.
**Plan:** D1.e0-1 ↔ E2.e0-1 inter-coach trunk.

**Required action:** locate and reconnect the inter-coach trunk cable between D1 e0-1 and E2 e0-1. If absent, install.

**Status:** 🔴 OPEN

---

### #4 — 4736-109 (6-car) — B3 e0-4 AP not connected

**What we see:** port admin-enabled, link DOWN, PoE drawing 0 W, never seen traffic.
**Plan:** AP attached to B3 e0-4 (AP trunk port).

**Required action:** verify whether an AP is physically installed at B3 position; if yes, connect the patch cable to B3 e0-4.

**Status:** 🔴 OPEN

---

### #5 — 4736-104 (6-car) — D3 e1-2 physical-layer fault

**What we see:** PoE active (~2.5W class-3, device powered) but Ethernet data link never negotiates. Line protocol DOWN, Speed/Duplex stuck at Auto/Auto, no MAC ever learned in switch table, all error counters zero (RX/TX/CRC/carrier-false all 0).

**Diagnosis:** power pairs intact, data pairs failing.

**Confirmed via:** `no configure interface e1-2 enable` / `configure interface e1-2 enable` cycle on 2026-05-09. 120s post-cycle, no link-state transition observed. Discovered during topology validation on box1-t10 (10.179.10.1). 23/24 APs visible.

**Required action — in order, simplest first:**
1. Replace patch cable between AP D4 and switch D3 e1-2 — symptoms suggest damaged data pairs while power pairs are working.
2. If cable replacement doesn't restore link, swap the AP with a known-good unit.
3. If AP swap doesn't help, investigate switch-side of D3 e1-2 (very unlikely — port admin/PoE both functional).

**Status:** 🔴 OPEN

## Resolved issues

*(none yet — move rows from "Open" to here once Stadler confirms re-cable and Nomad re-runs `lldp_topology_check.py` clean)*

## How to add a new entry

1. Run `lldp_topology_check.py` (after applying the consist-specific `EXPECTED_TOPOLOGY` and `SWITCHES`). For non-trunk faults (AP/access-port), use `show interface summary` + `show interface <port> details`.
2. For each MISMATCH or down trunk port, distinguish **template/config issues** (Nomad's responsibility — duplicate hostnames, `dosto-00000000`, missing OBN config) from **physical cabling issues** (Stadler's responsibility — wrong port, missing cable, swapped cables). **Only physical cabling issues belong in this register.**
3. Identify the fault type from the conventions table above.
4. Append a row under "Open issues" with the next sequential `#`. Use generic switch IDs (A1, D2, etc.) and port labels (e0-0, e1-8, etc.) — no IPs, no MACs, no live hostnames.
5. If the fault triggers a per-train Stadler-facing fault report (`Stadler_FzgNNN_*_Cabling_Fault_Report_v1.0.docx`), add a `Report:` link in the action cell.

## Related artefacts

- Per-train Stadler cable-fault reports — `Stadler_Fzg<id>_<consist>_Cabling_Fault_Report_v1.0.docx` (workspace root).
- Topology verification script — [scripts/lldp_topology_check.py](scripts/lldp_topology_check.py).
- Procedure for the LLDP cabling check — [troubleshooting-runbook.md](troubleshooting-runbook.md) → "LLDP Cabling / Topology Check".
- Expected per-train trunk topology — derived from the consist's IP-allocation PDF in `train-ip-allocation-commission/<series>/<series>-NNN/` and from `/etc/obn/template/nv4-*.cfg` or `nv6-*.cfg` on the CCU.
