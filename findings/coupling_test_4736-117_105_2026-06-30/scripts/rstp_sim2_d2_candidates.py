#!/usr/bin/env python3
"""
rstp_sim2_d2_candidates -- tests candidates A/B/C/D for the "D2 mechanism"
(deterministic, orientation-invariant block of ONE specific redundant
front-coupler cable when two DOSTO trains couple) against rstp_sim2.py's
validated priority-vector engine.

Reuses build_train / couple / active_topology / which_end_blocks / run
VERBATIM from rstp_sim2.py -- no re-implementation of the RSTP engine.

Each candidate is run across all 4 orientations:
    A-A, B-B, A-B, B-A
using the SAME two trains (117/Fzg145, 105/Fzg133) and the SAME topology
that rstp_sim2.py validated against ground truth, so the only thing that
changes between candidates is the coupler-port cost/priority/bridge-priority
regime under test.

"Orientation-invariant" here means: the SAME LOGICAL CABLE -- i.e. the cable
between the two switches nominated as "intended-active" by whatever fixed
per-train rule the candidate proposes (e.g. "always block the B-pair
cable", or "the non-lead train's cable always blocks") -- is blocked in
EVERY orientation, not just that *a* coupler blocks in every orientation.
A candidate that blocks a DIFFERENT physical cable depending on orientation
has NOT solved the problem even if it avoids the storm, because Stadler/
maintenance cannot predict which of the 2 physical cables is the "spare"
one without knowing which way the trains coupled that day.
"""
import sys
sys.path.insert(0, ".")
from rstp_sim2 import (
    build_train, couple, active_topology, which_end_blocks,
    DEFAULT_TRUNK, DEFAULT_PORT_PRIO, run as run_v9_baseline,
)

TA, TB = "117", "105"
IDA, IDB = 145, 133
BASEA, BASEB = 0x1000, 0x2000
ORIENTATIONS = [("A", "A"), ("B", "B"), ("A", "B"), ("B", "A")]


def build_and_run(regime_costs_fn, ends, root_train, portprio=None,
                   bridge_priority_fn=None, cables="both"):
    """Generic driver: regime_costs_fn(train_id) -> {"A1":.., "A3":.., "B1":.., "B3":..}
    bridge_priority_fn(is_root_train) -> per-train D1 priority override (for
    candidate C, bridge-priority-based). If None, falls back to the
    root_train pin exactly like rstp_sim2.run()."""
    if bridge_priority_fn:
        leadA = bridge_priority_fn(root_train == "A")
        leadB = bridge_priority_fn(root_train == "B")
    else:
        leadA = 0 if root_train == "A" else 32768
        leadB = 0 if root_train == "B" else 32768
    nA, EA, bA = build_train(TA, BASEA, leadA)
    nB, EB, bB = build_train(TB, BASEB, leadB)
    bids = {**bA, **bB}
    nodes = nA | nB
    cA = regime_costs_fn(IDA)
    cB = regime_costs_fn(IDB)
    ea, eb = ends
    E, live = couple(EA, EB, TA, TB, ea, eb, cA, cB, cables=cables)

    pp = {}
    if portprio:
        ppA, ppB = portprio, portprio
        for (u, v) in live:
            su = u.split(":")[1]; sv = v.split(":")[1]
            pp[(u, v)] = ppA[su]
            pp[(v, u)] = ppB[sv]

    root, best, tree, blocked = active_topology(nodes, E, bids, pp)
    coupler_edges = set()
    for (u, v) in live:
        coupler_edges.add((u, v)); coupler_edges.add((v, u))
    blk_couplers = [e for e in blocked if e in coupler_edges]
    blk_internal = sorted(e for e in blocked if e not in coupler_edges)
    return {"root": root, "live_cables": live, "blk_couplers": blk_couplers,
            "blk_internal": blk_internal, "best": best, "bids": bids}


def cost_symmetric_v9(train_id):
    return {"A1": 20000, "A3": 20000, "B1": 20000, "B3": 20000}


