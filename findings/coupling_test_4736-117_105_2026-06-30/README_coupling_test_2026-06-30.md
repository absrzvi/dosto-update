# Coupled-Train RSTP Test — 4736-117 (Fzg 145) + 4736-105 (Fzg 133)

**Date:** 2026-06-30 · **Engineer:** Abbas Rizvi (Nomad Digital) · **Status:** PREP — test not yet run.

## Live log (2026-06-30)
- **117 master vlan7 FIXED.** Found misrendered `172.19.208.2/17` (decodes Fzg 160) → corrected to
  `172.19.200.130/17` via NDSU chroot + safe_reboot. Post-reboot verified: live+nmconnection match,
  FW `172.19.200.129` ARP-reachable, ICMP 100% loss = commissioned. This was a real blocker for the
  VLAN-5 test (master FW path) — now clear.
- **105 backup vlan7 OK** (`172.19.194.130/17`), FW commissioned.
- ⚠️ **Switch fabric still settling.** After repeated consist power-cycles, switches re-joining
  vlan100 slowly. tcpdump confirmed it's NOT dark — caught VDS `a0:59:3a:d0:80:00` getting a DHCP
  offer + APs leasing live; earlier "0 switches" reads were timing artifacts (sampled between
  boot and lease-completion). CCU side fully healthy: bond0 up (both 10G members, 0 failures),
  dhcpd serving, vlan7+FW good. Some switches coming online gradually (engineer on-ground confirms).
- **DECOUPLE REQUESTED (Stadler).** Plan: decouple to two clean solo trains → let each stabilize →
  confirm single clean root D1 per train + capture baseline coupler costs → **re-couple** → run Part 1
  (v9 STP cost churn test). NOTE: Part 1's actual proof needs them COUPLED — decouple is for clean
  baselines + the v9 fix, not the test itself. Confirm with Stadler the plan is decouple→stabilize→
  **re-couple**, not decouple-and-leave.
- **Post-decouple gate (June A6/A7 lesson):** verify all four `e0-2` coupler ports read link-DOWN on
  each train (`show interface summary`) before trusting any STP/cost reading — "cables removed" ≠
  link down; phantom/half-seated couplers flap and corrupt the reading.
- **Resume order when switches up:** 00_resolve → harvest_ports (validate counters) → 01_rstp_harvest
  (baseline costs + confirm clean root) → [re-couple] → 03_churn_watch baseline → 02_rstp_set_cost →
  03_churn_watch after → verify.

---

**Purpose:** Runtime validation of switch-config **v9 Option A** (flat symmetric coupler port-cost = 20000)
on a real coupled pair, before committing the change to the nv6/nv4/fv5/fv6 template repos as a git MR.
Follow-on to the 2026-06-12 test (4736-110 + 4736-119), which proved cost=20000 stops the TC churn
**on the active link only** — today validates the full four-port scheme on both trains.

**Plan of record:** `../coupling_test_4736-110_119_2026-06-12/PLAN_runtime_test_option_a_v9_2026-06-20.md`
**v9 change-list:** `../coupling_test_4736-110_119_2026-06-12/PLAN_v9_switch_config_changelist_2026-06-20.md`

## Test pair

| Train# | Fzg | CCU IP | CCU vlan7 | Stadler FW (odd→.129) | Notes |
|---|---|---|---|---|---|
| 4736-117 | 145 (odd) | `10.179.32.1` | `172.19.200.130/17` | `172.19.200.129` | VERIFIED CLEAN 2026-05-29: 18/18 sw, 24/24 AP, 0/18 LLDP faults, single stable root |
| 4736-105 | 133 (odd) | `10.179.1.1` | `172.19.194.130/17` (computed) | `172.19.194.129` | DONE w/ Stadler; ⚠️ Coach 5 AP2 missing (pre-existing HW gap, NOT test-related) |

Both 6-car nv6 → 18 switches each → **36-switch coupled fabric** (same scale as June).
Coupler ports = `e0-2` on **A1, A3, B1, B3** of each train.

## Success criteria (all must hold to greenlight v9)

- [ ] All four coupler ports on **both** trains read `port-cost 20000` (no train_id value)
- [ ] Both ends of **each** coupler link show **equal** cost (asymmetry gone)
- [ ] Topology correct: single root, one coupler link FWD, redundant twin ALTR/BLK
- [ ] **Zero TC churn**: with `debug rstp,coupled` on, per-switch "Flushing all entries" / TC cycle
      does NOT recur — frozen count over ≥10 min window (vs the captured churning baseline)
- [ ] No new CRC / carrier-false on coupler ports

## Pre-flight checks (before Step 0)

