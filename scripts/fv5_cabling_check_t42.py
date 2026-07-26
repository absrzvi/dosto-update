#!/usr/bin/env python3
"""Check box1-t41 physical backbone cabling (from LLDP) against expected fv5 ring.

Strategy: don't trust OBN's position labels (suspected scrambled). Instead, take
the physical LLDP adjacency graph on ports 3(e0-0)/4(e0-1) and check whether it
forms the expected fv5 A-C-E-F-B ring *topology* (degree sequence + connectivity),
then try to align it to positions via the CCU anchor.

Expected fv5 backbone (e0-0 far-end, e0-1 far-end) per position:
"""
import json
import sys

# Expected backbone adjacency by POSITION (undirected edges on e0-0/e0-1).
EXPECTED_EDGES = {
    frozenset(["A1", "A3"]), frozenset(["A1", "C1"]),
    frozenset(["A2", "A3"]), frozenset(["A2", "C3"]),
    frozenset(["C1", "E1"]),
    frozenset(["C2", "C3"]), frozenset(["C2", "E3"]),
    frozenset(["E1", "E2"]),  # via? E1 e0-1->C2 ... recompute below
}
# Build expected edges directly from the topology table (e0-0 far, e0-1 far):
TABLE = {
    "A1": ("A3", "C1"), "A2": ("A3", "C3"), "A3": ("A1", "A2"),
    "C1": ("A1", "E1"), "C2": ("C3", "E3"), "C3": ("A2", "C2"),
    "E1": ("F1", "C2"), "E2": ("E3", "C1"), "E3": ("F2", "E2"),
    "F1": ("B1", "E1"), "F2": ("F3", "E3"), "F3": ("B2", "F2"),
    "B1": ("B3", "F1"), "B2": ("B3", "F3"), "B3": ("B1", "B2"),
}
exp_edges = set()
for pos, (a, b) in TABLE.items():
    exp_edges.add(frozenset([pos, a]))
    exp_edges.add(frozenset([pos, b]))

# --- load LLDP-derived physical graph ---
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/discovery.json"))
devs = d["devices"] if isinstance(d, dict) else d
mac2ip = {x.get("mac"): x.get("ip") for x in devs}


def last(ip):
    return ip.split(".")[-1] if ip else "?"


# physical backbone edges: ports 3 & 4 only, between two switches
phys_edges = set()
ccu_links = []
sw_ips = set()
for x in devs:
    if x.get("type") == "BOX":
        continue
    ip = x.get("ip") or ""
    if not ip.startswith("10.179.42.1"):
        continue
    sw_ips.add(last(ip))
    for n in (x.get("neighbours") or []):
        port = str(n.get("port"))
        pm = n.get("mac")
        peer_ip = mac2ip.get(pm)
        if port in ("3", "4"):
            if peer_ip and peer_ip.startswith("10.179.42.1"):
                phys_edges.add(frozenset([last(ip), last(peer_ip)]))
            elif peer_ip and peer_ip.endswith(".1"):
                ccu_links.append((last(ip), port))

# degree per switch in physical backbone
from collections import defaultdict
deg = defaultdict(int)
for e in phys_edges:
    for n in e:
        deg[n] += 1

print("=== physical backbone degree per switch (expect: most=2, ends of ring vary) ===")
for ip in sorted(sw_ips, key=int):
    print(f"  .{ip}: degree {deg[ip]}")

print(f"\n=== switches linking to CCU on port5 (expect 2: C1 & C3) ===")
for ip, port in ccu_links:
    print(f"  .{ip} (port {port})")

print(f"\n=== physical edge count: {len(phys_edges)} | expected ring edge count: {len(exp_edges)} ===")

# Expected degree sequence
exp_deg = defaultdict(int)
for e in exp_edges:
    for n in e:
        exp_deg[n] += 1
from collections import Counter
print("expected degree histogram:", dict(Counter(exp_deg.values())))
print("physical degree histogram:", dict(Counter(deg.values())))
