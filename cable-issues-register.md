# DOSTO Fleet — Cable Issues Register

Consolidated log of physical cabling and port-assignment faults found on DOSTO trainsets during Nomad Digital L2 health checks. Add a new row whenever LLDP topology verification or per-port checks reveal a fault that requires Stadler to re-cable, re-patch, or install a missing cable.

This register uses **generic switch IDs only** (A1, A2, A3, B1…B3, C1…C3, D1…D3, E1…E3, F1…F3, G1…G3) and **port labels** (e0-0, e0-1, e0-2, …) — no IPs, no live hostnames, no MACs. The expected topology is whatever the IP-allocation plan / OBN templates define for that consist type.

## Conventions

- **Consist type** — 4-car (A/G/E/B) or 6-car (A/B/C/D/E/F).
- **Status** — `OPEN` (Stadler action pending) · `RESOLVED` (re-verified clean) · `WONTFIX` (accepted as-is, e.g. AP physically not installed).
- **Fault type** —
  - `cable swap` — both cables present but plugged into wrong ports on the same switch
  - `wrong neighbour` — cable goes to the wrong far-end switch
  - `missing trunk` — no LLDP either end, cable absent or unplugged
  - `AP not connected` — AP trunk port admin-enabled but no link / no PoE draw
  - `end-device not connected` — access port admin-enabled for an end device (FIS display, energy meter, etc.) but link never establishes (no negotiation, 0 RX, 0 errors), and a port bounce does not recover it; switch side proven healthy via an UP sibling port. Fault is the cable or the device end (Stadler-side)
  - `wrong far-end port` — cable lands on the correct switch but wrong port number
  - `PoE PSE fault` — switch PoE power-sourcing subsystem fails to initialise (0 W available, survives reboot); hardware repair/replacement
  - `PoE port fault` — a single PoE port reports a PSE error state (e.g. `E(1e)`) and delivers 0 W while the rest of the PSE is healthy; the powered device stays dark and link/RX never establishes; survives a switch reboot. Fault is the cable, connector, or powered device on that port (Stadler-side), or the port's PoE PHY

## Open issues — at a glance

| #  | Trainset  | Switch / Port      | Fault type        | Status   |
|----|-----------|--------------------|-------------------|----------|
| 1  | 4734-101  | E2 ↔ B1            | wrong neighbour   | 🔴 OPEN (⚠️ not in Zabbix) |
| 2  | 4736-108  | C3 e0-0 / e0-1     | cable swap        | ✅ RESOLVED |
| 3  | 4736-108  | D1 ↔ E2            | missing trunk     | ✅ RESOLVED |
| 4  | 4736-109  | B3 e0-4            | AP not connected  | 🔴 OPEN |
| 5  | 4736-104  | D3 e1-2            | physical-layer    | 🔴 OPEN |
| 6  | 4736-120  | C2 e0-4            | AP not connected  | ✅ RESOLVED |
| 7  | 4736-108  | A2.e0-1 ↔ A3.e0-1  | physical-layer    | 🔴 OPEN (⚠️ no Zabbix trigger) |
| 8  | 4736-115  | B3 e0-4 (Coach6)   | AP not connected  | 🔴 OPEN |
| 9  | 4736-118  | E1 (whole switch)  | PoE PSE fault     | 🟡 MONITORING (PoE healthy 2026-06-20) |
| 10 | 4734-109  | A1 e0-0/e0-2 ↔ A3  | cable swap (coupler) | ✅ RESOLVED (A1 switch replaced + re-cabled, 2026-06-17) |
| 11 | 4736-114  | 14× e2-* (FIS displays + 1 energy meter, all coaches) | end-device not connected | 🔴 OPEN |
| 12 | 4736-120  | A2 e1-9 (redundant Sprechstelle) | PoE port fault | 🔴 OPEN |
| 13 | 4736-109  | E2 (whole switch)  | cold bypass (power/health, NOT cabling) | 🔴 OPEN (⚠️ not in Zabbix) |
| 14 | 4734-125  | E1 e0-4 (Coach E AP) | physical-layer (RX CRC storm) | 🔴 OPEN |

---

### #1 — 4734-101 (4-car) — E2 ↔ B1 wrong neighbour

**What we see:** E2.e0-0 reaches B1 (and B1.e0-1 reaches E2).
**Plan:** E2.e0-0 ↔ E3 (intra-E coach), and B1.e0-1 ↔ E1 (inter-coach E↔B).
**Diagnosis:** the intra-E-coach trunk and the E↔B inter-coach trunk are cross-wired.

**Required action:** re-patch the E-coach end so E2.e0-0 lands on E3, and the inter-coach E↔B trunk lands on E1.e0-0 ↔ B1.e0-1.

**Zabbix coverage (2026-06-20):** ⚠️ **monitoring gap** — 4734-101 (CCU `10.179.4.1`, would be group `50_6004`) is **not provisioned in Zabbix**; no host group exists. This fault cannot be corroborated or alarmed from the NMS. "No Zabbix alarm" here does NOT mean "no fault." Provisioning 6004 is a separate NMS task.

**Status:** 🔴 OPEN

---

### #2 — 4736-108 (6-car) — C3 cable swap

