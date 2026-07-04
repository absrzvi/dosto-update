#!/usr/bin/env python3
"""Extract fv5/fv6 backbone + Stadler-facing topology from an IP-Port-Allocation PDF.

Parses the `e0-0`/`e0-1` "FIS Switch XY" trunk rows (the real inter-switch backbone),
coupler (Frontkupplung), OBS/RDC, Stadler firewall, and AP ports. Emits a
_shared/<schema>-topology.md in the same structure as the nv4/nv6 references.

The raw .cfg description strings are asymmetric/unreliable; the IPA PDF rows are the
authoritative wiring source (per project_fv5_topology_reference).
"""
import pdfplumber, re, sys

def extract(path):
    """Return (fzg, ordered list of switch-blocks) from the PDF.
    Each block: {'sw': 'A1', 'ports': {port: (usage, vlans, ptype)}}"""
    fzg = None
    blocks = []
    cur = None
    cur_sw = None
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            txt = pg.extract_text() or ""
            for ln in txt.splitlines():
                mf = re.search(r'Fzg\.?\s*ID:\s*(\d+)', ln)
                if mf: fzg = int(mf.group(1))
                # a port row; switch label may prefix the port token (e.g. "A1 e1-7 ...")
                m = re.match(r'^(?:([A-F]\d)\s+)?(e[0-9]-\d{1,2})\s+(.*)$', ln)
                if not m:
                    continue
                sw_label, port, rest = m.group(1), m.group(2), m.group(3)
                if sw_label:
                    cur_sw = sw_label
                # start a new block when we see e0-0 (top of a switch's port list)
                if port == 'e0-0':
                    cur = {'sw': None, 'ports': {}}
                    blocks.append(cur)
                if cur is None:
                    continue
                cur['ports'][port] = rest
                # infer switch id from the e0-0/e0-1 "FIS Switch XY" neighbours later
    # assign switch labels: prefer the sw_label captured; else infer from neighbours
    return fzg, blocks

def parse_neighbor(rest):
    m = re.match(r'FIS Switch ([A-F]\d)', rest)
    return m.group(1) if m else None

def build(path, schema, series, coach_order):
    fzg, blocks = extract(path)
    # Determine each block's own switch id: the block whose e0-0 says "FIS Switch X" —
    # X is a NEIGHBOUR, not self. Self-id must come from the sw_label column or by
    # cross-referencing. We reconstruct self-id from the known coach layout + sequence:
    # blocks appear in document order grouped by coach (3 per coach), positions 1,2,3.
    rows = []
    idx = 0
    for coach in coach_order:
        for pos in (1, 2, 3):
            if idx >= len(blocks):
                break
            b = blocks[idx]; idx += 1
            sw = f"{coach}{pos}"
            e00 = parse_neighbor(b['ports'].get('e0-0', ''))
            e01 = parse_neighbor(b['ports'].get('e0-1', ''))
            special = []
            for p, txt in b['ports'].items():
                if 'Firewall' in txt or 'STADLER' in txt:
                    special.append(f"**Stadler FW on {p}**")
                elif txt.startswith('OBS D') or 'OBS D1' in txt:
                    special.append(f"OBS on {p}")
                elif txt.startswith('RDC D') or 'RDC D1' in txt:
                    special.append(f"RDC on {p}")
                elif 'Frontkupplung' in txt:
                    special.append(f"coupler on {p}")
            rows.append((sw, e00, e01, "; ".join(dict.fromkeys(special))))
    return fzg, rows

