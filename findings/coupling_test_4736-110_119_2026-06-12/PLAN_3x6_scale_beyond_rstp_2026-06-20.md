# DOSTO 3x6 / >40-node scaling — architecture recommendation

**Source:** multi-agent design panel (4 approaches developed + adversarially stress-tested; 1 survived), 2026-06-20.
**Companion to:** PLAN_v9_switch_config_changelist_2026-06-20.md (the 2x6 fix that ships first).

---

I have grounded all the firmware claims. Now I'll write the report.

# DOSTO Triple-Traction (>40-node) Architecture Recommendation

**Question:** how should DOSTO support up to 3 coupled consists (~52 switches) past the RSTP 40-node ceiling?
**Author:** Lead architect · 2026-06-20 · firmware claims grounded in `switch_user_manual.pdf` v2.0.4 (`.claude/switch_manual.txt`) and live config/coupling-test evidence.

---

## 1. TL;DR recommendation

**Do not solve >40 nodes inside the VDS switch fabric. Terminate inter-consist traffic at Layer 3 — preferably at the Stadler firewalls per IEC 61375-2-5, with switch-native TCDS Routed Mode held as a Nomad-owned fallback only if Stadler cannot/won't own the L3 boundary.** Three facts force this. (1) The 40-node ceiling is a property of a single L2/STP domain; the *only* way to support 3×6 is to stop bridging the coupler and make it an IP hop — every viable approach is some flavour of "route, don't bridge." (2) The switch firmware genuinely supports a routed boundary (TCDS Routed Mode + R-NAT + vTBN, §21.5), so the mechanism is real — **but** it has no dynamic multicast routing (`PIM/DVMRP unsupported`, manual L5019-5021), which would silently black-hole VLAN-5 CCTV the moment the coupler is routed, and the fleet has **zero field hours** on any L3 feature (all live configs are pure L2). (3) The proven coupled-operation outage is **already a Stadler-side VLAN-15 FW↔FW problem** (coupling-test A8), so the firewalls are the natural and correct place to terminate inter-consist traffic — doing it there forces resolution of the VLAN-15 question instead of quietly routing around it. **Critically, this is a SEPARATE, LATER workstream gated on ÖBB confirming triple-traction is even required** — the already-decided v9 (flat coupler cost + native-999 + max-age 38) makes the *confirmed* 2×6 envelope robust and field-proven today, and must ship first regardless.

---

## 2. Comparison table

