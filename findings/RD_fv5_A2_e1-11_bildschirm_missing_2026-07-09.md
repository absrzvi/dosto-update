# fv5 template: A2 e1-11 "Bildschirm Werbung A4" missing — fleet-wide dead advertising display

**Date:** 2026-07-09
**Train reported:** 4705-103 (Fzg 231, box1-t41, CCU 10.179.41.1)
**Scope:** ALL 4705 (fv5) trains — template bug, not train drift
**Status:** ✅ Fixed + DEPLOYED to Puppet master 2026-07-09. `nomad-obn-template-fv5` @ `c734ff5` (v0.0.20, pushed), deb registered+promoted to bookworm **main** on vmrepo01, hieradata pin 0.0.20 (`3f2ef41`), master env `dostoneu_migration_mar5` updated+verified. Remaining: per-train `puppet agent -t` (or factory up) + `obn update c` A2 when each 4705 is online. (An e2-5 enable was briefly committed then dropped in the history cleanup — see e2-5 section.)

## Field report (origin)

Technician (Fabian Hasselmann, Stadler) reported: "Car A switch A2 port 1-11 seems to be wrong — the screen on this port is always showing ÖBB." Accompanying laptop screenshot (172.25.112.215/255.255.255.255, GW 0.0.0.0) was retracted — wrong adapter; the correct adapter showed "not connected".

## Diagnosis

1. **Live switch** (fv5-A2-v8-231 @ 10.179.41.184, 2026-07-09): `interface e1-11` = bare `no enable`, access on default VLAN 1, zero lifetime RX/TX. All other A2 ports match the IPA exactly.
2. **IPA PDF** (`4705-103_IP-Port-Allocation.pdf`): A2 `e1-11` = **Bildschirm Werbung A4, VLAN 3 (pis), 172.17.243.228, IPID 100**.
3. **Template repo** (`nomad-obn-template-fv5` v0.0.19, `fv5-100-A2.cfg`): stanza is `no enable` — the device was never in the template. `172.17.x.228`/IPID 100 appears nowhere in the template set (device not relocated — simply missing).

Live == template ⇒ the OBN push worked correctly; the **template** was wrong. Every fv5 train has a dead "Bildschirm Werbung A4" advertising display in car A. The "always ÖBB" screen the technician saw is a *different, healthy* VLAN-3 display nearby; the laptop's "not connected" is exactly what a `no enable` port produces.

## Full audit (all 15 switches, 420 ports)

Rendered all 15 templates locally (`train_id=231`) and diffed against the parsed IPA PDF — see
[`fv5_231_rendered_v0.0.19/IPA_vs_template_fullmap.md`](fv5_231_rendered_v0.0.19/IPA_vs_template_fullmap.md).

- ✅ 376 ports match (377 after fix)
- 🟡 37 benign (future-use boxes disabled; label drift: C1/F1 e1-11 desc "Bildschirm C7/F7" vs IPA "C5/F5", B1 e1-12/13 "Funksensor E5/E6" vs "B5/B6")
- 🟠 4 intentional deviations: coupler trunks A1/A3/B1/B3 e0-2 = v9 containment (native-999, allow 5,15, cost 20000) — load-bearing, do NOT "correct" to the IPA list
- ❌ **A2 e1-11 (this finding)** — fixed v0.0.20. Post-fix audit: 377/420 match, 0 faults, 4 intentional coupler deviations.

### e2-5 "Service VLAN PWLAN" — NOT a fault (resolved 2026-07-09)

A3/B3 `e2-5` is `no enable` in the template while the IPA lists it as a trunk (100,10,20,30,31,131,150). Briefly enabled in `ea23549` (v0.0.21), then **reverted** (`447a323`) after cross-checking nv6: the nv6 templates carry the **identical stanza with `no enable`**, and the live, fully-commissioned nv6 train Fzg 138 (box1-t23, checked 2026-07-09) has both e2-5 ports disabled/down. Disabled-until-needed is the fleet convention — an always-on socket carrying passenger client VLANs 10/20/30 in an accessible location would be a security hole. The IPA describes physical allocation, not operational policy (same as the coupler VLAN list).

## Fix

`nomad-obn-template-fv5` commit `c734ff5`, v0.0.20 — added to `fv5-100-A2.cfg`:

