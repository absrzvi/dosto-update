#!/usr/bin/env python3
"""Regenerate the nv6 / nv4 port-map snapshots consumed by gen_notfound_register.py.

Reads the OBN switch-config templates (nv{4,6}-*.cfg) from the local template clones
and emits one `switch|port|enable|description` line per interface block, matching the
format of findings/nv{6,4}_port_map_YYYYMMDD.txt.

Each `interface <port>` block contributes exactly one row:
  - enable  = 1 if the block contains a bare `enable` line, else 0 (`no enable`)
  - description = the quoted string on the block's `description` line, else empty
A port can be `no enable` yet still carry a description (e.g. Funksensor) — both are
recorded independently, exactly as the register join expects.

Usage:
  python scripts/gen_port_map.py                # writes findings/nv{6,4}_port_map_<today>.txt
  python scripts/gen_port_map.py --date 20260713 # force the date stamp in the filename
The switch key is the final hyphen segment of the cfg filename (nv6-100-A1 -> A1).
"""
import argparse
import datetime
import os
import re
from pathlib import Path

HOME = Path(os.path.expanduser("~")) / "Documents"
FLEETS = {
    "nv6": HOME / "nomad-obn-template-nv6" / "src/etc/obn/template",
    "nv4": HOME / "nomad-obn-template-nv4" / "src/etc/obn/template",
}

IFACE_RE = re.compile(r"^\s*interface\s+(\S+)\s*$")
DESC_RE = re.compile(r'^\s*description\s+"(.*)"\s*$')


def parse_cfg(path: Path):
    """Yield (port, enable, description) for each interface block in a cfg file."""
    port = None
    desc = ""
    enabled = 0
    have_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        m = IFACE_RE.match(line)
        if m:
            if have_block:
                yield port, enabled, desc
            port, desc, enabled, have_block = m.group(1), "", 0, True
            continue
        if not have_block:
            continue
        dm = DESC_RE.match(line)
        if dm:
            desc = dm.group(1)
        elif re.match(r"^\s*no\s+enable\s*$", line):
            enabled = 0
        elif re.match(r"^\s*enable\s*$", line):
            enabled = 1
    if have_block:
        yield port, enabled, desc


def switch_key(cfg_name: str) -> str:
    # nv6-100-A1.cfg -> A1 ; nv4-300-G1.cfg -> G1
    return cfg_name.rsplit(".", 1)[0].rsplit("-", 1)[-1]


def build(fleet: str, tpl_dir: Path) -> list[str]:
    lines = []
    cfgs = sorted(tpl_dir.glob(f"{fleet}-*.cfg"))
    if not cfgs:
        raise SystemExit(f"no {fleet}-*.cfg found under {tpl_dir}")
    for cfg in cfgs:
        sw = switch_key(cfg.name)
        for port, enable, desc in parse_cfg(cfg):
            # Skip vlan SVIs (vlan1/vlan100) — the register joins on physical
            # e0-*/e1-* ports only, and the original snapshots omit SVIs.
            if port.startswith("vlan"):
                continue
            lines.append(f"{sw}|{port}|{enable}|{desc}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().strftime("%Y%m%d"),
                    help="date stamp for the output filename (YYYYMMDD)")
    ap.add_argument("--out-dir", default="findings")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for fleet, tpl_dir in FLEETS.items():
        rows = build(fleet, tpl_dir)
        out = os.path.join(args.out_dir, f"{fleet}_port_map_{args.date}.txt")
        Path(out).write_text("\n".join(rows) + "\n", encoding="utf-8")
        n_en = sum(1 for r in rows if r.split("|")[2] == "1")
        print(f"wrote {out}: {len(rows)} ports ({n_en} enabled) across "
              f"{len(set(r.split('|')[0] for r in rows))} switches")


if __name__ == "__main__":
    main()
