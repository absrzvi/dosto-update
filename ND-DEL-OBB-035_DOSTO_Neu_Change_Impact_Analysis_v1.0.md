# ÖBB DOSTO Neu — Change Impact Analysis (Non-Repercussions)

**Document details**

| Field | Value |
|---|---|
| Title | ÖBB DOSTO Neu — Change Impact Analysis (Non-Repercussions) |
| Purpose | Assess the operational impact of changes to the delivered IoB baseline, and state where no adverse repercussion arises |
| Issued to | ÖBB — Österreichische Bundesbahnen |
| Document Reference | ND-DEL-OBB-035-CIA-001-01 |
| BMS Document Reference | BMS-ENGI-FOR-006-02 |
| BMS Version Number | 01 |
| Last updated | 14 July 2026 |
| Approver | *(TBD)* |
| Number of pages | — |
| Related documents | ND-DEL-OBB-035-RN-001-01 (HW & SW Release Note); ND-DEL-OBB-035-RM-001-01 (Software / Firmware Package Release Plan); ND-DEL-OBB-035-SDD-002-01 / -003-01 (System Design Documents); ND-DEL-OBB-035-REL-001-01 (Switch Configuration Release Notes); ND-DEVOPS-OBB-TER-026-04 (Nomad Connect Test Exit Report) |

This document and any related documents contain strictly confidential information intended only for the designated recipient(s). Any unauthorised disclosure, dissemination, distribution or copying of this document or any related documents in any form is strictly prohibited.

## Document control

| Version | Revision date | Summary of edits | Created By | Approved By |
|---|---|---|---|---|
| 1 | 14 July 2026 | First version of the document | Abbas Rizvi | *(TBD)* |

## Disclaimer of liability

The information in this document is subject to change without notice and should not be construed as a commitment by Nomad Digital Ltd. While reasonable precautions have been taken, Nomad Digital Ltd assumes no responsibility for technical inaccuracies or typographical errors that may appear in this document. Nomad Digital Ltd reserves the right to revise this publication without obligation to provide notification of such revisions.

---

## 1. Introduction

### 1.1 Document Purpose

This document assesses the impact of each change to the delivered Internet-on-Board (IoB) baseline on the ÖBB DOSTO Neu project, and states — with the reasoning behind it — where a change carries **no adverse repercussion** for passenger service, for vehicle systems, or for the existing delivered baseline.

The assessment is made per change. For each, this document records:

- **What changes**, in operational terms.
- **What it affects** — the functions, systems and interfaces within the change's reach.
- **What it does not affect**, and why that boundary holds.
- **The residual impact**, if any, and how it is contained.
- **The verification** by which the assessment is or will be substantiated.

### 1.2 Method

Each change is assessed against four questions:

1. **Reach** — which systems can the change physically or logically touch?
2. **Passenger service** — can the change interrupt or degrade the passenger Wi-Fi service, and if so, when and for how long?
3. **Vehicle systems** — can the change affect systems outside the Nomad onboard network?
4. **Reversibility** — can the change be withdrawn, and at what cost?

A change is assessed as **no adverse repercussion** only where the reach is bounded by an argued technical boundary, not merely where no problem has been observed.

### 1.3 Scope boundary

This analysis covers the **Nomad onboard network**: the CCU, the VDS Rail consist switches, the Westermo access points, and their configuration.

Nomad provides the configuration of the switch ports serving Stadler devices. **The testing of those devices is Stadler's responsibility.** The Nomad boundary ends at the switch-port configuration and at the transit link to the vehicle firewall; Stadler performs inter-VLAN routing and owns the device VLANs (cameras, displays, passenger information, intercom, on-board systems, remote data communication and energy metering). The Nomad CCU has no visibility of those VLANs and no route into them.

This boundary is what makes several of the "does not affect" statements in this document sound, and it is stated once here rather than repeated per change.

---

## 2. Baseline under assessment

The delivered baseline against which these changes are assessed is that recorded in the HW & SW Release Note (ND-DEL-OBB-035-RN-001-01):

| Item | Version |
|---|---|
| VDS Rail Consist Switch firmware | 7.4.2 |
| VDS Rail Consist Switch configuration | V8 |
| Westermo RT610LV access point firmware | 6.11.2-0 (IbexOS) |
| Nomad Connect / onboard-network engine (nd-obn) | 2.2.23 |
| CCU platform image (Nomad Connect) | 2025.2.1 |

