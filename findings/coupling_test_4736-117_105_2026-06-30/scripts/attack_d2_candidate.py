#!/usr/bin/env python3
"""
attack_d2_candidate -- adversarial test of the recommended D* mechanism
(candidate_D_real in rstp_sim2_d2_candidates.py).

D*'s rule, as specified in the recommendation:
  "is_lead consist runs a runtime discovery step (LLDP/link-state) AFTER
   coupling to see which of ITS OWN two coupler ports have a live neighbor;
   if both do, it administratively disables (no enable) its own
   higher-numbered port (the '3' port) and keeps the '1' port up. The rule
   references only the lead's own static, commission-time-known port
   identity -- never the peer's letter/identity."

Attacks attempted:
  1. Flip which train is is_lead/root -- does the rule still work if 117
     (not 105) is lead? (The existing sim ALWAYS makes 105 lead+root; never
     tested the other way.)
  2. Decouple is_lead from root election. The recommendation implies
     is_lead and RSTP-root are the same train, but nothing in real DOSTO
     ties is_lead (a traction/coupling-system signal) to which D1 wins the
     RSTP bridge-ID election (a function of bridge priority + MAC). What
     happens if is_lead's D1 does NOT win root (e.g. backup train's D1 has
     the lower MAC/priority)?
  3. Both-cables-live but with the BACKUP train also running D*'s rule
     (symmetry attack) -- does backup independently disabling ITS OWN
     higher-numbered port matter, conflict, or double-disable?
  4. Single-cable-live ground truth (2026-06-30 actual condition) combined
     with root=lead flipped.
  5. A cable flap: cable on the '1' port drops after '3' was disabled --
     does the mechanism strand the train with zero live coupler links
     instead of failing over to the disabled '3' port?
  6. 3-train couple (117-105-X): does "lead disables its own 3-port"
     generalize, or does a middle train's OWN two coupler port pairs face
     TWO neighbors simultaneously, breaking the "only one train runs the
     rule" assumption?
  7. Lead's own two ports are asymmetric-cost-to-D1 (already true per the
     topology, 4000/6000 vs 22000/12000) -- does "keep '1' disable '3'"
     always coincide with "keep the closer-to-D1 port"? If not on some
     letter pair, D* may be blocking the wrong (electrically better) path
     even though it stays loop-free -- i.e. determinism achieved, but the
     "close to D1 wins" property implicitly assumed is not always true.
"""
import sys
sys.path.insert(0, ".")
from rstp_sim2 import (
    build_train, couple, active_topology, which_end_blocks,
    DEFAULT_TRUNK, DEFAULT_PORT_PRIO,
)
from rstp_sim2_d2_candidates import (
    TA, TB, IDA, IDB, BASEA, BASEB, ORIENTATIONS, cost_symmetric_v9,
    _solo_backbone_dist,
)

SEP = "=" * 78


