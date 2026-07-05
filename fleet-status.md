# DOSTO Fleet — v8 Rollout Status

**Last updated:** 2026-05-22 by Abbas Rizvi — live SSH verification of 6 trains: 4736-119/110/111 → 🟢 DONE (all sw+APs+snapshot confirmed); 4734-111 → PAUSED (sw ✅, 16 APs need fw push); 4734-113 → PAUSED (3 sw still v7m + APs need fw); 4734-115 → PAUSED (all 12 sw v7 + APs need fw, check template target). Previously: 4734-190 BLOCKED on G2 e0-0 cabling fault.
**Update discipline:** This file is the source of truth for "where did we leave off". Every engineer **must update the relevant row at the end of every train session, before logging out** — this is Step 11 of the train-login checklist. If you don't update, the next person can't pick up.

**Companion file:** Narrative per-train history (recovery sequences, discovered lessons, session context) lives in [`fleet-journal.md`](fleet-journal.md). This file holds **current state** only — table + diagnostic-state bullet lists. Prose blocks in the per-train detail sections below are being migrated to the journal as each train is visited. When you visit a train, move its prose to the journal and trim its block here to just the diagnostic-state fields.

## Legend

| Lozenge | Status | Meaning |
|---|---|---|
| 🟢 | **DONE** | All v8 work complete, no Nomad action remaining |
| 🟢 | **DONE w/ Stadler** | Nomad work complete, awaiting Stadler on cabling/FW |
| 🔵 | **IN PROGRESS** | **Orchestrator-claimed, worker is mid-stage.** Auto-managed by `/dosto-orchestrate` and refreshed every cycle digest + every stage-transition report. Cell format: `🔵 IN PROGRESS — stage <stage_id> (<step>/<total>, t+<elapsed>), hb <iso8601>, sess <sess-id>`. **Heartbeat liveness:** < 10 min = fresh; 10–30 min = lagging; > 30 min = stale (likely a dead session — see `/dosto-morning-brief`'s stale-claim gate for cleanup). |
| 🟡 | **PAUSED** | Partial work; train powered off mid-run; will resume as-is |
| 🔴 | **BLOCKED** | Stadler cabling fault must be fixed before we can continue |
| ⚪ | **UNKNOWN** | Visited but state not captured here yet, or never visited |

Field-level emoji used in the per-train detail blocks below: ✅ done · 🟡 partial · 🔴 broken · ⏸️ paused · ⬜ not started · ❓ unknown / not yet checked

## Train#-and-Fzg convention

**Train# is the primary identifier.** Engineers type `4736-104` (the Nomad-internal name) when invoking skills. The Fzg ID is the ÖBB customer-facing number, derived per series:

- **4736 series**: `Fzg = train# + 28`  (e.g. 4736-103 = Fzg 131, 4736-120 = Fzg 148).
- **4734 series**: `Fzg = train# − 100` (e.g. 4734-119 = Fzg 19).
- **4705 series**: `Fzg = train# + 128` (e.g. 4705-103 = Fzg 231).
- **4706 series**: `Fzg = train# + 88`  (e.g. 4706-103 = Fzg 191).

⚠️ **Formulas are reference only.** At runtime, skills look up the Fzg from the fleet-status row for the Train# (via `scripts/fleet_status_lookup.py`). If the row's Fzg cell is `❓` or missing, the skill halts and asks the engineer rather than trusting the formula silently — misimaged CCUs, stale Puppet images, and hand-set wrong values have all left switch hostnames and templates carrying the wrong Fzg pre-commissioning, and that's exactly what commissioning fixes. Trust the file, never the formula.

---

## Fleet at a glance

Five-column scan tables. For full per-train detail (OBN patches, switch firmware, AP firmware, vlan7, Stadler cabling, FW reach, health check, customer report, last touched), see the per-train detail blocks below.

### 4736 series (DOSTO NEU 6-car)

**Stadler status** = 🔴 **BLOCKED** when any APs/switches are missing OR a cabling fault is open; ✅ clear otherwise; ❓ when not yet checked.

| Train# | Fzg | CCU IP | Nomad status | Stadler status | Next action |
| --- | --- | --- | --- | --- | --- |
| 4736-101 | 129 | `10.179.7.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t7) |
| 4736-102 | 130 | `10.179.47.1` | 🟡 PAUSED — 2026-06-02 sess 0602Z: Gate 5 answered 'partial' (push 22 visible APs, 2 E3 absent=Stadler), but CCU dropped SSH/cellular before fw push started (2× timeout ~10:12-10:13Z). No CCU work applied this session. Prior state intact: 18/18 sw v8-130 ✅, OBN 9/9 ✅, vlan7 172.19.193.2/17 ✅. Remaining: AP fw push for .218 .220 .225 .228 .229 → 6.11.2-0; re-check staged-not-activated .219 .224 .234 + incomplete .221 .237 .239; resume push_ap_firmware when CCU back. Last touched 2026-06-02 AR | 🔴 E3 sw + 2 APs absent | **2026-05-21 /dosto-orchestrate:** Gate 1 (bug9 fold-in) + Gate 2 (safe_reboot) approved 12:48Z–13:10Z. OBN **9/9 persisted** (run2) ✅, vlan7 172.19.193.2/17 ✅, train_id=130 ✅. 17/17 sw all on nv6-X-v8-130 fw 7.4.2 ✅ (E3 absent). Gate 4 serial AP fw push completed: **12/20 APs at 6.11.2-0 ✓** (.220 .222 .225 .226 .227 .229 .230 .231 .232 .233 .235 .236); **3 APs staged-not-activated** (.219 .224 .234 — 6.10.0-0 active, 6.11.2-0 staged, need re-`obn update f` to trigger partition swap); **3 APs incomplete** (.221 .237 .239 — push went wrong, recovery needed); **1 AP reset to factory** (192.168.1.20, was likely .238 — lost DHCP, needs LuCI bypass to recover); **.218 still incomplete** (known SNMP-silent, was deliberately skipped). 10 APs in coaches 4/5/6 have AP\*-v1→AP\*m-v1 config drift (separate Stage 19 issue, not affected by this push). **Next visit:** (a) `obn update f <ip>` for .219 .224 .234 to activate staged fw; (b) investigate .221 .237 .239 incomplete state; (c) LuCI bypass to recover 192.168.1.20 anomaly + identify which slot it is; (d) AP config refresh (push_ap_config) for the 10 AP\*m-v1 drift APs. |
| 4736-103 | 131 | `10.179.11.1` | 🟡 **PAUSED — awaiting Stadler on F3 AP3m + B2 null fw** | 🔴 F3 AP3m missing | reboot to activate run3 (8/8 OBN persisted); push AP fw 6.10.0-0→6.11.2-0 after Stadler |
| 4736-104 | 132 | `10.179.10.1` | 🟢 **DONE w/ Stadler — 22/22 visible APs at 6.11.2-0; D4 AP cable reg #5 still open** | 🔴 D4 AP missing (cable reg #5, D3.e1-2 PHY fault) | **2026-05-21 13:00Z /dosto-orchestrate:** D4 SWITCH group recovered today (was 15/18 sw at brief time, now 18/18 ✓). Gate 1 (bug9 fold-in) + Gate 2 (safe_reboot) approved 12:48Z–13:10Z. OBN **9/9 persisted** (run2 with bug9) ✅, vlan7 172.19.194.2/17 ✅. Gate 4 approved 13:30Z (serial, 4 APs). AP fw push completed under nohup ~13:25Z: .233 .240 .236 .225 all at 6.11.2-0 ✓. `obn validate` confirms 22/22 visible APs at 6.11.2-0, 0 stuck. **D4 AP (Coach3 pos 4) still absent** — D3.e1-2 PHY fault, cable register #5, Stadler-side. Train is functionally complete pending D4 cable fix. |
| 4736-105 | 133 | `10.179.1.1` | 🟢 **DONE w/ Stadler** | 🔴 Coach 5 AP2 missing | **2026-06-30 (AR, coupling-test backup train w/ 4736-117):** CCU healthy `box1-t1`; vlan7 `172.19.194.130/17` ✅ correct (Fzg 133 odd), FW peer `172.19.194.129` ICMP 100% loss = commissioned ✅. ⚠️ **Switch fabric DARK** — 16+ min uptime but 0/18 sw + 0 AP on vlan100 (vlan100 UP, dhcpd serving vlan100, near-zero RX; fping switch range empty). Switches not booted/joined post-power-cycle — same as 117. Coupling test BLOCKED on fabric returning. — prior: wait for Stadler on Coach5 AP2 + FW path |
| 4736-106 | 134 | `10.179.19.1` | 🟡 PAUSED — pre-flight 2026-06-02: only 2/18 sw + 0/24 AP visible (CCU uptime 3min, coaches still joining). Re-probe in ~15min. OBN 0/8 vanilla, vlan7+train_id correct. Last touched 2026-06-02 AR | ❓ | confirm v8 state — pre-flight 2026-05-28: HARD-FAIL sw 5/18 + ap 0/24 visible on vlan100 (CCU reachable but consist devices not joined — coaches powered off or just rebooted) — skipped this run. pre-flight 2026-06-02 13:08Z: UNREACHABLE on TCP/22 — skipped this run |
| 4736-107 | 135 | `10.179.25.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t25) |
| 4736-108 | 136 | `10.179.8.1` | 🟢 DONE w/ Stadler — 18/18 sw v8-136, 18/23 APs at 6.11.2-0; 5 deferred + A2↔A3 PHY fault | 🔴 A2.e0-1↔A3.e0-1 physical-layer fault (cable reg #7) + 1 AP (192.168.1.20) absent | 2026-06-08 sess 0900Z: OBN 10/10 persisted (run1/551) ✅, train_id=136 ✅, vlan7 172.19.196.2/17 ✅, 18/18 sw nv6-X-v8-136 fw 7.4.2 ✅. AP config 11/11 m-variant converted ✅. 18/23 reachable APs at 6.11.2-0; 5 staged-not-activated (.223 .235 .226 .219 .225) — deferred run-wide (partition-swap, R&D). 1 AP (192.168.1.20) absent + A2↔A3 trunk PHY fault = Stadler reg #7. (worker died mid-fw-push; orchestrator verified final state via obn validate). Last touched 2026-06-08 AR |
| 4736-109 | 137 | `10.179.28.1` | 🟢 DONE w/ Stadler — 2026-06-09 sess orch9: 18/18 sw v8-137 fw 7.4.2 ✅, OBN 11/11 (incl bug11) ✅, train_id=137 ✅, vlan7 ✅CORRECTED+PERSISTED 2026-06-11: 06-09 session had set WRONG 172.19.206.2; fixed to **172.19.196.130/17** — runtime active (FW REACHABLE) AND baked via NDSU chroot (promoted run2/release, verified: vlan7 + 2 marker files [2.2.23-native baseline] + train_id 137); activates fully on next boot (recipe findings/RECIPE_loop_fix_4736-109_110_2026-06-11.md). **2026-06-11 L2-loop event** (coupled w/ 4736-110, storm at Stadler FW, capture 07:41Z): containment applied+persisted — rate-limit broadcast 1M on A1/A3/B1/B3 e0-2 + A3 e1-4, native VLAN 999 on A3 e1-4 (prune set intact). ✅ Coupler native retag (e0-2 → 999, allow 5,15) applied+persisted all 4 ports 2026-06-11 ~13:40Z after train power-cycle. Same power-cycle ALSO validated reboot-persistence: booted run2 with vlan7 196.130 native (stale 206.2 gone, FW REACHABLE) + all switch changes intact from startup-config. **AP fw: 22/22 visible APs at 6.11.2-0** ✅ — incl both m-variants (.223 AP3m, .227 AP1m) which ACTIVATED with bug11-patched OBN (m-variant wall DISPROVEN; was OBN report bug + short settle, not hardware). Only gap: 3 B-coach APs PHYSICALLY ABSENT = Stadler cable reg #4. Last touched 2026-06-09 AR | 🔴 3 B-coach APs missing (cable reg #4) | 2026-06-08 sess 0900Z + bug11 follow-up: OBN now 11/11 (bug11 westermo-fw-verify applied+PERSISTED run1/release ✅), train_id=137 ✅, vlan7 172.19.196.130/17 ✅, 18/18 sw v8-137 ✅. AP fw RE-VALIDATED after settle: 15/21 at 6.11.2-0 (3 recovered as case-a false-negatives — were slow-but-fine, not failures). 7 remain at 6.10.0-0 ALL with ~6.2h uptime = genuine case-b RT-610 flash-trigger hangs (.226 .232 .228 .223 .235 .230 .219); bug11 now makes obn update f report these honestly → retry candidates. 3 B-coach APs absent = Stadler reg #4. Last touched 2026-06-08 AR |
| 4736-110 | 138 | `10.179.23.1` | 🟢 **DONE** — 2026-06-11 L2-loop containment applied+persisted (coupled-pair storm w/ 109): rate-limit broadcast 1M on A1/A3/B1/B3 e0-2 + A3 e1-4, native VLAN 999 on A3 e1-4, **+ coupler native retag (e0-2 → native 999, allow 5,15 only) all 4 ports applied+persisted** — coupler now carries ONLY tagged 5+15 per AR directive. NOTE: FW seen TXing on VLAN 15 (e1-4 FDB) — supports FW-bridge ring hypothesis. See findings/RECIPE_loop_fix_4736-109_110_2026-06-11.md. **2026-06-15 live check:** online, 18/18 sw, root=D1-138 own/clean, **decoupled** (all e0-2 down). ⚠️ Runtime coupling fixes WIPED by power-cycle as expected: B3-138 e0-2 port-cost back to template `137999999` (>2^27 overflow — re-arms TC storm on next coupling); coupler back to `prune allow 5,15`. Permanent fix needs nv6 template change (port-cost <2^27 + max-age 38/fwd-delay 20). See findings/coupling_test_4736-110_119_2026-06-12/ A8. | ✅ clear | 2026-05-22 verified live: 18/18 sw v8-138 fw 7.4.2 ✅, 24/24 APs 6.11.2-0 ✅, snapshot promoted (release+knownworking present), vlan7 172.19.197.2/17 ✅. OBN 11/11 persisted (run1, ID 373) — verified post-reboot 2026-06-09: bug10+bug11 added (train was at old 9-bug baseline), promoted via chroot + safe_reboot, all 11 markers + train_id 138 + vlan7 confirmed in the booted snapshot. L2 health check 2026-06-09: ✅ HEALTHY — 18/18 sw + 24/24 AP, 0 CRC/0 carrier-false fleet-wide, single stable STP root, all trunks at target speed, FW commissioned (Q1 ARP reachable, Q2 ICMP 100% loss); findings/findings_10.179.23.1_20260609.json. Customer report 2026-06-09: reports/customer/OBB_Fzg138_Network_Health_Check_Report_v1.0.docx (draft for review). All commissioning + deliverables complete. |
| 4736-111 | 139 | `10.179.24.1` | 🟢 **DONE** | ✅ clear | 2026-06-16 AR: vlan7 DRIFT found+fixed — live was `172.19.204.2/17` (encoded Fzg 152), corrected to `172.19.197.130/17` via NDSU chroot (heredoc-into-stdin; interactive paste failed twice → promote never ran), persisted (booted run2). FW path Q1 FAILED: nothing at `.197.1`, Westermo answers ARP at `.197.129` but drops ICMP → Stadler-side FW not commissioned at `.1` (not a Nomad blocker). Switch templates untouched + correct: 18/18 `train_id=139`, hostnames `nv6-*-v8-139` ✅. — 2026-05-22 prior: 18/18 sw v8-139 fw 7.4.2 ✅, 24/24 APs 6.11.2-0 ✅, OBN 8/8+bug9 persisted. (vlan7 was recorded ✅ on 2026-05-22 but live had drifted to .204.2 by 2026-06-16.) |
| 4736-112 | 140 | `10.179.40.1` | ⚪ UNKNOWN — train_id+vlan7 FIXED 2026-06-09; commissioning not yet started | ❓ | 2026-06-09 AR: CCU IP confirmed `10.179.40.1` (`box1-t40`); engineer confirmed true Fzg = 140. Was misimaged toward Fzg 168 (broken `128 + train_id` formula → 168 + vlan7 set to .212.2). **FIXED via chroot + safe_reboot**: all 18 nv6 templates now `{%- set train_id = 140 -%}` ✅, vlan7 `172.19.198.2/17` ✅ (live+nmconnection). Post-reboot verified: FW peer `172.19.198.1` ARP REACHABLE + ICMP 100% loss = **FW commissioned by Stadler** ✅. Commissioning (OBN patches, sw/AP fw+config, device discovery, L2 health) **not yet started** — safe to `obn update c all` now (renders nv6-X-v8-140). Prior `10.179.12.1` attribution was wrong (= Fzg 147, confirmed 2026-05-21). |
| 4736-113 | 141 | `10.179.22.1` | 🟢 **DONE (commissioned, per live ID 2026-06-15)** — box1-t22 confirmed live = nv6 Fzg 141, OBN literal `train_id = 141` (clean hardcode), switch hostnames `nv6-*-v8-141`, vlan7 `172.19.198.130/17`. CCU IP was ❓ until 2026-06-15 sweep identified box22. | ❓ | 2026-06-15: identified via fleet-wide live sweep (was box=❓). v8 + hardcoded literal = commissioned. L2 health / report not yet run. |
| 4736-114 | 142 | `10.179.27.1` | 🟡 PAUSED — misimage RESOLVED; switches DONE, AP fw pending | 🟡 14 FIS displays link-down (fit-out?) | **2026-06-20 AR: misimage FULLY CORRECTED + verified live.** CCU now `box1-t27` @ `10.179.27.1` (was misimaged as 4706-103's T17/10.179.17.1 — collision cleared, zero 103/6017 contamination found). train_id=27, rtl_train_id=6027, vlan7 `172.19.199.2/17` ✅ (correct for Fzg 142). 18/18 sw `nv6-X-v8-142` fw 7.4.2-RC1 ✅; 18/18 switch templates `set train_id = 142` ✅. 24/24 APs leasing, correct Nomad config ✅. **REMAINING (Nomad): AP fw push 0/24 — all at 6.10.0-0, need 6.11.2-0.** Zabbix 6027 = 43/43 hosts monitored+SNMP-available. **14 e2-* FIS display ('Bildschirm') + 1 energy-meter ports link-DOWN** across coaches — CCU-side checks EXHAUSTED 2026-06-20 (port details: never-negotiated, 0 RX, 0 errors; UP siblings prove switch healthy; port bounce on all 14 → 0 recovered; non-PoE). Logged as **cable reg #11** (end-device not connected, Stadler-side). Caveat: may be Stadler fit-out/power state not hard faults — confirm device power before treating as cable faults. Zabbix alarms left active. **ÖBB status report issued 2026-06-20: reports/customer/OBB_Fzg142_4736-114_Commissioning_Status_v1.0.docx** (network commissioned; AP fw in progress; display ports = verification requested from ÖBB/Stadler). Split-brain alarm = false-positive on single-CCU train (mcarp=1 healthy; trigger already disabled). Earlier note: 10.179.42.1 is a DIFFERENT train (fv5/4705-101/Fzg 229), not 114. |
| 4736-115 | 143 | `10.179.18.1` | 🟢 DONE w/ Stadler — re-validated 2026-06-09 (sess orch9): 18/18 sw v8-143 fw 7.4.2, 23/24 APs at 6.11.2-0, OBN 9/9, vlan7 172.19.199.130/17, L2 HEALTHY (STP single-root D1, 0 error counters, FW Q1 REACHABLE+Q2 commissioned). Coach6 AP4 = Stadler reg #8. Last touched 2026-06-09 AR | 🔴 Coach6 AP4 (B3 e0-4) disconnected — cable reg #8 | 2026-06-08 sess 0900Z: 18/18 sw nv6-X-v8-143 fw 7.4.2 ✅, OBN 8/8 ✅, vlan7 172.19.199.130/17 ✅. 23/24 APs at 6.11.2-0 ✅; 12 m-variant configs (coaches 4/5/6) pushed ✅; no fw push needed (already at target). Coach6 AP4 (192.168.1.20) physically disconnected — Stadler cable reg #8; once cabled, LuCI bypass + fw for that 1 AP. Last touched 2026-06-08 AR |
| 4736-116 | 144 | `10.179.16.1` | 🟢 DONE — 18/18 sw v8-144, **24/24 APs at 6.11.2-0** | 🟢 Coach 6 AP3 visible post-reboot (cable reg #6 confirmed resolved) | 2026-06-09 re-probe: the 3 previously-"deferred" APs (.231 .234 .228) are ALL now 6.11.2-0, rpcFwFlash=0 (done), uptime 3h — they self-recovered = case-(a) false-negatives (counted on 2026-06-08 before flash+reboot finished), NOT partition-swap failures. **24/24 done.** CCU rebooted since 2026-06-08 (uptime 3h) → bug11/TFTP-helper/conntrack-timeout runtime patches all WIPED (OBN back to 10/10). 2026-06-08 base: 18/18 sw nv6-X-v8-144 fw 7.4.2 ✅, vlan7 172.19.200.2/17 ✅, all 24 AP configs green. Fully commissioned. Last touched 2026-06-09 AR |
| 4736-117 | 145 | `10.179.32.1` | 🟢 vlan7 FIXED 2026-06-30 (multitraction prep) — see note | 🟢 no Stadler issues found | **2026-06-30 (AR, coupling-test prep w/ 4736-105):** Arrived for multitraction test; found **vlan7 MISRENDERED** — live + nmconnection both `172.19.208.2/17` (decodes to Fzg 160), persisted across reboot. Expected for Fzg 145 (odd) = `172.19.200.130/17`. **FIXED via NDSU chroot (heredoc-into-stdin) + safe_reboot**; post-reboot verified all 4 assertions: nmconnection ✅ `172.19.200.130/17`, live vlan7 ✅ match, FW peer `172.19.200.129` ARP REACHABLE (Westermo `00:90:e8:cb:5d:cc`), ICMP 100% loss = **FW commissioned** ✅. Switch templates already correct (18/18 `nv6-*-v8-145` confirmed pre-power-cycle). ⚠️ **Switch fabric DARK post-power-cycle:** consist power-cycled repeatedly this session (CCU uptimes ~5 min); after reboots 0/18 sw + 0 AP reachable on vlan100 (vlan100 UP, dhcpd serving, but near-zero RX — switches not booted/joined). Health check + coupling test BLOCKED on switch fabric returning; needs consist power/boot confirmation on the ground. — **2026-05-29 0625Z initial visit + clean-fabric verification (Abbas):** CCU 2-min uptime, vlan100 `10.179.32.129/25` ✓, vlan7 `172.19.200.130/17` ✓ (Fzg 145 odd → octet4=130 matches formula). 18/18 sw + 24/24 APs visible on first DHCP/ARP. LLDP topology: **0/18 faults** — every inter-coach trunk matches OBN nv6 templates exactly. STP: single stable root D1 (a0:59:3a:d0:76:e0), priority 0, all 18 agreeing. **Storm forensics: cumulative broadcasts per switch e0-0 = 100-3000** vs 600k-3.5M unicast (bc:uni ratio 0.001-0.005×) — textbook clean idle. **Answers ÖBB hypothesis:** no hidden open inter-coach trunk (all 36 e0-0/e0-1 link-UP and forwarding) — admin-up-link-DOWN ports exist but are non-trunks (front-couplers e0-2 on A1/A3/B1/B3 — expected solo, end-host e0-5 ports). Stadler FW vlan7: ARP REACHABLE peer at 172.19.200.129 (Westermo OUI), ICMP 100% loss, TCP "no route to host" → quirk (FW not at canonical .1?). **State:** v8 templates rendered (nv6-X-v8-145), train_id 145 in switch hostnames — initial v8 commissioning likely already done before this visit. **Next:** confirm `obn validate` clean (would expect green), capture findings JSON. |
| 4736-118 | 146 | `10.179.21.1` | 🔴 ERROR — novel nd-obn 2.2.23 layout; fix_obn.py targets old /usr/share/obn/*.py paths (would no-op). HELD pending R&D confirm whether 2.2.23 ships bugs 1-10 natively. 18/18 sw, 22 AP. **2026-06-02 AR: E1 PoE PSE fault — `show poe` 0 W / 0 W avail vs 202 W max (siblings ~20-32 W drawn); PoE-init hangs every boot, survives `sysadmin reboot`; SNMP agent also unresponsive. Hardware PoE fault → Stadler (cable-issues-register #9). Likely cause of "Coach E AP1m absent" (AP may be present but PoE-starved on E1 e0-4).** **2026-06-15 AR: re-verified — E1 PoE still 0 W / E(11) on all ports. Exhausted CCU-side recovery: port bounce no-op; SNMP reboot OID accepted but ignored (switch didn't reboot); CLI `sysadmin reboot` did reboot but PSE came up dead again. Root cause = degraded `KMkon` module (owns PoE PSE + SNMP-reboot, both dead; CLI reboot path still works). Not remotely recoverable → Stadler hardware. See register #9.** Last touched 2026-06-15 AR | 🟡 Coach E AP1m dark — E1 PoE PSE fault (see #9), not confirmed-missing (Stadler) | **pre-flight 2026-05-29: CCU unreachable on TCP/22 + ICMP — skipped this dispatch.** **2026-05-28 07:06Z live verification (Abbas):** all 18 sw on v8 — `obn validate` clean: IP ✓ / fw 7.4.2 ✓ / config `nv6-X-v8-146` ✓ across A1/A2/A3, B1/B2/B3, **C1**/C2/C3, D1/D2/D3, E1/E2/E3, F1/F2/F3 (C1 present — prior "absent" claim was wrong). APs: 23 visible (was 22 on 2026-05-21 — one more came online), all carry correct `AP*-v1-00145a*` config ✓, all still at firmware `6.10.0-0` (target `6.11.2-0`) ❌. Coach E (logical coach 4) only shows AP positions 2/3/4 → AP1m physically absent (Stadler). Gate 3 `obn update c` already complete (switches render as v8-146). **Next:** Gate 4 AP fw push to all 23 (6.10.0-0→6.11.2-0); ensure TFTP CT helper applied before push. **History:** 2026-05-21 /dosto-orchestrate green-field v8: Gate 1 promote_snapshot OBN 9/9 patches persisted, train_id=146 hardcoded in all 18 nv6-*.cfg, vlan7 = 172.19.201.2/17. Gate 2 safe_reboot 13:05Z. Gate ap_factory_bypass: LuCI HTTP push to 22 factory APs 12:55Z–13:03Z (302/200/200 per AP). |
| 4736-119 | 147 | `10.179.12.1` | 🟢 **DONE** — **2026-06-15 live check:** online, **18/18 sw** (C2-147 RECOVERED — was dark on 06-12 coupling test, back with fresh lease + 7-min uptime, healthy; was transient cold-bypass not a brick), root=D1-147 own/clean, **decoupled** (all e0-2 down). Was part of 06-12 coupled-test w/ 110 (port-cost TC storm + CCTV/ZFR outage — see findings/coupling_test_4736-110_119_2026-06-12/). Runtime test changes wiped by power-cycle. ⚠️ Coupler port-cost re-armed at template overflow value on next coupling until nv6 template fix lands. | ✅ clear | 2026-05-22 verified live: 18/18 sw v8-147 fw 7.4.2 ✅, 24/24 APs 6.11.2-0 ✅, vlan7 172.19.201.130/17 ✅. OBN 8/8+bug9 persisted. FW ping replies (uncommissioned — Stadler-side, not a Nomad blocker). **2026-06-24:** found `obn report` OOM-loop (60GB, 4×/24h) = OBN regressed to **9/11** (Bug10 BFS-guard + Bug11 wiped, on fresh run1 — likely promote/nd-obn refresh). This froze June-12 Zabbix alarms (publish dead). FIX: applied bug10+11 → **11/11**, persisted via NDSU chroot → run2 (ID 349), rebooted + verified 11/11 survived, `obn report` now exits 0 @ 16MB (was 60GB). Discovery timer re-enabled. See [[project_fzg147_4736119_obn_report_oom_bug10_wiped]]. ⚠️ Topology: 43 discovered ≠ 42 expected — possible stray/missing device, needs obn validate follow-up. |
| 4736-120 | 148 | `10.179.2.1` | 🟡 PAUSED — 2026-06-09 sess orch9: CCU dropped ~11:50Z (sustained, simultaneous with 4734-112 = consist/cellular outage). Gate 5 partial approved. PROGRESS: was mid apply_obn_patches (6/10→applying bugs 2,3,5,7,10). NOT yet promoted/rebooted — patches were live-fs only, may be wiped if CCU rebooted in the outage. REMAINING on resume: re-check OBN patch state, apply missing, promote (Gate 1, hand chroot to orchestrator), reboot, then 23-AP fw push (exclude Coach C AP3 = Stadler). vlan7 172.19.202.2/17 ✅, train_id=148 ✅, 18/18 sw v8-148 ✅. Last touched 2026-06-09 AR | 🟢 Coach2 AP3 recovered (cable reg #6 resolved 2026-05-22) | **2026-05-22 live check:** E3 coach power restored by Stadler — `nv6-E3-v8-148` now online at .181 ✅. `obn validate` (from stale discovery.prev): **18/18 sw all on nv6-X-v8-148 fw 7.4.2 ✅**. APs: 23/24 visible (Coach2 AP3 missing — not in DHCP); 15/23 at 6.11.2-0 ✅; 8 at `6.10.0-0 (6.11.2-0) ✗` = staged-not-activated (.221 .234 .225 .222 .220 .237 .223 .235). OBN patches: **0/8 on active run3** (vanilla — patches were in a different snapshot, not carried into run3). Active snap: run3/id45128. **2026-05-22 cable reg #6 resolved:** C2 e0-4 port bounce (`no configure`/`configure enable`) restored Coach2 AP3 — link UP 1000 Mb/s Full, active traffic, zero errors. Transient stall likely caused by Stadler E3 coach work. **Next:** (1) apply OBN patches via fix_obn.py → persist (Gate 1) → reboot (Gate 2); (2) serial `obn update f <ip>` for 8 staged APs to trigger partition swap. pre-flight 2026-06-09 orch10: UNREACHABLE on TCP/22 (re-dropped post-outage) — not dispatched; re-probe later. Last touched: 2026-05-22 AR |

### 4734 series (DOSTO NEU 4-car)

vlan7 IPs marked ✅ (PDF) are confirmed from the IP-Port-Allocation PDF; ❓ (expect ...) are computed but not yet verified on the live CCU.

| Train# | Fzg | CCU IP | Nomad status | Stadler status | Next action |
| --- | --- | --- | --- | --- | --- |
| 4734-101 | 1 | `10.179.4.1` | 🔴 **BLOCKED** | 🔴 E2↔B1 cable wrong-neighbour (cable reg #1) | wait for Stadler on register #1 (re-patch E↔B trunk) |
| 4734-102 | 2 | `10.179.6.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t6) |
| 4734-103 | 3 | `10.179.5.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP from control sheet 2026-05-21 (sheet: Done, v2/6.10.0, NC 2025.2.1); not yet probed |
| 4734-104 | 4 | `10.179.9.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t9) |
| 4734-105 | 5 | `10.179.30.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP merged from duplicate row 2026-06-30 (box1-t30) |
| 4734-106 | 6 | `10.179.31.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t31) |
| 4734-107 | 7 | `10.179.35.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP confirmed 2026-06-30 (box1-t35) |
| 4734-108 | 8 | 10.179.29.1 | 🟡 PAUSED — 2026-06-09 sess orch9: CCU dropped ~12:05Z mid AP-push (.231 reset by peer) in depot-wide rolling outage. PROGRESS: switches 12/12 v8-008 fw 7.4.2 ✅, OBN 9/10 persisted (run2/id333) ✅, train_id=8 directive persisted+rebooted ✅, vlan7 172.19.132.2/17 ✅, TFTP helper loaded. APs: 0/15 fw pushed (push could not execute — worker SSH-detach wall + then CCU outage). ROOT CAUSE of stall: obn update f takes 6-15min/AP; harness detaches worker SSH >90s → fire-and-idle; orchestrator must drive pushes, but CCU dropped on first attempt. RESUME: when CCU stable, drive 7 plain APs (.231/.223/.222/.219/.226/.221/.218) serial from orchestrator session via run_in_background; 8 m-variant stage-once-no-retry; skip 169.254.177.109. Last touched 2026-06-09 AR | ❓ | **2026-05-22 sess 1212Z DONE-PARTIAL:** (1) Recovered 2 stuck AP3s via A3/E3 e0-4 port bounce → 16/16 live. (2) Gate 3 obn update c sw → 12/12 v8-008 ✅. (3) Found + patched **OBN bug 10** (number_coaches BFS infinite-loop in report_dosto_neu.py; persisted via NDSU chroot). (4) Gate 4 AP fw push attempted on .229 — fw staged but never activated despite force-reboot; OBN's update.py has no post-reboot version verify. **Next session:** try LuCI HTTPS upload bypass on .229; if works, replicate for other 15 APs; then `obn update c ap` for coach 3+4 m-variant config. |
| 4734-109 | 9 | `10.179.38.1` | 🟢 **DONE — 12/12 sw v8-009; A1 switch REPLACED by Stadler + commissioned 2026-06-17** | ✅ clear (cable reg #10 RESOLVED) | **2026-06-17 AR:** Stadler **replaced the faulty A1 switch** (old A1 was mis-cabled at A1↔A3 coupler, reg #10). Replacement (`d0:c1:c0`, `.186`) came up factory; re-cabled correctly (e0-0→A3, e0-1→G1, e0-2→Fzg15 coupler — verified LLDP). Pushed `nv4-A1-v8-009` via `obn update c .186` (RRQ→reboot→persisted). **12/12 sw now `nv4-X-v8-009`**, RSTP single-root G1 unchanged + converged. cable reg #10 → RESOLVED. NOTE: had to runtime-patch OBN `tree.py` Bug-6 None-guard (cross-consist crash; absent on 2.2.23) — not persisted. Old A1 (`d0:8f:a0`) now isolated spare on A3 e0-2 coupler. L2 health/customer report not run (engineer deferred). — 2026-06-08 sess 1155Z: manual TFTP/SNMP bypass pushed v8-009 to 11/12 switches (A2/A3/B1/B2/B3/E1/E2/E3/G1/G2/G3 verified nv4-X-v8-009; RSTP single-root G1 d0:43:a0, FWD, clean). **A1 PM re-diagnosis (supersedes "misimaged"+"absent"):** A1 present+healthy, reached in-band via native-VLAN-1 workaround (192.168.1.2/24 on CCU bond0 untagged → SSH+SNMP to A1 @192.168.1.100). Root cause = **physical cable swap at A1↔A3 coupler**: A1 e0-0/e0-1 (vlan100 trunks) plugged into coupled Fzg-15 consist (nv4-A3/G1-v8-015); A1 e0-2 (coupler, VLAN5/15, no vlan100) faces this train's A3. → A1 vlan100 unreachable; ALL remote push transports (TFTP/HTTP/SCP) fail (0 outbound pkts). vlan100 NOT bridged across coupler — the vlan100-carrying trunk *cables* are on the wrong train. **✅ A1 config HAND-CORRECTED to train_id-9 in-band + persisted:** sent CLI inbound over native-VLAN-1 (hostname→nv4-A1-v8-009 + 27 DHCP deltas .135→.132/.7→.4); 0 train-15 left in running+startup; save running-config done. Does NOT restore service (still mis-cabled) — pre-stages config so post-recable A1 needs no push. **Fix = Stadler on-train RE-CABLE** (move A1 e0-0→Fzg9 A3, e0-1→Fzg9 G1, e0-2→real coupler; cable reg #10 has full as-cabled/as-designed map). Verify Fzg9+Fzg15 intended-coupled. Staged render at /data/auto-topology/upload/. OBN 10/10, train_id=9 Form-1, vlan7 ✅. Last touched 2026-06-08 PM AR |
| 4734-110 | 10 | `10.179.36.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP from control sheet 2026-05-21 (sheet: Done, v6/6.10.0, NC 2025.2.1); not yet probed |
| 4734-111 | 11 | `10.179.39.1` | 🟢 **DONE — 15/15 visible APs at 6.11.2-0; 12/12 sw v8-011; OBN 8/8** | ❓ | **2026-05-22 sess 0951Z DONE:** Gate 4 obn_update_f approved 10:05Z. nohup serial AP fw push: 14/15 visible APs activated to 6.11.2-0 by 11:09Z; final .228 (Coach4 AP2m) pushed by orchestrator at 11:20Z (was staged-not-activated) → 6.11.2-0 ✅. **15/15 visible APs at 6.11.2-0**, 12/12 sw v8-011 fw 7.4.2, OBN 8/8. Coach3 AP1 not present in validate — verify if expected (4-car nv4 spec). Last touched: 2026-05-22 AR |
| 4734-112 | 12 | `10.179.37.1` | 🟡 PAUSED — 2026-06-09 sess orch9: CCU dropped ~11:50Z (sustained >5min, with 4736-120 simultaneously = consist/cellular outage, NOT CCU fault). PROGRESS THIS SESSION (all persisted): OBN 10/10 (run2/id339) ✅, train_id=12 directive re-promoted+rebooted ✅ (was lost in 1st promote from stale work-subvol; fixed), 12/12 sw nv4-*-v8-012 fw 7.4.2 ✅, vlan7 172.19.134.2/17 ✅. REMAINING: read rpcFwFlash on 8 m-APs (.219/.220/.225/.226/.227/.228/.230/.233) → push only rpcFwFlash=0; plain APs already 8/8 at 6.11.2-0. Resume: re-probe, no re-promote needed. Last touched 2026-06-09 AR | ✅ clear | 2026-06-08 sess 0900Z: 12/12 sw v8-012 fw 7.4.2 ✅, OBN 9/9 (run2/id333) ✅, vlan7 172.19.134.2/17 ✅. 8/8 plain APs at 6.11.2-0 ✅. 8 m-variant APs (coaches 3+4: .222/.224/.225/.226/.228/.230/.232/.233) staged-not-activated — TFTP confirmed, won_t partition-swap after 4 reboots; deferred run-wide, R&D ticket candidate. Last touched 2026-06-08 AR |
| 4734-113 | 13 | `10.179.46.1` | 🟡 **PAUSED — chroot promote DONE (8/8 persisted incl bug9); reboot issued 10:18Z but CCU off-coverage since; next visit: verify reboot completed, then Gate 3 obn_update_c (3 v7m sw), Gate 4 AP fw push** | ❓ | 2026-05-22 live probe: 12/12 sw on vlan100 ✅, vlan7 172.19.134.130/17 ✅, FW ARP INCOMPLETE (path not fully established). `obn validate`: 9/12 sw on v8 config ✓; 3 sw still v7m (G1 .180, G3 .183, E3/E2 .190/.192) ✗; all 16 APs at fw 6.10.0-0 ✗. Next: (1) re-apply TFTP helper + bug9 runtime; (2) re-run `obn update c all` to push remaining 3 sw; (3) AP fw push serial. |
| 4734-114 | 14 | `10.179.44.1` | 🟢 DONE — 2026-06-09 sess orch9: 12/12 sw nv4-*-v8-014 fw 7.4.2 ✅, OBN 10/10 (run2/id331) ✅, train_id=14 directive persisted+rebooted ✅, vlan7 172.19.135.2/17 ✅, FW commissioned (Q1 ARP REACHABLE + Q2 ICMP-filtered). APs: 9/16 at 6.11.2-0 (+2 this session: .218/.219); 7 deferred (1 staged-not-activated .222 + 6 m-variant R&D wall). Last touched 2026-06-09 AR | ✅ clear | 2026-06-08 sess 0900Z: 12/12 sw v8-014 fw 7.4.2 ✅, OBN 10/10 (run1/328) ✅, vlan7 172.19.135.2/17 ✅. 7/16 APs at 6.11.2-0 (incl 2 m-APs that activated). 9 APs staged-not-activated after 1 obn update f attempt — deferred run-wide (partition-swap failure, R&D ticket). Last touched 2026-06-08 AR |
| 4734-115 | 15 | `10.179.61.1` | 🟢 DONE-PARTIAL — 12/12 sw v8-015, 9/16 APs at 6.11.2-0; 6 deferred (staged-not-activated) | ❓ | 2026-06-08 sess 0900Z: 12/12 sw nv4-XX-v8-015 fw 7.4.2 ✅ (orchestrator drove last 2 E2/E3 after worker stalled), OBN 8/8 (run2/308) ✅, train_id=15 ✅, vlan7 172.19.135.130/17 ✅. AP fw via BATCH obn update f (helper applied): 9/16 at 6.11.2-0; 6 deferred staged-not-activated (.229 AP1, .232/.231 AP2m, .221/.223 AP4m, .233 AP3m) — partition-swap wall, R&D ticket. Last touched 2026-06-08 AR |
| 4734-116 | 16 | `10.179.3.1` | 🔵 IN PROGRESS — stage push_switch_config (8/12+, t+6600s), hb 2026-06-09T16:02Z, sess 1421Z — Gate 3; CCU-detached `obn update c all` (PID 640571) STILL RUNNING ON CCU (last seen 8/12 v8, A-coach pushing leaf-first). FLEET-WIDE SSH/TCP-22 DOWN ~16:00Z (ICMP still UP → likely local SSH egress block/rate-limit, NOT CCU fault). Detached push continues regardless; re-attach to verify 12/12 when SSH restored. Then 2nd promote (vlan7) + LuCI AP bypass. | ❓ | initial visit — CCU IP from control sheet 2026-05-21 (sheet: Done, v7/6.10.0, NC 2025.2.1); not yet probed |
| 4734-117 | 17 | `10.179.14.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP from control sheet 2026-05-21 (sheet: Done, v7/6.10.0, NC 2025.2.1); not yet probed |
| 4734-118 | 18 | `10.179.48.1` | ⚪ UNKNOWN | ❓ | initial visit — CCU IP from control sheet 2026-05-21 (sheet: Done, v6/6.10.0, NC 2025.2.1); not yet probed |
| 4734-119 | 19 | `10.179.45.1` | 🟢 **DONE** | ✅ clear | done — 16/16 APs ✅, 12/12 sw ✅, vlan7 ✅. vlan7 `172.19.150.130/17` is train_id-45 convention (correct; do not fix). State-inventory OBN 3/8 = false-negative; confirmed 8/8 via `dosto-obn-patches --check`. |
| 4734-120 | 20 | `10.179.49.1` | 🟢 **DONE** | ✅ clear | done — 12/12 sw + 16/16 APs ✅, vlan7 ✅. State-inventory OBN 3/8 = false-negative; train_id template claim also false-negative (verify via `cat /etc/obn/template/nv4-*.cfg` if in doubt). |
| 4734-121 | 21 | `10.179.50.1` | 🟢 **DONE** | ✅ clear | done — 8/8 OBN markers confirmed (run2/id297); state-inventory 4/8 was false-negative. 12/12 sw + 16/16 APs ✅, vlan7 ✅. **2026-06-24 AP channel investigation (Anton "WE vertauscht" B&E):** confirmed band plan does NOT alternate per coach (live A,G=non-m / E,B=m per rules.yaml `[1,2]/[3,4]` half-split). Root cause = rules.yaml coach-grouping bug in canonical nv4 template (fleet-wide), NOT cabling/OBN-runtime. Supersedes 2026-06-03 wirelessFreq theory. Evidence: findings/fzg21_4734-121_ap_channel_plan_2026-06-24.md. Fix blocked on Stadler 5 GHz anchor; fix in template via R&D, not per-train. |
| 4734-190 | 90 | `10.179.54.1` | 🟡 PAUSED — 2026-06-10 0610Z orchestrate sess: reached Gate 4 (await_obn_update_f), engineer ended session before approval, NO fw pushed. Live state verified this session: 12/12 sw v8-090 ✅, OBN 11/11 ✅, TFTP helper re-applied (runtime, wiped on reboot), vlan7 172.19.173.2/17 ✅, subvol run1 id335. 16/16 AP visible (coach4 AP1m .229/.230 present after all). RESUME: push 8 APs 6.10.0-0→6.11.2-0 = .218 .221 .223 .226 .227 .229 .230 .231 (8 already at target). obn batch flash-hangs on these RT-610; LuCI 2-step flashops bypass proven on .219. Orchestrator must drive each obn update f via run_in_background (worker SSH-detach wall). Last touched 2026-06-10 AR | ✅ 12/12 sw + 16/16 AP all present; consist fully cabled (LLDP-verified) | 2026-06-02: **UNBLOCKED.** G2 e0-0 trunk now CONNECTED (LLDP: G2 e0-0 → nv4-G3-v8-090) — was the Stadler cabling fault that blocked this train since 2026-05-22; full 12-switch LLDP sweep confirms every e0-0/e0-1 inter-coach trunk has a correct neighbour, no missing/miscabled ports. obn discover+report+validate all run clean: 12/12 sw at fw 7.4.2 ✅ + config nv4-*-v8-090 ✅. **OBN now 10/10 persisted (run1/id335)** — bug 10 (BFS guard) was MISSING (box was 9/10); earlier today found obn report hung @99.9% CPU / 47GB RSS, killed it, applied + persisted bug 10 via NDSU chroot + safe_reboot; obn report/validate no longer hang. RCA: findings/RCA_obn_report_bfs_infinite_loop_2026-06-02.md. train_id=90 hardcoded in 12 nv4-*.cfg ✅, vlan7 172.19.173.2/17 ✅, nd-systemupdate .dont ✅. REMAINING (Nomad): 15 APs on Nomad config ✅ but fw 6.10.0-0 ✗ (target 6.11.2-0). Next: dosto-tftp-helper-check, then Gate 4 AP fw push (15 APs serial 6.10.0-0→6.11.2-0). Switches need no further work. pre-flight 2026-06-02 13:08Z: 9/12 sw + 13/16 AP — 3 sw dropped post-outage, coaches re-joining, not dispatched (re-probe later). |
| 4734-122 | 22 | `10.179.53.1` | 🟡 PAUSED — 2026-06-10 0610Z orchestrate sess: reached Gate 4 (await_obn_update_f), engineer ended session before approval, NO fw pushed. Live state verified this session: 12/12 sw v8-022 ✅, OBN 11/11 ✅ (path /usr/share/obn/lib/), TFTP helper re-applied (runtime, wiped on reboot), vlan7 172.19.139.2/17 ✅. RESUME: push 3 residual m-APs 6.10.0-0→6.11.2-0 = .218(AP4m) .222(AP2m) .223(AP3m) — .219 self-activated since last session. ⚠️ iptables nf_tables backend → CT helper rule may be silent no-op; single-AP .218 first, check /proc/net/nf_conntrack_expect during RRQ, fall back to native nft CT rule if empty. .233 still physically absent (Stadler scope, do not push). Last touched 2026-06-10 AR | 🔴 .233 missing (no lease, ARP FAILED, not on factory 192.168.1.x) — physical/cabling, Stadler scope | 2026-06-09 re-probe (CCU rebooted, uptime 22min, runtime patches WIPED): 12/12 sw v8-022 ✅. AP state changed vs 2026-06-08 — several "deferred" self-recovered on power-cycle (case-a). NOW: 12/15 at 6.11.2-0; **3 still 6.10.0-0 = .219(AP4m) .222(AP3m) .223(AP2m), all rpcFwFlash=0 (idle/nop, NOT hung — never pushed), RT-610-LV, Nomad config, LuCI :443 open → ready for normal push**. **.233 ABSENT: no DHCP lease, ARP FAILED, 100% ping, not on 192.168.1.x, all 12 sw healthy → powered-off/disconnected/dead AP or down port, NOT a fw issue**. 2026-06-08 base: OBN 10/10, train_id=22, vlan7 172.19.139.2/17. Next: push .219/.222/.223; inspect .233 physically. **2026-06-09 ~07:40Z: TIER-2 BATCH TEST STAGED but consist fabric dropped mid-launch — vlan100 went fully dark (0 sw / 0 AP, both ping DOWN) while CCU stayed UP (uptime 42min, SSH fine) = consist-side power/backbone flap, APs likely rebooting together. `obn update f ap` launched into empty fabric → exited silently (0-byte log), nothing pushed. PREREQS STILL APPLIED (CCU never rebooted): bug11 marker=1, TFTP helper loaded + CT rule, conntrack udp_timeout=180 — all in place for resume, NO re-prep needed unless CCU later reboots. RESUME: wait for fabric to re-present, re-probe the 3 (.219/.222/.223 may have self-activated on the power-cycle — recheck fw first), then run `obn update f ap` for the clean Tier-2 batch validation (0 Connection-refused = Tier-2 confirmed). Last touched 2026-06-09 AR |
| 4734-123 | 23 | `10.179.67.1` | ⚪ UNKNOWN — discovered 2026-06-09 (auto-sweep); partial ID done, CCU dropped mid-inventory | ❓ | **2026-06-10 sess (AR): single-promote chroot → run2 (subvolid 300), rebooted, verified.** (Overwrote stale sess-0610Z IN PROGRESS claim, hb 06:05Z — that session never reported.) Found nd-obn **2.2.23** = R&D-upstreamed build, NEW `lib/` source layout: bugs 1–10 fixed natively — marker greps for bug9 `_SNMP_DISPATCH_LOCK` / bug10 `NDP-PATCH-BUG10-BFS-GUARD` are FALSE NEGATIVES on this version (native BFS guard lives at report_dosto_neu.py ~282 commented "Bug 9 fix: only enqueue resolved devices"). **Bug 11 (westermo fw-verify) was the ONLY missing patch** → applied via /var/tmp/fix_obn_bug11_westermo_fw_verify.py in chroot, marker=1 post-reboot. nv4 templates were Form-2 with **NO train_id directive at all** (line 1 = hostname; `backbone-discovery.yaml: train_id: 67` would be the rendered value = TRAP) → prepended `{%- set train_id = 23 -%}` to all 12 in same chroot. vlan7 `172.19.139.130/17` correct + already pinned in nmconnection; FW `.129` ARP REACHABLE (Q2 ICMP / Q3 TCP not yet run). Post-reboot verify: bug11 marker 1 ✅, directive 12/12 ✅, `obn discover` + `obn report` exit 0 (BFS guard live), `obn validate -t sw` 12/12 ✓ all `nv4-X-v8-023` @ 7.4.2 ✅. STILL PENDING: AP fw/config pass (16 APs), TFTP CT helper (runtime fix wiped by reboot — re-apply before any AP fw push), Phase-6 Q2/Q3, full L2 health, allocation PDF folder absent (`train-ip-allocation-commission/4734-xxx/4734-123/`). Last touched 2026-06-10 AR |

### 4706 series

Different platform from 4734/4736 NEU; discovered on the management VLAN as part of the 2026-05-20 morning-brief sweep, populated from the Fleet Control Sheet (2026-02-11).

| Train# | Fzg | CCU IP | Nomad status | Stadler status | Next action |
| --- | --- | --- | --- | --- | --- |
| 4706-101 | 189 | `10.179.20.1` | ⚪ UNKNOWN | ❓ | sheet `Investigate`; initial visit. CCU IP corrected 2026-06-30: was wrongly `10.178.20.1`, true IP is `10.179.20.1` (box1-t20). |
| 4706-102 | 190 | `10.179.15.1` | ⚪ UNKNOWN | ❓ | CCU IP confirmed 2026-06-30: `10.179.15.1` (box1-t15) IS this train. ⚠️ Supersedes 2026-06-15 note that had excluded it — box1-t15 was found misimaged (broken `128+box-id(15)=143` formula → hostnames `nv6-*-v7-143` + vlan7 199.130, colliding with real 4736-115/Fzg143 at box18). The misimage stands as a commissioning fix item, but the box↔train identity is now confirmed. See findings/dosto_train_list_2026-06-15.md. |
| 4706-103 | 191 | `10.179.17.1` | 🟡 **PAUSED — 18/18 sw v8-191 ✅; 23/24 APs need fw push 6.10.0-0→6.11.2-0** | 🔴 1 AP missing (DHCP absent — Stadler cabling item) | **pre-flight 2026-05-22 sess 0834: 0 sw / 0 AP on vlan100 — consist offline; not dispatched.** **2026-05-22 initial visit:** OBN 9/9 persisted (run1 incl bug9) ✅, train_id=191 ✅, vlan7 172.19.223.130/17 ✅. Gates 1+2+3 complete — **18/18 sw on nv6-*-v8-191 fw 7.4.2-RC1** ✅. 23/24 APs visible all at 6.10.0-0 → need 6.11.2-0. Coach 2/2 (.234) has `incomplete` config — run `obn update c 10.179.17.234` first, then serial AP fw push (`obn update f <ip>` × 23). Re-apply TFTP helper on reconnect. Stadler FW 172.19.223.1 ARP FAILED (not commissioned — Stadler item, not Nomad blocker). Last touched: 2026-05-22 AR |

### 4705 series

| Train# | Fzg | CCU IP | Nomad status | Stadler status | Next action |
| --- | --- | --- | --- | --- | --- |
| 4705-101 | 229 | `10.179.42.1` | ⚪ UNKNOWN | ❓ | **2026-05-22 sess 0834: orchestrator pre-flight blocked — dosto-commission-train does not enumerate 4705 platform (only 4-car/6-car); switch hostname prefix fv5-* + ~14-15 sw observed suggest non-standard consist family. Skill update needed before commissioning.** sheet `Done`; initial visit — was previously attributed to Fzg 13 in error |
| 4705-102 | 230 | `10.179.43.1` | ⚪ UNKNOWN | ❓ | sheet `Done`; initial visit |
| 4705-103 | 231 | `10.179.41.1` | ⚪ UNKNOWN | ❓ | **2026-05-22 sess 0834: orchestrator pre-flight blocked — dosto-commission-train does not enumerate 4705 platform (only 4-car/6-car); switch hostname prefix fv5-* + ~14-15 sw observed suggest non-standard consist family. Skill update needed before commissioning.** sheet `Done`; live CCU confirmed at `.41.1` (switch hostnames `fv5-*-v3-231`); control sheet had `.42.1` typo (duplicate with 4705-101) |

---

## 2026-05-21 status check drift summary

12 reachable trains were checked via parallel `dosto-state-inventory` + `dosto-device-discovery` subagents (read-only). Key findings:

**Fleet-wide pattern resolved 2026-05-21: `dosto-state-inventory` has a stale marker-grep for bugs 2/3/5/7 — false-negative, not a real regression.** Confirmed via `dosto-obn-patches --check` on Fzg 21: all 8 markers present (counts 1, 2, 1, 1, 1, 1, 1, 1), patches genuinely persisted in `/.snapshots/run2`. Same false-negative applies to every train in this report — when state-inventory says "OBN 4/8 (bugs 2/3/5/7 absent)" treat as suspect. Real patch state requires `dosto-obn-patches --check`. The fix belongs in state-inventory's grep patterns; no CCU action needed. See [[project_state_inventory_marker_false_negative]].

**vlan7 FW ARP `.129` instead of `.1`** observed on Fzg 139 and Fzg 147 (same Westermo MAC family). Likely a Stadler routing/IP pattern worth investigating.

**Per-train trail of new findings** (full detail in row "Next action" cells):
- **Fzg 136** — positive drift: 18/18 sw + 24/24 APs visible (was 2 sw + 9 APs on 2026-05-19). Cable register #2/#3 may be Stadler-resolved — verify with LLDP topology check.
- **Fzg 139** — 3/18 switches already on v8-139 (C3, B2, B3); status row updated from UNKNOWN to PAUSED.
- **Fzg 143** — batch experiment **final result: 8/24 at 6.11.2-0 (33%)**. OBN regressed 8/8 → 4/8.
- **Fzg 144** — **OBN patch regression 8/8 → 4/8** (btrfs id changed 303 → 306 — a promote happened). 9/23 APs at 6.11.2-0. Coach 6 AP3 now visible (register #6 may be self-resolved). Coach 6 AP4 firmware `incomplete`.
- **Fzg 147** — AP hostnames now Nomad-form (no longer factory `RT610LV-dosto-*`). vlan7 ARP `.129` anomaly.
- **Fzg 148** — E3 coach still off (confirmed). OBN regressed 8/8 → 4/8 (new info).
- **Fzg 12** — first real visit at corrected IP 10.179.37.1: fully wired, 0/8 OBN patches (genuine fresh-CCU).
- **Fzg 13** — first real visit at corrected IP 10.179.46.1: switches on v7 config (not v8). All APs plain `AP*-v1` (no m-variants — worth verifying nv4 expected).
- **Fzg 19** — AP firmware push confirmed 16/16 at 6.11.2-0 ✅. vlan7 `172.19.150.130/17` is the train_id-45 Nomad-internal convention (NOT Fzg-19 formula) — confirmed correct per detail block; do not "fix".
- **Fzg 20** — DONE; active subvol is run1/id297, not run2/id294 where patches were persisted (informational).
- **Fzg 21** — DONE; OBN markers 4/8 reported by state-inventory was a false-negative (canonical check shows 8/8).
- **Fzg 137** — matches BLOCKED state; first-visit unpatched as expected.

## Per-train detail

One block per train that's been touched or has known state. Fields under each block:

- **OBN patches** — `10/10` all bug fixes applied · `7/10` only `fix_obn.py` applied (covers 1–7) · `0/10` vanilla CCU · `persisted` = baked into btrfs run<N> via `nd-systemupdate.sh shell` (survives reboot). **NOTE 2026-05-22:** target was `8/8` before bugs 9 (pysnmp Lock) and 10 (BFS hang guard) were added. Historical entries below say `8/8` — treat them as 8/8-of-the-then-known-bugs, NOT current target. Re-check at next visit with `/dosto-obn-patches <ccu-ip>` to confirm 10/10. **UPDATE 2026-06-09:** current target is now **11/11** (bug 11 = AP-fw activation verify, added 2026-06-09). A live re-check of 4736-110 found its row's "8/8+bug9 persisted" claim was actually **9/11** on the CCU — persisted at the old baseline before bug10/11 existed. **Fleet implication:** any row claiming `8/8`/`9/9` (pre-bug10) is silently ≤9/11 and needs bug10+bug11; any row claiming `10/10` (pre-bug11) is silently ≤10/11 and needs bug11. Pre-bug10 candidates (14): 4706-103, 4734-111/112/113/115/119/121, 4736-102/103/104/111/115/118/119. Pre-bug11 candidates (6): 4734-109/114/122/190, 4736-108/116. These are row-claims, not live readings — verify each via `dosto-obn-patches --check` when the CCU is next online and top up via chroot promote. Low urgency (bug10 only bites on `obn report` of an incomplete consist; bug11 only on `obn update f ap`).
- **Switches v8** — target `18/18` (6-car) or `12/12` (4-car); `mixed` = some v3/v4 + some v8 (RSTP storm risk)
- **APs** — target firmware `6.11.2-0`, config `v1`; `factory` = some/all in `RT610LV-…-v1-FD` (need LuCI bypass)
- **vlan7** — formula `172.19.<128+Fzg//2>.<2 if even else 130>/17`; persists in `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection`
- **Stadler cabling** — ✅ clean topology · 🔴 cable fault open · ❓ not yet checked
- **FW reach** — TCP probe to the train's `172.19.<octet3>.1` (Stadler firewall, host `.1`)
- **Last touched** — `YYYY-MM-DD <initials>`

> L2 health checks and customer reports are no longer part of the commissioning pipeline. They remain available as optional engineer-invoked skills (`/dosto-l2-health`, `/dosto-l2-report`) but don't gate a train's DONE status and aren't tracked as diagnostic-state fields.

---

### Fzg 130 — 4736-102 — 🟡 PAUSED (3 switches need config push; 24 APs need fw upgrade)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.47.1` (`box1-t47`) · **Last touched:** 2026-05-12 AR

**Diagnostic state:**
- **OBN patches:** ✅ 8/8 patched (persisted in run1; bug 6 count=2 per audit F7)
- **Switches v8:** 🟡 18/18 visible and reachable; 15/18 on correct `nv6-*-v8-130` config; **3 still on `-man` config** (`.180` E1, `.186` B1, `.187` F1) — need `obn update c` in leaf-first order
- **APs:** 🟡 24 APs visible, all correct Nomad config, all on `6.10.0-0` (target `6.11.2-0`) — firmware upgrade not yet started
- **vlan7:** ✅ `172.19.193.2/17` live (run1, post-reboot verified)
- **Stadler cabling:** ✅ 18/18 switches visible — D2/E2/E3/F2 returned; no cable fault (prior BLOCKED state lifted)
- **FW reach:** ✅ **commissioned** (2026-05-12 confirmed): ARP REACHABLE `00:90:e8:bb:9d:67`, ICMP 100% loss = Stadler policy drop per Phase 6 Q2; TCP 80+22 OPEN
- **TFTP helper:** 🟡 runtime fix applied this session (in-memory only — re-apply after any CCU reboot before AP fw push)

**OBN workflow:** always run `sudo obn discover && sudo obn report` before any `obn update c` or `obn validate` — OBN reads from `discovery.prev.json` (committed report snapshot), not raw `discovery.json`. Skipping `obn report` causes stale data / "readonly" false-positive. See [handoff-fzg130-2026-05-12.md](handoff-fzg130-2026-05-12.md).

**Next session — first commands:**
```bash
lsmod | grep nf_conntrack_tftp   # re-apply if missing
sudo python3 -c "import json; d=json.load(open('/tmp/discovery.prev.json')); print(len(d.get('devices',[])), 'devices')"
# If < 43: sudo obn discover && sudo obn report
sudo obn update c 10.179.47.180  # leaf
sudo obn update c 10.179.47.186  # leaf
sudo obn update c 10.179.47.187  # middle node — try without --allow-non-leaf first
# Then: 24 × AP firmware push serially
```

Session-specific narrative: see [fleet-journal.md#fzg-130--4736-102](fleet-journal.md) and [handoff-fzg130-2026-05-12.md](handoff-fzg130-2026-05-12.md).

---

### Fzg 131 — 4736-103 — 🟡 PAUSED (awaiting Stadler on F3 AP3m + B2 null fw)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.11.1` (`box1-t11`) · **Last touched:** 2026-05-11 AR

**Diagnostic state:**
- **OBN patches:** ✅ 8/8 applied to subdir layout `/usr/share/obn/lib/device/vendor/` (live run2); **persisted to run3 via chroot promote** (subvol id 795, gen 68260). Activates on next reboot.
- **Switches v8:** 🟡 18/18 on `nv6-X-v8-131` config; 17/18 fw `7.4.2`; **B2 (10.179.11.197, a0:59:3a:d0:48:00) reports null firmware** — confirmed via fresh `obn discover` (not stale-file artefact). SNMP firmware-OID read selectively failing.
- **APs:** 🔴 23/24 visible; **AP3m on coach F missing** (F3 e0-4 link UP @ 1G/full but RX bytes/pkts = 0 since boot, no LLDP neighbour). B3 + E3 AP3m's present. All visible APs on fw `6.10.0-0` (target `6.11.2-0`).
- **vlan7:** ✅ `172.19.193.130/17` (live + nmconnection both correct for odd Fzg/host-130)
- **Stadler cabling:** ✅ inter-coach fabric clean — full LLDP sweep 2026-05-11 confirms 36/36 e0-0/e0-1 trunks match nv6 template exactly (no cross-wires). Prior "E3/F3 hostname mismatch" finding withdrawn — was a misread of valid topology. 🟡 D3.e0-2 (OBS trunk) sees CCU itself as LLDP peer while D1.e0-2 is silent — possibly D1↔D3 OBS roles swapped at install; not a fault, worth confirming with OBS installer.
- **FW reach:** ❓ not tested this session

**2026-05-11 session work:**
- Found `nd-obn 2.2.23` uses subdir layout (`/usr/share/obn/lib/device/vendor/vdsrail.py` etc.) — `fix_obn.py` `Path()` constants already target this layout (lines 25-29), so no script changes were needed. v2.2.23 ships **0/8 fixes natively** — all 8 patches were absent, none upstreamed.
- Applied `fix_obn.py` + `fix_obn_bug8.py` live (run2): 8/8 PATCHED.
- Removed `/usr/sbin/nd-systemupdate.sh` (per engineer); only `.sh.dont` remains.
- Fixed `train_id` template in all 18 `/etc/obn/template/nv6-*.cfg` from broken `{%- set train_id = 128 + train_id -%}` formula to hardcoded `{%- set train_id = 131 -%}`.
- Chroot promote via `sudo /usr/sbin/nd-systemupdate.sh.dont shell`: re-applied all 3 changes inside chroot, confirmed `nd-systemupdate.sh` was present in chroot from `release` baseline (proved CLAUDE.md "chroot starts fresh from release" — re-removed). New subvols: `release` id 794, `run3` id 795.

**For Stadler (open items):**
- **F3 coach AP3m missing** — switch F3 (10.179.11.203) port e0-4 link UP at 1G/full but zero RX since boot; no LLDP. Cable likely OK (link comes up); check **PoE flow** and whether AP3m is physically installed/powered.
- **B2 (10.179.11.197) null firmware** — config push fine, firmware SNMP read failing. Check snmpd on B2 or ACL.

**Internal observation (not Stadler):**
- **D3.e0-2 (OBS trunk) sees CCU as LLDP peer; D1.e0-2 silent** — expected pattern is the opposite. Possibly D1↔D3 OBS roles swapped at install. Both ends inside consist; not an L2 fault. Confirm with OBS installer when convenient.

**Next actions for next session (no Stadler needed):**
1. Reboot CCU to activate run3 (or wait for natural reboot — patches+template+`.sh` removal persist there).
2. Re-apply TFTP CT helper runtime fix post-reboot before any AP firmware push.
3. After Stadler fixes F3 AP3m: push AP firmware 6.10.0-0 → 6.11.2-0 on the 23 visible APs (serial; per handoff lesson 11).
4. After Stadler responds on B2 null fw: re-check; if real, may need switch reboot or config re-push.

---

### Fzg 132 — 4736-104 — 🟡 PAUSED (train offline; D4 BLOCKED Stadler)

**Status:** 🟡 **PAUSED — train offline; D4 still BLOCKED on Stadler** · **CCU:** `10.179.10.1` (`box1-t10`) · **Last touched:** 2026-05-09 AR

**Diagnostic state:**
- **OBN patches:** ✅ persisted (run1, ID 314)
- **Switches v8:** ✅ 18/18 SW + 18/24 AP fw
- **APs:** 🔴 23/24 (D4 missing)
- **vlan7:** ✅ `172.19.194.2`
- **Stadler cabling:** 🔴 D3.e1-2 (AP D4) link DOWN
- **FW reach:** ✅ 80/22 OPEN

Topology validated against [`_shared/nv6-topology.md`](train-ip-allocation-commission/extracted/_shared/nv6-topology.md) — every predicted trunk and AP location matches LLDP, except AP D4.

**End-state (after 2026-05-09 evening session — partial AP firmware push):**
- ✅ OBN patches **8/8 persisted** in active snapshot `/.snapshots/run1` (subvol ID 314, gen 136390)
- ✅ `train_id = 132` hardcoded in all 18 nv6-*.cfg templates (mar5-compliant, no `128 +` formula)
- ✅ vlan7 = `172.19.194.2/17` (live and persisted; matches formula for Fzg 132 even/device-2)
- ✅ Stadler firewall TCP-reachable on vlan7 (port 80 OPEN, port 22 OPEN)
- ✅ 18/18 switches reachable, all on `nv6-*-v8-132`, all on firmware `7.4.2`
- ✅ Inter-coach trunks (sampled A1, A3, D1, D3, B1, B3) all match expected LLDP peers
- ✅ A3 e1-4 sees Stadler firewall (`firewall.networ` MAC `00:90:e8:ba:0e:bf`)
- ✅ `nd-systemupdate.sh.dont` rename preserved across both promotes — auto-update timer harmless
- ✅ All 23 visible APs on correct per-MAC config (`AP*-v1-...` / `AP*m-v1-...`)
- ✅ TFTP CT helper runtime fix applied 2026-05-09 15:40 UTC (in-memory only — re-apply if CCU rebooted during outage)
- 🟡 **AP firmware: 18/24 on target `6.11.2-0`** (was 15/21 at session start). Two stuck APs unblocked this session: `.226 → 6.11.2-0` (143s), `.230 → 6.11.2-0` (636s). Both via the dosto-ap-firmware-update --execute state machine: push → RRQ verify → 15-min poll → completion.
- 🟡 `.231` indeterminate. Push fired at 16:02 UTC, RRQ verified at 16:02:32, mid-activation reboot at t+334s. Cellular outage hit at t+919s (15-min poll exhausted), AP never returned SNMP-responsive within budget. `obn validate` last showed `6.10.0-0 (6.11.2-0) ✗` (staged-but-not-activated pattern, handoff lesson 16). May have completed offline. **Monday: run `sudo obn discover` first; if `.231` shows `6.11.2-0`, mark complete; if still staged, force-reboot.**
- 🟡 Outstanding: `.237 .238 .240` (AP2-v1, AP1m-v1, AP2m-v1) not yet attempted.
- 🔴 **23/24 APs visible — Coach D AP4 missing.** D3.e1-2 link DOWN, no LLDP peer, no MAC learned. PoE cycle test confirmed physical-layer fault (PoE flowing 2.5W class-3 but PHY never negotiates). Cable register row #5.

**Discovered during commissioning (lessons that fed back into the playbook):**
- The first chroot promote silently *reverted* the train_id template fix and the vlan7 nmconnection edits because they had only been applied to the live `run1` (not to `release` or `work`). The chroot starts fresh from `release`, so any in-place fix on the running snapshot dies on the first promote unless re-applied inside the chroot. **Procedure update**: any per-train hand fix must be re-applied inside `nd-systemupdate.sh.dont shell` to persist. Required two-step promote on this train (OBN first, then template+vlan7).
- `nd-systemupdate.sh` is renamed `.dont` fleet-wide as a defensive freeze against the nightly auto-update timer pulling vanilla OBN from Puppet env `dostoneu_migration_mar5` (no patches yet). Invoke by full filename: `sudo /usr/sbin/nd-systemupdate.sh.dont shell`. Do NOT remove the rename until R&D upstreams the patches. See handoff.md "Open questions" for the R&D nag note.
- box1-t1 (Fzg 133) currently has `nd-systemupdate.sh` at the canonical name — **exposed to auto-update**, will clobber its `persisted (run3)` patches on next Sun/weekday-night cycle. Re-rename to `.dont` on next visit.
- **AP firmware push reliability: parallel `obn update f ap` is unreliable.** Initial 15-AP parallel batch had only ~5 actually flash. Root cause: CCU firewall lacks the TFTP conntrack helper rule; iptables-nft compat shim silently fails to attach `CT --helper tftp`. Runtime fix is in-memory only (`sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp`); validated end-to-end this session by 3 successful single-AP RRQs. Documented in [troubleshooting-runbook.md](troubleshooting-runbook.md) "CCU Firewall — TFTP conntrack helper missing".
- **dosto-ap-firmware-update skill bugs found and fixed this session:** (1) standalone `snmpget` precondition was too strict — false-positive `ap_in_factory_config` on Nomad APs that OBN's SNMP library polls fine. Fixed: read `/tmp/discovery.json` for AP reachability instead. (2) `journalctl --since` rejected ISO-8601 with `+00:00` offset, masking real RRQ-verification successes. Fixed: use `date +"%Y-%m-%d %H:%M:%S"` instead. Both fixes shipped to the SKILL.md.

**Next actions for Monday (no Stadler needed for these):**

1. SSH to CCU; verify uptime — if rebooted since 2026-05-09 evening, **re-apply TFTP CT helper runtime fix first**:
   ```bash
   sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp -m comment --comment "TFTP conntrack helper for in.tftpd (runtime fix)"
   ```
2. `sudo obn discover && sudo jq -r '.[] | select(.ip=="10.179.10.231") | .firmware' /tmp/discovery.json` — if `6.11.2-0`, AP completed offline; mark .231 done. If still `6.10.0-0`, force-reboot via `ssh nomad@10.179.10.231 reboot`, wait 90s, re-poll for activation.
3. Push remaining 3 APs serially: `.237 .238 .240`. Use `/dosto-ap-firmware-update <ccu> <ap> --execute` with the fixed snmpget + journalctl recipes. ~10-15 min per AP × 3 = ~30-45 min.
4. After 24/24 APs (well, 23/24 — D4 still missing) on target firmware: update fleet-status row and Confluence, file customer report.

**Stadler-dependent (cannot proceed without):**
- ❌ Do NOT run `obn update c all` or `obn update f all` (broad target) until Stadler replaces D4 cable. Pushing now would leave D4 in pending state when it eventually comes online.
- 🔧 Wait for Stadler on cable register row #5: replace D3.e1-2 cable first, swap AP second.
- After Stadler completes: revisit, re-run device discovery to confirm 24/24, then run `obn update c <D4-IP>` and `obn update f <D4-IP>` for the new AP, then `/dosto-l2-health` for the customer baseline.

---

---

### Fzg 136 — 4736-108 — 🟡 PAUSED (Stadler register #2/#3 likely resolved)

**Status:** 🟡 **PAUSED — Stadler register #2/#3 likely resolved (verify with LLDP)** · **CCU:** `10.179.8.1` (`box1-t8`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** 🔴 **NOT applied** — vdsrail.py is 165 lines (vanilla 2.2.23); bugs 1+2 partially present but bugs 3–8 absent; `fix_obn.py` not on CCU. Active snapshot: `run1`.
- **Switches v8:** 🟡 **partial / train offline** — DHCP leases show 5 switches registered (`A1`, `A3`, `C3`, `D1`, `F1`) but ALL ping DOWN. OBN validate shows only 2 switches (D1=`.195` incomplete, C3=`.178` fw `7.4.2`). 13/18 switches not visible.
- **APs:** 🟡 9 APs in DHCP leases (all `AP*-v1` named → correct Nomad config), none pingable right now. Firmware unknown.
- **vlan7:** ✅ `172.19.196.2/17` live and correct (Fzg 136 even → `.2`)
- **Stadler cabling:** 🔴 C3 trunks swapped (`e0-0`/`e0-1`) + D1↔E2 inter-coach missing (register #2 + #3)
- **FW reach:** 🟡 **path partial** — ARP DELAY for `172.19.196.1` (MAC `00:90:e8:c2:60:22` Westermo ✅), ICMP 100% loss = commissioned per Phase 6 Q2, but TCP 80+22 = **No route to host** (routing issue, not FW policy). Investigate.
- **nd-systemupdate:** ✅ renamed `.dont`
- **train_id in templates:** ✅ hardcoded `136` in nv6-*.cfg

**Train state 2026-05-19:** Train appears mostly powered off — all switches ping DOWN despite recent DHCP leases. Only CCU is reachable. This is expected if consist is in depot/powered-down state.

**2026-05-21 status check (read-only):** Train now substantially powered up. **18/18 switches and 24/24 APs visible in DHCP** (was 5 switches DHCP + 9 APs on 2026-05-19, all switches DOWN). Cable register #2 (C3 trunk swap) and #3 (D1-E2 inter-coach) may have been resolved by Stadler — NOT verified via LLDP yet. Run `lldp_topology_check.py` adapted for 6-car as next session's first step; if 0 mismatches, proceed to OBN patch + v8 push. All 24 APs report plain `AP*-v1` hostnames (zero m-variants) — count is correct for 6-car but the absence of m-variant naming is unusual; verify with `obn discover` whether APs received coach-differentiated config or all got uniform template.

**Cable register items blocking v8:**
- **#2** — C3 (`nv6-C3-v8-136`, `.183`) trunks swapped on `e0-0` / `e0-1`
- **#3** — D1↔E2 inter-coach cable missing

**Action when Stadler confirms re-cable:** copy `scripts/lldp_topology_check.py` to CCU `/tmp/`, edit `SWITCHES`/`EXPECTED_TOPOLOGY` for this consist (6-car), run with `python3`. Expect 0 mismatches. Then:
1. SCP `fix_obn.py` to CCU `/tmp/` and run `sudo python3 /tmp/fix_obn.py` — 8/8 patches needed.
2. Persist via `sudo /usr/sbin/nd-systemupdate.sh.dont shell`.
3. `sudo obn discover && sudo obn report && sudo obn update c all` (leaf-first).
4. AP firmware push serially after TFTP helper check.

Customer health-check report v1.0 already filed (this was a *health check*, not a v8 push). Don't confuse the two.

---

### Fzg 137 — 4736-109 — 🔴 BLOCKED Stadler

**Status:** 🔴 **BLOCKED** · **CCU:** ❓ · **Last touched:** —

**Diagnostic state:**
- **OBN patches:** ❓
- **Switches v8:** ❓
- **APs:** ❓
- **vlan7:** ❓ (expect `172.19.196.130`)
- **Stadler cabling:** 🔴 B3.e0-4 AP not connected
- **FW reach:** ❓

Cable register item #4 — B3.e0-4 (AP trunk) link DOWN, PoE 0 W, AP not physically installed/connected.

Stadler L2 fault report v1.0 issued (`reports/customer/Stadler_4736-109_L2_Health_Check_Report_v1.0.docx`).

**Action when Stadler confirms AP installed:** verify `e0-4` link UP and PoE drawing on B3, then proceed with v8 push if not yet done.

---

### Fzg 148 — 4736-120 — 🟡 PAUSED (OBN patches + AP fw push pending)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.2.1` · **Last touched:** 2026-05-22 AR

**Diagnostic state:**
- **OBN patches:** 🔴 **0/8 on active run3** — vanilla 2.2.23; patches were applied to an earlier snapshot but not carried into run3. Must re-apply via `fix_obn.py` + chroot persist before AP fw push.
- **Switches v8:** ✅ **18/18** — all on `nv6-X-v8-148`, fw `7.4.2` (E3 back online 2026-05-22)
- **APs:** 🟡 **24/24 reachable** — Coach2 AP3 recovered via port bounce 2026-05-22 (cable reg #6 resolved ✅); 15/24 at `6.11.2-0` ✅; 8 staged-not-activated: `.221` `.234` `.225` `.222` `.220` `.237` `.223` `.235` — all show `6.10.0-0 (6.11.2-0) ✗`; Coach2 AP3 fw state not yet confirmed
- **vlan7:** ❓ (expect `172.19.202.2` — not yet confirmed live on run3)
- **Stadler cabling:** ✅ E3 power restored ✅; Coach2 AP3 recovered ✅ (cable reg #6 resolved 2026-05-22)
- **FW reach:** ❓

- **2026-05-04:** All 8 OBN bugs patched. `obn update c all` interrupted by train power-off.
- **2026-05-19:** 18/18 sw on `nv6-XX-v8-148`. 24/24 APs visible, Nomad config applied, fw `6.10.0-0`.
- **2026-05-21:** E3 cold-bypassed (no coach power). 17/18 sw. BLOCKED.
- **2026-05-22:** E3 power restored by Stadler — `nv6-E3-v8-148` (.181) back online. `obn validate` confirms 18/18 sw all ✅. 23/24 APs in DHCP (Coach2 AP3 missing). 15 APs already at 6.11.2-0 from prior push; 8 staged-not-activated. OBN patches absent from active run3 (generation 45128) — must re-apply.
- **2026-06-25 (AR):** Fabian reported displays link-up-but-no-ZFR at power-up (F2, A2 rebooted → recovered). Live check: 18/18 sw REACHABLE, 23/24 APs. **F2 (.188) logged the `KMdev: internal error while setting interface vlan1` + KMdev restart on this morning's cold boot** — its displays self-recovered (ifInOctets climbing). **10 passenger displays (vlan 3) currently link-DOWN** (RX 0, carrier-false 0): D2 e2-1 (Bildschirm D6), D2 e2-3 (D4), C2 e2-0 (C8), C1 e2-3 (C3), C1 e2-4 (C), D1 e2-2 (D1), F2 e2-4 (F11), E1 e2-1 (E5), B2 e2-1 (B6), B2 e2-3 (B4). Port bounce on D2 e2-1 did NOT recover (control port did) → switch offers link, display end not answering = display/cable-end fault, NOT switch-side. NMS AP alarm `7.7.7.7` = stale template IP (real APs .218–.240); "Port DOWN admin-enabled" alarms are the 10 real down displays.
- **2026-06-25 (AR):** 🟢 **Cold-boot logging ARMED on all 18 switches** — debug `dev,switch,poe,dhcp,lldp,rstp,diag` persisted to startup-config + persistent log cleared (verified per switch). Next cold power-cycle will capture KMdev/module-crash trace. ⚠️ Slate is consumed by first reboot — **read `show log persistent` after next power-up before any second reboot.** Capture with `scripts/sw_bootwindow_poll.sh <sw-ip> 300 3`. **Do NOT reboot the down-display switches until the cold-boot capture is collected** (a reboot wipes the armed evidence). See [findings/display_transient_rca_coldboot_repro_2026-06-24.md](findings/display_transient_rca_coldboot_repro_2026-06-24.md).

**Next session — in order:**
1. Re-apply OBN patches: `sudo scp fix_obn.py developer@10.179.2.1:/tmp/ && sudo python3 /tmp/fix_obn.py`
2. Persist + promote: `sudo /usr/sbin/nd-systemupdate.sh.dont shell` (Gate 1)
3. Safe reboot (Gate 2); re-apply TFTP CT helper after reboot
4. `sudo obn discover && sudo obn report`
5. Serial `obn update f <ip>` for 8 staged APs (.221 .234 .225 .222 .220 .237 .223 .235)
6. Investigate Coach2 AP3 absence — check switch port DHCP/LLDP (cable reg #6)

---

### Fzg 1 — 4734-101 — 🔴 BLOCKED Stadler

**Status:** 🔴 **BLOCKED** · **CCU:** `10.179.4.1` (`box1-t4`) · **Last touched:** 2026-05-22 AR

**Diagnostic state:**
- **OBN patches:** ❓
- **Switches v8:** ❓
- **APs:** ❓
- **vlan7:** ✅ `172.19.128.130` (PDF)
- **Stadler cabling:** 🔴 E2↔B1 wrong neighbour
- **FW reach:** ❓

Cable register item #1 — E2↔B1 trunk wrong-neighbour (E2.e0-0 reaches B1, plan says E2.e0-0 ↔ E3 intra-E and B1.e0-1 ↔ E1 inter-coach). Cross-wired.

**Action when Stadler confirms re-patch:** re-run `lldp_topology_check.py` (4-car variant — see `scripts/lldp_topology_check.py`'s `EXPECTED_TOPOLOGY` for 4-car layout in [troubleshooting-runbook.md](troubleshooting-runbook.md)). Expect 0 mismatches.

---

### Fzg 19 — 4734-119 — 🟡 PAUSED — AP fw DONE; L2 health + report pending

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.45.1` (box1-t45) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ bugs 1–8 + bug 9 persisted (confirmed via `fix_obn.py` idempotency check 2026-05-21); active subvol `run1`
- **OBN template:** ✅ `{%- set train_id = 19 -%}` hardcoded in all 12 `nv4-100/300/400/600-*.cfg` (correct — ÖBB Fzg ID; backbone-discovery.yaml has Nomad internal ID `45`)
- **Switches v8:** ✅ 12/12 at firmware 7.4.2 + config `nv4-*-v8-019` (`obn validate` 2026-05-21)
- **APs:** ✅ **16/16 pushed to 6.11.2-0** (2026-05-21, serial `obn update f`, completed ~06:26 WEST) — `obn validate` confirmation pending (CCU went offline post-push)
- **vlan7:** ✅ `172.19.150.130/17` (correct for odd Nomad train_id 45; verified stable post-reboot)
- **Stadler cabling:** ❓ LLDP topology check not yet run
- **FW reach:** ❓
- **TFTP helper:** 🟡 runtime fix applied 2026-05-21 (re-apply post any reboot)
- **nd-systemupdate:** ✅ `.dont` confirmed

**2026-05-21 session (AR):**
- OBN bugs 1–8 confirmed present via `fix_obn.py`; bug 9 also confirmed. Template correction: 2026-05-20 session incorrectly concluded `train_id` should NOT be hardcoded in nv4 templates — **corrected**: backbone-discovery.yaml carries Nomad internal ID (45), nv4-*.cfg carries ÖBB Fzg ID (19). Re-added `{%- set train_id = 19 -%}` to all 12 templates via chroot.
- `obn validate`: 12/12 switches ✅, 16/16 APs visible ✅ (AP3m on B3 e0-4 was stuck — recovered via PoE cycle `no configure interface e0-4 enable` + `configure interface e0-4 enable`; not a cable fault).
- AP firmware push started 2026-05-21 ~05:06 WEST, serial `obn update f <ip>` x16.

**Next actions (next session):**
1. `sudo obn discover && sudo obn report && sudo obn validate` — confirm 16/16 APs at 6.11.2-0.
2. Re-apply TFTP CT helper (`modprobe nf_conntrack_tftp` + iptables rule) if any reboot occurred.
3. LLDP topology check (adapt `scripts/lldp_check_4734-120.py` for box1-t45 IPs).
4. Run `/dosto-l2-health` for customer baseline.
5. Generate customer report via `/dosto-l2-report`.

---

---

### Fzg 139 — 4736-111 — 🟡 PAUSED (23/24 APs; AP .222 stuck)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.24.1` (`box1-t24`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ bugs 1-8 applied, bug 9 BFS fix applied (live root)
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-139` config
- **APs:** 🟡 23/24 at 6.11.2-0 · `.229` + `.224` transiently SNMP-deaf (confirmed 6.11.2-0 earlier in session — transient issue) · Coach1 AP4 (`10.179.24.222`, serial `3623-073001-1-04-00000091-2206`) stuck on 6.10.0-0: SNMP daemon broken — deaf even after full PoE power-cycle (`configure interface e1-2 poe mode off/on` on switch `.138`). AP boots, gets DHCP, responds to ICMP — SNMP agent never starts. LuCI HTTP also refused (Nomad config disables it). `obn update f` cannot reach it. 6.11.2-0 is staged but cannot be activated remotely. **Physical access required: factory-reset via hardware button OR swap the unit.**
- **vlan7:** ✅ `172.19.197.130/17` live (correct for odd Fzg 139)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks 10G full, 0 CRC/carrier errors
- **FW reach:** ❓ Q1/Q2/Q3 probe not yet run
- **OBN template:** ✅ `train_id = 139` hardcoded in all 18 `nv6-*.cfg` templates
- **nd-systemupdate:** ✅ renamed `.dont` (confirmed in run1 snapshot)
- **Snapshot:** ✅ run1 active

**2026-05-21 session:**
- Promoted snapshot with train_id=139 templates + OBN patches 1-8
- safe_reboot executed → run1 active post-reboot
- Bug 9 BFS fix applied to live root (obn report was looping on v3→v8 topology)
- 18/18 switches pushed to v8-139 via `obn update c all`
- Serial AP firmware push completed: 23/24 APs at 6.11.2-0
- AP .222 stuck: SNMP deaf, multiple `obn update f` + SSH reboot cycles failed to activate 6.11.2-0 partition

**Next actions:**
1. Physically inspect/replace Coach1 AP4 (`10.179.24.222`) — hardware fault suspected
2. Once 24/24 APs confirmed, mark 🟢 DONE

---

### Fzg 140 — 4736-112 — ⚪ UNKNOWN (train_id + vlan7 fixed 2026-06-09; commissioning not yet started)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.40.1` (hostname `box1-t40`, confirmed 2026-06-09) · **Last touched:** 2026-06-09 AR

> ⚠️ Prior `10.179.12.1` attribution was wrong (belongs to Fzg 147 / 4736-119, confirmed 2026-05-21). True CCU IP is **`10.179.40.1`**. Engineer confirmed true Fzg = **140**.

**Diagnostic state (2026-06-09 AR — `dosto-vlan7-config` + `dosto-fzg-id-check`, then live chroot fix + reboot):**

This CCU was misimaged toward **Fzg 168**: broken `{%- set train_id = 128 + train_id -%}` formula (backbone train_id=40 → renders 168) AND vlan7 set to `172.19.212.2` (the .168 encoding). Both fixed in one chroot session (templates→`{%- set train_id = 140 -%}`, vlan7 nmconnection→`172.19.198.2/17`), promoted, `safe_reboot`. Verified live post-reboot:

- ✅ **train_id ok** — all 18 `nv6-*.cfg` now `{%- set train_id = 140 -%}` (live). Will render `nv6-X-v8-140`. (`backbone-discovery.yaml` still reads `train_id: 40` — untouched per mar5 rule; Form-1 hardcode makes it irrelevant.)
- ✅ **vlan7 ok** — live + nmconnection both `172.19.198.2/17`.
- ✅ **FW reach (Q1+Q2)** — peer `172.19.198.1` ARP **REACHABLE** (MAC `00:90:e8:c5:3d:ce`, Westermo OUI) + ICMP 100% loss = **FW commissioned by Stadler**. (The earlier `path_broken` was an artifact of the wrong .212.1 target.)
- ❓ **Not yet started:** OBN patches, switch fw/config, AP fw/config, device discovery, L2 health, customer report. CCU is now safe for `obn update c all` (renders correct Fzg 140). Next session: run full commissioning pipeline from device discovery.

---

### Fzg 147 — 4736-119 — 🟡 PAUSED (L2 health + customer report pending)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.12.1` (`box1-t12`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ bugs 1-8 applied (confirmed idempotent in run3 snapshot)
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-147` config
- **APs:** ✅ **24/24 at 6.11.2-0** (confirmed 2026-05-21)
- **vlan7:** ✅ `172.19.201.130/17` live (correct for odd Fzg 147; confirmed via probe 2026-05-21)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks clean
- **FW reach:** ❓ Q1/Q2/Q3 probe not yet run this session
- **OBN template:** ✅ `train_id = 147` hardcoded in all 18 `nv6-*.cfg` templates
- **nd-systemupdate:** ✅ `nd-systemupdate.sh` removed inside chroot (run3); `.dont` variant retained
- **Snapshot:** ✅ run3 active (promoted 2026-05-21)

**2026-05-21 session:**
- IP conflict resolved: `10.179.12.1` previously misattributed to Fzg 140 — confirmed as Fzg 147 via vlan7=`172.19.201.130/17` decode
- run3 snapshot promoted (bug 9 pysnmp patch + nd-systemupdate.sh removed); safe_reboot → run3 active
- 18/18 switches pushed to v8-147 via `obn update c all` (two passes due to cellular drops; confirmed via fresh `obn discover`)
- TFTP conntrack helper applied; serial AP firmware push started via nohup

**Next actions:**
1. Verify 24/24 APs at 6.11.2-0: `sudo obn validate` (wait for nohup push to complete)
2. Run L2 health check: `/dosto-l2-health --ccu-ip 10.179.12.1 --fzg 147`
3. Generate customer report: `/dosto-l2-report`

---

### Fzg 138 — 4736-110 — 🟡 PAUSED (AP fw DONE; L2 health + customer report pending)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.23.1` (`box1-t23`) · **Last touched:** 2026-05-20 AR

**Diagnostic state:**
- **OBN patches:** ✅ **8/8 + bug 9 persisted** in `/.snapshots/run1` (2026-05-20 chroot promote + safe_reboot; markers verified bug1/6/7/9 directly via grep post-reboot)
- **Switches v8:** ✅ 18/18 on v8 config (`nv6-*-v8-138`), fw 7.4.2
- **APs:** ✅ **24/24 at 6.11.2-0** (target firmware), all `AP*-v1` / `AP*m-v1` Nomad config ✅ — completed 2026-05-20 via serial `obn update f <ip>` re-runs
- **vlan7:** ✅ `172.19.197.2/17` (correct for even Fzg 138; persisted from 2026-05-19)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks clean, 0 errors
- **FW reach:** ✅ **commissioned** (2026-05-19): ARP REACHABLE `00:90:e8:c5:3d:9d` (Westermo), ICMP 100% loss = Stadler policy drop per Phase 6 Q2
- **OBN template:** ✅ `train_id = 138` hardcoded in all 18 nv6-*.cfg
- **nd-systemupdate:** ✅ `.dont` renamed (fleet standard)
- **TFTP helper:** 🟡 runtime fix applied 2026-05-20 (re-apply post any reboot)

**2026-05-20 session (AR):**
- /dosto-orchestrate fzg=138 — pre-flight PASS (18/18 sw + 24/24 AP visible).
- Discovered OBN had only bug 9 marker present (1/9) — bugs 1-8 missing on active subvol. Parent SCP'd all 5 fix scripts to `/var/tmp/`; Gate 1 approved → chroot promote applied all → new `run1`. Gate 2 approved → reboot. Post-reboot bug markers all present.
- TFTP CT helper runtime fix re-applied; Gate 4 approved for AP firmware push.
- Initial OBN-driven push to 7 APs (.219 .225 .232 .233 .235 .238 .241) staged firmware but didn't activate — APs sat at `current (staged) ✗`. SSH-`reboot` and SNMP-reboot OID both restarted the APs but they came back on OLD firmware → bare reboot does NOT swap firmware partitions.
- **Discovered: re-running `obn update f <ip>` is the activation trigger** (it calls confmgmtd's `set firmware` RPC under the hood). Verified end-to-end on `.219` first, then looped the remaining 6 serially. All 7 activated to 6.11.2-0.
- Special case `.225`: SSH non-interactive exec is in dropbear restricted-exec mode (every command incl. `echo test` returns "Command failed: Not found"). SNMP-reboot worked (OID `.1.3.6.1.4.1.16177.1.400.1.3.3.1.0`) but bare reboot still didn't swap firmware; `obn update f .225` did swap. Lesson 18 added to `dosto-ap-firmware-update` skill.

**Discovered lessons (folded back into runbook):**
- **AP firmware activation requires OBN's full flow, not just a reboot.** SSH `reboot` and SNMP reboot OID `.1.3.6.1.4.1.16177.1.400.1.3.3.1.0` both restart the AP on its existing partition — they do NOT mark the staged firmware as active. Only `obn update f <ap-ip>` (which calls confmgmtd's `set firmware` RPC) triggers the partition swap. If you see `current (staged) ✗` in `obn validate -t ap`, the recovery is to re-run `obn update f <ap-ip>`, not a force-reboot.
- **`Command failed: Not found` from non-interactive SSH** is the Westermo restricted-exec-mode signal. Diagnostic test: `ssh nomad@<ap-ip> 'echo test'` — if that returns "Not found", every non-interactive command is blocked. Fall back to OBN SNMP set on reboot OID for restart; but per above, **prefer re-running `obn update f`** to actually swap firmware.

**Next actions (next session):**
1. Re-apply TFTP CT helper runtime fix if any CCU reboot happened in between.
2. Run `/dosto-l2-health` for customer baseline.
3. Generate customer docx report via `/dosto-l2-report`.
4. After report filed, set status to 🟢 **DONE**.

---

### Fzg 9 — 4734-109 — 🟡 DONE-PARTIAL (12/12 sw config-correct on v8-009; A1 ↔ A3 coupler cable swap blocks A1 service — Stadler re-cable)

**Status:** 🟡 **DONE-PARTIAL** · **CCU:** `10.179.38.1` (`box1-t38`) · **Last touched:** 2026-06-08 PM AR

**Diagnostic state:**
- **OBN patches:** ✅ 10/10 native (0.0.19), train_id=9 Form-1 in all 12 nv4-*.cfg (sess 0900Z)
- **Switches v8:** 🟡 **12/12 config-correct on v8-009** (A2/A3/B1/B2/B3/E1/E2/E3/G1/G2/G3 verified `nv4-X-v8-009`; **A1 now config-corrected to train_id-9 in-band** — see A1 block). ⚠️ A1 is config-correct but **NOT in service**: it's mis-cabled at the A1↔A3 coupler (Stadler cabling, reg #10) — A1's vlan100 trunks (e0-0/e0-1) plug into the coupled **Fzg-15** consist; only its coupler port (e0-2, VLAN 5/15, no vlan100) faces this train. A1 healthy + managed in-band via native-VLAN-1 workaround. **Needs physical re-cable, not factory-reset.** See A1 block below
- **APs:** 🟡 16 APs visible, all `AP*-v1` Nomad config — firmware unknown (out of scope this session)
- **vlan7:** ✅ `172.19.132.130/17` live (correct for odd Fzg 9)
- **Stadler cabling:** 🟡 inter-coach trunks clean; RSTP single-root `a0:59:3a:d0:43:a0` (G1), all FWD, no split — clean reconvergence after 11 reboots
- **FW reach:** ❓ not re-checked this session

**2026-06-08 sess 1155Z — manual TFTP/SNMP v8 push (11/12):**
- OBN's `obn update c` no-ops standalone (`discovery.prev.json` target=None — needs NMS/MQTT context). Bypassed via manual per-switch TFTP/SNMP push (proven Fzg 123 bench procedure): render cfg via OBN jinja → upload → SNMP location/trigger → poll → hostname-commit → reboot OID → verify. Leaf-first, A-car (A2 then A3) last.
- 3 CCU bypasses applied (runtime-only, **wiped on reboot**): `modprobe nf_conntrack_tftp`, raw PREROUTING CT helper udp/69, MGMTI ACCEPT udp/69.
- All 11 verified on `v8-009`; RSTP converged single-root, clean.

**🔴 A1 — A1↔A3 COUPLER CABLE SWAP (Stadler cabling, reg #10) — CORRECTED 2026-06-08 PM:**
- **Re-diagnosed.** Prior reads ("misimaged" then "physically absent") were both incomplete. A1 **is present, powered, healthy** (Normal Mode, ~49 °C) — it was just unreachable on vlan100. Reached in-band this session via a **native-VLAN-1 workaround**: temp `192.168.1.2/24` on the CCU's untagged `bond0` → A1 answers SSH (`admin`/`Nom@dCome1n`) + SNMP at its static `192.168.1.100`. (Temp IP since removed; no persistent CCU change.)
- **Root cause = physical cable swap at the A1↔A3 coupling.** Live LLDP: A1 **e0-0 → Fzg-15's A3** (`…d0:93:80`), A1 **e0-1 → Fzg-15's G1** (`…d0:6e:00`), A1 **e0-2 (front-coupler, VLAN 5/15 only) → this train's A3** (`…d0:67:60`). I.e. A1's vlan100-carrying intra-consist trunks (e0-0/e0-1) are plugged into the **coupled Fzg-15 consist**, while its no-vlan100 coupler port faces this train. This train's A3 confirms: A3 e0-2 (its coupler port) faces this A1.
- **Why no remote push works:** A1's vlan100 (`10.179.61.183`, dead train-15 subnet) has no bridged path to this CCU. Every config-fetch transport tested fails — TFTP/HTTP/SCP all emit **zero** outbound packets (verified via tftpd log + tcpdump) because A1 sources config-fetch from its unreachable vlan100 interface. Only untagged VLAN 1 crosses the mis-cabled coupler → management-only.
- **train_id-15 imaging is a SYMPTOM:** OBN auto-topology on A1 saw Fzg-15 neighbours on e0-0/e0-1 and rendered A1 as a train-15 switch.
- **✅ 2026-06-08 PM — A1 config HAND-CORRECTED to train_id-9 in-band + PERSISTED.** Since A1 can't fetch a config (vlan100 unreachable → TFTP/HTTP/SCP all fail), the config was corrected by *sending* CLI commands inbound over the native-VLAN-1 SSH channel (the v8-009 render keeps `vlan1 192.168.1.100` + e0-2 native unchanged, so the mgmt path survives the edit). Applied: hostname `nv4-A1-v8-015`→`nv4-A1-v8-009` + all 27 train-id deltas (10 DHCP-group default-router/server-id + 17 per-port client-address; `.135`→`.132`, `.7`→`.4`). Verified **0 train-15 values remain** in both running- AND startup-config; `save running-config` persisted (survives reboot). A1's config now matches what OBN renders for Fzg 9. **This does NOT restore A1 service** (still mis-cabled) — it pre-stages config-correctness so that after the Stadler re-cable A1 slots in with **no push needed**.
- **Fix = Stadler on-train RE-CABLE (not factory-reset, not remote push):** correct the A-end patch so A1 e0-0/e0-1 land on **this train's** A3/G1 and e0-2 is the actual inter-train coupler. After re-cabling, A1's vlan100 reaches the CCU and OBN auto-topology sees Fzg-9 — a clean re-cable may auto-recover A1; else push the staged `nv4-100-A1` train_id=9 (already at `/data/auto-topology/upload/nv4-A1-v8-009-render.cfg`; A1 LAST, v8-cabling-trap caution).
- **⚠️ Verify with Stadler whether Fzg 9 + Fzg 15 are *intended* to be coupled here.** If yes, the fault is purely the A-end intra-consist patch (e0-0/e0-1 must stay within Fzg 9); the coupler (e0-2) is legitimately cross-train.

**2026-05-19 findings (prior):**

**2026-05-19 findings:**
- All 12 switches clean — 0 CRC/carrier errors on inter-coach trunks
- STP root: `a0:59:3a:d0:3a:a0` (B1 `.220`, priority 32768) — stable
- B1 e1-11 + B3 e1-11 both DOWN — ZFR not connected/powered at time of check; check with Stadler if ZFR expected active

**Next actions:**
1. Complete FW probe when CCU recovers
2. Confirm v5 is correct target config for 4734 series (vs v8 for 4736)
3. Check ZFR presence/power

---

### Fzg 12 — 4734-112 — 🟡 PAUSED (AP fw push outcome unknown — verify obn validate)

**Status:** 🟡 **PAUSED — AP fw push started 2026-05-21; outcome unknown** · **CCU:** `10.179.37.1` (`box1-t37`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ **9/9 persisted in run2/id333** (incl bug 9). Promoted via chroot 2026-05-21T08:23Z (run1/330 → run2/333); reboot activated run2 at 08:27Z. Canonical `dosto-obn-patches --check` confirms all markers post-reboot (state-inventory 0/8 reading was the documented false-negative).
- **Switches v8:** ✅ 12/12 at `nv4-XX-v8-012`, firmware 7.4.2 (target met — push_switch_config no-op).
- **APs:** 🔵 16/16 Nomad-form at 6.10.0-0 → target 6.11.2-0 — **push in flight** (single-AP serial, est ~2.4hr from 08:39Z).
- **vlan7:** ✅ `172.19.134.2/17` (correct for even Fzg 12; live + nmconnection).
- **train_id template:** ✅ `{%- set train_id = 12 -%}` hardcoded in all 12 nv4-*.cfg.
- **Stadler cabling:** ✅ 12/12 sw visible; FW ARP REACHABLE `00:90:e8:cf:6f:49`.
- **TFTP helper:** 🟡 runtime fix re-applied post-reboot 2026-05-21T08:30Z (in-memory only).
- **nd-systemupdate:** ✅ `.sh.dont` rename in place.
- **btrfs:** ✅ active subvol `/.snapshots/run2 (id 333)`, all 9 patches persisted.

**2026-05-21 /dosto-orchestrate run (in progress):**
- Pre-flight: 12/12 sw + 16/16 AP visible via fping+ARP; scripts pre-staged at /tmp/ + /var/tmp/.
- Gate 1 (promote_snapshot) approved 08:19Z — chroot promote landed at run2/id333 with 9/9 markers.
- Gate 2 (safe_reboot) approved 08:25Z — executed by parent session per F1-C handoff; CCU back at +3min on run2.
- post_reboot_verify: 9/9 markers confirmed live; TFTP CT helper re-applied.
- obn_discover_initial: switches all at target; routed to skip push_switch_config and go straight to Gate 4.
- Gate 4 (obn_update_f) approved 08:39Z — 16 APs single-AP serial via /dosto-ap-firmware-update --execute.

**Next:** await per-AP progress reports; after 16/16 at 6.11.2-0 → final_l2_health_check → generate_report → DONE.

#### Stale notes (against wrong CCU IP 10.179.41.1 — 2026-05-19; ignore)

**Diagnostic state:**
- **OBN patches:** ❓ (not checked)
- **Switches v8:** 🔴 15/15 visible, all **v3 config** (`fv5-*-v3-231`, wrong train_id 231)
- **APs:** 🟡 20 APs visible, all `AP*-v1` Nomad config — firmware unknown
- **vlan7:** ✅ `172.19.134.2/17` — **FIXED 2026-05-19** (was `172.19.243.130`, now correct for even Fzg 12, persisted to run1)
- **Stadler cabling:** 🟡 15/15 visible; inter-coach trunks clean; **B1 (.185) e1-11 DOWN**, **B3 (.181) e1-11 DOWN**; C3 (.189) has 4×10G UP (unusual — verify LLDP)
- **FW reach:** ❓ no ARP entry yet (vlan7 just fixed, no FW probe run)
- **Consist size:** ⚠️ **5-car** (cars A,B,C,E,F — 15 switches, 20 APs); briefed as 4-car — verify against schema PDF
- **OBN template:** 🔴 `train_id` not hardcoded for nv4 series (renders nd-redundancy train_id=41, not Fzg 12)

**Next actions:**
1. Verify consist size against 4734-112 schema PDF
2. Check STP root and run FW probe: `ip neigh show dev vlan7 && ping -c 5 172.19.134.1`
3. Investigate C3 (.189) 4×10G UP — run LLDP check
4. Fix OBN template `train_id` → hardcode `12`
5. Check/apply OBN patches

---

### Fzg 13 — 4734-113 — 🟡 PAUSED (v7 → v8 push needed at corrected IP)

**Status:** 🟡 **PAUSED — v7 → v8 switch config push needed** · **CCU:** `10.179.46.1` (`box1-t46`) · **Last touched:** 2026-05-21 AR

**2026-05-21 status check at corrected IP (read-only):**
- CCU reachable at `10.179.46.1` (corrected from `10.179.42.1` — that IP belongs to 4705-101).
- 12/12 switches present (coaches A, G, B, E × 3) — fully cabled. Hostname pattern `nv4-XX-v7-013` / `nv4-XX-v7m-013`: switches are on **v7 config, not v8**. Full v8 config push needed.
- 16/16 APs present, but **all 16 are plain `AP[1-4]-v1` with zero m-variants**. nv4 expected mix is 2 plain + 2 m-variant per slot. Either APs are in factory/un-configured state or all coaches got uniform (non-mirrored) config. Verify with `obn discover` before deciding.
- vlan7 `172.19.134.130/17` ✅ (correct for odd Fzg 13). train_id template `{%- set train_id = 13 -%}` ✅.
- State-inventory said OBN 4/8 in active subvol run2/id308 — **false-negative per the 2026-05-21 Fzg 21 disambiguation**; treat as likely 8/8. Re-verify with `dosto-obn-patches --check` before any destructive op.
- TFTP module not loaded, CT helper rule absent.
- `.dont` rename in place ✅.

**Next session:** verify OBN state via canonical check; verify AP config expectation (plain vs m-variant for nv4); v7 → v8 switch config push (`obn update c` leaf-first); then AP firmware push.

#### Stale notes (against wrong CCU IP 10.179.42.1 — 2026-05-19; ignore — that IP belongs to 4705-101)

**Diagnostic state:**
- **OBN patches:** ❓ (not checked)
- **Switches v8:** 🔴 **15/18 visible**, all v3 config (`fv5-*-v3-229`, wrong train_id 229) — **3 switches missing from DHCP**
- **APs:** 🟡 20 APs visible, all `AP*-v1` Nomad config — firmware unknown
- **vlan7:** ❓ no ARP entry observed; FW probe not completed
- **Stadler cabling:** 🔴 **3 switches missing** — potential cable/power faults on those 3 cars; B1/B3 ZFR e1-11 checked and clean; checked switches had 0 errors
- **FW reach:** ❓ incomplete (CCU dropped mid-session)
- **OBN template:** 🔴 `train_id` not hardcoded

**2026-05-19 findings:**
- 15 switches across `.184–.205` range visible; gaps suggest 3 switches not powered/connected
- STP root: `a0:59:3a:d0:29:60` (A2 `.184`, priority 32768) — stable on visible switches
- Missing switches need physical investigation by Stadler

**Next actions:**
1. Identify which 3 switches are missing (run `sudo dhcp-lease-list` + `fping` sweep when CCU recovers)
2. Log missing switches as cable register items if Stadler cabling fault confirmed
3. Complete FW probe
4. Fix OBN template `train_id`

---

### Fzg 14 — 4734-114 — 🟡 PAUSED (AP fw push outcome unknown — verify obn validate)

**Status:** 🟡 **PAUSED — AP fw push started 2026-05-21; outcome unknown** · **CCU:** `10.179.44.1` (`box1-t44`) · **Last touched:** 2026-05-21 AR

**Initial visit:** train discovered 2026-05-21 via morning-brief sweep; matched to 4734-114 (T44, status `Done`, NC release 2025.2.1 per Fleet Control Sheet 2026-02-11). First Nomad-side commissioning attempt this session via `/dosto-orchestrate fzg=12,14`.

**Diagnostic state:**
- **OBN patches:** ✅ **9/9 persisted in run2/id325** (incl bug 9). fix_obn.py + fix_obn_bug8.py + fix_obn_bug9_pysnmp_thread_safety.py applied live then chroot-promoted 2026-05-21T08:17Z (run1/322 → run2/325); reboot activated run2 at 08:21Z. Canonical `dosto-obn-patches --check` confirms all markers post-reboot.
- **Switches v8:** ✅ 12/12 at `nv4-X-v8-014`, firmware 7.4.2 (target met — push_switch_config no-op). Coaches A, G, E, B × 3 positions each. Control-sheet "v6/6.10.0" was stale; switches are actually already at v8 target.
- **APs:** 🔵 16/16 Nomad-form at 6.10.0-0 → target 6.11.2-0 — **push in flight** (single-AP serial, est ~2.4hr from 08:33Z).
- **vlan7:** ✅ `172.19.135.2/17` (correct for even Fzg 14: `128 + 14//2 = 135`, `0 + 2 = 2`). Live + nmconnection both match.
- **train_id:** nv4 4-Teiler convention — `train_id=44` in `/etc/nd-redundancy/backbone-discovery.yaml` (Nomad internal ID, not Fzg ID — per memory `feedback_train_id_4734_4teiler`). No template hardcode needed.
- **Stadler cabling:** ✅ 12/12 sw visible; FW ARP REACHABLE `172.19.135.1` (`00:90:e8:ce:86:2a` — Westermo OUI). Q1 path OK.
- **TFTP helper:** 🟡 runtime fix re-applied post-reboot 2026-05-21T08:30Z (in-memory only).
- **nd-systemupdate:** ✅ `.sh.dont` rename in place (was already present pre-visit).
- **btrfs:** ✅ active subvol `/.snapshots/run2 (id 325)`, all 9 patches persisted.

**2026-05-21 /dosto-orchestrate run (in progress):**
- Pre-flight: 12/12 sw + 16/16 AP visible via fping+ARP; scripts pre-staged at /tmp/ + /var/tmp/.
- Stage 1 initial_diagnostics: confirmed device counts, switches already at v8-014 target, APs Nomad-form at 6.10.0-0.
- Stage 4 apply_obn_patches: fix scripts run live (run1/322 had 0/9; post-apply 9/9 in run1).
- Stages 2 (apply_train_id_fix) + 3 (apply_vlan7_fix) skipped — both already correct.
- Gate 1 (promote_snapshot) approved 08:13Z — chroot promote landed at run2/id325 with 9/9 markers.
- Gate 2 (safe_reboot) approved 08:18Z — executed by parent session per F1-C handoff (worker SSH was harness-denied); CCU back at +1s on run2.
- post_reboot_verify: 9/9 markers confirmed live; TFTP CT helper re-applied.
- obn_discover_initial: routed to skip push_switch_config and go straight to Gate 4.
- Gate 4 (obn_update_f) approved 08:33Z — 16 APs single-AP serial via /dosto-ap-firmware-update --execute.

**Next:** await per-AP progress reports; after 16/16 at 6.11.2-0 → final_l2_health_check → generate_report → DONE.

---

---

### Fzg 143 — 4736-115 — 🟡 PAUSED (8/24 APs at 6.11.2-0; 16 need serial retry)

**Status:** 🟡 **PAUSED — 8/24 APs at 6.11.2-0; 16 need serial retry** · **CCU:** `10.179.18.1` (`box1-t18`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ⚠️ state-inventory reported 4/8 in active subvol `run1 (id 312)` — **false-negative** per `dosto-obn-patches --check` on Fzg 21 (2026-05-21). Treat as still 8/8 + bug 9 pending direct re-verify.
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-143`, all firmware `7.4.2`
- **APs:** 🟡 24/24 visible, all Nomad config — **8/24 at 6.11.2-0 (33%)**: coach 1 = 4/4 ✅, coach 2 = 3/4 (.232 still 6.10.0-0), coach 3 = 0/4, coach 4 = 0/4, coach 5 = 0/4, coach 6 = 1/4 (.238 only). 16 APs still on 6.10.0-0. Coaches 4-6 (12 APs) still need config refresh from `AP*-v1` → `AP*m-v1`
- **vlan7:** ✅ `172.19.199.130/17` live (was wrong `172.19.201.2` — encoded Fzg 146; fixed + persisted via chroot promote)
- **Stadler cabling:** ✅ 18/18 sw + 24/24 AP visible (pre-flight discovery clean)
- **FW reach:** ⬜ Q1/Q2/Q3 not yet probed
- **OBN template:** ✅ `train_id = 143` hardcoded in all 18 nv6-*.cfg
- **nd-systemupdate:** ✅ `.dont` renamed (fleet standard)
- **TFTP helper:** 🟡 runtime fix applied this session (in-memory only — re-apply post-reboot before next AP fw push)

**2026-05-20 session (AR):**
- Initial visit from ⚪ UNKNOWN. OBN was at v2.2.23 with new lib hierarchy `/usr/share/obn/lib/device/vendor/`. `fix_obn.py` already targets these paths — no script changes needed.
- v8 template detection bug surfaced: workers false-alarmed `v8_templates_missing_post_update` because they globbed for `nv6-*-v8-*.cfg` (a pattern that doesn't exist in any shipped package). 0.0.19 package retains flat `nv6-NNN-XN.cfg` naming. Updated `dosto-commission-train` SKILL.md to use `dpkg-query` version check (`nd-obn-template-dostoneu-nv6 ≥ 0.0.19`) in 6 spots.
- Applied OBN 8/8 fixes + train_id=143 + vlan7=172.19.199.130 via single chroot promote (Gate 1 approved).
- Switch config push (Gate 3) crashed mid-batch with `pysnmp.error.PySnmpError: IndexError: pop from empty list` — diagnosed as `SNMPEngineManager` singleton sharing one `SnmpEngine` across `ThreadPoolExecutor` workers in `cli/update.py`. Pysnmp's asyncore dispatcher is not thread-safe.
- **OBN Bug 9 patch:** added `scripts/fix_obn_bug9_pysnmp_thread_safety.py` — module-level `threading.Lock()` around `_snmp_parse_results`'s `list(generator)`. Persisted in chroot promote (run3).
- Post-patch `obn update c sw` ran cleanly to completion: 18/18 switches converged to `nv6-*-v8-143`.
- TFTP helper runtime fix applied; AP firmware push launched (`obn update f ap`); OBN exited at its optimistic 5-min wait while APs still curl-downloading 30MB images (handoff lesson 14).

**2026-05-21 status check (read-only):**
- `obn validate` confirms 8/24 APs at 6.11.2-0 — the 2026-05-20 batch experiment with TFTP helper pre-applied did NOT achieve 100% success. Per-coach: 1=4/4, 2=3/4, 3=0/4, 4=0/4, 5=0/4, 6=1/4. The 16 remaining APs need a retry (serial via dosto-ap-firmware-update).
- ⚠️ State-inventory said OBN 4/8 — confirmed **false-negative** (canonical `dosto-obn-patches --check` on Fzg 21 found all 8 markers present). Treat Fzg 143 as still 8/8 + bug 9 pending direct re-verify.
- TFTP module + CT helper absent (uptime ~65 min — runtime fix lost on reboot).
- Memory `project_obn_update_f_ap_batch_experiment_fzg143` updated with 8/24 final count.

**Next session — first commands:**
```bash
ssh developer@10.179.18.1
sudo modprobe nf_conntrack_tftp && sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
# Verify OBN state via dosto-obn-patches --check (NOT state-inventory's grep)
sudo obn discover && sudo obn report
sudo obn validate -t ap   # confirm 8/24 still at target
# Then: 16 × single-AP serial fw push via /dosto-ap-firmware-update
# After APs done: push config refresh for coaches 4-6 APs (AP*-v1 → AP*m-v1)
```

Then: L2 health sweep + FW Q1/Q2/Q3 probe + customer report.

---

### Fzg 144 — 4736-116 — 🟡 PAUSED (9/23 APs at 6.11.2-0; OBN patch state needs re-verify)

**Status:** 🟡 **PAUSED — 9/23 APs at 6.11.2-0; OBN patch state needs re-verify** · **CCU:** `10.179.16.1` (`box1-t16`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ⚠️ state-inventory reported 4/8 — **false-negative** per `dosto-obn-patches --check` on Fzg 21 (2026-05-21). Treat as still 8/8 pending direct re-verify. btrfs subvol id changed 303 → 306 between sessions (a promote happened — note, not necessarily a problem).
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-144`, all firmware `7.4.2`
- **APs:** 🟡 24/24 visible (Coach 6 AP3 now in DHCP — register #6 may be self-resolved); **9/23 at 6.11.2-0** (coach 1=3/4, coach 2=2/4, coach 3=2/4, coach 4=1/4, coach 5=0/4, coach 6=1/4 + AP4 `incomplete` firmware state). 13 still on 6.10.0-0. Coaches 4-6 (12 APs) also need config refresh from `AP*-v1` → `AP*m-v1`
- **vlan7:** ✅ `172.19.200.2/17` live (was already correct for even Fzg 144 — no nmconnection edit needed)
- **Stadler cabling:** 🔴 Coach 6 AP3 missing (B3 e1-2 port live with RX/TX traffic per pre-flight but AP not in DHCP across 2 cycles — likely AP physically present but bricked or stuck) — cable register #6
- **FW reach:** ✅ **commissioned** (2026-05-20): Q1 ARP REACHABLE `00:90:e8:ca:3e:aa`, Q2 ICMP 100% loss = Stadler policy drop per Phase 6, Q3 TCP 80+22 OPEN
- **OBN template:** ✅ `train_id = 144` hardcoded in all 18 nv6-*.cfg (was broken `128 + train_id` formula)
- **nd-systemupdate:** ✅ `.dont` renamed
- **TFTP helper:** 🟡 runtime fix applied this session (in-memory only — re-apply post-reboot before next AP fw push)

**2026-05-20 session (AR):**
- Initial visit from ⚪ UNKNOWN. Same OBN 2.2.23 + v8 detection bug pattern as Fzg 143; same fixes applied.
- Pre-flight soft-FAIL: 23/24 APs in DHCP at first probe (all 6 X3 e1-2 AP4 ports active per `show interface details`) — engineer chose `proceed` at Gate 5. Coach 6 AP3 still missing post-reboot, confirmed across two discovery cycles → cable register #6.
- Applied OBN 8/8 + train_id=144 fold-in via single chroot promote (Gate 1). vlan7 was already correct so no fold-in there.
- Bug 9 patch applied + persisted (same procedure as Fzg 143). 18/18 switches converged to `nv6-*-v8-144` on `obn update c sw`.
- AP firmware push launched on 23 APs; OBN exited at 5-min wait while APs still installing.

**2026-05-21 status check (read-only, parallel state-inventory subagent):**
- AP firmware push continued installing offline — **now 9/23 at 6.11.2-0** (not 0/23 as the 2026-05-20 row implied). 13 APs still on 6.10.0-0. Coach 6 AP4 (10.179.16.222) reports `incomplete` firmware — SNMP unreachable, mid-update stuck, or bricked.
- Coach 6 AP3 (10.179.16.224) **now visible** in DHCP — was missing across 2 cycles last session. Cable register #6 may be self-resolved; recommend a second DHCP cycle next session before closing.
- ⚠️ **State-inventory reported OBN 4/8 — confirmed false-negative** (dosto-state-inventory has stale marker-grep; canonical `dosto-obn-patches --check` on Fzg 21 found all 8 markers present). Treat as still 8/8 pending direct re-verify on next session. The btrfs subvol id moving from 303 → 306 was a real promote but did not regress patches.
- TFTP CT helper absent (uptime ~27 min — runtime fix lost on reboot, expected).

**For Stadler (open items):**
- **Coach 6 AP3 missing** (cable register #6) — B3 e1-2 port live with RX/TX traffic, but AP not in DHCP after 2 discovery cycles. Likely AP physically connected but bricked / stuck / not booting. Required action: visually verify AP installed → replace patch cable B3 e1-2 ↔ AP → swap AP unit if cable doesn't restore.

**Next session — first commands:**
```bash
ssh developer@10.179.16.1
sudo modprobe nf_conntrack_tftp && sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
sudo obn discover && sudo obn report
sudo obn validate -t ap | grep -c '6.11.2-0 ✓'   # if not 23, single-AP serial via dosto-ap-firmware-update
# After APs done: push config refresh for coaches 4-6 APs (AP*-v1 → AP*m-v1)
```

Then: L2 health sweep + customer report. FW reach already validated this session — no further FW work needed.

---

### Fzg 90 — 4734-190 — 🔴 BLOCKED (Stadler cabling: G2 e0-0 trunk unconnected)

**Status:** 🔴 **BLOCKED** · **CCU:** `10.179.54.1` (`box1-t54`) · **Last touched:** 2026-05-22 AR

**Diagnostic state:**
- **OBN patches:** ✅ **8/8 persisted** in run2 (btrfs id 319) — applied 2026-05-22 via chroot promote
- **Switches v8:** ✅ **12/12 on `nv4-*-v8-090`** config, fw 7.4.2
- **APs:** 🟡 **15/15 Nomad config** (`AP*-v1` / `AP*m-v1`), firmware **6.10.0-0** (target 6.11.2-0) — push not yet done (blocked)
- **vlan7:** ✅ `172.19.173.2/17` — live and persisted in nmconnection ✅
- **train_id in templates:** ✅ **hardcoded `90`** in all 12 `nv4-*.cfg` (done inside chroot 2026-05-22)
- **nd-systemupdate:** ✅ `.dont` in place
- **Active snapshot:** `run2` (btrfs id 319)
- **Stadler cabling:** 🔴 **G2 (.191) `e0-0` port has no LLDP neighbour** — only `e0-1 → E1`. Full LLDP sweep confirmed: G1/G3 connect to CCU and form backbone; G2 is isolated on the BFS (only reachable via E1↔B1 loop with no root anchor). This causes `obn report` to hang indefinitely in `number_coaches()` BFS.
- **FW reach:** ❓ not yet probed

**2026-05-22 session (AR):**
- Identified via ping sweep — first visit, added to fleet-status
- /dosto-orchestrate ran Gate 1 (OBN patches applied + train_id hardcoded) + Gate 2 (safe reboot)
- Post-reboot: run2/id319 active, 8/8 patches confirmed, train_id=90 in all 12 templates ✅
- LLDP topology sweep revealed G2 `e0-0` has no inter-coach trunk neighbour → BFS hang → blocked

**LLDP topology found:**
```
CCU → G1 (e0-2/e0-3), G3 (e0-2/e0-3)
G1 (.184):  e0-0→A1,  e0-1→E2
G3 (.195):  e0-0→A2,  e0-1→(none — G3 e0-1 unconnected)
G2 (.191):  e0-0→(NONE),  e0-1→E1   ← FAULT: G2 has no e0-0 peer
E1 (.192):  e0-0→B1,  e0-1→G2
B1 (.200):  e0-0→B3,  e0-1→E1
```
G2 should connect `e0-0` toward the backbone (G1 or G3 e0-1). Without this, the B1/E1/G2 sub-chain is unreachable from the CCU-rooted BFS.

**For Stadler:** Connect G2 (`nv4-G2-v8-090`, MAC `a0:59:3a:d0:9e:20`, IP `10.179.54.191`) port `e0-0` to its expected inter-coach trunk peer (likely G3 `e0-1` or G1 `e0-1` depending on physical coach layout). After fix, verify with `show lldp neighbours` on G2.

**Next session — after Stadler fixes G2 e0-0:**
```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@10.179.54.1
# 1. Verify G2 e0-0 now has LLDP neighbour
# (pexpect or sshpass into .191, run: show lldp neighbours)

# 2. Re-apply TFTP conntrack helper + bug9 fix (lost on reboot)
sudo modprobe nf_conntrack_tftp && sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
scp fix scripts to /tmp/, then sudo cp /tmp/fix_obn_bug9*.py /var/tmp/
sudo python3 /var/tmp/fix_obn_bug9_pysnmp_thread_safety.py

# 3. Run OBN discover + report (should no longer hang)
sudo obn discover && sudo obn report

# 4. Gate 3: obn update c all (verify 12/12 switches confirm nv4-*-v8-090)
# 5. Gate 4: serial AP fw push — 15 APs, obn update f <ip> one at a time (target 6.11.2-0)
```

---

## How to update this file

At the **end** of every train session, before you `exit` the SSH:

1. Find your train's row in the at-a-glance table — update `Status` and `Next action`.
2. If the train has a per-train detail block below, update its **Diagnostic state** fields (the bulleted list at the top of the block).
3. If the train is in any non-trivial state (PAUSED / BLOCKED / DONE w/ Stadler) and doesn't have a detail block yet, add one. If the train has reached plain `DONE`, delete its detail block to keep the file clean.
4. Update the `Last touched` line in the block.
5. Update the `Last updated` line at the top of the file.
6. Commit if the repo is under git, or just save.

If the very next person to log into this train can't see "what's the next command to run" without asking you, the row isn't done.


<!-- pending Fzg assignment (managed by dosto-morning-brief) -->

## Pending Fzg assignment

CCU IPs discovered by morning-brief network sweep where the engineer has not yet provided a Fzg ID. These are skip-listed (not re-prompted next run). Hand-edit this section: delete the row and add a proper entry to the 4736 or 4734 series table once you identify the train (physical inspection or cross-ref against `train-ip-allocation-commission/` PDFs — do NOT trust .cfg filenames or switch hostnames since the train_id formula is broken pre-commissioning).

| CCU IP | Discovered |
|---|---|
| `10.179.22.1` | 2026-05-20 |
| `10.179.32.1` | 2026-05-20 |
| `10.179.45.1` | 2026-05-20 |
| `10.179.122.1` | 2026-05-20 | **4122 bench (not a train)** — group `50_4122_*`, live proxy `dostoneu-bench-zproxy-4122a` (10630), phantom dead proxy `dostoneu-nv4-zproxy-4122a` (13519). **2026-07-03 AR:** the 2026-06-04 dead-proxy fix had REGRESSED — all 28 hosts back on 13519 (datalen 3687, "host not found" spam). Re-fixed: massupdate 28→10630 + `zabbix_proxy -R config_cache_reload` (datalen 3687→200013). Also found + fixed stale `7.7.7.7` placeholder IPs: MAC-joined 12 live devices (1 AP `.138` + 11 SW `.178-.199`; R1=A R2=G R3=E R4=B per inventory MAC) → set SNMP iface IPs; AP host `R3_AP1` securityname `snmpadmin`→`admin` (SW/AP cred inversion). Result: 11/11 SW + AP now poll (SWSysUptime/ICMP live, ifaces UP). Bench physically has 1 AP + 11 SW; ~16 Zabbix hosts are phantom template entries left at 7.7.7.7 (engineer decision "real devices only"). **REMAINING (pre-existing, fleet-wide, NOT bench-specific):** switch+AP templates poll wrong OIDs — `snmp.statusoper.port*`, `software.version`, `switch.*`, AP `snmp.firmware_version` all `No Such Instance/Object` (see project_zabbix_switch_template_wrong_oids). R1_SW1 (A1) had no lease this session, left at 7.7.7.7 (reconciles on rerun when it leases). **2026-07-03 AR OBN:** found vanilla OBN 2.3.8 (0/11) after reboot — `obn report` hung 2h20m @99% CPU (Bug10 BFS loop on this miscabled bench; 10 devices unnumberable). Killed runaway PID, applied 10/11 patches (bug10 hand-adapted — fix-script anchor lacks `# nv6 - END` on 2.3.8; bug11 skipped, only affects `obn update f ap` + anchor also drifted), **persisted via chroot → run3 (subvolid 537), survived reboot, verified 1,2,1,1,1,1,1,1,2,1 + obn report now 4s exit 0**. NDSU `.dont` OK. OBN patches: **10/11 persisted (run3)**. **2026-07-04 AR OBN "not working" check:** OBN is functional — `discover`/`report`/`validate` all exit 0, `obn report` now 0.24s (bug10 BFS-guard present in running code). ⚠️ **Booted subvol is run1 (subvolid 544), NOT run3 (542)** — only the bug10 marker survives in the running tree; the other 9 patches are effectively absent from live code (bug10 guard alone is why report doesn't hang). Reconcile: re-persist to booted run1 or set run3 default. **Topology (10 SW leased, A1+B3 absent):** bench is correctly cabled A-G-E-B 4-Teiler, CCU in G1 — 8/10 leased SW match nv4-topology.md exactly. **A1 = COLD BYPASS** (powered off/failed; A3 e0-0 LLDP↔G1 reciprocal, both UP 10G 0 CRC) — NOT omitted/re-cabled (I made that wrong call first; see project_vds_cold_bypass). **B3 = dead/half-connected** (B1 e0-0 UP 10G but no LLDP peer + RX crc 2/TX crc 3/60k RX errors — powered off/boot-crash or bad B1↔B3 cable). AP `.138` leased (v1 form, Nomad config) but SNMP times out in discover — powered down or radio issue. None block anything on a bench. **Do NOT trust the bench PDF (`ND-DEL-OBB-035-IPA-250_Bench`)** for topology — header says "6 Teiler" and its e0-0/e0-1 table names stale 6-car coaches C/D/F; use `_shared/nv4-topology.md` (aliasing-resolved) instead. **2026-07-04 AR OBN engine prototype (running on bench NOW):** prototyped + persisted the topology-anchored coach-numbering fix (findings/RD_obn_coach_numbering_bypass_downstate). `report_dosto_neu.py` replaced (md5 2debd733, marker NDP-BYPASS-FIX) via chroot → **booted snapshot run3 (subvolid 551)**. Backup in-snapshot `report_dosto_neu.py.orig-20260704`; rollback = `nd-systemupdate.sh.dont rollback`. `obn validate` now shows **full 12-row table: 10 switches UP at correct positions + A1/B3 as DOWN rows** (was 2 rows pre-patch). bug10 guard preserved; discover/report exit 0. ⚠️ This snapshot is a bench PoC of a shared-engine change — NOT for fleet rollout; the OBN patch-count/state now differs from the 2026-07-03 baseline. **2026-07-04 AR v2 (running now, md5 a01413d5, snapshot run2):** hardened after a flaky-link false-alarm (a partial discovery scan had mislabelled healthy switches DOWN). Now: DOWN requires positive bypass-reciprocal evidence (else UNKNOWN); terminus switches (B3) → UNKNOWN not DOWN; added discovery-completeness gate (discovered vs DHCP-lease count → `⚠ DISCOVERY INCOMPLETE N/M` banner + UNKNOWN rows on partial scans). Verified live: full scan = 10 UP + A1 DOWN(reciprocal via A3,G1) + B3 UNKNOWN; forced 9/10 partial scan = INCOMPLETE banner + UNKNOWN, zero false DOWN. Prototype + partial-scan fixture + R&D writeup in findings/. **2026-07-04 AR v3 (running now, md5 ebecff21, snapshot run3):** made the completeness gate SWAP-PROOF — counts distinct leased *positions* (from `client-hostname` in dhcpd.leases) not MACs, so replacing a switch (new MAC, same 4t-A3 hostname) doesn't double-count the position and false-fire the INCOMPLETE banner (dhcpd.leases never drops old MACs). Verified vs real 1261-line leases file + simulated A3 swap (MAC-count 10→11 wrong, position-count stayed 10). Note: a swap still needs a Zabbix MAC-reconcile (NMS hosts are MAC-joined) — pre-existing, outside this fix. **2026-07-04 AR v8 commission session:** (1) **vlan7** already correct `172.19.253.2/17` (Fzg 250, even→.2) — no change. (2) **Templates upgraded v5→v8**: bench was on stale nv4 v5 templates (pkg 0.0.2) + Puppet env `Engage26`. Re-pointed to `migration_mar5` (dbc12 via real master `vmpuppet01:9494`, NOT CCU-local :9494 which hangs), bumped `dostoneu-bench.yaml template_pkg_ensure 0.0.10→0.0.19` via GitLab (commit c2490d5) + master deploy; `ndsu up` installed pkg 0.0.19 (v8) + nd-obn 2.3.8→2.2.23. Fixed 2 bench-only pkg failures blocking snapshot promotion (purged stale `nd-ccu-api`, aligned `libmosquitto1` u2→u1 — see project_bench_4122_stale_pkg_puppet_failures). Prepended `{%- set train_id=250 -%}` to all 12 v8 nv4 templates (Form-2 → renders `nv4-X-v8-250`). (3) **OBN patches** re-applied bugs 1-8,10 (2.2.23 is NOT natively patched — anchors matched; bug9 anchor absent=skip→serial push; bug11 AP-fw irrelevant) + re-applied coach-numbering prototype (wiped by ndsu up) — all persisted. **Auto-update BLOCKED**: renamed canonical `/usr/sbin/nd-systemupdate.sh`→`.disabled-20260704` (timer ExecStart finds nothing), `.dont` kept. (4) **MULTICAST STORM found+contained**: ~404k mc-pps/524Mbps into root G1 via e0-0 (A1-bypass loop, RSTP-invisible) saturated switch mgmt-CPU (load 4-5)→half the switches flapped ICMP/SNMP. Disabled G1 e0-0 (`no configure interface e0-0 enable`, runtime only) → storm gone, E/B-car stable (see project_bench_4122_multicast_storm_e0_0). (5) **v8 config pushed to 5/10 switches**: E1(.184) E2(.178) E3(.188) B1(.186) B2(.192) → all `nv4-X-v8-250` ✅ (E2/E3/B2 via `obn update c`, E1/B1 via manual TFTP/SNMP bypass — OBN LLDP-walk couldn't reach them). **Not pushed (5):** G1(.200 root, skipped — reboot would re-enable e0-0/restart storm), A2/A3/G2/G3 (isolated behind disabled e0-0). **BLOCKED on physical fix**: restore A1 (cold-bypass) so loop clears + e0-0 can re-enable + A/G-far switches reachable; then push remaining 5 to v8. Lease≠reachable trap bit repeatedly (see project_dhcp_lease_not_reachable_trap). **2026-07-04 AR session cont'd:** (6) **G1 root NOW on v8** — manual TFTP/SNMP push of a hand-patched v8 config: rendered `nv4-300-G1.cfg` then changed `interface e0-0 / enable` → `no enable` so G1 boots on v8 with e0-0 held down = NO storm (the v8 template explicitly enables e0-0; a plain push would re-trigger the storm). ⚠️ config-file port-disable MUST be `no enable`, NOT omitting the enable line — switch rejects the whole config with "missing 'enable' for port e0-0" if omitted (learned this push). Result: `nv4-G1-v8-250`, e0-0 disabled/down, e0-1→E2 up, load 1.07, E/B-car all healthy. **Storm containment now DURABLE** (baked into G1 v8 config, survives reboot) — but this means A-side stays cut off until A1 physically fixed; when A1 restored, revert G1 e0-0 to `enable`. (7) **Front coupler ports (e0-2) disabled + persisted** (`save running-config force`) on the reachable end-switches: **B1** e0-2 ✅, **A3** e0-2 ✅ (A3 done via brief e0-0 window + tight-retry before storm saturation). A1/B3 coupler ports can't be touched (powered off/dead). ⚠️ A3 still on v3 — its saved config is v3+e0-2-disabled; when A3 gets v8 later, re-verify e0-2 stays disabled in v8. **v8 progress now 6/10**: G1,E1,E2,E3,B1,B2 ✅ | A2,A3,G2,G3 blocked (A-side, need A1 power-on). **2026-07-04 AR FINAL — ALL 10 SWITCHES ON v8 ✅ + STORM RESOLVED:** pushed the remaining A-side (A2,A3,G2,G3) via a timeout-hardened detached push loop during e0-0-enabled "oscillation windows" (the storm had already degraded to intermittent-reachability, not saturation). **Two script lessons (cost several failed attempts):** (a) wrap EVERY snmpget/snmpset in `timeout` — an unguarded SNMP call hangs forever when the target flaps mid-push and wedges the whole loop; (b) resolve target IP by **MAC from dhcp-lease-list each iteration** — A-side lease IPs churn constantly (A3 moved .193→.206→...), hardcoding an IP = pinging a dead address. Final loop: enable e0-0 → wait 40s → per-target 18-22s push budget → MAC-lookup IP → hard re-disable via EXIT trap + external watchdog. Got A2/G2/G3 in one run, A3 in a focused MAC-lookup run. **KEY DISCOVERY — the v8 upgrade ITSELF resolved the storm:** the 404k-pps multicast storm was caused by an RSTP **split-brain** between mixed-config switches (v3 A-side elected G3(prio 8192) as a 2nd root while v8/G1 side saw G1(prio 0) → two root domains → partition → unicast black-hole → the "unreachable but leased" A-side + the flood). With **all 10 switches on uniform v8**, RSTP converges to a **single root (G1), no split-brain, no oscillation** — verified: every switch agrees root=G1, A-side e0-0=ROOT/FWD, A2/A3/G2/G3 = 5/5 stable reachable. The A1-bypass loop physically persists but degraded from a 404k-mc-pps CPU-saturating storm to a **benign ~3-6k-pps broadcast trickle** (loop signature: bcast in e0-0 ~3.3k + out e0-1 ~2.6k), load stable ~2.9 (not climbing). **FINAL STATE: e0-0 ENABLED + PERSISTED on G1** (`save running-config force`; running-config shows `interface e0-0/enable`) → full 10-switch fabric reachable + survives reboot. Fabric usable as-is; the residual loop is cosmetic (elevated-but-stable load) until A1 is physically restored. A1+B3 still absent (powered-off/dead — only switches not on v8, can't push until powered). Related new memory: split-brain-from-mixed-config resolved by uniform-v8; timeout+MAC-lookup push-script pattern. Last touched 2026-07-04 AR |
| `10.179.124.1` | 2026-05-20 |
| `10.179.127.1` | 2026-05-20 |
| `10.179.123.1` | 2026-05-21 | **Bench (not a train)** — confirmed by engineer 2026-05-21; do not move to series table. OEBB-251 bench (v3/train_id 251). 2026-06-04: NMS chain healthy, but physical wiring wrong (inter-coach A1→B1 should be A1→B2; CCU on A2 e0-1 should be A2 e0-3; B2 jumpered via e0-4, ring ports down; no APs). Re-cabling worklist: [findings/bench_2123_topology_recabling_2026-06-04.md](findings/bench_2123_topology_recabling_2026-06-04.md). Sibling 4122 bench had separate NMS fault (dead-proxy 13519 → reassigned to live 10630, fixed 2026-06-04). |


<!-- pending Train# assignment (managed by dosto-morning-brief) -->

## Pending Train# assignment

CCU IPs discovered by morning-brief network sweep where the engineer has not yet provided a Train#. These are skip-listed (not re-prompted next run). Hand-edit this section: delete the row and add a proper entry to the matching series table once you identify the train (cross-ref against `train-ip-allocation-commission/` PDFs — do NOT trust .cfg filenames or switch hostnames since the train_id formula is broken pre-commissioning).

| CCU IP | Discovered |
|---|---|
| `10.179.40.1` | 2026-06-08 |
