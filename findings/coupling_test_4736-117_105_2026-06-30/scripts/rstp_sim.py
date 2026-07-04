#!/usr/bin/env python3
"""
RSTP active-topology simulator for nv6 DOSTO consists, single + coupled.

Models per-port path cost and runs Dijkstra from the root bridge to every
switch. The link RSTP BLOCKS in each loop is the highest-cost link on the
unique cycle that is NOT on any switch's least-cost path to root -- i.e. for
each fundamental cycle, the designated/blocked port is the one whose removal
leaves all switches still reached at minimum cost. We approximate the standard
RSTP outcome: build the shortest-path tree (root-port per bridge by lowest
root-path-cost, tie-broken by lower designated-bridge-id), every non-tree link
has exactly one blocking (Alternate) end.

Costs:
  - inter-switch 10G trunk default (uncosted in template): IEEE long-path-cost
    for 10G = 2000. (VDS uses long path-cost; 10G nominal = 2000.)
  - B1<->B3 chord e0-0: 400100 (both ends)
  - couplers e0-2: regime-dependent (template formula OR v9 symmetric 20000)
"""
import heapq, itertools

DEFAULT_TRUNK = 2000      # 10G long-path-cost
CHORD_COST    = 400100    # B1<->B3 e0-0 both ends

# ---- intra-train adjacency from template trunk descriptions (e0-0 / e0-1) ----
# undirected edges (u, v, cost_u_side, cost_v_side, label)
# default trunk unless a custom port-cost is set on that end.
def build_train(t):
    """Return nodes set + list of edges for train prefix t (e.g. '117')."""
    n = lambda s: f"{t}:{s}"
    E = []
    def edge(a,b,ca=DEFAULT_TRUNK,cb=DEFAULT_TRUNK):
        E.append((n(a),n(b),ca,cb))
    # spine (from descriptions, dedup undirected)
    edge("A1","A3"); edge("A1","C1")
    edge("A2","A3"); edge("A2","C3")
    edge("C1","D1")
    edge("C2","C3"); edge("C2","D3")
    edge("D1","E2"); edge("D2","D3"); edge("D2","E1")
    edge("E1","F1"); edge("E2","E3")
    edge("E3","F2")
    edge("F1","B1"); edge("F3","B2"); edge("F2","F3")
    # the B-car chord with custom cost both ends
    edge("B1","B3",CHORD_COST,CHORD_COST)
    edge("B2","B3")
    nodes = set()
    for a,b,_,_ in E: nodes.add(a); nodes.add(b)
    return nodes, E

# ---- coupler cost regimes ----
def coupler_costs(train_id, regime):
    """Return dict port->cost for A1,A3,B1,B3 couplers on one train."""
    if regime == "v9":
        return {"A1":20000,"A3":20000,"B1":20000,"B3":20000}
    # template default: train_id-derived, train_id>=10 branch
    return {
        "A1": train_id*1000000 - 1,
        "A3": train_id*2000000 - 1,
        "B1": train_id*2000000 - 1,
        "B3": train_id*1000000 - 1,
    }

def couple(EA, EB, na, nb, end_a, end_b, ca, cb):
    """Add coupler edges joining train A end_a to train B end_b.
       end in {'A','B'}: A-end uses A1/A3 couplers, B-end uses B1/B3.
       Standard: the two coupler switches at each end pair up (1<->1, 3<->3),
       but a B-to-A coupling pairs A-end(A1,A3) with B-end(B1,B3)."""
    pa = ("A1","A3") if end_a=="A" else ("B1","B3")
    pb = ("A1","A3") if end_b=="A" else ("B1","B3")
    E = list(EA)+list(EB)
    # two physical coupler cables, straight 1<->first, 3<->second
    for sa, sb in zip(pa, pb):
        E.append((f"{na}:{sa}", f"{nb}:{sb}", ca[sa], cb[sb]))
    return E

# ---- RSTP active topology via root-path-cost tree ----
def active_topology(nodes, edges, root):
    # adjacency with per-direction cost (cost applied at RECEIVING port = far end's port cost
    # toward root is the cost of the port on the path; RSTP sums *root-path cost* = sum of
    # segment costs where each segment cost = the cost of the port on the bridge CLOSER to root's
    # downstream... we use the standard: cost to traverse edge = port-cost of the port on the
    # bridge that is FURTHER from root (its root port). Symmetric edges => direction-independent.)
    adj = {x:[] for x in nodes}
    for u,v,cu,cv in edges:
        # traveling u->v, you arrive via v's port (cost cv); v->u via u's port (cost cu)
        adj[u].append((v,cv,(u,v)))
        adj[v].append((u,cu,(u,v)))
    dist={root:0}; pq=[(0,root)]; rootport={}
    while pq:
        d,x=heapq.heappop(pq)
        if d>dist.get(x,1e18): continue
        for (y,c,e) in adj[x]:
            nd=d+c
            if nd<dist.get(y,1e18):
                dist[y]=nd; rootport[y]=e; heapq.heappush(pq,(nd,y))
    tree_edges=set(rootport.values())
    all_edges={(u,v) for u,v,_,_ in edges}
    blocked = all_edges - tree_edges
    return dist, tree_edges, blocked

def edge_cost(edges,e):
    for u,v,cu,cv in edges:
        if (u,v)==e or (v,u)==e: return f"{cu}/{cv}"
    return "?"

def report(title, nodes, edges, root):
    print("="*70); print(title); print("="*70)
    dist,tree,blocked=active_topology(nodes,edges,root)
    print(f"  root = {root}   switches = {len(nodes)}   links = {len(edges)}   blocked = {len(blocked)}")
    for e in sorted(blocked):
        print(f"  BLOCKED: {e[0]:>10} <-> {e[1]:<10}  cost {edge_cost(edges,e)}")
    # sanity: all reachable?
    unreached=[x for x in nodes if x not in dist]
    if unreached: print("  !! UNREACHABLE:", unreached)
    print()
    return blocked

if __name__=="__main__":
    import sys
    regime = sys.argv[1] if len(sys.argv)>1 else "v9"
    tA, tB = "117", "105"
    idA, idB = 145, 133   # Fzg ids
    print(f"\n########## REGIME: {regime}   (couplers: {'symmetric 20000' if regime=='v9' else 'template train_id formula'}) ##########\n")

    # ---- single train ----
    nA,EA = build_train(tA)
    report(f"SINGLE TRAIN {tA} (root D1, chord 400100 present)", nA, EA, f"{tA}:D1")

    # ---- coupled: 3 orientations ----
    nB,EB = build_train(tB)
    nodes = nA|nB
    cA = coupler_costs(idA, regime); cB = coupler_costs(idB, regime)
    root = f"{tA}:D1"  # 117 is MASTER; assume its D1 (priority 0) wins root

    for (ea,eb,name) in [("A","A","A-to-A"),("B","B","B-to-B"),("A","B","A-to-B")]:
        E = couple(EA,EB,tA,tB,ea,eb,cA,cB)
        report(f"COUPLED {name}:  {tA}[{ea}-end] <=> {tB}[{eb}-end]", nodes, E, root)
