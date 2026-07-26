# Zabbix port-down severity split: Nomad ports Medium, Stadler device ports Warning (2026-07-10)

**Status: LIVE fleet-wide (project 50). All changes scoped to DOSTO-owned Zabbix objects — no shared/cross-fleet template edited.**
Owner: Abbas Rizvi. Companion change: `zabbix_train_level_icmp_suppression_prototype_2026-07-10.md`.

## Policy (engineer decision 2026-07-10)

Nomad is responsible only for what OBN discovers/maintains: the switches themselves, the CCU,
the APs, and the switch ports that carry them. Ports feeding Stadler end devices (cameras,
displays, AFZ, Sprechstellen, ADU, amplifiers, ZFR, firewall, …) must alarm at **Warning**
only, so the NMS diagram doesn't show red/Medium for devices we don't maintain.

**Port ownership map** (verified uniform across ALL FOUR template families nv6/nv4/fv5/fv6 by
parsing `~/Documents/nomad-obn-template-*/src/etc/obn/template/*.cfg` port descriptions):

| Ports | Role | Severity |
|---|---|---|
| e0-0, e0-1 | backbone inter-switch trunks | **Average (Medium)** via new "Nomad port" rule |
| e0-4 | AP | **Average (Medium)** via new "Nomad port" rule |
| e0-2, e0-5 | coupler / service | not discovered at all (pre-existing LLD exclusion) |
| everything else (e0-3, e1-x, e2-x) | Stadler end devices | **Warning** |

Caveats:
- **e1-2 is mixed** (4th AP on ~6 roles per family, interior cameras elsewhere) → deliberately
  Warning; a dead 4th AP still raises its own High AP-ICMP alarm, we only lose the Medium
  cable-vs-device hint for that port.
- **The CCU uplink is D3 e0-2** (verified live on 6047 via `show mac-address vlan 100` — CCU MAC
  00:21:21:21:10:01 learned on D3 e0-2; port is templated "OBS D3"). e0-2 is excluded from
  discovery, so it produces no port alarm; CCU islanding is covered by the train-level ICMP
  master trigger (companion doc). Optional future: per-train static item on the D3 switch host.

## Why not an LLD override (the obvious mechanism)

The port-discovery rule on `Template VDS Switch - DOSTO NEU` (10723, rule 162480 `ifDescrv3`)
is **inherited** from `Template SNMP Interfaces v3` (10102, rule 46392), which is the base for
SIX templates incl. cross-fleet ones (Eltec AP - NC chain, Oring Luna, Westermo AP, MEN DANI,
VDS Enzo). **Zabbix 6.0 API silently ignores `overrides` on an inherited LLD rule** — the
update returns success but nothing persists (canary-proven: create/update overrides work fine
on a non-inherited rule). Editing the parent would structurally touch other fleets → rejected
per engineer constraint. Note for posterity: the June-2026 fixes to this rule (filter macro,
e0-2/e0-5 exclusions) DID stick on the child — filters are child-editable, overrides are not.

## What was changed (all on 10723, DOSTO-only)

1. **Trigger prototype 150691** "Port {#SNMPVALUE} DOWN (admin-enabled) on {HOST.NAME}"
   (DOSTO-owned, templateid=0): priority 3 → **2 (Warning)**. ⚠️ Prototype priority edits
   cascade to ALL discovered triggers **immediately** (no LLD re-run needed) — observed live:
   the whole fleet's port-down triggers flipped to Warning within a minute.
2. **New LLD rule 1107780** "Nomad port discovery (backbone + AP)", key `ifDescrv3Nomad`,
   same SNMP walk (`discovery[{#SNMPVALUE},IF-MIB::ifDescr]`), 1h delay, filter
   `{#SNMPVALUE} matches ^e0-[014]$`. Being non-inherited, it is fully DOSTO-controlled.
3. **Item prototypes 1108558/1109336**: `nomad.ifOperStatus[{#SNMPVALUE}]` /
   `nomad.ifAdminStatus[{#SNMPVALUE}]` (SNMP, 60s, ifIndex via {#SNMPINDEX}).
4. **Trigger prototype 341894** "Nomad port {#SNMPVALUE} DOWN (admin-enabled) on {HOST.NAME}",
   priority 3 (Average), expression `min(nomad.ifOperStatus,#2)=2 and last(nomad.ifAdminStatus)=1`
   — the `#2` two-sample guard prevents the known SNMP-subagent-reinit phantom port-down
   (single bad poll can no longer alarm; see memory `project_zabbix_phantom_port_down_snmp_subagent`).
5. **778 already-open port-down problems** on Stadler ports fleet-wide were ack'd with
   severity→Warning so NMS converges immediately (new events fire at Warning natively).

**Known duplicate-by-design:** when a Nomad port (e0-0/e0-1/e0-4) fails, TWO alarms fire — the
Medium "Nomad port ... DOWN" plus the generic Warning — because the inherited rule's filter
cannot exclude Nomad ports (child filter edits would affect... actually child filters ARE
editable; NOT changed to stay surgical — revisit if the duplicate annoys). Accepted trade-off
of the DOSTO-only option (Option B) vs. editing the cross-fleet parent (Option A, rejected).

**Convergence:** the new rule's first discovery runs per host on the hourly LLD cycle
(forced immediately on 6047). Nomad-port triggers appear per train over ~1h fleet-wide.

## NMS coloring — investigated, no NMS change needed

The NMS train chip / device box color follows the **train-level `severity` field = max
severity of open issues** (backend-computed from Zabbix; `/monitoring/trains?projectId=50`).
Verified: T4736113 (only port-down issues) already showed severity 2 after the flip, while
6047 stays red because of its genuinely-missing AP (High — correct). The train-type template
(`/configurations/50/traintypes/NV6`) has a per-device-type `alarmColor` field (null everywhere,
not severity-conditional) and NO severity→color mapping; the mapping is NMS frontend/backend
logic. If a different threshold is ever wanted, that's an R&D/NMS product ask — but with
Stadler ports at Warning the diagram already stops going red for them.

## Rollback

```
1. triggerprototype.update 150691 priority=3 (cascades fleet-wide immediately)
2. discoveryrule.delete 1107780 (removes its discovered items+triggers everywhere)
3. (open problems keep ack'd Warning severity until they resolve — acceptable residue)
```

## Verification checklist

- [ ] ~1h after 2026-07-10 ~15:00 UTC: `trigger.get` on a few trains — each switch should have
      3 "Nomad port ..." triggers (e0-0/e0-1/e0-4) at priority 3 with items collecting.
- [ ] NMS: trains with only port-down issues show non-red chips (T4736113/115/117).
- [ ] Next real Stadler port failure arrives as Warning; next backbone/AP port failure arrives
      as Medium (+ the expected duplicate Warning).