---

## 3. Change impact — Switch configuration V9

**V9 is an interim multi-traction workaround, not the multi-traction design.** It makes **2 × 6-car** coupled operation stable enough for service by removing specific fault conditions observed in the field. The designed solution — full multi-traction including 3 × 6-car — is V10, in Package 2, subject to its own design freeze (§4.1).

This framing matters for reading the assessments below. Each V9 change is assessed as *"does this remove a fault condition without introducing another"* — the correct question for a workaround. It is **not** assessed as *"does this deliver multi-traction"*, which it does not claim to.

V9 does not alter single-consist operation. The five constituent changes are assessed individually below, then collectively.

### 3.1 V9-1 — Symmetric coupler port cost

| | |
|---|---|
| **What changes** | The spanning-tree port cost on the four coupler ports is set to a single fixed value, identical at both ends of every coupler link and on every train. Previously the value was derived per train, so the two ends of a coupler link disagreed. |
| **What it affects** | Spanning-tree path selection across a coupler link, in the coupled state only. |
| **What it does not affect** | Single-consist operation. When a train runs solo the coupler ports carry no link, so the port cost is not evaluated and behaviour is bit-for-bit identical to V8. |
| **Residual impact** | None identified. The change removes a condition; it does not add one. |
| **Verification** | Field-validated on a coupled pair on 12 June 2026: setting the cost symmetrically stopped the continuous topology-change condition immediately. Runtime re-test on a coupled pair before release. |

**Assessment: no adverse repercussion.** The prior asymmetric value was the cause of a continuous spanning-tree reconvergence condition in the coupled state. Symmetry resolves it. In the solo state the parameter is not reached.

### 3.2 V9-2 — Coupler native-VLAN containment

| | |
|---|---|
| **What changes** | The coupler trunk's untagged (native) VLAN moves from VLAN 1 to an unused VLAN. The set of VLANs permitted to cross the coupler is unchanged. |
| **What it affects** | Untagged traffic at the coupler boundary. After the change, only the two intended VLANs — CCTV and the multi-traction transit VLAN — cross between coupled trains. |
| **What it does not affect** | The permitted VLAN set is **unchanged** — no VLAN that crossed the coupler before is prevented from crossing now. CCTV continues to cross. Single-consist operation is unaffected, as the coupler carries no link. |
| **Residual impact** | None identified for intended traffic. The change removes an unintended path. |
| **Verification** | Applied and validated in the field on coupled pairs; runtime re-test before release. |

**Assessment: no adverse repercussion.** This change closes an unintended leak rather than restricting an intended flow. Without it, untagged traffic — including the switch-management subnet, which is identical on every train — crosses between coupled trainsets. Two coupled trains therefore present duplicate management addressing to each other. Containing the native VLAN removes that overlap. Because the permitted VLAN set is untouched, no service that crossed the coupler stops crossing it.

### 3.3 V9-3 — Definition of the containment VLAN

| | |
|---|---|
| **What changes** | An unused VLAN is defined in each platform template to serve as the drain for untagged traffic. |
| **What it affects** | Nothing operationally. It is the supporting definition for V9-2. |
| **What it does not affect** | No user-visible or service-visible behaviour. No traffic is assigned to this VLAN by design. |
| **Residual impact** | None. |
| **Verification** | Covered by the V9-2 validation. |

**Assessment: no adverse repercussion.** Supporting definition only.

### 3.4 V9-4 — Spanning-tree timer widening

| | |
|---|---|
| **What changes** | The spanning-tree forward-delay and max-age timers are set explicitly, replacing the firmware defaults, identically on every switch in every platform. |
| **What it affects** | The time the merged coupled network takes to converge after a topology change, and the network diameter the protocol can span. |
| **What it does not affect** | Traffic forwarding in the steady state. Timers govern convergence behaviour, not forwarding. |
| **Residual impact** | **Convergence after a topology change takes marginally longer.** This is the intended trade and is discussed below. |
| **Verification** | Values are per VDS Rail guidance. Runtime re-test on a coupled pair before release. |

**Assessment: no adverse repercussion, with a stated trade.** This is the one V9 change with a real cost, and it should be read as a trade rather than a free improvement.

