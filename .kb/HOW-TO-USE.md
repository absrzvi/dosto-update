---
type: guide
title: How to use this knowledge base
description: Orientation for an AI agent (or engineer) picking up the DOSTO NEU knowledge base — what's here, how it's organised, and how to navigate it.
project: dosto-neu
tags: [meta, onboarding, navigation]
timestamp: 2026-07-04T00:00:00Z
---

# What this is

This is a knowledge base for the **DOSTO NEU** onboard-network commissioning project (Stadler
double-deck trainsets with VDS Rail consist switches, Westermo APs, and a Nomad Connect CCU/OBN
stack). It exists so an agent can **learn the system and troubleshoot it without repeating work
that has already been done** — especially the approaches that were tried and *proven not to work*.

It follows the **Open Knowledge Format (OKF) v0.1**: a directory of markdown files, each with a
small YAML frontmatter block. No tooling required — read the `.md` files directly.

# How to read it

Start at [index.md](/.kb/index.md), then drill into the category you need:

- **`components/`** — how each device *type* behaves (switch, AP, CCU/OBN). Written generically
  so the core is reusable; DOSTO-specific values sit in clearly-marked `EXAMPLE (DOSTO NEU)`
  blocks. **Read these first when troubleshooting a device.**
- **`topics/`** — cross-cutting subjects that span devices (vlan7 addressing, coupled-train RSTP,
  Zabbix/NMS monitoring, the Fzg-ID two-namespace problem, L2 health methodology).
- **`fleet/`** — one record per commissioned train: its Fzg ID, CCU IP, quirks, and links to its
  own config files, allocation PDFs, reports, and tickets.
- **`deliverables/`** — pointers to the SDD/BID documents, control sheets, and customer reports
  (the real files are `.docx`/`.xlsx`; each has a summary stub here).
- **`tickets/`** — R&D / TRIAG / OEBB tickets with their status and linked evidence.
- **`assets/`** — one index per train for the raw allocation PDFs and switch `.cfg` files.

# The two conventions that make this worth reading

1. **⛔ Proven dead ends.** Every component and topic doc has a section listing what has been
   *tried and disproven on live hardware*. Before you attempt a fix, check it — e.g. the switch
   CLI has no working `reboot` command, and remote syslog silently transmits nothing. This is the
   payload: **don't re-test what already failed.**
2. **`resource:` links.** Facts that come from a specific file (a PDF, a `.docx`, a switch `.cfg`,
   a script) carry a `resource:` link in frontmatter or inline, so you are one hop from the source
   evidence.

# What to trust

- `maturity: field-validated` — observed on live hardware; a `# Citations` block names the session.
- `maturity: reported` — believed true from docs/tickets but not personally re-verified.
- `maturity: draft` — provisional.

Per OKF, treat broken links and missing optional fields as tolerable — this KB grows incrementally.

# Related

- [Root index](/.kb/index.md)
- Source project playbook (full methodology, live-state): [CLAUDE.md](/CLAUDE.md)
- Live per-train state (positionally-parsed, do not edit from here): [fleet-status.md](/fleet-status.md)