**What we see:** C3.e0-0 → C2 and C3.e0-1 → A2.
**Plan:** C3.e0-0 ↔ A2 and C3.e0-1 ↔ C2.
**Diagnosis:** the two trunk cables on C3 are swapped.

**Required action:** swap the two trunk cables on C3. After swap, `show lldp neighbours` on C3 should show e0-0=A2, e0-1=C2.

**Status:** ✅ RESOLVED (2026-05-29 re-verification: C3.e0-0=A2 ✓, C3.e0-1=C2 ✓)

---

### #3 — 4736-108 (6-car) — D1 ↔ E2 missing trunk

**What we see:** no LLDP peer on either end. Both switches reachable on management VLAN; only this inter-coach link is dark.
**Plan:** D1.e0-1 ↔ E2.e0-1 inter-coach trunk.

**Required action:** locate and reconnect the inter-coach trunk cable between D1 e0-1 and E2 e0-1. If absent, install.

**Status:** ✅ RESOLVED (2026-05-29 re-verification: D1.e0-1=E2 ✓ AND E2.e0-1=D1 ✓ — trunk present and forwarding)

---

### #4 — 4736-109 (6-car) — B3 e0-4 AP not connected

**What we see:** port admin-enabled, link DOWN, PoE drawing 0 W, never seen traffic.
**Plan:** AP attached to B3 e0-4 (AP trunk port).

**Required action:** verify whether an AP is physically installed at B3 position; if yes, connect the patch cable to B3 e0-4.

**Status:** 🔴 OPEN

---

### #5 — 4736-104 (6-car) — D3 e1-2 physical-layer fault

**What we see:** PoE active (~2.5W class-3, device powered) but Ethernet data link never negotiates. Line protocol DOWN, Speed/Duplex stuck at Auto/Auto, no MAC ever learned in switch table, all error counters zero (RX/TX/CRC/carrier-false all 0).

**Diagnosis:** power pairs intact, data pairs failing.

**Confirmed via:** `no configure interface e1-2 enable` / `configure interface e1-2 enable` cycle on 2026-05-09. 120s post-cycle, no link-state transition observed. Discovered during topology validation on box1-t10 (10.179.10.1). 23/24 APs visible.

**Required action — in order, simplest first:**
1. Replace patch cable between AP D4 and switch D3 e1-2 — symptoms suggest damaged data pairs while power pairs are working.
2. If cable replacement doesn't restore link, swap the AP with a known-good unit.
3. If AP swap doesn't help, investigate switch-side of D3 e1-2 (very unlikely — port admin/PoE both functional).

**2026-05-22 re-verification:** `no configure interface e1-2 enable` + `configure interface e1-2 enable` port bounce performed. Result unchanged — interface enabled, line protocol still DOWN, Speed/Duplex Auto/Auto (no negotiation), RX/TX packets 0, all error counters 0. Physical-layer fault confirmed. Port cycling cannot recover this — Stadler cable replacement required.

**Status:** 🔴 OPEN

---

### #6 — 4736-120 (6-car) — C2 e0-4 AP not connected (Coach2 AP3)

**What we see:** Coach 2 AP3 absent from DHCP leases entirely as of 2026-05-22 live check. Switch C2 e0-4 (AP trunk port) — link state and PoE status not yet verified (CCU fping non-responsive at time of check; state inferred from absence in `obn validate` and `dhcp-lease-list`).
**Plan:** AP3 connected to C2 e0-4 (AP trunk port, 6-car nv6 template).
**Context:** previously 24/24 APs were visible on 2026-05-19 — this AP was present then. Absence is new as of 2026-05-22. E3 coach power restoration work by Stadler may have disturbed cabling elsewhere.

**Required action:**
1. Check C2 e0-4 link state and PoE draw via `show interface e0-4 details` on C2 switch.
2. If link DOWN / PoE 0W: verify AP is physically installed and patch cable is connected.
3. If link UP but AP not in DHCP: AP may be in factory config — check via `show lldp neighbours` on C2 e0-4.

**2026-05-22 resolution:** `no configure interface e0-4 enable` + `configure interface e0-4 enable` port bounce performed. Link came up cleanly — 1000 Mb/s Full, line protocol UP, active RX/TX traffic, zero errors. AP recovered after port bounce; likely a transient PoE or link negotiation stall after the Stadler E3 coach work. No physical fault.

**Status:** ✅ RESOLVED — 2026-05-22, port bounce restored link, AP active

---

### #7 — 4736-108 (6-car) — A2.e0-1 ↔ A3.e0-1 physical-layer fault (intra-A coach trunk)

**What we see:** the intra-A-coach trunk between switches A2 and A3 accumulates RX errors continuously at idle, even after a fresh switch reboot.

| Endpoint | RX errors (16 min uptime, idle) | Rate |
|---|---|---|
| A2.e0-1 | 10,382 | ≈ 158 / minute |
| A3.e0-1 | 10,219 | ≈ 105 / minute |

All other RX error categories — CRC, runts, giants, frag, jabber, carrier-false — are zero on both ports. This is NOT a CRC fault; it is frame-level errors that the switch ASIC counts under "RX errors" but that the FCS check accepts (alignment / low-level PHY anomaly class).

