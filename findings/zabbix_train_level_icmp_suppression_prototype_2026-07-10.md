# Zabbix train-level ICMP alarm suppression — prototype on 50_6047 (2026-07-10)

**Status: PROTOTYPE LIVE on one train (4736-102 / Fzg 130 / box1-t47 / Zabbix group `50_6047`).**
Pending: observation through ≥2 real power cycles, then Zabbix-owner review before any fleet rollout.
Owner: Abbas Rizvi. All objects are host-level — **no template was edited; zero impact on other trains/projects.**

## Problem

Every train power event floods the service desk with per-device High ICMP alarms that later
self-clear, so the desk cannot tell a real fault from a transient. Two mechanisms, both
ground-truthed live on 2026-07-10:

1. **Post-power-on convergence flood** (traced end-to-end on 6047): train boots → DHCP
   reshuffles switch/AP IPs (dynamic pools by design) → Zabbix pings yesterday's IPs →
   13–18 High alarms → OBN→MQTT→NMS→Zabbix IP re-sync lands → proxy config sync (300 s) →
   alarms auto-clear. Duration that morning: **~95 min** (03:02→04:37 UTC). The proxy and
   server were both healthy; the lag is in the central NMS re-sync.
2. **Parked-train / ignition-wake flood** (traced on 6024): CCU wakes briefly on ignition
   while the consist switches are unpowered → pings fail → 18 alarms fire and then freeze
   open (proxy off) for the whole parked period (median 24 h on 6024) → clear minutes after
   the next real boot.

**30-day fleet measurement (project 50, all `50_*` groups, 7,085 resolved "unavailable by
ICMP" events):** p50=10 m, p75=76 m, p90=15.2 h; 69 % clear <30 min (mechanism 1), ~20 %
last 2 h–24 h+ (mechanism 2). Weekly trend flat → not a regression, a structural property.
Volume ≈ **7,200 switch ICMP alarms/month**, almost all false. Analysis script:
`scratchpad zbx_icmp_convergence_rerun.py` (session 2026-07-10); June baseline in memory
`project_zabbix_switch_icmp_dhcp_drift`.

Correlated multi-device ICMP failure is never device-actionable (it is power state or the
IP-sync pipeline). Only a *single* device failing on an otherwise-reachable train is a real
fault. The design encodes exactly that distinction.

## Design

Per train, all on the CCU host (`50_60XX_MAR3-B1`), no template objects touched:

| Object | Detail |
|---|---|
| Host tags | `role:sw` / `role:ap` on the 42 device hosts (needed for the foreach filters) |
| Item `train.icmp.up.sw` | calculated, 60 s: `sum(last_foreach(/*/icmpping[,5]?[group="50_6047" and tag="role:sw"]))` → 0–18 |
| Item `train.icmp.up.ap` | calculated, 60 s: same with `role:ap` → 0–24 (23 on 6047: R5_AP2 genuinely missing since 21/05) |
| Master trigger | "Train 6047: fabric mass-unreachable (power-off or post-boot IP convergence) — device ICMP alarms suppressed", severity Average. Problem: `max(sw,5m)<=12 or max(ap,5m)<=16`. Recovery: `min(sw,5m)>=16 and min(ap,5m)>=20` (hysteresis so partial convergence cannot un-suppress mid-window). |
| Dependencies | each of the 42 device ICMP triggers (18 SW "unavailable by ICMP", 24 AP "cannot be pinged") depends on the master → Zabbix auto-suppresses them while the master is in problem |

**Deliberately NOT suppressed:** the CCU host's own ICMP trigger — it is the genuine
"train offline" signal and must always fire.

**Race math:** device ICMP triggers use a 15 m window; the master fires after ~5 m of
collapse (+~1–2 min value-cache warm-up after proxy start), so the master always wins.
A proxy restart on a healthy train cannot false-fire it: `max()` over the window sees the
first good sample.

**Coupling:** Zabbix groups are per-train and static; coupling two consists does not change
group membership, so the counts and thresholds are unaffected.

## Created object IDs (6047)

- items: `train.icmp.up.sw` = **1107590**, `train.icmp.up.ap` = **1107591** (host `50_6047_MAR3-B1`, hostid via group 50_6047)
- master trigger: **341831**
- dependencies: on the 42 device ICMP trigger instances (per-host rows; template trigger 44453 untouched)
- host tags `role:sw|ap` on 42 hosts

Verified after creation: items steady at sw=18 / ap=23; master state OK, no error; 42/42
dependencies present.

## What the service desk sees after this

- Parked train or booting train: **one** Average alarm on the train, clearly worded, instead
  of 13–42 Highs.
- A single dead switch/AP on a running train: still an individual High alarm — now
  trustworthy ("if it alarms alone, it's real").

## Verification plan (before proposing rollout)

1. Watch 6047 through ≥2 real power cycles (auto: the master trigger's event history vs the
   device triggers' — expect master fires ~5–7 min post-wake, zero device ICMP events while
   it is active, master clears after convergence).
2. Confirm no device ICMP alarm leaks during a convergence window, and that a genuinely-dead
   device (R5_AP2 is a permanent natural test case — its trigger must stay OPEN/able to fire
   when the master is OK) still alarms.
3. Then: Zabbix-owner review; fleet rollout is a ~50-train scripted repeat (tags, 2 items,
   1 trigger, deps). Exclude bench groups (already de-alarmed).

## Rollback (complete, order matters)

```
1. trigger.update on each of the 42 device triggers: remove dep on 341831
2. trigger.delete 341831
3. item.delete 1107590, 1107591
4. (optional) remove role tags from the 42 hosts
```

## Known limitations / open items

- **Durability:** an NMS re-provisioning of the train's Zabbix hosts may wipe host-level
  items/tags/deps → prototype silently disappears (fails safe: alarms revert to today's
  behaviour). Check after any re-provision.
- **AP-only drift floods** are covered by the `ap` count arm; SW-only by the `sw` arm; a
  *mixed* partial flood below both thresholds (e.g. 5 SW + 7 AP stale) would not suppress —
  acceptable, rare.
- This masks the symptom. The root fixes remain with R&D: trigger the NMS→Zabbix IP re-sync
  promptly on power-up (OBN has correct IPs within minutes) and/or DHCP reservations
  (`networks.epp` has none, fleet-wide by design).
- The shared base template "Template ICMP Ping Congested Switch" is linked by Oring/MEN/Enzo
  fleets — that is WHY the design avoids template edits entirely.
