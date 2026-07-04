---
schema: fv6
consist: 6-car FV (A-C-D-E-F-B)
applies_to: all 4706-1xx trains
extracted_from: 4706-101_IP-Allocation.pdf (Fzg 189)
extracted_at: 2026-07-04
extracted_by: scripts/extract_fv_topology.py (pdfplumber, e0-0/e0-1 FIS-Switch rows)
authoritative_source: IP-Port-Allocation PDF trunk rows (raw .cfg descriptions are asymmetric — do not trust)
---

# DOSTO 6-car FV (A-C-D-E-F-B) (fv6) — Topology Reference

Applies to **every train in the 4706-1xx series**. Per-train values (Fzg ID, vlan7 IPs) live in the fleet records; this file holds the shared topology.

Coach order (backbone): **A → C → D → E → F → B**. 18 switches (3/coach) + ~24 APs.

## Inter-coach / intra-coach backbone (from `e0-0`/`e0-1` FIS-Switch rows)

| Switch | e0-0 far-end | e0-1 far-end | Special ports |
|---|---|---|---|
| A1 | A3 | C1 | coupler on e0-2 |
| A2 | A3 | C3 |  |
| A3 | A1 | A2 | coupler on e0-2; **Stadler FW on e1-4** |
| C1 | A1 | D1 |  |
| C2 | C3 | D3 |  |
| C3 | A2 | C2 |  |
| D1 | C1 | E2 | OBS on e0-2; RDC on e0-3 |
| D2 | D3 | E1 |  |
| D3 | C2 | D2 | OBS on e0-2; RDC on e0-3 |
| E1 | F1 | D2 |  |
| E2 | E3 | D1 |  |
| E3 | F2 | E2 |  |
| F1 | B1 | E1 |  |
| F2 | F3 | E3 |  |
| F3 | B2 | F2 |  |
| B1 | B3 | F1 | coupler on e0-2 |
| B2 | B3 | F3 |  |
| B3 | B1 | B2 | coupler on e0-2 |

## Critical Stadler-facing / service trunks

| Role | Location | Notes |
|---|---|---|
| Stadler firewall | A3 `e1-4` | vlan7 transit — this is the **Stadler** FW, not the Nomad CCU |
| Front coupler | A1/A2 `e0-2` | VLANs 100,2,3,5,6,7,8,9,12; DOWN when solo |
| OBS / RDC (CCU coach) | D1 & D3 `e0-2`/`e0-3` | OBS coach is **D**; OBS 48,90,131,150,200,202; RDC 200,202 |
| AP trunks | each switch `e0-4` (+ X3 `e1-2` for AP4) | VLANs 100,10,20,30,31,131,150 |

## Notes & caveats

- **Backbone is authoritative from these PDF rows**, NOT from the raw `fv6-*.cfg` `description` strings — those are hand-typed and asymmetric (both ends frequently disagree). See [fv5/fv6 topology topic](/.kb/topics/fv5-topology.md).
- `e0-0`/`e0-1` values above are the **neighbour** each port connects to (as the PDF states it); a full both-ends cross-check may still show minor PDF inconsistencies — trust live LLDP when commissioning.

## Cross-references

- [fv5/fv6 topology topic (sources + dead ends)](/.kb/topics/fv5-topology.md)
- Fleet records: `/.kb/fleet/4706-1NN.md`