**Diagnosis:** SFP module, connector seating, or cable electrical-characteristics-under-load fault. Stadler Fluke continuity testing of this trunk on 2026-05-28 returned "Verbindung OK" — confirming the cable is electrically continuous at low data rates. The failure manifests only under sustained traffic, which is consistent with one of: degraded SFP transmit/receive optics; loose or oxidised connector contact; cable specification marginal for the 10G link rate.

**Impact:** under doppeltraktion load (4736-108 paired with 4736-117 on 2026-05-28 12:30 onwards), this trunk's elevated error rate dropped RSTP BPDU frames repeatedly, triggering continuous root-bridge re-elections. Each re-election created a 10-30 s window of MAC-table flush and unknown-unicast broadcast flooding — which manifested to ÖBB as the FIS-down / no-video-stream / "network dies and revives" cycle. The ~1.17 billion cumulative broadcast count per switch observed on 2026-05-29 morning is the forensic record of this cycle.

**Required action — in order, simplest first:**
1. Re-seat the SFP modules at BOTH ends of the A2 ↔ A3 trunk (A2.e0-1 and A3.e0-1). Intermittent contact often resolves on re-seat.
2. Swap the SFP modules at both ends with known-good units. Compare RX error rate before/after.
3. Replace the cable end-to-end with a new pre-tested cable.
4. Acceptance criterion: zero RX errors on A2.e0-1 and A3.e0-1 over a 10-minute idle sample. Nomad Digital can verify remotely on request.

**Secondary trunks to address with the same procedure (lower priority, post-A↔A fix):**
- C2.e0-0 ↔ C3 (5,141 RX errors at idle, accumulating slowly).
- C3.e0-0 ↔ A2 (6,439 RX errors at idle, accumulating slowly).
- F2.e0-0 (had 30,864 RX errors on 2026-05-28, zero today at idle — load-dependent; re-verify under load after A↔A fix).

**Report:** [reports/customer/OBB_Fzg136_145_4736-108_117_Post_Storm_Verification_v1.1.docx](reports/customer/OBB_Fzg136_145_4736-108_117_Post_Storm_Verification_v1.1.docx)

**Zabbix coverage (2026-06-20):** ⚠️ **monitoring gap by design** — this fault is an *error-accumulating trunk that stays link-UP* (RX errors at idle), not a down port. Zabbix 6008 has port-down and SNMP-unreachable triggers but **no RX-error-rate trigger**, so this fault is invisible in the NMS (confirmed: no corresponding alarm on 6008). Catching trunk degradation like this would need an ifInErrors-rate item/trigger added to the switch template. Until then, "no Zabbix alarm" does NOT mean the trunk is clean.

**Status:** 🔴 OPEN

---

### #8 — 4736-115 (6-car, Fzg 143) — B3 e0-4 (Coach6) AP4 not connected

**What we see:** Coach6 AP4 is physically absent from the consist. During the 2026-06-02 commissioning run, `obn validate` listed an AP at `192.168.1.20` (factory-default address, stale discovery data), but LLDP on all three Coach6 switches shows only AP1/AP2/AP3 on their e0-4 ports — no AP4 neighbour anywhere:

| Switch | e0-4 LLDP neighbour |
|---|---|
| B1 (10.179.18.178) | AP1 (00:14:5a:04:8c:52 → .235) |
| B2 (10.179.18.180) | AP2 (00:14:5a:04:79:c2 → .231) |
| B3 (10.179.18.188) | AP3 (00:14:5a:04:8b:f5 → .232) |

ARP for 192.168.1.20 returns INCOMPLETE even after adding a temporary 192.168.1.1/24 address to vlan100. The AP is not on DHCP and not LLDP-visible — it is physically disconnected, unpowered, or not installed.

**Expected:** B3 port e0-4 (or the Coach6 AP4 position) hosts AP4 per nv6 topology.

**Required action:** Stadler to verify physical installation and power of Coach6 AP4, and confirm its patch cable to the Coach6 switch e0-4 port. Once the AP appears on vlan100 (DHCP lease), Nomad can complete its config + firmware push remotely. The other 23 APs were commissioned 2026-06-02.

**Status:** 🔴 OPEN

---

### #9 — 4736-118 (6-car, Fzg 146) — E1 PoE PSE subsystem fault (whole switch)

**What we see:** Switch E1's PoE power-sourcing subsystem fails to come up. `show poe` reports every port armed (`mode on`, status `E(11)` detecting) but delivering 0.00 W, with **Total 0 W / Available 0 W against a 202 W max** — i.e. no power budget ever comes online. A healthy sibling shows ~20–32 W drawn and ~170–181 W available:

| Switch | Total draw | Available | Max |
|---|---|---|---|
| **E1** | **0 W** | **0 W** | 202 W |
| E2 | 32 W | 170 W | 202 W |
| E3 | 21 W | 181 W | 202 W |
| F1 | 31 W | 171 W | 202 W |
| A1 | 27 W | 174 W | 202 W |

