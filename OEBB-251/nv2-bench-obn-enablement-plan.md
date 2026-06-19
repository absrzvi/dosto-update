# OEBB-251 2-coach bench — OBN + NMS enablement plan

**Date:** 2026-06-04
**Bench:** NMS train **2123 / `OEBB-Bench-2C`**, type `NV2 - Bench` (project 50 / rtl_project 50, obn project_id 51).
**CCU:** `developer@10.179.123.1` (box1-t123). SSH key `./openssh`.
**Goal:** make OBN produce a valid 2-coach consist so the NMS host skeleton rebuilds with coach-1 (`R1`) + coach-2 (`R2`) devices at real IPs — which in turn fixes the NMS consist diagram's coach-A header label (currently **"N/A"**).

---

## Root-cause chain (all verified this session, reverse-engineered from `main.d338fc0ee0b0573fffdc.bundle.js` + live CCU)

1. **NMS coach-A label = "N/A"** — the consist renderer (`Coach` ctor in `alarmObjects.js`) sets the label as
   `paintedCoachId !== "unknown" ? paintedCoachId : name`, then renders `this.name || 'N/A'`. `paintedCoachId` is attached **at draw time** from the matching live `train.deviceGroups["Coach N"]`; with no live "Coach 1" group it stays `undefined` → `undefined !== "unknown"` is true → label `undefined` → **"N/A"**. **`paintedCoachId` is NOT a config field** — the backend `DeviceLayout` model has only 7 props (`connections, position, type, name, id, coach, up`); POSTing it → `UnrecognizedPropertyException 500` (proven).
2. **All 8 NMS/Zabbix hosts are `50_2123_R2_*`** (coach 2), at placeholder IPs `7.7.7.7`/`0.0.0.0` — a stale skeleton from an older provisioning. The `R%d` token = coach number, parsed by the renderer at `split[2].replace("R","")`. No `R1` host → coach A unlabeled.
3. **OBN never produced a valid 2-coach consist**, so the skeleton was never rebuilt. Three causes:
   - **(a)** `report_dosto_neu.py` `number_coaches()` has **no `nv2` entry** in `ccu1_coach_map`/`max_coaches` (`{"nv4":2,"nv6":3,"fv5":2,"fv6":3}` / `{"nv4":4,...}`). With `train_type: nv4` it seeds `ccu1_coach=2, max_coach=4` and the BFS expects 4 coaches.
   - **(b)** OBN templates on the CCU are the **nv4 4-coach set** (`nv4-100-A1 … nv4-600-B3`, hostname `nv4-A1-v5-123`), and `backbone-discovery.yaml` says `train_type: nv4`.
   - **(c)** the bench's **CCU attachment is non-standard** vs the BFS's CCU→SW1(LAN1)/SW3(LAN2) assumption (see topology below).

> Sizing half of the NMS task is already DONE: NV2 train-type `gridSize` tightened 1250×850 → **1225×800**, pushed as version `activatedOn 1780564811287`.

---

## Declarative topology — SPEC (`ND-DEL-OBB-035-IPA-251_Bench.p.pdf`, the 2-coach bench schema, v1.6)

⚠️ Two PDFs in that folder: `..._Bench.pdf` = full **6-Teiler** (A-C-D-E-F-B, 6 pages) — NOT this bench. The authoritative one is **`..._Bench.p.pdf`** = 2-coach (3 pages: coach A = A1/A2/A3, coach B = B1/B2/B3). Use the `.p` file.

Inter-switch (FIS) trunks + AP + firewall ports, exactly as specified:

| Switch | e0-0 | e0-1 | e0-2 | e0-3 | e0-4 | e1-2 | e1-4 |
|---|---|---|---|---|---|---|---|
| **A1** | A3 | C1\* | Frontkupplung A1 | OBS D1 (trunk) | **AP A1** | — | — |
| **A2** | A3 | C3\* | — | — | **AP A2** | — | — |
| **A3** | A1 | A2 | Frontkupplung A2 | RDC D1 (200,202) | **AP A3** | **AP A4** | **Firewall** (trunk) |
| **B1** | B3 | F1\* | Frontkupplung B1 | — | **AP B1** | — | — |
| **B2** | B3 | F3\* | — | — | **AP B2** | — | — |
| **B3** | B1 | B2 | Frontkupplung B2 | — | **AP B3** | **AP B4** | — |

