# ÖBB DOSTO Neu — Software / Firmware Package Release Plan

**Document details**

| Field | Value |
|---|---|
| Title | ÖBB DOSTO Neu — Software / Firmware Package Release Plan |
| Purpose | Define the software / firmware packages delivered to the fleet, and bind each package to the delivery milestones that gate its release |
| Issued to | ÖBB — Österreichische Bundesbahnen |
| Document Reference | ND-DEL-OBB-035-RM-001-01 |
| BMS Document Reference | BMS-ENGI-FOR-006-02 |
| BMS Version Number | 01 |
| Last updated | 14 July 2026 |
| Approver | *(TBD)* |
| Number of pages | — |
| Related documents | ND-DEL-OBB-035-RN-001-01 (HW & SW Release Note); ND-DEL-OBB-035-SDD-002-01 / -003-01 (System Design Documents); ND-BID-OBB-036 (Technical Description); ND-DEL-OBB-035-CIA-001-01 (Change Impact Analysis); ND-DEVOPS-OBB-TER-026-04 (Nomad Connect Test Exit Report) |

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

This document defines how Nomad software and firmware reach the ÖBB DOSTO Neu fleet.

It replaces a per-component view — in which each switch configuration, firmware image and platform release is rolled out on its own schedule — with a **package** model: a versioned set of components, tested together, released together, and installed on each vehicle in **a single rollout window**.

The purpose is to answer two questions:

1. **What is in each package**, and what is deliberately not.
2. **Which delivery milestones gate that package**, and therefore what must be complete before it may be installed on a vehicle.

**Two packages are planned.** They are different in kind, and the distinction matters more than any detail in this document:

| | **Package 1** | **Package 2** |
|---|---|---|
| Delivers | Switch config **V9**, switch firmware **7.4.8**, Nomad Connect **2025.3** | Switch config **V10** |
| Multi-traction | **Interim workaround** — 2 × 6-car coupled operation | **Full multi-traction**, including 3 × 6-car |
| Gated by | The **current** design freeze (SDD-002 / SDD-003) — near complete | A **second, separate** design freeze for the multi-traction design — not yet started |
| Timing | Ready once its gates pass | Follows Package 1 |

Package 1 can proceed because its design freeze is nearly closed. Package 2 cannot, because the design it implements has not yet been reviewed or frozen. Splitting them is what allows the V9 workaround, switch firmware and platform release to reach the fleet without waiting for the multi-traction design to be settled.

### 1.2 Why a package, and why one window

**All updates are installed remotely.** Software and firmware are pushed from the Nomad CCU over the vehicle's own network — no attendance at the train, no depot booking, no withdrawal from service for the work itself. This applies to every component in Package 1: the switch configuration, the switch firmware and the Nomad Connect platform release.

Because installation is remote, the case for packaging is **not** about saving visits. It is about what reaches the fleet, and in what state:

- **One tested combination.** Components are validated together, so the combination installed on the train is the combination that was tested. Rolling components out independently produces a fleet in which no two vehicles necessarily carry the same combination — and a combination that was never tested as a whole.
- **One approval.** ÖBB approve a package, not a stream of individual changes.
- **A defined fleet baseline.** After the window, every vehicle reached is at a known, identical baseline — which is what makes the fleet supportable and the next change assessable.
- **One scheduling exercise.** Each installation still requires a slot when the vehicle is not carrying passengers (§4.4). Packaging means agreeing one such slot per vehicle rather than one per component.

The cost of this model is that a window is gated by its slowest component: nothing rolls out until everything in that package is ready. §4.3 states how that is managed within a package — and the two-package split (§1.1) is the same principle applied at the larger scale, keeping the settled work from waiting on the unsettled.

### 1.3 Scope

All four DOSTO Neu platform variants: nv4 (4734, 4-car, 25 trainsets), nv6 (4736, 6-car, 20), fv5 (4705, CAT 5-car, 3) and fv6 (4706, FV 6-car, 3) — **51 trainsets**.

---

## 2. How packages bind to delivery milestones

This section defines the mechanism. §3 and §4 apply it.

### 2.1 The two rules

A package is bound to the delivery milestones by two rules.

**Rule 1 — Entry gate.** A package may not be installed on a vehicle until every one of its gate milestones is complete. The gates are cumulative: all must pass, in order.

**Rule 2 — Content freeze.** When the package content is frozen, its contents stop changing. Any component not ready at freeze does not delay the package — it waits for the next window. This is what prevents a single unready component from holding the whole fleet.