`show log` contains only `KMdev: Initializing PoE subsystem` with **no completion/power-good line**, on every boot. The switch's SNMP agent is also unresponsive on all communities (the management plane is partially hung), while the L2 data plane is fully healthy (e0-0/e0-1 inter-coach trunks up at 10G, access links up). A controlled reboot via `sysadmin reboot` was performed 2026-06-02 — the PSE init hangs identically on the fresh boot, confirming this is **not a transient software hang but a hardware PoE fault.**

**Impact:** E1 e0-4 is the PoE feed for Coach E AP1 (`AP1m`, per nv6 topology). This is very likely why that AP has been recorded as "absent" — it may be physically present but dark because E1 cannot source PoE. Recharacterises the standing "Coach E AP1m absent (Stadler)" note from a *missing AP* to a *PoE-starved AP*.

**Expected:** E1 PoE subsystem initialises and presents the full 202 W budget; e0-4 sources power to Coach E AP1.

**Required action:** Stadler to repair or replace the E1 consist switch (PoE PSE board / power-supply fault). No CCU-side action can restore a dead PSE. After replacement, re-verify `show poe` shows ~202 W available and confirm Coach E AP1 appears on vlan100 DHCP.

**2026-06-15 re-verification (AR):** Fault confirmed unchanged and root cause narrowed. Exhausted all CCU-side recovery:
1. **Port bounce** of e0-4 (link `no enable`/`enable` + PoE `mode off`/`on`) — no effect, still `E(11)` / 0 W.
2. **SNMP reboot OID** (`.1.3.6.1.4.1.8072.1.3.2.2.1.7.6...` = `3`, the OBN `vdsrail.py reboot()` path) returned rc 0 / `INTEGER: 3` but the switch **did not reboot** (uptime kept climbing) — the SNMP-commanded reboot is silently ignored.
3. **`sysadmin reboot` (CLI)** *did* reboot the switch (uptime reset to 0). On the fresh boot, `show poe` **immediately** shows e0-4 + all 17 ports at `E(11)` / 0 W, Total 0 W / Available 0 W; boot log shows `KMdev: Initializing PoE subsystem` then **no power-good and no fault/short/over-current trap** — PSE comes up dead-silent.

Root cause narrowed to a **degraded `KMkon` device-management module**: `show log persistent` carries `The "KMkon" module has been restarted (1)`. `KMkon` owns *both* the PoE PSE control and the SNMP reboot action — explaining why PoE delivers 0 W **and** why the SNMP reboot OID is ignored (CLI reboot uses a different path and still works). This is a board-level fault that survives a full reboot. Confirms Stadler hardware repair/replace is the only fix; remote recovery is not possible.

**2026-06-20 re-verification (AR) — fault NOT currently present:** Live check of E1 (`10.179.21.180`, same chassis — MAC `a0:59:3a:d0:4b:40`, serial `240602`, **not replaced**) shows **PoE fully healthy**: `show poe` Total **33 W** / Available 168 W / Max 202 W, with `e0-4` (AP) at 6.7 W and the e1-* camera ports all powered (2.7–3.9 W each). E1 is reachable via SNMP (`obn validate` returns it ✓ on `nv6-E1-v8-146`), and the persistent log shows no recent `KMkon` restart. The Zabbix 6021 access-point "cannot be pinged" alarms also cleared (resolved 2026-06-20 10:39Z), consistent with E1 sourcing PoE again. **Caveat:** the original fault was intermittent and reboot-surviving, so this is recorded as "not currently present" rather than confirmed-fixed — the PSE may have come up clean on the current boot (uptime ~20 h). Monitor across further power-cycles before closing. Stadler hardware replacement may no longer be required.

**Status:** 🟡 MONITORING — PoE healthy on 2026-06-20 live check; was 🔴 OPEN. Confirm stable across power-cycles before resolving.

---

### #10 — 4734-109 (4-car, Fzg 9) — A1 ↔ A3 coupler cable swap (UPDATED 2026-06-08)

**Superseded diagnosis (2026-06-08 AM):** previously logged as "A1 switch absent / missing trunk." That was incomplete. A1 is **present, powered, and healthy** — it was simply unreachable on vlan100. Deeper diagnosis (below) shows the real fault is a **physical cable swap at the A1↔A3 coupling**, which also explains the train_id-15 contamination.

**What we see (live LLDP, 2026-06-08):**

