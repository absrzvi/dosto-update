# Multitraction (up to 3 coupled trains) — alternatives analysis & reply basis to VDS

**Date:** 2026-07-10
**Author:** Abbas Rizvi (analysis assembled from field tests 2026-06-12 / 2026-06-30, RSTP simulator, 2026-06-20 design panel, VDS switch manual v2.0.4)
**Trigger:** Giorgio (VDSRail) reply to Nenad, 2026-07 — (a) still evaluating whether an RSTP config can guarantee the coupled ports are always blocked for the 2-train case, will bench-verify; (b) confirms 3-train is over the RSTP node limit; proposes **MSTP or L3 separation** as alternatives.
**Requirement:** supporting up to **3 coupled trains** is mandatory (confirmed 2026-06-20). Worst composition 3×6-Teiler = 54 switches.

Companion docs:
- `findings/coupling_test_4736-110_119_2026-06-12/PLAN_3x6_scale_beyond_rstp_2026-06-20.md` — design panel (4 approaches stress-tested)
- `findings/coupling_test_4736-117_105_2026-06-30/ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md` — diameter/composition math
- `reports/customer/OBB_DOSTO_RSTP_Coupling_Simulator_2026-07-06.html` + `findings/coupling_test_4736-117_105_2026-06-30/scripts/rstp_sim2*.py` — ground-truth-validated simulator
- `giorgio-6teiler-v8-configs/` — live v8 configs (4736-117/Fzg145, 4736-119/Fzg147) already provided to VDS 2026-07-06 for their bench replica

---

## 1. TL;DR

