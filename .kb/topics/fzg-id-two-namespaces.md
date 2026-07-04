---
type: topic
title: Fzg-ID vs Nomad-internal train_id — Two Namespaces in One Field
description: Why OBN's train_id carries two conflicting values (the Nomad-internal box ID that builds CCU/OSPF IPs, and the ÖBB Fzg number that builds switch hostnames), the cascade the conflation caused, and the box=Fzg resolution.
project: dosto-neu
tags: [fzg-id, train-id, obn, templates, hostnames, ntp, commissioning, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

In the OBN configuration engine, the field `train_id` is overloaded: it is asked to be **two
semantically different numbers at once**, and the two are not equal for most trains. Every
recurring Fzg-ID bug on this project traces back to that overload.

- **Nomad-internal ID** (the box number, e.g. `28` on `box1-t28`) — builds the **CCU's own IPs**:
  management, OSPF, DHCP scope. Lives in `/etc/obn/backbone-discovery.yaml`.
- **ÖBB Fzg ID** (the customer vehicle number, e.g. `137`) — builds **switch hostnames**, the
  switch-port DHCP math, and (historically) the NTP source and vlan7 IP.

These are different values on almost every train, because the deployed box number drifts from the
planned one (imaging / reassignment). Treating them as one field is what breaks things.

> **Portability note.** The two-namespace problem, the shadowing mechanism, and the
> location-discipline rule are generic to the OBN/Jinja config engine. Series formulas, subnet
> literals, and the "v9 / box=Fzg" decision in the `EXAMPLE` block are DOSTO-NEU-specific.

# Why the two values were ever related (the original, sound design)

The allocation sheet defines a **consistent per-series offset** between the planned Nomad box
number (NC-ID) and the ÖBB Fzg: 4-car series at offset 0, 6-car series at offset +128. So the
templates deriving Fzg *from* the box number by that offset (`train_id → 128 + train_id`, and
`fis_id + train_id` in the network template) was a deliberate, defensible design — it avoided
storing Fzg redundantly.

**It assumed box = planned-NC-ID = Fzg − offset.** That assumption held on paper and broke in the
field: real CCUs got arbitrary box numbers from imaging, not the planned NC-ID. Once box ≠
planned-NC-ID, the offset formula renders the **wrong** Fzg — which forced a per-train hand-hardcode,
which `obn update c` then wipes. The disease was field box-drift, not a bad design.

# How the conflation renders wrong

Inside a switch `.cfg` template, a line-1 Jinja directive `{%- set train_id = <Fzg> -%}`
**template-scope-shadows** the engine-injected internal `train_id` for that file only. That is how
a hand-hardcoded Fzg reaches the hostname while the engine still uses the internal ID for CCU IPs.
Two failure modes follow:

1. **Wrong CCU subnet on reboot.** If you instead set the Fzg in `backbone-discovery.yaml`
   (thinking "train_id should be the Fzg"), the engine builds the CCU's own IPs from it and the
   CCU **moves to a different management subnet on reboot** — the classic disconnect. `train_id`
   in `backbone-discovery.yaml` must remain the **internal** value.
2. **Dead NTP source.** A template line written for the `128 + train_id` remap era recovers the
   internal ID with `train_id − 128`. Once a raw Fzg is hardcoded, `Fzg − 128` renders a bogus,
   unreachable NTP IP — leaving every switch with no working time source, fleet-wide, silently.

# The location-discipline rule

Until the namespaces are cleanly separated, the operational rule is:

> **The Fzg ID may appear ONLY inside `/etc/obn/template/<fleet>-*.cfg` (the per-switch config
> templates). Never in `backbone-discovery.yaml` or any other file.** Those `.cfg` files are the
> single source of truth for the Fzg rendered into switch hostnames.

# The durable resolutions

Two paths were designed; the second was chosen.

- **`fzg_id` namespace split** — add a *separate* Puppet-owned `fzg_id` key (not a `train_id`
  override); templates reference `fzg_id` for hostnames + device DHCP; `train_id` means "internal"
  everywhere. Requires one generic engine line to copy `fzg_id` from merged config into the render
  target (the Jinja sandbox can only see engine-injected keys — a per-fleet static `rules.yaml`
  cannot carry a per-train value, so "no engine change" structurally cannot supply a per-train
  Fzg).
- **box = Fzg (chosen, 2026-06-30)** — renumber each CCU's box ID to equal its Fzg. Then
  `train_id` *is* the Fzg by identity (cannot drift), which **eliminates** the `fzg_id` key, the
  engine change, and the Puppet node lines entirely — one uniform model. Cost: a net-new re-IP of
  in-service 6-car trains. This restores the original designer's intent (box and Fzg
  deterministically related) by identity rather than by a driftable offset.

# Proven dead ends — do NOT repeat these

