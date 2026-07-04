---
type: deliverable-ref
title: ND-SDD-MAR5 — Tunnel Architecture (template)
description: SDD template describing the MAR5 train-to-ground tunnel between each vehicle CCU (Nomad Connect) and the Vaneza backend Home Agents.
resource: /ND-SDD-MAR5-Tunnel-Architecture-template.docx
project: dosto-neu
tags: [deliverable, sdd, mar5, tunnel, connectivity, backend]
timestamp: 2026-07-04T00:00:00Z
---

# ND-SDD-MAR5 — Tunnel Architecture (template)

Pointer stub. The document is at
[`ND-SDD-MAR5-Tunnel-Architecture-template.docx`](/ND-SDD-MAR5-Tunnel-Architecture-template.docx).

## What it is

A System Design Description **template** for **MAR5**, the train-to-ground tunnel protocol used by
Nomad Connect. It describes the architecture and technical parameters of the tunnel between each
vehicle-side CCU and the Vaneza backend. Each train has one R5001C CCU (NIMD 1138) running Nomad
Connect, which establishes the MAR5 tunnel to the ground. This tunnel is independent of the other
tunnel layers in the Vaneza on-board system (e.g. the Televic tunnel).

## Section map

- **Nomad Connect — Train-to-Ground Connectivity** (top)
  - Overview — one CCU per train, MAR5 tunnel, independence from other tunnels
  - Tunnel Protocol: MAR5
  - Security
  - Vaneza Backend Endpoints (Home Agents)

## Why it matters here

MAR5 is the deploy-environment branch name for the whole DOSTO Puppet estate
(`dostoneu_migration_mar5`) and the axis of the ID-migration work — so this SDD is the
architectural reference behind several active threads:

- **Backend HA / failover:** a CCU's backend is assigned via a PRIMARY + BACKUP pair
  (`tunnel_remote_host` + `_backup`, auto-switch), or via DCM DNS — not a single IP
  (77.237.62.x range). See the MAR5 HA-failover project note.
- **ID migration (SA-2444):** the `migration_mar5` ID-50 → 10.178 move gates execution of the v9
  work — see [SA-2444](/.kb/tickets/SA-2444-mar5-id-migration.md).
- **Deploy pipeline:** all DOSTO trains deploy from the `migration_mar5` Puppet branch — see
  [publish→Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md).

## Note

This is a **template** (`-template.docx`), not a per-train signed deliverable — treat section
values as placeholders to be filled per deployment, not as committed facts.

# Related

- [SA-2444 — MAR5 ID migration](/.kb/tickets/SA-2444-mar5-id-migration.md)
- [publish→Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)
- [Fzg-ID two-namespaces](/.kb/topics/fzg-id-two-namespaces.md)
- [SDD v2.2 (the main customer SDD)](/.kb/deliverables/sdd-v2.2.md)
- [Deliverables index](/.kb/deliverables/index.md)

# Citations

[1] `ND-SDD-MAR5-Tunnel-Architecture-template.docx` — headings + overview text (2026-05-20).
[2] Memory `project_mar5_ha_backend_failover` — PRIMARY+BACKUP backend assignment, 77.237.62.x.