def run_d_real(ends, lead_prefix, root_prefix, cables="both"):
    """Generalized D-real driver: lead_prefix runs the admin-disable rule.
    root_prefix independently controls who wins the RSTP root election
    (decoupled from lead_prefix, to test attack #2)."""
    leadA_root_prio = 0 if root_prefix == TA else 32768
    leadB_root_prio = 0 if root_prefix == TB else 32768
    nA, EA, bA = build_train(TA, BASEA, leadA_root_prio)
    nB, EB, bB = build_train(TB, BASEB, leadB_root_prio)
    bids = {**bA, **bB}
    nodes = nA | nB
    cA = cost_symmetric_v9(IDA)
    cB = cost_symmetric_v9(IDB)
    ea, eb = ends
    E, live = couple(EA, EB, TA, TB, ea, eb, cA, cB, cables=cables)

    if not live:
        # nothing physically live at all -- degenerate
        root, best, tree, blocked = active_topology(nodes, E, bids)
        return {"root": root, "live_cables": [], "blk_couplers": [],
                "blk_internal": sorted(blocked), "best": best, "bids": bids,
                "admin_disabled_lead_port": None, "admin_kept_lead_port": None,
                "loop_free": len(tree) == len(nodes) - 1, "nodes": nodes}

    lead_live = []
    for (u, v) in live:
        if u.startswith(lead_prefix + ":"):
            lead_live.append((u.split(":")[1], (u, v)))
        elif v.startswith(lead_prefix + ":"):
            lead_live.append((v.split(":")[1], (u, v)))

    disable_edge = None
    keep_sw = disable_sw = None
    if len(lead_live) >= 2:
        lead_live.sort(key=lambda t: t[0])
        keep_sw, keep_edge = lead_live[0]
        disable_sw, disable_edge = lead_live[-1]
    # if lead_live has < 2 entries, the lead doesn't see two live local
    # ports at couple-time (e.g. single-cable-live ground truth, or lead
    # isn't even a party to this coupling face) -- rule is a no-op.

    if disable_edge:
        E2 = [e for e in E if (e[0], e[1]) != disable_edge and (e[1], e[0]) != disable_edge]
        remaining_live = [p for p in live if p != disable_edge]
    else:
        E2 = E
        remaining_live = live

    root, best, tree, blocked = active_topology(nodes, E2, bids)
    coupler_edges = set()
    for (u, v) in remaining_live:
        coupler_edges.add((u, v)); coupler_edges.add((v, u))
    blk_couplers = [e for e in blocked if e in coupler_edges]
    blk_internal = sorted(e for e in blocked if e not in coupler_edges)
    loop_free = (len(tree) == len(nodes) - 1)
    return {"root": root, "live_cables": remaining_live, "blk_couplers": blk_couplers,
            "blk_internal": blk_internal, "best": best, "bids": bids,
            "admin_disabled_lead_port": f"{lead_prefix}:{disable_sw}" if disable_sw else None,
            "admin_kept_lead_port": f"{lead_prefix}:{keep_sw}" if keep_sw else None,
            "loop_free": loop_free, "nodes": nodes}


def attack1_flip_lead_to_117():
    print(SEP)
    print("ATTACK 1 -- flip is_lead/root to 117 instead of 105 (never tested in the")
    print("original candidate_D_real, which hardcodes lead=105=root in every run)")
    print(SEP)
    all_invariant_label = set()
    for ends in ORIENTATIONS:
        r = run_d_real(ends, lead_prefix=TA, root_prefix=TA, cables="both")
        suffix = r["admin_disabled_lead_port"][-1] if r["admin_disabled_lead_port"] else "NONE"
        kept = r["admin_kept_lead_port"][-1] if r["admin_kept_lead_port"] else "NONE"
        all_invariant_label.add(f"keep-{kept}-disable-{suffix}")
        print(f"  {str(ends):10} root={r['root']:10} kept={r['admin_kept_lead_port']!s:10} "
              f"disabled={r['admin_disabled_lead_port']!s:10} loop_free={r['loop_free']}  "
              f"remaining={r['live_cables']}  extra_blocks={r['blk_couplers']}")
    print(f"\n  distinct rules observed: {all_invariant_label}")
    print(f"  STILL INVARIANT WITH 117 AS LEAD: {len(all_invariant_label) == 1}")


def attack2_lead_not_root():
    print("\n" + SEP)
    print("ATTACK 2 -- decouple is_lead from RSTP root election.")
    print("Real DOSTO: is_lead is a TRACTION/COUPLING-SYSTEM signal (driver's cab).")
    print("RSTP root is elected by bridge-ID (priority+MAC), a SEPARATE mechanism.")
    print("Nothing in the recommendation ties these together operationally --")
    print("what if the BACKUP train's D1 has the lower bridge ID and wins root,")
    print("while the LEAD (per traction signal) is still the one running D*'s rule?")
    print(SEP)
    for ends in ORIENTATIONS:
        # lead = 105 (as the recommendation frames it), but root = 117 (backup wins root)
        r = run_d_real(ends, lead_prefix=TB, root_prefix=TA, cables="both")
        print(f"  {str(ends):10} root={r['root']:10} lead=105  kept={r['admin_kept_lead_port']!s:10} "
              f"disabled={r['admin_disabled_lead_port']!s:10} loop_free={r['loop_free']}  "
              f"remaining={r['live_cables']}  extra_blocks={r['blk_couplers']}")
    print("\n  Does invariance / loop-freedom survive lead != root? (see loop_free column)")