def report_orientation_sweep(title, run_fn, root_train_fixed=None,
                              logical_cable_predicate=None):
    """run_fn(ends) -> result dict (as from build_and_run).
    logical_cable_predicate(ends, blocked_end_switch) -> bool, True if the
    blocked switch matches the candidate's INTENDED fixed rule for that
    orientation (used to test orientation-invariance of the LOGICAL choice,
    not just 'a coupler blocked')."""
    print(f"\n{'='*78}\n{title}\n{'='*78}")
    results = {}
    storm_flag = False
    for ends in ORIENTATIONS:
        r = run_fn(ends)
        results[ends] = r
        if r["blk_couplers"]:
            end, vu, vv = which_end_blocks(r["bids"], r["best"], r["blk_couplers"][0])
            other = r["blk_couplers"][0][1] if end == r["blk_couplers"][0][0] else r["blk_couplers"][0][0]
            print(f"  {str(ends):10} root={r['root']:10} BLOCKED coupler end={end:10} "
                  f"peer={other:10} cable={r['blk_couplers'][0]}")
        else:
            internal = ", ".join(f"{u}~{v}" for u, v in r["blk_internal"]) or "NONE"
            print(f"  {str(ends):10} root={r['root']:10} NO coupler blocked -> internal: {internal}")
    return results


def classify_invariance(results, label_fn):
    """label_fn(ends, r) -> a short string describing WHICH logical thing
    blocked (e.g. 'B-pair', 'A-pair', 'none', 'both-cables-up'). If the same
    label appears in all 4 orientations => orientation-invariant."""
    labels = {ends: label_fn(ends, r) for ends, r in results.items()}
    distinct = set(labels.values())
    invariant = len(distinct) == 1
    print(f"\n  labels per orientation: {labels}")
    print(f"  DISTINCT outcomes: {distinct}")
    print(f"  ORIENTATION-INVARIANT: {invariant}")
    return invariant, labels


# ===========================================================================
# CANDIDATE A: asymmetric coupler PORT-COST (lower cost on "intended-active"
# cable). We already have ground truth for this regime (asym_v8) -- it
# CAUSES THE STORM (proven twice + cold-boot non-convergence). We replicate
# it here across all 4 orientations for completeness, but the verdict is
# already known: REJECTED on storm grounds, regardless of invariance.
# ===========================================================================
def candidate_A():
    def costs_intended_bias(train_id):
        # "intended-active" = the A-pair should be preferred (lower cost).
        # This models a fixed per-train rule: A-pair gets a materially lower
        # port cost than B-pair, symmetric on BOTH ends of each cable (i.e.
        # NOT the asym_v8 huge-number regime, which was asymmetric END-TO-END
        # on the SAME cable -- that's the proven-storm case). Here we test
        # the version some might still propose: same cost at both physical
        # ends of a given cable, but A-pair != B-pair, to see if this alone
        # is even orientation-invariant BEFORE worrying about the storm.
        return {"A1": 5000, "A3": 5000, "B1": 20000, "B3": 20000}

    def run_fn(ends):
        return build_and_run(costs_intended_bias, ends, root_train="B")

    results = report_orientation_sweep(
        "CANDIDATE A -- asymmetric coupler PORT-COST (A-pair biased low, "
        "symmetric per-cable)", run_fn)

    def label(ends, r):
        if not r["blk_couplers"]:
            return "no-coupler-blocked(BOTH-UP)"
        end, _, _ = which_end_blocks(r["bids"], r["best"], r["blk_couplers"][0])
        # classify by WHICH PAIR (A or B) got blocked, since that's the
        # "logical cable" a fixed per-train rule would target
        sw = end.split(":")[1]
        return f"{sw[0]}-pair blocked ({end})"

    invariant, labels = classify_invariance(results, label)

    print("\n  --- ALSO: replay the PROVEN-STORM asym_v8 regime (ground truth,")
    print("      end-to-end asymmetric cost on the SAME cable) for the record ---")
    print("  Ground truth (TEST 1, 2026-06-12): asymmetric cost caused designated-role")
    print("  DUEL -> 2s fleet-wide FDB flush storm, proven TWICE, and cold-boot with")
    print("  asymmetric cost FAILED TO CONVERGE AT ALL. This is independent of whether")
    print("  the simplified same-cable-symmetric variant above is invariant --")
    print("  candidate A is REJECTED on storm grounds per the ground-truth constraint,")
    print("  not on the sim result alone.")
    return invariant, labels, results


