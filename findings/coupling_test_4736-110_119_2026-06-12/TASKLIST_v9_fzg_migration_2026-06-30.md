# DOSTO v9 + Fzg-ID + 4734 Migration — Master Task List

**Date:** 2026-06-30 · **Author:** AR + Claude · **Status:** PLAN — staged work done locally; execution gated on SA-2444.
**Gate:** ⛔ **BLOCKED until [SA-2444](https://nomad-digital.atlassian.net/browse/SA-2444) closes** — *"OEBB Dosto NEU Migration complete — Gitlab Repo clean up and normalization"* (SysOps / Julia Frick, To Do).

## Why SA-2444 is the gate (the dependency, explained)

SA-2444 stands up the **mar5 backend HAs** and completes the MAR5 migration:
- **ID 50 (`10.178.x.x`) = 4734 4-car trains** — *still on mar3, must migrate to mar5* (3 HAs: vmmar5be34/35/+1 TBD).
- **ID 51 (`10.179.x.x`) = 6-car trains** — already on mar5 (vmmar5be31), being normalized to 3 HAs (be31/32/33).

Our **4734 box-id = Fzg** plan re-IPs the 4734s to `10.178.<Fzg>` — that target subnet/backend only exists once SA-2444 lands the ID-50 mar5 HAs. So **infra (SA-2444) → then config/migration (this list).** The 6-car `fzg_id` workstream is *less* gated (ID 51 backend already serving) and could start sooner.

Related R&D ticket: **[RD-12434](https://nomad-digital.atlassian.net/browse/RD-12434)** — upstream v8 hand-patches into OBN (adjacent; the OBN-patch + engine-key questions may fold here).

---

## Strategy decisions locked (2026-06-30)

| # | Decision |
|---|---|
| D1 | **UNIFY box-id = Fzg for ALL fleets** (4734 + 6-car). `train_id` becomes = Fzg everywhere → **NO fzg_id key, NO OBN engine change, NO Puppet fzg_id node lines.** One uniform model. (Superseded the earlier 4734-only fork.) |
| D2 | Feasibility verified fleet-wide: 4734 → 10.178.<Fzg> (1–90, empty subnet); 6-car → 10.179.<Fzg> (129–231, disjoint from current boxes 1–47 → no transient collision). No collisions anywhere. |
| D3 | v9 coupler correctness (M1–M4) + NTP-source fix ships for ALL fleets. Templates use `train_id` directly; `128+train_id` shadow deleted. |
| D4 | **No push to remote** until explicitly authorised. All staging is local. |
| D5 | GitLab commits match team style (Davud terse single-line), author **Abbas Rizvi <abbas.rizvi@nomadrail.com>**, NO Claude trailer. |
| D6 | **Cost accepted:** 4734 re-IP ~free (rides SA-2444); 6-car re-IP = net-new on 26 in-service trains, accepted to permanently kill fzg_id/engine complexity. |

---

## ✅ DONE (staged locally this session — not pushed)

- [x] **v9 + NTP fix committed** on `feature/v9-fzg-id` in ALL 4 fleets (Phase A): M1 flat coupler cost 20000, M2 native vlan 999, M3 vlan999 def, M4 forward-delay 20/max-age 38, NTP `train_id-128`→`train_id`. Validated (16 couplers, 4 vlans, 63 timers, 0 dead-NTP).
- [x] **Unified to box=Fzg (D1):** all fleets use `train_id` directly for hostnames+DHCP (0 fzg_id refs). `128+train_id` line-1 shadow DELETED in nv6/fv5/fv6 (commit "Drop 128+train_id remap"); nv4 never had it. (The earlier fzg_id-rename phase B was reverted on all repos.)
- [x] **Render-tested under box=Fzg:** nv6 Fzg137→nv6-A1-v8-137/NTP 10.179.137.1; nv4 Fzg20→v8-020/10.178.20.1; fv5 231; fv6 191 — all correct.
- [x] **Fleet list reconciled** in fleet-status.md: 50 trains, 8 CCU IPs filled, 4734-105 de-duped, phantom 4736-121/122/123 removed, 4706-101 corrected to 10.179.20.1.
- [x] **Fzg values cross-checked** against official `design freeze/Fzg-Nr-ID Aufteilung-v1.xlsx` — 50/50 match.
- [x] ~~fzg_id Puppet line list~~ — **obsolete** under box=Fzg (no fzg_id key needed). Kept only as a Train#↔Fzg reference.

---

## ⛔ BLOCKED ON SA-2444 — execution tasks (do NOT start until it closes)

### Workstream A — OBN engine ✅ NO CHANGE NEEDED
- [x] **Engine change eliminated by D1 (box=Fzg).** Since `train_id` = Fzg, no fzg_id injection, no `onboard/obn` touch, no R&D blocker. The render-transport constraint is moot. *(This is the big win of unifying.)*

### Workstream B — Template repos (push + MR)
- [ ] **T-TPL-1** — Re-base `feature/v9-coupler-boxfzg` branches on latest `origin/master`; re-run validation greps + Jinja render-test. *(Branch already renamed from feature/v9-fzg-id, 2026-06-30.)*
- [ ] **T-TPL-2** — `version` bump + README line per repo (`v9 - symmetric coupler cost + native-999 + max-age 38 (2x6); box-id=Fzg (drop 128+ remap)`). Davud style.
- [ ] **T-TPL-3** — Push branches, open MRs → **Davud** (owns the cost formula). All 4 MRs = v9+NTP + shadow-drop (nv4 = v9+NTP only, no shadow to drop).

### Workstream C — Puppet / CMS
- [x] **fzg_id node lines + networks.epp fzg_id swap — DROPPED** (box=Fzg means train_id from `backbone-discovery.yaml` carries Fzg; vlan7 computes from train_id directly). Verify networks.epp vlan7 formula works with train_id=Fzg (it already uses train_id — should be correct once train_id=Fzg).
- [ ] **T-PUP-1** — ⚠️ **Rotate the leaked GitHub PAT** in `Config Management/.git/config` remote URL (security).
- [x] **T-PUP-2 — RESOLVED (verified 2026-06-30):** `networks.epp` vlan7 formula `172.19.{{128+((fis_id+train_id)//2)}}` is **BROKEN under box=Fzg for 6-car** (fis_id=128 + train_id=Fzg overshoots → invalid octet 256+). Correct for nv4 (fis_id=0). **Fix (apply in real CMS):** drop the `fis_id` term, use train_id directly:
  ```
  L141: ipaddress: "172.19.{{ 128 + (train_id // 2) }}.2"
  L143: ipaddress: "172.19.{{ 128 + ((train_id-1) // 2) }}.130"
  ```
  Verified correct for all Fzg 1–231 (nv4 + 6-car). `fis_id` has NO other functional use (only these 2 lines) → becomes vestigial, safe to leave or remove. *(Was the bridge for the old internal-id model; under box=Fzg train_id carries the full Fzg.)*

### Workstream D — Re-IP migration (box-id = Fzg, ALL fleets)
**⚠️ `nd-systemupdate.sh factory up` prompt answers (DON'T set RTL project-ID to 51):**
```
project-ID:      51 (6-car: 4736/4706/4705) / 50 (4734)   ← INTERNAL addressing, keep split (IP subnet 10.179 / 10.178)
RTL project-ID:  50  ← ALL DOSTO trains. NMS only has project 50; setting 51 = train dark in NMS (the 6040 bug). Do NOT "make it consistent" with project-ID.
train-ID:        <Fzg>   ← box=Fzg
RTL train-ID:    <accept default; for DOSTO = 6000+Fzg → Zabbix host 50_6<Fzg>>
```
Rationale: internal `project_id` and `rtl_project_id` are intentionally on DIFFERENT axes — addressing is split 50/51, monitoring is unified under 50 (one NMS view for the whole ÖBB fleet). NMS auto-creates Zabbix hosts when a train is added, keyed on rtl_project_id; there is no NMS project 51 to receive 51-namespaced data. See [[reference_zabbix_host_naming_rtl_formula]], [[project_6040_rtl_projectid_51_nms_namespace]].

**4734 (rides SA-2444, ID-50→10.178):**
- [ ] **T-MIG-1** — Per 4734: set `train_id = <Fzg>` in `backbone-discovery.yaml`; re-IP CCU to `10.178.<Fzg>.1`. 24 trains, Fzg 1–90. (NDSU prompt: project-ID 50, RTL project-ID 50, train-ID Fzg.)
**6-car (net-new re-IP, stays on 10.179):**
- [ ] **T-MIG-2** — Per 6-car: set `train_id = <Fzg>` in `backbone-discovery.yaml`; re-IP CCU `10.179.<box>` → `10.179.<Fzg>.1`. 26 trains, Fzg 129–231. Phased; disjoint ranges = no transient collision.
**Both (per train):**
- [ ] **T-MIG-3** — **MAR5 HA backend assignment per CCU node file** (the SA-2444 backend distribution). Per node: `base_profile::ccu::mar5_enabled: true` + **PRIMARY/BACKUP failover** (not single IP):
  ```yaml
  mar3_frontend::tunnel_remote_host: "<primary HA>"
  mar3_frontend::tunnel_remote_host_backup: "<next HA>"   # auto-switch in seconds if primary down
  ```
  Distribution (prefix **77.237.62.x**, engineer-confirmed): primaries spread ~equally across the 3 HAs per project (6-car 9/9/8 across be31/.210·be32/.212·be33/.214; 4734 8/8/8 across be34/.216·be35/.218·be36/.TBD), backup = next HA (rotates) so load stays balanced after a failover. **Full per-train table in the xlsx "Post-Unification" sheet (cols M/N).** ⚠️ be36 (6th HA, ID-50) IP still TBD — SA-2444 adds it. *(Alt mechanism: DCM DNS-resolved HA via `dcm_lookup_hostname` — more dynamic but bigger change; primary+backup is the lower-friction fit.)*
- [ ] **T-MIG-4 — ZABBIX host rename + re-IP (the big monitoring impact).** Zabbix host group = `<rtl_project_id>_<rtl_train_id>_<role>` = e.g. `50_6027_MAR3-B1`. Where `rtl_project_id = 50` (whole DOSTO fleet, NMS-facing namespace — stays 50) and **`rtl_train_id = 6000 + train_id`** (= 6000 + box-id). Under box=Fzg, box-id flips to Fzg, so **EVERY train's Zabbix host group changes** `50_6<old-box>` → `50_6<Fzg>` (e.g. 4736-114: `50_6027` → `50_6142`), AND the host IP changes (re-IP). Two coupled changes per train:
  - **`rtl_train_id` source** = facter `/etc/facter/facts.d/nd.yaml` (`rtl_trainId_21net`) + `backbone-discovery.yaml` — set at provisioning (`nd-systemupdate factory up` with train-ID = Fzg → rtl_train_id auto = 6000+Fzg).
  - **Zabbix side:** host groups `50_6<box>_*` must be renamed/recreated as `50_6<Fzg>_*`, and host **interface IPs** updated to the new `<subnet>.<Fzg>.1` (+ switch/AP IPs). Zabbix won't auto-rename — needs API-driven update (or NMS "add train" which links official train-ID → CCU fqdn, see NMS Config Guide 2026.1). Expect a flood of ICMP/SNMP alarms during the window (stale IPs); pre-plan (trigger window bump, see [[project_zabbix_switch_icmp_dhcp_drift]]).
  - ⚠️ **4734 also moves project subnet** (10.179→10.178) but `rtl_project_id` STAYS 50 (both DOSTO projects publish to NMS namespace 50 — do NOT change rtl_project_id; see [[project_6040_rtl_projectid_51_nms_namespace]]). Only `rtl_train_id` + IPs change.
  - 🚫 **DO NOT split Zabbix hosts to `51_...` for the 6-car fleet to "match project 51"** (a natural-seeming tidy — REJECTED). `project_id` (50/51) is INTERNAL addressing + MQTT namespace only; **NMS/Zabbix has NO project 51 — it keys on `rtl_project_id=50` for the ENTIRE DOSTO fleet.** Publishing 6-car as `51_*` makes those trains go DARK in NMS (no telemetry/KPI/GPS) — this is literally the 6040 bug ([[project_6040_rtl_projectid_51_nms_namespace]], [[project_nms_train_record_vs_monitoring_layer]] line: "No project 51 exists in NMS"). Keep everything `50_6<Fzg>`.
  - Full before→after host-group map derivable from the xlsx "Post-Unification" sheet (box→Fzg) — add a Zabbix column if useful.
  - Also coordinate: cellular/OSPF routing, DHCP scopes.
- [ ] **T-MIG-5** — Update fleet-status: CCU IP + box1-tNN → box1-t<Fzg>.
- [ ] **T-MIG-6** — Re-verify each: hostnames `<variant>-X-v8-<Fzg>`, NTP source = CCU mgmt IP, vlan7 correct, L2 healthy, **MAR5 tunnel up to primary HA (+ backup failover tested)**.
- [ ] **T-MIG-7 — CCU-state survival check after re-IP reboot** (from commissioning state-inventory cross-check, 2026-06-30). The re-IP requires a reboot/promote — run `dosto-state-inventory <ccu-ip> <Fzg>` after each migrated train and confirm the **commissioning state that lives directly on the CCU survived**, re-applying what the reboot wipes:
  - **TFTP CT helper rule (fact 11) — WILL be wiped by the reboot** (runtime-only iptables rule). Re-apply via `dosto-tftp-helper-check --apply-runtime` before any post-migration `obn update f`. (Not yet Puppet-persisted — see [[project_tftp_conntrack_helper]].)
  - **OBN patches (facts 4/5/12)** — if the migration's `train_id` change goes via an NDSU chroot promote (it does — backbone-discovery.yaml is chroot-edited), verify 11/11 patches survived the promote (re-apply via `dosto-obn-patches --persist` folded into the same chroot if not). Watch for nd-obn upgrade wiping them.
  - **NDSU `.dont` rename (fact 6)** — confirm still `.dont` (blocks auto-update promote that would wipe patches).
  - **train_id template (fact 7)** — under box=Fzg, should now be a CLEAN hardcode `{%- set train_id = <Fzg> -%}` OR absent (nv4); confirm no `128+` shadow regressed.
  > These are general per-train commissioning state, not migration-specific — but the re-IP reboot is exactly when they get wiped, so the migration MUST re-assert them. Fold the train_id/vlan7/patches changes into ONE chroot promote (single-promote pattern, handoff lesson 1) to minimize reboots.

### Workstream F — Skill/rule updates for box=Fzg (do alongside deploy)
**Surfaced by the commissioning-skill cross-check, 2026-06-30. Under box=Fzg the OLD mar5 two-namespace assumptions are REVERSED — several skills will false-alarm if not updated.**
- [ ] **T-SKILL-1 — `dosto-fzg-id-check`:** under box=Fzg there is NO template hardcode (`train_id` used directly; shadow deleted). Skill currently expects/repairs `{%- set train_id = <Fzg> -%}`. For box=Fzg trains it must accept "bare train_id, no hardcode" as the correct `all_match` state, NOT broken_formula. Otherwise stage 4 will "repair" a correct template.
- [ ] **T-SKILL-2 — `dosto-state-inventory` fact 7:** same — expect bare `train_id` (no hardcode line) as PASS for box=Fzg trains; current expectation would fail-alarm.
- [ ] **T-SKILL-3 — mar5 rule reversal documented:** Under box=Fzg, `backbone-discovery.yaml train_id = Fzg` is now CORRECT and load-bearing (set at provisioning). The old "never touch backbone-discovery.yaml train_id" rule was a workaround for when box≠Fzg — it is SUPERSEDED for unified trains. Document so no one "restores" the template hardcode or refuses to set the backbone value. (Keep the rule for any non-unified train.)
- [ ] **T-SKILL-4 — `dosto-vlan7-config`:** its formula already derives from Fzg (correct), but the skill notes networks.epp uses train_id — under box=Fzg train_id=Fzg so consistent. Verify no stale "train_id≠Fzg" warnings fire.

### Workstream E — Deploy & verify (per train, after package lands)
- [ ] **T-DEP-1** — Package templates → `.deb` → Puppet (standard OBN path). Confirm v9 renders on a test CCU before any switch push.
- [ ] **T-DEP-2** — Per train: Fzg-ID verify gate (`dosto-fzg-id-check` → all_match) BEFORE `obn update c`. *(Now verify-only for 6-car once Puppet owns fzg_id; for nv4 confirms train_id=Fzg.)*
- [ ] **T-DEP-3** — `obn update c` per train, leaf-first, single-switch (`dosto-sw-config-update --execute`). Per-switch reboot+RSTP-converge gate.
- [ ] **T-DEP-4** — Re-verify coupled pair (110/119 reference): zero TC churn ≥10min, max-age 38, native-999, costs symmetric → clears the VDS/Giorgio gate.
- [ ] **T-DEP-5** — vlan7 + NTP verify per train (`dosto-vlan7-config` → all_match; NTP source reachable, no longer dead 10.179.9.1).

---

### Workstream G — RTPI journey feed (per RMD-520; two mechanisms + an external blocker)
**Source of truth: [RMD-520](https://nomad-digital.atlassian.net/browse/RMD-520) (status Acceptance, assignee Madhu Bethina).**
- [ ] **T-RTPI-1 — NMS train names must be `T47xxxxxx`** so they match the RTPI MQTT topics. Per Madhu (NMS): *"For NMS to pick up journeys from MQTT, either the official ID or the name must match the MQTT topics."* Topics: `to/obb/train/-/T4744038/T4744038/T4744038-MMC-01/rtpiJourney/...`. DOSTO names → `T4736<NNN>` / `T4734<NNN>` / `T4706<NNN>` / `T4705<NNN>` (full train number). Madhu reported "train IDs updated in NMS" 2026-06-23 — **verify it covers the full 50-train fleet** and that the box=Fzg `rtl_train_id` change (6000+box→6000+Fzg) doesn't desync the NMS name↔topic match.
- [ ] **T-RTPI-2 — lookup.xlsx friendly naming** (SEPARATE, cosmetic): map `T<trainnum>`→`Nomad ID` on the importer pod. File attached to RMD-520 (still the 71-row Railjet/CAT/Nightjet set, no DOSTO). Optional/cosmetic — only changes raw `T4736110` to a friendly label.
- ⚠️ **THE ACTUAL BLOCKER (external, not ours):** ÖBB's HAFAS / JourneyFeed API (`api-gateway.oebb.at/JourneyFeed_API/1.0/GetVehicleSchedules`) **doesn't carry the Dosto NEU fleet yet** — Marcus (RTPI) repeatedly couldn't find any 4734/4736 vehicle. No journey data flows until ÖBB publishes the fleet, regardless of NMS names. Latest (2026-06-30): 4736-110/id 6023 trip still not in NMS. **Pursue with ÖBB; not a Nomad config fix.**
- ⚠️ Independent of box=Fzg timing — `T47xxxxxx` = customer number, unchanged by re-IP. See [[project_rtpi_journey_feed_lookup_mapping]].

## Cross-cutting / sequencing notes

- **6-car can lead, 4734 follows SA-2444.** Workstreams A/B/C (6-car fzg_id) are gated only by the engine decision + repo push, not strictly by SA-2444. Workstream D (4734 box=Fzg) is hard-gated on SA-2444's 10.178 backend.
- **v9 coupler/NTP (Phase A) is independent of the fzg_id/migration debate** — it's field-validated and could ship first as its own MR if desired (decouples the urgent TC-storm fix from the slower migration).
- **3×6 triple-traction** remains a separate workstream (RSTP 40-node limit) — NOT in v9. ≤2×6 envelope only.
- **RD-12434** (upstream hand-patches) may be the natural home for the engine-key change — coordinate.

## Key reference docs (all in findings/coupling_test_4736-110_119_2026-06-12/)
- `RUNBOOK_v9_switch_config_deploy_2026-06-30.md` — v9 deploy gates
- `PLAN_durable_fzg_id_no_hand_hardcode_2026-06-30.md` — fzg_id design + vlan7 fold-in
- `AUDIT_train_id_uses_all_fleets_2026-06-30.md` — every train_id use classified + NTP bug
- `PLAN_v9_switch_config_changelist_2026-06-20.md` — M1–M4 definitive change-list
- `fzg_id_puppet_lines_2026-06-30.tsv` — per-train obn::fzg_id lines (filter to 6-car)