def attack3_both_trains_run_the_rule():
    print("\n" + SEP)
    print("ATTACK 3 -- symmetry attack: what if BOTH consists run D*'s rule")
    print("independently (e.g. is_lead is mis-set on both sides, or the 'backup'")
    print("also runs a defensive local disable because it can't distinguish itself")
    print("from lead without a reliable cross-consist signal at the moment of")
    print("coupling)? Does double-application still leave exactly one path, or")
    print("does it over-disable and strand the consist pair?")
    print(SEP)
    for ends in ORIENTATIONS:
        leadA_root_prio = 32768
        leadB_root_prio = 0
        nA, EA, bA = build_train(TA, BASEA, leadA_root_prio)
        nB, EB, bB = build_train(TB, BASEB, leadB_root_prio)
        bids = {**bA, **bB}
        nodes = nA | nB
        cA = cost_symmetric_v9(IDA); cB = cost_symmetric_v9(IDB)
        ea, eb = ends
        E, live = couple(EA, EB, TA, TB, ea, eb, cA, cB, cables="both")

        # BOTH sides independently compute "keep my own '1', disable my own '3'"
        disable_edges = set()
        for prefix in (TA, TB):
            local_live = []
            for (u, v) in live:
                if u.startswith(prefix + ":"):
                    local_live.append((u.split(":")[1], (u, v)))
                elif v.startswith(prefix + ":"):
                    local_live.append((v.split(":")[1], (u, v)))
            if len(local_live) >= 2:
                local_live.sort(key=lambda t: t[0])
                disable_edges.add(local_live[-1][1])

        E2 = [e for e in E if (e[0], e[1]) not in disable_edges and (e[1], e[0]) not in disable_edges]
        remaining_live = [p for p in live if p not in disable_edges]
        root, best, tree, blocked = active_topology(nodes, E2, bids)
        loop_free = (len(tree) == len(nodes) - 1)
        connected = len(remaining_live) > 0
        print(f"  {str(ends):10} root={root:10} both-sides-disabled={sorted(disable_edges)}  "
              f"remaining_live={remaining_live}  loop_free={loop_free}  "
              f"still_connected_via_coupler={connected}")
    print("\n  If remaining_live becomes EMPTY, both physical cables get admin-disabled")
    print("  and the two trains are severed from each other entirely -- worse than the")
    print("  storm this was meant to avoid (total loss of the inter-consist link vs a")
    print("  transient flush storm).")


def attack4_single_cable_ground_truth_with_flip():
    print("\n" + SEP)
    print("ATTACK 4 -- single-cable-live (actual 2026-06-30 ground truth) with lead")
    print("NOT being the train whose port is the live one (i.e. lead's OWN coupler")
    print("only has ONE live local port, on either the '1' or '3' side depending on")
    print("orientation) -- does the rule ever accidentally disable the ONLY live link?")
    print(SEP)
    for ends in ORIENTATIONS:
        for lead_prefix in (TA, TB):
            r = run_d_real(ends, lead_prefix=lead_prefix, root_prefix=TB, cables="first")
            danger = (len(r["live_cables"]) == 0)
            print(f"  ends={str(ends):10} lead={lead_prefix:4} root=105  "
                  f"kept={r['admin_kept_lead_port']!s:10} disabled={r['admin_disabled_lead_port']!s:10} "
                  f"remaining_live={r['live_cables']}  {'*** SEVERED ***' if danger else ''}")