1. **2-train (Giorgio's bench question):** our simulator — validated against both live coupling-test harvests — has already swept the static-RSTP design space. **No time-invariant RSTP parameter set (cost, port-priority, bridge-priority, or any per-position combination) guarantees that a coupler port is always the blocked element across orientation × root position × faults.** We should send Giorgio the simulator + the 8-case sweep as *falsifiable bench predictions* so his verification effort targets the right hypothesis space instead of re-discovering this. Our decided mechanism for deterministic coupler standby is non-RSTP: **CCU app reads multitraction state from the Stadler DXS and admin-disables the designated spare Frontkupplung port** (ÖBB-paid change request, scoped 2026-07-06 with failback / root-alignment / per-junction requirements).
2. **3-train:** we agree with Giorgio that flat RSTP cannot do it — and it is not just the ~40-node ceiling; the **BPDU message-age wall** is the harder physics (measured 31 hop-equivalents on a live 2×6; ~50 at 3×6 > the ~38-hop reach of even max-age 40). Between his two alternatives:
   - **MSTP — declined as primary.** Not in the deployed firmware (manual v2.0.4 / fleet target 7.4.2 documents RSTP only), so it means new VDS firmware + our approval cycle (7.4.8 already failed approval). And it fixes only the spanning-tree ceiling while keeping one flat 54-switch broadcast domain — the June field tests prove services (CCTV/ZFR via VLAN-15 FW↔FW, DHCP) already fail at 2× coupling *while RSTP is converged and healthy*. Scaling the same flat domain 1.5× cannot improve those.
   - **L3 separation — accepted, and it is what our 2026-06-20 design panel independently concluded.** Primary flavour: **terminate inter-consist traffic at the Stadler firewalls per IEC 61375-2-5** (each train stays its own ≤18-node RSTP island; couplers carry only a STP-excluded FW↔FW transit; exactly one active cable per junction enforced by the same D2 CCU mechanism). Fallback flavour (Nomad/VDS-owned, in *current* firmware): **switch-native TCDS routed mode + R-NAT + vTBN (§21.5)** with its known gaps engineered around (static-mroute-only multicast, vTBN redundancy via VRRP, composition lock/head, TTCMP enablement).
3. **Sequencing:** v9 (symmetric 20000 + native-999 + max-age 38) ships regardless — it is the proven ≤2×6 envelope. The D2 change request (CCU coupling-state app) is the bridge: it solves 2-train determinism *and* is the enabler of the 3-train FW-terminated design. The 3× architecture build is gated on the Stadler A8 characterisation and the ÖBB change-request/commercial scoping (SDD currently lists multi-train shared network as "VO, nicht im Leistungsumfang").

---

## 2. Evidence base (what is already proven, not opinion)

| # | Fact | Source |
|---|------|--------|
| E1 | Asymmetric per-end coupler cost sustains a designated-role duel → TC every ~2s → fleet-wide FDB flush storm; stopped the second costs were made symmetric (20000). | 2026-06-12 test, intervention-proven |
| E2 | Live 2×6 worst root-path distance = **31 hop-equivalents** (far end exactly at the default 20-hop max-age horizon; degraded legs included). Clean-model diameter 2×6 B-B = 16 hops. Fix: forward-delay 20 + max-age 38 (~36-hop reach). | 2026-06-20 harvest re-analysis; `rstp_diameter.py` |
| E3 | Under v9 symmetric cost with both coupler cables live, a blocked (standby) coupler exists in only **3 of 8** orientation × root-position combinations; in the other 5 RSTP blocks an internal spine link instead. Deterministic per orientation, but orientation varies in the field and root is a MAC lottery. | 8-case sim sweep 2026-07-06, sim validated against both live harvests |
| E4 | No static knob changes E3: port-priority is never consulted (root-path-cost strictly dominates, byte-identical sim outcomes), bridge-priority only moves the root, asymmetric spreads reintroduce E1. | `rstp_sim2_d2_candidates.py`, `attack_d2_candidate.py` |
| E5 | The coupled-service outage (CCTV/ZFR/displays) is **not** an STP failure: RSTP was converged; pruning VLAN 5 off the coupler did nothing; only full physical decouple recovered service. Prime suspect: **VLAN-15 FW↔FW transit poisoning Stadler FW routing state** (A8). | 2026-06-12 test, recovery-sequence confirmed |
| E6 | Coupled-only DHCP pathology (F4): ~9/18 switches loop DISCOVER→OFFER→no-REQUEST; single server-id proven on the wire; solo train leases 18/18 clean. | 2026-06-30 test, EVIDENCE E5 |
| E7 | VLAN-5 CCTV multicast is unsnooped, ~3 kpps crossing the coupler each way in 2× composition. | 2026-06-12 harvest |
| E8 | TTCMP/KON consist-management traffic can flood under fault (Malformed KON storm → snmpd/AgentX restarts, switches drop off SNMP). TTCMP/TCDS is currently **inactive** fleet-wide. | bench box1-t122, 2026-07-04 |
| E9 | Deployed firmware surface (manual v2.0.4, fleet target 7.4.2): RSTP only — **no MSTP anywhere in the manual**; per-port STP exclusion exists (`no configure interface <p> spanning-tree enable` → NotManaged/Forwarding, no BPDUs, manual L1978-1986); TCDS plain + **routed mode w/ R-NAT + vTBN** (§21.5); static `mroute` only, no PIM/DVMRP; composition lock + head flag (§21.6); VRRP (instances 1-4). | `.claude/switch_manual.txt` greps 2026-07-10 |
| E10 | New-firmware reality check: 7.4.8 was evaluated and **not approved**; fleet target stays 7.4.2 (templates fv5 0.0.21 / fv6 0.0.19 re-pinned 2026-07-09). Any MSTP path inherits at least this approval latency. | project history 2026-07-09 |

Topology reminder (supersedes older mental models): each train is a **ring** (e0-0/e0-1 backbone through all 18 switches, plus the B1↔B3 chord); trains join via **4 coupler ports per train** (e0-2 on A1/A3/B1/B3 only). One physical end couples at a time → **2 redundant cables per junction**. Coupling orientation (A-A/B-B/A-B/B-A) varies in the field. Backbone distances D1→{A1,A3,B1,B3} = 4000/6000/22000/12000 — these fixed asymmetries are what decide the block placement once the two equal-cost cables cancel out.

---

## 3. Part A — the 2-train question ("guarantee the coupled ports are always blocked")

### 3.1 Why no static RSTP configuration can do it (mechanism, sim-proven)

1. **Two parallel cables, symmetric costs → the cable costs cancel.** For any switch comparing a path via cable 1 vs cable 2, the identical cable costs drop out of the comparison; the decision falls to the *internal* path deltas between the four coupler switches. Those deltas are fixed per position (A1/A3/B1/B3 = 4000/6000/22000/12000 from D1) but **which positions face each other varies with coupling orientation** — so the blocked element is orientation-dependent, and in 5 of 8 orientation×root cases it is an internal spine link, not a coupler (E3).
2. **Making the cables unequal is not expressible statically.** A per-position cost spread (e.g. A1≠A3≠B1≠B3) puts unequal costs on the two *ends of the same cable* in most orientations — that is exactly the measured role-duel/TC-storm failure (E1). And "cheap cable 1, expensive cable 2" cannot be pre-baked because which physical cable is which depends on how the shunter couples.
3. **Port-priority is structurally inert** here — RSTP compares root-path-cost first and the margins are wide; the priority field is never reached (E4). **Bridge-priority** only chooses the root; it does not choose which redundant element blocks.
4. **"…and faults" makes it strictly harder:** after any single-link failure the tree re-forms on the residual static costs — same arithmetic, same non-determinism. A time-invariant parameter set cannot encode run-time coupling state.

Conclusion: the invariant "a coupler port is always the blocked element" requires runtime knowledge (which cables are live, which orientation) that RSTP parameters cannot carry. This is a *structural* result on this topology, not a tuning gap.

### 3.2 What to do with Giorgio's bench effort (constructive)

Giorgio already has the live v8 configs of both coupling-test trains (provided 2026-07-06). Send him:
- the **simulator** (`rstp_sim_ui.html` standalone; full 802.1D priority-vector engine, validated against both live harvests — asym B-B reproducing 119:B3 ALTR/BLK, and v9-sym B-A reproducing no-coupler-block), and
- the **8-case sweep table** as bench predictions: per orientation (A-A/A-B/B-A/B-B) × root position, which element blocks under v9 symmetric.

Framing: *if his bench matches the sim on the riggable cases, the exhaustive sweep transfers and closes the question; if the bench diverges anywhere, we want the `show spanning-tree` + cost harvest to correct the model.* Either outcome is progress; nobody burns weeks re-walking the swept space. If VDS does find a working static scheme, the sim can immediately cross-check it against all orientations, roots, and single-fault cases — we should say plainly we would welcome that, and equally plainly that the swept candidates (symmetric, asymmetric, port-priority, bridge-priority, per-position spreads) are all refuted.

### 3.3 The decided mechanism (D2 → D\*)

Decision of 2026-07-06 stands: **CCU application reads multitraction state (coupled y/n + master/slave) from the Stadler DXS and deterministically admin-disables the designated spare Frontkupplung port.** Confirmed obtainable signal; packaged as a **change request that ÖBB orders and pays for**. Scoped-in requirements from the adversarial pass: (1) continuous link monitor + automatic re-enable (failback — never leave a train dark with a healthy spare admin-down); (2) root alignment tied to the same DXS signal (is_lead ≠ RSTP-root gap); (3) per-junction scope (middle consist in 3-traction handles one spare per junction); (4) selection by measured link health, not port-number convention.

Interim: v9 symmetric 20000 stays as the storm-safe baseline; non-deterministic standby documented as a known limitation.

---

## 4. Part B — the 3-train question

### 4.1 The wall, precisely

Two independent limits, both must be respected:

| Limit | Value | 2×6 | 3×6 |
|---|---|---|---|
| VDS practical RSTP node ceiling | ~40 nodes (Giorgio; ring topology) | 36 — inside | **54 — over, no knob exists** |
| BPDU message-age reach | max-age 38 ≈ 36 hops; absolute protocol max 40 ≈ ~38 hops | 31 hop-equivalents measured (E2) — covered by max-age 38 | **~50 hop-equivalents — beyond max-age 40. No timer fixes it.** |

Composition matrix (from the 2026-06-30 analysis): 2× anything ≤ 6+6 = OK under v9. 3×4 = 36 switches / ~10-hop diameter = numerically at the same envelope as 2×6, so *pure 4-Teiler triples* are arguably inside flat-RSTP — but any triple containing a 6-Teiler (42/48/54) is over. The requirement is "up to 3 coupled trains" generically → design for 3×6 = 54 and treat 3×4 as a lucky special case, not a design point.

### 4.2 Alternative 1 — MSTP (Giorgio's first option): honest assessment, then decline

**What MSTP would genuinely buy** (stated fairly, so the decline is credible):
- Per-train **MST regions** collapse each train to one virtual bridge in the CIST's external view; message-age increments only at region boundaries → the external diameter of a 3-train composition is ~3, and each region's internal topology runs on its own hop budget. The diameter wall and the node ceiling are both addressed *at the protocol level*.
- No readdressing, no NAT, no new Stadler dependency; L2 service model (VLAN 5/15 across couplers) unchanged.

**Why we should still decline it as the primary:**
1. **It does not exist in the product we deploy.** Manual v2.0.4 documents RSTP only (E9). MSTP means VDS firmware development + our fleet approval cycle + fleet-wide rollout — and the 7.4.8 precedent (evaluated, rejected, target re-pinned to 7.4.2) says this path is measured in quarters, not weeks (E10).
2. **It fixes the only layer that is currently *not* failing.** In both field tests RSTP was converged and stable while services died: the CCTV/ZFR outage is FW↔FW VLAN-15 state poisoning (E5), and coupled DHCP fails between OFFER and REQUEST (E6). Those are flat-broadcast-domain pathologies. MSTP keeps one flat L2 domain of 54 switches — every measured failure mode scales *up*, not away: unsnooped VLAN-5 multicast floods all 54 switches (E7), three FWs now share the VLAN-15 transit instead of two, TTCMP/KON fault amplification gets a bigger blast radius (E8).
3. **Region-consistency fragility in a coupling fleet.** MSTP only forms a region when name/revision/VLAN-map match *exactly*; any mismatch silently splits per-switch. Two consequences: (a) per-train region names are mandatory (identical fleet templates would merge a coupled composition into ONE 54-switch region — reproducing the exact problem); (b) any template-version drift between coupling partners (guaranteed during every rollout window — we already lived the mixed-config split-brain storm) degrades into per-switch regions with undefined interaction. The fleet's own history is the argument.
4. **D2 is untouched.** At each junction the two parallel cables are external CIST links; the block election is the same cost arithmetic in CIST space — deterministic standby still needs the runtime mechanism (§3.3).
5. **No field precedent** we know of for MSTP regions across arbitrary revenue-service train couplings. We would be the first, on new firmware, with our fleet.

**Disposition:** not the primary. One genuine open question to VDS is worth asking before burying it (§6, Q-V4): is MSTP an existing capability in a newer VDS build or a roadmap offer? If a build already exists and has rail field hours, the calculus on point 1 softens — points 2–4 still stand.

### 4.3 Alternative 2 — L3 separation (Giorgio's second option = our design-panel recommendation)

The 2026-06-20 design panel stress-tested four approaches; the survivor is L3 termination, in two flavours with a clear preference order.

#### Primary: terminate inter-consist traffic at the Stadler firewalls (IEC 61375-2-5 pattern)

Design sketch:
- Each consist stays its **own RSTP domain, ≤18 nodes / ≤9 hops** — comfortably inside every limit, identical to today's solo behaviour. Solo-train behaviour is completely unchanged.
- Coupler ports are **excluded from RSTP** (`no configure interface e0-2 spanning-tree enable`, E9) and pruned to carry **only the FW↔FW transit VLAN (15)** — no general fabric bridging, no merged STP domain. (Note: with VDS single-instance RSTP, *any* bridged VLAN across the coupler merges the STP domains — the per-port exclusion is what actually cuts the tree, the prune is what cuts the traffic.)
- **Exactly one active cable per junction**, enforced and monitored by the **same D2 CCU mechanism** (§3.3). This is load-bearing: with STP excluded on coupler ports, a second live cable would be an unprotected loop (manual's own warning) — so the D2 app is not a nicety here, it is the loop-protection control plane. Failback requirement already scoped covers the redundancy story (spare swaps in on active-cable fault).
- The **Stadler FWs route all inter-consist traffic** over the VLAN-15 transit — which is precisely the IEC 61375-2-5 model (consist-local L2; inter-consist via the train-backbone router; the Stadler FW *is* the train-backbone router). CCTV/ZFR/display cross-train relay stays on the FW path, where it already lives today.
- Positive side effects: kills the cross-train native/mgmt leakage class entirely; F4's coupled-DHCP trigger disappears (DHCP domains stay per-train); broadcast/multicast blast radius stays 18 switches regardless of composition length; works identically for 2×, 3×, and any mixed 4/6-Teiler composition.

Why primary: it puts the L3 boundary where inter-consist service routing *already* lives, and it **forces resolution of A8** — the VLAN-15 FW↔FW behaviour that is the prime suspect for the existing 2× outage — instead of routing around it. The FWs already misbehaving at 2× must be fixed for *any* multitraction future; this design makes that fix the centrepiece rather than a loose end.

Honest dependencies: bulk of the work is **Stadler-owned** (FW routing policy, VLAN-15 relay behaviour, per-composition service routing); needs the A8 characterisation closed first; needs ÖBB commercial scoping (SDD lists multi-train shared network as "VO, nicht im Leistungsumfang" — same change-request family as D2).

#### Fallback: switch-native TCDS routed mode + R-NAT + vTBN (§21.5) — if Stadler cannot/won't own the boundary

- **Exists in the currently deployed firmware** (E9) — no new firmware, Nomad/VDS-owned, template-deliverable through the existing OBN → .deb → Puppet pipeline.
- Each consist = its own L2/RSTP island; boundary (coupler) ports become access ports on a backbone VLAN; vTBN switches auto-configure inter-consist routing + 1:1 R-NAT on every composition change. Per-junction redundancy is handled *structurally*: the backbone VLAN at a junction is a tiny L2 segment (4 boundary ports, 2 cables) — RSTP trivially blocks one of two parallel links in a 4-node domain. D2 dissolves at the junctions as a bonus.
- Known gaps to engineer around (from the design panel + manual):
  - **No dynamic multicast routing** (no PIM/DVMRP; static `tcds vtbn mroute` only) → CCTV multicast cannot simply flood across. Mitigation: keep cross-train CCTV/service relay on the Stadler FW path — but note honestly: boundary-as-access-port means VLAN 15 no longer bridges across the coupler either, so the FW↔FW relay must itself ride the routed backbone (R-NAT'd) → **Stadler coordination is unavoidable in this flavour too**, just smaller.
  - **vTBN is a single point of failure** → VRRP exists in-firmware (instances 1-4); VDS must confirm vTBN+VRRP composition.
  - **Requires enabling TCDS/TTCMP fleet-wide** (currently inactive, E8) → behavioural change with a proven fault-amplification mode; bench-validate under fault injection.
  - **Composition lock + head flag** (§21.6) for deterministic position-dependent addressing across arbitrary orientations.
  - **Zero known field hours** for routed mode on v2.0.4 — VDS must state whether any customer runs it in revenue service (the manual's "5 consists" example is plain-mode *discovery*, not a routed deployment).
  - R-NAT's headline rationale (identical address spaces colliding) is *partially* real for us: switch mgmt 192.168.1.0/24 does NOT cross the coupler today (cable-register #10), but per-train vlan100 mgmt/DHCP scopes and the Stadler-side per-train VLANs would need the actual overlap list enumerated before the R-NAT plan is drawn.

#### Rejected for completeness

- **Coupled-switch mode (§20.3)** — pairs two switches into one bridge entity; reduces node count marginally; wrong tool (panel-rejected).
- **Operational restriction to ≤2×** — dead against a mandatory 3× requirement; but the *commercial* half survives: the SDD scope line must be reconciled with the requirement, and the whole 3× build should be an ÖBB-ordered change request.

### 4.4 Decision matrix

| Criterion | MSTP | TCDS routed (fallback) | **FW-terminated L3 (primary)** |
|---|---|---|---|
| Breaks the 54-node / diameter wall | Yes (regions) | Yes (per-consist RSTP) | Yes (per-consist RSTP) |
| In deployed firmware today | **No** (RSTP only) | Yes (§21.5) | Yes (per-port STP exclusion + prune) |
| New VDS firmware + approval cycle | **Required** | No | No |
| Fixes A8 (VLAN-15 FW↔FW outage — the actual 2× service killer) | No — untouched | Partly forces it (transit must be re-plumbed) | **Yes — makes it the centrepiece** |
| Fixes F4 (coupled DHCP loop) | No | Yes (per-train DHCP domains) | Yes (per-train DHCP domains) |
| Multicast/broadcast blast radius | 54 switches | 18 + static mroutes (gap) | 18 + FW relay (today's model) |
| Deterministic coupler standby (D2) | Still unsolved | Structural (tiny per-junction domain) | Via D2 CCU app (already decided/scoped CR) |
| Config-consistency risk across arbitrary pairings | **High** (region merge/split traps) | Medium (TCDS params, addressing templates) | Low (per-train configs stay self-contained) |
| Field precedent | None known (rail couplings) | None known — VDS to confirm | IEC 61375-2-5 standard pattern |
| Main owner | VDS fw + Nomad rollout | Nomad templates + VDS support | **Stadler** (+ Nomad coupler config + D2 app) |
| Solo-train behaviour changed | Yes (new protocol fleet-wide) | Yes (TCDS on, addressing) | **No** (couplers only) |

---

## 5. Recommendation & sequencing

1. **Now / unchanged:** v9 ships (symmetric 20000, native-999 + prune 5,15, fwd-delay 20 + max-age 38). Proven ≤2×6 envelope; nothing in the 3× workstream is allowed to delay it.
2. **2-train determinism:** proceed with the **D2 change request** (CCU + DXS coupling-state app, admin-disable spare, failback + root-alignment + per-junction scope). Send VDS the simulator + sweep so bench effort converges (§3.2).
3. **3-train architecture:** answer Giorgio — agree RSTP is out; of his two alternatives choose **L3 separation**, in order of preference:
   - **Primary: Stadler-FW-terminated per IEC 61375-2-5** (consist-local L2, STP-excluded VLAN-15-only couplers, one active cable per junction via the D2 app, FWs route inter-consist).
   - **Fallback: TCDS routed mode hybrid** (current firmware, Nomad-deliverable) if Stadler declines ownership — with the multicast/vTBN/TTCMP gaps engineered as in §4.3.
   - **MSTP: declined as primary** (not in deployed firmware; preserves every measured flat-domain failure; region fragility across arbitrary pairings) — with one clarifying question to VDS before final burial (Q-V4).
4. **Gates before any build:** (a) Stadler A8 characterisation of FW behaviour under coupled VLAN-15 (prerequisite for *both* L3 flavours and already owed for the 2× outage); (b) ÖBB commercial scoping — 3× multi-train networking as ordered change request (SDD "VO" line reconciled); (c) VDS confirmations (Q-V1..V4).
5. **Joint bench proposal (cheap, high-value):** Giorgio is assembling switches for the 2-train verification anyway. Propose extending that same bench to **three mini-consists** (4-6 switches each — routed-mode scale is per-consist, so small consists prove the mechanism) to validate: TCDS routed mode + R-NAT under composition change, vTBN failover (VRRP), boundary-port STP exclusion behaviour, composition lock/head across re-couplings, and fault injection (cable pull mid-composition). That one bench answers both workstreams.

## 6. Open questions per party

**VDS (Giorgio):**
- Q-V1: TCDS routed mode on build v2.0.4/7.4.2 — any revenue-service field deployment anywhere? Known issues list?
- Q-V2: vTBN redundancy — is vTBN + VRRP a supported combination? Failover time on coupling change?
- Q-V3: Confirm static-mroute-only multicast in routed mode and its practical limits (table size, re-install latency on composition change).
- Q-V4: MSTP — existing capability in a newer build or roadmap item? If existing: which firmware, and any rail field hours with regions across vehicle couplings? What is VDS's own view on a 54-switch flat broadcast domain even with MSTP converged?
- Q-V5: In routed mode, what exactly happens to a boundary port when the peer consist runs *plain* L2 (mixed-mode coupling during migration)?
- Q-V6: Confirm per-port STP exclusion (`no configure interface … spanning-tree enable`) is stable under link flap on coupler ports (for the FW-terminated design).

**Stadler:**
- Q-S1: A8 — characterise FW behaviour when 2 (then 3) consists share the VLAN-15 transit; this is owed for the existing 2× outage regardless of 3×.
- Q-S2: Will Stadler own FW↔FW inter-consist routing per IEC 61375-2-5 (FW as train-backbone router)? If yes, what does the FW need from our fabric (transit VLAN, addressing, one-active-cable guarantee)?
- Q-S3: DXS multitraction state feed to the CCU (D2 CR dependency) — interface spec + latency.

**ÖBB / commercial:**
- Q-O1: Confirm 3× composition envelope (which combinations: 3×4, 4+4+6, 3×6?) as ordered scope; reconcile SDD "VO, nicht im Leistungsumfang" line; change-request framing for both the D2 app and the 3× architecture.

**Nomad R&D:**
- Q-N1: D2 CCU app (DXS read + port disable + failback) — sizing per the 2026-07-06 scoped requirements.
- Q-N2: If fallback flavour is chosen: template work for TCDS routed (backbone VLAN, vTBN SVI, R-NAT templates, mroutes, composition lock) across nv4/nv6 repos + address-overlap enumeration.

---

## 7. Draft reply to Giorgio (for Nenad to send / adapt)

> Hi Giorgio,
>
> thank you — this matches our own analysis, and we can hopefully save you some bench time on the two-train case.
>
> 1. Two trains: we built an RSTP simulator (full 802.1D priority-vector logic) and validated it against the switch-by-switch harvests of both our June coupling tests — it reproduces the live outcomes exactly. Sweeping all four coupling orientations and both root positions over the v8/v9 configs you already have: with both coupler cables connected, a blocked coupler port exists in only 3 of 8 orientation/root combinations; in the other 5, RSTP blocks an internal backbone link instead. We also swept the static remedies — port cost (symmetric and asymmetric), port priority, bridge priority, per-position spreads. None guarantees a blocked coupler across orientation, root position and single faults; asymmetric per-end costs additionally reproduce the TC-storm role duel we measured in June. We will send you the simulator and the 8-case table as predictions for your bench — if your bench matches them, the sweep result transfers; if it diverges anywhere, we would very much like the spanning-tree harvest to correct the model. Our conclusion is that the guarantee needs runtime coupling knowledge, which RSTP parameters cannot carry: our planned mechanism is a CCU-side function that reads the coupling state (train coupled + master/slave) from the vehicle bus and administratively disables the designated spare coupler port, with continuous link monitoring and automatic re-enable on fault. This is being prepared as a change request towards the customer.
>
> 2. Three trains: agreed — and beyond the node count, our measured worst-case root-path distance on a live 2×6 was already 31 hops, so a 3×6 (~50) is past any max-age. Between your two alternatives we prefer L3 separation over MSTP: MSTP is not in the firmware release we deploy (manual 2.0.4 documents RSTP only), and it would keep one flat broadcast domain of ~54 switches — our June tests show the services fail at the flat-L2 layer (FW-to-FW transit, DHCP, unsnooped CCTV multicast) even while spanning tree is perfectly converged. For L3 we see two implementations, in order of preference: (a) terminating inter-consist traffic at the train firewalls per IEC 61375-2-5, with the coupler carrying only a spanning-tree-excluded FW-to-FW transit VLAN and exactly one active cable per junction (enforced by the same CCU function as above); (b) your TCDS routed mode (§21.5) with vTBN + R-NAT, which has the advantage of existing in the current firmware. For (b) we would need from you: field-deployment status of routed mode on 2.0.4, vTBN redundancy (VRRP?), the static-mroute multicast limits, and the behaviour of a routed boundary port against a plain-L2 peer during migration.
>
> 3. Proposal: since you are assembling switches for the two-train verification anyway, could we extend the same bench to three small consists (4-6 switches each) and jointly validate the routed-mode mechanics (composition change, vTBN failover, boundary-port behaviour, cable-pull faults)? That single bench would answer both the two-train determinism question and the three-train architecture.
>
> Regards, …

---

*Prepared 2026-07-10. Sources: switch manual v2.0.4 (`.claude/switch_manual.txt` — §6.1.6 L1959-1998, §21.5 L9037-9153, §21.6 L9155-9276, VRRP L5145-5206); design panel PLAN_3x6_scale_beyond_rstp_2026-06-20.md; ANALYSIS_rstp_chord_cost_and_traction_limit_2026-06-30.md; coupling-test reports 2026-06-12 / 2026-06-30; sim suite rstp_sim2*.py (validated); bench RCA box1-t122 2026-07-04.*
