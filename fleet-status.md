# DOSTO Fleet — v8 Rollout Status

**Last updated:** 2026-05-21 by Abbas Rizvi (12-train status check via parallel state-inventory subagents — drift report folded into rows below; see "2026-05-21 status check drift summary" at top of per-train section)
**Update discipline:** This file is the source of truth for "where did we leave off". Every engineer **must update the relevant row at the end of every train session, before logging out** — this is Step 11 of the train-login checklist. If you don't update, the next person can't pick up.

**Companion file:** Narrative per-train history (recovery sequences, discovered lessons, session context) lives in [`fleet-journal.md`](fleet-journal.md). This file holds **current state** only — table + diagnostic-state bullet lists. Prose blocks in the per-train detail sections below are being migrated to the journal as each train is visited. When you visit a train, move its prose to the journal and trim its block here to just the diagnostic-state fields.

## Legend

| Lozenge | Status | Meaning |
|---|---|---|
| 🟢 | **DONE** | All v8 work complete, no Nomad action remaining |
| 🟢 | **DONE w/ Stadler** | Nomad work complete, awaiting Stadler on cabling/FW |
| 🔵 | **IN PROGRESS** | Actively being worked on this session |
| 🟡 | **PAUSED** | Partial work; train powered off mid-run; will resume as-is |
| 🔴 | **BLOCKED** | Stadler cabling fault must be fixed before we can continue |
| ⚪ | **UNKNOWN** | Visited but state not captured here yet, or never visited |

Field-level emoji used in the per-train detail blocks below: ✅ done · 🟡 partial · 🔴 broken · ⏸️ paused · ⬜ not started · ❓ unknown / not yet checked

## Fzg-ID convention

- **4736 series**: `Fzg = train# + 28` (e.g. 4736-103 = Fzg 131, 4736-120 = Fzg 148).
- **4734 series**: `Fzg = train# − 100` (confirmed via 4734-120 PDF header).
- **4705 / 4706 series**: not yet touched in this rollout (different platform).

---

## Fleet at a glance

Five-column scan tables. For full per-train detail (OBN patches, switch firmware, AP firmware, vlan7, Stadler cabling, FW reach, health check, customer report, last touched), see the per-train detail blocks below.

### 4736 series (DOSTO NEU 6-car)

