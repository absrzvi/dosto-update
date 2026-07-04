#!/usr/bin/env python3
"""Generate .kb/fleet/<train>.md records from fleet-status.md (authoritative source).

Per-train reference fields: train name, Fzg ID, box-id, CCU 10.179.x.x IP, Zabbix host
group, vlan7 IPs, topology (series -> shared ref), plus status summary + CCU-IP history.

Does NOT overwrite the 8 hand-written rich records (they have investigation history the
table can't hold). Emits the rest as reference records + rewrites fleet/index.md.
"""
import re, os, sys

FS = "fleet-status.md"
OUT = ".kb/fleet"
os.makedirs(OUT, exist_ok=True)

# 8 hand-written rich records to preserve (do not regenerate)
RICH = {"4736-105","4736-114","4736-119","4734-119","4734-109","4705-101",
        "box1-t40-fzg140","4736-117-105-coupling"}
# box1-t40-fzg140 IS train 4736-112 — skip that train# too so we don't double up
RICH_TRAINS = {"4736-105","4736-114","4736-119","4734-119","4734-109","4705-101","4736-112"}

SERIES = {
    "4736": dict(schema="nv6", consist="6-car (A-C-D-E-F-B)", cars=6,
                 topo="/train-ip-allocation-commission/extracted/_shared/nv6-topology.md",
                 sw=18, ap=24, hostpfx="nv6"),
    "4734": dict(schema="nv4", consist="4-car", cars=4,
                 topo="/train-ip-allocation-commission/extracted/_shared/nv4-topology.md",
                 sw=12, ap=16, hostpfx="nv4"),
    "4705": dict(schema="fv5", consist="5-car CAT (A-C-E-F-B, D/300 removed)", cars=5,
                 topo="/train-ip-allocation-commission/extracted/_shared/fv5-topology.md",
                 sw=15, ap=20, hostpfx="fv5"),
    "4706": dict(schema="fv6", consist="6-car FV (A-C-D-E-F-B)", cars=6,
                 topo="/train-ip-allocation-commission/extracted/_shared/fv6-topology.md",
                 sw=18, ap=24, hostpfx="fv6"),
}