\* The spec lists A1/A2 e0-1 → coach C and B1/B2 e0-1 → coach F because this 2-coach bench schema was derived from the 6-Teiler (A is coach 1, B is coach 6). **C and F do not exist on this bench** — those e0-1 ports are the inter-coach uplinks that, on the physical 2-coach rig, are patched **A↔B directly**.

**Spec facts that drive OBN/NMS:**
- **Intra-coach hub = SW3** (A3: e0-0→A1, e0-1→A2; B3: e0-0→B1, e0-1→B2). ✓ matches OBN BFS hub-is-SW3.
- **Spec defines 4 APs/coach** (AP1/2/3 on SW1/2/3 **e0-4**, **AP4 on SW3 e1-2**) — but see PHYSICAL INVENTORY below: the bench has only **1 AP**.
- **CCU/OBS port = A1.e0-3.** The spec label "OBS D1" on A1.e0-3 IS the CCU/on-board-server attach on this bench (confirmed by engineer + live LLDP: CCU e0-3 → A1). So the CCU's primary FIS switch neighbour is **A1 (=SW1 of coach A) on port e0-3** → CCU is in **coach A**. (The secondary CCU lan1→A2.e0-1 link seen live is a management path, not the primary attach.)
- **Firewall:** A3.e1-4 trunk. **RDC D1:** A3.e0-3 (200,202).

### PHYSICAL INVENTORY (bench ground truth — overrides spec device counts)
- **6 switches:** A1/A2/A3 (coach A) + B1/B2/B3 (coach B).
- **1 AP only**, on **A1.e0-4**. All other spec AP ports (A2/A3/A4, B1–B4) are unpopulated — would sit at NMS `7.7.7.7` forever. ⇒ the NV2 train-type's 4-AP/coach should be trimmed to match (1 AP coach A, 0 AP coach B) for a clean diagram, OR accept ghost AP hosts.
- **CCU** on A1.e0-3. **Firewall** on A3.e1-4. **Inter-coach A↔B** patched A1.e0-1↔B1.e0-1.
- For the coach-label fix specifically, only **≥1 discovered device per coach mapped to the right coach number** is required — coach B has switches (B1/B2/B3) so it can map even with 0 APs.

## Live wiring (LLDP sweep, 2026-06-04) — how the bench is ACTUALLY patched

MAC↔host: `d0:62:60`=A1(.184), `d0:56:20`=A2(.181), `d0:56:00`=A3(.180), `d0:3c:00`=B1(.183), `d0:3c:20`=B2(.182), `d0:5b:a0`=B3(.178). All `2t-<pos>-v3-251`. CCU `box1-t123` MAC `7c:70:bc:70:d4:f4`.

```
COACH A                                   COACH B
  A3 ─e0-0─ A1     A3 ─e0-1─ A2             B3 ─e0-0─ B1     B3 ─e0-1─ B2
  A3 ─e1-4─ Firewall                        B2 ─e0-4─ B3 (second B2↔B3 link, UP 10G)
  A1 ─e0-4─ AP "AP A1" (DOWN)
  A1 ─e0-1─ B1   ◄── INTER-COACH A↔B (patched direct, spec=via C/F) ──►   B1 ─e0-1─ A1
  CCU lan1 ─ A2.e0-1 ;  CCU e0-3 ─ A1
```

**Live-vs-spec deltas to resolve in Stage 1:**
- **CCU = A1.e0-3** (OBS port) → CCU is in **coach A**, primary neighbour SW1(A1). BFS standard seed expects CCU→SW1 on LAN1 + CCU→SW3 on LAN2; here it's CCU→SW1 on **e0-3**. nv2 needs a CCU-seed rule: `BOX neighbour on OBS/e0-3 → that SW = device 1, same coach (=ccu coach)`.
- Inter-coach A↔B is on **A1.e0-1 ↔ B1.e0-1** (SW1↔SW1 on e0-1). Spec routes A1.e0-1→C, B1.e0-1→F; bench shortcuts them. OBN BFS SW1↔SW1-next-coach rule keys on **e0-0**, not e0-1 → needs an nv2 hop rule on e0-1.
- **Only 1 AP on the whole bench (A1.e0-4).** Spec's 4-AP/coach is aspirational; trim NV2 train-type to 1 AP (coach A) + 0 AP (coach B), or accept ghost `7.7.7.7` AP hosts.

---

## Plan (staged) — capture only; execute later with bench access