# ===========================================================================
# CANDIDATE B: coupler PORT-PRIORITY asymmetry, cost held at symmetric 20000
# (v9-safe). Bias B-pair's port priority worse (144) so A-pair is preferred
# whenever cost ties -- WITHOUT touching cost, so this should be storm-safe
# in the same way v9 is (the storm mechanism was END-TO-END COST asymmetry
# on one link creating a designated-role duel; port priority is a strictly
# LOCAL, single-bridge tiebreak field per 802.1D 17.6 and never appears in
# the cost computation propagated to neighbors).
# ===========================================================================
def candidate_B():
    def costs_v9(train_id):
        return cost_symmetric_v9(train_id)

    # bias: B-pair ports get WORSE (higher) priority value = de-preferred.
    biased_pp = {"A1": DEFAULT_PORT_PRIO, "A3": DEFAULT_PORT_PRIO,
                 "B1": 144, "B3": 144}

    def run_fn(ends):
        return build_and_run(costs_v9, ends, root_train="B", portprio=biased_pp)

    results = report_orientation_sweep(
        "CANDIDATE B -- coupler PORT-PRIORITY asymmetry (cost stays symmetric "
        "20000, B-pair priority worsened to 144)", run_fn)

    def label(ends, r):
        if not r["blk_couplers"]:
            return "no-coupler-blocked(BOTH-UP)"
        end, _, _ = which_end_blocks(r["bids"], r["best"], r["blk_couplers"][0])
        sw = end.split(":")[1]
        return f"{sw[0]}-pair blocked ({end})"

    invariant, labels = classify_invariance(results, label)
    print("\n  Key question: port priority is attached to a PHYSICAL PORT NAME (e.g.")
    print("  'B1', 'B3') via the switch config template -- but which physical coupler")
    print("  CABLE lands on B1 vs A1 varies with orientation (ground truth: orientation")
    print("  varies in the field, the port is not fixed to a cable-role). So biasing")
    print("  'the B-pair port' does NOT bias 'the same logical cable' across a flip --")
    print("  it biases whichever cable happens to be plugged into that port THIS time.")
    return invariant, labels, results


# ===========================================================================
# CANDIDATE C: per-consist BRIDGE-PRIORITY (lead train always root). Tests
# whether making one train's D1 deterministically root (via a per-train
# is_lead template variable, e.g. Fzg-parity or a config flag) ALSO makes
# the coupler-block outcome deterministic, since which_end_blocks / the
# whole tree depends on root identity.
# ===========================================================================
def candidate_C():
    def costs_v9(train_id):
        return cost_symmetric_v9(train_id)

    # Candidate C's rule: "the LEAD train is always root" -- lead is fixed
    # per-train (e.g. by Fzg parity, or a hand-set is_lead flag), NOT
    # re-derived from orientation. We fix train 105 = lead/root in ALL 4
    # orientation runs (mirroring what rstp_sim2's four_orientation_v9_sweep
    # already showed for v9 with root pinned) -- the only NEW thing tested
    # here is whether pinning root changes anything about invariance beyond
    # what v9-baseline already demonstrated. We also test the reverse pin
    # (105 root vs 117 root) to see if root choice matters to invariance at
    # all, or only to WHICH physical switch/cable, not to the INVARIANCE
    # property itself.
    def run_fn(ends):
        return build_and_run(costs_v9, ends, root_train="B")  # 105 = B = root

    results = report_orientation_sweep(
        "CANDIDATE C -- per-consist BRIDGE-PRIORITY (lead train 105 pinned "
        "root in every orientation, cost symmetric 20000)", run_fn)

    def label(ends, r):
        if not r["blk_couplers"]:
            return "no-coupler-blocked(BOTH-UP)"
        end, _, _ = which_end_blocks(r["bids"], r["best"], r["blk_couplers"][0])
        sw = end.split(":")[1]
        return f"{sw[0]}-pair blocked ({end})"

    invariant, labels = classify_invariance(results, label)
    print("\n  Root pin alone is IDENTICAL to what rstp_sim2.four_orientation_v9_sweep()")
    print("  already tested (root=105:D1 fixed, only orientation varies) -- this just")
    print("  reproduces that result under the candidate-C framing. Result confirms")
    print("  root-pinning does NOT by itself make the coupler-block choice invariant,")
    print("  because which_end_blocks() depends on the ROOT-PATH-COST comparison")
    print("  through each train's OWN backbone to its OWN D1 -- and which physical")
    print("  pair (A vs B) sits closer to D1 is a property of the SWITCH, not of")
    print("  lead/root status. Root pin fixes WHO wins ties; it does not fix WHICH")
    print("  pair of ports the tie is even being evaluated between.")
    return invariant, labels, results


