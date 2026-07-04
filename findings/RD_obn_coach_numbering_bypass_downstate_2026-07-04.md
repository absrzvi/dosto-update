# R&D proposal — OBN silently drops healthy, discovered switches from its report (monitoring false-negative) when a switch is bypassed

**Author:** Abbas Rizvi
**Date:** 2026-07-04
**Component:** `nd-obn` — `lib/report/report_dosto_neu.py` (`DostoNeuReport.number_coaches`)
**Observed on:** bench box1-t122 (4122, nv4 A-G-E-B), nd-obn 2.3.8
**Status:** proposal / not started

---

## 0. Severity — this is a monitoring false-negative, not a cosmetic numbering bug

**OBN silently drops discovered, healthy, running switches from its report.** On the bench, 10 switches are physically present, powered, passing traffic, and answering SNMP — OBN's report shows **2**. Not "2 up + 8 flagged missing": just 2, with no indication the report is truncated. The other 8 healthy switches are erased from the report, the NMS/MQTT message, and `validate`.

Consequences:

- **Monitoring goes blind to real hardware.** The 8 dropped switches are not in the NMS report, so NMS/Zabbix can never alarm on them. If one of those 8 later fails, the dashboard stays green — a dead switch with no alarm.
- **The report reads as healthy.** A 2-row backbone table on a 12-switch consist looks like "small consist, all present," not "10 switches missing from view." Nothing signals the truncation.
- **Trigger is a single common event.** One switch losing power / rebooting mid-scan cold-bypasses, mislabels the switch that moves into its slot, and collapses everything "downstream" of the mislabel to invisibility. This will happen in the field routinely, not just on the bench.
- **The Bug-10 guard made detection worse.** It converted a loud 100%-CPU hang into a silent 2-row report — the failure went from "obviously broken" to "looks fine, isn't."

**The minimum bar (independent of the numbering redesign):** a device OBN has discovered and can SNMP-poll must NEVER be silently deleted from the report. If it can't be coach-numbered, it must still appear (e.g. as `UNPLACED` / `status=DOWN`), never vanish. See §5c — this is separable from, and higher priority than, getting the coach numbers right.

## 1. Summary (the ask, in two lines)

When a consist switch is **cold-bypassed** (powered off / failed, backbone relayed through it), OBN's coach-numbering walk mis-numbers the switch that moves into the gap, then collapses — and `normalise_devices()` deletes every device it couldn't number, **including healthy, SNMP-reachable switches**. The whole downstream fabric vanishes from the report instead of showing them.

Ask (two separable parts): **(A, must-have)** stop silently dropping discovered/reachable devices — surface unnumberable ones as `UNPLACED` instead of deleting them; **(B, the fix)** make `number_coaches` **topology-anchored** instead of neighbour-following, and emit a first-class **DOWN** device for a bypassed/absent switch.

## 2. Impact

- `obn report` / `obn validate` show a near-empty backbone table when a single switch is down. On the bench, 10 healthy switches were reduced to 2 numbered rows; the other 8 fell into `test_unnumbered_devices` / were dropped.
- No operator-visible signal that says "switch A1 is DOWN." The engineer cannot tell "one switch off" from "consist mis-cabled" from OBN output alone — both look like a collapsed report.
- Downstream consumers (NMS/MQTT report from `create_nms_device_nodes`) never receive the down switch, so monitoring can't alarm on it.
- This is the same class of failure that historically triggered the Bug-10 BFS hang; the bug-10 guard stopped the hang but converted it into **silent truncation**, which is arguably worse for diagnosis.

## 3. Root cause — the bypass causes an identity shift, not just a gap

VDS Rail Consist Switches have **cold bypass**: a powered-off switch relays its backbone trunks (`e0-0`/`e0-1`) straight through, so its two chain-neighbours become LLDP-adjacent to each other. See ops memory `vds-switch-cold-bypass`.

`number_coaches` is a **pure walk over live LLDP** driven by port rules (e0-0/e0-1 → coach ±1). It has **no model of the expected topology**. So when A1 is bypassed:

1. The switch that now sits where A1 used to be (A3, directly reachable from G1) is assigned **A1's coach/device identity** by the port rule — because the rule keys off *position in the walk*, not *who the switch actually is*.
2. That mislabel means the next hop matches no rule → the walk dead-ends.
3. `normalise_devices()` drops everything unnumbered.