Together these mean a package has exactly two states: **not yet released** (a gate is open) or **released** (all gates passed, contents frozen, installing). There is no partial release.

### 2.2 The gate chain

Each package runs the same gate chain. **Each package has its own design freeze** — this is the point on which the two-package structure turns.

```img:diagrams/package_gate_chain_v1.png:6.6
```

*Figure 1 — The two packages and their gate chains. Each package is gated by its own design freeze: Package 1 by the current SDD-002 / SDD-003 freeze (near complete), Package 2 by a separate multi-traction design freeze (not started). This is why the packages are separate.*

Each gate exists for a reason, and the order is not arbitrary:

| Gate | Owner | What it establishes | Why it precedes the next |
|---|---|---|---|
| **Design Freeze** | ÖBB (approval); Nomad (documents) | The agreed design against which the package is built and tested. | Testing against an unfrozen design is not evidence — a later design change invalidates the test result. |
| **FAT** | Nomad | The package works as an integrated whole in Nomad's environment. | Presenting an unvalidated package for customer testing wastes the customer's bench time. |
| **ÖBB Bench Testing** | ÖBB | The customer has validated the package and approves it for their fleet. | This is the approval. Fleet installation without it is a change to the customer's fleet that the customer has not accepted. |
| **Rollout Window** | Nomad + ÖBB (scheduling) | — | — |

### 2.3 What each gate produces

Gates are evidenced by documents, not by assertion:

| Gate | Evidence |
|---|---|
| Design Freeze | SDD-002 and SDD-003 approved by ÖBB |
| Package content freeze | This document, revised to state the frozen contents |
| FAT | Test Exit Report(s) for the package components |
| ÖBB Bench Testing | ÖBB approval of the package |
| Rollout | HW & SW Release Note (ND-DEL-OBB-035-RN-001-01) revised to the new baseline |

### 2.4 Approval of firmware and configuration via the bench gate

**Switch firmware 7.4.8 and switch configuration V9 are approved through the ÖBB bench-testing gate, not before it.** They enter the package as candidates; the bench gate is the mechanism by which they become approved for the fleet.

This is stated explicitly because it is the clearest illustration of how the package model differs from a per-component one. Under a per-component model, each item would need its own approval before rollout. Under this model, the package is tested as a whole and approved as a whole — which is both fewer approvals for ÖBB and a stronger guarantee, because what is approved is the combination that will actually be installed.

Until that gate passes, the fleet target remains the current baseline (§3.1).

---

## 3. Baseline and package contents

### 3.1 Current fleet baseline

As recorded in the HW & SW Release Note (ND-DEL-OBB-035-RN-001-01):

| Component | Current version |
|---|---|
| VDS Rail Consist Switch firmware | 7.4.2 |
| VDS Rail Consist Switch configuration | V8 |
| Westermo RT610LV access point firmware | 6.11.2-0 (IbexOS) |
| Nomad Connect / onboard-network engine (nd-obn) | 2.2.23 |
| CCU platform image (Nomad Connect) | 2025.2.1 |
| Nomad NMS | 2026.1.2 |

**Rollout position:** 25 of 51 trainsets are commissioned to this baseline. The remainder are at various stages, dependent on vehicle availability and on Stadler-side cabling work (§5.2).

### 3.2 Package 1 — contents

| # | Component | From | To | Rationale |
|---|---|---|---|---|
| 1 | VDS switch configuration | V8 | **V9** | **Interim multi-traction workaround** — see §3.2.1. Assessed in ND-DEL-OBB-035-CIA-001-01. |
| 2 | VDS switch firmware | 7.4.2 | **7.4.8** | Approved via the ÖBB bench gate (§2.4). |
| 3 | Nomad Connect platform | 2025.2.1 | **2025.3** | Next validated platform release. |
| 4 | Onboard-network engine (nd-obn) | 2.2.23 | *(per NC 2025.3)* | Delivered as part of the platform release. |

#### 3.2.1 V9 is an interim workaround, not the multi-traction design

**This is the most important statement in this document and should not be read past.**

V9 provides an **interim workaround** enabling **2 × 6-car** coupled operation. It makes coupling at that size stable enough for service by removing the specific fault conditions observed in the field — an asymmetric coupler path cost, untagged traffic crossing between coupled trains, and spanning-tree timers with no margin at the coupled network's diameter.

