# 2-second power-logger rollout — 2026-07-24

Purpose: capture pre-cut CMM voltage (Vin/Vign + rails + temp) at 2 s resolution to
diagnose the "randomly offline / CCU dying" outages on 4736 trains. Canonical source
= 4736-110's verified running copy. Files staged in `_canonical_deploy/`.

Logger = `vign_poll.sh` (INTERVAL=2, HB=2) on `/data/ignition-log/`, units in
`/etc/systemd/system` (installed via btrfs `ro-toggle`: `btrfs property set -ts / ro false`
→ write units + `systemctl enable` → `ro true`). Enable MUST happen while `/` is writable
(the `.wants` symlink is under `/etc`).

| Train | Fzg | CCU IP | Status |
|---|---|---|---|
| 4736-110 | 138 | 10.179.23.1 | ✅ DONE (original; bumped 30s→2s this session). Backup: `vign_poll.sh.bak_pre_2s_20260724` |
| 4736-105 | 133 | 10.179.1.1 | ✅ DONE 2026-07-24 08:51Z — 3 units active+enabled, 2s cadence verified |
| 4736-119 | 147 | 10.179.12.1 | ✅ DONE 2026-07-24 08:51Z — 3 units active+enabled, 2s cadence verified |
| 4736-103 | 131 | 10.179.11.1 | ⏳ BLOCKED — CCU SSH timed out (offline/stale IP). Retry when online. |
| 4736-120 | 148 | 10.179.2.1 | ⏳ BLOCKED — CCU SSH timed out (offline/stale IP). Retry when online. |

## Recipe to finish 103 / 120 when reachable
1. `scp` the 3 scripts from `_canonical_deploy/` to CCU `/tmp/` (NOT /var/tmp — not
   developer-writable on these CCUs; /tmp is).
2. Run the install heredoc as `sudo bash -s` (see session transcript / this dir): install
   scripts to /data/ignition-log, ro-toggle, write 4 unit files, **enable while writable**,
   ro-close, start, verify.
3. Verify: 2s cadence (`tail` twice), real CMM Vin/Vign, all 3 units active+enabled.

## Persistent journald rollout (2026-07-24, added same day)

Separate instrument for the **hang / "on-but-unreachable"** failure mode (distinct from the
power-cut mode). Discovered on 4736-106: CCU was up but unreachable, cleared by a manual reboot
at ~10:30 CEST; no pstore panic, /data written continuously = software/USB/network hang, NOT a
power cut. Root cause unprovable because the kernel journal is volatile (`/var/log` is a 300 MB
**tmpfs** → wiped on reboot). Fix = point journald at /data so the NEXT hang's logs survive.

Mechanism: bind-mount `/data/persistent-journal` over `/var/log/journal` (unit
`var-log-journal.mount`, ordered `Before=systemd-journald`), `Storage=persistent`,
`SystemMaxUse=500M`. Installed via ro-toggle; journald.conf backed up to
`journald.conf.bak_2026-07-24`. A plain `Storage=persistent` alone does NOT work here because
/var/log is tmpfs — the bind mount to /data is the load-bearing part.

| Train | CCU | Persistent journal |
|---|---|---|
| 4736-106 | 10.179.19.1 | ✅ DONE 2026-07-24 (origin of finding). Baseline: `106_baseline_2026-07-24.txt` |
| 4736-110 | 10.179.23.1 | ✅ DONE 2026-07-24 |
| 4736-105 | 10.179.1.1 | ✅ DONE 2026-07-24 |
| 4736-119 | 10.179.12.1 | ✅ DONE 2026-07-24 |
| 4736-103 | 10.179.11.1 | ⏳ pending — CCU offline |
| 4736-120 | 10.179.2.1 | ⏳ pending — CCU offline |

Setup script: `/tmp/setup_persistent_journal.sh` (this session) — idempotent, skips if bind
mount already present. Re-run on 103/120 when reachable, and re-run after any Puppet/NDSU
promote (the /etc mount unit + journald.conf revert on snapshot roll; /data dir persists).

## 5h scheduled-reboot cron rollout (2026-07-24) — Stadler availability stopgap