```
interface e1-11
  description "Bildschirm Werbung A4"
  switchport mode access vlan 3
  dhcp-server client-group fis
  {%- if train_id % 2 == 0 %}
  dhcp-server client-address 172.17.{{ 128 + (train_id // 2) }}.100
  {%- else %}
  dhcp-server client-address 172.17.{{ 128 + ((train_id - 1) // 2) }}.228
  {%- endif %}
  spanning-tree edge on
  enable
```

Render-verified both branches: odd 231 → `172.17.243.228` (= IPA), even 230 → `172.17.243.100` (host = IPID for even, IPID+128 for odd — consistent with all sibling stanzas).

## Pipeline log (2026-07-09, all done)

1. ✅ Pushed `c734ff5` + `777b241` (README changelog) to git-nc.
2. ✅ Built deb in WSL via dpkg-deb fallback (132 MB), verified e1-11 stanza inside.
3. ✅ vmrepo01: registered to unstable, **promoted to main** (fleet consumes main — 0.0.19 precedent), repo signed, `Version: 0.0.20` verified in main Packages index. NOTE: `-promote` takes the bare deb filename, not a /tmp path.
4. ✅ `env-dostoneu-mar5` hieradata/pipeline/dostoneu-fv5.yaml: `obn::template_pkg_ensure: "0.0.20"` (`3f2ef41`), pushed.
5. ✅ vmpuppet01: `nd-update-puppetenv.sh migration_mar5` — env HEAD verified `3f2ef41`, pin verified 0.0.20.
6. ✅ SUPERSEDED same day by **0.0.21** (`f1d1406`): SW firmware reverted 7.4.8 → 7.4.2 (7.4.8/NMID1143 not approved; the 0.0.18 bump was premature). fv6 likewise reverted (0.0.19, `5c15845`). Both rebuilt, promoted to main, pins `3b14f2e`, master redeployed+verified. e1-11 fix and rules.yaml coach fix retained (⚠️ the rules.yaml coach-refs fix postdates the fw bump — a naive `git revert` of 0.0.18 would resurrect the shift bug; firmware lines were edited surgically instead).

## On-train verification — 4705-103 (2026-07-09 PM, post NDSU up)

- Template pkg 0.0.21 confirmed installed by the NDSU up; Form-1 hardcode was wiped by the pkg upgrade (expected) and re-added to all 15 cfgs via btrfs ro-toggle. TFTP CT helper re-armed (runtime fix, wiped by reboot).
- `obn discover` + `obn report`: 15/15 switches, coach numbering correct (0.0.19 rules fix working), **all fw 7.4.2 — no 7.4.8 exposure on this train**, all configs `fv5-*-v8-231` ✓.
- `obn update c 10.179.41.180` (A2): applied, switch rebooted, e1-11 now `vlan 3 / fis / 172.17.243.228 / enabled` — verified in running-config post-reboot. Hostname stayed `fv5-A2-v8-231`.
- e1-11 link is DOWN: no powered device currently on the socket. Field follow-up: power/connect the Bildschirm Werbung A4 display and confirm it links at 100/1000 and leases `172.17.243.228`.

## Remaining steps

0. **Firmware exposure check**: for each fv5/fv6 train touched between 2026-07-02 (0.0.18 deploy) and 2026-07-09 (revert), verify no switch was flashed to 7.4.8 (`show version` / OBN report firmware column). Bench box1-t122 runs 7.4.8 deliberately via its per-host template_pkg_ensure override — leave it.

1. ~~4705-103~~ DONE (above). Other 4705 trains when online: `puppet agent -t` pulls template 0.0.21, re-add Form-1, then `obn update c` A2 → `sudo obn discover && sudo obn report && sudo obn update c <A2-ip>` → verify e1-11 enabled + display gets 172.17.x.228/.100 lease.
2. 4705-103 specifically: pull all 15 live running-configs and diff vs `fv5_231_rendered_v0.0.19/` renders (closes the live==template loop; fetch script may still be staged at CCU `/tmp/fetch_all_cfgs.py`).
3. Cosmetic (optional, separate commit): C1/F1 e1-11 + B1 e1-12/13 description strings.

## Cross-refs

- `findings/RD_fv5_rules_template_shift_2026-07-07.md` — previous fv5 template bug (0.0.19)
- `findings/RD_fv5_coupler_hash_comment_config_reject_2026-07-07.md` — rendered coupler stanzas still contain `#` comment lines (VDS CLI rejects); visible in these renders too
- Memory: `project_fv5_topology_reference`, `project_vds_switch_rejects_hash_comments`
