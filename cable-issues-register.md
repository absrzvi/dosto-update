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
  - `wrong far-end port` — cable lands on the correct switch but wrong port number
  - `PoE PSE fault` — switch PoE power-sourcing subsystem fails to initialise (0 W available, survives reboot); hardware repair/replacement

## Open issues — at a glance

| #  | Trainset  | Switch / Port      | Fault type        | Status   |
|----|-----------|--------------------|-------------------|----------|
| 1  | 4734-101  | E2 ↔ B1            | wrong neighbour   | 🔴 OPEN |
| 2  | 4736-108  | C3 e0-0 / e0-1     | cable swap        | ✅ RESOLVED |
| 3  | 4736-108  | D1 ↔ E2            | missing trunk     | ✅ RESOLVED |
| 4  | 4736-109  | B3 e0-4            | AP not connected  | 🔴 OPEN |
| 5  | 4736-104  | D3 e1-2            | physical-layer    | 🔴 OPEN |
| 6  | 4736-120  | C2 e0-4            | AP not connected  | ✅ RESOLVED |
| 7  | 4736-108  | A2.e0-1 ↔ A3.e0-1  | physical-layer    | 🔴 OPEN |
| 8  | 4736-115  | B3 e0-4 (Coach6)   | AP not connected  | 🔴 OPEN |
| 9  | 4736-118  | E1 (whole switch)  | PoE PSE fault     | 🔴 OPEN |
| 10 | 4734-109  | A1 e0-0/e0-2 ↔ A3  | cable swap (coupler) | ✅ RESOLVED (A1 switch replaced + re-cabled, 2026-06-17) |

---

### #1 — 4734-101 (4-car) — E2 ↔ B1 wrong neighbour

**What we see:** E2.e0-0 reaches B1 (and B1.e0-1 reaches E2).
**Plan:** E2.e0-0 ↔ E3 (intra-E coach), and B1.e0-1 ↔ E1 (inter-coach E↔B).
**Diagnosis:** the intra-E-coach trunk and the E↔B inter-coach trunk are cross-wired.

**Required action:** re-patch the E-coach end so E2.e0-0 lands on E3, and the inter-coach E↔B trunk lands on E1.e0-0 ↔ B1.e0-1.

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

**Status:** 🔴 OPEN

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
