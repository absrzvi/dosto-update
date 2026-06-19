# Coupled-Train RSTP Test — 4736-110 (Fzg 138) + 4736-119 (Fzg 147)

**Date:** 2026-06-12, coupled ~10:00Z, B-end to B-end
**Engineers:** Abbas Rizvi (Nomad Digital)
**Context:** Controlled repro of the 2026-06-0x broadcast-storm incident (4736-109+110), informed by VDS support (Giorgio) max-age hypothesis received same morning.
**Raw data:** `4736-110_fzg138_harvest.txt`, `4736-119_fzg147_harvest.txt`, `tc_trace_138.txt`, `tc_trace_147.txt` (this folder).

## Executive summary

1. **No broadcast storm reproduced.** The coupled 36-switch network converged to a single, stable RSTP topology: one root, one active coupler link, the redundant coupler link correctly blocked.
2. **The max-age partition did not occur** — but only because the root happens to sit near the middle of the merged chain (max observed radius 14 hops vs the 20-hop BPDU horizon). The margin is ~5 hops; Giorgio's failure mode remains plausible for unlucky root placement and is **certain** for 3×6-car compositions.
3. **A real, coupling-specific pathology WAS found:** a perpetual RSTP topology-change (TC) storm. Both trains' switches flush their MAC tables every ~2 s, continuously, driven by a designated-role proposal duel on the **active** coupler link. A solo control train (Fzg 132, same firmware, same debug) shows zero such events.
4. The TC churn turns the merged fabric into a permanent flood domain: every FDB flush converts forwarded traffic into unknown-unicast/multicast flooding. ~3 kpps of multicast (unsnooped VLAN-5 CCTV being the prime suspect) crosses the coupler in each direction continuously. This is the plausible **precursor state** of the June storm: degraded but survivable at 2×6-car scale; with added triggers (BPDU horizon crossing, more traffic, more consists) it can escalate.

## Test setup

- 4736-110 = box1-t23 (10.179.23.1), hostnames `nv6-*-v8-138`; 4736-119 = box1-t12 (10.179.12.1), hostnames `nv6-*-v8-147`.
- Storm watchers on both CCUs sampling bond0 rx_pps/mcast_pps every 3 s (`/tmp/bond0_storm_watch.log`).
- Per VDS support guidance, `configure system logging debug rstp,coupled` enabled pre-coupling on 8 cab switches + 2 priority-0 roots; extended to all 36 switches mid-test.
- All switches at RSTP defaults: Hello 2 s, **Max Age 20**, Forward Delay 15.

## Findings

### F1 — Clean RSTP convergence (single root, redundant link blocked)