def attack5_cable_flap_after_disable():
    print("\n" + SEP)
    print("ATTACK 5 -- cable flap: the KEPT '1' port's cable drops AFTER the '3' port")
    print("was admin-disabled by D*. Does the mechanism define any failback? The")
    print("recommendation's rule is a ONE-SHOT post-coupling decision -- it does not")
    print("mention re-arming discovery or re-enabling the disabled port if the kept")
    print("one later fails. Simulate: disable '3' at couple time (ends=A-A, both")
    print("cables live), then the '1' cable's link drops with '3' still admin-down.")
    print(SEP)
    ends = ("A", "A")
    r = run_d_real(ends, lead_prefix=TB, root_prefix=TB, cables="both")
    print(f"  post-couple: kept={r['admin_kept_lead_port']} disabled="
          f"{r['admin_disabled_lead_port']} remaining_live={r['live_cables']}")
    # Now simulate the kept cable physically dropping (remove it from the graph
    # entirely, as a link-down would), while the admin-disabled port is STILL
    # admin-down (D* did not re-arm it):
    kept_edge = r["live_cables"][0]
    leadA_root_prio = 32768
    leadB_root_prio = 0
    nA, EA, bA = build_train(TA, BASEA, leadA_root_prio)
    nB, EB, bB = build_train(TB, BASEB, leadB_root_prio)
    bids = {**bA, **bB}
    nodes = nA | nB
    cA = cost_symmetric_v9(IDA); cB = cost_symmetric_v9(IDB)
    E, live = couple(EA, EB, TA, TB, ends[0], ends[1], cA, cB, cables="both")
    # remove BOTH the admin-disabled edge AND the now-flapped kept edge
    disabled_edge = None
    for (u, v) in live:
        if (u, v) != kept_edge and (v, u) != kept_edge:
            disabled_edge = (u, v)
    E_after_flap = [e for e in E
                    if (e[0], e[1]) != kept_edge and (e[1], e[0]) != kept_edge]
    root, best, tree, blocked = active_topology(nA | nB, E_after_flap, bids)
    loop_free = (len(tree) == len(nA | nB) - 1)
    fully_connected = loop_free and len(tree) == len(nA | nB) - 1
    # Is the graph even still connected (no coupler link between trains at all)?
    reachable = set()
    adjm = {}
    for (u, v, _, _) in E_after_flap:
        adjm.setdefault(u, []).append(v)
        adjm.setdefault(v, []).append(u)
    stack = [next(iter(nA))]
    seen = {stack[0]}
    while stack:
        x = stack.pop()
        for y in adjm.get(x, []):
            if y not in seen:
                seen.add(y); stack.append(y)
    trains_still_joined = any(n in seen for n in nB)
    print(f"  AFTER kept-cable flap (admin-disabled '3' port still down, not re-armed):")
    print(f"  trains_still_joined_via_coupler = {trains_still_joined}")
    if not trains_still_joined:
        print("  *** FAILURE MODE: D* has no failback -- disabling '3' at couple time")
        print("      with no re-arm/re-enable-on-failure logic means a later failure of")
        print("      the surviving '1' cable leaves the two consists with ZERO coupler")
        print("      connectivity even though a perfectly good spare cable ('3') is")
        print("      sitting there administratively shut down. RSTP alone (no admin-")
        print("      disable) would have kept both cables' redundancy available for")
        print("      exactly this failure. ***")


