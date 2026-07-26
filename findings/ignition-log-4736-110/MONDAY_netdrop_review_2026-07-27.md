# Monday netdrop log review — 4736-110 / 105 / 106

**Date:** 2026-07-27 (reviewing weekend 25–26 Jul) · Logger deployed 2026-07-25.

## Reachability at review time
- **4736-105 (box1-t1, 10.179.1.1): reachable** — full weekend of data pulled + analysed.
- **4736-110 (10.179.23.1) and 4736-106 (10.179.19.1): OFFLINE** (SSH timeout). No weekend data yet — retry when reachable.

## 4736-105 result (netdrop.csv, 2026-07-25 12:14 → 07-26 06:24 UTC, 1133 rows)

**Headline: every tunnel/RDS disruption this weekend traces to a REBOOT. No standalone carrier-churn drop, no coverage drop, no hard power cut during steady-state.**

### Reboots (the actual availability cost)
6 boots in ~18 h, in 3 tight PAIRS (a scheduled reboot, then a 2nd reboot ~15–20 min later):
| ~time (UTC) | marker | verdict |
|---|---|---|
| 17:14 | SCHEDULED_REBOOT_5H + GRACEFUL | our 5h cron — commanded |
| 17:35 | no marker, but journal shows orderly unmount sequence | clean/commanded, NOT a hard cut |
| 22:35 | SCHEDULED_REBOOT_5H + GRACEFUL | our 5h cron |
| 22:50 | no marker, journal orderly | clean |
| 03:00 | GRACEFUL | commanded |
| 03:22 | no marker, journal orderly | clean |

All 6 shut down cleanly (journal boots -6/-4/-2 end with proper `Unmounted /tmp`, `var-cache Deactivated`). **Zero hard cuts / ignition drops in the window.**

### Tunnel-flow (rds_flow) drops
- 9 rds_flow drops within 120 s of a boot = expected boot gap.
- **36 rds_flow drops NOT at a boot — but ALL occurred with links_up=2, clustered in the 17:00 / 22:00 / 03:00 hour buckets** = the ~20 min modem re-registration tail AFTER each reboot pair, before all 4 modems came back. Not steady-state drops.
- ⇒ The tunnel was stable whenever the CCU was up and settled. The disruption is the **reboot + its long modem-recovery tail**, not carrier churn eating a healthy tunnel.

### Implication
The dominant availability cost on 105 this weekend was **the reboots themselves** (incl. our own 5h scheduled cron) and the slow (~20 min) 4-modem re-registration after each. Worth reconsidering whether the 5h auto-reboot is net-positive — it may be causing more visible downtime than the faults it was meant to paper over. Raise with ÖBB/Stadler before defending it.

## Caveats / data-quality issues found (must fix)
1. **The 2s power logger is BROKEN on 105 (script bug, not just stopped).** Correct unit name is `vign-logger.service` (not vign-poll). The process `vign_poll.sh` IS running (restarts each boot) but at 2026-07-25 11:51:59 it hit `awk: line 1: syntax error` on a malformed CMM read, wrote a corrupt row (`...4.88,,NA,NA,I`) and has produced ~0 valid rows since — only 1 row since the 03:24 reboot vs 1-per-2s expected. So CMM voltage coverage is effectively missing from 25 Jul 11:52 onward, incl. the whole reboot-active weekend.
   - **Root cause: unhandled awk failure in `vign_poll.sh` when the CMM I2C read returns a non-numeric/partial value.** The script doesn't guard the parse, so one bad read kills the writer until next reboot.
   - **⚠️ HIGH PRIORITY: this bug is likely present on 110 and 106 too** (same script from the same canonical deploy). If so, our power-vs-VPN correlation loses its power side fleet-wide. MUST verify vign row-freshness on 110/106 the moment they're reachable, and fix the awk guard in `vign_poll.sh` + redeploy.
   - Mitigation for this review: power-classified the 105 reboots from the persistent-journal shutdown sequence instead (all clean) — but that only tells commanded-vs-abrupt, not the Vin/Vign signature.
2. **netdrop logger undersamples fast IP churn**: 0 per-modem carrier-IP CHANGES recorded on 105, vs the every-few-minutes re-addressing seen on 110's journal. The 5 s cadence + IP only refreshed on `change` rows misses sub-5 s re-address bursts. The journal (nm-mar3) is the higher-fidelity source for the churn; netdrop is better for links_up / rds_flow state. Consider logging nm-mar3 `command=up` events into netdrop too.
3. Only 1 of 3 trains reachable — 110/106 pending.

## Power-logger deep-dive (2026-07-27) — TWO separate problems, not one

Investigating why vign.csv stopped on 105 uncovered two independent faults:

1. **awk crash bug in `vign_poll.sh` — FIXED + deployed to 105.** Every awk call string-interpolated
   shell vars (`if($vin>0)`); an empty/partial value made the program `if(>0)` → `awk: line 1: syntax
   error`, killing the writer and emitting a corrupt row (`...4.88,,NA,NA,...`). Fix: (a) `hexok()`
   guard — every I2C byte must be `0xNN` or the sample is skipped (no crash, no garbage row); (b) the
   pct/delta awk calls now pass values via `awk -v` so an empty var can never malform the program.
   Verified: reproduced the exact crash with empty vin on the old code; new code returns `NA`.
   `bash -n` clean. Backed up on-box as `vign_poll.sh.bak_pre_awkfix_20260727`. Canonical fixed copy:
   `_canonical_deploy/vign_poll.sh`.

2. **CMM I2C bus is WEDGED on 105 — hardware, NOT script. This is why there is no power data.**
   `i2ctransfer -y 2 w1@0x2d 0x04 r9` → `Error: Sending messages failed: Connection timed out`, and
   even `i2cdetect -y 2` hangs (command timed out). The ADLINK R5001C CMM stopped answering the I2C
   bus ~2026-07-25 11:51 and has not recovered. The (now-fixed) logger correctly reads empty and skips
   — so post-fix it will resume writing automatically IF/WHEN the CMM bus recovers, but it cannot force
   the CMM back. Recovery is a hardware action (likely a full CCU power-cycle / CMM reset), not remote-
   fixable and not something to attempt over SSH. **The awk fix stops the corruption; it does NOT
   restore power data on 105 until the CMM I2C comes back.**
   - Consequence: 105 has NO usable CMM voltage data from 25 Jul 11:51 onward. Power-classification of
     105's weekend reboots rests on the journal shutdown-sequence (clean) only.
   - ⚠️ Check on 110/106 when reachable: (a) redeploy the awk fix; (b) test `i2ctransfer` — if their CMM
     I2C is also wedged, the whole power-logger workstream needs the CMM-hang root cause addressed
     (possible link to the [[project_ccu_cmm_i2c_ignition_readout]] readout path / a known CMM firmware hang).

## ⚠️ LIKELY ROOT CAUSE of the CMM hang: the 2s poll cadence (was 30s)

Tested the hypothesis "the 2s change wedged the CMM." Strong circumstantial support:
- **Control (110, 30s cadence):** 56,637 rows over 5.5 weeks (16 Jun–24 Jul) → **3 glitch rows total**
  (0.005%), 0 NA, 0 empty. CMM rock-solid at 30s.
- **105 at 2s:** ~27 h → **24 glitch rows** (2×655.35V/0xFFFF, 15 NA, 7 empty), and the glitch rate
  **escalated in the final ~3 h** (24T09h:1 → 25T09h:4 → 10h:3 → 11h:11) then the bus **fully locked up**
  at 11:51:58 (i2ctransfer + i2cdetect both time out since).
- Mechanism: over-polling the CMM's embedded I2C slave ~15× faster than the proven-safe rate → its I2C
  handler falls behind → partial reads → eventual controller wedge. Classic embedded-I2C failure mode.
- Honest strength: **strong + directional, not yet proof** (n=1 hang; can't see 105's own pre-2s
  baseline; 110/106 at 2s unconfirmed because offline). But the 250×+ glitch-rate jump + escalation +
  lockup all point one way.

