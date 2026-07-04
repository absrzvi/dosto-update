# DRIVE GUIDE — coupled-train test 2026-06-30 (read me first if you're driving this live)

**Audience:** Claude, driving this test for Abbas trackside. This is the durable brief — the
reasoning that produced the test card + scripts, so you don't re-ask decisions already made.
**Pair:** 4736-117 (Fzg 145, box1-t? — resolve) = **MASTER** (driver cab) · 4736-105 (Fzg 133) = **BACKUP**.
**CCU IPs:** master `10.179.32.1`, backup `10.179.1.1` (confirm live; may have moved).
**Files:** `README_coupling_test_2026-06-30.md` (test card, 3 parts) · `scripts/` (10 scripts + README).

## The three parts (what we're testing today)
1. **Part 1 — v9 RSTP cost.** Set coupler `e0-2` port-cost = 20000 on A1/A3/B1/B3, BOTH trains.
   Prove the ~2s fleet-wide TC/FDB-flush churn FREEZES. Validates the v9 git MR (runtime-first).
2. **Part 2 — single-FW VLAN-5 routing.** Repoint BACKUP cameras' gateway → MASTER FW, so only one
   FW routes VLAN-5 (CCTV). Chasing coupled CCTV latency.
3. **Part 3 — prove A8.** Stadler downs the BACKUP FW's VLAN-5 SVI → backup FW fully out of VLAN-5.
   If CCTV recovers only here, the backup FW's presence on bridged VLAN-5 was the culprit.

## Decision log — DO NOT re-litigate these (already decided with Abbas)
- **Master = occupied-driver cab = 4736-117/Fzg145.** Backup = 4736-105/Fzg133. Gateway target flips
  if the driver moves cabs — confirm which cab is occupied on the day.
- **Measurement is SWITCH-PORT TRAFFIC, not ping.** The CCU has NO VLAN-5 interface (cameras on
  172.18.x.x = Stadler device VLAN; CCU sees only vlan100/vlan7/bond0). `11_port_traffic.sh` watches
  port RX/TX counters; `09_precheck_measure.sh` confirms reachability first. Do not propose CCU ping.
- **Part 3 = Stadler shuts the backup FW VLAN-5 SVI — NOT a VLAN-5 prune.** Pruning VLAN 5 off a trunk
  breaks the inter-train CCTV transit the test depends on. Also: June ALREADY pruned VLAN 5 off the
  COUPLER and it was REFUTED (A8) — don't repeat it. SVI-down removes the *router* while keeping the
  *bridge*. That's the new variable.
- **Staged S0→S1→S2 with measurement at each.** All-at-once loses attribution. Keep them separate.
- **Mutations are echo-only.** Scripts 02/10/99 PRINT commands; Abbas pastes them. Don't auto-execute
  switch config changes on a live coupled train.
- **No `save running-config force`.** Keeps revert trivial; matches runtime-first plan. An
  `obn update c` from the current package reverts everything anyway.
- **VLAN 5 stays on the Frontkupplung** (engineer directive). We are NOT removing it from coupler trunks.
- **NOT a skill today** (Simplicity First — one-day, partly-Stadler-gated experiment).

## Two LIVE dependencies — surface these early, don't assume
1. **Master FW VLAN-5 return route.** Repointing backup cameras to the master FW only works if the
   master FW can route back to the backup camera subnet `172.18.194.0/24`. Works if the master FW's
   VLAN-5 interface is the `/17` (172.18.128.0/17); a `/24` needs Stadler to add a route. **Tell at S0:
   if VLAN-5 traffic never shows as RX on the master-FW trunk (A3 e1-4), the return path isn't there.**
   Stadler note already drafted asking this — confirm they answered.
2. **Counter-field regex.** `11_port_traffic.sh` parses `show interface <port> details`. The exact
   field labels aren't confirmed against live output. **Run `harvest_ports.sh <sw-ip> <port>` FIRST** —
   clean `RX=… TX=…` line = good; `could not parse` = fix the regex in harvest_ports.sh AND
   11_port_traffic.sh (kept identical).

## Execution order (deploy scripts to /tmp/cpltest on each CCU first)

### Pre-flight (both CCUs)
- Confirm pair actually COUPLED: coupler ports link-UP, not just cabled (June A6/A7 phantom-link trap —
  a flapping half-seated cable mimics the churn signature and proves nothing).