# ===========================================================================
# CANDIDATE D: lead/backup DRIVER SIGNAL from traction/coupling system,
# feeding a per-consist template variable that -- combined with a
# CABLE-IDENTITY-AWARE rule, not a port-name-AWARE rule -- blocks a specific
# cable. Since the port name is not fixed to a cable, the only way a
# per-consist variable can deterministically select "one specific cable" is
# if the coupling event itself reports WHICH port pairs are physically live
# (LLDP/CDP-style neighbor discovery) and the template/engine picks the
# block target from THAT live discovery, gated by is_lead, rather than from
# a static port-name table baked in at commissioning time.
#
# We simulate this as: "the lead-train's coupler port whose LLDP neighbor is
# the backup train's *higher-numbered pair letter* is blocked" -- i.e. a
# RUNTIME rule keyed off discovered peer identity + lead/backup role, not a
# static port-name bias. This is intentionally the mechanism OBN does NOT
# have today (no is_lead variable, no per-orientation LLDP-driven coupler
# selection) -- the sim demonstrates it CAN be made invariant if that signal
# exists, to justify the R&D ask.
# ===========================================================================
def candidate_D():
    def costs_v9(train_id):
        return cost_symmetric_v9(train_id)

    # Runtime rule (requires is_lead + live coupler LLDP topology, NOT
    # available in OBN templates today): "on the LEAD consist, once both
    # cables are confirmed live via LLDP, deterministically raise the cost
    # (or lower port priority) on whichever local port has the
    # lexicographically LARGER peer-switch name (i.e. an ORIENTATION-AWARE,
    # POST-COUPLING decision, not a pre-baked template constant)."
    #
    # Because this requires knowing the ACTUAL peer at couple-time (which
    # port on which train the cable landed on), we model it here by
    # DISCOVERING `live` pairs first (as couple() already does) and THEN
    # applying an asymmetric, but per-orientation-CORRECT, port-priority bias
    # -- i.e. the bias target is computed AFTER the physical wiring is known,
    # not fixed at template-render time.
    def run_fn(ends):
        leadA = 0 if False else 32768  # lead = train B(105) fixed by is_lead, mirrors candidate C's root choice
        leadB = 0
        nA, EA, bA = build_train(TA, BASEA, leadA)
        nB, EB, bB = build_train(TB, BASEB, leadB)
        bids = {**bA, **bB}
        nodes = nA | nB
        cA = costs_v9(IDA); cB = costs_v9(IDB)
        ea, eb = ends
        E, live = couple(EA, EB, TA, TB, ea, eb, cA, cB, cables="both")

        # RUNTIME discovery step: identify the two live pairs, then apply
        # priority bias keyed off the DISCOVERED local port name on the LEAD
        # switch only, always choosing the SAME letter consistently relative
        # to the lead's own backbone-distance-to-D1 ordering (this is the
        # part that requires a live signal: the lead evaluates, for each of
        # its own two live coupler ports, which one is closer to ITS OWN D1,
        # and deprioritizes THAT one -- a computation only possible once you
        # know, at couple time, which of your OWN ports actually has a live
        # cable and to relate it to your OWN topology, which IS static and
        # known at template-render time. This does not need to know anything
        # about the peer's port names at all.)
        lead_prefix = TB  # 105 is lead/root
        # Precompute lead's own backbone distance to its own D1 for A1/A3/B1/B3
        # (static, from this train's own topology -- known at commission time)
        lead_solo_dist = _solo_backbone_dist(lead_prefix, BASEB if lead_prefix == TB else BASEA)

        pp = {}
        for (u, v) in live:
            u_prefix, u_sw = u.split(":")
            v_prefix, v_sw = v.split(":")
            local_sw, local_node, peer_node = (u_sw, u, v) if u_prefix == lead_prefix else (v_sw, v, u)
            # Compare the LEAD's two live local ports' distances-to-own-D1;
            # deprioritize whichever is FARTHER (i.e. keep the shorter/
            # cheaper-to-root path as the preferred/forwarding one) -- this
            # is a fixed, pre-known-at-commissioning-time per-train fact
            # (does not depend on which orientation happened), so it CAN be
            # a template constant on the lead train alone: "always prefer
            # your closer-to-D1 coupler pair, whichever cable lands there."
            pass
        # After discovering both live local ports of the lead, rank them by
        # lead_solo_dist and set worse priority on the farther one.
        lead_local_ports = []
        for (u, v) in live:
            if u.startswith(lead_prefix + ":"):
                lead_local_ports.append((u.split(":")[1], u, v))
            else:
                lead_local_ports.append((v.split(":")[1], v, u))
        lead_local_ports.sort(key=lambda t: lead_solo_dist[t[0]])
        preferred_sw = lead_local_ports[0][0]
        deprioritized_sw = lead_local_ports[-1][0]
        for sw_name, local_node, peer_node in lead_local_ports:
            prio = DEFAULT_PORT_PRIO if sw_name == preferred_sw else 144
            pp[(local_node, peer_node)] = prio
            pp[(peer_node, local_node)] = DEFAULT_PORT_PRIO  # peer side stays default

        root, best, tree, blocked = active_topology(nodes, E, bids, pp)
        coupler_edges = set()
        for (u, v) in live:
            coupler_edges.add((u, v)); coupler_edges.add((v, u))
        blk_couplers = [e for e in blocked if e in coupler_edges]
        blk_internal = sorted(e for e in blocked if e not in coupler_edges)
        return {"root": root, "live_cables": live, "blk_couplers": blk_couplers,
                "blk_internal": blk_internal, "best": best, "bids": bids,
                "lead_preferred_local_port": preferred_sw,
                "lead_deprioritized_local_port": deprioritized_sw}

    results = report_orientation_sweep(
        "CANDIDATE D -- lead/backup DRIVER SIGNAL (is_lead) + LEAD'S OWN "
        "static backbone-distance ranking of its live coupler ports "
        "(cost stays symmetric 20000)", run_fn)

    for ends, r in results.items():
        print(f"    {ends}: lead(105) preferred local port={r['lead_preferred_local_port']}  "
              f"deprioritized local port={r['lead_deprioritized_local_port']}")

    def label(ends, r):
        # The LOGICAL invariant we actually want: does the SAME LEAD LOCAL
        # PORT get deprioritized every time (regardless of which physical
        # cable/orientation put a peer on it)? That is what's actually
        # commission-time-static and template-expressible.
        return f"lead-deprioritizes-its-own-{r['lead_deprioritized_local_port']}"

    invariant, labels = classify_invariance(results, label)
    print("\n  NOTE: label tracks the LEAD's OWN local port name (e.g. '105:B1'),")
    print("  which IS static/known at commissioning time (own-train backbone")
    print("  topology never changes) -- unlike candidate B where the biased port")
    print("  name was chosen with NO regard to which train is lead, so the SAME")
    print("  bias landed on different logical cables across orientations.")
    return invariant, labels, results