**Action taken:** cadence backed off **2s → 10s**, HB **2s → 30s**, in the canonical script (deployed to
105). 10s is 3× the glitch-free 30s baseline, 1/5 the wedging 2s load, and still gives a last-sample
≤10s before any cut — ample, since the hard-cut argument rests on the GAP + missing shutdown marker,
not sub-10s voltage resolution. Recommend NEVER going back to 2s on the CMM path.

## awk-fix redeploy status
| Train | awk fix | CMM I2C | power data |
|---|---|---|---|
| 4736-105 | ✅ deployed 2026-07-27 | ❌ wedged (timeout) | none since 07-25 11:51 until CMM recovers |
| 4736-110 | ⏳ offline — stage when reachable | unknown | unknown |
| 4736-106 | ⏳ offline — stage when reachable | unknown | unknown |

## FINDING 2026-07-27 — 2 modems stuck on wrong APN (`ims`, not the data APN) — ties to the churn carriers

After the 105 soft reboot (which did NOT clear the CMM I2C hang — still times out, confirming it needs
a true power cycle), `marcli`/`mmcli` showed only 2 of 4 modems CONNECTED, persistently (not a
re-registration tail — stable over >10 min, uptime 6 min):

| Modem | Carrier | Bearer APN | IP type | ce iface IP | State |
|---|---|---|---|---|---|
| ce0 A1 (23201) | mtm.tag.com | ipv4v6 | 10.10.200.216 | ✅ CONNECTED |
| ce2 A1 (23201) | mtm.tag.com | ipv4v6 | 10.10.169.196 | ✅ CONNECTED |
| ce1 **Drei (23205)** | **ims only** | ipv6 | **none** | ❌ REGISTERED, DOWN |
| ce3 **T-Mobile (23203)** | **ims only** | ipv6 | **none** | ❌ REGISTERED, DOWN |

**⚠️ CORRECTION 2026-07-27b — my "give them the mtm.tag.com profile" idea was WRONG.** mtm.tag.com is
an **A1-only** APN (both working modems are A1/23201). You cannot put an A1 APN on a Drei/T-Mobile SIM.
Each carrier has its own APN. So the fix is NOT "copy mtm.tag.com" — disregard that. Corrected analysis
below.

**Root cause of the 2 down modems — what is PROVEN vs UNKNOWN (2026-07-27, deeper check):**
PROVEN:
- The 2 stuck modems get NO IP at all (no inet/inet6 on ce1p0/ce3p0). The earlier "ipv6" was just the
  `default-attach` (ims) signaling bearer, which carries no address. We are NOT assigned an IPv6 IP.
- Both WORKING modems are **A1 (23201)** using **mtm.tag.com** (an A1 APN). Both STUCK modems are
  **different carriers: Drei/3AT (23205)** and **T-Mobile/Magenta (23203)**. So mtm.tag.com working is
  consistent with it being A1-specific — it does NOT belong on the other two.
- Each stuck iface HAS carrier-appropriate profiles: ce1p0 → drei.at + m2m.fusion-iot.de (+1 blank);
  ce3p0 → gprsinternet + m2m.fusion-iot.de. apn_lookup_table maps 23205→drei.at, 23203→gprsinternet.
  `m2m.fusion-iot.de` on BOTH looks like an MVNO/IoT-aggregator (Fusion IoT) APN — possibly the intended
  real data APN for these SIMs.
- All the stuck-iface profiles are **autoconnect=false**; `nmcli` shows ONLY ce0p0-1 + ce2p0-1
  (the A1 ones) as `activated`. So on Drei/T-Mobile NO data profile is active → no data bearer attempt
  completing → no PDP → no IP → MAR DOWN.