- [ ] Both CCU IPs live (DHCP/state may have moved since May) — `ssh ... developer@<ccu-ip>`
- [ ] Pair actually coupled — **verify coupler port link-state UP**, not just "cables on" (June A6/A7 phantom-link trap)
- [ ] Note coupling orientation (B-B / A-A / A-B) — Option A should hold in all four
- [ ] Fresh switch IPs via `sudo dhcp-lease-list` (2-min leases — never reuse)

## Procedure (condensed — full commands in the PLAN)

0. Arm churn watcher + `configure system logging debug rstp,coupled` on cab switches; **capture churning baseline first**.
1. Capture current per-port costs for precise revert (`show running-config | grep -A3 "interface e0-2"`).
2. Set `configure interface e0-2 spanning-tree port-cost 20000` on all 4 coupler ports, both trains. One cmd/session. **Don't save.**
3. Verify symmetric costs + safe topology + flush count **freezes** ≥10 min.
4. PASS → greenlight v9 git MR. FAIL → revert (Step 1 values), capture logs, escalate to VDS (Giorgio).

## Cleanup before trains split

- [ ] `no configure system logging debug` on all switches (runtime-only; power cycle also clears)
- [ ] Kill CCU storm watchers
- [ ] Revert runtime cost change if NOT committing to v9 deploy (or leave — `obn update c` from v8 reverts it)

---

# Part 2 — Single-FW VLAN-5 routing test (CCTV latency)

**Hypothesis (from June A8):** coupled CCTV/speaker latency is caused by Stadler having done
NO coupling-specific FW config. When coupled, two FWs are both online, each train's devices use
their own train's FW as default gateway → FW↔FW interaction over VLAN-15 degrades inter-VLAN routing.
**Idea:** designate one FW as the single inter-VLAN router for VLAN 5.

**Master / Backup designation:**
- **Master = 4736-117 (Fzg 145)** — driver sits here, checks the HMI. Master FW routes all VLAN 5.
  (Confirm on the day which cab is actually occupied — master = occupied-driver train.)
- **Backup = 4736-105 (Fzg 133)** — its VLAN-5 devices get repointed to the master FW.

**Scope today: VLAN 5 (CCTV) ONLY.** VLAN 9 (Sprechstelle/speaker) left on local FW — isolate one variable first.

## Mechanism (CORRECTED 2026-06-30 from live nv6 templates)

Cameras are **DHCP clients**; the VDS switch runs a **per-port DHCP server**. The gateway is NOT a
per-port `default-gw` line — it is the **`default-router` option in the `video` DHCP client-group**
(`dhcp_groups/video_group.j2`). Per-port stanzas only set the camera *address*
(`dhcp-server client-address`).

**VLAN-5 space = `172.18.128.0/17`** (netmask `255.255.128.0` from video_group). Per-train subnets:

| Train | Role | VLAN-5 default-router (FW) | Camera addresses | DHCP server-id |
|---|---|---|---|---|
| 4736-117 / Fzg 145 | MASTER | `172.18.200.129` | `172.18.200.158+` | `172.18.200.254` |
| 4736-105 / Fzg 133 | BACKUP | `172.18.194.129` (own, today) | `172.18.194.158+` | `172.18.194.254` |

Both subnets sit inside the same `/17` → a FW with a `/17` VLAN-5 interface is on-link to both.

## The change (CCTV-only)

1. **[NOMAD] On the BACKUP train (Fzg 133) switches** — change the `video` DHCP group `default-router`
   from `172.18.194.129` → **`172.18.200.129`** (the master FW). Runtime equivalent of editing
   `video_group.j2`. Applies to all VLAN-5 camera ports on the backup train.
2. **[NOMAD] Force DHCP lease renewal** on backup VLAN-5 ports (poe cycle / `no enable`→`enable`,
   or wait out the lease) so cameras pick up the new gateway.
