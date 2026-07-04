# `train_id` use audit — all 4 fleets (for the fzg_id split)

**Date:** 2026-06-30 · **Author:** AR + Claude · **Method:** every `train_id` occurrence across nv6/nv4/fv5/fv6 templates, normalized to distinct patterns, classified Fzg-vs-internal against **live box1-t28** ground truth (internal=28, Fzg=137, project_id=51, CCU mgmt=10.179.28.1).
**Status:** AUDIT — feeds the combined v9 + fzg_id MR. **Surfaced a live latent bug (NTP source) — see §Finding.**

---

## ⚠️ Finding: the NTP source line is currently BROKEN fleet-wide (hand-hardcode regression)

`nv6-*.cfg:299` (and all fleets): `ntp client source address 10.{{ project_id + 128 }}.{{ train_id - 128 }}.1`

This formula was written for the **`128 + train_id` remap era**, when the rendered `train_id` was `156` (=128+internal-28) and `train_id - 128` recovered the internal-28 → `10.179.28.1` (the CCU mgmt IP / NTP source, per the IoB NTP spec: switches → train CCU).

The **Fzg hand-hardcode (`{%- set train_id = 137 -%}`) silently broke this**: it now renders `10.179.{{137-128}}.1` = **`10.179.9.1`**, which is **UNREACHABLE** (verified by ping from box1-t28). So switches currently have a dead NTP source. This is a real fault, independent of v9, that the fzg_id split will *fix* as a side effect (because the internal value gets its own clean source).

> This is the smoking gun for *why* the two namespaces must be split: a single `train_id` that's been overloaded to mean Fzg has already corrupted an internal-id-derived formula. Classifying every use is not optional hygiene — at least one is actively wrong in production.

---

## Classification rule (from box1-t28)

- **Fzg** (→ rename to `fzg_id`): the value the hand-hardcode sets (137). Used by anything that must match the **ÖBB switch identity / device-VLAN DHCP plan** that today renders off the line-1 shadow. On box1-t28 these render off 137 and that's *intended* (switch hostnames are `nv6-A1-v8-137`, and the device-DHCP scopes are part of the Stadler IP plan keyed to Fzg).
- **Internal** (→ keep `train_id`, = backbone-discovery value 28): anything that must resolve to the **CCU's own mgmt subnet `10.179.28.x`** or otherwise address the Nomad infrastructure.

The decider for each pattern: *does the correct rendered value on box1-t28 come out right with 137 (Fzg) or with 28 (internal)?*

---

## Per-pattern classification

