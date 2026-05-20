# DOSTO Fleet — v8 Rollout Status

**Last updated:** 2026-05-19 by Abbas Rizvi (Fzg 138 vlan7 fix + CCU IP correction)
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
| 136 | 4736-108 | `10.179.8.1` | 🔴 **BLOCKED** | train mostly offline — only 2 switches visible; wait for Stadler on register #2 + #3; then apply OBN patches + full v8 push |
| 137 | 4736-109 | `10.179.28.1` | 🔴 **BLOCKED** | wait for Stadler on register #4 (AP install at B3); CCU IP populated from fleet control sheet 2026-05-20 (Train NC ID T28, prio test train, v8/6.10.0 per sheet) |
| 138 | 4736-110 | `10.179.23.1` | 🟡 **PAUSED** | fix OBN template train_id → 138; apply OBN patches; obn update c all; check nd-systemupdate rename |
| 139 | 4736-111 | `10.178.24.1` | ⚪ UNKNOWN | CCU IP corrected from sheet 2026-05-20 (was `10.179.24.1` — sheet says 178/16); L2 healthy notes below were collected against the wrong IP, re-verify next visit |
| 140 | 4736-112 | `10.178.40.1` | ⚪ UNKNOWN | CCU IP corrected from sheet 2026-05-20 (was `10.179.12.1` — sheet says that is Fzg 147 / 4736-119); re-verify next visit |
| 141 | 4736-113 | ❓ | ⚪ UNKNOWN | initial visit |
| 142 | 4736-114 | ❓ | ⚪ UNKNOWN | initial visit |
| 143 | 4736-115 | `10.179.18.1` | ⚪ UNKNOWN | initial visit |
| 144 | 4736-116 | `10.179.16.1` | ⚪ UNKNOWN | initial visit |
| 145 | 4736-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 146 | 4736-118 | `10.179.21.1` | ⚪ UNKNOWN | CCU IP populated from sheet 2026-05-20; confirm v8 state — only baseline + customer report on file |
| 147 | 4736-119 | `10.179.12.1` | ⚪ UNKNOWN | CCU IP populated from sheet 2026-05-20 — was previously attributed to Fzg 140 in error |
| 148 | 4736-120 | `10.179.2.1` | 🟡 **PAUSED — AP fw pending** | push AP fw `6.10.0-0` → `6.11.2-0` on 24 APs |
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
| 12 | 4734-112 | `10.179.37.1` | ⚪ UNKNOWN | CCU IP corrected from sheet 2026-05-20 (was `10.179.41.1` — sheet says 37.1); prior notes were against the wrong IP, re-verify next visit |
| 13 | 4734-113 | `10.179.46.1` | ⚪ UNKNOWN | CCU IP corrected from sheet 2026-05-20 (was `10.179.42.1` — sheet says 46.1; `10.179.42.1` belongs to 4705-101); prior notes were against the wrong IP, re-verify next visit |
| 14 | 4734-114 | ❓ | ⚪ UNKNOWN | initial visit |
| 15 | 4734-115 | ❓ | ⚪ UNKNOWN | initial visit |
| 16 | 4734-116 | ❓ | ⚪ UNKNOWN | initial visit |
| 17 | 4734-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 18 | 4734-118 | ❓ | ⚪ UNKNOWN | initial visit |
| 19 | 4734-119 | ❓ | ⚪ UNKNOWN | scripts/lldp_check_4734-119.py exists — possibly visited |
| 20 | 4734-120 | `10.179.49.1` | ⚪ UNKNOWN | confirm switches v8 state; APs done 2026-05-05 |
| 21 | 4734-121 | `10.179.50.1` | 🟢 **DONE w/ Stadler** | L2 healthy (12/12 sw, 16 APs, 0 errors) — v8 config ✅; FW UNCOMMISSIONED (at .129 not .1 — bare Westermo); wait for Stadler to commission FW at 172.19.138.1 |

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

### Fzg 136 — 4736-108 — 🔴 BLOCKED Stadler

**Status:** 🔴 **BLOCKED** · **CCU:** `10.179.8.1` (`box1-t8`) · **Last touched:** 2026-05-19 AR

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

### Fzg 148 — 4736-120 — 🟡 PAUSED (AP fw pending)

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.2.1` · **Last touched:** 2026-05-19 AR

**Diagnostic state:**
- **OBN patches:** ✅ all 8
- **Switches v8:** ✅ 18/18 `nv6-XX-v8-148`, FW `7.4.2`
- **APs:** 🟡 24/24 visible, Nomad config `v1` ✅, firmware `6.10.0-0` → needs `6.11.2-0`
- **vlan7:** ❓ (expect `172.19.202.2` — not yet confirmed live)
- **Stadler cabling:** ❓ (C1/C3 were previously missing — now back online; Stadler suspected B&E We1/2 swap in config)
- **FW reach:** ❓
- **Health check:** ⬜
- **Customer report:** ⬜

- **2026-05-04:** All 8 OBN bugs patched. `obn update c all` interrupted by train power-off — left mixed v4/v8 state at the time.
- **2026-05-19:** Verified live — all 18 switches now on `nv6-XX-v8-148` (update completed since 2026-05-04). 24/24 APs visible with Nomad config applied but firmware still `6.10.0-0`. OBN template hardcoded to `train_id = 148` ✅.
- **Next:** `sudo obn update f` to push AP firmware `6.10.0-0` → `6.11.2-0` on all 24 APs. Then confirm vlan7 + FW reach.

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

### Fzg 20 — 4734-120 — ⚪ UNKNOWN (APs done)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.49.1` · **Last touched:** 2026-05-05 AR

