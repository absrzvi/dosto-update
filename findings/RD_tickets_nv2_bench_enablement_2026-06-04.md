# R&D tickets — enable OBN `nv2` (2-coach) train type for the OEBB-251 bench

**Document ID:** RD-NV2-BENCH-001
**Date:** 2026-06-04
**Author:** Abbas Rizvi (Nomad Digital)
**Target CCU:** `box1-t123.dostoneu-bench.21net.com` (10.179.123.1), NMS train 2123 / `OEBB-Bench-2C`, project 50.
**Status:** Root-caused end-to-end; engine patch + template package drafted locally; needs 3 changes across 2 R&D-owned repos + 1 hiera change (Abbas can do) + 1 physical re-cable.
**Jira:** Tickets 1 + 2 (the R&D-access-blocked items) filed as **[TRIAG-8586](https://nomad-digital.atlassian.net/browse/TRIAG-8586)** (assigned Julia Frick, 2026-06-04). Ticket 3 (hiera) + the re-cable are not access-blocked → handled by Abbas directly, tracked here.

---

## 0. Context / why

OBN has **no 2-coach (`nv2`) train type.** The OEBB-251 bench is a physical 2-coach DOSTO consist (coach A = switches A1/A2/A3, coach B = B1/B2/B3, 1 AP on A1.e0-4, CCU on A1.e0-3, Stadler FW on A3.e1-4). It is currently mis-configured as `nv4` (4-coach) via Puppet, so:

- `report_dosto_neu.py::number_coaches()` seeds/walks for 4 coaches and cannot number a 2-coach consist (no `nv2` key in `ccu1_coach_map`/`max_coaches`).
- The CCU runs nv4 4-coach switch templates against 6 physical switches.
- Net effect in the NMS: all devices register as coach 2 (`R2_*`), so the consist diagram renders coach A as "N/A". (The NMS train-type JSON + diagram sizing are already fixed separately; the remaining blocker is OBN coach-numbering.)

Coach-numbering decision (topology confirmed from LLDP + IPA schema `ND-DEL-OBB-035-IPA-251_Bench.p.pdf`): **coach A = 1, coach B = 2, CCU in coach 1** → `ccu1_coach = 1`, `max_coach = 2`. Intra-coach hub = SW3 (matches existing BFS). Inter-coach trunk = A1.e0-1 ↔ B1.e0-1 (on **e0-1**, vs the existing rule's e0-0).

---

## Ticket 1 — `nd-obn`: add `nv2` support to `report_dosto_neu.py`

**Repo:** `onboard/obn` (builds `nd-obn`; engine maintainer Darren Fitzgibbon). *R&D-owned — Abbas has no access.*
**File:** `src/usr/share/obn/lib/report/report_dosto_neu.py` (`DostoNeuReport.number_coaches()`).
**Reference patch (idempotent, drafted + locally validated):** `scripts/fix_obn_nv2_report_dosto_neu.py` in the dosto-troubleshooting workspace.

Three edits:

1. **Train-type maps** — add `nv2`:
   ```python
   ccu1_coach_map = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3, "nv2": 1}
   max_coaches    = {"nv4": 4, "nv6": 6, "fv5": 5, "fv6": 6, "nv2": 2}
   ```

2. **Inter-coach hop rule** — insert after the existing "SW1 of first/last coach → SW3 same coach on E0-0" block. The bench's A↔B trunk is SW1↔SW1 on **e0-1** (existing inter-coach SW1→SW1 rule keys on e0-0). Collision-free: no existing rule matches `device_number==1 AND port==E0_1`.
   ```python
   # SW1 of the ccu1 (first) coach reached on E0-1 -> SW1 of next coach (+1)
   elif (
       from_device.device_number == 1
       and from_device.coach_number == ccu1_coach
       and from_device.coach_number < max_coach
       and port == DostoNeuPort.E0_1
   ):
       to_device.device_number = 1
       to_device.coach_number = from_device.coach_number + 1
   ```

3. **BFS termination guard (Bug-10)** — this file variant lacks it; enabling the nv2 path would otherwise hang `obn report` at 100% CPU on the AP / edge switches (same defect as RCA-OBN-BFS-001). Guard the enqueue:
   ```python
   if to_device.coach_number is not None:
       queue.appendleft(to_device)
   ```

**BFS trace (validates the result), CCU re-cabled lan0→A1 / lan1→A3:** A1=c1/dev1 → A3=c1/dev3 → A2=c1/dev2 → AP=c1; A1.e0-1→B1=c2/dev1 → B3=c2/dev3 → B2=c2/dev2. ✓ coach A=1, B=2.

**Note for R&D:** confirm whether the active engine HEAD still uses `DostoNeuReport` (the deployed fleet does, via the `pipeline/dostoneu-*.yaml` hiera) or has moved to `GenericReport`. If GenericReport, the equivalent change is a `dostoneu2` block in `topology.yaml` (`box1_coach_number: 1`, 2-coach wagon map) instead of this Python patch.

---

## Ticket 2 — new repo `nd-obn-template-dostoneu-nv2`

**Repo:** create `onboard/nd-obn-template-dostoneu-nv2` (mirror `onboard/nd-obn-template-dostoneu-nv4` layout). *R&D creates, or Abbas forks-and-MRs.*
**Drafted package:** `OEBB-251/nv2-template-src/` in the dosto-troubleshooting workspace (builder `OEBB-251/build_nv2_template_pkg.py`).

Contents (`src/etc/obn/`):
- `template/nv2-100-A1.cfg`, `nv2-100-A2.cfg`, `nv2-100-A3.cfg`, `nv2-200-B1.cfg`, `nv2-200-B2.cfg`, `nv2-200-B3.cfg`
- `template/{vlans.j2, dostoneu-obn.cfg, dhcp_groups/*.j2}` (copied from nv4)
- `rules.yaml` — coach 1 d1/d2/d3 → nv2-100-A1/A2/A3; coach 2 d1/d2/d3 → nv2-200-B1/B2/B3; AP rules coach[1,2] d1-4; firmware SW 7.4.2 / AP 6.11.2-0.
- `build.sh` (`name=nd-obn-template-dostoneu-nv2`), `version` 0.0.1, README.md.

**Key design point:** the 6 switch cfgs are based on the **field-tested `2t-bench-*-v4.cfg`** (already pushed to these switches), **NOT nv4** — because nv4-A1's `e0-3` is `no enable`, but `e0-3` is the **CCU/OBS uplink port** on this bench (enabled vlan100 trunk). Copying nv4 verbatim would isolate the CCU. The only change from the 2t-bench source is the hostname line → `nv2-<pos>-v8-{{ ("%03d"|format(train_id)) }}` (verified 1-line content diff per file).

**Action for R&D:** before `build.sh`, copy firmware binaries `ipart-ng.kad-7-4-2` + `IBEX-firmware-6.11.2-0.img` from the nv4 repo into `src/etc/obn/firmware/` (omitted from the drafted tree as large binaries).

---

## Ticket 3 — Puppet hiera: flip the bench CCU to `nv2`

**Repo:** `env/environment-dostoneu` (id 1136), branch **`Engage26`** (the deployed env `dostoneu_Engage26`). *Abbas has Developer access — can branch + MR directly. Listed here for completeness / sequencing.*
**File:** `hieradata/nodes/dostoneu-bench/box1-t123.dostoneu-bench.21net.com.yaml`

The `dostoneu-bench` CCUs are mixed types (t122=OBB-4C, **t123=OBB-2C**, t124=NCL-4C, t125=NCL-6T) sharing `pipeline/dostoneu-bench.yaml` (`train_type: nv4`). So override **per-node** (node layer > pipeline; t127 already does this), do NOT change the shared pipeline. Add:
```yaml
obn::train_type: "nv2"
obn::report_module: "DostoNeuReport"
obn::template_pkg_name: "nd-obn-template-dostoneu-nv2"
obn::template_pkg_ensure: "0.0.1"
```
**Sequencing:** merge Ticket 1 (`nd-obn` with nv2 support) and Ticket 2 (template package published to apt) BEFORE this hiera flip applies — otherwise the CCU pins a non-existent template package / runs unpatched coach-numbering.

---

## Non-repo prerequisite — physical CCU re-cable

OBN's BOX→SW seed keys on the CCU *interface* name (`walker.py`: `lan0→LAN1→dev1`, `lan1→LAN2→dev3`), independent of switch-side port. Current bench: `lan0` is **down** (no carrier); `lan1 → A2.e0-1` (would mislabel A2 as dev3). The bond (`bond0`, lan0+lan1) must present:
- **CCU lan0 → A1** (coach-1 SW1) — bring link up
- **CCU lan1 → A3** (coach-1 SW3) — move from A2

Then the existing BOX→SW LAN1/LAN2 rule seeds A1=dev1, A3=dev3 correctly with no extra code. (Switch-side port is immaterial to OBN; use the OBS/uplink trunk port.)

---

## Done-when (success criteria)

1. `nd-obn` ships with `nv2` in the train-type maps + the e0-1 hop rule + BFS guard.
2. `nd-obn-template-dostoneu-nv2` 0.0.1 published to apt (incl. firmware binaries).
3. `box1-t123` node hiera sets `train_type: nv2` + the nv2 template pkg; Puppet applied.
4. CCU re-cabled (lan0→A1, lan1→A3, both bond slaves up).
5. On the CCU: `sudo obn discover && sudo obn report` → `/tmp/discovery.json` shows 6 switches across **coach 1 (A1/A2/A3)** and **coach 2 (B1/B2/B3)** + the A1 AP in coach 1; `obn report` does not hang.
6. NMS rebuilds the 2123 skeleton with `R1` + `R2` hosts → consist diagram labels coach **A** (no longer "N/A").

## Cross-references
- Full GitLab/Puppet process + access map: `OEBB-251/obn-gitlab-process.md`
- nv2 enablement plan + verified topology: `OEBB-251/nv2-bench-obn-enablement-plan.md`
- BFS hang RCA (Bug-10, same guard as Ticket 1 edit 3): `findings/RCA_obn_report_bfs_infinite_loop_2026-06-02.md`
- Existing OBN hand-patch ticket backlog: memory `project_rd_gitlab_tickets_todo`