**V9 is not the final multi-traction design.** Full multi-traction is delivered by **V10**, in Package 2, subject to its own design freeze (§4).

What this means for ÖBB:

- V9 is a **stopgap with a known successor**, not a delivered capability. It should be planned as such.
- V9's envelope is **2 × 6-car**. It does not extend further, and no configuration value can extend it — see §6.
- Package 1 is proposed **because** V9 is a workaround: it lets the switch firmware, platform release and coupling fixes reach the fleet now, rather than waiting for the multi-traction design to be reviewed and frozen.

**Deliberately excluded from Package 1:**

| Component | Status | Reason |
|---|---|---|
| Westermo AP firmware | Remains **6.11.2-0** | No change required. The current version is the fleet target. |
| AP configuration | **Unchanged** | No change required. |
| Switch configuration **V10** — full multi-traction | **Package 2** | Awaiting its own design review and freeze (§4). Not a matter of validation only: the design itself is not yet settled, and requires Stadler and VDS Rail input. |

The exclusions are as much a part of the package definition as the inclusions: they are what the content freeze (§2.1, Rule 2) has decided.

### 3.3 Resulting fleet baseline after Package 1

| Component | Version after rollout |
|---|---|
| VDS Rail Consist Switch firmware | **7.4.8** |
| VDS Rail Consist Switch configuration | **V9** |
| Westermo RT610LV access point firmware | 6.11.2-0 *(unchanged)* |
| Nomad Connect platform | **2025.3** |
| Onboard-network engine (nd-obn) | *(per NC 2025.3)* |

---

## 4. Package 1 — milestones and schedule

### 4.1 Gate status