### Evidence (bench box1-t122, real `/tmp/discovery.json`, reproduced in a local harness)

CCU plugs into G1 on LAN1. Real inter-switch edges (port → neighbour):

```
CCU        port1 -> G1
G1  (.178) port5 -> CCU, port4(e0-1) -> E2, port3(e0-0) -> A3
A3  (.182) port4 -> A2, port3 -> G1
E2  (.180) port3 -> E3, port4 -> G1
... (A2, G2, G3, E1, E2, E3, B1, B2 all present & healthy in discovery.json)
```

Truly absent from discovery.json: **A1, B3** (cold-bypassed / dead).

The walk makes exactly two hops then dies:

```
CCU -> G1  port1(LAN1)  = coach2 dev1     OK
G1  -> A3  port3(e0-0)  = coach1 dev1     <-- MISLABELLED (A3 given A1's identity)
                                              next hops match no rule -> walk stops
Numbered: {G1:(2,1), A3:(1,1)}   ← matches the real `obn validate` output exactly
```

So the observable "only A3 + G1 numbered, 8 dropped" is fully explained: **A3 is impersonating A1 because it moved into A1's topological slot, and the mislabel collapses the walk.**

## 4. Why the cheap fixes don't work

- **"Insert a DOWN placeholder node and let the walk flow through it"** — fails. The port rules key on the *arriving switch's* `device_number`, which the placeholder never legitimately earns, and the real arriving switch (A3) has already been given the wrong number. A phantom node cannot repair an identity error. (Prototyped in the harness — placeholder injected, walk still numbered only A3+G1.)
- **Bumping the coach counter past a gap** — would keep numbering but propagate the A3-as-A1 identity error to the whole A coach and shift every downstream coach by one.

The walk's neighbour-following model is the root problem: once the physical chain is perturbed by a bypass, *position* no longer equals *identity*.

## 5. Proposed fix — topology-anchored numbering + DOWN state

Two parts.

### 5a. Anchor discovered switches to expected positions

Give `number_coaches` the **expected inter-coach adjacency** for the consist (the aliasing-resolved chain already captured per-schema in our `_shared/{nv4,nv6}-topology.md`; R&D-side this should come from the templates / a schema file, not a hardcode). Then number by **matching the discovered LLDP graph against the expected chain** rather than blindly following ports:

- Walk the *expected* chain from the CCU coach outward.
- At each expected position, find the discovered switch that fits (by its adjacency signature / hostname position if trustworthy).
- If the expected switch is **present** → assign its real coach/device.
- If the expected switch is **absent** but its two expected neighbours are present and LLDP-adjacent to each other on the **ports that face the missing position** (the cold-bypass signature) → emit a **DOWN** placeholder for it and **continue** past the gap, keeping the downstream switches' true identities.

This keeps A3 = A3, numbers E/G/B correctly, and yields A1 = DOWN.

### 5b. First-class DOWN device state

`Device` (in `lib/report/device.py`) has no status field. Add one (e.g. `status: str = "UP"`), set it to `"DOWN"` on bypass/absent placeholders, and:

- Have `normalise_devices()` **retain** DOWN devices (currently it deletes anything with `coach_number is None`; DOWN devices get a real coach/device number, so they survive if the placeholder is numbered).
- Surface `status` in `create_nms_device_nodes()` and the `backbone_validate.py` switch-overview table so a DOWN switch renders as a row (`A1  DOWN`) rather than an omission.

### 5c. Must-have, ships independently: never silently drop a discovered device

This is the highest-priority, lowest-risk change and does **not** depend on the numbering redesign in 5a.

`normalise_devices()` currently deletes any device with `coach_number is None`:

```python
self.device_instances = {
    k: v for k, v in self.device_instances.items()
    if v.coach_number is not None and v.device_number is not None and v.type is not None
}
```

A switch that was **discovered and SNMP-polled** but that the walk failed to number is thrown away here — that is the mechanism by which 8 healthy switches disappear. Change the contract to: **a discovered, reachable device is always retained.** If it couldn't be coach-numbered, keep it with an explicit `UNPLACED` marker (e.g. `coach_number = None` retained + `status = "UNPLACED"`), and render it in the report/NMS in an "unplaced devices" section rather than dropping it.

Effect on the bench case *even without* 5a: instead of a 2-row table, the report shows 2 numbered + 8 `UNPLACED` (all reachable) + 2 `DOWN`/absent — i.e. all 12 accounted for and monitoring can see every live switch. Numbering them correctly (5a) is the follow-on quality improvement; **not losing them (5c) is the correctness floor.**