Stadler asked for an auto-reboot every 5h to improve availability. Implemented **marker-safe**
so it does NOT corrupt the outage diagnostics: `/data/ignition-log/scheduled_reboot.sh` writes
`<iso> SCHEDULED_REBOOT_5H uptime_s=<n> host=<h>` to the SAME `/data/ignition-log/shutdown.log`
the vign shutdown-marker uses → power-log analysis classifies these as COMMANDED, not hard-cut.
Also `logger -t nd-scheduled-reboot` to the (now persistent) journal, then `systemctl reboot`.

Units: `nd-scheduled-reboot.service` (oneshot) + `nd-scheduled-reboot.timer`
(**OnActiveSec=5h**, NOT OnBootSec — OnBootSec would insta-fire on any CCU already >5h uptime
when armed; OnActiveSec gives a full 5h from arm/boot uniformly). Installed via ro-toggle,
enabled to persist.

| Train | CCU | Scheduled reboot | Next fire (armed 2026-07-24 ~09:07Z) |
|---|---|---|---|
| 4736-106 | 10.179.19.1 | ✅ DONE | 14:07 UTC |
| 4736-110 | 10.179.23.1 | ✅ DONE | 14:07 UTC |
| 4736-105 | 10.179.1.1 | ✅ DONE | 14:07 UTC |
| 4736-119 | 10.179.12.1 | ✅ DONE | 14:07 UTC |
| 4736-103 | 10.179.11.1 | ⏳ offline | — |
| 4736-120 | 10.179.2.1 | ⏳ offline | — |

Setup script: `/tmp/setup_scheduled_reboot.sh` (this session). Re-run on 103/120 when online,
and after any Puppet/NDSU promote (units revert on snapshot roll; /data script persists).

⚠️ **Interaction with the 2s power logger:** on 110/105/119 the scheduled reboot fires every 5h,
so the vign.csv will show a SCHEDULED_REBOOT_5H commanded gap every 5h. This is fine for the
power analysis (tagged commanded) but it caps continuous-uptime capture at 5h — so an abrupt
hard-cut can only ever be caught within a <5h window. Acceptable tradeoff per Stadler's request;
revisit if we need a longer uninterrupted capture on any one train.

## First log review — 2026-07-25 (box1-t19 / 4736-106 only reachable)

Only **4736-106 (10.179.19.1)** was reachable at review time; 110/105/119/103/120 all SSH-timed-out
(offline / stale cellular IP). Findings from 106's now-persistent journal + shutdown.log:

**Instruments (106):** persistent journal ✅ working (bind mount on `/var/log/journal` intact, journal
now spans 6 boots back to the 2026-07-24 08:33 rollout — pre-persistence these would have been wiped);
5h scheduled-reboot ✅ working (marker present, tagged commanded). NB **no 2s power logger on 106** —
expected, 106 was never in the vign table (persistent-journal + scheduled-reboot only).

**Reboot reconciliation since rollout — the instrument earned its keep.** 6 boots, but only **1** carried
a `SCHEDULED_REBOOT_5H` marker. Classifying each by shutdown-sequence presence + empty `/sys/fs/pstore`:

| Boot ended (UTC) | shutdown markers | pstore panic | verdict |
|---|---|---|---|
| Fri 07-24 12:11 | 1 | — | orderly reboot |
| **Fri 07-24 12:18** | **0** | none | 🔴 **abrupt power cut** |
| (12:18 → 00:30 gap) | — | — | overnight ignition-off (train parked; normal) |
| Sat 07-25 03:00 | 9 | — | orderly reboot |
| Sat 07-25 08:00 | 9 | — | ✅ the tagged 5h SCHEDULED_REBOOT |
| **Sat 07-25 08:51** | **0** | none | 🔴 **abrupt power cut** |

**Two abrupt-power-loss events captured on 106** (Fri 12:18, Sat 08:51): journal stops dead mid-normal
activity (DHCP ACKs flowing) with NO shutdown sequence, `/sys/fs/pstore` empty (no kernel panic/oops),
and no scheduled marker. Signature = hard supply cut, **not** a software hang and **not** commanded.
⚠️ This nuances the DRAFT_email framing of 106 as the "on-but-unreachable hang" mode: the *original*
finding (manual reboot ~10:30 CEST 07-24 cleared an up-but-unreachable CCU) still stands, but 106 is
now *also* showing the same hard-cut mode seen on 110/105 — i.e. 106 has **both** modes. Re-review 110/105/119
the same way once reachable, and correlate the two 106 cut timestamps against Stadler's vehicle
power/ignition log before sending the email.