> Kept so a fresh agent does not re-trigger the Fzg-133-class cascade.

1. **Setting the Fzg in `backbone-discovery.yaml` `train_id:`.** The engine builds the CCU's own
   management/OSPF/DHCP IPs from that field. Overriding it to the Fzg **moves the CCU to a
   different subnet on reboot** and disconnects it. `train_id` there must stay the internal box ID.
2. **Hardcoding the Fzg and trusting `Fzg − 128` NTP lines.** The NTP-source template line was
   written to recover the *internal* ID via `train_id − 128`. A raw-Fzg hardcode makes it render a
   dead IP (e.g. `10.179.9.1`), silently killing switch time sync. Keep NTP keyed to the internal
   value.
3. **`box = Fzg` for any fleet whose Fzg > 127.** The `factory up` train-ID caps at 0-127 (it is
   the 3rd IP octet). The 6-car / CAT / FV series have Fzg 129-231, which exceed it — box=Fzg only
   fits the 4-car series (Fzg 1-90). Do not `obn update c` a >127 train commissioned with box=Fzg
   assumptions without the re-IP in place; the v9 remap-drop renders wrong hostnames otherwise.
4. **Trusting a series→Fzg formula at runtime.** Formulas are reference only. Misimaged CCUs,
   stale Puppet images, and hand-set wrong values mean the *rendered* Fzg on a live CCU is often
   wrong pre-commissioning — that is what commissioning fixes. Resolve the Fzg from the
   authoritative per-train record (fleet-status / allocation sheet / physical inspection), and
   halt if it is unknown rather than computing it.
5. **Trusting the allocation sheet's NC-ID column as the live box number.** NC-ID is the *planned*
   box; the deployed box differs (that drift is the whole problem). The sheet confirms Fzg only;
   the live box comes from the live CCU.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Series → Fzg (reference only, never trusted at runtime):
  `4734-NNN → NNN-100`; `4736-NNN → NNN+28`; `4705-NNN → NNN+128`; `4706-NNN → NNN+88`.
- Live example: 4736-109 runs on `box1-t28` (internal 28), Fzg 137, project_id 51,
  vlan100 `10.179.28.129`. `128 + 28 = 156 ≠ 137` — the offset formula renders wrong here.
- Dead NTP fault (verified box1-t28, 2026-06-30): template `10.{{project_id+128}}.{{train_id-128}}.1`
  under a Fzg hardcode renders `10.179.9.1` (unreachable) instead of `10.179.28.1` (the CCU).
- box=Fzg target mapping: 4734 → `10.178.<Fzg>` (Fzg 1-90, via the ID-50→10.178 migration);
  6-car → `10.179.<Fzg>` (Fzg 129-231). Verified collision-free fleet-wide.
- Authoritative Fzg source: `design freeze/Fzg-Nr-ID Aufteilung-v1.xlsx`, "Mar5 - Server
  Allocation" sheet — **upper** of two stacked tables (a naive parse keeps the wrong lower table).

# Related

- [vlan7 bit-packed addressing](/.kb/topics/vlan7-addressing.md) — same class of `train_id`-vs-Fzg break in the vlan7 formula
- [Coupled-train RSTP TC-storm](/.kb/topics/coupled-rstp-tc-storm.md) — the coupler-cost bug is a `train_id`-derived-value misuse
- [Zabbix / NMS monitoring model](/.kb/topics/zabbix-nms-model.md) — Zabbix host names key off the box ID, so box=Fzg renames every host
- [Nomad Connect / OBN — bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] Session memory `project_obn_train_id_two_namespaces` — the two values, their sources, the Jinja line-1 shadow (OBN source verified 2026-06-30).
[2] Session memory `project_why_davud_split_train_id_fzg` — the per-series offset origin and field box-drift.
[3] Session memory `project_switch_ntp_source_broken_by_fzg_hardcode` — dead `10.179.9.1` NTP source (box1-t28, 2026-06-30).
[4] Session memory `project_fzg_id_render_transport_constraint` — Jinja sandbox / rules.yaml cannot carry per-train Fzg.
[5] Session memory `project_box_equals_fzg_strategy_split` — the box=Fzg decision (2026-06-30).
[6] Session memory `project_box_fzg_breaks_127_octet_limit` — the >127 octet ceiling.
[7] Session memories `reference_series_formulas`, `reference_fzg_id_aufteilung_crosscheck` — series formulas and the authoritative sheet + parser trap.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/topics/vlan7-addressing|vlan7-addressing]]
- [[.kb/topics/coupled-rstp-tc-storm|coupled-rstp-tc-storm]]
- [[.kb/topics/zabbix-nms-model|zabbix-nms-model]]
- [[.kb/components/nomad-connect-obn/bug-suite|bug-suite]]
- [[.kb/fleet/index|index]]
