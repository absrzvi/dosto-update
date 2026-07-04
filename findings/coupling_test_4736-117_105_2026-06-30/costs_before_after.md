# Coupler port-cost baseline + change record — 2026-06-30

Captured during runbook Part 1, decoupled solo state, before any change.

## Cab-switch IPs (resolved 2026-06-30 ~07:50Z, 2-min leases — re-resolve if stale)

| | A1 | A3 | B1 | B3 | D1 (root) |
|---|---|---|---|---|---|
| 117 master (Fzg 145) | 10.179.32.186 | 10.179.32.184 | 10.179.32.189 | 10.179.32.193 | 10.179.32.181 |
| 105 backup (Fzg 133) | 10.179.1.190 | 10.179.1.193 | 10.179.1.183 | 10.179.1.188 | 10.179.1.181 |

## RSTP root (solo, decoupled) — both clean

- 117: root `a0:59:3a:d0:76:e0` (D1-145), prio 0, all agree ✅
- 105: root `a0:59:3a:d0:6c:80` (D1-133), prio 0, all agree ✅
- All 4 coupler `e0-2` ports DOWN on both trains (real decouple, not phantom — June A6/A7 gate passed).

## Coupler port-cost BEFORE (revert target)

| Port | 117 master (Fzg 145) | 105 backup (Fzg 133) |
|---|---|---|
| A1 e0-2 | `144999999` | `132999999` |
| A3 e0-2 | *(no explicit port-cost — default)* | *(no explicit port-cost — default)* |
| B1 e0-2 | *(no explicit port-cost — default)* | *(no explicit port-cost — default)* |
| B3 e0-2 | `144999999` | `132999999` |

Pattern = v8 template `train_id × 1,000,000 − 1` on A1/B3; A3/B1 unset (use default). This per-train
asymmetry is what drives the coupled TC churn. v9 fix = flat `20000` on all four, both trains.

## Coupler trunk baseline (M2 reference, NOT changed today)

- native VLAN = `0001` (VLAN 1) on all coupler ports — the v9 M2 target (native 999). Cost-only test today.
- prune set = `allow 5,15` ✅ (load-bearing — keep).

## Change applied (Part 1)