Note this also needs the report/NMS builders (`create_nms_device_nodes`, `backbone_validate.py`) and any code that sorts/groups by `coach_number` to tolerate `UNPLACED` (null coach) devices without erroring.

### Distinguishing DOWN vs mis-cable (keep it a lead, not a verdict)

The reciprocal-on-expected-ports signature is a **strong lead**, not proof — a bypass-shaped mis-cable (L patched straight to R while the switch is fine on a dangling cable) looks identical over LLDP. OBN should mark the placeholder `DOWN (suspected cold-bypass — verify power)` rather than asserting it. Two signals sharpen it if available: the reciprocal must land on the **expected toward-X ports**, and independent confirmation that X is powered flips the call to mis-cable. (This is already how the ops-side `dosto-device-discovery` Step 4b frames it.)

## 6. Interim mitigation already shipped (ops side)

`dosto-device-discovery` Step 4b (2026-07-04) does the reciprocal-LLDP bypass classification from the CCU side and reports `switches_missing[].bypass_status ∈ {cold_bypass, dead_link, link_down, miscable}` with a Stadler-actionable "check power/health of X first" instruction. This gives operators the DOWN signal today **outside** OBN. The engine change above is what puts the signal **inside** OBN/NMS so monitoring can alarm on it.

## 6b. Field confirmation — 4736-109 / Fzg 137 (2026-07-04)

First **production** occurrence, on a live train (not the bench), confirming the bench RCA generalises:

- CCU `10.179.28.1`, nd-obn **2.2.23** (pre-fix), 6-car nv6.
- OBN/DHCP see **16/18 switches**. The two absent (E2, C3) are exactly the two failure classes this doc separates:
  - **E2 = cold_bypass** (§5a/5b case). D1 e0-1 LLDP→ E3 across E2's slot, both links UP 10G / 0 CRC / carrier-false 0 (reciprocal clean-link). Powered-off/failed switch, backbone relayed through — surfaced today only by ops-side reciprocal LLDP, invisible to OBN/NMS.
  - **C3 = healthy-but-unnumbered** (§5c case). Present and forwarding heavily (C2 e0-0→C3 UP 10G, RX 9.9 GB / TX 280 GB, 0 CRC) but with **no DHCP lease / no mgmt IP** — dropped from the report, invisible to NMS. Note C3's root cause is a mgmt-IP/DHCP fault local to the switch, so the §5c floor would surface it as `UNPLACED` (good) but the *full* fix also needs C3 to reacquire a vlan100 IP to become a normal monitored host.
- **NMS was not alarming on either** — the dashboard read 16/18 as green. This is the exact "dead switch with no alarm" consequence from §0, observed in the field.

Tracked ops-side: cable register #13 (E2), fleet-journal Fzg 137 entry 2026-07-04 (both). Reinforces the §0 severity framing and the §5c "correctness floor" priority.

## 7. Test fixtures

The bench `discovery.json` (A1 + B3 bypassed, 10 present) is a ready-made regression fixture — captured 2026-07-04, committed at `findings/fixture_bench_box1-t122_discovery_2026-07-04.json`. Suggested unit tests:

1. **(5c floor)** One switch bypassed → **all 10 discovered switches still present in the report** (2 numbered + 8 UNPLACED), 0 dropped. This is the must-pass test; it fails today (only 2 survive).
2. Full consist present → unchanged numbering (no regression).
3. One mid-chain switch absent + neighbours reciprocal → that switch DOWN, all others correctly numbered (5a).
4. Terminus switch (last-coach SW3) absent → DOWN via single-neighbour dead-link signature.
5. Two adjacent switches absent → both DOWN or flagged un-anchorable (must NOT mislabel survivors).
6. Genuine mis-cable (switch present but wired to an unexpected peer) → NOT reported as DOWN.

## 7b. Prototype validated end-to-end on the bench (2026-07-04)

A working prototype of §5a + §5c was built, proven against the bench fixture in a local harness (happy-path, bypass, three-gap, and misimage cases — 0 mis-numbered switches in all), then persisted to bench box1-t122 via NDSU chroot and **confirmed on the real `obn validate`**:

