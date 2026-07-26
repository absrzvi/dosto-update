#!/usr/bin/env python3
"""Derive true switch positions on box1-t41 from the LLDP backbone ring.

Anchors:
- CCU (.1) connects to the two C-coach switches (C1, C3) — they carry port 5->.1
- The ring on ports 3/4 is walked from those anchors.

fv5 coach order A - C - E - F - B, CCU in coach C. Per topology:
  C1 e0-0->A1, e0-1->E1   |  C3 e0-0->A2, e0-1->C2
So from a CCU-facing switch, one backbone direction heads into the A coach,
the other into the E/F/B coaches. We label by walking and using the AP/ap-count
and coupler ends to distinguish A-end vs B-end.

This script just prints the ring order + adjacency so we can hand-assign
positions with the topology table, rather than trust OBN's (scrambled) labels.
"""
import json, sys
from collections import defaultdict

d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/discovery.json"))
devs = d["devices"] if isinstance(d, dict) else d
m2ip = {x.get("mac"): x.get("ip") for x in devs}
def L(ip): return ip.split(".")[-1] if ip else "?"

# backbone adjacency (ports 3/4), switch<->switch only
adj = defaultdict(dict)   # ip -> {port: peer_ip}
ccu_facing = []
for x in devs:
    ip = x.get("ip") or ""
    if not ip.startswith("10.179.41.1") or x.get("type") == "BOX":
        continue
    for n in (x.get("neighbours") or []):
        port = str(n.get("port")); peer = m2ip.get(n.get("mac"))
        if port in ("3", "4") and peer and peer.startswith("10.179.41.1"):
            adj[L(ip)][port] = L(peer)
        if port == "5" and peer and peer.endswith(".1"):
            ccu_facing.append(L(ip))

print("CCU-facing switches (C-coach, port5->.1):", ccu_facing)

# Walk the ring: start at first CCU-facing switch, follow unused edges
start = ccu_facing[0]
order = [start]
visited = {start}
cur = start
prev = None
while True:
    nxts = [p for p in adj[cur].values() if p != prev]
    # pick an unvisited neighbour to continue the ring
    nxt = None
    for p in nxts:
        if p not in visited:
            nxt = p; break
    if nxt is None:
        # ring closed or dead-end
        break
    order.append(nxt); visited.add(nxt); prev, cur = cur, nxt

print("ring walk order from", start, ":")
print("  " + " -> ".join("." + o for o in order))
print("switches not in walk (branch/degree>2 or unreached):",
      sorted(set(adj.keys()) - set(order), key=lambda z: int(z)))

print("\nfull backbone adjacency:")
for ip in sorted(adj, key=lambda z: int(z)):
    print(f"  .{ip}: " + "  ".join(f"{p}=>.{q}" for p, q in sorted(adj[ip].items())))