A1 (`nv4-A1-v8-015`, MAC `…d0:8f:a0`) is alive and was reached in-band via the **native/untagged VLAN 1** path (SSH `admin`/`Nom@dCome1n` + SNMP both work from the CCU after adding a temporary `192.168.1.2/24` to the CCU's untagged `bond0`). It reports Normal Mode, ~49 °C, sensible uptime. The misimage is cosmetic (train_id 15 rendered into hostname + DHCP client-addresses).

A1's live inter-switch neighbours vs. the nv4 plan:

| A1 port | Plan (nv4-topology) | Live neighbour | |
|---|---|---|---|
| e0-0 | → A3 (intra-A, carries vlan100, `prune allow 1-1000`) | **Fzg-15's A3** (`nv4-A3-v8-015`, …d0:93:80) | ❌ wrong train |
| e0-1 | → G1 (inter-coach A↔G, carries vlan100) | **Fzg-15's G1** (`nv4-G1-v8-015`, …d0:6e:00) | ❌ wrong train |
| e0-2 | → front-coupler (to coupled neighbour train; `prune allow 5,15`, **no vlan100**) | **this train's A3** (`nv4-A3-v8-009`, …d0:67:60) | ❌ should be the coupler |

This train's A3 confirms the swap from its side: **A3 e0-2** (its front-coupler port, no vlan100) faces **this train's A1**, while A3 e0-0/e0-1 correctly face G1/A2.

**Mechanism (important — vlan100 is NOT bridged across the coupler):** the coupler ports (e0-2, both sides) carry only VLAN 5 (cctv-net) + VLAN 15 (multitraction-transit) by design — vlan100 is correctly excluded. The contamination is the opposite: A1's **regular vlan100 trunk ports e0-0/e0-1** (`prune allow 1-1000`) are physically cabled into **Fzg-15's** A3/G1. So A1's vlan100 DHCP DISCOVER egresses e0-0 into Fzg-15's vlan100 fabric, Fzg-15's CCU answers, and A1 leases `10.179.61.183` — a real lease, from the wrong train. Meanwhile A1↔this-train-A3 are joined coupler-to-coupler (e0-2↔e0-2), which carries no vlan100 → only the untagged native VLAN reaches this train (hence native-VLAN-1 management works but A1 never leases on this CCU's vlan100). It is a physical cross-wire of the three A-head cables, not a VLAN-config error.

**Diagnosis:** A1 and A3 are cabled **front-coupler-port to front-coupler-port (A1 e0-2 ↔ A3 e0-2)**. Those ports carry only VLANs 5 + 15 — **not** the management VLAN 100. A1's *proper* intra-consist trunk ports (e0-0/e0-1, which carry vlan100) are instead plugged into the **physically-coupled Fzg-15 consist**. Net effect: A1's vlan100 has no bridged path to this train's CCU, so A1 cannot lease/route on vlan100 and **no remote config-push transport works** — TFTP, HTTP, and SCP all fail because A1 sources every config-fetch from its (unreachable) vlan100 interface (`10.179.61.183`, on the dead train-15 subnet). Only untagged VLAN 1 crosses the mis-cabled coupler, which is why management works but a push does not. The train_id-15 imaging is a *symptom*: OBN auto-topology on A1 saw Fzg-15's neighbours on e0-0/e0-1 and rendered A1 as a train-15 switch.

**Full A-head map — as-designed vs as-cabled (live LLDP 2026-06-08; Fzg-9 + Fzg-15 are physically coupled at the A-end).** Identity key: `…d0:8f:a0`=Fzg9-A1, `…d0:67:60`=Fzg9-A3, `…d0:43:a0`=Fzg9-G1, `…d0:7e:a0`=Fzg9-A2, `…d0:3c:c0`=Fzg9-E2, `…d0:93:80`=**Fzg15-A3**, `…d0:6e:00`=**Fzg15-G1**.

| Port | Should reach (nv4-topology) | Actually reaches (live) | |
|---|---|---|---|
| A1 e0-0 | Fzg9 A3 (intra-A, vlan100) | **Fzg15-A3** | ❌ wrong train |
| A1 e0-1 | Fzg9 G1 (inter 1↔2, vlan100) | **Fzg15-G1** | ❌ wrong train |
| A1 e0-2 | Frontkupplung → next train (VLAN 5,15) | Fzg9 A3 | ❌ should be coupler |
| A3 e0-0 | Fzg9 A1 (intra-A) | Fzg9 G1 | ❌ |
| A3 e0-1 | Fzg9 A2 | Fzg9 A2 | ✅ |
| A3 e0-2 | Frontkupplung → next train | Fzg9 A1 | ❌ should be coupler |
| G1 e0-0 | Fzg9 A1 (inter 2↔1) | Fzg9 A3 | ❌ |
| G1 e0-1 | Fzg9 E2 | Fzg9 E2 | ✅ |
| G1 e0-2 | OBS D1 (vlan100,…) → CCU | CCU box1-t38 | ✅ |

(Fzg-15's CCU `10.179.61.1` was offline, so Fzg-15 switches were identified via LLDP from Fzg-9's A1, which is plugged into them.)

**Expected end-state (Fzg-9 internal A-head):** A1 e0-0 ↔ A3 e0-0 (intra-A) · A1 e0-1 ↔ G1 e0-0 (inter 1↔2) · A1 e0-2 ↔ front coupler (to Fzg 15) · A3 e0-1 ↔ A2 (already ✅) · A3 e0-2 ↔ front coupler · G1 e0-1 ↔ E2 (already ✅).

**Required action (Stadler, on-train physical re-cable) — move A1's three e0 cables:**
1. **A1 e0-0**: off Fzg15-A3 → onto **Fzg9 A3 e0-0**.
2. **A1 e0-1**: off Fzg15-G1 → onto **Fzg9 G1 e0-0**.
3. **A1 e0-2**: off Fzg9-A3 → onto the **actual front-coupler jumper** to Fzg 15.