| # | Gate | Owner | Status | Evidence required |
|---|---|---|---|---|
| 1 | **Design Freeze** (current — SDD-002 / SDD-003) | ÖBB | **Near complete.** SDD-003 review closed — all answerable ÖBB comments addressed. SDD-002 freeze-ready. Awaiting ÖBB approval of the final Technical Description. *(This is Package 1's design freeze. Package 2 has its own — see §6.)* | SDD-002 / SDD-003 approved |
| 2 | **Package content freeze** | Nomad | **Proposed** — this document, §3.2 | This document, approved |
| 3 | **FAT** | Nomad | **Not started** — gated on 1 | Test Exit Report(s) |
| 4 | **ÖBB Bench Testing** | ÖBB | **Not started** — gated on 3 | ÖBB approval of the package |
| 5 | **Rollout window opens** | Nomad + ÖBB | **Not started** — gated on 4 | — |

**Critical path: Gate 1 → 3 → 4 → 5.** Design freeze is the long pole, and it is close. Everything downstream waits on ÖBB approval of the frozen design.

### 4.2 Indicative schedule

> **Dates to be confirmed.** The targets below are placeholders pending agreement with ÖBB and DevOps. The **gate logic is fixed**; the dates are not, and each is conditional on the preceding gate.

| Milestone | Owner | Target | Depends on |
|---|---|---|---|
| Design freeze — ÖBB approval | ÖBB | *(TBD)* | SDD-002 / SDD-003 (Nomad side complete) |
| Package content freeze | Nomad | *(TBD)* | Design freeze |
| NC 2025.3 Test Exit Report | Nomad DevOps | *(TBD)* | Package content freeze |
| FAT — package validated | Nomad | *(TBD)* | TER; design freeze |
| ÖBB bench testing | ÖBB | *(TBD)* | FAT |
| ÖBB package approval | ÖBB | *(TBD)* | ÖBB bench testing |
| **Rollout window opens** | Nomad + ÖBB | *(TBD)* | ÖBB package approval |
| Rollout window closes | Nomad + ÖBB | *(TBD)* | Vehicle availability |

### 4.3 Managing the window's dependency on its slowest component

The package model's cost (§1.2) is that the window waits for its slowest component. This is managed by the content freeze:

- At content freeze, any component not ready is **removed from the package** rather than allowed to delay it.
- A removed component becomes a candidate for the next window.
- The freeze decision is a Nomad recommendation, confirmed with ÖBB.

The practical consequence for Package 1: if NC 2025.3 is not ready to enter FAT at content freeze, the package proceeds as switch config V9 + switch firmware 7.4.8, and NC 2025.3 moves to a second window. The reverse also applies.

### 4.4 The rollout window itself

The rollout window is a **scheduling window, not a visit window.** Each vehicle receives the full package remotely, in one installation:

- **Installed remotely** from the CCU. No attendance at the vehicle.
- **Installed when the vehicle is not carrying passengers.** This is what protects passenger service, and it is the one operational condition the package depends on. There is **no fixed maintenance window** — availability is established per vehicle, see §4.5.
- All package components are installed in **one sequence**, in a defined order so that a device restart does not isolate devices behind it.
- The vehicle is **verified against the Package 1 baseline** (§3.3) after installation.
- The vehicle's state is **recorded**, so an installation interrupted by loss of connectivity resumes from a known point rather than restarting.

Vehicles are taken into the window as they become available — either on notification from Stadler / ÖBB, or when telemetry shows the vehicle parked and reachable (§4.5). The window closes when all reachable vehicles carry the package.

### 4.5 The one operational condition

Applying a switch configuration or firmware image **restarts the switch** — this is how the change is persisted, and it is unavoidable. While a switch restarts, the passenger Wi-Fi it serves is briefly unavailable.

Remote installation does not remove this. It changes only *how* the work is delivered, not *what happens on the train* when it lands. The protection is therefore **timing**:

> Package installations are performed when the vehicle is not in passenger service — never during revenue operation.

This is stated plainly because it is a **condition, not a property**. The package is safe for passenger service because of when it is installed, not because of anything intrinsic to the changes. If a vehicle were updated in service, passengers would see Wi-Fi interruptions as each switch restarted. This condition is what makes the assessment in ND-DEL-OBB-035-CIA-001-01 hold.

#### How availability is established

**There is no fixed maintenance window on this project.** Vehicle availability is established per vehicle, from either of two sources:

| Source | How it works |
|---|---|
| **Notification** | Stadler or ÖBB advise Nomad that a vehicle is available for work. |
| **Telemetry** | Nomad confirms from the CCU that the vehicle is parked and not in service before initiating the installation. |

The two are complementary rather than alternatives: a notification tells Nomad a vehicle *should* be available; telemetry confirms it *is*, at the moment of installation. Where both are present, telemetry is the check that immediately precedes the push.

**This makes vehicle availability a shared dependency, not solely a Nomad one.** Nomad cannot create availability; it can only use it when it arises or is advised. Rollout pace therefore follows vehicle availability, which is why §4.2 offers no fixed rollout duration.

**Connectivity dependency.** Because installation is remote, it depends on the vehicle being reachable over its cellular link for the duration. Vehicles that are powered down or out of coverage are not reached and are picked up on a later occasion — an unreachable vehicle is a deferral, not a failure. In practice a proportion of the fleet is unreachable at any given time, and the rollout is planned on that basis.

---

## 5. Dependencies outside the package

### 5.1 ÖBB

- Approval of the final Technical Description (design freeze) — **gate 1, critical path**.
- Bench testing and package approval — **gate 4**.
- **Notification of vehicle availability** for installation, where known in advance (§4.5). There is no fixed maintenance window, so each installation depends on a vehicle being out of passenger service and reachable. Nomad also confirms this from CCU telemetry, but advance notice from ÖBB or Stadler materially improves rollout pace.

### 5.2 Stadler

Stadler-side activities, outside Nomad's scope, which do not gate the package but affect per-vehicle completion:

- **Open cabling faults.** Physical cabling and port-assignment faults identified during Nomad health checks require Stadler action. Tracked and reported separately. A vehicle with an open cabling fault can still receive the package; the fault remains open.
- **Firewall commissioning** on the transit link, incomplete on some trainsets. Does not affect the Nomad onboard-network baseline.

**Scope boundary:** Nomad provides the configuration of the switch ports serving Stadler devices. The testing of those devices is Stadler's responsibility.

---

## 6. Package 2 — V10, full multi-traction

### 6.1 What Package 2 delivers

Package 2 delivers switch configuration **V10**: **full multi-traction support, including 3 × 6-car**. It replaces the V9 interim workaround with the designed solution.

ÖBB have confirmed in principle the intent to couple up to **3 × 6-car** in service. V9 does not support this and cannot be extended to support it — the reason is a hard protocol limit, set out below.

### 6.2 Why V10 requires its own design freeze

Three coupled 6-car trainsets total **54 switches**. This **exceeds the 40-node spanning-tree protocol limit**. It is a node-count limit in the protocol itself: no firmware version, no configuration value and no timer setting can raise it. This is why 3 × 6-car cannot be reached by extending V9 — the limit is not a tuning parameter.

Supporting 3 × 6-car requires **terminating Layer 2 at the consist boundary and routing between consists**, so that each train's network remains its own bounded domain irrespective of how many trains couple. Each train then stays well inside the node limit, however long the formation.

That is an **architecture change, not a configuration change**, and it is why V10 carries a design review and freeze of its own rather than riding the current one:

| Input required | From | For |
|---|---|---|
| Operational requirement and timeline for 3 × 6-car | **ÖBB** | Confirming the target formation length *(confirmed in principle 20 June 2026; timeline to be defined)* |
| Firewall behaviour across coupled consists; ownership of the inter-consist Layer-3 boundary | **Stadler** | The routed boundary is expected to sit at the Stadler firewalls, which already relay inter-consist traffic |
| Routed-mode behaviour confirmation on the relevant firmware build | **VDS Rail** | The fallback path, if the firewall boundary is not adopted |

Multicast handling (IGMP snooping and querier behaviour across a coupled composition) is resolved within this design rather than as a standalone change, since its correct behaviour depends on where the inter-consist boundary sits.

### 6.3 Package 2 gate status

| # | Gate | Owner | Status |
|---|---|---|---|
| 1 | **Multi-traction design review** | Nomad + Stadler + VDS Rail | **Not started** — inputs above outstanding |
| 2 | **Multi-traction design freeze** | ÖBB | **Not started** — gated on 1 |
| 3 | Package 2 content freeze | Nomad | Not started |
| 4 | FAT | Nomad | Not started |
| 5 | ÖBB bench testing | ÖBB | Not started |
| 6 | **Rollout window 2** | Nomad + ÖBB | Not started |

**Package 2 is not scheduled.** Its critical path starts with the design review, which needs Stadler and VDS Rail input. No target dates are offered until the design is frozen — a schedule set before the design is settled would not be meaningful.

### 6.4 Relationship between the packages

- Package 1 is **not a prerequisite** for the Package 2 design work, which can proceed in parallel.
- Package 1 **is** expected to precede Package 2 on the vehicles: the fleet reaches the V9 baseline first, then V10 in a second window.
- If the multi-traction design freeze completes unexpectedly early, the packages could in principle merge. This is **not** the plan of record: it would make the whole delivery wait on the slowest, least-settled component, which is exactly what the two-package split exists to avoid.

---

## 7. Summary

- Nomad proposes to deliver software and firmware to the DOSTO Neu fleet as **packages, each installed in a single rollout window per vehicle**, rather than as independently scheduled component updates. One tested combination, one approval, one known baseline per window.
- **All updates are installed remotely** from the CCU — no attendance at the vehicle. The rollout window is a scheduling window, not a visit window. Installation is performed **when the vehicle is not in passenger service**: switch restarts are unavoidable, so timing is what protects passenger service. **There is no fixed maintenance window** — availability is established per vehicle, either on notification from Stadler / ÖBB or confirmed from CCU telemetry (§4.5).
- **Two packages are planned**, distinguished by which design freeze gates them:

| | Package 1 | Package 2 |
|---|---|---|
| **Contents** | Switch config **V9**, switch firmware **7.4.8**, Nomad Connect **2025.3** | Switch config **V10** |
| **Multi-traction** | **Interim workaround** — 2 × 6-car | **Full multi-traction**, incl. 3 × 6-car |
| **Design freeze** | Current (SDD-002 / -003) — **near complete** | Multi-traction design — **not started** |
| **Schedule** | Indicative dates, §4.2 | **Not scheduled** — gated on the design review |

- **V9 is an interim workaround, not the multi-traction design** (§3.2.1). It makes 2 × 6-car coupling stable enough for service. Full multi-traction is V10.
- **3 × 6-car cannot be reached by extending V9.** 54 switches exceeds the 40-node spanning-tree limit — a protocol limit no configuration value can raise. It requires the routed inter-consist design delivered by V10, which needs Stadler and VDS Rail input and a design freeze of its own (§6).
- Each package is gated by: **design freeze → FAT → ÖBB bench testing → rollout window**. Switch firmware **7.4.8** and configuration **V9** are **approved via the ÖBB bench gate**, not before it.
- **Package 1's critical path is the current design freeze**, close to complete on the Nomad side, awaiting ÖBB approval of the final Technical Description.
- **Dates are to be confirmed.** The gate logic is fixed; the §4.2 schedule is indicative and each date is conditional on the preceding gate. No dates are offered for Package 2 until its design is frozen.