The measured diameter of a coupled 2 × 6-car network is 31 hops, with the far end sitting **exactly on the default 20-hop limit — zero margin**. At zero margin, spanning-tree control messages may not reach the far end of the coupled network reliably, and the protocol's correctness assumptions do not hold. Widening the timers restores adequate margin for the coupled case.

The cost is that reconvergence after a topology change takes longer than with the default timers. In exchange, the coupled network converges *correctly* rather than quickly-but-unreliably. Applied uniformly, the timers are consistent across every switch, which is itself a precondition for correct operation. In the solo case, where the diameter is well within the default limit, the widened timers are conservative rather than necessary — the trade is accepted for uniformity, since a single fleet-wide template is materially safer to operate than a per-state variant.

### 3.5 V9-5 — Consistency and documentation

| | |
|---|---|
| **What changes** | A port-description typo is corrected and explanatory comments are added to load-bearing settings in the templates. |
| **What it affects** | Nothing operationally. |
| **What it does not affect** | No forwarding, no configuration semantics. Descriptions and comments are not interpreted by the switch. |
| **Residual impact** | None. |
| **Verification** | Template review. |

**Assessment: no adverse repercussion.** Documentation only. Its purpose is to prevent a future edit from silently undoing a load-bearing setting.

### 3.6 V9 — collective assessment

| Question | Assessment |
|---|---|
| **Reach** | The four coupler ports and the spanning-tree parameters of the consist switches. V9 does not touch access-point configuration, the CCU, or any port serving a Stadler device. |
| **Passenger service** | No steady-state impact. Applying V9 requires a switch configuration push, which reboots the switch — see §5. |
| **Vehicle systems** | None. The permitted VLAN set across the coupler is unchanged, so no Stadler device sees a change in what reaches it. Testing of Stadler devices remains Stadler's responsibility (§1.3). |
| **Reversibility** | Fully reversible by re-pushing the V8 template. |

**V9 supported envelope: up to 2 × 6-car (36 switches), within the 40-node protocol limit.** As an interim workaround, V9 makes the 2 × 6-car coupling case stable enough for service. It does not extend the envelope beyond that, and does not claim to — 3 × 6-car is delivered by V10, see §4.2.

---

## 4. Change impact — Package 2 and beyond

The following are **not in Package 1**. They are recorded here so that ÖBB have the position in advance, and so the reasons they are not yet proposed for release are explicit rather than implied.

### 4.1 Switch configuration V10 — full multi-traction (Package 2)

**Status: design not yet reviewed or frozen. No impact assessment is possible at this time.**

V10 delivers full multi-traction support, including 3 × 6-car, by terminating Layer 2 at the consist boundary and routing between consists. It is an **architecture change**, not a configuration adjustment, and it replaces V9's interim workaround with the designed solution.

**Why no assessment is offered:** an impact assessment assesses a design. V10's design has not yet been reviewed or frozen — it requires input from ÖBB (operational requirement for 3 × 6-car), Stadler (firewall behaviour across coupled consists, and ownership of the inter-consist Layer-3 boundary) and VDS Rail (routed-mode behaviour). Assessing the impact of a design that does not yet exist would be an invention.

Two consequences follow, and both are material:

- **Multicast handling** (IGMP snooping and querier behaviour across a coupled composition) is resolved **within** the V10 design, not as a standalone change. Its correct behaviour depends on where the inter-consist boundary sits, so it cannot be assessed before that is decided. The known open question — whether multicast is flooded (safe) or pruned (**CCTV loss**) when snooping is enabled without an active querier — is an input to the V10 design review, not a separate item.
- **The 3 × 6-car limit is not a tuning question.** 54 switches exceeds the 40-node spanning-tree protocol limit. No firmware version, configuration value or timer setting can raise it. This is why V10 is an architecture change and why V9 cannot be extended to cover it.

**Assessment: to be produced once the V10 design is frozen.** This document will be revised at that point. Nomad will not propose V10 for release before its design freeze, FAT and ÖBB bench testing.

### 4.2 VDS switch firmware 7.4.8

**Status: candidate in Package 1. Approved via the ÖBB bench-testing gate, not before it. Until that gate passes, the fleet target remains 7.4.2.**

Switch firmware 7.4.8 enters Package 1 (ND-DEL-OBB-035-RM-001-01) as a candidate, and is tested as part of that package at FAT and then at ÖBB bench testing. The bench gate is the mechanism by which it becomes approved for the fleet.