This frees Fzg9 A3 e0-0 and G1 e0-0 (currently patched to each other as a side-effect of A1 vacating its slot) to receive A1, and returns A3 e0-2 to coupler duty. NOT fixable by factory-reset or remote config push — the vlan100-carrying cables are physically on the wrong train. After re-cabling, A1's vlan100 reaches this CCU; OBN auto-topology sees Fzg-9 neighbours and A1 can auto-recover (or push staged `nv4-100-A1` train_id=9 at `/data/auto-topology/upload/nv4-A1-v8-009-render.cfg`; A1 LAST per v8-cabling-trap). **Note:** A1's running config has already been hand-corrected to train_id=9 (hostname + 27 DHCP deltas) via the native-VLAN-1 channel, so post-recable it should slot in without a push.

**⚠️ Stadler to confirm:** whether the cross-wire is at the inter-train coupler jumper or inside Fzg-9's A-coach patch panel — the corrective end-state above is the same either way. Also confirm Fzg-9+Fzg-15 are intended to be coupled here.

**Note on coupled-train caveat:** because the two consists are physically coupled, verify with Stadler whether Fzg 9 and Fzg 15 are *intended* to be coupled here. If so, the fault is purely the A-end intra-consist patch (e0-0/e0-1 must stay within Fzg 9); the coupler itself (e0-2) is legitimately cross-train.

**Status:** ✅ RESOLVED 2026-06-17 (AR). Stadler **replaced the A1 switch** and re-cabled the A-head correctly. The replacement (chassis `a0:59:3a:d0:c1:c0`, DHCP `.186`) came up on factory config (`dosto-000000000000-v1-FD`) but is now cabled per the as-designed map — live LLDP confirms: A1 e0-0 → Fzg9 A3 ✓, e0-1 → Fzg9 G1 ✓, e0-2 → Fzg15 A3 (front coupler) ✓. Config `nv4-A1-v8-009` pushed via `obn update c .186` (RRQ seen, switch rebooted, hostname adopted, persisted) → **12/12 switches now `nv4-X-v8-009`**, RSTP single-root G1 (`a0:59:3a:d0:43:a0`) unchanged + converged. The OLD A1 (`a0:59:3a:d0:8f:a0`, was hand-corrected in-band on 2026-06-08) is now a spare hanging off A3 e0-2 coupler trunk (VLAN 5/15 only, no vlan100) — no fabric clash; Stadler can remove/retain as spare.

**OBN note:** `obn update c` initially crashed with `AttributeError: 'NoneType' object has no attribute 'type'` at `tree.py:34` (`OBNTree.create_tree`) — the cross-consist None-guard (Bug 6) was **absent** on this 2.2.23 CCU despite the "bugs 1–10 native" assumption. Applied the canonical `if neighbour_device is None: continue` guard at runtime (backup `tree.py.pre-bug6`); push then succeeded. Runtime-only — wiped on reboot unless persisted via NDSU chroot.

---

### #11 — 4736-114 (6-car, Fzg 142) — 14× FIS-display / energy-meter ports link-down (end-device not connected)

**What we see:** 14 access ports configured for end devices (13 FIS passenger displays — *Bildschirm* — plus 1 energy meter — *Energiezähler E*) are admin-enabled per the nv6 template but show `line protocol down`, never negotiated (Speed/Duplex Auto/Auto), 0 RX/TX packets, and **all error counters zero** (no CRC, carrier-false, runts, giants). Spread across coaches, partial within each switch:

| Switch (R/SW) | Down port(s) | Device |
|---|---|---|
| A1 (R1_SW1) | e2-0, e2-2 | Bildschirm A7, A1 |
| C1 (R2_SW1) | e2-1, e2-3 | Bildschirm C5, C3 |
| C2 (R2_SW2) | e2-1 | Bildschirm C6 |
| D2 (R3_SW2) | e2-0 | Bildschirm D8 |
| E1 (R4_SW1) | e2-0 | Bildschirm E7 |
| E2 (R4_SW2) | e2-2 | Bildschirm E2 |
| E3 (R4_SW3) | e2-0 | **Energiezähler E** (energy meter) |
| F1 (R5_SW1) | e2-3 | Bildschirm F3 |
| B1 (R6_SW1) | e2-0, e2-1, e2-3 | Bildschirm B7, B5, B3 |
| B2 (R6_SW2) | e2-2 | Bildschirm B2 |

**Diagnosis:** for each down port the **switch side is proven healthy** — every affected switch has multiple *other* `e2-*` display ports UP at 100 Mb/s Full passing traffic, on identical hardware/config. The down ports never establish a link and carry zero errors, i.e. the electrical path to the device is simply open. Fault is the **cable/connector or the display's own network interface** — the device end, not the switch.