def vlan7(fzg):
    o3 = 128 + (fzg // 2)
    ccu_host = 130 if (fzg % 2) else 2
    fw_host  = 129 if (fzg % 2) else 1
    return f"172.19.{o3}.{ccu_host}/17", f"172.19.{o3}.{fw_host}"

IP_RE = re.compile(r'10\.179\.(\d+)\.1')

def parse_rows():
    txt = open(FS, encoding="utf-8").read()
    rows = []
    for line in txt.splitlines():
        m = re.match(r'^\|\s*(47\d{2}-\d{3})\s*\|', line)
        if not m: continue
        cols = [c.strip() for c in line.split('|')[1:-1]]
        train = cols[0]
        fzg = None
        mf = re.match(r'^\d+$', cols[1].strip('`* '))
        if mf: fzg = int(cols[1].strip('`* '))
        ipm = IP_RE.search(cols[2])
        box = int(ipm.group(1)) if ipm else None
        ccu = f"10.179.{box}.1" if box is not None else None
        nomad = cols[3] if len(cols) > 3 else ""
        rows.append(dict(train=train, fzg=fzg, box=box, ccu=ccu, nomad=nomad))
    return rows

def status_flag(nomad):
    for k in ("DONE","PAUSED","UNKNOWN","BLOCKED","ERROR"):
        if k in nomad.upper(): return k
    return "UNKNOWN"

def render(r):
    series = r["train"].split("-")[0]
    s = SERIES.get(series, {})
    fzg, box = r["fzg"], r["box"]
    fzg_s = str(fzg) if fzg is not None else "❓ (see fleet-status)"
    box_s = str(box) if box is not None else "❓"
    zbx = f"50_6{box}" if box is not None else "❓"
    v7c, v7fw = vlan7(fzg) if fzg is not None else ("❓","❓")
    hostpfx = s.get("hostpfx","?")
    host_render = f"{hostpfx}-<pos>-v8-{fzg}" if fzg is not None else f"{hostpfx}-<pos>-v8-<fzg>"
    flag = status_flag(r["nomad"])
    box_ne_fzg = (fzg is not None and box is not None and box != fzg)

    L = []
    L += ["---",
          "type: train-record",
          f"title: {r['train']} — Fzg {fzg_s}",
          f'description: "Train-level reference for {r["train"]} (Fzg {fzg_s}) — box-id, CCU IP, Zabbix host, vlan7, topology."',
          f"train: {r['train']}",
          f"fzg: {fzg if fzg is not None else 'null'}",
          f"box_id: {box if box is not None else 'null'}",
          f"ccu_ip: {r['ccu'] or 'null'}",
          f"ccu_host: box1-t{box}" if box is not None else "ccu_host: null",
          f"zabbix_host_group: {zbx}",
          f"series: {series}",
          f"schema: {s.get('schema','?')}",
          "project: dosto-neu",
          f"tags: [{series}, {s.get('schema','?')}, fleet-record, {flag.lower()}]",
          "maturity: reported",
          "timestamp: 2026-07-04T00:00:00Z",
          "---",
          "",
          f"# {r['train']} — Fzg {fzg_s}",
          "",
          "> Reference record. Live commissioning state is in "
          "[fleet-status.md](/fleet-status.md) (authoritative, positionally-parsed — read it, "
          "don't edit from here). This record holds the stable train-level identity + topology.",
          "",
          "## Identity",
          "",
          "| Field | Value |",
          "|---|---|",
          f"| Train name (Nomad) | `{r['train']}` |",
          f"| Fzg ID (ÖBB) | {fzg_s} |",
          f"| Box-id | {box_s} |",
          f"| CCU IP | `{r['ccu'] or '❓'}` |",
          f"| CCU host | `box1-t{box}`" + " |" if box is not None else "| CCU host | ❓ |",
          f"| Zabbix host group | `{zbx}_*`  *(updates on box=Fzg migration → `50_6{fzg}_*`)* |" if fzg is not None else f"| Zabbix host group | `{zbx}_*` |",
          f"| Series / schema | {series} / {s.get('schema','?')} |",
          f"| Consist | {s.get('consist','?')} |",
          "",
    ]
    if box_ne_fzg:
        L += [f"> ℹ️ **box-id ({box}) ≠ Fzg ({fzg}) — this is normal.** Two independent namespaces: "
              f"the **box-id** ({box}) drives the CCU IP (`10.179.{box}.1`) and Zabbix host "
              f"(`50_6{box}`); the **Fzg** ({fzg}) drives switch hostnames and vlan7. They are *not* "
              "meant to match on 6-car/CAT/FV. **What WOULD be a misimage:** live switch hostnames "
              f"or vlan7 encoding the box-id ({box}) instead of the Fzg ({fzg}) — e.g. a hostname "
              f"`{hostpfx}-A1-v8-{box}` or vlan7 derived from {box}. Trust live `dhcp-lease-list`; "
              "flag any such disagreement. See "
              "[Fzg-ID two-namespaces](/.kb/topics/fzg-id-two-namespaces.md).",
              ""]

    L += ["## vlan7 (Stadler FIS) addressing",
          "",
          "Computed from Fzg via the bit-packed scheme — see "
          "[vlan7 addressing](/.kb/topics/vlan7-addressing.md).",
          "",
          "| Endpoint | IP |",
          "|---|---|",
          f"| CCU vlan7 | `{v7c}` |",
          f"| Stadler FW peer | `{v7fw}` |",
          "",
          "## Topology",
          "",
    ]
    if s.get("topo"):
        L += [f"- **{s.get('sw','?')} switches**, **{s.get('ap','?')} APs** — full port-level "
              f"topology (switch positions, AP→port map, inter-coach + Stadler-facing trunks) "
              f"in [{s.get('schema','?')} topology reference]({s['topo']}).",
              f"- Switch hostnames render as `{host_render}` (one per position).",
              ""]
    else:
        L += [f"- **{s.get('sw','?')} switches**, **{s.get('ap','?')} APs** (fv6). "
              "No shared topology reference file yet — nearest analog is the "
              "[fv5 topology](/.kb/topics/fv5-topology.md) and the nv6 6-car layout.",
              f"- Switch hostnames render as `{host_render}`.",
              ""]

    L += ["## Current state (snapshot — see fleet-status for live detail)",
          "",
          f"Status: **{flag}**.",
          ""]
    # trim the nomad cell to a lead sentence for context, avoid dumping the whole essay
    lead = re.split(r'(?<=[.)])\s', r["nomad"].replace("**",""), maxsplit=1)[0][:400]
    if lead.strip():
        L += ["> " + lead.strip(), ""]

    asset_line = (f"- [Allocation assets (PDFs + cfgs)](/.kb/assets/{r['train']}.md)"
                  if os.path.exists(f"{OUT}/../assets/{r['train']}.md")
                  else f"- Allocation assets: none on disk for {r['train']} "
                       "(no per-train folder in `train-ip-allocation-commission/`)")
    L += ["## Related",
          "",
          asset_line,
          "- [VDS switch behaviour](/.kb/components/vds-consist-switch/cli-and-management.md)",
          "- [Nomad Connect / OBN](/.kb/components/nomad-connect-obn/index.md)",
          "- [L2 health methodology](/.kb/topics/l2-health-methodology.md)",
          "- [Zabbix / NMS model](/.kb/topics/zabbix-nms-model.md)",
          "- [Fleet index](/.kb/fleet/index.md)",
          "- Live state: [fleet-status.md](/fleet-status.md)",
          ""]
    return "\n".join(L)

def main():
    rows = parse_rows()
    written, skipped = [], []
    for r in rows:
        if r["train"] in RICH_TRAINS:
            skipped.append(r["train"]); continue
        open(f"{OUT}/{r['train']}.md","w",encoding="utf-8").write(render(r))
        written.append(r["train"])

    # rebuild index
    all_recs = sorted(set(written) | RICH_TRAINS | {"box1-t40-fzg140","4736-117-105-coupling"})
    idx = ["---","type: fleet-index","title: Fleet — per-train records",
           "description: One reference record per train: identity (Fzg/box-id/CCU IP/Zabbix host), vlan7, topology, and current-state snapshot.",
           "project: dosto-neu","timestamp: 2026-07-04T00:00:00Z","---","",
           "# Fleet — per-train records","",
           "Each record holds the stable train-level identity and topology; live commissioning "
           "state lives in [fleet-status.md](/fleet-status.md). Records marked ★ are hand-written "
           "and carry extra investigation history.","",
           "| Train | Fzg | Box-id | CCU IP | Zabbix host | Series |","|---|---|---|---|---|---|"]
    by_train = {r["train"]: r for r in rows}
    for t in sorted(by_train):
        r = by_train[t]
        star = " ★" if t in RICH_TRAINS else ""
        fzg = r["fzg"] if r["fzg"] is not None else "❓"
        box = r["box"] if r["box"] is not None else "❓"
        zbx = f"50_6{r['box']}" if r["box"] is not None else "❓"
        series = t.split("-")[0]
        # rich train 4736-112 is documented under box1-t40-fzg140.md
        link = "box1-t40-fzg140" if t=="4736-112" else t
        idx.append(f"| [{t}]({link}.md){star} | {fzg} | {box} | `{r['ccu'] or '❓'}` | `{zbx}_*` | {series} |")
    idx += ["","## Special records","",
            "* [box1-t40-fzg140](box1-t40-fzg140.md) ★ - train 4736-112 (Fzg 140), documented by CCU box.",
            "* [4736-117-105-coupling](4736-117-105-coupling.md) ★ - the coupled multitraction test pair.",
            "","> ★ = hand-written record with investigation history. Others are generated from "
            "fleet-status.md identity + computed fields.",""]
    open(f"{OUT}/index.md","w",encoding="utf-8").write("\n".join(idx))

    print(f"wrote {len(written)} generated records; preserved {len(skipped)} rich records: {sorted(skipped)}")
    print("index rebuilt with", len(by_train), "train rows")

if __name__ == "__main__":
    main()