| | |
|---|---|
| **What changes** | The consist-switch firmware version, fleet-wide. |
| **What it affects** | Switch behaviour in full. A firmware change is the broadest change in the package and is assessed as such. |
| **What it does not affect** | The access points and their configuration, which are unchanged in Package 1. |
| **Residual impact** | To be established by FAT and ÖBB bench testing. Firmware is validated in combination with switch configuration V9, since that is the combination the fleet will run. |
| **Verification** | FAT, then ÖBB bench testing. Approval is the bench gate. |

**Assessment: impact to be established at the bench gate.** No claim of no-adverse-repercussion is made for 7.4.8 in advance of the testing that is designed to establish it. This document will be revised once the bench gate is passed.

**Assessment of the current baseline: no impact**, because until the gate passes, no change to the delivered baseline takes effect.

### 4.2 Triple traction (3 × 6-car) — delivered by V10, not by V9

**Status: within the scope of V10 (Package 2). Not supported by V9 (Package 1).**

Three coupled 6-car trainsets total 54 switches. This **exceeds the 40-node spanning-tree protocol limit**. It is a node-count limit in the protocol itself: no timer value, no cost value, and no configuration change can raise it.

**V9's timer widening addresses network *diameter* for the 2 × 6-car case. It does not address *node count*. The two must not be conflated** — this is the single most likely misreading of V9, and it is why V9's envelope is stated as 2 × 6-car throughout.

Operating 3 × 6-car after Package 1 would place the network outside the protocol's supported bounds. It is supported only after V10, which terminates Layer 2 at the consist boundary and routes between consists so that each train's network stays its own bounded domain irrespective of formation length.

**Assessment: out of envelope until V10.** Stated plainly because the gap is between a confirmed ÖBB operational intent (3 × 6-car) and what Package 1 delivers (2 × 6-car), and it is better surfaced now than discovered in service.

---

## 5. Impact of the delivery mechanism itself

The changes above are delivered by pushing a configuration or firmware image to each device during the rollout window (ND-DEL-OBB-035-RM-001-01 §4.4). The delivery mechanism carries impact independent of any change's content.

**All updates are installed remotely**, pushed from the Nomad CCU over the vehicle's own network. No attendance at the vehicle is required. Remote installation changes how the work is delivered; it does not change what happens on the train when the change lands, and the assessment below turns on the latter.

| | |
|---|---|
| **What happens** | Applying a switch configuration reboots the switch — this is how the configuration is persisted. Applying switch firmware likewise requires a restart. Package 1 changes both, so each switch restarts during installation. This is unavoidable and is not altered by installing remotely. |
| **Passenger service impact** | While a switch restarts, the passenger Wi-Fi it serves is unavailable. The interruption is per device, and the network reconverges around it. |
| **Vehicle systems impact** | Devices connected to a switch being restarted lose their network path for the duration of that restart. This includes Stadler devices on that switch. |
| **Containment** | Installation is performed **when the vehicle is not in passenger service** — never during revenue operation. There is no fixed maintenance window; availability is established per vehicle, either on notification from Stadler / ÖBB or confirmed from CCU telemetry before the push. Installation is sequenced so that a device restart does not isolate devices behind it. |
| **Reversibility** | Configuration is reversible by re-pushing the prior template. Firmware is reversible by re-flashing the prior image. Both are remote operations. |

**Assessment: no adverse repercussion to passenger service, conditional on timing.**

This assessment rests on **when** the package is installed, not on any property of the changes themselves. The distinction is material and is stated rather than buried:

- Installed to a vehicle that is not in service, the switch restarts fall outside passenger service and there is no passenger impact.
- Installed to a vehicle in service, passengers would see the Wi-Fi drop as each switch restarted. Nothing in the package prevents this — only the timing does.

The condition is therefore part of the assessment, not an operational footnote to it: **package installations are performed only when the vehicle is not in passenger service.** If that practice is not maintained, this assessment does not hold.

**How the condition is met.** There is no fixed maintenance window on this project. Availability is established per vehicle from either of two sources: **notification** from Stadler or ÖBB that a vehicle is available, or **CCU telemetry** confirming the vehicle is parked and not in service. Telemetry is the check immediately preceding the push. Vehicle availability is therefore a **shared dependency** — Nomad can use availability when it arises or is advised, but cannot create it.