**CCU-side checks performed (exhausted, 2026-06-20 AR):**
1. Confirmed port config matches the nv6-X-v8-142 template (admin-enabled, VLAN 3 FIS, correct).
2. `show interface <port> details` on every down port — line protocol down, Auto/Auto, 0 packets, 0 errors, no `RUNNING` flag.
3. Same-switch UP sibling comparison — proves the switch PHY/port-block is good (e.g. A1 e2-1/e2-3/e2-4/e2-5 all up while e2-0/e2-2 down).
4. **Port bounce** (`configure interface <port> no enable` / `enable`) on all 14 ports, 30–35 s settle — **none recovered.** (Port bounce DID recover a transient stall on cable reg #6, so a non-recovery here is meaningful.)
5. PoE not applicable — `e2-*` are non-PoE ports (displays externally powered); confirmed via `show poe` (e2-* block absent from PoE table).
6. **Switch logs verified clean** (`show log` + `show log persistent` on all 10 affected switches) — no link up/down (flap) events on any of the down e2-* ports, no PHY/CRC/interface errors, no PoE faults. The *absence* of any link-transition history on those ports supports "no device ever connected" over an intermittent/faulting link. The only non-routine entry is a `KMkon` module restart (count 1–2) present on 9 of 10 switches fleet-wide and self-recovered — benign, mechanistically unrelated to the data-only display ports (distinct from the Fzg 118 #9 case, where `KMkon` degraded with a dead PoE PSE; here PoE is healthy, e.g. B1 28 W / 202 W).

VLAN 3 (FIS) is a Stadler-side device VLAN with no CCU visibility, so whether each display's NIC is actually up cannot be confirmed remotely — the irreducible boundary.

**Required action:** Stadler to verify, per listed port, (a) the patch cable from the switch port to the display/energy-meter is intact and seated, and (b) the device is powered with its Ethernet interface up. Acceptance: link comes up (100/Full) on the listed port. Nomad can re-verify remotely on request via `show interface <port> details`.

**Caveat (open question for Stadler/ÖBB):** this train (4736-114 / Fzg 142) had its CCU misimage corrected on 2026-06-20 and its device-side commissioning state is not independently confirmed. If some displays are simply **not yet fitted/powered** as part of ongoing fit-out, those ports are expected-down (commissioning state), not faults. The partial-per-coach pattern is consistent with incremental fit-out. Confirm device power/fit status before treating all 14 as hard cable faults.

**Status:** 🔴 OPEN

---

### #12 — 4736-120 (6-car) — A2 e1-9 PoE port fault (redundant Sprechstelle)

**What we see:** A2 port e1-9 (the redundant intercom/operator-station — Sprechstelle — link) reports PoE status `E(1e)` (PSE error state) and delivers 0.00 W, while every other PoE port on A2 is healthy (`on/on`, ~2–4 W) and the PSE has 173 W available. The port's link shows protocol-up but the device is silent: **RX packets 0 / RX bytes 0** (switch TX-only — RSTP/IGMP/LLDP multicast), 0 RX/CRC/carrier errors. The condition **survived a switch reboot** by the on-site tester (2026-06-24).

**Diagnosis:** single-port PoE delivery fault. Because the PSE itself is healthy and only this port faults, the cause is the cable, connector, or the powered device on e1-9 — or that port's PoE PHY. Not a Nomad config issue (PoE config on A2 is uniform across ports).

**Context:** the tester's reboot of A2 restored ZFR reachability for *almost all* screens — but e1-9 stayed faulted, confirming e1-9 is independent of the screen/ZFR-path symptom (the reboot cleared a transient forwarding condition on the inter-coach path; the A3↔Stadler-FW trunk and all inter-coach trunks verify clean post-recovery). e1-9 is the redundant Sprechstelle leg, not a ZFR uplink.

**Required action (Stadler):** inspect the e1-9 cable/connector and the Sprechstelle device end; reseat or replace as needed. Re-verify with `show poe` (expect `on/on`, non-zero W, valid class) and `show interface e1-9 details` (expect non-zero RX). If the device end and cable are proven good and the port still faults, the switch's PoE PHY on e1-9 is suspect → switch repair/replacement.

**Status:** 🔴 OPEN

---

### #13 — 4736-109 (6-car) — E2 cold-bypassed (whole switch absent from fabric + monitoring)

**What we see:** E2 has no DHCP lease and no vlan100 management IP — invisible to the CCU sweep and to NMS/Zabbix. Its two chain-neighbours (E3 via E2 e0-0 intra-coach, D1 via E2 e0-1 inter-coach) are LLDP-adjacent to each other across E2's slot: D1 e0-1 LLDP→ E3, both links UP 10G, 0 CRC, carrier-false 0.

**Diagnosis:** **cold bypass** — E2 is powered off or failed in place, and its backbone trunks relay straight through (the VDS cold-bypass behaviour). This is the reciprocal, clean-link signature. It is **NOT a cabling fault** and NOT re-cabling: LLDP alone can't fully separate a true cold bypass from a bypass-shaped miswire, but the clean reciprocal on the expected toward-E2 ports makes power/health of E2 the first thing to check.

**Required action (Stadler):** check **power/health of switch E2** (coach E, middle switch) first. If E2 is confirmed powered and healthy, pivot to inspecting the E3↔E2 / E2↔D1 cabling. Once E2 is back, verify it leases a vlan100 IP and appears in `dhcp-lease-list`.

**Zabbix coverage (2026-07-04):** ⚠️ **monitoring blind spot** — because E2 never entered the OBN report (coach-numbering walk drops the bypassed position), NMS never provisioned a host for it, so **nothing can alarm on E2 being down.** The dashboard reads 16/18 as green. This is the field confirmation of the OBN coach-numbering false-negative — see [findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md](findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md). Engine fix (surface bypassed switches as DOWN rows so NMS can alarm) is the durable close.

**Note:** C3 on the same train is ALSO absent from monitoring (no lease) but is a **different** root cause — C3 is present, healthy, and forwarding heavily (C2 e0-0→C3 UP 10G, RX 9.9GB/TX 280GB, 0 CRC); it simply never got a mgmt IP. That is a Nomad-side DHCP/mgmt-VLAN fault on C3, not a cabling fault, so it is tracked in the fleet-journal, not here.

**Status:** 🔴 OPEN

---

### #14 — 4734-125 (4-car, Fzg 25) — E1 e0-4 AP link RX-CRC storm (uncommissionable factory AP)

**What we see:** The Coach-E AP (Westermo `00:14:5a:04:e6:59`) is the missing 16th AP — it never pulled a Nomad vlan100 lease and sits stuck on factory default `192.168.1.12`. It is the ONLY AP of 16 not on `-v1-` Nomad config; the other 15 APs and all 12 switches are healthy on v8 (`nv4-*-v8-025`). The AP's switch port **E1 (10.179.62.181) e0-4 is link-UP at 1000/Full**, so no port-down trigger fires. But the port shows **RX crc errors: 1593 against only 340 RX packets**, plus jabber 76 / RX errors 6 (carrier-false 0, TX-CRC 0). From the CCU (temp `192.168.1.2/24` on vlan100): ICMP is **60% loss** on small frames and **100% loss on any frame ≥1400 bytes**; TCP ports 22/80/443 accept SYN but every application handshake (SSH banner, TLS ClientHello) times out — because those are large frames the link corrupts.

**Diagnosis:** **physical-layer corruption on the E1 e0-4 ↔ Coach-E AP link.** Small frames intermittently pass; large frames are dropped 100%. This is a bad cable / dirty or damaged connector / EMI signature (RX CRC on the switch's receive side = the AP→switch direction is corrupting). It is NOT a config or commissioning problem — the AP is stuck in factory config *because* it cannot be commissioned: OBN's SNMP push and any LuCI config import are large payloads that never complete across a link that drops everything ≥1400 bytes. Attempting a config push here is futile and could half-write the AP.

**Required action — in order, simplest first:**
1. Replace the patch cable between the Coach-E AP and switch E1 e0-4 (RX-CRC storm points at the AP→switch pairs / connector).
2. If cable replacement doesn't clear the CRC counter, swap the AP with a known-good unit.
3. Once the link is clean (E1 e0-4 RX CRC = 0, large-frame ping passes), re-run `dosto-ap-factory-recover` — the AP will then commission normally over LuCI and pull a `-v1-` lease.

**Zabbix coverage:** likely a blind spot in the same shape as #8/#13 — the AP is on a factory `192.168.1.x` address OBN never discovered, so any NMS ping alarm points at an unroutable/stale target while the port-up state suppresses a link alarm. Confirm on next NMS pass.

**Discovered:** 2026-07-08 (AR), box1-t62 / 10.179.62.1, during a factory-AP recovery request. Temp interface removed after diagnosis; no config pushed.

**Status:** 🔴 OPEN

---

## Resolved issues

| #  | Trainset  | Switch / Port      | Fault type        | Resolved     |
|----|-----------|--------------------|-------------------|--------------|
| 6  | 4736-120  | C2 e0-4            | AP not connected  | 2026-05-22 — port bounce restored link, AP active, zero errors |

## How to add a new entry

1. Run `lldp_topology_check.py` (after applying the consist-specific `EXPECTED_TOPOLOGY` and `SWITCHES`). For non-trunk faults (AP/access-port), use `show interface summary` + `show interface <port> details`.
2. For each MISMATCH or down trunk port, distinguish **template/config issues** (Nomad's responsibility — duplicate hostnames, `dosto-00000000`, missing OBN config) from **physical cabling issues** (Stadler's responsibility — wrong port, missing cable, swapped cables). **Only physical cabling issues belong in this register.**
3. Identify the fault type from the conventions table above.
4. Append a row under "Open issues" with the next sequential `#`. Use generic switch IDs (A1, D2, etc.) and port labels (e0-0, e1-8, etc.) — no IPs, no MACs, no live hostnames.
5. If the fault triggers a per-train Stadler-facing fault report (`Stadler_FzgNNN_*_Cabling_Fault_Report_v1.0.docx`), add a `Report:` link in the action cell.

## Related artefacts

- Per-train Stadler cable-fault reports — `Stadler_Fzg<id>_<consist>_Cabling_Fault_Report_v1.0.docx` (workspace root).
- Topology verification script — [scripts/lldp_topology_check.py](scripts/lldp_topology_check.py).
- Procedure for the LLDP cabling check — [troubleshooting-runbook.md](troubleshooting-runbook.md) → "LLDP Cabling / Topology Check".
- Expected per-train trunk topology — derived from the consist's IP-allocation PDF in `train-ip-allocation-commission/<series>/<series>-NNN/` and from `/etc/obn/template/nv4-*.cfg` or `nv6-*.cfg` on the CCU.
