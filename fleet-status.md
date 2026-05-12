# DOSTO Fleet — v8 Rollout Status

**Last updated:** 2026-05-12 by Abbas Rizvi
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
| 134 | 4736-106 | ❓ | ⚪ UNKNOWN | confirm v8 state — only customer report on file |
| 135 | 4736-107 | ❓ | ⚪ UNKNOWN | initial visit |
| 136 | 4736-108 | ❓ | 🔴 **BLOCKED** | wait for Stadler on register #2 + #3 |
| 137 | 4736-109 | ❓ | 🔴 **BLOCKED** | wait for Stadler on register #4 (AP install at B3) |
| 138 | 4736-110 | ❓ | ⚪ UNKNOWN | confirm v8 state — only customer report on file |
| 139 | 4736-111 | ❓ | ⚪ UNKNOWN | initial visit |
| 140 | 4736-112 | ❓ | ⚪ UNKNOWN | initial visit |
| 141 | 4736-113 | ❓ | ⚪ UNKNOWN | initial visit |
| 142 | 4736-114 | ❓ | ⚪ UNKNOWN | initial visit |
| 143 | 4736-115 | ❓ | ⚪ UNKNOWN | initial visit |
| 144 | 4736-116 | ❓ | ⚪ UNKNOWN | initial visit |
| 145 | 4736-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 146 | 4736-118 | ❓ | ⚪ UNKNOWN | confirm v8 state — only baseline + customer report on file |
| 147 | 4736-119 | ❓ | ⚪ UNKNOWN | initial visit (schema PDF in `docs/`) |
| 148 | 4736-120 | `10.179.2.1` | 🟡 **PAUSED** | `sudo obn discover && sudo obn update c all` |

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
| 9 | 4734-109 | ❓ | ⚪ UNKNOWN | initial visit |
| 10 | 4734-110 | ❓ | ⚪ UNKNOWN | initial visit |
| 11 | 4734-111 | ❓ | ⚪ UNKNOWN | initial visit |
| 12 | 4734-112 | ❓ | ⚪ UNKNOWN | initial visit |
| 13 | 4734-113 | ❓ | ⚪ UNKNOWN | initial visit |
| 14 | 4734-114 | ❓ | ⚪ UNKNOWN | initial visit |
| 15 | 4734-115 | ❓ | ⚪ UNKNOWN | initial visit |
| 16 | 4734-116 | ❓ | ⚪ UNKNOWN | initial visit |
| 17 | 4734-117 | ❓ | ⚪ UNKNOWN | initial visit |
| 18 | 4734-118 | ❓ | ⚪ UNKNOWN | initial visit |
| 19 | 4734-119 | ❓ | ⚪ UNKNOWN | scripts/lldp_check_4734-119.py exists — possibly visited |
| 20 | 4734-120 | `10.179.49.1` | ⚪ UNKNOWN | confirm switches v8 state; APs done 2026-05-05 |

### 4705 / 4706 series

Not yet touched in the v8 rollout (different platform). Folders exist in `train-ip-allocation-commission/4705-xxx/` and `4706-xxx/` (101–103 each). Excluded from this tracker until they enter scope.

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

**Status:** 🔴 **BLOCKED** · **CCU:** ❓ · **Last touched:** —

**Diagnostic state:**
- **OBN patches:** ❓
- **Switches v8:** ❓
- **APs:** ❓
- **vlan7:** ❓ (expect `172.19.196.2`)
- **Stadler cabling:** 🔴 C3 swap + D1↔E2 missing
- **FW reach:** ❓
- **Health check:** ❓
- **Customer report:** ✅ v1.0

Cable register items #2 (C3 trunks swapped on `e0-0` / `e0-1`) and #3 (D1↔E2 inter-coach missing). See [cable-issues-register.md](cable-issues-register.md).

**Action when Stadler confirms re-cable:** copy `scripts/lldp_topology_check.py` to CCU `/tmp/`, edit `SWITCHES`/`EXPECTED_TOPOLOGY` for this consist (6-car), run with `python3`. Expect 0 mismatches. Then proceed with `sudo obn update c all`.

Customer health-check report v1.0 already filed (this was a *health check*, not a v8 push). Don't confuse the two — the v8 rollout for this train hasn't started.

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

### Fzg 148 — 4736-120 — 🟡 PAUSED

**Status:** 🟡 **PAUSED** · **CCU:** `10.179.2.1` · **Last touched:** 2026-05-04 AR

**Diagnostic state:**
- **OBN patches:** ✅ all 8
- **Switches v8:** 🟡 mixed v4/v8
- **APs:** ⬜
- **vlan7:** ❓ (expect `172.19.202.2`)
- **Stadler cabling:** ❓
- **FW reach:** ❓
- **Health check:** ⬜
- **Customer report:** ⬜

- **2026-05-04:** All 8 OBN bugs patched on `10.179.2.1`. `sudo obn update c all` interrupted when train powered off mid-run. **Mixed v4/v8 config across consist** → RSTP storm risk if not finished.
- **Resume command:** `sudo obn discover && sudo obn update c all`
- **Verify first:** patches still in place (Step 3 of [train-login-checklist.md](train-login-checklist.md)) — power-off may not have wiped them, but check.
- Fzg ID in `/etc/obn/template/nv6-*.cfg` may not match the CCU IP subnet — that's intentional (mar5 migration workaround), don't "fix" it.

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

## How to update this file

At the **end** of every train session, before you `exit` the SSH:

1. Find your train's row in the at-a-glance table — update `Status` and `Next action`.
2. If the train has a per-train detail block below, update its **Diagnostic state** fields (the bulleted list at the top of the block).
3. If the train is in any non-trivial state (PAUSED / BLOCKED / DONE w/ Stadler) and doesn't have a detail block yet, add one. If the train has reached plain `DONE`, delete its detail block to keep the file clean.
4. Update the `Last touched` line in the block.
5. Update the `Last updated` line at the top of the file.
6. Commit if the repo is under git, or just save.

If the very next person to log into this train can't see "what's the next command to run" without asking you, the row isn't done.