- **Before:** 2-row backbone table (only A3 + G1), 8 healthy switches dropped.
- **After (running on bench, snapshot run3):** full 12-row table — all 10 present switches numbered at correct positions, **A1 and B3 shown as explicit DOWN rows** (`A1 DOWN (localised via A3,G1)`, `B3 DOWN (localised via B1,B2)`).

Approach that worked: **validated-hostname anchoring** — trust the switch's hostname-declared position, but validate it against the expected adjacency (bypass-tolerant: an absent expected-neighbour may be replaced in the live view by the switch beyond it). A switch whose hostname claim is contradicted by its neighbours is held out as `UNPLACED` (misimage-safe), never mis-numbered. Absent expected positions with an anchored neighbour → `DOWN`; §5c retains all discovered switches.

Prototype shortcuts to clean up when productionising (all cosmetic, all in-scope for the MR):
- Topology model is hardcoded in `report_dosto_neu.py` — load from templates/schema instead.
- Status is encoded in the `config` string + a `0.0.0.0` sentinel IP (chosen to avoid editing `device.py` / `backbone_validate.py` for the PoC). Productionise with a real `Device.status` field and teach `backbone_validate.py` to skip IP/target validation for DOWN rows (currently they trip `test_incomplete_devices` and show a spurious `(nv4-A1-v5) ✗` target — cosmetic).
- `normalise_devices` is overridden in `DostoNeuReport` (base `report.py` untouched, so ace/ccjpa are unaffected) — fine to keep, or lift into the base with a per-report opt-in flag.
- Prototype file (validated): committed alongside this doc as `findings/report_dosto_neu_PATCHED_2026-07-04.py`. Bench backup of the original kept in-snapshot at `report_dosto_neu.py.orig-20260704`.

## 7c. Robustness rules (learned from a flaky-link false-alarm, 2026-07-04)

First bench persist over-asserted: on an **incomplete discovery scan** (SNMP timeouts on the cellular link captured only 6 of 10 switches), the report labelled healthy-but-not-scanned switches `ABSENT`/`DOWN` — the *inverse* false-negative (false DOWN alarms), arguably worse than the original silent drop. Two rules were added and validated live on the bench:

1. **DOWN requires positive bypass evidence.** A position is only asserted `DOWN` when its two expected neighbours are BOTH anchored AND LLDP-reciprocate across it (each sees the other on the port facing the missing position). Every other not-discovered position is **`UNKNOWN`** ("not discovered; no bypass evidence — verify power/SNMP"), never DOWN. Consequence: a **terminus** switch (single neighbour, e.g. B3) can't be proven bypassed from LLDP alone → it is UNKNOWN, not DOWN, on a full scan. (A real dead terminus needs port link-state — `dead_link` signature — which `discovery.json` doesn't carry; a proper fix would extend discovery to capture the neighbour's toward-terminus port link/err state.)

2. **Discovery-completeness gate.** Before trusting any absence, compare discovered switch count to the **DHCP-lease count** (independent ground truth: distinct `a0:59:3a` MACs in `/var/lib/dhcp/dhcpd.leases`, deduped — matches `dhcp-lease-list`). If `discovered < leased`, emit a loud banner row (`⚠ DISCOVERY INCOMPLETE N/M switches scanned — re-run obn discover`) and mark ALL unseen positions `UNKNOWN`, never DOWN. Verified live: a forced 9/10 partial scan produced the banner + UNKNOWN rows, zero false DOWN.

The completeness gate counts distinct **switch positions** (from `client-hostname` in `dhcpd.leases`, e.g. `4t-A3-...` → `A3`), **not MACs**. This is deliberate and load-bearing: `dhcpd.leases` accumulates expired lease records and never drops an old MAC, so a **hardware swap** (replacement unit, new MAC, same position/hostname) would make a MAC-count double-count that position permanently (10→11→…) and false-fire the INCOMPLETE banner forever. Position-counting is swap-stable and consistent with the rest of the algorithm's position-based identity. Verified against the real 1261-line bench leases file + a simulated A3 swap: MAC-count went 10→11 (wrong), position-count stayed 10 (correct).

Productionization note: a fleet version might prefer the expected consist size (12/nv4, 18/nv6, minus known-absent positions) or a Puppet-provided count as the ground truth instead of the lease file. Also note a swap breaks **NMS/Zabbix** (hosts are MAC-joined) — the new MAC needs a Zabbix reconcile; that's pre-existing NMS behavior, outside this fix.

## 7d. NMS-consumption constraint (learned the hard way, 2026-07-04)

