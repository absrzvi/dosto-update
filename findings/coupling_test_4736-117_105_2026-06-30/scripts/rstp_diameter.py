#!/usr/bin/env python3
"""
RSTP DIAMETER / Max-Age budget check for coupled DOSTO consists.

The real RSTP limit is NOT a raw node count -- it is the BPDU 'message age'
budget. Each bridge a BPDU traverses from the root increments message age by
(at least) 1 (the IEEE-recommended per-hop increment; many stacks use 1s).
A BPDU is discarded when message_age >= Max Age. So the protocol works only if:

        (longest root-to-leaf HOP COUNT)  <=  Max Age - 1

VDS switch: Max Age default 20s, per-hop increment 1s (IEEE 802.1D-2004).
=> safe bridge diameter from root <= 19 hops (IEEE conservative design figure
   for classic STP is a diameter of 7 with default timers; 802.1w/RSTP relaxes
   timing but the message-age cap is the hard wall). We report the worst-case
   hop distance from root and flag against both the conservative (7) and the
   absolute message-age (Max Age - 1) ceilings.

Default inter-switch PortPathCost on this VDS switch = 200000 (per manual Table 4).
"""
import heapq, importlib.util, sys
spec=importlib.util.spec_from_file_location("s","rstp_sim.py")
base=importlib.util.module_from_spec(spec); sys.argv=["x"]; spec.loader.exec_module(base)

# correct the default trunk cost to the VDS factory default
base.DEFAULT_TRUNK = 200000
CHORD = base.CHORD_COST  # 400100

MAXAGE = 20
PERHOP = 1
HARD_HOP_CEIL = MAXAGE - PERHOP          # message-age wall = 19
CONSERVATIVE  = 7                         # classic STP recommended diameter

def hops_from_root(nodes, edges, root):
    """BFS-style hop distance over the ACTIVE (post-RSTP) tree only."""
    dist,tree,blocked = base.active_topology(nodes,edges,root)
    # build tree adjacency
    adj={x:[] for x in nodes}
    for (u,v) in tree:
        adj[u].append(v); adj[v].append(u)
    # hop BFS
    from collections import deque
    h={root:0}; q=deque([root])
    while q:
        x=q.popleft()
        for y in adj[x]:
            if y not in h: h[y]=h[x]+1; q.append(y)
    return h, tree, blocked

def run(label, nodes, edges, root):
    h,tree,blocked = hops_from_root(nodes,edges,root)
    unreached=[x for x in nodes if x not in h]
    worst = max(h.values()) if h else 0
    far = [k for k,v in h.items() if v==worst]
    flag = "OK" if worst<=CONSERVATIVE else ("MARGINAL" if worst<=HARD_HOP_CEIL else "OVER-LIMIT")
    print(f"{label}")
    print(f"   switches={len(nodes)}  blocked-links={len(blocked)}  worst-case diameter={worst} hops  -> {flag}")
    print(f"   (conservative ceil {CONSERVATIVE} | message-age wall {HARD_HOP_CEIL}; farthest: {far[0]})")
    if unreached: print("   !! UNREACHABLE:", unreached)
    print()
    return worst

def two_six(regime):
    nA,EA=base.build_train("M"); nB,EB=base.build_train("S")
    cA=base.coupler_costs(145,regime); cB=base.coupler_costs(133,regime)
    out={}
    for ea,eb,name in [("A","A","A-to-A"),("B","B","B-to-B"),("A","B","A-to-B")]:
        E=base.couple(EA,EB,"M","S",ea,eb,cA,cB)
        out[name]=run(f"6+6 {name} [{regime}]", nA|nB, E, "M:D1")
    return out

def four_teiler(t):
    """Approx 4-Teiler = drop E and F coaches (keep A,C,D + B). 12 switches.
       4-Teiler ring still closes A<->...<->B via the shortened spine."""
    n=lambda s:f"{t}:{s}"; E=[]
    def e(a,b,ca=base.DEFAULT_TRUNK,cb=base.DEFAULT_TRUNK): E.append((n(a),n(b),ca,cb))
    # shortened spine: A1-A3-A2 head, C car, D car, B car; couplers at A & B ends
    e("A1","A3"); e("A2","A3"); e("A1","C1"); e("A2","C3")
    e("C1","D1"); e("C2","C3"); e("C2","D3")
    e("D1","B1"); e("D2","D3"); e("D2","B2")   # D connects to B car (no E/F)
    e("B1","B3",CHORD,CHORD); e("B2","B3")
    nodes=set()
    for a,b,_,_ in E: nodes.add(a); nodes.add(b)
    return nodes,E

def triple_444(regime):
    # 3x 4-Teiler chained: T1[B]<->T2[A], T2[B]<->T3[A]  (linear chain)
    n1,e1=four_teiler("T1"); n2,e2=four_teiler("T2"); n3,e3=four_teiler("T3")
    c=lambda fz: base.coupler_costs(fz,regime)
    E=list(e1)+list(e2)+list(e3)
    # couple T1.B <-> T2.A
    for sa,sb in zip(("B1","B3"),("A1","A3")):
        E.append((f"T1:{sa}",f"T2:{sb}", c(101)[sa], c(102)[sb]))
    # couple T2.B <-> T3.A
    for sa,sb in zip(("B1","B3"),("A1","A3")):
        E.append((f"T2:{sa}",f"T3:{sb}", c(102)[sa], c(103)[sb]))
    nodes=n1|n2|n3
    return run(f"4+4+4 chain [{regime}]", nodes, E, "T2:D1")  # middle train root

if __name__=="__main__":
    print("\n#### RSTP DIAMETER / MESSAGE-AGE BUDGET CHECK ####")
    print(f"   VDS Max Age={MAXAGE}s, per-hop=+{PERHOP}s  =>  message-age wall = {HARD_HOP_CEIL} hops")
    print(f"   conservative IEEE design diameter = {CONSERVATIVE} hops")
    print(f"   default trunk PortPathCost = {base.DEFAULT_TRUNK} (VDS factory); chord = {CHORD}\n")
    for regime in ["v9","template"]:
        print(f"================= regime: {regime} =================")
        nS,ES = base.build_train("S0")
        run(f"SINGLE 6-Teiler [{regime}]", nS, ES, "S0:D1")
        two_six(regime)
        triple_444(regime)
