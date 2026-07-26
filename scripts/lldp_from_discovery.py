#!/usr/bin/env python3
"""Extract switch LLDP neighbour topology from OBN's /tmp/discovery.json.

Reads the SNMP-gathered neighbour list OBN already collected (no per-switch SSH
needed). Prints each switch's e0-0/e0-1 (backbone trunk) peers so miscabling
shows up as an unexpected neighbour. fv5 backbone is a ring: each switch's
e0-0/e0-1 should connect to the adjacent coach's switch in a consistent order.
"""
import json
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/discovery.json"
d = json.load(open(path))
devs = d["devices"] if isinstance(d, dict) else d

mac2ip = {x.get("mac"): x.get("ip") for x in devs}
mac2name = {x.get("mac"): (x.get("hostname") or x.get("name") or "") for x in devs}


def last(ip):
    return ip.split(".")[-1] if ip else "?"


rows = []
for x in devs:
    ip = x.get("ip") or ""
    if x.get("type") != "SW" and "a0:59:3a" not in (x.get("mac") or ""):
        # keep only switches (and box for reference)
        if x.get("type") != "BOX":
            continue
    nbrs = []
    for n in (x.get("neighbours") or []):
        port = n.get("port", "?")
        pm = n.get("mac")
        if pm in mac2ip:
            peer = "." + last(mac2ip[pm])
            pname = mac2name.get(pm, "")
        else:
            peer = "EXT(" + str(pm)[-8:] + ")"
            pname = ""
        nbrs.append((str(port), peer, pname))
    # sort neighbours by port for readability
    nbrs.sort()
    rows.append((ip, x.get("type"), x.get("mac"), nbrs))

rows.sort(key=lambda r: [int(p) if p.isdigit() else 0 for p in last(r[0]).split() ] or [0])
rows.sort(key=lambda r: last(r[0]))

for ip, typ, mac, nbrs in rows:
    nbstr = "   ".join(f"{p}=>{peer}{(' '+pn) if pn else ''}" for p, peer, pn in nbrs)
    print(f".{last(ip):<4} {str(typ):<4} {mac}  |  {nbstr}")