**Diagnostic state:**
- **OBN patches:** ❓
- **Switches v8:** ❓
- **APs:** ✅ 16/16 (factory bypass via LuCI)
- **vlan7:** ✅ `172.19.138.2` (PDF)
- **Stadler cabling:** ❓
- **FW reach:** ❓
- **Health check:** ⬜
- **Customer report:** ⬜

2026-05-05: All 16 APs on this CCU were in factory `RT610LV-…-v1-FD` config after Stadler commissioning. Pushed Nomad config via LuCI HTTP import + `rpcCfgApply` (scripts: `scripts/push_ap_config.sh`, `scripts/push_remaining_aps.sh`, `scripts/apply_ap_configs.sh`).

**Switch v8 state not captured.** Confirm next visit.

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

### Fzg 140 — 4736-112 — ⚪ UNKNOWN (L2 healthy, v8 config, FW not commissioned)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.12.1` (`box1-t12`) · **Last touched:** 2026-05-19 AR

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

### Fzg 138 — 4736-110 — 🟡 PAUSED

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.23.1` (`box1-t23`) · **Last touched:** 2026-05-19 AR

**Diagnostic state:**
- **OBN patches:** ❓ (not checked this session)
- **Switches v8:** ✅ 18/18 on v8 config (`nv6-*-v8-138`)
- **APs:** ✅ 24 APs visible, all `AP*-v1` / `AP*m-v1` Nomad config ✅
- **vlan7:** ✅ `172.19.197.2/17` — **FIXED 2026-05-19** (was `172.19.203.130`, now correct for even Fzg 138, persisted via chroot + safe_reboot; post-reboot verified)
- **Stadler cabling:** ✅ 18/18 switches visible, all inter-coach trunks clean, 0 errors
- **FW reach:** ✅ **commissioned** (2026-05-19): ARP REACHABLE `00:90:e8:c5:3d:9d` (Westermo), ICMP 100% loss = Stadler policy drop per Phase 6 Q2
- **Health check:** ⬜
- **Customer report:** ⬜
- **OBN template:** 🔴 `train_id` not hardcoded (was rendering as 138 from broken formula — fix to hardcode `138`)
- **nd-systemupdate:** ❓ not checked

**Next actions:**
1. Fix OBN template `train_id` → hardcode `138` in all `/etc/obn/template/nv6-*.cfg`
2. Check/apply OBN patches (`sudo python3 /tmp/fix_obn.py`), rename `nd-systemupdate.sh → .dont`
3. Persist fixes via `sudo /usr/sbin/nd-systemupdate.sh.dont shell` + reboot
4. `sudo obn discover && sudo obn report && sudo obn update c all` (leaf-first)
5. Run `/dosto-l2-health` for customer baseline

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

### Fzg 12 — 4734-112 — ⚪ UNKNOWN (5-car, L2 healthy, v3 config, vlan7 fixed)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.41.1` (`box1-t41`) · **Last touched:** 2026-05-19 AR

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

### Fzg 13 — 4734-113 — ⚪ UNKNOWN (3 switches missing)

**Status:** ⚪ **UNKNOWN** · **CCU:** `10.179.42.1` (`box1-t42`) · **Last touched:** 2026-05-19 AR

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

### Fzg 21 — 4734-121 — 🟢 DONE w/ Stadler (FW commissioning pending)

**Status:** 🟢 **DONE w/ Stadler** · **CCU:** `10.179.50.1` (`box1-t50`) · **Last touched:** 2026-05-19 AR

**Diagnostic state:**
- **OBN patches:** ❓ (not checked this session)
- **Switches v8:** ✅ 12/12 on `nv4-*-v8-021` — correct v8 config, correct train_id
- **APs:** ✅ 16 APs visible (8 AP + 8 APm), all `AP*-v1`/`AP*m-v1` Nomad config
- **vlan7:** ✅ `172.19.138.130/17` live and correct (odd Fzg 21)
- **Stadler cabling:** ✅ 12/12 visible; all inter-coach trunks 10G clean; 0 CRC/carrier errors
- **FW reach:** 🟡 **UNCOMMISSIONED** — ARP REACHABLE at `172.19.138.129` (Westermo MAC `00:90:e8:db:4d:6a`), ICMP 0 replies, TCP "No route to host"; FW responding at `.129` not `.1` — bare Westermo defaults, Stadler has not commissioned
- **Health check:** ✅ 2026-05-19 (partial — throughput sample interrupted by CCU drop; all other steps complete)
- **Customer report:** ⬜

**Stadler action required:** Commission Stadler FW at `172.19.138.1` (currently responding at `.129` = bare Westermo default IP).

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
