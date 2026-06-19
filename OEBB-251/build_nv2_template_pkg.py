#!/usr/bin/env python3
"""
Assemble the nd-obn-template-dostoneu-nv2 package source tree.

Base = field-tested OEBB-251/2t-bench-*-v4.cfg (CCU/OBS port e0-3 enabled,
bench-correct VLAN pruning) -- NOT nv4 (whose e0-3 is 'no enable', which would
isolate the CCU). Only transform: hostname -> Jinja nv2-<pos>-v8-{{train_id}}
so OBN renders per-train, consistent with nv4/nv6.

Shared files (dhcp_groups, vlans.j2, dostoneu-obn.cfg, firmware) copied from the
nv4 reference we pulled from git. rules.yaml written fresh for the 2-coach map.

Output: OEBB-251/nv2-template-src/<repo layout> ready to push to a new
onboard/nd-obn-template-dostoneu-nv2 repo (or hand to R&D).
"""
import re, shutil
from pathlib import Path

ROOT = Path("C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/OEBB-251")
BENCH = ROOT                                   # 2t-bench-*-v4.cfg live here
NV4REF = ROOT / "nv2-template-src" / "_nv4-reference"
OUT = ROOT / "nv2-template-src"
TPL = OUT / "src" / "etc" / "obn" / "template"
DHCP = TPL / "dhcp_groups"
DHCP.mkdir(parents=True, exist_ok=True)

# 1) Switch cfgs: 2t-bench-<pos>-v4.cfg -> nv2-1/2 00-<pos>.cfg, hostname transformed
SW = {  # bench source pos -> (coach hundred, output filename, hostname pos)
    "A1": ("100", "nv2-100-A1.cfg", "A1"),
    "A2": ("100", "nv2-100-A2.cfg", "A2"),
    "A3": ("100", "nv2-100-A3.cfg", "A3"),
    "B1": ("200", "nv2-200-B1.cfg", "B1"),
    "B2": ("200", "nv2-200-B2.cfg", "B2"),
    "B3": ("200", "nv2-200-B3.cfg", "B3"),
}
HOST_RE = re.compile(r'^system hostname .*$', re.M)
for pos,(hund,outfn,hpos) in SW.items():
    src = (BENCH / f"2t-bench-{pos}-v4.cfg").read_text()
    new_host = 'system hostname nv2-%s-v8-{{ ("%%03d"|format(train_id)) }}' % hpos
    src = HOST_RE.sub(new_host, src, count=1)
    (TPL / outfn).write_text(src)
    print("switch:", outfn, "<- 2t-bench-%s-v4.cfg (hostname -> %s)" % (pos, new_host))

# 2) Shared files from nv4 reference
for rel in ["template/vlans.j2", "template/dostoneu-obn.cfg"]:
    shutil.copy(NV4REF / rel, TPL / Path(rel).name); print("shared:", rel)
for g in ["afz","energiezaehler","fis","reservierung","service","sprechstelle","video"]:
    fn = f"{g}_group.j2"; shutil.copy(NV4REF / "template/dhcp_groups" / fn, DHCP / fn)
print("shared: dhcp_groups/* (7)")

# 3) rules.yaml for the 2-coach map
RULES = '''---
config_rules:
  - coach_number: [1]
    device_number: 1
    type: "SW"
    target:
      config: "nv2-A1-v8"
      template: "nv2-100-A1.cfg"
  - coach_number: [1]
    device_number: 2
    type: "SW"
    target:
      config: "nv2-A2-v8"
      template: "nv2-100-A2.cfg"
  - coach_number: [1]
    device_number: 3
    type: "SW"
    target:
      config: "nv2-A3-v8"
      template: "nv2-100-A3.cfg"

  - coach_number: [2]
    device_number: 1
    type: "SW"
    target:
      config: "nv2-B1-v8"
      template: "nv2-200-B1.cfg"
  - coach_number: [2]
    device_number: 2
    type: "SW"
    target:
      config: "nv2-B2-v8"
      template: "nv2-200-B2.cfg"
  - coach_number: [2]
    device_number: 3
    type: "SW"
    target:
      config: "nv2-B3-v8"
      template: "nv2-200-B3.cfg"

  # APs: bench physically has 1 AP (coach 1 / device 1 on A1.e0-4); rules kept
  # for all 4 device slots per coach for spec parity (absent APs never discovered).
  - device_number: 1
    coach_number: [1,2]
    type: "AP"
    target:
      config: "AP1-v1"
      template: "dostoneu-obn.cfg"
      wirelessModulation0: 3
      wirelessModulation1: 10
      wirelessBandwidth: 0
      wirelessFreq: 2412
  - device_number: 2
    coach_number: [1,2]
    type: "AP"
    target:
      config: "AP2-v1"
      template: "dostoneu-obn.cfg"
      wirelessModulation0: 28
      wirelessModulation1: 28
      wirelessBandwidth: 5
      wirelessFreq: 5180
  - device_number: 3
    coach_number: [1,2]
    type: "AP"
    target:
      config: "AP3-v1"
      template: "dostoneu-obn.cfg"
      wirelessModulation0: 28
      wirelessModulation1: 28
      wirelessBandwidth: 5
      wirelessFreq: 5220
  - device_number: 4
    coach_number: [1,2]
    type: "AP"
    target:
      config: "AP4-v1"
      template: "dostoneu-obn.cfg"
      wirelessModulation0: 3
      wirelessModulation1: 10
      wirelessBandwidth: 0
      wirelessFreq: 2462

firmware_rules:
  - type: "SW"
    target:
      firmware: "7.4.2"
      binary: "ipart-ng.kad-7-4-2"
  - type: "AP"
    target:
      firmware: "6.11.2-0"
      binary: "IBEX-firmware-6.11.2-0.img"
'''
(OUT / "src" / "etc" / "obn" / "rules.yaml").write_text(RULES)
print("rules.yaml: written (coach 1=A, coach 2=B)")

# 4) build.sh (fpm), version, README
BUILD = '''#!/bin/bash

rm -rf *.deb

version=$(/bin/cat version)
maintainer="Nomad Digital"
name="nd-obn-template-dostoneu-nv2"
url="http://nomad-digital.com"
description="Nomad Digital OBN Templates for Dosto Neu train type nv2 (2-coach bench)"
vendor="Nomad Digital"

fpm -s dir \
    -t deb \
    -f \
    -n "${name}" \
    -v "${version}" \
    -a all \
    -m "${maintainer}" \
    --deb-no-default-config-files \
    --url "${url}" \
    --description "${description}" \
    --vendor "${vendor}" \
    --provides "${name}" \
    src/=/
'''
(OUT / "build.sh").write_text(BUILD)
(OUT / "version").write_text("0.0.1\n")
(OUT / "README.md").write_text(
    "DOSTO NEU NV2 SWITCH/AP CONFIG (2-coach bench, OEBB-251)\n"
    "- 0.0.1 initial: 6 switches (A1/A2/A3 coach1, B1/B2/B3 coach2) based on field-tested\n"
    "  2t-bench-v4 cfgs; hostname -> nv2-<pos>-v8-{{train_id}}; CCU on A1.e0-3 (OBS trunk);\n"
    "  firewall on A3.e1-4; inter-coach A1.e0-1<->B1.e0-1. Pairs with report_dosto_neu.py\n"
    "  nv2 patch (ccu1_coach=1,max_coach=2) + per-node hiera train_type: nv2.\n"
)
(OUT / ".gitignore").write_text("*.deb\n")
print("build.sh / version(0.0.1) / README.md / .gitignore: written")
print("\nDONE. Tree under:", OUT)
