# Jira ticket — request DevOps TER for NC 2025.3 (DOSTO Neu)

**Not yet raised.** Paste into Jira when ready.

- **Project:** NCD (NC DevOps)
- **Issue type:** Task
- **Reporter:** Abbas Rizvi
- **Assignee:** *(DevOps to assign — Szymon Dutkiewicz / Piotr Romanowski authored TER-026-04)*
- **Priority:** *(TBD)*

---

## Summary

```
DOSTO Neu (DEL-OBB-035) — Test Exit Report for Nomad Connect 2025.3
```

---

## Description

```
Requesting a Test Exit Report for Nomad Connect 2025.3 on the DOSTO Neu bench, to
support the ÖBB release documentation pack.

Background
----------
The delivered DOSTO Neu baseline is NC 2025.2.1, evidenced by TER ND-DEVOPS-OBB-TER-026-04
(16 April 2026, Newcastle T112 bench). ÖBB have requested the release documentation pack for
NC 2025.3, which needs a TER as its test evidence. There is currently no 2025.3 test evidence
for this project.

The release note (ND-DEL-OBB-035-RN-001-01) and roadmap (ND-DEL-OBB-035-RM-001-01) reference
the TER as the validation record for any Nomad Connect release before fleet rollout, so the
pack cannot be completed for 2025.3 without it.

Ask
---
1. Confirm whether a 2025.3 TER for DEL-OBB-035 already exists or is planned. If it exists,
   please point us at it — the rest of this ticket falls away.
2. If not, schedule the bench test run and produce the TER, following TER-026-04 as the
   structural baseline.
3. Confirm the expected date, so the ÖBB documentation pack and the fleet-rollout gate can
   be planned around it.

Scope
-----
TER-026-04 §2.2 lists the items tested for 2025.2.1. As a starting point for scoping, the
DOSTO-specific areas most likely to need re-running:

- OBN functionality — automatic discovery, config update, validation
- Switch and AP functionality, incl. AP accessibility
- System boot and firmware validation
- Tunnel connectivity
- System update functionality
- On-board monitoring / Zabbix / NMS reporting
- Passenger connectivity flow, DHCP, DNS

DevOps to confirm the final scope — the above is a prompt, not a specification.

Known limitations carried over from TER-026-04 (§2.4), worth confirming whether they still
apply:

- Bench is a 4-car consist only; six-car configuration could not be fully validated.
- SIM provisioning limitations — recommended to be covered by in-country testing.

Scope boundary to state in the TER
----------------------------------
Please include a statement of the Nomad/Stadler responsibility boundary, to this effect:

  Nomad provides the configuration of the switch ports for Stadler devices; the testing of
  those devices is Stadler's responsibility.

This is needed because ÖBB have asked for a freedom-from-interference / absence-of-interaction
position, and this boundary statement is where we address it. The Nomad boundary ends at the
switch-port configuration and the vlan7 transit link; Stadler perform inter-VLAN routing and own
the device VLANs (cameras, displays, AFZ, intercom, OBS, RDC, energy meter). The CCU has no
visibility of those VLANs.

Reference
---------
- ND-DEVOPS-OBB-TER-026-04 — NC 2025.2.1 TER (structural baseline for this request)
- ND-DEL-OBB-035-RN-001-01 — HW & SW Release Note (delivered baseline)
- ND-DEL-OBB-035-RM-001-01 — Delivery and Release Roadmap (release gates)
```

---

## Notes before raising (not part of the ticket body)

- **Confirm 2025.3 is real and is what ÖBB want.** This whole request assumes NC 2025.3 exists as a
  release and is the intended next baseline for DOSTO. Nothing in the project workspace references
  2025.3 — every reference is to 2025.2.1. Worth a sanity check with DevOps/ÖBB before raising,
  since the ticket looks foolish if the version is wrong.
- **Assignee.** Szymon Dutkiewicz and Piotr Romanowski authored TER-026-04; Ben Turner approved it.
  Derek Abdinor approved revisions 2–3. Any of these is a reasonable first point of contact, but
  let DevOps assign.
- **NCD-516 is not a precedent.** The Q2 phase plan lists "TestBench - NC v 2025.2.1 TER | DevOps |
  ABGESCHLOSSEN | NCD-516", but NCD-516 is actually a SIM slot 0 issue, marked "Won't do". The phase
  plan reference is wrong — don't cite it in the ticket.
- **Priority / due date** left blank — set per the ÖBB pack deadline.