**Non-anomalies (benign, seen every boot — do NOT escalate):** `ntpd` socket/leapsecond config noise;
`dhcpd Abandoning 10.179.19.17x pinged before offer` (known ping-check cascade); zabbix `netstat`
sudo-denied; i915 `tgl_dmc` firmware -2; TPM interrupt polling; `nd-auto-system-update` EXEC-not-found
(`.dont` rename in place — expected). One kernel `WARNING at net/sched/cls_u32.c:854 u32_change`
(boot 0, 08:56:56) — benign one-shot WARN from a `tc` filter add via rtnetlink; kernel continued, did
not cause the reboot. Not the outage cause.

## netdrop logger (tunnel/VPN-drop evidence) rollout — 2026-07-25

Purpose: capture the CAUSE of NON-power VPN drops (carrier IP re-addressing / coverage / reboot),
the gap the power logger can't fill. Records per-modem IP + carrier state + RDS-flow-present +
ModemManager access-tech every 5s + on change → `/data/netdrop-log/netdrop.csv`. Root-cause context:
`ANALYSIS_nonpower_vpn_drops_2026-07-25.md`. Files: `netdrop_logger/`. RDS_HOST=62.2.130.53 (fleet-wide).

| Train | CCU | netdrop logger |
|---|---|---|
| 4736-110 | 10.179.23.1 | ✅ DONE 2026-07-25 (origin; upgraded w/ per-modem IP capture) |
| 4736-105 | 10.179.1.1  | ✅ DONE 2026-07-25 12:14Z — active+enabled, per-modem IP rows verified |
| 4736-106 | 10.179.19.1 | ✅ DONE 2026-07-25 12:14Z — active+enabled, per-modem IP rows verified |
| 4736-119 | 10.179.12.1 | ⏳ offline — retry when reachable |
| 4736-103 | 10.179.11.1 | ⏳ offline — retry when reachable |
| 4736-120 | 10.179.2.1  | ⏳ offline — retry when reachable |

Install recipe (per train, from `netdrop_logger/`): scp `netdrop_poll.sh`+`netdrop-poll.service` to
`/tmp`; `sudo`: install script to `/data/netdrop-log/`, `btrfs property set -ts / ro false`, install
unit, `systemctl enable` (while writable), `ro true`, `systemctl start`, verify. Reverts on Puppet/NDSU
snapshot roll (unit in /etc); /data script persists — re-run install after any promote.

**Plan (2026-07-25):** let 110/105/106 log over the weekend; check logs Monday. Ask Hartmann for a
FRESH VPN connectivity-state report covering **only** the logged trains for the same window, so we can
correlate ÖBB's session drops against our per-drop cause data (this time the windows WILL overlap).

## Notes / caveats
- **File growth:** 2s continuous ≈ 15× the 30s rate → 50 MB self-cap reached in ~2–3 weeks
  (was ~9 months). PULL LOGS within ~2 weeks or revert to 30s after capturing 2–3 cuts.
- `vign-shutdown-marker.service` shows `active=inactive` until `systemctl start`ed (oneshot
  + RemainAfterExit); it's enabled and fires ExecStop at shutdown regardless. Start it to arm
  the RemainAfterExit breadcrumb so state matches 110.
- Persistence: scripts on /data survive reboot; /etc units survive reboot but a Puppet/NDSU
  snapshot roll would revert them (scripts on /data stay). Re-run install after any promote.
- `i2ctransfer` not in developer PATH on these CCUs — fine, service runs as root (sudo
  secure_path has /usr/sbin) and script calls it bare.

## 2026-07-26 — DURABLE fleet bake of the full logger + alarm stack (NDSU .dont chroot)

**Change of persistence model:** the earlier rollouts were RUNTIME (btrfs ro-toggle) — they revert on the
next NDSU/Puppet promote. Made them **durable** by baking the whole stack into a promoted snapshot via
`nd-systemupdate.sh.dont shell` (chroot of a fresh snapshot cloned from `release`; on clean `exit` it
promotes to release+run and becomes default-boot). Because NDSU is renamed `.dont` fleet-wide, Puppet never
runs, so the baked `/etc/systemd` units + `/etc/zabbix/*.conf.d` are not purged. **Survives reboot + NDSU.**