### Stage 1 — Finalise the nv2 topology contract  ✅ DECIDED
- **Coach numbering: A = 1, B = 2. CCU is in coach A ⇒ `ccu1_coach = 1`, `max_coach = 2`.** (Engineer decision 2026-06-04.)
- CCU attaches at **A1.e0-3** (OBS port) → CCU's neighbour A1 = coach-1 SW1.
- Inter-coach A↔B at **A1.e0-1 ↔ B1.e0-1** (coach-1 SW1 → coach-2 SW1, on e0-1).
- 1 physical AP at A1.e0-4 (coach-1 SW1's AP). Trim NV2 train-type to 1 AP coach A + 0 AP coach B (or accept ghosts).
- ⚠️ Note: `ccu1_coach=1` means the CCU is in the FIRST coach, not a middle coach — the existing BFS hop rules assume CCU sits mid-consist (nv4=2 of 4, nv6=3 of 6). For a 2-coach with CCU in coach 1, propagation is purely **coach1 → coach2 (+1)**; no −1 direction. The nv2 rules only need: seed coach1 at the CCU's switch, number coach1's other switches via the hub rules, then one **SW1.coach1.e0-1 → SW1.coach2** hop (+1). Simpler than the general case.

**CRITICAL — CCU uplink is a BONDED pair; seed keys on slave-interface name (code-verified `walker.py:92` RD-8261):**
`lan0` + `lan1` are slaves of **`bond0`** (mode load-balancing XOR, shared MAC `00:21:21:21:00:01`; backbone + all VLANs ride on bond0). OBN scans `ccu_interfaces:[lan0,lan1]` and LLDP-walks each **physical slave by name**, mapping `ccu_port = int(iface[3:])+1` ⇒ **lan0→LAN1(1), lan1→LAN2(2)**. Existing BOX rule: LAN1→device 1, LAN2→device 3 (same coach). The **switch-side port (e0-2 OBS/coupler/e0-3) is irrelevant to seeding** — only which CCU slave the cable lands on.

Standard pattern (verified box1-t1, box1-t32): both slaves UP; **lan0→SW1, lan1→SW3** of the CCU's coach (those trains: D1/D3 on e0-2). ⇒ LAN1→dev1, LAN2→dev3. The bench must match this slave→switch assignment.

Live bench reality (`/proc/net/bonding/bond0`, `lldpctl`):
- **lan0 is DOWN (NO-CARRIER)** — no LLDP neighbour. (Cable absent/dead, not a config choice.)
- **lan1 → A2.e0-1** (only live CCU link). `lan1`→LAN2 ⇒ existing rule would set **A2 = device 3** — WRONG (A2 is the SW2-leaf; A3 is the real dev-3 hub).

⇒ **Re-cabling target (engineer approved): CCU lan0 → A1 (coach-1 SW1, on its OBS/uplink port), CCU lan1 → A3 (coach-1 SW3).** Both bond slaves UP. Then existing LAN1/LAN2 rule seeds A1=dev1, A3=dev3 with NO special seed code. (Switch-side port can be e0-2 or e0-3 — OBN doesn't care; pick whichever the bench patch uses, just ensure lan0↔A1 and lan1↔A3.) NOTE: on an end-coach (A), e0-2 is the Frontkupplung (coupler) so the CCU likely uses the OBS trunk e0-3 — fine, immaterial to OBN.

**BFS trace with `ccu1_coach=1, max_coach=2` (ASSUMING corrected CCU cabling: lan0→A1, lan1→A3):**
1. BOX seeded coach 1. CCU **lan0 → A1** ⇒ port=LAN1 ⇒ existing rule sets A1 = dev1, coach 1. ✓ (CCU **lan1 → A3** ⇒ LAN2 ⇒ A3 = dev3, coach 1 ✓ — IF re-cabled so lan1 reaches A3 not A2.) *No new seed rule needed if cabling is corrected.*
2. A1 (dev1, coach1): e0-0 → A3. Existing rule "SW1 of first/last coach → SW3 same coach on e0-0" (`coach in [1,max_coach]`, here 1∈[1,2]) ⇒ A3 = dev3, coach1. ✓
3. A3 (dev3, coach1): e0-1 → A2. Existing "SW3 → SW2 same coach on e0-1" ⇒ A2 = dev2, coach1. ✓ A3.e0-4→AP, A3.e1-2→AP4 (none present). A1.e0-4 → AP dev1 coach1. ✓
4. A1 (dev1, coach1): e0-1 → B1. Need rule: SW1 of coach1 (the ccu coach, which is also the first coach) on **e0-1** → SW1 of next coach (+1). ⇒ B1 = dev1, coach2. *(New nv2 hop rule — existing inter-coach SW1→SW1 rule keys on e0-0; bench uses e0-1.)*
5. B1 (dev1, coach2): e0-0 → B3 ⇒ "SW1 of last coach → SW3 same coach on e0-0" (2==max_coach) ⇒ B3 = dev3, coach2. ✓
6. B3 (dev3, coach2): e0-1 → B2 ⇒ SW3→SW2 same coach ⇒ B2 = dev2, coach2. ✓

⇒ **What nv2 needs:**
1. **Dict entries:** `ccu1_coach_map["nv2"]=1`, `max_coaches["nv2"]=2`. (code)
2. **CCU cabling corrected:** lan0→A1 (coach-1 SW1), lan1→A3 (coach-1 SW3) — so the existing BOX→SW LAN1/LAN2 rule seeds A1=dev1, A3=dev3 correctly. (physical) — **today lan1→A2 mis-seeds; lan0 link down.**
3. **One new inter-coach hop rule:** coach-1 SW1 on **e0-1** → next-coach SW1 (+1), to cross A1.e0-1→B1. *(Existing SW1→SW1-next-coach rule keys on e0-0; bench A↔B is on e0-1.)* Alternatively re-patch A↔B onto e0-0 and reuse the existing rule — but e0-0 is already A1↔A3 intra-coach, so the e0-1 hop rule is cleaner.
4. `train_type: nv2` in backbone-discovery.yaml + nv2 templates (Stage 3).

Net: **2 code lines (dict) + 1 new hop rule + CCU re-cable**. Re-cabling the CCU (item 2) is unavoidable regardless — the current lan1→A2 seed is wrong for any coach scheme.

### ⚠️ ARCHITECTURE FORK discovered 2026-06-04 — two coach-numbering engines

OBN has **two** report modules that do coach numbering:
- **`DostoNeuReport`** (`report_dosto_neu.py`) — hardcoded BFS (the `ccu1_coach_map`/rules code). **Currently active** (`report_module: DostoNeuReport`). Does NOT read `topology.yaml`.
- **`GenericReport`** (`report_generic.py`) — declarative engine that reads **`topology.yaml`**: `self.topology[train_type][coach][from_type][port][to_type]` → `{coach_inc, device_val}`. `topology.yaml` already defines `dostoneu6` + `dostoneu4` maps (assembled from `wagon_a100`…`wagon_b600` anchors) but **no `dostoneu2`**. This is the modern path R&D is migrating to.

`topology.yaml` is currently INERT on this CCU (active module is the hardcoded one). So nv2 can be enabled two ways:

**Option A — patch `report_dosto_neu.py`** (DRAFTED: `scripts/fix_obn_nv2_report_dosto_neu.py`). Keeps `DostoNeuReport`. 3 edits (nv2 dict, e0-1 hop rule, bug-10 guard). Matches what runs today + the bug-1–10 hand-patch convention. Con: more Python hand-patch R&D debt.

**Option B — switch to `GenericReport` + add `dostoneu2` to `topology.yaml`.** Set `report_module: GenericReport`, `train_type: dostoneu2`; add a 2-coach map reusing `*wagon_a100` (coach 1) + `*wagon_b600` (coach 2) anchors + set `box1_coach_number: 1`. PURE DATA, no Python edits — the intended modern path. Con: bigger behavioral switch on the bench; must confirm GenericReport is production-ready and that wagon_a100/b600 port rules match the bench's actual A↔B-on-e0-1 wiring (they encode the 6-car's A→C / B→F e0-1 hops, so a 2-coach `dostoneu2` map needs its OWN wagon rules for the direct A↔B link, not the stock anchors).

**Engineer decision needed before Stage 2 executes.** (Both still require the CCU re-cable + nv2 templates.)

#### GenericReport readiness assessment (2026-06-04)
- `report_generic.py` is a **complete, exported class** (186 lines: number_coaches, find_type, fixed_consist_algo, remap_device_type_aliases, normalise_devices, get_current_ccu_box_and_coach). Not a stub.
- It's **newer/cleaner** than DostoNeuReport: RD12057 multi-CCU aware (seeds by matching CCU **serial** + `topology.box1_coach_number`, not just first BOX), and it already has the **bug-10 guard built in** (`if to_device and to_device.coach_number: queue.appendleft`).
- **BUT deployed on ZERO trains.** Surveyed box1-t1 (nv6), box1-t32 (nv6), box1-t123 (bench): **all three `report_module: DostoNeuReport`**. None has `dostoneu2`. `topology.yaml` ships everywhere but is **inert** (no train selects GenericReport).
- `topology.yaml` has no `device_type_aliases` key (GenericReport treats it as optional — `if "device_type_aliases" in self.topology`).
- Seeding difference: GenericReport seeds the CCU's coach from `get_current_ccu_box_and_coach()` (serial-matched) + topology, NOT from `ccu1_coach_map`. A `dostoneu2` map would set `box1_coach_number: 1`.

**Verdict / recommendation: Option A (patch DostoNeuReport) for the bench NOW.** Rationale: (1) it's the engine every train actually runs, so the bench stays consistent with the fleet and with how OBN bugs 1–10 were patched; (2) switching the bench to an undeployed module (GenericReport) makes the bench a one-off that validates nothing about the real fleet path and risks untested discovery behavior; (3) Option A is already drafted + locally validated. Treat **Option B (GenericReport + dostoneu2) as the R&D-ticket recommendation** — it's the right long-term home for nv2 (pure-data, no hand-patch), to be done when R&D migrates the fleet to GenericReport. File both: the bench hand-patch AND a "add dostoneu2 to topology.yaml + adopt GenericReport" ticket.

### Stage 2 — Patch `report_dosto_neu.py` for nv2 (core code fix) [Option A]
- Add `"nv2": 2` to `ccu1_coach_map` and `"nv2": 2` to `max_coaches` (CCU in coach 2, 2 coaches total).
- Reconcile the CCU-seed + inter-coach hop rules with the real cabling (CCU→A2/A1; A↔B on e0-1). Two options:
  - **(i) re-cable bench** to standard (CCU→SW1/SW3 of its coach; A↔B on e0-0 SW1↔SW1) → keeps report module changes to just the dict entries. *Cleaner long-term.*
  - **(ii) add nv2-specific BFS rules** matching the bench wiring → no physical work but bench-only tech debt.
- Persist via NDSU chroot (same path as OBN bugs 1–10; `/var/tmp` bind-mount). File an R&D GitLab ticket (joins the existing OBN-bug backlog — see `project_rd_gitlab_tickets_todo`).

### Stage 3 — nv2 OBN templates
- Set `train_type: nv2` in `/etc/obn/backbone-discovery.yaml`.
- Create `nv2-*` discovery/report templates for the 6 switches (A1/A2/A3/B1/B2/B3) with the `2t-`/v3 hostname scheme matching the live switches. Base on existing `OEBB-251/2t-bench-*-v4.cfg` (switch configs) + nv4 template structure (discovery side). Strip ports for devices the bench lacks.

### Stage 4 — Discover → report → validate
- `sudo obn discover && sudo obn report` (report writes `discovery.prev.json` — required before `validate`/`update`; see `project_obn_workflow_order`). Confirm `discovery.json` shows 6 switches split across coach 1 and coach 2, 1 AP coach A.

### Stage 5 — NMS skeleton rebuild + verify
- OBN report feeds the NMS → skeleton regenerates with `R1`+`R2` hosts at real IPs → hard-refresh NMS → coach A shows "A". Sizing already correct.

---

## NMS API quick-reference (validated)
- Base `https://nms-obb.nomadrail.com/nms`; auth `POST /rest/user/authenticate {username,password}` → `.token` in `Auth-Token` header. Curl **from the CCU**.
- Train-type GET+POST only (PUT/PATCH/DELETE=405). POST=Mongo insert: drop `_id`, set `activatedOn` > current max to activate. Strict parser (27 top-level fields; unknown field → 500).
- GET active: `GET /rest/configurations/50/traintypes/NV2%20-%20Bench` returns ALL versions; highest `activatedOn` wins. **Always start edits from the live highest-activatedOn version, not the reference file** (it drifts).
- Live device→coach data: `GET /rest/monitoring/trains` → train `2123` → `trainStructure.devices[].coachId` + hostname `R%d`.
- Full method writeup: `troubleshooting-runbook.md` → "NMS Train-Type Config" (incl. new "Coach header label and canvas sizing" subsection).
