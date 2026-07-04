# Coupled-train test scripts — 2026-06-30 (4736-117 master + 4736-105 backup)

Bash, **run ON the CCU** (scp the whole `scripts/` folder to each CCU's `/tmp/`). Switch SSH uses the
VDS legacy-algo snippet in `_common.sh` (one command per session — CLI rejects `;` chaining).

**Mutating scripts are ECHO-ONLY** (`02`, `10`, `99`): they print copy-paste commands and run nothing.
You review, then paste each line. Read-only scripts (`00`, `01`, `03`, `11`) run directly.

## Deploy
```bash
# from laptop, per CCU (master 10.179.32.1, backup 10.179.1.1):
scp -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" -r \
    findings/coupling_test_4736-117_105_2026-06-30/scripts developer@<ccu-ip>:/tmp/cpltest
# on the CCU:
cd /tmp/cpltest && chmod +x *.sh
```

## Pre-flight (both CCUs)
- Confirm CCU reachable; pair actually coupled — **coupler ports link-UP**, not just cabled (June A6/A7).
- `./00_resolve.sh` → record A1/A3/B1/B3 IPs for that train (2-min leases — resolve fresh).
- **`./harvest_ports.sh <sw-ip> <port>`** → settle the counter-field parsing BEFORE trackside. If it
  prints a clean `RX=… TX=… RXp=… TXp=…` line, `11_port_traffic.sh` will parse (shared regex). If it
  prints `could not parse` + raw lines, adjust the regex in BOTH files (they're kept identical).
- Enable RSTP debug on cab switches before churn baseline:
  `swcmd $SW "configure system logging debug rstp,coupled"` (helper `swcmd` is in `_common.sh`).

## Part 1 — v9 Option-A coupler cost (kills TC churn)
| # | Script | Type | Notes |
|---|---|---|---|
| 1 | `01_rstp_harvest.sh <A1> <A3> <B1> <B3>` | read | capture costs + topology + counters. Tee to `../4736-<...>_harvest.txt`. SAVE the cost lines. |
| 2 | `03_churn_watch.sh 60 5 <A1> <A3> <B1> <B3>` | read | **baseline** — expect CHURNING (+delta each sample) |
| 3 | `02_rstp_set_cost.sh <A1> <A3> <B1> <B3>` | ECHO | prints 4 `port-cost 20000` lines per train; paste them (8 ports total, both trains). DO NOT save. |
| 4 | `03_churn_watch.sh 60 12 <A1> <A3> <B1> <B3>` | read | **after** — PASS = FROZEN every sample, ≥10 min |
| 5 | `01_rstp_harvest.sh ...` again | read | costs all = 20000, both ends equal, one coupler FWD + twin ALTR/BLK |

PASS → greenlight v9 git MR. FAIL → `99_revert.sh`, capture logs, escalate to VDS (Giorgio).

## Part 2 + 3 — single-FW VLAN-5 routing (CCTV latency) — STAGED

**Measurement note (corrected):** the CCU has NO interface on VLAN 5 — it can't ping cameras
(`172.18.x.x` is a Stadler device VLAN). So we DON'T ping from the CCU. Instead we monitor the
**camera switch ports' RX/TX counters** (cameras stream continuously) and the **master-FW trunk
(A3 e1-4)** to confirm VLAN-5 traffic is reaching the master FW. Same byte-delta technique as the
playbook Phase-5/7 sampler. **`09_precheck_measure.sh` first** — proves the ports are reachable and
streaming before we commit to the staged window.

Run `11_port_traffic.sh` at **each** stage with identical targets; pair with driver HMI observation.

| Stage | Action | Script | Owner |
|---|---|---|---|
| **pre** | confirm camera ports reachable + streaming | `09_precheck_measure.sh <sw-ip> <cam-ports...>` | Nomad |
| **S0** | coupled baseline, both FWs routing VLAN 5 | `11_port_traffic.sh S0 30 <ip:port>...` | Nomad |
| **S1** | repoint backup cameras → master FW | `10_vlan5_set_gw.sh <backup-sw-ips...>` (ECHO) + renew leases, then `11_port_traffic.sh S1 30 ...` | Nomad |
| **S2** | backup FW VLAN-5 SVI down | Stadler shuts SVI on cue, then `11_port_traffic.sh S2 30 ...` | **Stadler** |

Watch these targets (`<ip>:<port>`) at every stage: a **backup camera port** (TX = still streaming?),
the **master-FW trunk A3 e1-4** (RX = VLAN-5 reaching master FW?), and a **master camera port**
(control — unchanged). VLAN-5 default-router CLI is verified: `configure ip dhcp-server group video
default-router <ip>` (manual v2.0.4 L4597).

**Reading:** latency/feed recovers at S1 = single-routing-authority fix · recovers only at S2 =
**A8 PROVEN** (backup FW presence was poisoning state) · neither = VLAN-15 FW↔FW transit / RSTP churn.

**Stadler dependency (confirm first):** master FW needs a return route to `172.18.194.0/24` — works if
its VLAN-5 interface is the `/17`; else Stadler adds the route. Tell at S0: if VLAN-5 traffic never
appears as RX on the master-FW trunk, the return path isn't there yet.

## Revert / cleanup
- `99_revert.sh` (ECHO) — restore coupler costs + backup VLAN-5 gateway; turn off debug logging.
- Stadler re-enables backup FW VLAN-5 SVI.
- Kill `03_churn_watch.sh`. Power-cycle / `obn update c` also clears all runtime changes.

## Notes / traps
- Nothing here runs `save running-config force` — keeps revert trivial and matches "runtime-first" plan.
- `10_vlan5_set_gw.sh` assumes the group-edit verb `ip dhcp-server group video default-router <ip>`;
  **verify the live CLI form** off one switch first (script's STEP 0 prints how). Adjust if the
  running-config shows a different form.
- `11_latency_matrix.sh` pings FROM wherever it runs — it must sit on VLAN 5 (camera shell / VLAN-5
  probe / laptop on a VLAN-5 access port). Confirm source placement before S0.

## Offline RSTP analysis (laptop, no CCU needed)

Two pure-Python models of the nv6 active topology, built from the template trunk descriptions.
Used to evaluate the B1↔B3 chord cost (`400100`) and the coupled-traction limit.

- **`rstp_sim.py [v9|template]`** — shortest-path-to-root tree for a single train and for 2×6
  coupled in all three orientations (A-A / B-B / A-B). Reports which link RSTP blocks per loop.
  Finding: the `400100` chord is load-bearing (it's the blocked link in the solo case); under v9
  symmetric-20000 couplers it is ~200× too large and pushes the coupled block onto a spine link.
- **`rstp_diameter.py`** — the real limit is the BPDU **message-age budget**, not node count.
  Computes worst-case root-to-leaf HOP COUNT over the active tree vs. the VDS Max-Age wall
  (Max Age 20s, +1/hop ⇒ 19-hop hard wall) and the conservative IEEE design diameter (7).
  Default VDS trunk PortPathCost = 200000 (manual Table 4); chord = 400100.

  Results: single 6-Teiler = 9 hops; 2×6 coupled = 12–16 hops (B-to-B is worst at 16);
  4+4+4 chain = 9–10 hops. ALL exceed the conservative-7 diameter (MARGINAL) but sit under the
  19-hop message-age wall. Triple traction WITH a 6-Teiler (42/48/54 switches) was not modeled
  as a single domain — it is over the practical limit and needs an L3/routed boundary
  (see project_3x6_triple_traction_required).

## F4 DHCP-loop instrumentation (for the NEXT coupling window)

Finding F4: while coupled, ~9/18 of 117's switches loop DISCOVER→OFFER→(no REQUEST,
no ACK)→DISCOVER and recover on decouple. The CCU log (EVIDENCE E5) proves a SINGLE
server (one server-id, no peer-CCU offers crossed) — so the failure is between the
server's OFFER and the switch's REQUEST. **The "two CCUs / nd-redundancy modulo /
competing-OFFER" theory was investigated and REFUTED** by E5 line 128 (only 117's
server-id seen). Do not re-test it.

These two scripts capture BOTH ends simultaneously to localise the OFFER→REQUEST gap.
Run them together during a coupling window, once coupled and once after decouple.

- **`12_dhcp_diag_ccu.sh [MAC] [secs]`** — CCU-side. tcpdump of all (or one) switch
  DHCP on vlan100 → pcap + readable + a per-switch DORA tally that flags ">>> F4 LOOP"
  rows (offer, no request). Read-only.
- **`13_dhcp_mirror_switch.sh <victim-ip> <uplink-port> [dest-port]`** — switch-side.
  Port-mirrors a victim switch's ROOT/uplink port onto a spare access port (default
  e0-5) so a capture laptop on that jack sees what the victim actually receives/sends.
  Uses `sysadmin port-mirror` = runtime-only, NOT saved, cleared on reboot. The mirror
  command is ECHO-ONLY (you paste it); pre-checks + teardown print are read-only.

Decision table once both captures are in hand:
  * OFFER leaves CCU (12) but NOT seen at switch (13)  → lost in coupled fabric (our L2/RSTP)
  * OFFER seen at switch (13), no REQUEST emitted       → switch DHCP client wedged (→ VDS)
  * REQUEST emitted at switch (13), absent at CCU (12)  → return-path broadcast loss (our L2)

Pick the victim = an affected (looping) switch from the 12_ccu tally, furthest from CCU.
Find its uplink/root port via `show spanning-tree` (the ROOT port). Never mirror onto a trunk.