| Fzg | Train# | CCU IP | Status | Next action |
|---|---|---|---|---|
| 129 | 4736-101 | ❓ | ⚪ UNKNOWN | initial visit |
| 130 | 4736-102 | `10.179.47.1` | 🟡 **PAUSED** | push config to 3 `-man` switches (.180 .186 .187), then push AP fw 6.10.0-0→6.11.2-0 on 24 APs |
| 131 | 4736-103 | `10.179.11.1` | 🟡 **PAUSED — awaiting Stadler on F3 AP3m + B2 null fw** | reboot to activate run3 (8/8 OBN persisted); push AP fw 6.10.0-0→6.11.2-0 after Stadler |
| 132 | 4736-104 | `10.179.10.1` | 🟡 **PAUSED — train offline; D4 BLOCKED Stadler** | verify .231; push .237 .238 .240 — see detail |
| 133 | 4736-105 | `10.179.1.1` | 🟢 **DONE w/ Stadler** | wait for Stadler on Coach5 AP2 + FW path |
| 134 | 4736-106 | `10.179.19.1` | ⚪ UNKNOWN | confirm v8 state — only customer report on file |
| 135 | 4736-107 | ❓ | ⚪ UNKNOWN | initial visit |
| 136 | 4736-108 | `10.179.8.1` | 🟡 **PAUSED — Stadler register #2/#3 likely resolved** | 2026-05-21 status check: 18/18 sw + 24/24 APs now visible (was 2 sw + 9 APs on 2026-05-19). State-inventory said OBN 3/8 — false-negative; re-verify with `dosto-obn-patches --check` (this CCU was likely never patched per fleet-status detail block, so could be genuinely 0/8 — confirm). Run LLDP topology check to confirm register #2/#3 resolved, then apply OBN patches + full v8 push |
| 137 | 4736-109 | `10.179.28.1` | 🔴 **BLOCKED** | wait for Stadler on register #4 (AP install at B3); CCU IP populated from fleet control sheet 2026-05-20 (Train NC ID T28, prio test train, v8/6.10.0 per sheet); 2026-05-21 status check confirmed: 18/18 sw on v8-137, 21/24 APs (3 missing AP1m/AP2m/AP3m on one B-coach), broken train_id template, 0/8 OBN patches (genuinely first-visit) |
| 138 | 4736-110 | `10.179.23.1` | 🟡 **PAUSED — AP fw DONE; L2 health + report pending** | OBN 8/8+bug9 persisted (run1) · 18/18 sw v8-138 ✅ · **24/24 APs at 6.11.2-0** ✅ (2026-05-20); remaining: L2 health sweep + customer report |
| 139 | 4736-111 | `10.179.24.1` | 🟡 **PAUSED — partial v8 push in progress** | 2026-05-21 status check: 3/18 switches already on `nv6-*-v8-139` config (C3, B2, B3); 15/18 still on v3 config. State-inventory said OBN 4/8 — false-negative; re-verify with `dosto-obn-patches --check`. All 24 APs visible. Resume: finish v8 switch config push. |
| 140 | 4736-112 | ❓ | ⚪ UNKNOWN | CCU IP `10.179.12.1` was attributed here in error — confirmed 2026-05-21 that IP belongs to Fzg 147. `10.179.40.1` also unconfirmed. True CCU IP unknown — physical inspection required. |
| 141 | 4736-113 | ❓ | ⚪ UNKNOWN | initial visit |
| 142 | 4736-114 | ❓ | ⚪ UNKNOWN | initial visit |
| 143 | 4736-115 | `10.179.18.1` | 🟡 **PAUSED — batch experiment result: 8/24 at 6.11.2-0 (33%)** | 2026-05-21 `obn validate`: 8/24 APs at target (coach 1 = 4/4, coach 2 = 3/4, coach 6 = 1/4; coaches 3/4/5 = 0/4). State-inventory said OBN 4/8 — false-negative; re-verify with `dosto-obn-patches --check`. TFTP helper lost on reboot. Resume: re-apply TFTP helper, retry 16 remaining APs serial. Coaches 4-6 also need AP*-v1 → AP*m-v1 config refresh. |
| 144 | 4736-116 | `10.179.16.1` | 🟡 **PAUSED — AP fw 9/23 done** | 2026-05-21 status check: btrfs subvol id changed 303 → 306 since 2026-05-20 (a promote happened — note, not blocking). 9/23 APs at 6.11.2-0; 13 still on 6.10.0-0; Coach 6 AP4 in `incomplete` firmware state. Coach 6 AP3 now visible (Stadler register #6 may be self-resolved — confirm). State-inventory said OBN 4/8 — false-negative; re-verify with `dosto-obn-patches --check`. Resume: re-apply TFTP helper, finish 14 remaining APs serial, AP*-v1 → AP*m-v1 config refresh coaches 4-6. |
| 145 | 4736-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 146 | 4736-118 | `10.179.21.1` | ⚪ UNKNOWN | CCU IP populated from sheet 2026-05-20; confirm v8 state — only baseline + customer report on file |
| 147 | 4736-119 | `10.179.12.1` | 🔵 **IN PROGRESS — AP config now Nomad-form** | 2026-05-21 status check: 18/18 sw on `nv6-*-v8-147`, 24/24 APs visible with Nomad-form hostnames (AP*-v1/AP*m-v1, no longer factory RT610LV-dosto-*). State-inventory said OBN 4/8 — false-negative; re-verify with `dosto-obn-patches --check`. vlan7 ARP shows `.129` not `.1` — same anomaly as Fzg 139, needs Q1/Q2/Q3 probe. Resume: push AP firmware. |
| 148 | 4736-120 | `10.179.2.1` | 🔴 **BLOCKED — E3 coach no power** | 2026-05-21 status check: 17/18 sw (E3 absent), 22/24 APs (2 E-coach APs absent) — E3 coach still off. State-inventory said OBN 4/8 — false-negative; treat as still 8/8. Stadler to restore E3 coach power. |
| 149 | 4736-121 | ❓ | ⚪ UNKNOWN | initial visit |
| 150 | 4736-122 | ❓ | ⚪ UNKNOWN | initial visit |
| 151 | 4736-123 | ❓ | ⚪ UNKNOWN | initial visit — CCU IP was incorrectly listed as 10.179.23.1 (that is Fzg 138) |

### 4734 series (DOSTO NEU 4-car)

vlan7 IPs marked ✅ (PDF) are confirmed from the IP-Port-Allocation PDF; ❓ (expect ...) are computed but not yet verified on the live CCU.

| Fzg | Train# | CCU IP | Status | Next action |
|---|---|---|---|---|
| 1 | 4734-101 | ❓ | 🔴 **BLOCKED** | wait for Stadler on register #1 (re-patch E↔B trunk) |
| 2 | 4734-102 | ❓ | ⚪ UNKNOWN | initial visit |
| 3 | 4734-103 | ❓ | ⚪ UNKNOWN | initial visit |
| 4 | 4734-104 | ❓ | ⚪ UNKNOWN | initial visit |
| 5 | 4734-105 | ❓ | ⚪ UNKNOWN | initial visit |
| 6 | 4734-106 | ❓ | ⚪ UNKNOWN | initial visit |
| 7 | 4734-107 | ❓ | ⚪ UNKNOWN | initial visit |
| 8 | 4734-108 | ❓ | ⚪ UNKNOWN | initial visit |
| 9 | 4734-109 | `10.179.38.1` | ⚪ UNKNOWN | L2 healthy (12/12 sw, 16 APs, 0 errors) — v5 config; B1+B3 ZFR e1-11 DOWN; FW probe incomplete (CCU dropped) |
| 10 | 4734-110 | ❓ | ⚪ UNKNOWN | initial visit |
| 11 | 4734-111 | ❓ | ⚪ UNKNOWN | initial visit |
| 12 | 4734-112 | `10.179.37.1` | 🟡 **PAUSED — ready to start commissioning** | 2026-05-21 status check at corrected IP: 12/12 sw (nv4-*-v8-012), 16/16 APs all correct config names, vlan7 ✅ `172.19.134.2/17`, train_id ✅. State-inventory said OBN 0/8 — could be genuine first-visit or false-negative; verify with `dosto-obn-patches --check`. Resume: confirm OBN state → full commissioning pipeline. |
| 13 | 4734-113 | `10.179.46.1` | 🟡 **PAUSED — v7 → v8 push needed** | 2026-05-21 status check at corrected IP: 12/12 sw visible but on `nv4-*-v7-013` config (not v8). 16/16 APs all plain `AP[1-4]-v1` (zero m-variants — unusual for nv4, verify expected). State-inventory said OBN 4/8 — false-negative; re-verify with `dosto-obn-patches --check`. vlan7 ✅ `172.19.134.130/17`. Resume: confirm OBN state, v7 → v8 switch config push. |
| 14 | 4734-114 | `10.179.44.1` | ⚪ UNKNOWN | discovered 2026-05-21 via morning-brief sweep; matched to 4734-114 (T44, status `Done`, NC release 2025.2.1 per fleet control sheet); initial visit pending |
| 15 | 4734-115 | ❓ | ⚪ UNKNOWN | initial visit |
| 16 | 4734-116 | ❓ | ⚪ UNKNOWN | initial visit |
| 17 | 4734-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 18 | 4734-118 | ❓ | ⚪ UNKNOWN | initial visit |
| 19 | 4734-119 | `10.179.45.1` | 🟡 **PAUSED — AP fw DONE (16/16 at 6.11.2-0 confirmed)** | 2026-05-21 `obn validate`: 16/16 APs ✅, 12/12 sw ✅. vlan7 `172.19.150.130/17` (per Nomad internal train_id 45 convention, NOT formula from Fzg 19 — confirmed correct in detail block). State-inventory said OBN 3/8 — false-negative; re-verify with `dosto-obn-patches --check`. Resume: LLDP check + L2 health sweep + customer report. |
| 20 | 4734-120 | `10.179.49.1` | 🟢 **DONE — customer report pending** | 2026-05-21 status check: 12/12 sw + 16/16 APs ✅, vlan7 ✅. State-inventory said OBN 3/8 — false-negative; train_id template "missing" claim also suspect (verify via direct `cat /etc/obn/template/nv4-*.cfg`). Customer report only remaining. |
| 21 | 4734-121 | `10.179.50.1` | 🟢 **DONE — customer report pending** | 2026-05-21 `dosto-obn-patches --check` confirmed 8/8 OBN markers all present in run2/id297; state-inventory's 4/8 reading was false-negative. 12/12 sw + 16/16 APs ✅, vlan7 ✅. Customer report only remaining. |

### 4706 series

Different platform from 4734/4736 NEU; discovered on the management VLAN as part of the 2026-05-20 morning-brief sweep, populated from the Fleet Control Sheet (2026-02-11).

| Train# | CCU IP | Status | Next action |
|---|---|---|---|
| 4706-101 | `10.178.20.1` | ⚪ UNKNOWN | sheet `Investigate`; initial visit |
| 4706-102 | `10.179.15.1` | ⚪ UNKNOWN | sheet `Investigate`; initial visit |
| 4706-103 | `10.179.17.1` | ⚪ UNKNOWN | sheet `Investigate` — switch config updated to v6 on 2026-02-12; more analysis from Stadler needed (RCU + Sec-Gateway); 2026-03-17 request to check monitors in wagon F |

### 4705 series

| Train# | CCU IP | Status | Next action |
|---|---|---|---|
| 4705-101 | `10.179.42.1` | ⚪ UNKNOWN | sheet `Done`; initial visit — was previously attributed to Fzg 13 in error |
| 4705-102 | `10.179.43.1` | ⚪ UNKNOWN | sheet `Done`; initial visit |
| 4705-103 | `10.179.42.1` | ⚪ UNKNOWN | sheet `Done`; **IP conflict with 4705-101** in the sheet — investigate |

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
- **Fzg 20** — DONE but active subvol is run1/id297, not run2/id294 where patches were persisted. Customer report unaffected.
- **Fzg 21** — DONE but OBN markers 4/8 in active subvol. Customer report unaffected.
- **Fzg 137** — matches BLOCKED state; first-visit unpatched as expected.

## Per-train detail

One block per train that's been touched or has known state. Fields under each block:

- **OBN patches** — `8/8` all bug fixes applied · `5/8` only `fix_obn.py` applied · `0/8` vanilla CCU · `persisted` = baked into btrfs run<N> via `nd-systemupdate.sh shell` (survives reboot)
- **Switches v8** — target `18/18` (6-car) or `12/12` (4-car); `mixed` = some v3/v4 + some v8 (RSTP storm risk)
- **APs** — target firmware `6.11.2-0`, config `v1`; `factory` = some/all in `RT610LV-…-v1-FD` (need LuCI bypass)
- **vlan7** — formula `172.19.<128+Fzg//2>.<2 if even else 130>/17`; persists in `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection`
- **Stadler cabling** — ✅ clean topology · 🔴 cable fault open · ❓ not yet checked
- **FW reach** — TCP probe to the train's `172.19.<octet3>.1` (Stadler firewall, host `.1`)
- **Health check** — date of last `/dosto-l2-health` run
- **Customer report** — latest version filed in `reports/customer/`
- **Last touched** — `YYYY-MM-DD <initials>`

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
- **Health check:** ⬜ (defer until 18/18 config + 24/24 AP firmware complete)
- **Customer report:** ⬜ (defer until health check done)
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
- **Health check:** ⬜
- **Customer report:** ⬜

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
- **Health check:** ⬜
- **Customer report:** ⬜

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

### Fzg 133 — 4736-105 — 🟢 DONE w/ Stadler

**Status:** 🟢 **DONE w/ Stadler** · **CCU:** `10.179.1.1` · **Last touched:** 2026-05-05 AR

**Diagnostic state:**
- **OBN patches:** ✅ persisted (run3)
- **Switches v8:** ✅ 18/18
- **APs:** ✅ 20/21
- **vlan7:** ✅ `172.19.194.130`
- **Stadler cabling:** ✅ clean
- **FW reach:** 🔴 not commissioned
- **Health check:** ✅ 2026-05-05
- **Customer report:** ✅ v1.0

All 18 switches on `nv6-*-v8-133`, FW `7.4.2`. All visible APs (20/21) on FW `6.11.2-0`, config `v1`. OBN patches persisted via `nd-systemupdate.sh shell` (run3).

**Open Stadler items:**
- Coach 5 AP2 never appeared (physical cable check needed at F-car AP2 → switch e0-4).
- Stadler FW (172.19.196.1) unreachable — vlan7 path on CCU clean (UP, 0 errors), TCP 80/22 both `No route to host`. Gateway not commissioned for this train.

No further Nomad action. See `reports/internal/105-l2-health-report-2026-05-05.md` for full health-check baseline.

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
- **Health check:** ⬜
- **Customer report:** ✅ v1.0 (health check only — v8 rollout NOT started)
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
- **Health check:** ❓
- **Customer report:** Stadler L2 fault report v1.0

Cable register item #4 — B3.e0-4 (AP trunk) link DOWN, PoE 0 W, AP not physically installed/connected.

Stadler L2 fault report v1.0 issued (`reports/customer/Stadler_4736-109_L2_Health_Check_Report_v1.0.docx`).

**Action when Stadler confirms AP installed:** verify `e0-4` link UP and PoE drawing on B3, then proceed with v8 push if not yet done.

---

### Fzg 148 — 4736-120 — 🔴 BLOCKED (E3 coach no power — Stadler)

**Status:** 🔴 **BLOCKED** · **CCU:** `10.179.2.1` · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ all 8
- **Switches v8:** ✅ 18/18 `nv6-XX-v8-148`, FW `7.4.2`
- **OBN patches:** ✅ all 8
- **Switches v8:** 🔴 17/18 — E3 switch cold-bypassed (coach has no power); all other 17 on `nv6-XX-v8-148`, FW `7.4.2`
- **APs:** 🔴 22/24 — 2 APs on E3 coach absent (cold bypass = AP ports dead); remaining 22 at `6.10.0-0` → needs `6.11.2-0`
- **vlan7:** ❓ (expect `172.19.202.2` — not yet confirmed live)
- **Stadler cabling:** 🔴 E3 coach no power — cold bypass engaged on E3 switch; 2 APs absent
- **FW reach:** ❓
- **Health check:** ⬜
- **Customer report:** ⬜

- **2026-05-04:** All 8 OBN bugs patched. `obn update c all` interrupted by train power-off — left mixed v4/v8 state at the time.
- **2026-05-19:** Verified live — all 18 switches now on `nv6-XX-v8-148`. 24/24 APs visible, Nomad config applied, firmware `6.10.0-0`.
- **2026-05-21:** E3 switch found cold-bypassed during pre-flight — E3 coach has no power. Confirmed via: no DHCP/fping/LLDP on E3; all 17 other switches show LLDP neighbours excluding E3; cold bypass relay confirmed via `show system` on adjacent switches. 2 APs on E3 coach also absent. **Stadler must restore power to E3 coach before commissioning can continue.** Not a cable fault — bypass relay is operating as designed under power loss.

**For Stadler:** Restore power to E3 coach on 4736-120 (box1-t2). E3 switch (expected at ~10.179.2.195) is cold-bypassed — no network presence. Once powered, E3 should auto-register via DHCP and appear in `sudo dhcp-lease-list`. Then resume AP fw push on all 24 APs.

---

### Fzg 1 — 4734-101 — 🔴 BLOCKED Stadler

**Status:** 🔴 **BLOCKED** · **CCU:** ❓ · **Last touched:** —

**Diagnostic state:**
- **OBN patches:** ❓
- **Switches v8:** ❓
- **APs:** ❓
- **vlan7:** ✅ `172.19.128.130` (PDF)
- **Stadler cabling:** 🔴 E2↔B1 wrong neighbour
- **FW reach:** ❓
- **Health check:** ⬜
- **Customer report:** ⬜

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
- **Health check:** ⬜
- **Customer report:** ⬜
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

### Fzg 20 — 4734-120 — 🟢 DONE — L2 health check complete

**Status:** 🟢 **DONE** · **CCU:** `10.179.49.1` (box1-t49) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ 7/7 (fix_obn.py bugs 1-7) persisted in btrfs `run2` snapshot (id 294)
- **Switches v8:** ✅ 12/12 at firmware 7.4.2 + config `nv4-*-v8-020`
- **APs:** ✅ 16/16 at firmware 6.11.2-0 + Nomad v1 config
- **vlan7:** ✅ `172.19.138.2/17` — **FIXED 2026-05-21** (was `172.19.152.130/17` encoding Fzg 49; corrected via chroot + safe_reboot)
- **Stadler cabling:** ✅ 24/24 inter-coach trunks correct (lldp_check_4734-120.py 2026-05-20)
- **FW reach:** ✅ **commissioned** (2026-05-21): Q1 ARP REACHABLE `00:90:e8:db:4d:5d`, Q2 ICMP 100% loss = Stadler policy drop, Q3 TCP 80+22 OPEN
- **Health check:** ✅ 2026-05-21 — 12/12 sw, 16/16 APs, 0 errors, STP single root `a0:59:3a:d0:b0:60` (G1), all critical trunks clean. Findings: `findings/findings_10.179.49.1_20260521.json`
- **Customer report:** ⬜

**Remaining for sign-off:** customer report only (`/dosto-l2-report`).

**2026-05-21 status check (read-only):** Device counts and vlan7 confirmed. Active subvol is `run1 (id 297)`, not `run2 (id 294)` where patches were persisted — note for the record, not a problem. State-inventory said OBN 3/8 and train_id template missing — **false-negatives** per the canonical `dosto-obn-patches --check` confirmation on Fzg 21. Re-verify directly with that skill + `cat /etc/obn/template/nv4-*.cfg` before assuming any drift. The customer report itself is unaffected regardless.

Session history: see `fleet-journal.md#fzg-20`.

---

### Fzg 139 — 4736-111 — ⚪ UNKNOWN (L2 healthy, v3 config — needs v8 push)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.24.1` (`box1-t24`) · **Last touched:** 2026-05-19 AR

**Diagnostic state:**
- **OBN patches:** ❓ (not checked this session)
- **Switches v8:** 🔴 **18/18 visible but all on v3 config** (`nv-*-v3-139`) — full v8 switch config push required
- **APs:** 🟡 24 APs visible, all `AP*-v1` Nomad config — firmware state unknown
- **vlan7:** ✅ `172.19.197.130/17` live (correct for odd Fzg 139)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks 10G full, 0 CRC/carrier errors
- **FW reach:** ❓ Q1 ARP = `.129` REACHABLE (Westermo MAC `00:90:e8:c5:3d:d4`), but TCP = "No route to host" — routing anomaly; full Q1/Q2/Q3 probe not completed (CCU dropped)
- **Health check:** 🟡 partial 2026-05-19 (error scan + STP complete; FW probe incomplete)
- **Customer report:** ⬜
- **OBN template:** 🔴 `train_id` not hardcoded (broken `128+train_id` formula) — fix before v8 push
- **nd-systemupdate:** ❓ not checked

**2026-05-19 findings:**
- 18/18 switches healthy — all inter-coach trunks at 10G, all Stadler-facing trunks clean (A3 e1-4 UP 1G, D1/D3 e0-2 UP 10G, B1/B3 e1-11 UP — ZFR B1 standby RX=0, B3 active)
- STP root: `a0:59:3a:d0:3d:20` (D2 `.188`, priority 32768) — stable
- Multiple e2-x ports DOWN across switches — needs schema PDF cross-check
- FW ARP shows `.129` not `.1` — likely vlan7 routing or FW IP mismatch; investigate on next visit

**Next actions:**
1. Complete FW probe: `ip neigh show dev vlan7 && ping -c 5 172.19.197.1 && nc -zv -w 5 172.19.197.1 80`
2. Check OBN patches state: `sudo python3 /tmp/fix_obn.py --check` (or grep vdsrail.py)
3. Fix OBN template `train_id` → hardcode `139`
4. Run full v8 switch config push (`obn update c all` leaf-first)
5. Check `nd-systemupdate.sh` rename

---

### Fzg 140 — 4736-112 — ⚪ UNKNOWN (prior session was against WRONG TRAIN — see note)

**Status:** ⚪ **UNKNOWN** · **CCU:** ❓ (IP unknown — `10.179.12.1` confirmed 2026-05-21 to be Fzg 147, not Fzg 140) · **Last touched:** 2026-05-19 AR (against wrong IP)

> ⚠️ **All diagnostic state below was recorded at `10.179.12.1` which is actually Fzg 147 / 4736-119. This block does NOT reflect Fzg 140 state. Physical inspection required to find Fzg 140's true CCU IP.**

**Diagnostic state:**
- **OBN patches:** ❓ (not checked this session)
- **Switches v8:** ✅ 18/18 on v8 config (hostname `nv6-*-v8-147` — wrong train_id due to broken OBN template formula, but config IS v8)
- **APs:** 🟡 24 APs visible, all `RT610LV-dosto-*` (factory-style names) — firmware/config state unknown
- **vlan7:** ✅ `172.19.198.2/17` live (correct for even Fzg 140)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks clean, 0 errors
- **FW reach:** 🔴 PATH_BROKEN — no ARP entry for `172.19.198.1`, "No route to host" on TCP — FW not installed or not commissioned
- **Health check:** 🟡 partial 2026-05-19 (error scan + STP complete; FW probe done but path broken)
- **Customer report:** ⬜
- **OBN template:** 🔴 `train_id` not hardcoded (broken `128+train_id` formula renders as 147 not 140)
- **nd-systemupdate:** ❓ not checked

**2026-05-19 findings:**
- All 18 switches clean — 0 CRC/carrier errors on all inter-coach + Stadler trunks
- STP root: `a0:59:3a:d0:73:a0` (D1 `.187`, priority 0) — stable
- Front coupler trunks (e0-2 on A3/A1/B1/B3) DOWN — expected, solo consist
- APs have factory-style hostnames (`RT610LV-dosto-...`) — may need Nomad config push (verify with `obn discover`)

**Next actions:**
1. Fix OBN template `train_id` → hardcode `140`
2. Check/apply OBN patches
3. `sudo obn discover` — check AP config state (factory vs Nomad)
4. Probe Stadler FW: confirm whether `172.19.198.1` is absent or misconfigured

---

### Fzg 151 — 4736-123 — ⚪ UNKNOWN

**Status:** ⚪ **UNKNOWN** · **CCU:** ❓ · **Last touched:** —

**Note:** CCU IP `10.179.23.1` was previously attributed to this train in error — confirmed 2026-05-19 to be Fzg 138 (4736-110) based on switch hostnames `nv6-*-v8-138` and vlan7 IP formula. Fzg 151 CCU IP not yet identified.

**Diagnostic state:**
- All fields ❓ — initial visit pending.

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
- **Health check:** ⬜
- **Customer report:** ⬜
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

### Fzg 9 — 4734-109 — ⚪ UNKNOWN (L2 healthy, v5 config)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.38.1` (`box1-t38`) · **Last touched:** 2026-05-19 AR

**Diagnostic state:**
- **OBN patches:** ❓ (not checked)
- **Switches v8:** 🟡 12/12 visible, all on **v5 config** (`nv4-*-v5-009`) — v5 may be current target for 4734; verify
- **APs:** 🟡 16 APs visible, all `AP*-v1` Nomad config — firmware unknown
- **vlan7:** ✅ `172.19.132.130/17` live (correct for odd Fzg 9)
- **Stadler cabling:** 🟡 12/12 switches visible; inter-coach trunks clean; **B1 (.220) e1-11 DOWN** and **B3 (.228) e1-11 DOWN** — ZFR ports both absent
- **FW reach:** ❓ Q1 ARP = `.129` STALE (Westermo MAC `00:90:e8:ce:86:39`); Q2/Q3 not completed (CCU dropped)
- **Health check:** 🟡 partial 2026-05-19
- **Customer report:** ⬜

**2026-05-19 findings:**
- All 12 switches clean — 0 CRC/carrier errors on inter-coach trunks
- STP root: `a0:59:3a:d0:3a:a0` (B1 `.220`, priority 32768) — stable
- B1 e1-11 + B3 e1-11 both DOWN — ZFR not connected/powered at time of check; check with Stadler if ZFR expected active

**Next actions:**
1. Complete FW probe when CCU recovers
2. Confirm v5 is correct target config for 4734 series (vs v8 for 4736)
3. Check ZFR presence/power

---

### Fzg 12 — 4734-112 — 🟡 PAUSED (4-car, ready to commission at corrected IP)

**Status:** 🟡 **PAUSED — ready to start commissioning** · **CCU:** `10.179.37.1` (`box1-t37`) · **Last touched:** 2026-05-21 AR

**2026-05-21 status check at corrected IP (read-only):**
- CCU reachable at `10.179.37.1` (corrected from `10.179.41.1` per fleet control sheet 2026-05-20).
- **Consist confirmed 4-car** (nv4 schema): 12/12 switches present (coaches A, G, E, B × 3 positions each), all hostnames `nv4-XX-v8-012`. 16/16 APs present with correct config-name distribution (2× each of AP1/2/3/4-v1 and AP1/2/3/4m-v1). Previous "5-car" briefing was a misread against the wrong CCU IP.
- vlan7 `172.19.134.2/17` ✅ (correct for even Fzg 12). train_id template `{%- set train_id = 12 -%}` ✅.
- **OBN patches: 0/8** — this CCU has genuinely never been patched. btrfs on run1/id330 (a promote has occurred at some point, but no patches were applied).
- TFTP module not loaded, CT helper rule absent — runtime fix never applied.
- `.dont` rename in place ✅.

**Next session:** apply OBN patches via fix_obn.py, persist via chroot, then run full commissioning pipeline from initial_diagnostics.

#### Stale notes (against wrong CCU IP 10.179.41.1 — 2026-05-19; ignore)

**Diagnostic state:**
- **OBN patches:** ❓ (not checked)
- **Switches v8:** 🔴 15/15 visible, all **v3 config** (`fv5-*-v3-231`, wrong train_id 231)
- **APs:** 🟡 20 APs visible, all `AP*-v1` Nomad config — firmware unknown
- **vlan7:** ✅ `172.19.134.2/17` — **FIXED 2026-05-19** (was `172.19.243.130`, now correct for even Fzg 12, persisted to run1)
- **Stadler cabling:** 🟡 15/15 visible; inter-coach trunks clean; **B1 (.185) e1-11 DOWN**, **B3 (.181) e1-11 DOWN**; C3 (.189) has 4×10G UP (unusual — verify LLDP)
- **FW reach:** ❓ no ARP entry yet (vlan7 just fixed, no FW probe run)
- **Health check:** 🟡 partial 2026-05-19 (13/15 switches error-scanned; STP/FW incomplete)
- **Customer report:** ⬜
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
- OBN patches 4/8 in active subvol run2/id308 — bugs 2/3/5/7 absent. Partial patch state; re-run fix_obn.py.
- TFTP module not loaded, CT helper rule absent.
- `.dont` rename in place ✅.

**Next session:** re-apply OBN patches; verify AP config expectation (plain vs m-variant for nv4); v7 → v8 switch config push (`obn update c` leaf-first); then AP firmware push.

#### Stale notes (against wrong CCU IP 10.179.42.1 — 2026-05-19; ignore — that IP belongs to 4705-101)

**Diagnostic state:**
- **OBN patches:** ❓ (not checked)
- **Switches v8:** 🔴 **15/18 visible**, all v3 config (`fv5-*-v3-229`, wrong train_id 229) — **3 switches missing from DHCP**
- **APs:** 🟡 20 APs visible, all `AP*-v1` Nomad config — firmware unknown
- **vlan7:** ❓ no ARP entry observed; FW probe not completed
- **Stadler cabling:** 🔴 **3 switches missing** — potential cable/power faults on those 3 cars; B1/B3 ZFR e1-11 checked and clean; checked switches had 0 errors
- **FW reach:** ❓ incomplete (CCU dropped mid-session)
- **Health check:** 🟡 partial 2026-05-19
- **Customer report:** ⬜
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

### Fzg 21 — 4734-121 — 🟢 DONE

**Status:** 🟢 **DONE** · **CCU:** `10.179.50.1` (`box1-t50`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ✅ (confirmed via v8 switch hostnames)
- **Switches v8:** ✅ 12/12 on `nv4-*-v8-021`
- **APs:** ✅ 16/16, all `AP*-v1`/`AP*m-v1` Nomad config
- **vlan7:** ✅ `172.19.138.130/17` (correct for odd Fzg 21)
- **Stadler cabling:** ✅ 12/12 visible; all inter-coach trunks 10G/1G clean; 0 CRC/carrier errors
- **FW reach:** 🟡 uncommissioned (ARP REACHABLE `00:90:e8:db:4d:6a`, ICMP replies = bare Westermo at `.129`) — Stadler's responsibility, not a Nomad blocker
- **Health check:** ✅ 2026-05-21 — full sweep, 0 errors. Findings: `findings/findings_10.179.50.1_20260521.json`
- **Customer report:** ⬜

**2026-05-21 status check (read-only):** Device counts and vlan7 confirmed. State-inventory said OBN 4/8 — **resolved as false-negative** on 2026-05-21: `dosto-obn-patches --check` on this exact CCU found **all 8 markers present** (counts 1, 2, 1, 1, 1, 1, 1, 1) in active subvol run2/id297. Patches are genuinely persisted. State-inventory's grep is stale; trust `dosto-obn-patches` going forward. See [[project_state_inventory_marker_false_negative]].

---

### Fzg 143 — 4736-115 — 🟡 PAUSED (batch experiment result: 8/24 at 6.11.2-0)

**Status:** 🟡 **PAUSED — batch experiment result: 8/24 at 6.11.2-0 (33%)** · **CCU:** `10.179.18.1` (`box1-t18`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ⚠️ state-inventory reported 4/8 in active subvol `run1 (id 312)` — **false-negative** per `dosto-obn-patches --check` on Fzg 21 (2026-05-21). Treat as still 8/8 + bug 9 pending direct re-verify.
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-143`, all firmware `7.4.2`
- **APs:** 🟡 24/24 visible, all Nomad config — **8/24 at 6.11.2-0 (33%)**: coach 1 = 4/4 ✅, coach 2 = 3/4 (.232 still 6.10.0-0), coach 3 = 0/4, coach 4 = 0/4, coach 5 = 0/4, coach 6 = 1/4 (.238 only). 16 APs still on 6.10.0-0. Coaches 4-6 (12 APs) still need config refresh from `AP*-v1` → `AP*m-v1`
- **vlan7:** ✅ `172.19.199.130/17` live (was wrong `172.19.201.2` — encoded Fzg 146; fixed + persisted via chroot promote)
- **Stadler cabling:** ✅ 18/18 sw + 24/24 AP visible (pre-flight discovery clean)
- **FW reach:** ⬜ Q1/Q2/Q3 not yet probed
- **Health check:** ⬜
- **Customer report:** ⬜
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

### Fzg 144 — 4736-116 — 🟡 PAUSED (AP fw 9/23 done; OBN regressed 8/8 → 4/8)

**Status:** 🟡 **PAUSED — AP fw 9/23 done; OBN regressed 8/8 → 4/8** · **CCU:** `10.179.16.1` (`box1-t16`) · **Last touched:** 2026-05-21 AR

**Diagnostic state:**
- **OBN patches:** ⚠️ state-inventory reported 4/8 — **false-negative** per `dosto-obn-patches --check` on Fzg 21 (2026-05-21). Treat as still 8/8 pending direct re-verify. btrfs subvol id changed 303 → 306 between sessions (a promote happened — note, not necessarily a problem).
- **Switches v8:** ✅ 18/18 on `nv6-*-v8-144`, all firmware `7.4.2`
- **APs:** 🟡 24/24 visible (Coach 6 AP3 now in DHCP — register #6 may be self-resolved); **9/23 at 6.11.2-0** (coach 1=3/4, coach 2=2/4, coach 3=2/4, coach 4=1/4, coach 5=0/4, coach 6=1/4 + AP4 `incomplete` firmware state). 13 still on 6.10.0-0. Coaches 4-6 (12 APs) also need config refresh from `AP*-v1` → `AP*m-v1`
- **vlan7:** ✅ `172.19.200.2/17` live (was already correct for even Fzg 144 — no nmconnection edit needed)
- **Stadler cabling:** 🔴 Coach 6 AP3 missing (B3 e1-2 port live with RX/TX traffic per pre-flight but AP not in DHCP across 2 cycles — likely AP physically present but bricked or stuck) — cable register #6
- **FW reach:** ✅ **commissioned** (2026-05-20): Q1 ARP REACHABLE `00:90:e8:ca:3e:aa`, Q2 ICMP 100% loss = Stadler policy drop per Phase 6, Q3 TCP 80+22 OPEN
- **Health check:** ⬜
- **Customer report:** ⬜
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
| `10.179.29.1` | 2026-05-20 |
| `10.179.32.1` | 2026-05-20 |
| `10.179.45.1` | 2026-05-20 |
| `10.179.54.1` | 2026-05-20 |
| `10.179.122.1` | 2026-05-20 |
| `10.179.124.1` | 2026-05-20 |
| `10.179.127.1` | 2026-05-20 |
| `10.179.123.1` | 2026-05-21 | **Bench (not a train)** — confirmed by engineer 2026-05-21; do not move to series table |