3. **[STADLER — dependency, the half we don't own]** Master FW (`172.18.200.129`) needs a **return
   path** to the backup camera subnet `172.18.194.0/24`. Works only if the master FW's VLAN-5
   interface is the full `172.18.128.0/17` (or a static route to `172.18.194.0/24`). If it's a
   narrow `/24`, backup-camera replies black-hole → Stadler must add the route. **This is the
   coupling-specific FW config Stadler has not done.**
4. **[STADLER — possible 2nd step]** Backup FW (`172.18.194.129`) is still live on the bridged
   VLAN-5 segment (ARP/advertise). If A8 FW↔FW interaction persists, may need Stadler to quiet the
   backup FW's VLAN-5 routing.

## Open question (decides feasibility)

**What mask is the master FW's VLAN-5 interface configured with?** Not in our files.
- `/17` → Nomad `default-router` change + Stadler confirm is enough.
- `/24` → Stadler must add a route to `172.18.194.0/24`.
On-the-day probe: from a backup camera (after change + renewal), ping master FW `172.18.200.129`,
then ping the master HMI. Both succeed = return path OK.

## Part 2 success criteria

- [ ] Backup VLAN-5 cameras show gateway `172.18.200.129` (master FW) after lease renewal
- [ ] Backup camera → master FW reachable (return path proven, Stadler dependency satisfied)
- [ ] HMI CCTV feed latency measurably improved vs coupled-baseline (driver observation + timing)
- [ ] No loss of CCTV on EITHER train (master cameras unaffected; backup cameras still reachable)

## Part 2 revert

- Restore backup `video` group `default-router` → `172.18.194.129` (own FW); renew leases.
- Power cycle / `obn update c` from current package also reverts (runtime change only).

---

# Part 3 — Prove A8: is the BACKUP FW's presence on VLAN 5 the culprit?

**Question:** after repointing backup cameras to the master FW (Part 2), the backup FW is still
alive on the bridged VLAN-5 segment (ARP/advertise/route). If A8's FW↔FW interaction is real,
latency won't fully clear until the backup FW is OUT of VLAN-5 routing entirely.

## Mechanism (CORRECTED — do NOT prune VLAN 5)

⚠️ **Pruning VLAN 5 off any trunk is WRONG and REJECTED.** VLAN 5 carries the inter-train CCTV
traffic that must reach the master HMI — it has to stay bridged everywhere. The goal is narrower:
**stop the backup FW from routing/participating on VLAN 5, while VLAN 5 keeps flowing.**

| Approach | Effect | VLAN-5 transit intact? | Owner | Verdict |
|---|---|---|---|---|
| **1. Stadler downs backup FW's VLAN-5 SVI/interface** | FW stops routing/ARPing VLAN 5; fabric still bridges VLAN 5 to master FW | ✅ Yes | **Stadler** | ✅ **CHOSEN** (Stadler on-site) |
| 2. Disable backup A3 e1-4 physical trunk | FW gone from ALL vlans; backup loses own VLAN 2/3/7/9 routing | ⚠️ cameras still reach master over coupler | Nomad | Fallback only |
| 3. Prune VLAN 5 off backup A3 trunk | breaks CCTV transit | ❌ No | — | ❌ REJECTED |

Note vs June: June pruned VLAN 5 off the **coupler** (removed the direct L2 bridge) → refuted.
Part 3 removes the **second router** (backup FW) while keeping the bridge → genuinely new variable.

## Staged sequence (3 measurement points — clean attribution)

| Stage | Change | Owner | What it isolates |
|---|---|---|---|
| **S0 — coupled baseline** | both FWs routing VLAN 5 (current default) | — | the broken state |
| **S1 — gateway repoint** | backup cameras → master FW (Part 2 change + lease renew) | Nomad | does single routing-authority alone fix it? |
| **S2 — backup FW VLAN-5 SVI down** | Stadler shuts backup FW (`172.18.194.129`) VLAN-5 interface | Stadler | was the backup FW's passive presence poisoning state? (A8) |

**Reading the result:**
- Latency clears at **S1** → fix is single-routing-authority (gateway config). Backup FW presence benign.
- Latency only clears at **S2** → **A8 PROVEN**: backup FW's presence on bridged VLAN 5 was the culprit.
- Clears at neither → cause is elsewhere (VLAN-15 FW↔FW transit per A8 prime suspect; or RSTP churn).

## Measurement at each stage (both, for comparability)

**The CCU has no VLAN-5 leg** → cannot ping cameras. Measure at the SWITCH PORTS instead
(`11_port_traffic.sh`), preceded by `09_precheck_measure.sh` to confirm ports reachable + streaming.

For S0 / S1 / S2 capture:
- **Objective (port counters):** RX/TX Mbps + pps via byte-delta on — a **backup camera port**
  (TX = still streaming?), the **master-FW trunk A3 e1-4** (RX = VLAN-5 reaching master FW?), and a
  **master camera port** (control). Plus CRC/carrier-false/drops hold at 0.
- **Subjective:** driver/HMI observation of CCTV feed lag (timestamp + qualitative description).

| Stage | backup-cam TX (Mbps/pps) | master-FW trunk RX (Mbps/pps) | master-cam (control) | Driver observation |
|---|---|---|---|---|
| S0 | | | | |
| S1 | | | | |
| S2 | | | | |

## Part 3 revert

- S2: Stadler re-enables backup FW VLAN-5 SVI.
- S1: restore backup `video` group `default-router` → `172.18.194.129`; renew leases.
- Power cycle / `obn update c` reverts all runtime switch changes.

---

## Raw data (to be captured during run)

- `4736-117_fzg145_harvest.txt` — TBD
- `4736-105_fzg133_harvest.txt` — TBD
- `tc_trace_145.txt` / `tc_trace_133.txt` — TBD
- `costs_before_after.md` — per-port cost table, before vs after