`number_coaches` writes to `self.device_instances`, which feeds THREE consumers, not one:
1. `obn validate` console table (via the `discovery.prev.json` snapshot),
2. the **NMS/MQTT report** (`create_nms_device_nodes`) — which **provisions Zabbix hosts** and **draws the consist diagram**,
3. the snapshot file itself.

Two mistakes were made and corrected in sequence:

- **First mistake — placeholders polluted NMS.** The synthetic DOWN/UNKNOWN/UNPLACED/banner devices were added to `device_instances`, so NMS created **junk Zabbix hosts** from them: `Car 0` (from the coach-0 INCOMPLETE banner), `Car 99` (from the coach-99 UNPLACED sentinel), and `DOWN:A1` leaked into a real host's MAC field. A device with a bogus coach (0/99) or a `PLACEHOLDER:`/`SCAN:` mac becomes a junk host.
- **Second mistake — over-correction blanked the diagram.** Moving **all** placeholders out of the report (to a console-only side-file) removed the A1/B3 DOWN devices too. But **NMS needs a device in every chain slot to render the consist diagram** — with slots (1,1) and (4,3) missing, the diagram pane went **blank**.

**The correct split (now running):**
- **In the report / `device_instances`:** DOWN/UNKNOWN devices for **real chain slots** (A1=coach1/dev1, B3=coach4/dev3, …), each with a **valid coach/device** (so NMS matches them to the correct `R#_SW#` host, not a junk host) and a **`7.7.7.7` ip** (the not-found placeholder address). NMS draws these as down boxes — this is what makes the diagram show A1/B3 as down. Verified: diagram renders + shows the right alerts; a **complete** report even let NMS self-heal a host (G2) that a prior messy re-create had dropped.
- **Console-only side-file (`discovery.placeholders.json`, merged by `backbone_validate.load_devices`):** ONLY the coach-0 `DISCOVERY INCOMPLETE` banner and the UNPLACED (unnumberable real switch) rows — these have no valid slot, so publishing them makes junk hosts.

**MR rule:** a bypassed/absent switch at a *known chain position* MUST appear in the NMS report (valid slot, 7.7.7.7 ip, DOWN status) so the diagram renders it. Only rows with no valid position (banners, unplaceable devices) stay console-only. Productionize with a real `status` field rather than the `DOWN:`/`7.7.7.7` conventions, and a NMS-report flag that marks a device "down/placeholder" so NMS colours it without treating it as a live host.

## 7e. Fleet-sharing of the changed files (checked 2026-07-04)

| File | Package | Shared? | Notes for the MR |
|---|---|---|---|
| `lib/report/report_dosto_neu.py` | nd-obn | **DOSTO-only** | One of 14 per-fleet report classes (ace, ccjpa_wd1/wd2, daisy_cybox, dani, dsb, luna, queensland, tgv, tgv2020, via, generic…). Each fleet selects its own via `report_module` config. Editing this cannot affect other fleets. The `normalise_devices`/`create_nms_device_nodes` behaviour is scoped by OVERRIDE in DostoNeuReport — base `report.py` untouched. |
| `backbone_validate.py` | nd-obn | **SHARED — every fleet's `obn validate`** | The side-file merge is GUARDED: `if cfg.get("report_module") != "DostoNeuReport": return devices`. Proven no-op for non-DOSTO (unit-tested: DOSTO merges the side-file, Ace/others skip it even when the file exists). Guard uses the same idiom as `backbone_discovery.py:24`. Reviewers should still scrutinise it as a shared-file change. |
| `pyproject.toml` (version) | nd-obn | metadata | own commit, per convention |
| `lib/report/device.py` (IF adding a real `status` field — clean route) | nd-obn | **SHARED base Device (all report types)** | additive field is low-risk but touches the shared base class; keep default so existing code is unaffected |

Rule: the fleet MR should keep every shared-file change **provably inert for non-DOSTO** (guard on `report_module`/`train_type`), not merely incidentally inert.

## 8. Scope / risk

- `report_dosto_neu.py` is shared-engine, CI-gated (653-test suite). This is a real algorithm change, not a hand-patch — must go through the normal MR + `make tag` release path, not a bench chroot.
- Needs an expected-topology source inside the engine. nv4/nv6 are known; fv5/fv6 chains must be confirmed before enabling there.
- Behaviour change is additive (DOWN rows appear where nothing appeared before) — low risk to healthy consists if fixture test 1 passes.
