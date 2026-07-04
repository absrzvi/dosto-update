# Durable Fzg-ID — eliminate per-train hand-hardcoding (fold into v9)

**Date:** 2026-06-30 · **Author:** AR + Claude · **Status:** DESIGN — verified against live OBN source, not memory.
**Goal:** Fzg ID for switch hostnames + port-level IPs comes from OBN deterministically, set once per train via Puppet, so **no `obn update c` (any version, including v9) can ever wipe it** and `dosto-fzg-id-check` becomes a verification-only safety net instead of a mandatory fix step.

---

## What I verified in the OBN source (ground truth)

Source read locally at `.tmp/gitlab-repos/obn/src/usr/share/obn/`:

1. **`lib/configuration.py:56-61`** — `Configuration` loads **every `*.yaml` in `/etc/obn`** (`OBN_CONFIG`, default `/etc/obn`), **sorted alphabetically**, and merges with `_config.update(...)` so **a later-sorting file's keys override an earlier file's.** `train_id` is just a merged key.
2. **`lib/device/snmpdevice.py:488`** — `target["train_id"] = self.cfg["train_id"]`. The value the template sees comes **straight from that merged config dict**, then `snmpdevice.py:536` renders the `.cfg` with it. No other source.
3. **`lib/device/ccudevice.py:61`, `dhcpwalker.py:41`, `ospf.py:62`** — `train_id` also drives CCU/DHCP/OSPF IP math, all from the same `self.cfg["train_id"]`.
4. **`report_ace.py:49-54`** — the "master CCU" election parses `box[0-9]+-t(NN)` from the **device serial** (the Nomad-internal ID), NOT from `cfg["train_id"]`. So overriding `train_id` for Fzg purposes does **not** disturb master-CCU/coupled-root logic. ✅

**Conclusion:** `train_id` is a plain config key with last-file-wins precedence. We can supply the Fzg ID from a **separate, Puppet-owned, late-sorting YAML in `/etc/obn`** and it overrides whatever `backbone-discovery.yaml` carries — **with zero OBN engine code change.**

---

## Why the hand-hardcode exists today (the actual root cause)

- OBN feeds the template exactly one `train_id` input, today from `backbone-discovery.yaml`, which holds the **Nomad-internal ID** (`box1-tNN` number), not the ÖBB Fzg.
- The repo templates try to bridge with line-1 `{%- set train_id = 128 + train_id -%}` — an **arithmetic guess** that is wrong for almost every train (the Nomad→Fzg map is an arbitrary lookup, not `+128`).
- So commissioning hand-overwrites line 1 on the CCU with `{%- set train_id = <Fzg> -%}`. That literal lives in a `.deb`-owned file → **the next `obn update c` from any fresh package restores the broken formula** → the fragility you want gone.