def attack6_three_train_couple():
    print("\n" + SEP)
    print("ATTACK 6 -- 3-train couple (117-105-X): does 'lead disables its own")
    print("3-port' generalize when a train is coupled on BOTH ends simultaneously")
    print("(a middle train in a 3-consist multitraction, not modeled by the 2-train")
    print("couple() helper)? If 105 sits in the middle, it has FOUR live coupler")
    print("ports at once (A1/A3 to one neighbour, B1/B3 to the other), not two.")
    print("D*'s rule as specified only reasons about ONE pair-of-two per consist.")
    print(SEP)
    print("  couple() in rstp_sim2.py only joins exactly 2 trains end-to-end; it has")
    print("  no support for a train coupled at BOTH ends simultaneously (a 3rd train")
    print("  attached to 105's OTHER end). Modeling this needs the coupler edges from")
    print("  105's currently-unused pair (e.g. A-pair, if B-pair already went to 117)")
    print("  wired to a 3rd train's build_train() output.")
    # Build it manually: 105's B-end couples to 117 (both cables live), and
    # 105's A-end couples to a 3rd train "999" (both cables live) -- a valid
    # physical scenario if 105 is a middle consist in a triple-traction.
    nA, EA, bA = build_train(TA, BASEA, 32768)       # 117
    nB, EB, bB = build_train(TB, BASEB, 0)            # 105 = lead/root
    nC, EC, bC = build_train("999", 0x3000, 32768)    # 3rd train
    bids = {**bA, **bB, **bC}
    nodes = nA | nB | nC
    cA = cost_symmetric_v9(IDA); cB = cost_symmetric_v9(IDB); cC = cost_symmetric_v9(200)
    E1, live1 = couple(EA, EB, TA, TB, "B", "A", cA, cB, cables="both")  # 117:B <-> 105:A
    E2, live2 = couple([], EC, TB, "999", "B", "A", cB, cC, cables="both")  # 105:B <-> 999:A
    E_all = E1 + E2
    live_all = live1 + live2
    print(f"  105's live coupler pairs simultaneously: {live_all}")
    # 105's OWN live local ports across BOTH ends:
    lead_prefix = TB
    lead_live = []
    for (u, v) in live_all:
        if u.startswith(lead_prefix + ":"):
            lead_live.append((u.split(":")[1], (u, v)))
        elif v.startswith(lead_prefix + ":"):
            lead_live.append((v.split(":")[1], (u, v)))
    print(f"  105's own live local coupler ports (should be 2 pairs = 4 ports under")
    print(f"  D*'s framing, but the rule 'keep the lexicographically first, disable")
    print(f"  the rest' was designed for exactly ONE pair of 2): {sorted(lead_live)}")
    lead_live_sorted = sorted(lead_live, key=lambda t: t[0])
    if len(lead_live_sorted) > 2:
        print(f"\n  *** FAILURE MODE: with 4 live local ports (A1,A3,B1,B3 all up because")
        print(f"      105 is coupled on BOTH ends), D*'s stated rule ('keep lexicographically")
        print(f"      first, disable the rest') would keep ONLY 105:A1 and disable A3, B1, AND")
        print(f"      B3 -- but B1/B3 are 105's link to a DIFFERENT, otherwise-unreachable 3rd")
        print(f"      train ('999')! The rule as literally stated ('keep own lower-numbered")
        print(f"      port') has no notion of 'per-neighbour pair' -- applied naively across")
        print(f"      all of a consist's live coupler ports at once, it would sever the entire")
        print(f"      3rd train from the consist, not just remove a redundant spare. ***")
        keep = lead_live_sorted[0]
        disable = lead_live_sorted[1:]
        print(f"  naive global rule keeps: 105:{keep[0]}   disables: {[d[0] for d in disable]}")


def attack7_closer_to_d1_check():
    print("\n" + SEP)
    print("ATTACK 7 -- does 'keep 1 / disable 3' always coincide with 'keep the")
    print("port electrically closer to own D1'? If not, D* achieves determinism but")
    print("may deliberately keep the LONGER/WORSE backbone path every time on one")
    print("letter-pair, silently downgrading a fine cable in favor of a farther one.")
    print(SEP)
    dist105 = _solo_backbone_dist(TB, BASEB)
    dist117 = _solo_backbone_dist(TA, BASEA)
    print(f"  105 own backbone distance to own D1: {dist105}")
    print(f"  117 own backbone distance to own D1: {dist117}")
    for prefix, dist in ((TB, dist105), (TA, dist117)):
        a_closer = dist["A1"] < dist["A3"]
        b_closer = dist["B1"] < dist["B3"]
        print(f"  {prefix}: is port '1' the CLOSER-to-D1 port on A-pair? {a_closer}   "
              f"on B-pair? {b_closer}")
    print("\n  If port '1' is NOT always the closer one for both pairs on both trains,")
    print("  then 'keep 1 / disable 3' is an arbitrary naming convention, not a rule")
    print("  grounded in link quality/cost -- it happens to work here only if 1-ports")
    print("  are always the shorter path BY CONSTRUCTION of this topology/labeling.")


if __name__ == "__main__":
    attack1_flip_lead_to_117()
    attack2_lead_not_root()
    attack3_both_trains_run_the_rule()
    attack4_single_cable_ground_truth_with_flip()
    attack5_cable_flap_after_disable()
    attack6_three_train_couple()
    attack7_closer_to_d1_check()