- `00_resolve.sh` → record A1/A3/B1/B3 IPs (2-min DHCP leases, resolve fresh).
- `harvest_ports.sh <sw-ip> <a-cam-port>` → validate counter parsing (dependency #2).
- Enable RSTP debug on cab switches: `swcmd $SW "configure system logging debug rstp,coupled"`.

### Part 1 (per train, then compare)
| Step | Cmd | Expect / branch |
|---|---|---|
| baseline churn | `03_churn_watch.sh 60 5 $A1 $A3 $B1 $B3` | CHURNING (+delta each sample). If FROZEN already → coupler may be down (dep, verify link) or churn isn't present this composition — note it. |
| harvest | `01_rstp_harvest.sh $A1 $A3 $B1 $B3` (tee to harvest file) | record original costs (revert) + topology |
| set cost | `02_rstp_set_cost.sh $A1 $A3 $B1 $B3` → paste 4 lines/train (8 total) | costs go to 20000; no reboot |
| after churn | `03_churn_watch.sh 60 12 $A1 $A3 $B1 $B3` | **PASS = FROZEN ≥10 min.** FAIL = churn continues → `99_revert.sh`, capture logs, escalate VDS/Giorgio (the unequal-cost role-duel question). |
| verify | `01_rstp_harvest.sh ...` | all=20000, both ends equal, one coupler FWD + twin ALTR/BLK |

PASS → greenlight v9 git MR (don't make the MR live; just record PASS).

### Part 2 + 3 (staged — measure at each)
| Stage | Action | Cmd | Read |
|---|---|---|---|
| precheck | confirm ports stream | `09_precheck_measure.sh <bk-sw> <cam-ports>` | ports link-UP, counters moving |
| **S0** | baseline (both FWs route VLAN5) | `11_port_traffic.sh S0 30 <bk-cam> <master-fw-trunk> <m-cam>` | record RX/TX. If VLAN-5 RX never at master FW → dep #1 not satisfied (raise with Stadler). |
| **S1** | repoint backup cams → master FW | `10_vlan5_set_gw.sh <bk-sw-ips>` (paste) + renew leases (bounce cam ports) → `11_port_traffic.sh S1 30 ...` | did feed/latency improve? single-routing-authority test |
| **S2** | Stadler downs backup FW VLAN-5 SVI | (Stadler) → `11_port_traffic.sh S2 30 ...` | recovers only here = **A8 PROVEN** |

**Reading the result:**
- recovers at S1 → fix = single routing authority (gateway config). Backup FW presence benign.
- recovers only at S2 → **A8 PROVEN** — backup FW's VLAN-5 presence was poisoning FW state.
- neither → cause is VLAN-15 FW↔FW transit (A8 prime suspect) or RSTP churn. Not solved by VLAN-5 work.
- ALWAYS pair port-traffic numbers with the driver's HMI observation (the actual user symptom; traffic
  is a proxy, not perceived latency).

### Cleanup before trains split
- `99_revert.sh` (paste) — restore coupler costs + backup VLAN-5 gateway.
- `no configure system logging debug` on all touched switches.
- Stadler re-enables backup FW VLAN-5 SVI.
- Kill `03_churn_watch.sh`. (Power-cycle / obn update c also clears all runtime changes.)

## Write-up after the test
- Capture harvests + per-stage tables into this folder; fill the test-card S0/S1/S2 table.
- Update `fleet-status.md` rows for 4736-117 and 4736-105 (Step 11 of the login checklist).
- Part 1 PASS → the v9 MR is greenlit (see PLAN_v9_switch_config_changelist). Part 3 result → Stadler comms.
- External comms (Stadler/Jira): short, scannable, no emoji, detail in linked doc (Abbas's house style).

## Gotchas (will bite if forgotten)
- Switch CLI = ONE command per SSH session (rejects `;` chaining). All scripts honour this.
- Switch SSH needs legacy algos — in `_common.sh` `swcmd`. Pseudo-terminal warning is harmless.
- Odd-Fzg Stadler FW sits at `.129`, not `.1` (both 145 and 133 are odd).
- Cellular link drops — background long watchers; retry missing switches, don't restart the whole run.
- Subagent/harness SSH detaches >90s — if driving via background jobs, keep a ledger and verify live
  (don't fire-and-idle).