UNKNOWN (can't tell from logs — journal only reaches the 06:39 reboot, no connect-attempt lines):
- WHY Drei/T-Mobile don't activate: (a) MAR isn't selecting/activating a profile for them, (b) the
  attempts fail (SIM not data-provisioned / wrong APN value / auth), or (c) they only come up when
  moving/over time. Cannot distinguish from current evidence.
- Which of the multiple per-iface profiles is the INTENDED one (drei.at vs m2m.fusion-iot.de, etc.).

**RESOLVED 2026-07-27c — live probe (ran mmcli --simple-connect on the 2 down modems, then cleaned up):**
- Drei modem 2 + `apn=drei.at` → **connected, IP 10.26.210.149** (data bearer up, type=default).
- T-Mobile modem 4 + `apn=gprsinternet` → **connected, IP 10.202.21.11 + IPv6** (dual-stack).
- ⇒ SIMs, APNs, and carrier data-provisioning are ALL FINE. Not IPv6-only. Not a carrier problem.
- BUT even with the MM bearer up + carrier IP assigned, `ce1p0`/`ce3p0` kernel ifaces still had NO IP
  and MAR still showed DOWN — because `--simple-connect` is a raw MM connect that bypasses NetworkManager,
  so the bearer IP was never applied to the interface.
- `nmcli --active` shows ONLY `ce0p0-1` + `ce2p0-1` (the A1 profiles) activated. Drei `ce1p0-3` /
  T-Mobile `ce3p0-2` profiles have the SAME `method=auto` IP config as the working A1 ones — profiles
  are fine — but are **`autoconnect=false` and NM never activates them**.

**⚠️⚠️ CORRECTION 2026-07-27e — the mar3.json `23203` gap is NOT the root cause. Disproven by control train 4736-102.**
Checked 4736-102 (box1-t47, 10.179.47.1), where all 4 modems work:
- 102 has the **IDENTICAL** config: same `mar3.json`, `priority1` ALSO missing 23203; and the **same SIM population**
  (ce0/ce2=A1 23201, ce1=Drei 23205, ce3=T-Mobile 23203) — confirmed same slots as 105.
- **YET on 102 all 4 incl. the T-Mobile ce3p0 are ACTIVE, with 23203 absent from the list.** So the modem
  connects fine without 23203 → the missing operator code is NOT what kept 105's modems down.
- ⇒ **Adding 23203 would NOT have fixed 105. Do NOT raise/keep the DevOps ticket as "the fix."** (Adding
  T-Mobile AT to the roaming list is a legit tidy-up — it's genuinely absent from the comment+codes — but it
  is NOT the cause of the down-modems and must not be framed as such.)

**ACTUAL ROOT CAUSE: runtime NM profile-activation failure on 105, induced by its reboot/instability state.**
- 102: uptime 4h15m, ONE clean boot today, mar3 started once → all 4 profiles auto-activated. Healthy.
- 105: uptime 36 min, a STORM of reboots today (22:50→03:00→03:21→03:22→06:39→06:40) + the CMM I2C wedge +
  the 2s-logger crash. Through that churn, MAR/NetworkManager failed to auto-activate 2 of 4 profiles
  (ce1p0 Drei, ce3p0 T-Mobile) → they sat DOWN. `nmcli connection up` fixed it (activation was the missing
  step) and it HELD across the 06:40 reboot (all 4 ACTIVE, still up).
- So the down-modems are a SYMPTOM of 105's instability (reboot storm + CMM wedge from the 2s logger), not an
  independent carrier/config fault. Ties back to the weekend conclusion: the availability cost on 105 is the
  reboots themselves. Fix the instability (revert 2s cadence [done], power-cycle to clear CMM, understand the
  reboot storm) and the modems auto-activate normally as on 102.
- Open Q for R&D: why does MAR/NM skip activating some profiles after churny reboots? (robustness gap — it
  should retry activation for all configured links.) That's the real lead, not the operator list.

**[SUPERSEDED — the mar3.json-gap theory below was DISPROVEN by 102; kept for history]**
**FIX PROVEN 2026-07-27d — all 4 modems brought ACTIVE on 105.** Root cause fully isolated in mar3.json.
- The NM profiles are `autoconnect=false` on ALL modems incl. the WORKING A1 ones (`permissions=user:mar3:` —
  MAR owns activation, not autoconnect). So autoconnect is NOT the differentiator.
- **`/etc/mar3/mar3.json` vlink `cascading_32` → group `priority1.codes` lists 23201(A1) + 23205(Drei)
  but is MISSING 23203 (T-Mobile/Magenta).** That is why MAR never activates T-Mobile.
- PROOF (runtime, no config change): `sudo nmcli connection up ce3p0-2` (T-Mobile) → ce3p0 ACTIVE, 5GNR,
  IP 10.202.209.222 +IPv6, traffic flowing. `sudo nmcli connection up ce1p0-3` (Drei) → ce1p0 ACTIVE,
  IP 10.60.56.239, traffic flowing (took a few extra s to settle; NOT a separate radio fault — same
  activation gap). **All 4 uplinks ACTIVE.**
- ⚠️ RUNTIME-ONLY / NOT DURABLE: modems were brought up by hand via `nmcli connection up`. This does NOT
  survive a reboot or MAR restart — MAR re-drives activation from mar3.json, which still lacks 23203, so
  ce3p0 (T-Mobile) will drop again on 105's next reboot. Drei (23205) IS in the list so should re-activate,
  but was down pre-fix → check MAR is actually selecting it.
- **DURABLE FIX (not applied — production config, likely Puppet-managed): add `23203` to `priority1.codes`
  in mar3.json.** MUST be done in the Puppet/hieradata source (a live hand-edit reverts on next agent run),
  then deployed. Applying + restarting mar3 restarts the tunnel (drops working A1 links briefly) → do in a
  maintenance window, not on an in-service train. Verify the same gap on 110/106 (likely same image).
- NOTE: this exactly matches the 110 churn finding — T-Mobile(23203) + Drei(23205) were the churn carriers
  there. The mar3.json operator-list gap is the CCU-side cause; still worth the R&D APN/carrier review too.

**ROOT CAUSE (isolated): CCU-side NetworkManager profile-activation gap.** The Drei + T-Mobile per-iface
NM profiles are correct but not being activated (autoconnect=false, and MAR/NM isn't bringing them up),
so those 2 modems never get their working data bearer applied to the kernel interface → MAR DOWN. The
two A1 profiles DO auto-activate. This is Nomad-side, fixable (activate/enable the correct per-carrier
profile for ce1p0/ce3p0), testable, reversible. NOT a carrier/SIM/APN fault. Hand to R&D: why are only
the A1 profiles activated — is MAR meant to pick one profile per iface and failing to on non-A1, or is
autoconnect supposed to be true? Test bearers were disconnected after probing; modems left `registered`
(as found).
(Superseded first-pass detail below for history.)

**[SUPERSEDED first-pass detail]**
- Clarification on the earlier "IPv6" note: the stuck modems get **NO IP AT ALL** (no inet/inet6 on
  ce1p0/ce3p0). The `ip type: ipv6` seen first was the `default-attach` bearer's property (the LTE
  network-attach signaling channel, `apn=ims`) — it carries no address block. We are NOT being assigned
  an IPv6 address; we are getting nothing, because no `type: default` DATA bearer ever activates.
- The working A1 modems have TWO bearers: `default-attach` + a `type: default` DATA bearer on
  `apn=mtm.tag.com` with a real IPv4 config (e.g. 10.10.200.216/28). The stuck modems have only the
  attach bearer, no data bearer.
- **Why:** per-interface NetworkManager profiles in `/etc/NetworkManager/system-connections/` differ:
  - ce0p0 (A1): `mtm.tag.com` ✅ ; ce2p0 (A1): `mtm.tag.com` + gprsinternet ✅
  - ce1p0 (Drei): profiles `ce1p0-2`(EMPTY apn), `ce1p0-3`=drei.at, `ce1p0-4`=m2m.fusion-iot.de — **no mtm.tag.com** ❌
  - ce3p0 (T-Mobile): `ce3p0-2`=gprsinternet, `ce3p0-4`=m2m.fusion-iot.de — **no mtm.tag.com** ❌
  The two working carriers have the `mtm.tag.com` M2M data APN that actually works on this deployment;
  the two stuck carriers are configured only with generic/public APNs (drei.at / gprsinternet /
  m2m.fusion-iot.de) + one blank-APN profile, none of which bring up a data bearer here.
- ⇒ **This is a CCU-side APN misconfiguration (NetworkManager connection profiles), likely NOT a
  carrier/SIM provisioning problem.** Fix = give the Drei + T-Mobile interfaces the working
  `mtm.tag.com` profile (or fix the empty-APN one), then re-connect. Nomad/R&D-ownable, testable,
  reversible. Still NOT changed from here (production modem config — R&D change + review).
- `/etc/mar3/apn_lookup_table.json` maps 23205→drei.at, 23203→gprsinternet, 23201→a1.net (generic
  public); the WORKING path is the NM per-iface `mtm.tag.com` override, not the lookup table. Worth
  confirming with R&D which is the intended source of truth.
- ⚠️ Caveat: this is 105 in a parked state (Wien, speed 0), 6-min uptime — verify the same profile gap
  on 110/106, and confirm the stuck modems don't recover once moving/over time. But the config
  asymmetry (missing mtm.tag.com profile on exactly the 2 stuck ifaces) is concrete regardless.

**Ties the whole investigation together:** the SAME two carriers (Drei 23205, T-Mobile 23203) are the
l1/l3 links that showed all the NAT-churn + `Auth login failed` on 110. Two trains, same two carriers,
both symptoms (churn on 110, no-data-bearer on 105) point at **Drei + T-Mobile SIM/APN provisioning**.
This is the strongest single lead for the actual availability fix — hand to R&D + the MNO: confirm those
SIMs are provisioned for `mtm.tag.com` (or why the CCU isn't applying the data APN to them and they fall
back to `ims`). NOT touched from here (production modem provisioning = R&D/carrier action).

## Reboot-storm + CMM-wedge root causes (2026-07-27, box1-t1)

Investigated why 105 reboots so often (the actual root behind the modem-activation failures). TWO findings:

**A) TWO reboot schedulers are stacked (config problem).**
- `nd-scheduled-reboot.timer` OnActiveSec=5h (the one we added 2026-07-24), AND
- `/var/spool/cron/crontabs/root`: `0 3 * * * /usr/sbin/reboot` — **Puppet-managed nightly 03:00 reboot**
  (comment `# Puppet Name: Scheduled CCU Reboot`).
- Both fire → more reboots than either alone, sometimes minutes apart. Today's 03:00 reboot was confirmed
  the CRON one (`CRON session opened → logind "system will reboot now"`), NOT the 5h timer — which is why it
  had no SCHEDULED_REBOOT marker (that marker only tags the 5h-timer path). **The 5h timer was added without
  removing/reconciling the pre-existing nightly cron.** Fleet-wide implication: check whether every DOSTO CCU
  now has BOTH. This is the main driver of the excess reboots. (The 06:39 reboot today was a one-off — my
  earlier authorized `systemctl reboot` to test CMM recovery, not a fault.)

**B) The wedged CMM I2C bus is degrading the WHOLE CCU, not just the logger.**
- `kernel: i2c_designware i2c_designware.1: controller timed out` repeating ~1/sec (05:20 window), and
- `watchfrr: Thread Starvation: ... scheduled to pop >53s ago` at 05:25 — a 53-SECOND scheduler delay.
- The stuck I2C controller spamming timeouts correlates with system-wide thread starvation → THIS is what
  caused MAR/NM to fail to auto-activate 2 of 4 modem profiles. So the CMM wedge (provoked by the 2s logger)
  has system-wide fallout: dead power data AND scheduling degradation AND the modem-activation failures.
- Reinforces: revert 2s→10s (done) AND the CMM needs a hardware power-cycle to clear the wedged controller;
  a soft reboot did NOT clear it. Until cleared, expect recurring i2c-timeout storms on 105.

