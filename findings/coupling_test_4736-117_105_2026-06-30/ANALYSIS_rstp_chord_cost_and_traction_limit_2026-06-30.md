# Post-test analysis — B1↔B3 chord cost & coupled-traction limit (2026-06-30)

Offline analysis follow-up to the 117+105 coupling test. Two questions:
1. Is the static `spanning-tree port-cost 400100` on B1/B3 **e0-0** (the B1↔B3 chord) needed?
2. How many trains can couple as one L2 (RSTP) domain, across the A-A / B-B / A-B orientations?

Models: `scripts/rstp_sim.py` (active-tree / which-link-blocks) and
`scripts/rstp_diameter.py` (BPDU message-age / hop-count budget). Both built from the live
nv6 template trunk descriptions. VDS factory trunk PortPathCost = 200000 (manual Table 4),
Max Age = 20 s, +1 s/hop.

## Q1 — The 400100 chord cost

**Provenance (git, `nomad-obn-template-nv6`):** introduced as `40100` in `308d10a`
(2026-03-31, "Add rstp priorities, v8"), bumped to `400100` in `0a5fe13` (2026-04-08,
"RSTP multitraction ports cost adjustment"). The later "Fix exceeding rstp costs" commit
(`deee326`) reworked only the **coupler** e0-2 formula and **left the e0-0 chord untouched**.
Author: Davud Zejnelovic.

**The B-car is a ring**, not a branch: B1 is dual-homed (e0-0→B3, e0-1→F1), so there is a
loop B1→B3→B2→F3→…→F1→B1. RSTP must block one link in it.

- **Solo train:** with `400100`, the blocked link is the B1↔B3 chord — correct. The tree runs
  the full train length via B1↔F1 instead of stubbing the B-car. **The cost is load-bearing —
  do not remove it.**
- **Coupled, v9 couplers (symmetric 20000):** `400100` is now ~200× a coupler and ~2× a single
  default trunk hop (200000). It is so heavy that RSTP keeps **both** coupler cables active and
  blocks an **internal spine link on the backup train instead** (A-A→105 A1-A3; B-B→105 C2-C3;
  A-B→105 A1-C1). Still 36/36 reachable, valid tree — but the coupled active topology is no
  longer the *designed* one; it falls out of un-rebalanced cost arithmetic.

**Recommendation:** keep the chord cost but **re-tune for v9**. With couplers at 20000 and a
default trunk at 200000, the chord should be just *above* a single trunk hop so it stays the
predictable block in both solo and coupled states, without dominating the coupled tree. The
exact safe window is the open item for Davud (see note to be drafted).

## Q2 — Coupled-traction limit (the real constraint is DIAMETER, not node count)

The limiting wall is the BPDU **message-age budget**: a BPDU is dropped once message age ≥ Max
Age. VDS Max Age = 20 s, +1 s/hop ⇒ **19-hop hard wall**; conservative IEEE design diameter = 7.

Worst-case root-to-leaf hop count over the active tree (`rstp_diameter.py`):

| Composition | Switches | Worst diameter (hops) | vs ceil-7 | vs wall-19 |
|---|---:|---:|---|---|
| Single 6-Teiler | 18 | 9 | over | OK |
| 2×6  A-to-A | 36 | 12 | over | OK |
| 2×6  A-to-B | 36 | 12–13 | over | OK |
| 2×6  B-to-B | 36 | **16** | over | OK (3-hop margin) |
| 3×4 (4+4+4) chain | 36 | 9–10 | over | OK |

Composition matrix vs the practical RSTP node ceiling (~40):

| Traction | Combination | Switches | RSTP single-domain |
|---|---|---:|---|
| 1× | 4-T / 6-T | 12 / 18 | OK |
| 2× | 4+4 / 4+6 / 6+6 | 24 / 30 / 36 | OK (6+6 at the edge) |
| 3× | 4+4+4 | 36 | edge (diameter ~10) |
| 3× | 4+4+6 | 42 | **over — needs L3** |
| 3× | 4+6+6 | 48 | **over — needs L3** |
| 3× | 6+6+6 | 54 | **over — needs L3** |

### Conclusions
- **Two trains couple safely** as one RSTP domain in **all three orientations** (A-A, B-B, A-B),
  up to 6+6 = 36 switches. v9 cost + native-999 makes this stable (test-validated).
- **B-to-B 2×6 is the worst case at 16 hops** — only 3 hops below the message-age wall. It is the
  orientation to watch; if Max Age is ever lowered, or a management bridge added to the path, B-B
  is the first to break. Diameter already exceeds the conservative-7 figure in every coupled case,
  which is why convergence is correct but not fast/robust — the v9 max-age/forward-delay tuning
  recommended in the test report (E10) addresses exactly this.
- **Triple traction containing any 6-Teiler (42/48/54 switches) cannot run as one flat RSTP
  domain** — over the node ceiling. Requires an L3/routed boundary or TCDS-style segmentation
  (see `project_3x6_triple_traction_required`). The v9 cost work does **not** rescue it.

## F4 residual DHCP loop — hypothesis status (2026-06-30)

Tracking which mechanisms for F4 (coupled-only, ~9/18 switches loop
DISCOVER→OFFER→no-REQUEST→DISCOVER, recover on decouple) are live vs ruled out:

- **REFUTED — dual DHCP server / nd-redundancy modulo contention.** The CCU dhcpd uses
  nd-redundancy modulo load-sharing (`class modulo_<rank>_<num_ccus>` matching on the last
  MAC byte). It was tempting to think coupling puts two authoritative servers on one bridged
  vlan100 and they race OFFERs. But EVIDENCE E5 line 128 explicitly shows **a single server-id
  (117 CCU 10.179.32.129) on all 50 OFFERs, no 105 offers crossed the coupler.** No second
  server is contending. Do not re-test this. (A solo "rogue 2nd server" injection on 4736-111
  was considered and dropped for this reason.)
- **Confirmed by direct measurement (still ruled out):** DHCP pool exhaustion; rogue/2nd
  server; transient broadcast flood from a test device.
- **LIVE leads — the failure is between OFFER and REQUEST, on the switch's side of the wire:**
  (a) OFFER lost in the coupled fabric before reaching the switch; (b) OFFER reaches switch but
  its DHCP client doesn't emit the REQUEST (client wedged, e.g. by a concurrent RSTP transition);
  (c) REQUEST emitted but its broadcast return path is disrupted. Distinguishing these needs a
  **simultaneous both-ends capture** — built as `scripts/12_dhcp_diag_ccu.sh` (CCU side) +
  `scripts/13_dhcp_mirror_switch.sh` (victim switch uplink mirror). Run at the next coupling
  window; the decision table is in `scripts/README_scripts.md`.
- **Note:** a solo train (e.g. 4736-111) leases 18/18 cleanly and **cannot reproduce F4** — it
  is coupled-state-specific. Confirmed 4736-111 baseline 2026-06-30: clean DORA on all 18.

### Caveats on the model
- Standard shortest-path-to-root tree; matches RSTP active topology for these symmetric costs.
  Exact tie-breaks (which of two equal v9 couplers stays active) follow real bridge-ID/port-ID,
  not modeled — but block/active *counts* and chord/spine decisions are robust (those costs untied).
- Root assumed at master D1 (priority 0). If the backup's D1 has the lower MAC, root flips and the
  blocked-spine side mirrors — same shape.
- 4-Teiler topology is reconstructed (drop E/F coaches); confirm against a real 4-T schema before
  citing the 3×4 number externally.