All 36 switches agree on root `0/a0:59:3a:d0:59:20` = **nv6-D1-v8-138** (priority 0; the switch where 110's CCU attaches). Physical coupler pairing (LLDP-verified, crossed — normal):

| Link | End A | End B | RSTP state |
|---|---|---|---|
| Active | B1-147 e0-2 (ROOT/FWD, cost 146999999) | B3-138 e0-2 (DESG/FWD) | forwarding |
| Redundant | B1-138 e0-2 (DESG/FWD) | B3-147 e0-2 (**ALTR/BLK**) | blocked — correct |

Coupler counters reconcile across the link pairs (B1-147 TX 29.7M ≈ B3-138 RX 29.8M; B1-138 TX 14.2M ≈ B3-147 RX 14.5M). Zero CRC / carrier-false on all four coupler ports.

### F2 — Max-age margin: passed, but thin

Worst observed root path cost 28000 (A3-147) = **14 hops** from root (2000/hop on 10G backbone). The far extremity of 147 sits ~15–16 hops out vs the 20-hop max-age BPDU horizon. No split-root observed anywhere. **Interpretation:** this composition passed because the priority-0 root (D1-138) lies near the middle of the merged 36-switch chain. Root election between the two trains' priority-0 bridges is decided by MAC tie-break, i.e. luck: a composition whose elected root sits nearer one extremity would push the far end past 20 hops, partition the tree, unblock the redundant coupler link, and close a genuine L2 loop — Giorgio's mechanism, fully consistent with the June 109+110 storm. A 3×6-car composition (54 switches) exceeds even max-age 40.

### F3 — Perpetual topology-change storm (NEW, coupling-specific)

With RSTP debug enabled, **every switch in both trains logs a TC + "Flushing all entries" cycle every ~2 s (hello time), continuously**, for the whole observation window (>40 min). Control: nv6-B1-v8-132 on solo train 4736-104, same firmware + debug, logged **zero** TC/proposal/agreement events in 40 s.

Origin localized to the **active** coupler link: B1-147 e0-2 logs `sending designated proposal` AND `received designated proposal` in the same second (tc_trace_147, 02:02:10–11) — both ends transiently claim the designated role. Each duel round resolves via proposal/agreement sync, emits a TC, and the TC propagates fleet-wide (D1-138 root relays it; every bridge flushes its FDB). The port-role oscillation is too fast to catch with `show spanning-tree` polling (4 samples over 20 s all showed stable roles) but is continuous in the debug logs.

Consequences of a 2-second FDB flush cycle across 36 switches:
- all learned MACs are discarded fleet-wide every cycle → sustained unknown-unicast flooding (B1-147→B3-138 carried 11.7M flooded unicasts);
- multicast/broadcast already flood by design (IGMP snooping disabled fleet-wide) → ~11.6M multicast + up to 6.5M broadcast crossed the coupler in each direction during the window (~3 kpps sustained — matches 119's CCU watcher: 2–6 kpps elevation vs 110's quiet baseline);
- the fabric runs permanently degraded; under additional load or with the F2 partition trigger, this is a credible escalation path to the 30+ kpps multicast storm observed in June.

### F4 — No CCU heartbeat cross-talk

10 s tcpdump sniffs on both CCUs (`dst 239.0.0.1`): each CCU sees only its own nd-redundancy heartbeat. The native-VLAN heartbeat leak suspected earlier is not present in this composition (coupler trunks prune to VLANs 5,15 with native 999).

### F5 — Watcher / traffic profile

- 110 bond0: quiet (10–200 pps background).
- 119 bond0: sustained 2–6 kpps unicast bursts, mcast_pps ~1–2 — consistent with flood traffic reaching the CCU, NOT a multicast storm signature. Stable over 90 s observation, no ramp.

## Recommendations

1. **Tactical (fleet, before further multi-traction):** raise RSTP timers on all switches — `configure spanning-tree forward-delay 20` then `configure spanning-tree max-age 38` (+ `save running-config force`). Order matters: the firmware enforces 2×(FwdDelay−1) ≥ MaxAge, so max-age 38 is rejected at the default forward-delay 15. Covers all 2-train compositions regardless of root placement. Must be added to the v8 templates (Part G MR) or the next `obn update c` reverts it.
2. **Escalate F3 to VDS support (Giorgio):** provide tc_trace files + this report. Key question: why do both ends of a P2P coupler link continuously re-negotiate the designated role? Ask whether the very large hand-set port-cost (146999999) on coupler ports is implicated, and whether a firmware fix or config change (e.g. restoring default cost) stabilizes the link role.
3. **Controlled experiment available on request:** revert coupler port-cost to default on the active link while coupled, watch whether the TC churn stops (the debug logging is still enabled fleet-wide on both trains).
4. **Strategic (Stadler/R&D):** terminate L2 at the coupler — route VLAN 5/15 between consists via the Stadler FWs (IEC 61375 pattern). Removes the max-age ceiling, TC churn, multicast flood-through, and the 54-switch impossibility in one move.
5. **Multicast hygiene:** ~3 kpps of unsnooped VLAN-5 multicast crosses the coupler continuously. Evaluate enabling IGMP snooping + querier, or rate-limit `multicast` (current coupler rate-limit covers broadcast only) — with care not to starve RSTP BPDUs (01:80:C2 should bypass storm-control per spec; verify with VDS).
6. **3-train compositions are not RSTP-viable** (54 > 40 max diameter). Confirm with ÖBB whether triple-traction is operationally required; if yes, only recommendation 4 solves it.

## Open questions

- Which end actually misbehaves in the proposal duel (B1-147 or B3-138)? Needs VDS engineering analysis of the debug logs / BPDU capture.
- Was the same TC churn present in the June 109+110 incident (no debug logging then)? Its escalation into a full multicast storm remains correlation, not proven causation.
- Whether the June storm's primary trigger was F2 (horizon partition), F3 (TC churn escalation), or a Stadler-FW interaction over the VLAN-15 transit remains unresolved — today's composition rules none of them out for that incident. (Note: the VLAN 5↔15 *ring* hypothesis is refuted as the cause of the CCTV/ZFR outage — see A8 — but a VLAN-15 FW↔FW interaction is now the prime suspect.)
- **Which coupled-L2 element actually breaks Stadler FW routing?** VLAN-5 prune refuted (A8); full decouple fixes it. Prime suspect = VLAN-15 FW↔FW transit. Needs Stadler FW-side characterisation, ideally at the Floridsdorf re-test.

## Addendum (11:30Z) — live experiments while coupled

### A1 — Port-cost experiment: TC churn root-caused and fixed

Reverting the active coupler link's hand-set port-cost (137999999 / 146999999) to 20000 on B3-138 + B1-147 stopped the fleet-wide TC churn **at the exact second of the change** (B3-138 TC/flush log count frozen at 2519 from the `Changing PortCost` event onward; topology unchanged, redundant link still ALTR/BLK). Note: both original values exceed 2^27 = 134,217,728 — suspected internal port-cost width overflow in the VDS firmware; question raised with VDS support. 147-side churn had ceased slightly earlier, so the duel may have been asymmetric (138-driven). Blocked-link ports (B1-138 / B3-147 e0-2) still carry the huge values — replace in templates with a value < 2^27.

### A2 — User-visible CCTV/ZFR outage root-caused: VLAN 5↔15 firewall ring (PROVEN)

Driver symptoms while coupled: 119's cab CCTV panels blank, then cross-train panels lost; passenger displays showing ÖBB logo = ZFR unreachable (per Stadler/Nenad: logo means display cannot reach ZFR); severe perceived latency. L2 fabric was healthy throughout (coupler at ~3 Mbps, zero errors); both Stadler FWs alive and commissioned on vlan7 (110: 172.19.197.1; **119: 172.19.201.129 — odd-Fzg FWs sit at .129, not .1**; playbook correction). Device IPs are Fzg-encoded statics — no duplicate-IP possibility (initial hypothesis retracted).

FDB evidence: both FW MACs (110 `00:90:e8:c5:3d:9d`, 119 `00:90:e8:cb:5d:c9`) present in both trains' tables; 110's FW MAC contaminating 119's VLAN 5 via the coupler; entries churning between samples.

Mechanism: Stadler FWs relay local traffic between consists over the VLAN-15 transit; our coupler trunks ALSO bridge VLAN 5 directly. Coupled, VLAN-5 traffic has two parallel paths (direct L2 + FW-relayed via 15) — a forwarding ring **invisible to RSTP because the legs are in different VLANs**. Circulating frames poison FW state, degrading ALL FW routing — including display→ZFR (VLAN 3→2, never touches the coupler).

Intervention proof: 11:00:40Z pruned VLAN 5 from both 110-side coupler ports (`prune allow 15`, native 999 kept). By 11:07Z cross-train VLAN-5 contamination gone from 119's FDB; ~11:15Z driver reports monitors recovering. A 2.5-min single-port prune earlier (10:37–10:40Z) had shown no recovery — FW state needs >5 min clean to converge.

**Decision required (Stadler):** either the FW multitraction relay must not coexist with a direct VLAN-5 coupler bridge, or VLAN 5 comes off coupler trunks fleet-wide (v8 template change). Current prune is runtime-only and reverts on power-cycle. Engineer directive 2026-06-11 (VLAN 5 stays on Frontkupplung; proven 5↔15 ring = Stadler-side fix) now has its proof.

### A3 — Additional template/config findings

- B1-147 e0-2 lacks `native vlan 999` (plain `trunk prune allow 5,15`) — native-VLAN mismatch vs 138 side; fix in v8 templates.
- Odd-Fzg Stadler FW vlan7 address is `.129` (device 1 + 128), not `.1` — CLAUDE.md/skills/08_e2e_probe assume `.1`; every odd-Fzg `FW reach` verdict recorded against `.1` needs re-verification.
- 119's FW appears physically attached at a switch other than A3-147 (own FW MAC learned via backbone on VLANs 2/3/5/7/9 even with clean coupler; e1-4 carries only its VLAN-15 leg) — verify attachment point against the IPA PDF.

## Addendum 2 (end of day, ~17:00Z) — afternoon events and revised conclusions

### A4 — VLAN-5 prune outcome AMBIGUOUS (revising A2's "proven" claim)

After the 11:00:40Z VLAN-5 prune, driver initially reported "some monitors coming back" (~11:15Z), but subsequently reported no lasting improvement (ÖBB logo / blank panels persisted). The FDB-level result stands (cross-train VLAN-5 contamination verifiably cleared), but **user-visible recovery was NOT confirmed** — the 5↔15 ring remains the leading hypothesis for FW-state disruption, not an intervention-proven root cause. The discovery of the C2 outage and link-flap churn (A5/A6) offers a competing/compounding explanation for the symptoms.

### A5 — C2-147 dead mid-day (cold bypass)

nv6-C2-v8-147 answered SSH at 10:02Z and was gone by ~11:13Z: no DHCP lease, LLDP shows C1/C3 peering straight through to A/D-coach switches (VDS cold-bypass relays). Coach-C cameras/APs down with it (AP census 22/24). Unpowered or dead — needs physical inspection/breaker check. If it was boot-looping before going fully dark, its bypass relay cycling is a train-internal TC/root-election churn source.

### A6 — Decoupling anomalies: phantom live links + flapping

After physical decoupling (~11:09Z), 119's switches repeatedly re-elected **110's root bridge** (C1 log: 5 elections 11:11–11:15Z, including foreign root at 11:15Z post-decouple) — at least one coupler link remained electrically alive after "cable removal," and it was **flapping** (root oscillating between own and foreign; continuous TCs). Admin-disabled B1-147 e0-2 at 11:19Z → RSTP failed over to the second still-live link (B3-147 e0-2, foreign root persisted at 11:25Z). 119's CCU then dropped offline mid-investigation. **Lesson: "cables removed" must be verified by port link-state, not assumed** — phantom/half-seated coupler cables produce exactly the TC-churn signature seen all day, and are a strong candidate mechanism for the June 109+110 storm precursor (a marginal coupler cable flapping = continuous fleet-wide FDB flushes).

### A7 — Single-cable recouple attempt (16:50Z) — no link

Crew recoupled with one cable "on B1". B1-147 e0-2 re-enabled at 16:51Z (undoing the 11:19Z disable) — link stayed DOWN on all four 147 cab ports; 110's CCU unreachable since ~11:25Z (train apparently powered down). Cable into a dead train = no link; cross-wiring note: B1-138's e0-2 mates with B3-147's, so a "B1-to-B1" single cable may also be the wrong pairing. Test ended with 119 going offline ~17:00Z.

### A8 — CCTV/ZFR outage root cause CORRECTED: VLAN-5 ring REFUTED; cause is coupled-L2-wide (prime suspect VLAN-15 FW↔FW transit)

**Supersedes A2 and A4.** Confirmed post-test from the engineer's direct on-vehicle observation of the recovery sequence:

- The 11:00:40Z VLAN-5 prune cleared cross-train VLAN-5 FDB contamination but **did NOT restore any service** — monitors stayed blank, ÖBB logo persisted.
- Monitors only began recovering after the **Frontkuppler cables were physically disconnected** from the switches (full decouple).

**Discriminator logic:** the VLAN-5 prune removed exactly one variable — the direct VLAN-5 L2 bridge across the coupler — and changed nothing for the driver. The full physical decouple removed everything else the coupler carried (VLAN-15 FW↔FW transit, native VLAN 1/999 + CCU cross-talk, and the merged RSTP domain) and service recovered. Therefore:

1. **The VLAN 5↔15 parallel-path ring (A2's mechanism) is REFUTED as the cause.** Severing the VLAN-5 leg should have broken that ring; it did not restore service. The VLAN-5 FDB contamination clearing was a real but **causally irrelevant side-effect** — VLAN-5 cross-bridging was never what broke the displays/cameras.
2. **The cause is some disruption introduced by the coupled L2 state as a whole**, removed only by full decouple. Ranked suspects:
   - **VLAN-15 FW-to-FW transit (PRIME SUSPECT).** VLAN 15 is the multitraction transit that lets the two Stadler firewalls talk when coupled. The display→ZFR (ÖBB-logo) symptom is the tell: displays (VLAN 3) and ZFR (VLAN 2) **never cross the coupler**, so coupling can only break that path by **disrupting the Stadler firewall's own routing/state** — and the sole FW↔FW channel is VLAN 15. Squarely Stadler's domain (FW multitraction relay behaviour with both consists present).
   - **Residual RSTP / coupler-link instability** — the A6 flapping phantom links = continuous TC churn = FW state never settles. Plausible intermittent contributor.
   - **Native-VLAN / CCU cross-talk** — least likely to break Stadler services (VLAN-1 Nomad artefact) but also removed only by decouple, so not fully excluded.

**Only confirmed mitigation:** full physical decouple. Pruning VLAN 5 is NOT a fix (refuted). This is consistent with the engineer directive (VLAN 5 stays on Frontkupplung) — there is no service reason to prune it, and the real fix is Stadler-side (VLAN-15 FW relay behaviour when coupled).

**Decision required (Stadler):** characterise what the Stadler firewall does when two consists are L2-coupled and the two FWs see each other over the VLAN-15 transit — this is the leading cause of the coupled-operation CCTV/display degradation. The earlier "remove VLAN 5 from the coupler" ask (A2) is withdrawn.

### Runtime state left on the trains (all non-persisted, cleared by power cycle)

| Train | Change | State at end of day |
|---|---|---|
| both | `system logging debug rstp,coupled` on all 36 switches | ON (runtime) |
| 110 | VLAN 5 pruned off B1/B3-138 e0-2 (`prune allow 15`) | ON (runtime) — restore `prune allow 5,15` before next coupled service if Stadler wants direct VLAN-5 bridging back |
| 110 | B3-138 e0-2 port-cost 20000 (was 137999999) | ON (runtime) |
| 119 | B1-147 e0-2 port-cost 20000 (was 146999999); port re-enabled | ON (runtime) |
| both | CCU storm watchers `/tmp/bond0_storm_watch.sh` | running until reboot |

### Consolidated handover items

1. **VDS (Giorgio):** TC churn evidence + port-cost >2^27 overflow question + max-age 38/forward-delay 20 recommendation + RSTP debug traces (tc_trace files). Also: confirm BPDUs bypass `rate-limit broadcast`.
2. **Stadler:** (a) C2-147 dead — physical/power check, (b) 5↔15 FW relay vs direct VLAN-5 coupler bridge design question + FDB evidence, (c) coupler cable integrity — flapping phantom links observed after decoupling, (d) ZFR/ÖBB-logo symptom correlation data.
3. **Nomad fleet actions:** odd-Fzg FW = `.129` correction (CLAUDE.md, 08_e2e_probe, re-verify all odd-Fzg `FW reach` verdicts); v8 template fixes (coupler port-cost < 2^27, B1-147-style missing `native vlan 999`); fleet-status update for 110/119.

## Cleanup before trains split

- `no configure system logging debug` on all 36 switches (currently runtime-only, not saved — a power cycle also clears it).
- Storm watchers on both CCUs (`/tmp/bond0_storm_watch.sh`) still running — kill or leave to die on reboot.