**Net causal chain for 105:** 2s CMM logger → wedged i2c_designware controller (soft-reboot won't clear) →
kernel i2c-timeout storm + 53s thread starvation → MAR/NM skips activating some modem profiles → modems DOWN.
Plus two stacked reboot schedulers (5h timer + nightly-03:00 cron) causing the excess reboots. NONE of this is
the mar3.json operator list (102 disproved that) and NONE is carrier/SIM.

## CMM recovery — ALL software paths exhausted, needs physical power cycle (2026-07-27, box1-t1)

The CMM I2C wedge is at the **chip level**, confirmed by elimination — every non-power recovery tried and failed:
1. **Soft reboot** (`systemctl reboot`) → i2ctransfer still timed out.
2. **`i2c_designware.1` driver unbind/rebind** → both writes succeeded (host controller re-initialized cleanly),
   but `i2ctransfer -y 2 w1@0x2d 0x04 r9` STILL `Connection timed out`. So the host controller was fine; the
   CMM chip is unresponsive. Verified bus 2 is CMM-dedicated (no other i2c clients on `2-*`; RTC/SPD/NICs are on
   other controllers) so the rebind was isolated and safe — it just couldn't help.
3. **`/usr/bin/cmm`** tool → dead (GLIBC 2.38 vs older libc — the known breakage).

⇒ **Only a TRUE power cycle (ignition off/on or chassis power removal at the vehicle) will clear it. No remote/
software option remains.** This is a physical/depot action.

**Failure-mode finding for R&D:** the 2s CMM poll cadence didn't merely glitch readings — it hung the CMM
microcontroller into a state that survives an OS reboot AND a host-I2C-controller reset, recoverable only by
physically removing power. Strong justification for the 2s→10s revert (done) and worth a hardware/firmware
ticket: over-polling the ADLINK R5001C CMM over I2C can wedge it unrecoverably-without-power-cycle.

## Zabbix fleet-state check (2026-07-27) — dark trains correlate with the 5h REBOOT CRON, not the logger

Queried Zabbix (trainzabbix-obb-alpin.nomadrail.com, okapi) for last-ICMP-data per CCU — independent of SSH
reachability. Result:

| Train | CCU | Last Zabbix ICMP | 2s CMM logger | 5h reboot cron | State |
|---|---|---|---|---|---|
| 110 | 10.179.23.1 | 07-26 00:56Z (~8h dark) | ✅ | ✅ | dark, no recovery |
| 119 | 10.179.12.1 | 07-26 02:59Z (~5h dark) | ✅ | ✅ | dark, no recovery |
| 106 | 10.179.19.1 | 07-26 03:48Z (~4h dark) | ❌ (journal+cron only) | ✅ | dark, no recovery |
| 105 | 10.179.1.1  | live (07:32Z)          | ✅ (now 10s) | ✅ | reachable, CMM wedged |
| 102 | 10.179.47.1 | live (07:32Z)          | ❌ | ❌ | healthy |

**Key correction (verified 106 does NOT have the 2s logger — deploy table + 25-Jul review note both confirm):**
- The common factor across ALL THREE dark trains (110/119/106) is the **5h reboot cron** we added 2026-07-24,
  stacked on the pre-existing nightly-03:00 cron. The only healthy control (102) is the one WITHOUT the 5h cron.
- The 2s CMM logger is an ADDITIONAL aggravator on 110/119 (and demonstrably wedged 105's CMM), but it is NOT
  the common factor — 106 is dark without it.
- ⇒ Best-supported hypothesis: **the extra reboot cron (double-reboot) is the primary driver of trains not
  recovering after a reboot** (excess reboots + the known FN990 modem-stuck-after-reboot behaviour = reboot →
  doesn't re-establish). The 2s logger compounds it on 110/119.
- Zabbix ICMP shows a clean FLATLINE at the reboot boundary (no ping=0 flapping, just stops) = fell off the
  network at once and stayed off — NOT normal cellular intermittency (which flaps up/down).
- Honest limit: correlation on 3-dark / 2-healthy (n small, 102 the only no-cron control). Not proof. But the
  cron is ours, added last week, and removable — so it's the first thing to pull.

**Actions:** (1) remove the 5h reboot cron fleet-wide (Puppet source) — 102 proves no-cron = healthy; (2)
110/119/106 likely need physical power cycles to recover (reboot won't fix a wedged/stuck-after-reboot state,
proven on 105); (3) revert 2s→10s on 110/119 once reachable (post power-cycle). Escalate: 3 CCUs dark needing
vehicle-side power cycles.

## FLEET-SCALE finding (2026-07-27 Zabbix sweep) — NV6-wide dark-after-reboot, NOT caused by our changes

Swept ALL project-50 DOSTO CCUs in Zabbix (last-ICMP per host). Result:
- **NV6 (50_6xxx): 5 live, 8 dark >1h.** NV4 (50_4xxx): 3 live, 1 dark. Other: 0 dark.
  (Also many "no-data-record" hosts — 10 NV6, 24 NV4 — UNKNOWN meaning: decommissioned / not-yet-commissioned
   / monitoring misconfig / aged-out history. Do NOT treat as "dark" — can't tell. So the honest statement is
   "among NV6 with recent history, ~as many dark as live," not "8 of 13".)
- The 8 dark NV6 CCUs dropped 07-25 14:36 → 07-26 05:29, EACH a clean **FLATLINE** (0 ping=0 points before
  dying = dropped off at once, no degrade/flap). Trains: 6018, 6016, 6040, 6023(=110), 6021, 6012(=119),
  6019(=106), 6002(=120).

**This CORRECTS the earlier direction of travel (I'd been narrowing toward "our 2s logger / 5h cron broke
110/119"). The fleet view disproves that as the primary cause:**
- Only 2 of 8 dark trains (110, 119) had our 2s logger; only 3 (110/119/106) had our 5h cron. **5 of 8 dark
  trains had NEITHER of our changes** (6018/6016/6040/6021/120). So the pattern is NOT ours.
- It's **NV6-specific** (8 dark vs 1 NV4) → an NV6 platform/config issue, not carrier/Zabbix/our-stopgap.
- Clean flatline + not-recovering-after-a-reboot-window = fits the **known pre-existing FN990 modem-stuck-
  after-reboot/power-cycle bug** ([[project_dosto_modem_stuck_registered]], RD-12165 etc.), mitigated only by
  the nd-watcher modem watchdog — which evidently isn't saving these.

**Revised conclusion:** there is a broader NV6 "reboot → modems don't come back → CCU stays dark" availability
problem, pre-dating and exceeding our changes. Our 5h reboot cron is a CONTRIBUTING factor only (more reboots
= more chances to hit the stuck-modem bug) — still worth removing, but NOT the root cause. 105's CMM wedge (our
2s logger) is a separate, real, but narrower issue (1 train, recoverable by power cycle).

**What to actually chase (R&D):** why NV6 modems don't re-establish after a reboot/power-cycle and why the
watcher watchdog isn't recovering them on these trains — that's the fleet availability driver. Cross-ref the
DEL-OBB availability complaint: the dark-after-reboot NV6 CCUs ARE the "randomly offline" trains ÖBB reported.

## ⚠️ THE LIMIT: monitoring CANNOT distinguish "powered off" from "modem stuck" (2026-07-27)

The open question — were the 8 dark NV6 trains normally powered off, or did they reboot/power-cycle and the
modems failed to reconnect? — **cannot be answered from the monitoring side.** Reason: Zabbix AND the NMS
reach the CCU only *through the cellular tunnel*. If the tunnel is down (case b: modem stuck), every monitoring
signal dies — exactly as it does if the CCU is powered off (case a). Confirmed on 110: all 381 Zabbix items
(ICMP, agent fs/docker/gps/msata checks — not just ping) stopped in the SAME 60s at 00:56. A clean simultaneous
death is consistent with BOTH power-off and tunnel-loss; it does not discriminate.

- Drop-time hint (soft, not proof): CEST drop times — 6018 16:36, 6016 16:54, 6040 21:43, 6012 04:59, 6002
  07:29 (several NOT obvious end-of-service); 6023/110 02:56 + 6021 03:04 (nightly-reboot window); 6019/106
  05:48. Suggestive of faults for the daytime ones, but "16:36 = in service" is an assumption about rostering,
  not knowledge — a train can be stabled off-peak. Timestamps are hard data; the in-service/parked reading is soft.

**What WOULD answer it (none available from here right now):**
1. The train's own journal AFTER it recovers — boot record + no successful tunnel = modem-stuck; clean
   shutdown→power-on = normal cycle. Needs the train back + SSH. (Why the persistent-journal rollout mattered —
   but it's on only 3 trains, all currently dark.)
2. CMM Vin/Vign across the drop — only on 110/105/119, all wedged/dark. Dead end now.
3. **ÖBB roster / ignition-relay logs: was each unit SCHEDULED IN SERVICE or stabled at its drop time?** The
   cleanest external discriminator — and it's exactly what the DEL-OBB RDS-availability thread is already asking
   Stadler/ÖBB for (vehicle-side power/ignition logs). This closes the loop with that thread.
4. NMS RTPI/journey feed — did the train have an ACTIVE journey when it went dark? Nomad-backend data (not the
   CCU), possibly queryable with an NMS login (okapi is Zabbix-only; needs abbas.rizvi NMS creds).

**Honest disposition:** we can prove *state* (8 NV6 dark, clean flatlines, NV6-specific, mostly not our trains)
but NOT *cause* (power-off vs modem-stuck) from monitoring alone. Do not assert modem-stuck as fact fleet-wide;
it's the leading hypothesis (fits the FN990 stuck-after-reboot pattern + NV6-specificity) but unproven per-train.
Next real evidence comes from (1) recovered-train journals or (3) ÖBB's roster/ignition data.

## ✅ RESOLVED via NMS GPS — the dark NV6 trains were POWERED OFF NORMALLY, not modem faults (2026-07-27)

Got the discriminator monitoring couldn't give: NMS `/gpsData` (project 50, per-train, via nms_console).
GPS speed+position right up to each train's drop time distinguishes "parked & powered off" from "dropped
in service". Checked 3 of the 8 dark NV6 trains:

| Train (box) | Drop UTC | GPS signature at drop | Verdict |
|---|---|---|---|
| 4736-120 (6002) | 05:29 | decel 31→0 km/h, then stationary ~1.3 min, then dark | normal stop & power-off |
| 4736-110 (6023) | 00:56 | stationary 90+ min at FLO (~0 km/h), then dark | parked → power-off/reboot |
| 4736-115 (6018) | 14:36 | low-speed shunt (max 16 km/h) → stop → parked ~1 min → dark | normal stop & power-off |

**All three were stationary/parked when they went dark — NONE dropped while running in service.** All three
were in the SAME Vienna-area location (~48.268, 16.416 — a depot/stabling yard, "FLO"). Even the mid-afternoon
drop (4736-115, 14:36) was low-speed yard shunting → stop → power-down, NOT a line-speed in-service cutoff.

**Conclusion — the fleet-scare is resolved and the earlier "NV6-wide fault" framing was WRONG:** the "8 dark
NV6 CCUs" are trains being taken out of service and PARKED/POWERED DOWN at a Vienna depot through the day, one
after another. The clean flatlines + clustering + NV6-specificity all fit normal end-of-service power-offs (NV6
trains are the ones cycling through this yard), NOT modem-stuck-after-reboot and NOT our logger/cron. The user's
instinct ("maybe it's just a normal train power off") was correct; GPS proves it for every train checked.

**UPDATE — 8 of 8 now confirmed (all 5 remaining GPS-checked):** 6016/4736-116 (moving→stopped 14:31→parked
23min→dark 14:54), 6040/4736-112 (parked→dark 19:43), 6019/4736-106 (parked at 47.80,16.23→dark 03:49), the
03:00 one (parked→dark, =nightly reboot), and one more (parked→dark 08:09). **Every one of the 8 was
stationary/parked when it went dark — none dropped in service.** They cluster in TWO Vienna-area stabling yards
(~48.26,16.41 and ~47.80,16.23). Fleet-scare fully resolved: 8/8 = normal depot power-downs.

**Caveats (kept honest):** (1) 8/8 verified parked — no genuine in-service fault in the dark set. (2) This does NOT undo the two REAL,
narrower findings that stand on their own: 105's CMM I2C wedge (our 2s logger — needs power cycle) and the
double reboot-scheduler (5h timer + nightly-03:00 cron). Those are still worth fixing. (3) A parked train going
dark is normal; it does NOT explain any *in-service* unreachability ÖBB reports — that (if real) is separate and
still points to the FN990 stuck-after-reboot pattern, but we have NO evidence of it in this dark set.

**Net for the DEL-OBB availability thread:** be careful not to present these 8 as "faults/outages" — GPS shows
they're normal depot power-downs. The genuine availability question (trains unreachable WHILE rostered/in-service)
needs ÖBB's roster to identify which offline events actually coincide with scheduled service — the dark set here
does not.

## IMAT roster cross-check (ÖBB Export_20260724_113929) — confirms the dark trains are NOT in-service failures

Cross-referenced the 8 dark NV6 trains against ÖBB's IMAT fleet-disposition export (as of 2026-07-24 11:39):

| Train | GPS verdict | IMAT TFZSTATUS | activity tag (REP col) |
|---|---|---|---|
| 4736-106 | parked→dark | **REP** (repair) | SFPR 23.07 |
| 4736-115 | stop→park→dark | **REP** (repair) | TUI 28.06 |
| 4736-116 | stop→park→dark | **Servicefahrt/PMM** | SFPR 22.07 |
| 4736-118 | parked→dark | **PMM** (maintenance) | F0 25.07 |
| 4736-110 | parked→dark | OK | F0 26.07 |
| 4736-119 | dark 02:59 | OK | F0 29.07 |
| 4736-120 | stop→park→dark | OK | BGWL 06.08 |
| 4736-112 | parked→dark | (not listed — commissioning) | — |

- 5 of 8 are **explicitly NOT in normal passenger service** (REP repair / PMM maintenance / Servicefahrt).
- The 3 marked **OK** (110/119/120) all carry a scheduled activity date-tag around their drop dates.
- ⚠️ ÖBB status codes (F0/BGWL/SFPR/TUI/Servicefahrt/PMM) NOT authoritatively decoded here — do not invent
  meanings; Servicefahrt=service/test run and REP=repair are safe; the short tags need ÖBB confirmation.

**Confirms the GPS conclusion:** the dark set is trains in maintenance/service-runs/parked-between-duties,
powered down normally — NOT "should-be-in-service trains that went dark." IMAT status backs GPS, doesn't
contradict it.

**Honest gap:** IMAT gives maintenance DISPOSITION + planned activities, NOT the minute-by-minute DUTY ROSTER.
So for the OK trains we can't PROVE they weren't rostered at the exact drop minute — only that GPS(parked) +
IMAT(scheduled activity) both indicate not-in-active-service. Strong, not absolute.

**This is the discriminator the DEL-OBB availability dispute needs:** cross-reference "CCU dark at time T" ×
"train rostered in passenger service at time T". None of these 8 fail that test. The IMAT export (or the duty
roster) is exactly the data to settle which — if any — ÖBB-reported "offline" events were real in-service outages
vs normal depot power-downs.

## ⭐ REAL IN-SERVICE OUTAGE FOUND: 110, 22-23 Jul — CCU POWERED OFF (not modem-stuck)

User reported 110 was in passenger service but didn't connect for ~2 days (22-23 Jul), back on the 24th.
This is a genuine in-service outage — DIFFERENT from the 25-26 Jul depot power-downs, and one the GPS method
COULD NOT catch (no modems up → no GPS → looks like "parked"). Traced it via two independent on-box/ground sources:

**Zabbix ICMP (ground-side, 110 = host 11425):** 22-24 Jul only 762 of ~5760 expected points — MOSTLY DARK.
Reachable 21 Jul until 15:50, then: dark 19.4h (22 Jul 05:34→23 Jul 00:58), brief blip, dark 23.8h
(23 Jul 02:44→24 Jul 02:32), recovered 24 Jul 02:32 full day. Flickering/cycling shape, not a clean single off.

**CMM power log (`vign_live_20260724.csv`, local, covers to 24 Jul 07:25) — THE DECISIVE SOURCE:** the CMM
logger has GAPS exactly matching the outage — 19.5h (22 Jul 05:34→23 Jul 01:03) + 23.9h (23 Jul 02:44→24 Jul
02:37). **The CMM logger writes to local /data independent of any network — it only stops when the CCU is
POWERED OFF.** If modems were merely stuck (CCU up), it would have logged straight through. It didn't → the CCU
was powered off during the outage. Last reading before each gap = fully healthy (Vin=121.37, Vign=121.60, both
nominal, no ignition drop, no collapse) then power removed between samples = the SAME "abrupt hard cut"
signature as the Stadler power-outage report.

**⚠️ CORRECTED CONCLUSION (user challenged "power cut" — rightly).** My first read said "CCU powered off /
vehicle power cut." That was OVERCONFIDENT. The CMM logger STOPPING does NOT prove power-off — it stops in EITHER
case: (A) power removed, OR (B) the CCU powered-but-HUNG severely enough to freeze even the local logger (full
kernel/scheduler hang — cf. the 53s thread-starvation seen on 105). Healthy voltage-to-last-sample is equally
true in both. So the CMM data alone CANNOT distinguish power-cut from hang.

**Why hang (mode B) is a live possibility, not a stretch:** 106 is a CONFIRMED hang-not-power case the SAME week
(up-but-unreachable, /data written continuously, no pstore panic, cleared only by a MANUAL/HARD reboot ~24 Jul).
User reports 106 needed a hard reboot Friday to recover — and asks whether 110 was the same. 110's outage also
ended only at a reboot (start rows at 23 Jul 01:03, 24 Jul 02:37). Ruled OUT the CMM-I2C-wedge hang sub-mode for
110 specifically (only 3 glitch rows, all 24 Jun; cadence was 30s not 2s on 22 Jul — 110 was NOT wedging its CMM
like 105). But a general software/USB/network hang (the 106 mode) remains fully consistent with the CMM-log gap.

**Honest conclusion: 110's 22-23 Jul in-service outage = CCU stopped logging + recovered only at a reboot.
Consistent with EITHER a vehicle power-cut OR a powered-but-hung state (the confirmed 106 mode). CMM data cannot
distinguish them.** What WOULD have distinguished: if the CCU were hung-but-alive with CMM still readable, the
local logger would have kept writing → we'd know it was a hang. It stopped → ambiguous (off, or hang severe
enough to freeze the logger). The persistent journal (which logs continuously through a hang, only wiped on
reboot) COULD have settled it — but it was installed 24 Jul, one day AFTER this outage. That is exactly the gap
the persistent-journal rollout closes going forward.

**Caveats:** (1) Do NOT tell the customer this was "vehicle power" — it's unproven; it may be the 106-style hang.
(2) Still a DIFFERENT event class from the 25-26 depot power-downs (this one was in service). (3) To catch the
NEXT one: persistent journal (writes through a hang) + CMM log together will distinguish hang vs power-cut
definitively — journal keeps logging in a hang, stops+pstore-clean in a power-cut.

**Method lesson:** GPS-based "was it parked?" CANNOT detect an outage where the modems are down (no GPS uploaded).
For in-service outages, the CMM power log (survives, local) + Zabbix ICMP history are the right sources — GPS only
works when the train is actually connected.

## ✅ 105 CMM WEDGE CLEARED by a power cycle (2026-07-26 ~08:05) — confirms the diagnosis

105 went offline on its own (no soft reboot by us) and came back ~08:05:08. Checked live at ~08:26:
- `i2ctransfer -y 2 w1@0x2d 0x04 r9` → **returns 9 bytes** (`0x04 0xa0 0x01 0xe7 0x2a...`) — CMM RESPONDING again.
- `dmesg | grep -c i2c_designware...timed out` → **0** (was a continuous ~1/sec storm while wedged).
- `vign-logger.service` active, writing REAL voltage (Vin=108.87, Vign=109.05) — first real CMM data since it
  wedged 2026-07-25 11:51.
- Uptime 21 min, boot 08:05:08.

**Confirms the CMM-wedge diagnosis end-to-end:** the wedge cleared ONLY after this reboot, and we had already
PROVEN a soft `systemctl reboot` + driver unbind/rebind do NOT clear it → therefore the 08:05 recovery was a
HARD POWER CYCLE (ignition off/on at the vehicle). Matches the prediction exactly: chip-level I2C wedge is
recoverable only by removing power. (Didn't need to separately confirm hard-cut via pstore/shutdown-marker — CMM
recovery IS the proof, since soft reboot can't do it.)

⚠️ 105 is FLAPPING right now — reachable at 08:26, dark again by ~08:30 (3 retries failed). Just came back +
possibly moving/settling; not necessarily a fault. The 10s-cadence + awk-fixed logger is in place so it will NOT
re-wedge the CMM. Also note: 106 shows offline in NMS right now (its own separate hang/outage — has persistent
journal since 24 Jul, so its NEXT recovery should be diagnosable hang-vs-powercut).

## Watcher-scripts investigation (2SD Confluence) — decided NOT to enable

Read the 2SD "Watcher Scripts" + "Check modem hardware" + "Telit FN990" pages (note: docs migrated to
nc-docs.nomadrail.com; 2SD is legacy). Findings:
- DOSTO CCUs run only 3 watchers (`services.json`): `watcher-mc7455-apn` (useless — for old Sierra modems),
  `watcher-fn990`, `watcher-modem-not-connected`. Confirmed identical on 102.
- NOT running: `watcher-hc-usb-bus-died` (greps journal for literal "HC died" → reboots when no users) and
  `watcher-modem-manager-defunct` (reboots immediately if MM defunct / `mmcli -L` times out, NO user check).
- These looked like candidates for the 106-style "up-but-unreachable, needs hard reboot" hang.

**VERIFIED on 105's persistent journal (reachable; spans all today's outages back to 24 Jul): ZERO "HC died",
zero USB-controller-death signatures.** So `watcher-hc-usb-bus-died` would NOT fire on 105's outages — they are
power cuts + orderly reboots, not USB-bus deaths. `mm-defunct`'s no-user-check immediate hard reboot is risky
given the modem churn. **Decision (user): do NOT enable the watchers** — no evidence they match our failure
modes, and they add reboot triggers we've been trying to reduce. Left unchanged.
- Open (only if pursued later): 106 is the actual documented hang case — if its journal shows "HC died", the
  hc-usb-bus-died watcher would be justified there specifically. Not chased now.

## 105 outage nature (2026-07-26) — mostly POWER, per persistent journal
- 08:26→11:05 outage (the one asked about): abrupt journal stop mid-activity (no shutdown seq) + CMM-log gap
  169min + voltage discharge(112→108.9)→recharge(124.6) + empty pstore = **hard power cut then restored.**
- Other today boundaries: 06:39 + 07:32 were ORDERLY reboots (clean unmount seq — 06:39 was our own authorized
  `systemctl reboot`). CMM i2c wedge RE-appeared 06:38 then cleared again by the power cycle. CMM healthy now.
- 105 pattern = repeated abrupt power loss + short cycles = supports the flapping-vehicle-power hypothesis; ties
  to the DEL-OBB power thread. 105's CMM seems fragile (re-wedges) — flag for depot HW attention.

## vlan7 FW-reachability probe added to netdrop logger (2026-07-26)

Question: "did the vlan7 VPN drop while the train was online?" The netdrop logger's `rds_flow` tracks the
tunnel-carried RDS app flow (62.2.130.53), NOT the raw vlan7 link to the Stadler FW. First pass on 105:
61 rds-down-while-online samples → 7 episodes, 6 = post-reboot settling, only **1 genuine mid-uptime RDS
drop (2026-07-26 08:06:44→08:08:31, ~1.8 min)**. So RDS app flow was stable while online bar one brief blip.

To close the vlan7-vs-RDS gap, EXTENDED the netdrop logger with two new columns: **`vlan7_fw`** (Stadler FW
ARP-reachable on vlan7? 1/0/-) and **`fw_ip`** (auto-derived per-train, NOT hardcoded — reads the vlan7
non-self neighbour, else CCU_vlan7_ip−1). Uses ARP state (REACHABLE/STALE/DELAY/PROBE=up), NOT ICMP —
a commissioned Stadler FW drops ping by policy (CLAUDE.md Phase 6 Q1) so ICMP would false-negative; sends a
1-pkt ping only to nudge L2 ARP resolution. Deployed to 105 2026-07-26 11:55, verified writing
`vlan7_fw=1, fw_ip=172.19.194.129`. Old CSV rotated to `netdrop.csv.pre_vlan7_*` (schema 8→10 cols).
Canonical: `netdrop_logger/netdrop_poll.sh`. TODO: redeploy to 110/119/106 when reachable.
Caveat: `vlan7_fw=0` reliably = vlan7-to-Stadler link down (ARP failed); small chance of brief false-0 if
ARP mid-refresh — good drop-detector, not a perfect uptime meter. A vlan7 drop while online = `vlan7_fw=0`
with `tun_up=1, links_up>=1`.

## Stadler-path L2/L3 coverage model — what the netdrop columns mean (2026-07-26)

Confirmed topology on 105 (conntrack): the Stadler RDS VPN is NOT built by the CCU — the Stadler FW/RCU
on vlan7 (172.19.194.129) originates it and it TRANSITS the CCU:
```
Stadler FW/RCU (172.19.194.129) --vlan7 L2--> CCU --NAT--> mar5-tun --> 62.2.130.53 (Stadler backend)
        [LEG 1: L2 link]                              [LEG 2: L3 VPN, transiting OUR tunnel]
```
conntrack: `src=172.19.194.129 dst=62.2.130.53 dport=83` NAT'd to CCU tunnel src `10.179.1.254`, egress mar5-tun.
So the CCU is a TRANSIT HOP for the L3 leg, not the VPN endpoint.

**How the netdrop columns map to the two legs (and how to tell them apart):**
| Observation | Meaning |
|---|---|
| `vlan7_fw=0` | **L2 fail** — vlan7 link CCU↔Stadler FW down (on-train / vlan7 problem) |
| `vlan7_fw=1` + `rds_flow=0` (+ `tun_up=1`) | **L3 fail** — vlan7 to Stadler is fine, but the RDS VPN flow to the backend isn't passing → failure is DOWNSTREAM of vlan7 (transit / backend leg) |
| `tun_up=0` or `links_up=0` | our OWN tunnel/cellular is the cause, not Stadler-specific |

⇒ The logger covers **both L2 (fully, CCU side) and L3 (the CCU-observable symptom)** and DISTINGUISHES
L2-vs-L3-vs-our-tunnel.

**Honest limitation (load-bearing when reading L3 failures):** because the CCU is only a transit hop for the
L3 leg, `rds_flow=0` detects the SYMPTOM (flow stopped appearing in conntrack) but CANNOT localize WHERE the L3
path broke — could be (a) the RCU stopped originating the VPN (Stadler-side), (b) our tunnel egress
(77.237.62.210), or (c) the path between our backend and 62.2.130.53. All three look identical from the CCU. To
localize an L3 failure you need our MAR backend logs and/or Stadler's RCU logs — the CCU alone can't see past
its own tunnel egress. (L2 failures, by contrast, ARE fully localizable from the CCU via `vlan7_fw`.)

## Zabbix→NMS alarm for netdrop — PROTOTYPE VALIDATED on 105 (2026-07-26)

Goal: surface the netdrop logger's Stadler-connectivity errors in the NMS. Built + validated end-to-end on
105 (host `50_6001_MAR3-B1`, hostid 12262). Alarm condition (as requested): **vlan7 L2 down OR RDS VPN down,
while the train is online.**

**The chain (all proven):**
1. CCU: `check-netdrop.sh` (→ `/usr/local/bin/`) reads the LAST netdrop.csv row, emits int:
   `0`=OK, `1`=vlan7 L2 link to Stadler FW down while online, `2`=RDS VPN flow to backend down while online.
   Gated on train-online (tun_up=1 & links_up>=1) + a 5-min stale-data guard (returns 0 if logger stale, so a
   whole-train-offline event doesn't double-alarm with the existing ICMP-down). Read-only; runs as `zabbix`.
2. Zabbix agent UserParameter `check_netdrop_stadler` (→ `/etc/zabbix/zabbix_agentd.conf.d/check_netdrop.conf`)
   — follows the existing `.conf.d/*.conf` custom-check pattern (UnsafeUserParameters=1 already set).
3. Proxy (on CCU) → server: item `1169350` (agent, numeric unsigned, 60s), trigger `355832`
   (`last(...)<>0`, severity 3/Average). Both HOST-SCOPED (templateid=0), not on the template.
4. **NMS: alarm surfaced** — confirmed by test-fire (forced script→`1`; NMS showed "Stadler connectivity lost
   while train online (netdrop) on MAR3-B1"; cleared cleanly on revert). ⭐ Notably a HOST-LEVEL, tag-less
   custom trigger DID surface in NMS — resolves the earlier uncertainty about whether non-template triggers show.

**Files:** `netdrop_logger/check_netdrop.sh` + `check_netdrop.conf` (canonical). Live on 105 runtime + the
Zabbix item/trigger are LIVE (real working alarm now on 105 only).

**Fleet rollout (NOT done — Puppet/DevOps owns; both pieces are Puppet-managed so runtime files revert):**
1. CCU side: ship `check-netdrop.sh` + `check_netdrop.conf` via the Puppet zabbix-agent module.
2. Zabbix side: add the item+trigger to **`Template CCU - DOSTO NEU`** (templateid 10463) so ALL DOSTO CCUs
   inherit it — cleaner than per-host API creates. Host-level surfaced in NMS, so template-level should too.
   ⚠️ template edits on this fleet are the known-risky path (inherited-LLD/override API footguns) — do carefully.
Prototype item/trigger on 105 can be left as-is (working) or removed once the template version lands (avoid dup).

## Hard power-cut counter — PROTOTYPE on 105 (2026-07-26)

Goal: quantify how many hard power-cuts a CCU gets (metric for the vehicle-power problem). Built + validated.

**Detection (ground truth):** a boot follows a HARD CUT if there is NO `GRACEFUL_SHUTDOWN`/`SCHEDULED_REBOOT`
marker in `/data/ignition-log/shutdown.log` within 90s before the power-loss (the vign-shutdown-marker service
writes such a marker only on a clean stop). "Hard cut" = abrupt-power-loss OR a severe hang that froze the box
before it could write a marker — **NOT proven "vehicle power cut"** (needs the vehicle-side ignition log;
voltage discharge/recharge across the gap in vign.csv tends to indicate real power).

**Chain:**
- `hardcut_classify.sh` (→ `/data/ignition-log/`) runs ONCE per boot via oneshot unit
  `nd-hardcut-classify.service` (After=vign-logger, 20s ExecStartPre so the 'start' row exists). Classifies the
  just-ended outage, maintains `/data/ignition-log/hardcut-state.json` `{total, last_event_iso, ...}`.
- `check-hardcut.sh total` → Zabbix UserParameter `check_hardcut_total` (→ `check_hardcut.conf`).
- Zabbix item `1169373` (5m poll, 365d trends) + trigger `355833` = `change(/50_6001_MAR3-B1/check_hardcut_total)>0`
  → NMS alarm "CCU hard power-cut detected" once per new cut. Validated by test-fire (NMS showed + cleared).

**DESIGN NOTE (learned the hard way):** first built a self-resetting `recent` flag item for the per-event
alarm — it's RACY through the agent→proxy→server cache (can latch/double-count). RETIRED it. The robust
per-event alarm is `change()>0` on the monotonic `total` counter — no self-reset, naturally one-alarm-per-cut.

**Seeded value on 105: total=1** — correctly captured today's confirmed hard cut (08:26→11:15, 169-min gap, no
shutdown marker). NOTE: 105 actually had TWO hard cuts this morning (a short ~08:04→08:11 one + the 08:26 one);
the counter only saw the latest because it was seeded after the fact — going live it counts each boot as it
happens. Files: `netdrop_logger/{hardcut_classify.sh,check_hardcut.sh,check_hardcut.conf,nd-hardcut-classify.service}`.

**Fleet rollout (Puppet/DevOps — same as the netdrop alarm):** ship the classifier script + oneshot unit +
UserParameter via Puppet; add the item+trigger to `Template CCU - DOSTO NEU`. The `nd-hardcut-classify.service`
/etc unit reverts on NDSU/Puppet snapshot roll (script on /data persists) — re-enable after promote.

## PoE-failure vs link-down discriminator — PROTOTYPE on 102/6047 (2026-07-26)

Goal: for switch port-down alarms, distinguish a PoE failure (powered device lost power) from a plain
link-down (cable/peer). **The switches do NOT expose PoE status over SNMP** (standard POWER-ETHERNET-MIB
absent; vendor net-snmp-extend only has PoE *control* actions portpoeon/portpoeoff, no status reader). So
the existing SNMP ifOperStatus alarm genuinely can't tell them apart. Solution = a CCU-side poller of the
switch CLI `show poe` (Option B), same decoupled pattern as netdrop/hardcut.

**Chain:** `poe_poll.sh` (→ `/data/poe-monitor/`) runs every 5 min via `nd-poe-poll.timer`, SSHes each VDS
switch (a0:59:3a on vlan100, ~18/train), reads `show poe` (per-port Status on/off) + `show interface summary`
(Line col = link up/down), caches per-port state to `poe_status.json`, and **detects on→off PoE transitions**
(sets flag `poe_lost`). `check-poe.sh` (Zabbix UserParameter) reads the cache instantly (agent never blocks on
switch SSH). Zabbix items `check_poe_worst` (0=OK/1=link-down/2=PoE-failure) + `..._fail_count` + `..._linkdown_count`
on host 50_6047_MAR3-B1 (11649), trigger 355834 on `check_poe_worst>=1` (alarm text carries which). Validated
by cache-injection test-fire: NMS showed "Switch port fault ... (worst=2: 1=link-down 2=PoE-failure)", cleared.

**Discriminator logic (behaviourally sound, no false alarms):**
- PoE FAILURE = a port that WAS powering a device (poe on→off transition = `poe_lost`). An always-off/empty
  port never transitions → NOT flagged (the naive "poe=off+link=down" would have false-alarmed on 121 empty
  ports; the transition logic correctly reports 0 on the healthy control train).
- LINK DOWN = link down but poe still `on` (PoE supplying, no link = cable/peer).

**⚠️ UNKNOWN captured for study — `E(1e)`:** `show poe` reports a status `E(1e)` (Power=0, Priority=critical) on
some ports, seen SYSTEMICALLY on ~e1-9 across several HEALTHY switches (link up). Meaning unknown; not in the
manual. Looks possibly-benign (same-position, healthy train) so it is CAPTURED in the poe field but deliberately
does NOT raise an alarm (would be 4 false alarms right now). **TODO: find out what E(1e) means** — if it's a real
fault it should be added to the PoE-failure signal; if benign, document it. Ask Stadler/VDS or check a switch
with a known-good vs known-bad PoE device on e1-9.

Files: `poe_monitor/{poe_poll.sh,check_poe.sh,check_poe.conf,nd-poe-poll.service,nd-poe-poll.timer}`.
**Cost note:** each poll SSHes ~18 switches × 2 commands (~45s/cycle); switches are already SNMP-monitored, so
this adds SSH load — acceptable at 5-min cadence but keep in mind for fleet rollout. Rollout = Puppet (scripts +
timer + UserParameter) + item/trigger on `Template CCU - DOSTO NEU`, same as the other two prototypes.

## Hard-cut + vlan7 alarms deployed to 5 "red" trains (2026-07-26)

Per NMS tile view, deployed BOTH alarms (hard-cut + vlan7/Stadler) to the 5 red (offline/problem) trains:
| Train | box | CCU IP | Zabbix host |
|---|---|---|---|
| 4736-102 | 6047 | 10.179.47.1 | 50_6047_MAR3-B1 (11649) |
| 4736-107 | 6025 | 10.179.25.1 | 50_6025_MAR3-B1 (11766) |
| 4736-109 | 6028 | 10.179.28.1 | 50_6028_MAR3-B1 (11021) |
| 4736-111 | 6024 | 10.179.24.1 | 50_6024_MAR3-B1 (13152) |
| 4736-118 | 6021 | 10.179.21.1 | 50_6021_MAR3-B1 (12306) |

None had the logging stack — deployed the FULL stack to each (runtime; Puppet rollout still needed for durability):
vign-logger (SAFE 10s cadence) + vign-shutdown-marker + nd-hardcut-classify + netdrop-poll (vlan7-extended) +
check-netdrop.sh/check-hardcut.sh readers + UserParameters. Installer: `scratchpad/deploy5/install_stack.sh`.
All 5: loggers active, netdrop vlan7 probe auto-derived correct per-train FW IP (193.1/195.129/196.129/197.129/
201.1), readers return 0 (healthy, no false alarms). Zabbix items+triggers created on all 5 (netdrop_stadler<>0,
change(hardcut_total)>0), verified collecting value=0 state=0.

**Seed artifact fixed:** the first classifier run (no prior boot data → no shutdown marker) falsely set
hardcut total=1/last_was_hardcut=1 on each; reset all 5 to total=0/0 so real cuts count from deploy.

**⚠️ known limitation (from 105):** for a rapidly-flapping train, the hard-cut alarm can only reach NMS if the
CCU stays up long enough between cuts for Zabbix to poll (5m item). The LOCAL /data counter is the reliable
record; NMS surfacing is best-effort and under-reports heavy flapping. Same trust model for these 5.

Rollout-to-durable = Puppet (scripts+units+UserParameters) + template item/trigger — same as the prototypes.

## Hard-cut + vlan7 alarms deployed to 2 MORE "red" trains — 104 + 108 (2026-07-26 evening)

Follow-up to the 5-train rollout above: of the 7 red trains in the NMS tile view, TWO had NOT had this logging
enabled — **4736-104 (box1-t10, 10.179.10.1, host 50_6010_MAR3-B1/11307)** and **4736-108 (box1-t8,
10.179.8.1, host 50_6008_MAR3-B1/11473)**. Both were completely bare (no /data logger dirs, no units, no
checks; `UnsafeUserParameters=1` already set; vlan7 up: 104=172.19.194.2 FW .1, 108=172.19.196.2 FW .1).

Deployed the identical FULL stack to each (installer `scratchpad/logger_deploy/install.sh`, same canonical
payload as the 5-train run — vign-logger **10s SAFE cadence + awk-fix**, vign-shutdown-marker,
nd-hardcut-classify, netdrop-poll vlan7-extended, check-netdrop/check-hardcut readers + UserParameters via
btrfs ro-toggle). Verified per CCU: all 4 units active; vign.csv writing real CMM voltage (104 Vin=104.78 /
108 Vin=118.62, both IGN_mode fault 0x00); netdrop vlan7_fw=1 with auto-derived FW IP (104=172.19.194.1,
108=172.19.196.1), 4/4 modems up, rds_flow=1; agent `-t` returns `check_netdrop_stadler [t|0]`. Same
empty-baseline seed artifact (first classify → false hardcut total=1) reset to total=0/recent=0 on both.

Zabbix server-side: created 2 items + 2 triggers per host (mirrors the 6 existing trains) — items 1170022/23
(104), 1170024/25 (108); triggers 355845/46 (104), 355847/48 (108): `last(check_netdrop_stadler)<>0` +
`change(check_hardcut_total)>0`, priority 3. 104 confirmed collecting value=0 state=0; 108 proxy config-cache
reloaded to pick up the new items. This brings the vlan7/hard-cut alarm coverage to **8 trains**
(105/102/107/109/111/118 + 104/108). Rollout-to-durable still = Puppet + template item/trigger.

## Next
- Retry 110 + 106; pull their weekend netdrop + vign.
- Restart vign-poll on 105 (and verify on 110/106).
- Monday email to Hartmann: still send the request for a fresh VPN report on 110/105/106 — with 105 we can already line up ÖBB's session drops against our reboot timeline for the overlap window.
- Open question for the team: is the 5h scheduled reboot doing more harm than good on trains that are otherwise power-stable?