**Connectivity dependency.** Remote installation requires the vehicle to be reachable over its cellular link for the duration. A vehicle that is powered down or out of coverage is not reached and is picked up later. This is a deferral, not a fault, and carries no impact.

---

## 6. Items outside Nomad's scope

The following are recorded for completeness. They are Stadler-side or vehicle-side matters, and are not repercussions of any Nomad change.

- **Open cabling faults.** Physical cabling and port-assignment faults identified during Nomad health checks require Stadler action to re-cable, re-patch or install missing cables. These are pre-existing installation matters, tracked and reported separately. They are not caused by, and are not affected by, the changes in this document.
- **Firewall commissioning.** Commissioning of the vehicle firewall on the transit link is a Stadler activity, incomplete on some trainsets. It does not affect the Nomad onboard-network baseline.
- **Testing of Stadler devices.** Per §1.3, Nomad provides the switch-port configuration for Stadler devices; testing those devices is Stadler's responsibility.

---

## 7. Summary of assessments

| Change | Status | Impact assessment |
|---|---|---|
| V9-1 Symmetric coupler port cost | Decided | **No adverse repercussion** — removes a fault condition; not reached when solo |
| V9-2 Coupler native-VLAN containment | Decided | **No adverse repercussion** — closes an unintended path; permitted VLAN set unchanged |
| V9-3 Containment VLAN definition | Decided | **No adverse repercussion** — supporting definition, no traffic |
| V9-4 Spanning-tree timer widening | Decided | **No adverse repercussion, with stated trade** — slower reconvergence in exchange for correct convergence at coupled diameter |
| V9-5 Consistency and documentation | Decided | **No adverse repercussion** — non-operational |
| **V9 collectively** | **In Package 1** | **No adverse repercussion within a 2 × 6-car envelope**, subject to coupled-pair runtime re-test and the bench gate |
| VDS firmware 7.4.8 | **In Package 1** | **To be established at the bench gate** — tested in combination with V9; no advance claim made |
| Nomad Connect 2025.3 | **In Package 1** | **To be established at FAT and the bench gate** — Test Exit Report is the evidence |
| Westermo AP firmware / config | **Not in Package 1** | **No impact** — unchanged at 6.11.2-0 |
| **V10 — full multi-traction** | **Package 2** | **Not assessable yet** — design not reviewed or frozen; assessment follows the design freeze |
| Triple traction 3 × 6-car | Delivered by V10 (Package 2) | **Out of envelope until V10** — exceeds the 40-node protocol limit; needs the routed design, not a config value |

### 7.1 Statement

For switch configuration **V9**, taken as a whole and within its stated 2 × 6-car envelope, Nomad assesses **no adverse repercussion** to passenger service, to vehicle systems, or to the delivered V8 baseline, on the following basis:

- Every V9 change is confined to the coupler ports and to spanning-tree parameters. None alters the set of VLANs crossing the coupler, and none touches a port serving a Stadler device.
- In the solo state, the coupler ports carry no link; V9 behaviour is therefore equivalent to V8.
- In the coupled state, each change removes a fault condition or an unintended path. The single trade — slower reconvergence under widened timers — is accepted deliberately, in exchange for convergence that is correct at the coupled network's measured diameter.
- The changes are reversible by re-pushing the prior template.

This assessment is **subject to the coupled-pair runtime re-test**, and to V9's validation as part of Package 1 at FAT and ÖBB bench testing. It is **bounded at 2 × 6-car** and does not extend to 3 × 6-car, which is delivered by V10 (§4.2).

**It is an assessment of a workaround, and should be read as one.** V9 is judged sound at what it sets out to do: make 2 × 6-car coupling stable for service in the interim. It is not the multi-traction design, and no part of this assessment should be read as saying multi-traction is delivered.

### 7.2 Note on the package model

V9 is delivered as part of Package 1 (ND-DEL-OBB-035-RM-001-01), together with switch firmware 7.4.8 and Nomad Connect 2025.3. The assessments above are made **per change**, which is what this document is for. The package is validated **as a combination** at FAT and at ÖBB bench testing, because the combination is what the fleet will run.

Neither substitutes for the other: a per-change assessment cannot establish how components interact, and combination testing cannot explain why an individual change is sound. The bench gate is where the combination is established, and this document will be revised to reflect its outcome.