**Recipe** (all in scratchpad `logger_deploy/`, canonical source in this dir):
- `bake_in_chroot.sh` — lays down scripts to /data (shared subvol) + units/confs/check-scripts into the
  snapshot /etc + /usr/local, enables the 4 units (multi-user.target.wants symlinks). NO ro-toggle, no
  service start (chroot context). NB `vign_poll.sh` here is the 10s-cadence awk-fixed version (NOT 2s — do
  not reintroduce the 2s CMM-wedge).
- `durable_bake_driver.sh` — stages payload in `/tmp/logger_payload` (developer-writable; `/var/tmp` is NOT,
  but both /tmp and /var/tmp are bind-mounted into the chroot per DIR_TO_MOUNT). Pipes the in-chroot commands
  via **STDIN heredoc** into `nd-systemupdate.sh.dont shell` (interactive paste no-ops). Copies payload to
  `/root/logger_payload` inside the chroot first (var/tmp is wiped in the promoted snapshot). Runs detached
  (setsid) so a cellular blip can't interrupt the promote.
- Verify: booted subvol = new run$i; all 7 files present in `/.snapshots/release`; 4/4 wants symlinks;
  units active+enabled post-reboot; check_netdrop/check_hardcut answer; a CLEAN reboot writes a
  GRACEFUL_SHUTDOWN marker so the classifier does NOT false-count it (verified on t8: total stayed 0).

**Baked + rebooted + verified durable (7 CCUs), 2026-07-26 ~19:30Z:**
| Train | box | boot subvol | vign | netdrop | check_nd | check_hc |
|---|---|---|---|---|---|---|
| 4736-108 | t8  | run1 | active/enabled | active/enabled | 0 | 0 |
| 4736-118 | t21 | run2 | active/enabled | active/enabled | 0 | 0 |
| 4736-111 | t24 | run2 | active/enabled | active/enabled | 0 | 0 |
| 4736-107 | t25 | run1 | active/enabled | active/enabled | 0 | 0 |
| 4736-109 | t28 | run1 | active/enabled | active/enabled | 0 | 0 |
| 4736-102 | t47 | run2 | active/enabled | active/enabled | 0 | 0 |
| 4734-112 | t37 | run2 | active/enabled | active/enabled | 0 | 0 |

- **t24 boot race (one-off):** vign-logger did not auto-start on the first baked boot (unit enabled+present,
  CMM responsive — not a wedge). `systemctl start` fixed it; it's enabled so should come up next boot.
  Robustness gap in the unit ordering (no retry catches a no-show at boot) — worth an `ExecStartPre` wait or
  a .timer trigger if it recurs. Did NOT happen on the other 6.
- **t37 (4734-112, nv4):** runtime-installed THEN baked (was bare). Zabbix items/triggers created on
  **`6_37_MAR3-B1`** (id 14095) — NB the 4734 series is monitored under `6_NN`/`48_NN` hosts, NOT the
  `50_6NNN` naming the 4736 alarm trains use. ⚠️ Confirm that's the right host for NMS surfacing.

**NOT baked / deferred:**
- **t124 (10.179.124.1):** NO `.dont` rename (plain `nd-systemupdate.sh`), puppet disabled+inactive,
  train_id empty (uncommissioned/bench-adjacent). Bake would not be guaranteed durable (NDSU auto path not
  frozen). Left alone — decide later.
- **~46 CCUs offline** at rollout time. The durable bake is a per-CCU manual op (same model as OBN patches /
  vlan7 fixes) — run `durable_bake_driver.sh` on each as it comes online. TRUE fleet-wide auto-propagation
  (incl. future-imaged trains) still requires Puppet + Zabbix-template, which is the DevOps-owned durable
  path and was NOT done here (prod-infra boundary).

**Zabbix alarm coverage now (items+triggers, both netdrop + hardcut):** 105, 102, 107, 109, 111, 118, 104,
108 (all 50_6*), + 4734-112 on 6_37. netdrop trigger = `last(check_netdrop_stadler)<>0` (sev Avg); hardcut
trigger = `change(check_hardcut_total)>0` (sev Avg).