def emit(schema, series, consist_desc, coach_order, fzg, rows, source_pdf, n_sw, n_ap):
    L = ["---", f"schema: {schema}", f"consist: {consist_desc}",
         f"applies_to: all {series}-1xx trains",
         f"extracted_from: {source_pdf} (Fzg {fzg})",
         "extracted_at: 2026-07-04",
         "extracted_by: scripts/extract_fv_topology.py (pdfplumber, e0-0/e0-1 FIS-Switch rows)",
         "authoritative_source: IP-Port-Allocation PDF trunk rows (raw .cfg descriptions are asymmetric — do not trust)",
         "---", "",
         f"# DOSTO {consist_desc} ({schema}) — Topology Reference", "",
         f"Applies to **every train in the {series}-1xx series**. Per-train values (Fzg ID, "
         "vlan7 IPs) live in the fleet records; this file holds the shared topology.", "",
         f"Coach order (backbone): **{' → '.join(coach_order)}**. "
         f"{n_sw} switches (3/coach) + ~{n_ap} APs.", "",
         "## Inter-coach / intra-coach backbone (from `e0-0`/`e0-1` FIS-Switch rows)", "",
         "| Switch | e0-0 far-end | e0-1 far-end | Special ports |",
         "|---|---|---|---|"]
    for sw, e00, e01, special in rows:
        L.append(f"| {sw} | {e00 or '—'} | {e01 or '—'} | {special or ''} |")
    L += ["", "## Critical Stadler-facing / service trunks", "",
          "| Role | Location | Notes |", "|---|---|---|",
          "| Stadler firewall | A3 `e1-4` | vlan7 transit — this is the **Stadler** FW, not the Nomad CCU |",
          "| Front coupler | A1/A2 `e0-2` | VLANs 100,2,3,5,6,7,8,9,12; DOWN when solo |"]
    if schema == "fv5":
        L += ["| OBS / RDC (CCU coach) | C1 & C3 `e0-2`/`e0-3` | CCU is in **coach C**; OBS 48,90,131,150,200,202; RDC 200,202 |"]
    else:
        L += ["| OBS / RDC (CCU coach) | D1 & D3 `e0-2`/`e0-3` | OBS coach is **D**; OBS 48,90,131,150,200,202; RDC 200,202 |"]
    L += ["| AP trunks | each switch `e0-4` (+ X3 `e1-2` for AP4) | VLANs 100,10,20,30,31,131,150 |", ""]
    L += ["## Notes & caveats", "",
          "- **Backbone is authoritative from these PDF rows**, NOT from the raw `" + schema +
          "-*.cfg` `description` strings — those are hand-typed and asymmetric (both ends "
          "frequently disagree). See [fv5/fv6 topology topic](/.kb/topics/fv5-topology.md).",
          "- `e0-0`/`e0-1` values above are the **neighbour** each port connects to (as the PDF "
          "states it); a full both-ends cross-check may still show minor PDF inconsistencies — "
          "trust live LLDP when commissioning.", ""]
    if schema == "fv5":
        L += ["- fv5 = the 6-car nv6 layout with the **D/300 wagon removed** → 5 coaches, no D. "
              "OBN's `topology.yaml` still numbers the CCU coach as `D=3` internally.", ""]
    L += ["## Cross-references", "",
          "- [fv5/fv6 topology topic (sources + dead ends)](/.kb/topics/fv5-topology.md)",
          "- Fleet records: `/.kb/fleet/" + series + "-1NN.md`", ""]
    return "\n".join(L)

def main():
    jobs = [
        dict(path="train-ip-allocation-commission/4705-xxx/4705-103/4705-103_IP-Port-Allocation.pdf",
             schema="fv5", series="4705", consist="5-car CAT (A-C-E-F-B)",
             coaches=["A","C","E","F","B"], n_sw=15, n_ap=20,
             out="train-ip-allocation-commission/extracted/_shared/fv5-topology.md"),
        dict(path="train-ip-allocation-commission/4706-xxx/4706-101/4706-101_IP-Allocation.pdf",
             schema="fv6", series="4706", consist="6-car FV (A-C-D-E-F-B)",
             coaches=["A","C","D","E","F","B"], n_sw=18, n_ap=24,
             out="train-ip-allocation-commission/extracted/_shared/fv6-topology.md"),
    ]
    for j in jobs:
        fzg, rows = build(j["path"], j["schema"], j["series"], j["coaches"])
        md = emit(j["schema"], j["series"], j["consist"], j["coaches"], fzg, rows,
                  j["path"].split("/")[-1], j["n_sw"], j["n_ap"])
        open(j["out"], "w", encoding="utf-8").write(md)
        print(f"wrote {j['out']}  (Fzg {fzg}, {len(rows)} switch rows)")

if __name__ == "__main__":
    main()