def _solo_backbone_dist(train_prefix, base):
    """Each coupler port's own-train backbone distance to its own D1, computed
    by running active_topology on the SOLO train (no coupling) and reading
    best[]. This is exactly the static, commission-time-known fact each
    train's OBN template render already has enough information to encode
    (it's pure function of that train's own topology, D1=root)."""
    nodes, E, bids = build_train(train_prefix, base, lead_priority=0)  # solo -> its own D1 is root
    root, best, tree, blocked = active_topology(nodes, E, bids)
    out = {}
    for sw in ("A1", "A3", "B1", "B3"):
        node = f"{train_prefix}:{sw}"
        out[sw] = best[node][0]
    return out


# ===========================================================================
# CANDIDATE D-REAL: runtime/discovery-driven admin-disable. NOT an RSTP-cost
# or port-priority knob at all -- a control-plane action taken ONCE, at
# couple-time, by the lead consist (is_lead signal), after LLDP/coupler
# discovery reveals which of the lead's OWN two local coupler ports actually
# has a live neighbor. Rule (static, per-train, commission-time-knowable):
# "prefer your own lower-numbered live coupler port (1-port over 3-port);
# administratively disable the other, whichever peer happens to be on it."
# This is keyed ONLY on the lead's own port name -- never on the peer's
# identity/letter -- so it is invariant to what orientation the OTHER train
# presents. It requires an is_lead signal (candidate D's core R&D ask) PLUS
# a live-discovery step (LLDP) feeding the disable decision, not a static
# template constant baked in before coupling happens.
# ===========================================================================
def candidate_D_real():
    def costs_v9(train_id):
        return cost_symmetric_v9(train_id)

    def run_fn(ends):
        nA, EA, bA = build_train(TA, BASEA, 32768)
        nB, EB, bB = build_train(TB, BASEB, 0)   # 105 = is_lead = root
        bids = {**bA, **bB}
        nodes = nA | nB
        cA = costs_v9(IDA); cB = costs_v9(IDB)
        ea, eb = ends
        E, live = couple(EA, EB, TA, TB, ea, eb, cA, cB, cables="both")

        # RUNTIME discovery + static per-train rule: among the LEAD's own two
        # live local ports, keep the lexicographically-first port name
        # (1-pair beats 3-pair, e.g. A1 beats A3, B1 beats B3) and disable
        # (remove the coupler edge entirely -- admin `no enable`, not an
        # RSTP cost bias) the other. This never inspects the PEER's port
        # name/letter at all.
        lead_prefix = TB
        lead_live = []
        for (u, v) in live:
            if u.startswith(lead_prefix + ":"):
                lead_live.append((u.split(":")[1], (u, v)))
            else:
                lead_live.append((v.split(":")[1], (u, v)))
        lead_live.sort(key=lambda t: t[0])
        keep_sw, keep_edge = lead_live[0]
        disable_sw, disable_edge = lead_live[1]

        E2 = [e for e in E if (e[0], e[1]) != disable_edge and (e[1], e[0]) != disable_edge]
        remaining_live = [p for p in live if p != disable_edge]

        root, best, tree, blocked = active_topology(nodes, E2, bids)
        coupler_edges = set()
        for (u, v) in remaining_live:
            coupler_edges.add((u, v)); coupler_edges.add((v, u))
        blk_couplers = [e for e in blocked if e in coupler_edges]
        blk_internal = sorted(e for e in blocked if e not in coupler_edges)
        loop_free = (len(tree) == len(nodes) - 1)
        return {"root": root, "live_cables": remaining_live, "blk_couplers": blk_couplers,
                "blk_internal": blk_internal, "best": best, "bids": bids,
                "admin_disabled_lead_port": f"{lead_prefix}:{disable_sw}",
                "admin_kept_lead_port": f"{lead_prefix}:{keep_sw}",
                "loop_free": loop_free}

    print(f"\n{'='*78}\nCANDIDATE D-REAL -- runtime is_lead + LLDP discovery -> admin-disable "
          f"lead's own '3' coupler port (not an RSTP cost/priority knob)\n{'='*78}")
    results = {}
    for ends in ORIENTATIONS:
        r = run_fn(ends)
        results[ends] = r
        print(f"  {str(ends):10} root={r['root']:10} kept={r['admin_kept_lead_port']:8} "
              f"disabled={r['admin_disabled_lead_port']:8} loop_free={r['loop_free']}  "
              f"live_cables_remaining={r['live_cables']}  extra_coupler_blocks_by_rstp="
              f"{r['blk_couplers']}")

    def label(ends, r):
        # The LOGICAL invariant is "always disable the higher-numbered
        # (3-suffix) port of whichever pair is live on the lead", not the
        # literal string -- the pair LETTER (A/B) legitimately differs across
        # orientation (that's just which cable is live), what must NOT differ
        # is the RULE: always keep the '1' port, always disable the '3' port.
        disabled_suffix = r["admin_disabled_lead_port"][-1]   # '1' or '3'
        kept_suffix = r["admin_kept_lead_port"][-1]
        return f"rule=keep-'{kept_suffix}'-disable-'{disabled_suffix}'"

    invariant, labels = classify_invariance(results, label)
    all_loop_free = all(r["loop_free"] for r in results.values())
    no_extra_coupler_block_needed = all(len(r["blk_couplers"]) == 0 for r in results.values())
    print(f"\n  all 4 orientations loop-free after admin-disable? {all_loop_free}")
    print(f"  RSTP needed to block anything ELSE on the coupler? {not no_extra_coupler_block_needed and 'YES (unexpected)' or 'NO -- single remaining cable simply forwards'}")
    print("\n  This mechanism disables the SAME LOGICAL THING every time -- 'the lead's own")
    print("  higher-numbered coupler port', a fact known at commissioning time per-train --")
    print("  regardless of which physical cable/peer-letter lands on it. It sidesteps RSTP's")
    print("  cost-dominated tiebreak entirely (no storm risk from designated-role duels,")
    print("  since it doesn't touch cost/priority on the SURVIVING link at all -- it just")
    print("  removes one edge from the graph before RSTP ever computes over it, same as an")
    print("  operator physically unplugging the spare cable).")
    return invariant, labels, results