The mar5 rule (don't put Fzg in `backbone-discovery.yaml`) is correct and stays: that file controls the CCU subnet; changing its `train_id` moves the CCU IP on reboot (the Fzg 133 disconnect). The fix is a **different** file.

---

## Decision Gate — RESOLVED on live box1-t28 (Fzg 137), 2026-06-30

Verified on the CCU you named (`10.179.28.1`, internal-28 / Fzg-137):

| Fact | Value on box1-t28 | Source |
|---|---|---|
| `backbone-discovery.yaml: train_id` | **28** (Nomad-internal) | live grep |
| `project_id` | 51 | live grep |
| Switch template line-1 (hand-hardcoded) | `{%- set train_id = 137 -%}` (Fzg) | live grep, all nv6-*.cfg |
| **CCU vlan100 IP** | `10.179.28.129` = `10.{128+51}.{28}.129` → **built from internal-28** | `ip addr` |
| Switch-port DHCP line in template | `172.17.{{ train_id // 2 }}.120` → uses the **line-1 Fzg 137** (=68) | live grep |

**The two values genuinely conflict and must stay separate:**
- **Engine-side Python** (`ccudevice.py:61`, `ospf.py:62`, `dhcpwalker.py:41`) reads `cfg["train_id"]` and needs **28** — it builds the CCU's own `10.179.28.x`. Overriding `cfg["train_id"]` to 137 would move the CCU to `10.179.137.x` on next render → **breaks the train.** This is the Fzg-133 disconnect mechanism, exactly why the mar5 rule exists.
- **Switch `.cfg` templates** (hostname + switch-port DHCP `train_id // 2`) need **137** — and today they get it purely from the **line-1 `{%- set train_id = 137 -%}` shadow**, which overrides the injected `cfg["train_id"]=28` *within each template* (Jinja template-scope `set` shadows the render context).

→ **A blunt `train_id:` override YAML is WRONG — it would corrupt the CCU IP. The correct fix is a separate `fzg_id` key consumed only by the switch templates.** (Tiny engine change. Folds into v9 as a coordinated template + engine release, which is what you chose.)

---

## The durable fix — separate `fzg_id` key (small, surgical engine change)

The whole problem is that the switch templates get their Fzg from a **hand-edited line-1 shadow in a `.deb`-owned file.** Move that value to a Puppet-owned `fzg_id` key that the engine injects, and reference `fzg_id` (not `train_id`) inside the switch templates. `train_id` keeps meaning Nomad-internal everywhere — no mar5 violation, no CCU-IP risk.

### 1. New per-train file (Puppet-owned, NOT in the OBN .deb)
```yaml
# /etc/obn/zz-fzg-id.yaml  — Puppet-managed, per train.
fzg_id: 137        # ÖBB Fzg ID. train_id (28, Nomad-internal) stays in backbone-discovery.yaml.
```
`zz-` sorts last so it can't be clobbered by an earlier file; but it's a **new key**, so there's no override race at all — it simply adds `fzg_id` to the merged config.

### 2. One-line engine change (`snmpdevice.py:_inject_metadata`)
```diff
  target["train_id"] = self.cfg["train_id"]   # Nomad-internal — CCU/DHCP/OSPF IP math
+ target["fzg_id"]   = self.cfg.get("fzg_id", self.cfg["train_id"])  # ÖBB Fzg for switch hostnames/ports
```
The `.get(..., train_id)` fallback means **trains without the new file keep today's behaviour** (whatever `train_id` resolves to) — safe incremental rollout, no flag day.

### 3. Switch-template change (goes in the v9 MR) — `fzg_id` replaces the line-1 shadow
On every `nv6-*.cfg` / `fv5-*.cfg` / `fv6-*.cfg` (and nv4 inline form), delete the line-1 `{%- set train_id = ... -%}` shadow and rename the **switch-port / hostname** uses of `train_id` → `fzg_id`:
```diff
- {%- set train_id = 128 + train_id -%}
- system hostname nv6-A1-v8-{{ ("%03d"|format(train_id)) }}
+ {# Fzg comes from /etc/obn/zz-fzg-id.yaml via engine fzg_id key. No line-1 shadow. #}
+ system hostname nv6-A1-v8-{{ ("%03d"|format(fzg_id)) }}
...
-   dhcp-server client-address 172.17.{{ train_id // 2 }}.120
+   dhcp-server client-address 172.17.{{ fzg_id // 2 }}.120
```
> ⚠️ **Scope care (Principle 3):** rename ONLY the uses that are semantically Fzg (hostname + the switch-port `dhcp-server client-address` block + the `ntp ... {{ train_id - 128 }}` line if that's Fzg-derived). Do NOT touch any `train_id` use that is genuinely Nomad-internal. Audit every `train_id` occurrence per file (there are ~30 in nv6-A1) and classify each before renaming. The M1 coupler-cost lines are **deleted** by v9 anyway, so they're moot.

### 4. Puppet wiring (Config Management repo)
Per-train `fzg_id` in node hieradata (`box1-tNN.dostoneu.21net.com.yaml`), `obn` class writes `/etc/obn/zz-fzg-id.yaml` from it. Populate from the fleet-status Fzg column. Puppet = single source of truth, re-asserted every run; `obn update c` can't wipe it (different file, different key).

### Net effect
- `obn update c` (any version) renders correct Fzg hostnames/IPs because `fzg_id` comes from the unowned Puppet file — **the hand-chroot is dead.**
- `train_id` means Nomad-internal everywhere, consistently — **mar5 rule honoured, CCU-IP safe.**
- Trains not yet migrated fall back to old behaviour via `.get()` — **safe gradual rollout.**

---

## vlan7 — same disease, fold into the SAME release (decided 2026-06-30: land together)

The CCU vlan7 IP has the identical root fragility: Puppet's `nd_redundancy/networks.epp` computes it from a **broken `train_id`-based formula**, so engineers override it by hand in the `nd-systemupdate.sh shell` chroot — and a **snapshot promote (`nd-systemupdate up`) re-renders the Puppet formula and wipes the hand-fix.** (`obn update c` does NOT touch vlan7 — only NetworkManager files matter, and OBN doesn't write them. So v9's config push is safe for vlan7; the risk is purely snapshot/image refresh.)

**Broken formula in `networks.epp` (verified present 2026-06-30):**
```
line 141 (even branch): ipaddress: "172.19.{{ 128 + ((fis_id+train_id) // 2) }}.2"
line 143 (odd branch):  ipaddress: "172.19.{{ 128 + ((fis_id+train_id-1) // 2) }}.130"
```

**Fix — swap the input to `fzg_id` (keep both even/.2 and odd/.130 branches):**
```
line 141: ipaddress: "172.19.{{ 128 + (fzg_id // 2) }}.2"
line 143: ipaddress: "172.19.{{ 128 + ((fzg_id-1) // 2) }}.130"
```
Verified 9/9 against the `dosto-vlan7-config` validated set (Fzg 1→172.19.128.130, 2→129.2, 133→194.130, 137→196.130, 138→197.2, …). Same `fzg_id` Puppet key already being added for the node files — no new per-train data.

**Net:** after this, Puppet re-asserts the correct vlan7 IP on every run → `nd-systemupdate up` no longer wipes it → `dosto-vlan7-config` becomes verify-only (like `dosto-fzg-id-check`). **Lands in the same coordinated release** as the templates + engine + node-file `fzg_id` (engineer decision: no interim/partial rollout).

### Coordinated release contents (all land together)
| Repo | Change |
|---|---|
| 4× `nd-obn-template-*` | v9 coupler (M1–M4) + NTP fix + `fzg_id` rename + line-1 shadow removal |
| `onboard/obn` (engine) | inject `target["fzg_id"] = self.cfg.get("fzg_id", self.cfg["train_id"])` |
| Config Mgmt (Puppet) | `obn::fzg_id: <Fzg>` per node (50-train list) + `networks.epp` vlan7 formula → `fzg_id` |

---

## How this changes the v9 runbook

- **v9 MR gains:** line-1 formula removal in all 4 fleets (template half of this fix) + the existing M1–M4 coupler changes.
- **Config Management MR (new, parallel):** `obn` class lays down `/etc/obn/zz-fzg-id.yaml` from `*::fzg_id` node hieradata; populate `fzg_id` for every dostoneu node from the fleet-status Fzg column.
- **Phase 3a (`dosto-fzg-id-check`) downgrades** from "mandatory fix gate" to "verification-only" — it should now always read `all_match` because Puppet owns the value. Keep running it as the post-deploy assertion (Principle 4), but it stops being a hand-fix step. Update the skill's framing once the durable fix lands.
- **Retirement criterion:** once one full coupled pair deploys v9 + the override file and `dosto-fzg-id-check` reads `all_match` across a reboot AND an `obn update c`, the per-train hand-hardcode is formally dead.

---

## What stays unchanged (don't let this fix sprawl — Principle 3)

- `backbone-discovery.yaml` — untouched (mar5 rule; it governs CCU subnet, not Fzg).
- `report_ace.py` master-CCU election — unaffected (parses serial, not `train_id`).
- The Nomad-internal ID / `box1-tNN` convention — unchanged.
- nv4's two-distinct-IDs model — the override file approach works identically; nv4 just also needs its line-1 inline form de-bridged.