| Approach | Breaks 40-node limit for 3×6? | Firmware-supported? | 2×6 impact | Stadler-FW impact | Effort | Confidence | Survived stress-test? |
|---|---|---|---|---|---|---|---|
| **A. TCDS Routed Mode + R-NAT/vTBN** (§21.5) — switch-native L3 boundary | **Yes** — RSTP becomes per-consist (≤18) not per-composition | Primitives real (L9037-9101; R-NAT L5208-5355) but **no dynamic multicast** (L5019-5021); "5 consists" is *plain-mode discovery* (L8990-8993), not a validated routed deployment | High & behaviour-changing — replaces working flat-L2 coupling with unproven L3+NAT for the common case | **High risk** — breaks VLAN-5 CCTV multicast by default; routing VLAN-15 likely breaks the FW↔FW relay it exists for | High | **Low** | **No** — fatal CCTV-multicast default-break; core R-NAT premise (192.168.1.0/24 collision) is **false** (VLAN 1 not trunked across coupler — cable-reg #10) |
| **B. Terminate inter-consist at Stadler FWs (IEC 61375-2-5)** — FWs are the L3 boundary; coupler stops bridging | **Yes** — each consist L2 island ≤18; FWs route between them | N/A in switch firmware (Stadler-owned); IEC-standard pattern | Low on switch side once coupler stops bridging; needs the v9 envelope underneath | **Owned by Stadler** — forces resolution of the VLAN-15 FW↔FW issue (the actual outage) rather than routing around it | Medium-High (Stadler-led) | **Medium-High** | **Yes (recommended)** — the stress-test's own "harder, more honest" endpoint |
| **C. Coupled-Switch mode** (§20.3, `role master\|slave`, IST) | **No** — pairs two switches into one engine (removes ~structural ports from STP); reduces node count marginally, does not segment per-consist | Real (L8444, L8530) | Designed for fixed mechanically-paired switches, not field-coupled trains | Neutral | Medium | Low (wrong tool) | **No** — addresses intra-pair STP, not multi-consist node count |
| **D. Composition Lock + Head flag alone** (§21.6) | **No** — solves root-determinism/numbering, not node count | Real (L9155-9264, `sysadmin set composition head` L9217) | Positive (deterministic root) — useful *adjunct* to A or B | Neutral | Low | High (for what it does) | Partial — necessary companion to a routed approach, insufficient alone |

---

## 3. Recommended approach in detail — terminate inter-consist traffic at L3 (Stadler FW primary; TCDS Routed fallback)

The recommendation is a **two-track, sequenced** plan. Track 1 (v9) is already decided and proven — ship it. Track 2 (>40) is the new workstream, and within it the *primary* design is **FW-terminated L3 per IEC 61375-2-5**, with **switch-native TCDS Routed Mode as the Nomad-owned fallback** (see §4).

### Why FW-termination is primary over switch-native routing

- It puts the L3 boundary where the inter-consist service architecture already lives. The Stadler FWs **already** relay inter-consist traffic over VLAN-15 (`FW↔FW transit`); the IEC-61375-2-5 model is precisely "consist-local L2, inter-consist at the train-backbone router." Stadler is the train-backbone router.
- It is the only path that **forces** resolution of the VLAN-15 FW↔FW problem that coupling-test **A8** identified as the prime cause of the coupled CCTV/ZFR/display outage. Switch-native R-NAT routes *around* that question and leaves it unresolved (or worsens it).
- It avoids the firmware's fatal multicast gap on the Nomad side: CCTV is unsnooped VLAN-5 multicast today; the switch has no dynamic multicast routing (L5019-5021). Keeping CCTV relay on the FW path (its current design) sidesteps a brittle, position-dependent static `mroute` table that would have to be Jinja2-templated across 4 repos and re-derived per composition length/orientation.

### Concrete steps

**Pre-work (gates — do not build anything until these clear):**
1. **ÖBB gate:** confirm triple-traction (3×6) is an actual operational requirement. v9 D1 already records this as open. If "no," the entire Track-2 workstream is shelved — do not build a safety-relevant redesign for a hypothetical.
2. **Stadler gate:** characterise FW behaviour when two (then three) consists are L2-coupled over VLAN-15 — i.e. close the A8 investigation. This is a hard prerequisite: if the FWs already misbehave at 2 consists over VLAN-15, they must be fixed before being asked to be the L3 boundary for 3.
3. **VDS/Giorgio gate:** if FW-termination cannot be delivered by Stadler and we fall to Track-2 fallback (TCDS Routed), get VDS to confirm Routed Mode + vTBN + R-NAT behaviour **and the static-multicast-only limitation** on the exact deployed build v2.0.4, and confirm whether any customer has run routed mode in revenue service (the manual demonstrates primitives, not a validated 3-consist routed deployment).

**Design (FW-terminated primary):**
4. The coupler stops being an L2 bridge for routed VLANs. Each consist's internal ring stays its own ≤18-node RSTP domain. The Stadler FWs become the inter-consist L3 boundary; inter-consist flows (mgmt/data) are routed FW↔FW. CCTV/display inter-consist relay stays on the FW path (Stadler-owned), resolving A8 rather than re-implementing it on the switches.
5. **Composition determinism (Track-2 companion, low-risk):** adopt Composition Lock + Head flag (`sysadmin set composition head`, L9217; lock `direct|reversed|forced`, L9299) so consist numbering/orientation and STP root are deterministic across couplings — needed by *any* routed boundary that uses position-dependent addressing.

**What goes where:**
- **Templates (OBN nv6/nv4/fv5/fv6):** for the primary FW-terminated design, the switch-side change is to stop the coupler bridging the routed VLANs — minimal switch config beyond v9. For the *fallback* (TCDS Routed), the heavier template work lands here: per-boundary-switch `configure tcds mode routed` / `backbone-vlan` / boundary-port `direction dir1|dir2`, vTBN SVI + `tcds vtbn enable` + `ip routing enable`, R-NAT rules, plus the static `tcds vtbn mroute` table for CCTV (L9150) — and a VRRP backup vTBN.
- **CCU/OBN:** config-only via existing Jinja2 → `.deb` → Puppet → `obn update c` path (leaf-first, reboots switches). No new OBN code feature. Add commissioning verification: `show tcds composition`, `show spanning-tree` (must show a separate root per consist), and for the fallback `show ip nat` / `show ip route` / `show ip mroutes`.
- **Stadler:** owns FW↔FW inter-consist routing, the VLAN-15 relay behaviour, and CCTV/display cross-train relay. This is the bulk of the primary-design work and is **outside Nomad's switch fabric**.

### Test & rollout — incremental and reversible

- **Reversibility:** entirely config/template-driven and git/Puppet-revertable. Reverting coupler stanzas to plain L2 (`trunk … prune allow 5,15`) and removing any tcds/vtbn block via `obn update c all` restores today's behaviour.
- **Roll out atomically per coupled-pair, never switch-by-switch** — a routed consist coupled to a plain consist is undefined/asymmetric.
- **Test ladder:** bench (single-consist routed mode + addressing) → one revenue 2×6 pair under a maintenance window (verify two independent STP roots, CCTV/display end-to-end, FW↔FW transit) → **a genuine 3×6 physical trial** before any fleet-wide claim. The 3-consist trial is the hard-to-arrange but mandatory proof; until it passes, ">40 supported" is documented-not-proven.

---

## 4. Fallback / hybrid if the primary hits a wall

**If Stadler cannot or will not own the L3 boundary (FW-termination blocked):** fall back to **switch-native TCDS Routed Mode (Approach A)** — but only with the multicast gap explicitly engineered around, not ignored:
- Keep CCTV/display inter-consist relay on the **Stadler FW VLAN-15 path** even in the routed-switch design (the firmware can't dynamically route the multicast). TCDS Routed then owns *only* consist-switch L2 segmentation + mgmt/data routing. This is the realistic hybrid: switch-native L3 for unicast mgmt/data, FW-relay for CCTV multicast.
- Mandatory companions: VRRP backup vTBN (the vTBN is otherwise a single point of failure), Composition Lock + Head flag (else DIR1/DIR2 and position addressing invert run-to-run), and **drop the R-NAT-for-192.168.1.0/24 rationale entirely** — that subnet does not cross the coupler (cable-reg #10), so R-NAT is only needed for genuinely-overlapping VLANs, which must be enumerated first.

**If 3×6 is confirmed *not* required by ÖBB:** the fallback is to do nothing beyond v9 — document ≤2×6 as the supported envelope and close the workstream. This is the likely and acceptable outcome.

---

## 5. Decisions / inputs needed from humans

1. **ÖBB — is triple-traction operationally required at all?** (v9 D1, open.) This gates the entire workstream. Everything below is moot if "no."
2. **Stadler — FW behaviour when consists are L2-coupled over VLAN-15** (close coupling-test A8). Prime suspect for the existing 2×6 CCTV/ZFR/display outage; must be resolved before the FWs can be the 3×6 L3 boundary. Also: will Stadler own FW↔FW inter-consist routing per IEC 61375-2-5?
3. **VDS/Giorgio — confirm on build v2.0.4:** (a) TCDS Routed + vTBN + R-NAT behaviour as documented; (b) the static-multicast-only limitation (no PIM/DVMRP) and its operational impact on CCTV; (c) whether routed mode has ever run in revenue service anywhere, or if DOSTO would be the first field deployment.
4. **Nomad R&D — if fallback chosen:** own OBN template changes, the backbone address plan, the per-coupling static `mroute` generation for CCTV, and the VRRP vTBN redundancy design.

---

## 6. Fit with the already-decided v9 — yes, it is a separate later workstream; v9 does not foreclose it

**v9 is the 2×6 envelope and ships first, independently.** Its three MUST-FIXes (M1 symmetric coupler cost `20000`; M2 native-`999` + `prune allow 5,15` containment; M4 `forward-delay 20` / `max-age 38`) make the *confirmed-required* 2×6 case robustly correct and field-proven (validated 2026-06-12). The v9 plan **already explicitly defers** >40: D1 states "3×6 = 54 nodes (over the 40-node ceiling — no timer value fixes a node-count limit)… Triple-traction needs a different L2 mechanism (terminate L2 at coupler / route via Stadler FWs) — escalate." This recommendation *is* that escalation, and it lands exactly where v9 pointed.

**Does v9 foreclose the >40 solution? No — and it is mildly enabling:**
- **M2 native-999 containment** is *consistent* with a future routed boundary: draining untagged traffic to a dead VLAN and keeping VLAN 1 off the coupler is exactly the hygiene a routed/terminated coupler wants. No conflict.
- **M1 flat coupler cost** is L2-domain behaviour that simply becomes irrelevant once the coupler is routed (RSTP no longer spans it) — it does not block the change.
- **M4 max-age 38** is explicitly scoped to 2×6 and the v9 release note must state ≤2×6 is RSTP-supported — which keeps the door open for a *different mechanism* at 3×6 rather than implying a timer fix exists.

**One thing v9 should preserve for the future (no change needed, just don't undo it):** keep VLAN 5 on the coupler (engineer directive; A8 confirmed pruning it is not the fix) and keep the load-bearing `5,15` set commented (v9 S4). The >40 workstream will revisit how VLAN-5/15 cross a routed boundary; v9's job is just to not pre-empt that decision — which it doesn't.

**Net sequencing:** Ship v9 now (proven, 2×6). Open the >40 workstream only on an ÖBB "yes," starting with the Stadler A8 characterisation and the VDS v2.0.4 confirmation — not with template code.

---

**Confidence statement (honest):** High confidence that the *mechanism* must be "route the coupler, don't bridge it" — this is forced by the node-count physics and confirmed by VDS. High confidence the firmware primitives for the switch-native fallback are real (verified in-manual: §21.5 L9037-9101, R-NAT L5208-5355, composition lock L9155-9264). High confidence the switch-native approach as originally proposed does **not** survive (CCTV multicast default-break per L5019-5021; false 192.168.1.0/24-collision premise per cable-reg #10; "5 consists" is plain-mode *discovery* per L8990-8993). **Medium** confidence on FW-termination as primary — it is architecturally correct and IEC-standard, but the bulk of it is Stadler-owned and depends on the unresolved A8 VLAN-15 investigation. The single largest open variable is non-technical: **whether ÖBB needs triple-traction at all.**

---

Key grounding files (absolute paths):
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\.claude\switch_manual.txt` — multicast static-only L5019-5024; TCDS routed §21.5 L9037-9101; "5 consists / plain mode" L8990-8993; coupled-switch §20.3 L8444/L8530; composition lock/head §21.6 L9155-9264, L9217.
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\findings\running-config_nv6-A3-v8-138_10.179.23.179_2026-06-11.txt` — coupler e0-2 = `trunk prune allow 5,15` (L83); VLAN 1/100 not in coupler allow set.
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\cable-issues-register.md` — #10 (L227-229): VLAN 100/1 NOT bridged across coupler; only untagged native crosses.
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\findings\coupling_test_4736-110_119_2026-06-12\REPORT_coupling_test_2026-06-12.md` — A8 (L121-138): CCTV/ZFR outage = coupled-L2-wide, prime suspect VLAN-15 FW↔FW transit; VLAN-5 ring refuted.
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\findings\coupling_test_4736-110_119_2026-06-12\PLAN_v9_switch_config_changelist_2026-06-20.md` — v9 MUST-FIX M1-M4, D1 (3×6 not RSTP-viable, escalate to different mechanism).