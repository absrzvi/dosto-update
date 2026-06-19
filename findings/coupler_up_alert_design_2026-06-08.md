# Design note: "coupler coupled" alert (e0-2 Frontkupplung up = train coupled)

**Status:** DESIGN ONLY — not implemented. Needs review before any live change to the shared Zabbix template `Template VDS Switch - DOSTO NEU` (id 10723, ~700 switch hosts).
**Raised:** 2026-06-08, during 6018 switch-monitoring work.

## Requirement (engineer)

For the **front-coupler ports**, invert the normal port-down logic:
- Coupler port **DOWN** → no alert (train running solo is normal).
- Coupler port **UP** → **alert** ("train is coupled to another consist") — an informational/status event, not a fault.

This is the opposite of the standard port-down trigger we added tonight (`ifOperStatus=2 AND ifAdminStatus=1` = fault). Currently e0-2 is **excluded** from monitoring entirely (LLD filter `NOT ^e0-2$`), so step 1 of any implementation is to bring the *coupler* e0-2 ports back into monitoring — but only with the inverted trigger, and only on the coupler switches.

## The hard constraint (why this isn't a one-line edit)

`e0-2` means **different things on different switch positions**, but the shared template's LLD keys only on the port NAME (`{#SNMPVALUE}` = `e0-2`) — identical across all 18/12 switch hosts. Verified from the OBN v8 cfg templates:

| Role | e0-2 (NV6) | e0-2 (NV4) | desired logic |
|---|---|---|---|
| **A1, A3, B1, B3** | Frontkupplung (coupler) | Frontkupplung (coupler) | **UP = alert (coupled)** |
| D1/D3 (NV6), G1/G3 (NV4) | OBS | OBS | **DOWN = alert (normal fault logic)** |
| A2, C*, E*, F*, D2/G2 | unused/blank | unused/blank | no alert (excluded, as now) |

So a template-level rule keyed on `e0-2` alone **cannot** distinguish a coupler e0-2 (A1/A3/B1/B3) from an OBS e0-2 (D1/D3 / G1/G3). Applying "up = alert" to all e0-2 would mislabel the OBS ports; applying the normal down-trigger to all e0-2 would (re)introduce solo-train coupler-down noise.

**Coupler switch host set** (where the inverted logic must apply):
- NV6: `R1_SW1` (A1), `R1_SW3` (A3), `R6_SW1` (B1), `R6_SW3` (B3)
- NV4: `R1_SW1` (A1), `R1_SW3` (A3), `R4_SW1` (B1), `R4_SW3` (B3)  *(NV4 = 4 cars; B is R4)*
- (host→role map verified 2026-06-08; see [[project_zabbix_switch_template_wrong_oids]] memory and the nv6/nv4 topology.)

## Candidate mechanisms (pick at implementation, must auto-inherit fleet-wide)

1. **Host macro on coupler switches.** Define a macro (e.g. `{$IS_COUPLER_SWITCH}=1`) on the A1/A3/B1/B3 host prototypes (or via NMS provisioning so it's set at host-creation). Then a trigger prototype `last(ifOperStatus[e0-2])=1 and {$IS_COUPLER_SWITCH}=1` fires coupler-up only on those hosts. Cleanest IF the macro can be set at provisioning so power-on trains inherit it. Needs: where does NMS/OBN set host macros? (unknown — investigate).
2. **Separate LLD rule + filter on host context.** A dedicated "coupler" discovery rule whose filter matches both port `e0-2` AND a host-identifying macro. LLD filters key on discovered macros, so this needs the host role exposed as an LLD macro — may not be available.
3. **Dedicated coupler host group.** Put the 4 coupler switches per train into a Zabbix host group; attach the inverted trigger via that group. Requires NMS to assign coupler switches to the group at provisioning (fleet-inherit question again).

The recurring open question for ALL options: **how does a coupler switch get tagged as such at provisioning time** so a freshly-powered train inherits the distinction automatically (rather than a per-host edit that goes stale). That's the thing to resolve first — likely an NMS train-type/host-prototype config question, same layer as the SNMP-cred fix.

## Trigger semantics (once scoped)

- **Coupler-up trigger:** `last(ifOperStatus[e0-2])=1` on coupler switches → severity **Information** (not a fault; it's a "train coupled" status). Name e.g. `Train coupled — coupler {#SNMPVALUE} UP on {HOST.NAME}`.
- Coupler ports must be **excluded from the normal port-down trigger** (they already are, via the `NOT ^e0-2$` LLD filter — keep that exclusion for the down-fault trigger; the coupler-up trigger is a separate path).
- OBS e0-2 (D1/D3/G1/G3): leave on normal down-fault logic (currently excluded by the blanket `NOT ^e0-2$` — note this means OBS e0-2 is currently NOT monitored either; decide if OBS-down should alarm, separate question).

## Caveat noted at design time

We currently exclude ALL e0-2 (and e0-5) from discovery. This design re-includes coupler e0-2 under inverted logic. Implementing it touches the shared 700-host template, so it warrants the same Zabbix-owner review as tonight's other 10723 changes.
