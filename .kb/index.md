---
okf_version: "0.1"
project: dosto-neu
title: DOSTO NEU Knowledge Base
description: Component-oriented knowledge base for the DOSTO NEU onboard-network project — device behaviour, cross-cutting topics, per-train records, deliverables, tickets, and proven dead ends.
---

# DOSTO NEU Knowledge Base

New here? Read [HOW-TO-USE.md](HOW-TO-USE.md) first. Maintaining the KB? See [MAINTENANCE.md](MAINTENANCE.md).

## Components — how each device type behaves

* [VDS Consist Switch — CLI & management](components/vds-consist-switch/cli-and-management.md) - CLI quirks, SNMP, reboot, traps, syslog, and proven dead ends.
* [VDS Consist Switch — L2 counters & RSTP](components/vds-consist-switch/l2-counters-rstp.md) - error-counter interpretation, STP roles/states.
* [VDS Consist Switch — firmware flashing](components/vds-consist-switch/firmware-flashing.md) - TFTP + SNMP boot-default OID, the regex/None-guard traps.
* [Westermo AP — factory vs Nomad config](components/westermo-ap/factory-vs-nomad-config.md) - SNMP-community trap, LuCI HTTP push bypass.
* [Westermo AP — firmware activation](components/westermo-ap/firmware-activation.md) - stage-vs-activate flakiness, partial-flash.
* [Nomad Connect / OBN — bug suite](components/nomad-connect-obn/bug-suite.md) - the 11 crash/silent-fail fixes.
* [Nomad Connect / OBN — discover→report→update](components/nomad-connect-obn/discover-report-update.md) - never skip `obn report`.
* [Nomad Connect / OBN — NDSU chroot persistence](components/nomad-connect-obn/ndsu-chroot-persistence.md) - btrfs snapshot, `.dont` rename, heredoc-not-paste.
* [Nomad Connect / OBN — TFTP conntrack helper gap](components/nomad-connect-obn/tftp-conntrack-helper.md) - silent AP-firmware batch failure.
* [Nomad Connect / OBN — publish→Puppet pipeline](components/nomad-connect-obn/publish-to-puppet-pipeline.md) - 7-step deploy, no auto-sync.

## Topics — cross-cutting subjects

* [Topics index](topics/index.md) - cross-cutting subjects, one entry per topic below.
* [vlan7 bit-packed addressing](topics/vlan7-addressing.md) - per-train FW IP scheme; ICMP = commission signal.
* [L2 health methodology](topics/l2-health-methodology.md) - the 7-phase sweep; leases-not-ARP, 3-question FW probe.
* [Coupled-train RSTP TC-storm](topics/coupled-rstp-tc-storm.md) - asymmetric coupler cost; ~40-node RSTP ceiling.
* [Fzg-ID two-namespace problem](topics/fzg-id-two-namespaces.md) - internal box-id vs ÖBB Fzg; box=Fzg resolution.
* [Zabbix / NMS monitoring model](topics/zabbix-nms-model.md) - inverted cred model, host naming, failure catalogue.

## Evidence — what's proven, with the raw artifact

* [Evidence index](evidence/index.md) - captured proof behind the findings (crash repros, coupled-RSTP storm, OBN bugs).

## Tools — instruments built for this project

* [Tools index](tools/index.md) - diagnostic + reporting instruments (SNMP boot-window poller, Zabbix checkers, port xref).

## Fleet — per-train records

* [Fleet index](fleet/index.md) - 51 per-train identity records (name, Fzg, box-id, CCU IP, Zabbix host, vlan7, topology).

## Deliverables, tickets, assets

* [Deliverables index](deliverables/index.md) - SDD/BID, fleet control sheet, phase plan, project status, MAR5 tunnel.
* [Tickets index](tickets/index.md) - TRIAG-8585, OEBB-251, SA-2444, RD-12434.
* [Asset index](assets/index.md) - per-train allocation PDFs + switch cfgs (46 trains).

## Sources — the raw corpus, categorised & linked

* [Sources index](sources/index.md) - every raw finding/report/email/plan/handoff (82 docs) as a categorised node linked to the trains + knowledge it concerns. Raw files stay in place; nodes link via `resource:`.

## Method (portable — reusable on any project)

* [The Evidence-First Method](method/index.md) - the methodology + an empty `_TEMPLATE/` to copy into a new repo.

## Provenance

Built from the DOSTO troubleshooting workspace: `CLAUDE.md`, `troubleshooting-runbook.md`,
`findings/`, `rd-handoff/`, `reports/`, the session `memory/` store, and the non-markdown asset
corpus (211 PDFs, 74 switch cfgs, 67 docx, 47 xlsx, 93 scripts).