**Applied 2026-06-30 ~07:55Z while SOLO/decoupled** (front-loaded so a coupling-induced SSH drop
can't catch us mid-change). All 8 ports verified by read-back = `port-cost 20000`. Not saved
(runtime only — `save running-config force` deliberately skipped; obn update c from v8 would revert).

| Port | new cost | applied? verified read-back |
|---|---|---|
| 117 A1/A3/B1/B3 e0-2 | 20000 | ✅ all four |
| 105 A1/A3/B1/B3 e0-2 | 20000 | ✅ all four |

Post-change sanity (solo): both roots unchanged (117 D1 d0:76:e0 / 105 D1 d0:6c:80), all coupler
ports still link-down, no topology disturbance. Cost change = no reboot, no side effects while solo.

**Test shape change:** because cost was applied solo (not coupled), the proof is now "symmetric cost
BEFORE coupling → couple → confirm NO churn arises" rather than the before/after-churn contrast on one
coupling event. Still valid (cleaner, even). Run 03_churn_watch as soon as coupled to confirm freeze.

## PART 1 RESULT — PASS ✅ (TC churn frozen, 2026-06-30 ~08:00–08:03Z)

Coupled ~07:59Z with symmetric cost 20000 pre-staged on all 8 coupler ports.

**Topology (clean merge):**
- 105 is the ROOT train (105 D1 root, root port e0-1 internal). 117 reaches root via coupler.
- Active coupler link: **117 B1 e0-2 = ROOT/FWD** ↔ **105 A1 e0-2 = DESG/FWD**, both cost 20000 (equal).
- `rstp,p2p,adminEdgeOff` on coupler ports — proposal/agreement ran as designed; converged.
- Other coupler ports down/blocked. One forwarding link, correct.

**Churn = ZERO (the proof):**
- 2 samples ~90s apart (08:00Z, 08:02Z), all switches sampled both trains: TC/flush count = **0**.
- Logs show only boot `RSTP Protocol Handler loaded` + coldStart + our SSH sessions — NO "Flushing all
  entries", NO proposal duel, NO topology-change events. Debug confirmed capturing (RSTP handler line present).
- **Contrast June 110+119:** same 36-switch coupling logged "Flushing all entries" every ~2s continuously,
  driven by asymmetric cost. With symmetric 20000 that storm does NOT occur.

**Verdict:** v9 M1 (flat symmetric coupler port-cost 20000) VALIDATED on a real coupled 2×6 pair →
greenlight the v9 git MR for the cost change. (Max-age M4 not tested today — deferred, see below.)

## ⭐ MAJOR FINDING — CCTV latency resolved by the COST FIX alone (2026-06-30 ~08:05Z)

After applying symmetric cost 20000 (churn stopped), the driver reports **both trains' CCTV feeds now
show on the 117 HMI with NO latency** — and we changed NOTHING on VLAN 5 or the firewalls.

Mechanism evidence captured live while coupled + healthy:
- **TC churn = 0** (Part 1 result above).
- **VLAN-5 FDB STABLE on the active coupler** (117 B1): 119 MACs, identical across two 8s-apart samples
  (vs June: flushed every ~2s). Stable table → frames FORWARDED not flooded. Stadler FW MAC
  `00:90:e8:cb:5d:cc` learned cleanly on e0-1 and held.
- **Coupler live rate ~95 Mbps symmetric** (RX 94.76 / TX 91.65) on B1 e0-2 = healthy bidirectional
  cross-train video, not flood garbage.

**Interpretation — revises June A8:** the coupled CCTV latency/HMI degradation was caused (at least
substantially) by the **TC churn (continuous FDB flush → CCTV flooding)**, NOT primarily the VLAN-15
FW↔FW interaction A8 suspected. June couldn't separate these because the only mitigation that worked
(full decouple) ALSO stopped the churn. Today isolates the variable: **churn stopped WITHOUT decoupling
and WITHOUT touching the FWs → CCTV recovered.**

**Consequence for Part 2/3:** the single-FW VLAN-5 redirect (S1) + backup-FW-SVI-down (S2) were designed
to fix an FW-routing problem that, on this evidence, was likely not the root cause. They may now be
UNNECESSARY. Decision pending (AR): run Part 2/3 anyway as confirmation, or bank the cost-fix result.

## Part 2/3 (confirmation run, system already healthy from cost fix)

Hypothesis INVERTED: CCTV already fixed by cost change → does FW config matter at all?
- CCTV stays perfect through S1/S2 → FW path was never the cause (confirms churn theory).
- CCTV degrades at an FW change → FW does play a role.
Approach: one coach (105 D1) first, brief lease-blip accepted, revert if degraded.

**S0 baseline (healthy):** 105 D1 cameras e1-0..e1-4 up 100M; e1-0 video RX 7.77 Mbps; backup video
group default-router = own FW 172.18.194.129; coupler ~95 Mbps symmetric; FDB stable; CCTV clean on HMI.

**S1 (105 D1 only — repoint to master FW 172.18.200.129):**
- Config changed + verified read-back: D1 video group default-router → 172.18.200.129 ✅
- Bounced e1-0..e1-4 to force renewal; all came back up 100M Full ✅
- Camera video still flowing: e1-0 RX 6.57 Mbps (≈S0's 7.77) — no degradation ✅
- Churn still 0, coupler healthy — repoint didn't disturb RSTP/FDB ✅
- ❓ AWAITING driver HMI confirm: do 105 D1 (coach 3) cameras still show on 117 HMI?
  (clean = master FW return route works; dropped = Stadler return-route gap to 172.18.194.0/24)
- All other 17 backup switches still on own FW 172.18.194.129 (only D1 changed).
- REVERT D1: `configure ip dhcp-server group video default-router 172.18.194.129` + bounce ports.

## CCU REBOOT mid-test (~08:14Z) — state survived

Both CCUs power-cycled again (consist instability) ~08:14Z. /tmp/cpltest wiped on both (redeployed).
**Switch config SURVIVED** (switches didn't reset, only CCUs rebooted): 105 all 4 coupler = 20000 ✅,
D1 video gw = 172.18.200.129 ✅, 117 A3/B1 = 20000 ✅, coupled. **Churn = 6 events** all at one
timestamp (01:02:47 = single reboot re-convergence burst), FROZEN at 6 over 60s — NOT the continuous
storm. Cost fix held through reboot. (Switch IPs rotated on new leases — re-resolve.)

## S1 FULL ROLLOUT — all 18 backup (105) switches → master FW (decision: AR, ~08:30Z)

Engineer directive: eliminate asymmetric FW routing → route ALL backup VLAN-5 via the single master FW.
Confirmed B1 (and D1) cameras working fine after the repoint = master FW return route to backup subnet
172.18.194.0/24 EXISTS (Stadler dependency satisfied — no return-route gap).

- Applied `configure ip dhcp-server group video default-router 172.18.200.129` on all 18 backup switches.
- **18/18 confirmed by read-back** (17 newly set + D1 already set).
- Cameras pick up new gw on DHCP lease renewal (D1 force-bounced earlier; rest renew naturally or bounce).
- Backup train VLAN-5 (CCTV) now routes via the single master FW — no FW-to-FW asymmetry.
- REVERT (all 18): `configure ip dhcp-server group video default-router 172.18.194.129` + renew.

**Camera renewal (force-bounce, ~08:35Z):** bounced each switch's actual VLAN-5 access ports
(per-switch detected: most e1-0..e1-4; A2/B2 +e1-7; the -3 switches only e1-0/e1-1; E2 e1-0..e1-3 —
no coupler/trunk ports touched). All cameras came back up; D1 e1-0 video RX 7.43 Mbps (≈ S0 7.77 /
S1 6.57) — healthy, no degradation. Whole backup train VLAN-5 now active on single master FW.
**RESULT: no CCTV degradation from routing all backup cameras via the master FW** → confirms the FW
routing was tolerant/not the bottleneck; the cost fix (churn) was the real CCTV fix.

## Monitoring during Stadler tests (08:36Z+)

Baseline 08:36Z: TC=6 both, root 105 D1, coupler ~88 Mbps, CCTV ~7.4 Mbps.
- 08:38Z cycle 1: healthy, TC=6.
- 08:42Z: TC jumped 117=24 / 105=42. **NOT the storm** — stepwise jumps (6→24→54) that each FREEZE,
  events clustered at single timestamps (e.g. 01:32:37 burst), then silent. = discrete RSTP TC bursts
  from Stadler's test actions (port bounce / link toggle on coupler), each followed by clean
  re-convergence. Root unchanged (105 D1), coupler up 93 Mbps, CCTV 7.20 Mbps throughout — forwarding
  plane fine. **Alarm logic refined: FROZEN-but-elevated TC = Stadler test event (OK); CONTINUOUSLY
  CLIMBING TC = real churn (flag).** Distinguished by 2 samples 30s apart — if equal, it settled.

## "Can't see 9 switches" on 117 — DIAGNOSED (08:57Z)

Symptom: only ~9/18 switches in `dhcp-lease-list`, IPs rotating (e.g. .181 was D1, later A2), some
SSH-unreachable. NOT a fabric outage — ARP shows 14+ VDS present, RSTP root stable (105 D1).

Ruled OUT:
- **OBN patches** — markers grep 0/11 but VERSION empty (likely 2.2.23 native layout; markers N/A).
  Irrelevant anyway: dhcpd (ISC DHCP) leases switches, NOT OBN; OBN bugs are discover/report/update.
- **nd-backbone-discovery / auto-update** — both run CLEANLY (finish in 1-40s, "Deactivated
  successfully", auto-update every 10 min ~1s each). NOT stuck, NOT churning.
- **dhcpd.conf rewrite** — 0 host stanzas (dynamic pool), last modified once at boot (08:15). Stable.

ACTUAL CAUSE: switches on a **dynamic DHCP pool** (no fixed per-switch entries). Every fabric
disruption — Stadler bouncing ports, TC reconvergence bursts (we watched 6→24→54) — interrupts a
switch's DHCP renewal; on the next DISCOVER it gets a DIFFERENT pool IP. So IPs rotate, only ~9 hold a
completed lease at once, the rest loop and vanish from the lease list. Switches are ALIVE + forwarding
throughout (ARP + stable RSTP root prove it) — only the MANAGEMENT-PLANE DHCP is unstable, driven by
the active-testing fabric disruption. Management-visibility problem, not data-plane.

IMPLICATION for save+restart test: can't reliably address all 18 to `save running-config` while IPs
rotate. Need the fabric to settle (Stadler stops toggling) → switches hold stable leases → THEN save.

## COORDINATED COLD RESTART (coupled) — ~09:10Z

Engineer restarted both trains coupled to observe cold-boot RSTP convergence. **SAVE did NOT happen**
in time (lease churn on 117 blocked addressing all 18; a save attempt mis-ran without _common.sh
sourced = false "18/18 saved"). So runtime changes REVERTED on boot:
- Coupler cost 20000 → back to template 144999999 (117) / 132999999 (105) = ASYMMETRIC
- VLAN-5 DGW (105) → back to own FW 172.18.194.129
- Debug logging → cleared

**So this cold boot = UNFIXED BASELINE / CONTROL.** Trains boot coupled with stock v8 asymmetric
costs → expected to show the convergence/churn behaviour WITHOUT the v9 fix. Useful "before" picture
(we already have the "after": churn frozen with cost 20000). Watch for: TC storm returning, convergence
time, floods, final topology. Also: clean cold boot should reset 117's stale-pool lease churn → expect
117 to come up 18/18 (as 105 did earlier from a clean boot) — tests whether 117's 9/18 was just pool churn.

Capture plan on return: switch boot→convergence timestamps from logs, final root/coupler roles, TC behaviour.

## COLD COUPLED BOOT WITHOUT v9 = FABRIC WON'T CONVERGE (09:10–09:30Z)

After the unsaved restart, trains cold-booted COUPLED with stock ASYMMETRIC template costs (v9 reverted).
Result over 20 min: **switch fabric will NOT come up** — 0–1 switches lease on each train, repeatedly.
- Engineer Wireshark (09:18Z): **DHCP broadcast flood** — same TXID 0x8f865dd0 from Nomad device
  `7c:70:bc:70:d9:59` ("ccu20230725") machine-gunning Discovers (dozens per millisecond). Subsided by
  09:28Z (CCU vlan100 broadcast rate normal then) but fabric still didn't establish.
- Could be the asymmetric-cost RSTP loop, a misbehaving DHCP client, or both — NOT definitively proven
  which. But the contrast is stark: WITH v9 (cost 20000) earlier = clean converge + frozen churn + CCTV
  perfect; WITHOUT v9 cold-boot coupled = fabric drowns. Strong support for v9 + clean-boot requirement.

**Chicken-and-egg:** can't apply v9 (need coupler cab switches reachable) because the unfixed coupled
fabric won't bring switches up. **DECISION (AR): decouple → apply cost 20000 + SAVE running-config solo
(both trains) → recouple + restart.** This worked earlier today (decoupled = clean 18/18 solo) minus the
save. Adding `save running-config` this time so v9 persists through the restart.

Solo-apply+save sequence (per train, all coupler switches A1/A3/B1/B3):
1. confirm decoupled (all e0-2 link-down). 2. wait clean 18/18. 3. cost 20000 on 8 ports.
4. `save running-config` + verify `show startup-config`. 5. recouple + restart → observe clean converge.

## v9 COST APPLIED + PERSISTED (solo, decoupled) — 09:33Z

Decouple worked again: switches came up clean to 18/18 on BOTH trains within ~1 min of decoupling
(117 1→18, 105 0→18). **Confirms coupled-without-v9 was what kept the fabric down.**

Applied `port-cost 20000` + `save running-config` on all 8 coupler ports (A1/A3/B1/B3 both trains),
all link-down (decoupled). **Verified in STARTUP-config = persists through reboot** (the step missed
earlier). New coupler IPs (this boot): 117 A1.192 A3.197 B1.200 B3.185; 105 A1.188 A3.185 B1.191 B3.187.
(Note: `save running-config` prints harmless "Failed to add host to known_hosts" SSH warning — NOT a
save error; startup-config confirmed correct.)

READY: recouple + restart → cold-boot coupled WITH v9 persisted → expect clean convergence (vs the
fabric-drowning we saw cold-booting without v9). This is the real cold-boot v9 validation.

## VLAN-5 single-FW DGW PERSISTED on 105 — 09:36Z

Re-applied + SAVED `video` group default-router → master FW 172.18.200.129 on all 18 of 105's switches.
**Verified in startup-config 18/18** — persists through restart. So both fixes now survive the cold boot:
coupler cost 20000 (both trains) + VLAN-5 single-FW routing (105). Cameras pick up new gw on lease
renewal after boot. Revert (if needed): default-router → 172.18.194.129 + save.

## ⭐ ROOT CAUSE of switch DHCP failure = native-VLAN-1 coupler bridge (v9 M2 gap) — 10:00Z

Symptom (engineer): coupled works fine until switches renew their lease — on 117 they don't get a new
IP, drop to 9/18. DHCP log shows the exact failure: every 117 switch does DISCOVER → OFFER → DISCOVER
again, **never REQUEST, never ACK** — handshake dies at OFFER, loops forever. (NOT renewal, it's the
initial DORA breaking at step 3.)

PROVEN cause: **coupler native VLAN = 0001 (VLAN 1)** — v9 M2 (native 999) was NOT applied (we did
cost-only today). Evidence: 117 B1 coupler e0-2 = `native 0001, allow 5,15`; **VLAN-1 FDB on B1 = 57
MACs learned via e0-2 (coupler)**, including 105's switch MACs (d0:2c/2e/34/38 = 105 range). So the two
trains' VLAN-1 (192.168.1.0/24, shared subnet) management segments are BRIDGED across the coupler via
the native-VLAN-1 trunk. Switch DHCP REQUEST broadcasts traverse native VLAN 1 → leak across coupler →
overlapping 192.168.1.0/24 → REQUEST/ACK disrupted → switches loop at OFFER → 9/18.

This is EXACTLY what v9 M2 prevents ("native 999 drains untagged traffic; VLAN 1 never crosses").
**The afternoon's cold-boot-coupled instability was NOT power/pool/OBN — it was the M2 gap.** Ruled out
along the way: rogue DHCP server (only 00:21:21:21 CCU answers), pool exhaustion (46/~70), OBN,
backbone-discovery, Stadler actions, cross-CCU leasing (105 sees no v8-145).

FIX = apply M2 (combined form, never native-alone): `configure interface e0-2 switchport mode trunk
native vlan 999 prune allow 5,15` on all coupler ports. Prereq M3: `vlan 999 name blackhole-native`
must exist or native assign may reject. Persist (save running-config) so it survives the restart.

## M2 (native VLAN 999) APPLIED + PERSISTED — 10:00–10:20Z — switch DHCP FIXED

Applied v9 M2+M3 on all 8 coupler ports both trains: created `vlan 999 name blackhole-native`, set
coupler e0-2 to `switchport mode trunk native vlan 999 prune allow 5,15` (combined form — never native
alone), saved. All 8 verified in startup-config with BOTH cost=20000 AND native=vlan 999.

**Proof the fix works:**
- Applying native-999 to the active coupler (117 B1) live: VLAN-1 leak FDB dropped **57 → 39 → 10**
  (105's MACs aged out — the cross-train VLAN-1 bridge closed).
- dhcpd restart on 117 → switches began completing **DHCPREQUEST → DHCPACK** (was DISCOVER→OFFER→loop).
- **Decoupling → 117 recovered 9 → 18/18 within ~1 min**, confirming the native-VLAN-1 bridge was the
  cause of the switch DHCP failure. (A1/B3 on 117 were the last ports on vlan 1; couldn't reach them
  while coupled due to the very churn they caused — got them post-decouple, now all 4 = 999.)

**v9 now COMPLETE + persisted (M1 cost 20000 + M2 native 999, both trains).** Ready for the cold-boot
coupled test with the FULL fix — expect clean convergence AND switches holding 18/18 coupled (the M2
gap that broke DHCP all afternoon is closed). M4 max-age still deferred to git MR.

## COLD-BOOT COUPLED w/ FULL v9 (M1+M2 persisted) — 10:25–10:35Z

Restarted both trains coupled with cost 20000 + native 999 persisted in startup-config.

**RESULT — v9 works; 117 has a SEPARATE switch-power problem:**
- **105: 18/18 coupled, clean** ✅ — full convergence on cold boot.
- **117: only 9/18 switches ELECTRICALLY PRESENT (ARP=9, not just leased)** — stuck at 9 over 90s.
  The 9 absent (A1,B2,B3,C1,D1,E2,E3,F2,F3) are the SAME ~9 missing all day — scattered across all
  coaches (not one coach = not a segment power loss). These switches aren't coming onto vlan100 at all.
- **v9 config SURVIVED boot + works:** B1 = native 999 + cost 20000 from startup; VLAN-1 leak FDB ~19
  (NOT 57) — native-VLAN-1 bridge GONE; the 9 present switches lease fine. So the earlier
  DHCP-break-on-coupling bug is FIXED.

**Conclusion:** the v9 fix (M1 cost + M2 native-999) is validated — survives cold boot, no churn, no
VLAN-1 leak, switches that boot lease cleanly (105 = full 18/18 proof). 117's 9-missing-switches is a
SEPARATE persistent hardware/power issue (same 9 fail repeatedly, not on wire) — needs physical/
electrical investigation on 117, independent of coupling. NOT a v9 problem.

## VLAN-5 DGW ROLLED BACK on 105 — 10:50Z (decision: AR)

Reverted 105's `video` group default-router from master FW (172.18.200.129) → back to own FW
(172.18.194.129) on all 18 switches, saved + verified in startup-config 18/18, cameras bounced to apply.
**Single-FW VLAN-5 routing is NOT kept** (the cost fix alone resolved CCTV latency earlier; single-FW
was confirmatory and not needed). Reason: keep the changeset minimal / cameras on their own FW.

**KEPT + persistent (unchanged):** coupler cost 20000 + native VLAN 999 on all 8 coupler ports both
trains (the v9 M1+M2 fix — validated, in startup-config).

Final persisted state for the field: v9 M1 (cost 20000) + M2 (native 999), both trains. VLAN-5 DGW back
to per-train own FW. Outstanding: 117 ~9 switches DISCOVER→OFFER→loop (won't REQUEST) while coupled,
acquire on decouple — Nomad-side management-visibility issue, NOT service-affecting for Stadler,
separate investigation (switch-side DHCP client reject cause; couldn't inspect — looping switches have
no stable IP to SSH to).

## ccu20230725 flooder GONE — was a red herring for the 9-switch loop (10:57Z)

The `ccu20230725` device (MAC 7c:70:bc:70:d9:58/59) — the DHCP-Discover flooder from the engineer's
Wireshark (stuck TXID 0x8f865dd0, thousands/sec) — has DISCONNECTED. Now 0 entries in either lease
list (was 2 on 117), 0 frames in 5s, no flood (23 DHCP frames/6s = normal background). Nenad's laptop
(S23-von-Nenad) also gone. New device V2208 (192.168.208.10) appeared on 117 — unrelated.

**KEY: 117 STILL stuck at 9/9 switches with the flooder gone + domain quiet.** So ccu20230725's flood
was NOT the cause of the persistent 9-switch DISCOVER→OFFER→loop — it was a transient test-device
misbehaviour during the restart window. The 9-switch loop is its own issue (not native-VLAN-1, not
pool, not 2nd server, not flood) → points to switch-side DHCP client reject or 117 fabric/forwarding
for those positions. Couldn't inspect (looping switches have no stable IP to SSH). Nomad-side
management-visibility, not Stadler-blocking.

## 105 HMI CCTV lost after mass camera-bounce → RESTART fixed it (11:10–11:30Z)

After the VLAN-5 DGW rollback, the mass bounce of all 18 switches' camera ports (to apply the reverted
gateway) **disrupted the Stadler FW session/routing state** (camera VLAN5 → display VLAN3). Result:
105 HMI showed NO CCTV, even though L2 was provably healthy (cameras streaming 5-7 Mbps, gateway
correctly 172.18.194.129 own FW, FW MAC learned on VLAN5, A3 e1-4 FW trunk up).

Escalation that worked: port-level FW-trunk bounce (A3 e1-4) did NOT recover it → **full 105 restart
DID.** Cold boot of cameras + FW + HMI rebuilt clean sessions → HMI CCTV restored. 105 booted back with
correct persisted config (cameras→own FW, cost 20000, native 999).

**LESSON:** bouncing ALL VLAN-5 camera ports simultaneously badly disrupts Stadler FW session state —
worse than expected, not recoverable by a port bounce, needed a full restart. Future: stagger camera
bounces, or expect/plan FW churn + a restart. The FW inter-VLAN (5→3) session handling is Stadler-side
(consistent with A8 domain).

## Max-age / forward-delay (v9 M4) — DEFERRED 2026-06-30 (decision: AR)

NOT applied today — **cost-only test** to keep one variable / one clean proof (does churn freeze).
Max-age only bites at coupled diameter (~20-hop horizon), so it has no pre-staging urgency like cost
did, and it belongs in the git MR as a shared STP include (v9 S1) so all switches stay identical.

When it IS applied (MR or a later session): **scope = ALL 18 switches per train** (bridge-wide timers
must be identical across the whole RSTP domain — never just cab switches). **Order is mandatory**
(firmware enforces `2×(fwd_delay−1) ≥ max_age`):
```
configure spanning-tree forward-delay 20     # first → 2×19 = 38
configure spanning-tree max-age 38           # then → 38 ≥ 38 passes (rejected at default fwd-delay 15)
```

## Revert recipe (per port)

- 117 A1, B3: `configure interface e0-2 spanning-tree port-cost 144999999`
- 105 A1, B3: `configure interface e0-2 spanning-tree port-cost 132999999`
- A3, B1 (both trains): `no configure interface e0-2 spanning-tree port-cost` (restore default / remove)
- Or: power-cycle / `obn update c` from v8 reverts all.