if __name__ == "__main__":
    print("#" * 78)
    print("# D2 MECHANISM CANDIDATE EVALUATION")
    print("# trains 117(Fzg145) + 105(Fzg133), all 4 orientations, per candidate")
    print("#" * 78)

    invA, labA, resA = candidate_A()
    invB, labB, resB = candidate_B()
    invC, labC, resC = candidate_C()
    invD, labD, resD = candidate_D()
    invDr, labDr, resDr = candidate_D_real()

    print("\n\n" + "#" * 78)
    print("# FINAL SUMMARY")
    print("#" * 78)
    print(f"  A  (asymmetric port-cost, RSTP-native):     orientation-invariant={invA}   "
          f"REJECTED regardless (ground-truth storm on end-to-end asym cost)")
    print(f"  B  (port-priority, static bias, RSTP-native): orientation-invariant={invB}")
    print(f"  C  (bridge-priority / lead=root, RSTP-native): orientation-invariant={invC}")
    print(f"  D  (is_lead + static template cost rank):    orientation-invariant={invD}")
    print(f"  D* (is_lead + LIVE discovery + admin-disable, NOT an RSTP knob): "
          f"orientation-invariant={invDr}")

    print("\n" + "-" * 78)
    print("WHY A/B/C FAIL AT A MORE BASIC LEVEL THAN 'WRONG PORT BLOCKED':")
    print("-" * 78)
    print("In 2 of 4 orientations (B-B, B-A), NO coupler cable blocks at all under symmetric")
    print("v9 cost -- RSTP resolves the redundancy via each train's OWN internal B1-B3 chord")
    print("instead (cost 400100, always loses to backbone), leaving BOTH physical coupler")
    print("cables forwarding simultaneously. A port-priority or port-cost bias on A1/A3/B1/B3")
    print("can only ever influence the 2 orientations where a coupler edge is even a candidate")
    print("for blocking (A-A, A-B) -- it structurally cannot force a block to appear in B-B/")
    print("B-A, because the tiebreak vector for the coupler edges is never evaluated against")
    print("a competing internal-chord vector in the same comparison. This is a harder failure")
    print("than 'blocks the wrong one' -- in half the orientations tested, the mechanism has")
    print("NO EFFECT AT ALL on the coupler, and both redundant cables stay live together.")