| # | Pattern | Count | Renders on box1-t28 with line-1=137 | Correct? | Verdict |
|---|---|---|---|---|---|
| 1 | `system hostname <fleet>-XX-v8-{{ "%03d"\|format(train_id) }}` | 84 (all switches) | `...-v8-137` | ✅ Fzg is intended | **→ `fzg_id`** |
| 2 | `dhcp-server client-address N.N.{{ train_id // 2 }}...` (+ `(train_id-1)//2`, +`128+` variants) | ~2,500 | device-VLAN scopes off 137 | ✅ Fzg device plan | **→ `fzg_id`** |
| 3 | `server-id` / `default-router` / `time-server` `{{ ...train_id... }}` (DHCP option blocks) | ~120 | same scope math as #2, off 137 | ✅ Fzg device plan | **→ `fzg_id`** |
| 4 | `{%- if train_id % 2 == 0 %}` (even/odd guard around #2/#3) | 918 | parity of 137 (odd) selects the `.248/.130`-style branch | ✅ must match #2/#3 | **→ `fzg_id`** |
| 5 | `{% if train_id < 128 -%}` (NTP guard) | 45 | guards the NTP line #6 | ⚠️ see #6 | **→ resolve with #6** |
| 6 | `ntp client source address ...{{ train_id }}` / `{{ train_id - 128 }}` / `10.{{project_id+128}}.{{train_id-128}}.1` | 108 | `10.179.9.1` — **DEAD** | 🔴 **BROKEN** — wants internal-28 → `10.179.28.1` | **→ `train_id` (internal) + FIX** |
| 7 | `{%- set train_id = 128 + train_id -%}` (line-1 shadow) | 51 | the bridge itself | n/a — being removed | **→ DELETE (replaced by fzg_id injection)** |
| 8 | `{%- if train_id < 10 %}` + `spanning-tree port-cost {{ train_id * N ... }}` (coupler cost) | 48 | coupler cost | n/a — **M1 deletes these** | **→ DELETED by v9 M1 (moot)** |

### The NTP block (#5 + #6) — the one that needs internal, not Fzg

This is the **only** group that must stay/return to the **internal** namespace. Two clean options for the MR:

- **Option N1 (preferred): use a dedicated internal var.** Inject `train_id` = internal (28) as today, and write the NTP source as the CCU mgmt IP directly: `10.{{ project_id + 128 }}.{{ train_id }}.1` (no `-128`). On box1-t28 → `10.179.28.1` ✅. This drops the legacy `-128` correction entirely and reads off the true internal id. Re-check the `{% if train_id < 128 %}` guard's intent (it was distinguishing remapped-vs-not; with a clean internal var it likely becomes unconditional — confirm before deleting the guard).
- **Option N2 (minimal): keep the formula, feed it the remap.** Less clean; perpetuates the `-128` dance. Not recommended.

**Either way the NTP line keeps `train_id` (internal), NOT `fzg_id`.** And either way it *fixes today's dead `10.179.9.1`.* Flag this fix in the v9 release note — it's a real switch-NTP restoration, customer-visible in time sync.

---

## Net rename plan for the MR

Per `.cfg` (and `dhcp_groups/*.j2`), mechanically:
1. **Delete** line-1 `{%- set train_id = 128 + train_id -%}` (#7).
2. **Rename `train_id` → `fzg_id`** in: hostname (#1), all `dhcp-server client-address` (#2), `server-id`/`default-router`/`time-server` (#3), and the `% 2 == 0` parity guards that wrap them (#4).
3. **Keep `train_id`** (internal) in the **NTP block only** (#5/#6), and **fix** it per Option N1 so it renders `10.179.28.1` not `10.179.9.1`.
4. Coupler cost (#8) is **already removed by v9 M1** — no action.

Engine side (`snmpdevice.py:_inject_metadata`): inject BOTH —
```python
target["train_id"] = self.cfg["train_id"]                          # internal (28) — NTP, CCU-addr
target["fzg_id"]   = self.cfg.get("fzg_id", self.cfg["train_id"])  # Fzg (137) — hostnames, device DHCP
```
`fzg_id` from Puppet `/etc/obn/zz-fzg-id.yaml`. Fallback keeps un-migrated trains rendering as today.

### Per-fleet validation greps (post-edit)
```bash
# no Fzg-meaning train_id left (only the NTP internal use + nothing else):
grep -rn "train_id" nomad-obn-template-*/src/etc/obn/template/   # every hit must be in an ntp line
# fzg_id now drives hostnames:
grep -rc "format(fzg_id)" nomad-obn-template-*/src/etc/obn/template/*.cfg   # = switch count per fleet
# NTP no longer renders the dead -128 form (Option N1):
grep -rn "train_id - 128" nomad-obn-template-*/src/etc/obn/template/   # expect 0
# line-1 shadow gone:
grep -rn "set train_id = 128" nomad-obn-template-*/src/etc/obn/template/   # expect 0
```

---

## Caveats / things to double-check before merging

- **nv4 two-distinct-IDs model** (memory `feedback_train_id_4734_4teiler`): nv4 has the same split conceptually but `backbone-discovery.yaml` carries the box-tNN internal there too; confirm the nv4 NTP/CCU math wants internal and the rename targets are the same patterns (the audit counts include nv4, so the pattern set is identical — but eyeball nv4's `project_id`).
- **`{% if train_id < 128 %}` guard (#5)** — confirm what it gated (remapped vs raw) on a live switch before deleting; it may have been a remap-era artifact that becomes unconditional under Option N1.
- **Device-DHCP scopes (#2/#3) = Stadler IP plan.** These off-137 scopes are part of the customer addressing; renaming to `fzg_id` keeps the *same rendered value* (137), so no IP change — verify the rendered output is byte-identical pre/post on one switch before fleet rollout.
- **Validate rendered output, not just templates** (Principle 4): after the engine+template change, render one switch and diff against a known-good v8 render — only the NTP line (and the deleted coupler cost) should differ.
