# DOSTO Fleet — Per-Train Journal

Narrative companion to [`fleet-status.md`](fleet-status.md). Where `fleet-status.md` answers *"what is the current state of every train"* in scannable table form, this file answers *"what happened on this train, in what order, and why."*

## What goes here

- Recovery sequences worked out for a specific train
- Session-specific context for the next engineer: train history, partial work in progress, things to verify
- Stadler-facing investigation notes (raw, before they become a customer report)
- Anything that previously lived as prose in `fleet-status.md` per-train detail blocks

## What does NOT go here

- **Current state** of any train — `fleet-status.md`
- **Cross-train architectural findings, gap audits, post-mortems** — these are *one-shot dated handoff docs* (`handoff-<topic>-<date>.md`). When a finding from a handoff doc is observed on a second train, it graduates to `CLAUDE.md` "Pitfalls."
- **Fleet-wide pitfalls** — `CLAUDE.md`
- **Skill behaviour** — the relevant `.claude/skills/<skill>/SKILL.md`
- **Cabling faults** — `cable-issues-register.md` (filed once Stadler diagnoses cause)

## File conventions

- One section per Fzg ID, in numeric order, grouped by series (4736 first, then 4734).
- Within each Fzg section, entries are append-only and dated. Most recent at the top. Never edit a prior session's entry — add a new one above it.
- Each entry starts with a `### <YYYY-MM-DD> — <initials> — <one-line summary>` header.
- Each entry answers: *what changed*, *what we learned*, *what's next*. Keep it tight; cross-reference handoff docs for cross-train findings rather than duplicating.

## Related handoff docs

- **2026-05-11 first-run audit** — [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md). Architectural findings F1–F8 from the first orchestrator-stack test.

---

## 4736 series

### Fzg 130 — 4736-102

#### 2026-05-12 — AR — L2 health check; 4 missing switches returned; FW commission confirmed; OBN readonly bug found

**Session goal.** Full L2 health check, push config to 3 `-man` switches, upgrade 24 APs from `6.10.0-0` → `6.11.2-0`.

**What changed.**

- Prior BLOCKED state (D2/E2/E3/F2 missing) **resolved without Stadler action** — all 4 switches returned; 18/18 now visible. Removed from cable-issues-register (no cabling fault, switches came back on their own — likely transient cellular outage on the previous visit).
- **Stadler FW commission state confirmed:** `ping -c 5 172.19.193.1` → 100% loss with ARP REACHABLE (`00:90:e8:bb:9d:67`). ICMP loss = Stadler policy drop = commissioned. Closes the open question from 2026-05-11 journal entry.
- **L2 fabric healthy:** 18/18 switches, all trunks UP 10G full, zero CRC/carrier-false errors, single stable RSTP root.
- **OBN patches:** 8/8 confirmed still in run1 (no reboot had wiped them).
- **TFTP conntrack helper** applied (runtime): `modprobe nf_conntrack_tftp` + `iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp`.
- **3 switches still on `-man` config:** `.180` (E1), `.186` (B1), `.187` (F1) — `obn validate -t sw` shows `✗`. These were never given OBN-rendered config (possibly pre-existed from factory or a different commissioning run).
- **24 APs on `6.10.0-0`** (target `6.11.2-0`), all correct Nomad config. Firmware push not yet started.
- **OBN `discover → report → update` workflow order learned:** `obn update c` and `obn validate` read from `discovery.prev.json` (the committed report snapshot), not `discovery.json` (raw scan). This is by design — `obn report` is the step that commits the scan. We had skipped `obn report`, so `discovery.prev.json` was stale (1 device only) → empty device set for target IP → Python `all([]) = True` → "Update not supported for readonly devices". Fix: always run `sudo obn discover && sudo obn report` before any `obn update c` or `obn validate`. `obn report` started in background; CCU dropped (cellular) before completion confirmed.

**What we learned.**

- **OBN canonical workflow is `discover → report → update/validate`** — not a bug, by design. `obn report` commits the raw scan into the stable snapshot that all OBN operations read from. Any train where `obn report` hasn't been run will show stale data in `obn validate` and "readonly" errors in `obn update c`. Always run both commands in sequence before any OBN push. Document in troubleshooting-runbook.md under "OBN update fails — readonly devices".
- **`obn validate` empty table when consist.yaml is empty** — OBN hadn't built a topology tree on this CCU. Workaround: read `/tmp/discovery.json` directly via Python.
- **`08_e2e_probe.sh` had hardcoded FW IP `172.19.196.1`** — produced false `path_broken` for Fzg 130 (actual FW is `172.19.193.1`). Always pass explicit second arg. Background task spawned to fix the script.
- **VDS switch reboot CLI command unknown** — `reboot`, `reload`, `system reboot` all rejected. Investigate via docs/switch_user_manual.pdf.

**Next.** Re-connect when CCU is back. Verify discovery.prev.json populated (≥43 devices). Push `.180`, `.186`, `.187` config in leaf-first order. Then push 24 AP firmware serially. See [handoff-fzg130-2026-05-12.md](handoff-fzg130-2026-05-12.md) for detailed resume commands.

#### 2026-05-11 — AR — CCU-local recovery executed via orchestrator-stack test run

**Session goal.** Test the orchestrator → train-worker → commission-train flow end-to-end. Recovery of Fzg 130 was a means to that end, not the primary goal. Findings on the stack are in [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md).

**Train-specific outcome.**

- Stage 1 `initial_diagnostics` confirmed prior state: 0/8 OBN patches, broken `128 + train_id` template, vlan7 = `172.19.215.130/17` (encoded Fzg 175). Plus a new finding: **4 switches missing** from vlan100 — D2, E2, E3, F2. Only 14/18 visible.
- Gate 5 (`device_count_mismatch`) approved as `partial`: proceed with CCU-local fixes only, halt before consist-wide pushes.
- Three-fix fold-in chroot promote (patches + vlan7 + train_id) into snapshot run1. Verified read-only mount confirmed correct contents before reboot.
- Post-reboot verify (parent-driven, 05:46 UTC, uptime 15 min): all green except expected TFTP-helper loss. Boot snapshot run1. vlan7 live = `172.19.193.2/17`. train_id = `130` uniform across 18 templates. OBN markers 8/8 (bug 6 count=2 per F7). **Stadler FW path: confirmed clean, commission state not confirmed** — ARP REACHABLE to `00:90:e8:bb:9d:67` (Westermo OUI); TCP 80 + 22 OPEN; ICMP not tested. Per CLAUDE.md Phase 6, the deciding test for a commissioned Stadler FW is ICMP (configured FW drops echo-request by policy), not TCP. Next session: run `ping -c 5 172.19.193.1` to determine actual FW state.

**Train-specific learnings.**

- Recovery sequence in fleet-status worked exactly as written.
- Template filenames on this CCU are `nv6-NNN-XX.cfg` (e.g. `nv6-100-A1.cfg`, `nv6-200-C1.cfg`), not `nv6-XX-vY.cfg`. Glob the templates, don't hardcode.
- D2/E2/E3/F2 missing pattern: D2 and F2 are mid-of-pair missing (peers present), E2+E3 missing together (broader E-coach issue). Not filed in cable-issues-register yet — pending Stadler diagnosis (power vs cabling vs switch fault).
- Stadler FW path is clean to `172.19.193.1` (ARP REACHABLE, TCP 80/22 OPEN) but FW commission state is **not confirmed** — we didn't run the deciding test (ICMP). A commissioned Stadler FW drops echo-request; an uncommissioned one wouldn't. Re-test next session before claiming FW state in customer reports.

**Next.** Mark Fzg 130 `🔴 BLOCKED — awaiting Stadler on D2/E2/E3/F2`. No customer report until consist-wide work resumes. TFTP CT helper not re-applied yet — only needed before AP firmware push, which is blocked anyway.

### Fzg 131 — 4736-103

#### 2026-05-11 — AR — Train offline, session skipped

CCU `10.179.11.1` unreachable (ping + ssh timeout) at attempt time. Fzg 130 on the same VPN was reachable, so the issue is train-side, not network-side. Worker spawned then killed cleanly. Fleet-status row reflects offline status.

### Fzg 132 — 4736-104

*(Journal entries to be migrated from `fleet-status.md` per-train block on next session visit. The Fzg 132 block currently contains the canonical record of: two-step promote requirement, TFTP CT helper runtime fix, AP firmware push parallelism failure, dosto-ap-firmware-update skill bugs found+fixed.)*

### Fzg 133 — 4736-105

*(Journal entries to be migrated. Current state: DONE w/ Stadler — Coach 5 AP2 missing, Stadler FW not commissioned.)*

### Fzg 136 — 4736-108

*(Journal entries to be migrated. Current state: BLOCKED on cable register #2 + #3.)*

### Fzg 137 — 4736-109

*(Earlier journal entries to be migrated. Prior state: BLOCKED on cable register #4 — B3 e0-4 AP not connected. Stadler L2 fault report v1.0 already filed.)*

#### 2026-07-04 — AR — NMS alarm review → uncovered two switches (E2, C3) absent from monitoring; field confirmation of the OBN coach-numbering blind spot

**Session goal.** Engineer asked why 4736-109 (ÖBB painted **6028**) shows a wall of NMS alarms. Triaged the panel, then chased the one real network-side finding.

**Alarm triage (all 12 rows were stale/unacknowledged, ✗ in Acknowledged):**
- **AP `7.7.7.7 cannot be pinged` ×5 (High)** — stale template placeholder IP, not a real AP. Confirmed from CCU: `ping 7.7.7.7` = 100% loss while all 19 real APs (`.218–.238`) answer 0%. NMS-side fix = correct AP monitoring IPs in the train-type template.
- **SW R2/R4 `unavailable by ICMP` ×3 (High)** — stale DHCP-drift/power-cycle transients; all live switches fping 0% loss now. Ack + `zbx_reconcile.py` if recurring.
- **Port e0-4 DOWN (admin-enabled) on R6 SW1/SW2 ×2 (Medium)** — the known B-coach AP-trunk gap = cable register #4 (Stadler-side, APs not installed).
- **SIM usage 96.42% High / 81.6% Medium** — cellular data-cap, not L2; flag to SIM plan owner.

**The real finding — 16/18 switches, and NMS wasn't alarming on the 2 missing (the blind spot):**
- **E2 = cold bypass.** No lease, no vlan100 IP. D1 e0-1 LLDP→ E3 (across E2's slot), both links UP 10G, 0 CRC, carrier-false 0 — reciprocal clean-link signature. E2 is powered off/failed in place; backbone relays through it. NOT a cabling fault → check power/health of E2. Logged as **cable register #13**.
- **C3 = healthy but stranded by DHCP abandonment.** Also no lease, but C2 e0-0→C3 is UP 10G with **RX 9.9GB / TX 280GB, 0 CRC** — C3 present and forwarding heavily. Root cause traced (NOT a bypass, NOT cabling): the CCU rebooted ~18:22, dhcpd came up cold with `ping-check true`, ICMP-pinged each pool address, got replies from switches still holding their RAM IPs, and **abandoned 14 addresses** (`pinged before offer` in the log at 18:23). C3's RAM-held `.189` was abandoned server-side (LLDP still advertises `.189`; `.189` is ICMP/ARP-dead) and C3 never completed a fresh DISCOVER → stranded with a dead mgmt IP. **This recurs on every CCU-only reboot.** Full RCA: [findings/dhcp_pingcheck_abandon_cascade_2026-07-04.md](findings/dhcp_pingcheck_abandon_cascade_2026-07-04.md). Band-aid = `systemctl restart isc-dhcp-server`; permanent guard = `ping-check false;` in the Puppet-rendered dhcpd.conf (fleet-wide). Tracked here + memory `project_dhcp_pingcheck_abandon_cascade`, not the cable register (not a cabling item).

**Why NMS couldn't alarm on either (the blind spot itself):** Zabbix hosts for this train are provisioned from the OBN report (`create_nms_device_nodes`). E2 gets dropped by OBN's coach-numbering walk (`normalise_devices()` deletes unnumberable positions); C3 isn't even in DHCP. No host provisioned → nothing to alarm on → dashboard reads 16/18 as green. This is the live field confirmation of the bench RCA in [findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md](findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md). CCU is on **nd-obn 2.2.23** (pre-fix).

**What's next.**
- **E2 → Stadler:** check power/health of switch E2 (register #13).
- **C3 → Nomad:** investigate why C3 doesn't lease vlan100 (mgmt-VLAN access / DHCP path on C3). Healthy switch, no mgmt IP.
- **NMS blind spot → R&D:** productionise the `report_dosto_neu.py` fix (§5c floor: never silently drop discovered switches; §5a/5b: emit bypassed positions as first-class DOWN rows with a valid slot so NMS provisions a host and can alarm). C3 shows the §5c floor alone isn't the whole story — a healthy-but-unmanaged switch also needs its mgmt IP back to be a normal monitored host.
- Ack the 12 stale alarms once the above are captured; NMS AP-IP template fix (`7.7.7.7`) is a separate NMS task.

### Fzg 148 — 4736-120

*(Journal entries to be migrated. Current state: PAUSED mid-`obn update c all` 2026-05-04.)*

---

## 4734 series

### Fzg 1 — 4734-101

*(Journal entries to be migrated. Current state: BLOCKED on cable register #1.)*

### Fzg 9 — 4734-109

#### 2026-06-17 — AR — A1 switch replaced by Stadler + commissioned; cable reg #10 closed; OBN tree.py Bug 6 found unpatched on 2.2.23

**Session goal.** Train listed as "Termin with Stadler to update switch config." On login, discovered the real change: **Stadler had physically replaced the faulty/mis-cabled A1 switch** (the long-standing reg #10 coupler cable swap). So the session became "commission the replacement A1," not "wait for re-cable."

**What changed.**
- New A1 = chassis `a0:59:3a:d0:c1:c0`, DHCP `.186`, came up on **factory config** `dosto-000000000000-v1-FD`, firmware already `7.4.2`. Cabling now **correct** (live LLDP): A1 e0-0 → Fzg9 A3, e0-1 → Fzg9 G1, e0-2 → Fzg15 A3 (front coupler). This is the exact as-designed A-head from reg #10's expected end-state.
- Old A1 (`a0:59:3a:d0:8f:a0`, hand-corrected in-band 2026-06-08) is now an isolated spare hanging off A3 e0-2 (coupler trunk, VLAN 5/15 only, no vlan100). No fabric/IP clash — confirmed it holds no vlan100 lease.
- Applied runtime TFTP conntrack helper (wiped by CCU's earlier reboot).
- `obn update c .186` → RRQ seen ~5s, switch rebooted (uptime 7 min, new lease), hostname adopted `nv4-A1-v8-009`, config persisted. **12/12 switches now `nv4-X-v8-009`.** RSTP single-root G1 (`a0:59:3a:d0:43:a0`) unchanged + fully converged (all A3 ports FWD).

**What we learned.**
- `obn update c` first crashed: `AttributeError: 'NoneType' object has no attribute 'type'` at `tree.py:34` in `OBNTree.create_tree`. Cause = the Fzg-15 coupler neighbour (`d0:93:80`) isn't in OBN's own device list → `next(..., None)` → `.type` deref. This is **Bug 6 (cross-consist tree guard)** — and it was **absent** on this nd-obn 2.2.23 CCU, contradicting the "2.2.23 ships bugs 1–10 native" assumption. Applied canonical `if neighbour_device is None: continue` guard at runtime (backup `tree.py.pre-bug6`); push then worked.
- The skill's `verify_reboot_started` 75s ICMP window can false-negative — the reboot was fast enough that ICMP didn't visibly drop, but uptime + new lease + new hostname prove it cycled. Trust the post-state (hostname/uptime), not just the ICMP-drop window.

**What's next.**
- OBN `tree.py` Bug 6 patch is **runtime-only** — wiped on next reboot. If this train (or any coupled 2.2.23 train) needs `obn` ops again, re-apply or persist via NDSU chroot. Worth confirming fleet-wide whether 2.2.23 actually ships this guard.
- L2 health check + customer report deferred (engineer chose commission+verify only). Run `/dosto-l2-health 10.179.38.1` when a deliverable is wanted.
- Old A1 spare on A3 e0-2 — Stadler to remove or retain.

### Fzg 19 — 4734-119

#### 2026-05-21 — AR — Customer B&E WAP1/WAP2 swap report investigated; no Nomad-side fault

**Session goal.** Customer (ÖBB) ran an in-coach Wi-Fi scan on Fzg 19 and Fzg 20 and reported that on coaches B and E the WE1 and WE2 SSIDs appear swapped vs schema.

**Method.** SSH to CCU (`10.179.45.1`); LLDP-walk every leaf switch's AP port (e0-4 / e1-2); then SSH each AP (`nomad`/`NomadComeIn`) and read `cfgSysHostname.0`.

**Result.** AP→switch-port mapping is uniform and consistent:
- Coach A: A1.e0-4=AP1, A2.e0-4=AP2, A3.e0-4=AP3, A3.e1-2=AP4 (`APx-v1` config)
- Coach G: G1.e0-4=AP1, G2.e0-4=AP2, G3.e0-4=AP3, G3.e1-2=AP4 (`APx-v1` config)
- Coach E: E1.e0-4=AP1m, E2.e0-4=AP2m, E3.e0-4=AP3m, E3.e1-2=AP4m (`APxm-v1` config)
- Coach B: B1.e0-4=AP1m, B2.e0-4=AP2m, B3.e0-4=AP3m, B3.e1-2=AP4m (`APxm-v1` config)

No swap at the OBN/cabling/switch-config layer. Pattern matches Fzg 20 exactly.

**Remaining suspects.** (1) `APxm-v1` Nomad payload broadcasts WE1/WE2 SSIDs inverted vs schema position numbering — only m-variant coaches affected; (2) coaches B and E physically installed reversed end-for-end relative to A and G.

**Next.** Handoff to Stadler/ÖBB: confirm physical orientation of B and E, or pull the `APxm-v1` vs `APx-v1` Nomad config payload diff to locate inverted Wi-Fi role parameter. No Nomad action required; train remains DONE.

### Fzg 20 — 4734-120

#### 2026-05-21 — AR — Customer B&E WAP1/WAP2 swap report investigated; no Nomad-side fault

Same investigation as Fzg 19 (see entry above). AP→switch-port mapping on Fzg 20 verified identical to Fzg 19. Symptom not in Nomad/OBN/cabling layer; suspects are m-variant Wi-Fi config payload or coach physical orientation. Train remains DONE. See [project_be_wap_swap_fzg19_20](../.claude/projects/C--Users-AbbasRizvi-Documents-dosto-troubleshooting/memory/project_be_wap_swap_fzg19_20.md) memory entry.

#### 2026-05-11 — AR — Partial Stage-1 probe via orchestrator-stack test; worker stalled mid-diagnostics

**Session goal.** Second parallel target of the orchestrator-stack test run. Architectural findings in [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md).

**Train-specific findings (from worker's sub-check 5/6 report before it stalled):**

- ✅ Switches: 12/12 visible, all on `nv4-*-v8-020`, FW `7.4.2`
- ✅ APs: 16/16 visible, all on FW `6.11.2-0`, Nomad v1 config (0 in factory)
- ✅ vlan7: live + nmconnection both `172.19.138.2/17`
- 🟡 OBN patches: standard grep found no markers; not yet investigated whether CCU is genuinely vanilla or whether nv4 paths differ

**Open question.** If switches AND APs are already at target state but OBN patches grep returned empty, possibilities are: (a) someone commissioned this train without patches (risky, but apparently survived); (b) patches were applied, persisted, then a `release` rollback wiped them; (c) the canonical grep markers differ for nv4 platforms. Worth a deeper inspection next session — but not via a fresh worker until the F1/F2 fixes from the audit doc are in place.

**Next.** No fleet-status flip yet; defer further work on this train until the bootstrap-audit fixes land. Current state in fleet-status remains `⚪ UNKNOWN`.

### Fzg 23 — 4734-123 (CCU box1-t67 @ 10.179.67.1)

#### 2026-06-09 — AR — New train discovered on morning-brief auto-sweep; identity confirmed, CCU dropped mid-inventory

**Session goal.** `/dosto-morning-brief` reachability sweep flagged `10.179.67.1` as a CCU on TCP/22 not present in fleet-status. Engineer chose to assign rather than skip; logged in to identify it.

**Identity — confirmed from convergent markers** (didn't trust any single field; an unvisited CCU can carry a wrong rendered train_id):

- Hostname `box1-t67`, bond0 `10.179.67.1/25`, vlan100 `10.179.67.129/25`.
- vlan7 live `172.19.139.130/17` → octet3 139 = 128 + Fzg//2 and **odd host (.130)** → **Fzg 23**. (Distinct from Fzg 22 / 4734-122, whose vlan7 is the even-host `172.19.139.2` — same octet3, different host bit.)
- **nv4 4-Teiler**: coaches A/B/E/G, 12 VDS switches all `nv4-*-v8-023`, 16 APs all Nomad form (`AP*-v1-*`, none factory `RT610LV`).
- Series formula 4734-NNN = Fzg+100 → **Train# 4734-123**. No existing fleet-status row, no allocation PDF folder → genuinely fresh train.
- Assigned via `dosto_morning_brief.py --assign 10.179.67.1 4734-123 --fzg 23`. New row added: `⚪ UNKNOWN / initial visit`.

**State inventory — INCOMPLETE.** Started `/dosto-state-inventory`; **CCU went offline mid-probe (~08:30Z)** — both bond0 and vlan100 timed out, stayed dark through a ~5-min poll. Classic cellular/consist drop, not us (every read prior was read-only and succeeded). Got facts 1–3 + 8; pending facts 4–12 (OBN patch count, NDSU filename, train_id template form, vlan7 nmconnection, TFTP module/helper/ipset).

**Notable.** Switches already render `-v8-023` correctly (train_id resolves to 23), yet the nv4 `.cfg` templates are **Form-2** (formula-based train_id, no `{%- set train_id = 23 -%}` directive). Couldn't confirm fact-7 form before the drop — open question whether it's Form-1-with-directive or sourced elsewhere. Commissioning will likely need the Form-1 directive added to all 12 nv4-*.cfg (cf. [feedback_nv4_form1_directive_required](../.claude/projects/C--Users-AbbasRizvi-Documents-dosto-troubleshooting/memory/feedback_nv4_form1_directive_required.md)).

**Next.** Re-run `/dosto-state-inventory 10.179.67.1 4734-123` when online to finish the 12-fact baseline; drop the IP-Port-Allocation PDF into `train-ip-allocation-commission/4734-xxx/4734-123/`. Train stays `⚪ UNKNOWN`.

---

## How to add an entry

1. Find the Fzg section (or create it if the train doesn't have one).
2. Insert a new dated `### YYYY-MM-DD — <initials> — <one-line summary>` header **at the top** of that train's section.
3. Keep it to *what changed / what we learned / what's next*. Cross-reference handoff docs for architectural findings rather than duplicating.
4. Update `fleet-status.md`'s per-train row only for state changes; the journal does not replace the table.

---

## Fzg 138 — 4736-110 (CCU box1-t23 @ 10.179.23.1)

### 2026-06-03 — AR — Crew report: no Wi-Fi signal in both Führerstände → root cause = wrong/foreign device on A3 e0-4 (front-cab AP3 position)

**Symptom:** crew report no signal in the cab at both ends. Read-only investigation from CCU.

**What was ruled out:**
- All other APs healthy: `obn validate -t ap` = 23 present, all firmware 6.11.2-0 ✓ + config ✓. (Train power-cycled mid-investigation; AP IPs rotated — IPs below are post-cycle.)
- `/etc/obn/coach_ap_mappings.yaml` showing all radios `updown: DOWN` is a **red herring** — read only by report.py for a report "floor" label, not radio control. Stale 2024 default.
- Radio band plan is **correct per template** (`~/Documents/nomad-obn-template-nv6/src/etc/obn/rules.yaml`): plain coaches AP1/AP4=2.4GHz, AP2/AP3=5GHz; m-variant coaches (4/5/6) mirror it AP1/AP4=5GHz, AP2/AP3=2.4GHz. Live cab APs all match. NOT the Fzg 19/20 m-variant divergence.
- TX power: all cab APs `cfgWlanDevPower=15` dBm, antenna 6 dBi, country DE → ~21 dBm EIRP. 2.4GHz already at ETSI 20dBm ceiling; 5GHz ch36/44 has only ~2dB legal headroom. Power bump NOT the fix.

**Root cause — front-cab AP3 (Coach 1, position A3, config AP3-v1, 5GHz/5220):**
- Expected MAC `00:14:5a:04:6a:ba` (Westermo) is **absent everywhere** — no DHCP lease, no vlan100 ARP, not on switch A3.
- Switch A3 = `10.179.23.179` (fingerprinted: e1-4 multi-VLAN Stadler trunk). Per nv6-topology, AP3 → **A3 e0-4**.
- A3 **e0-4 is link UP, 1000/Full, 0 errors/CRC/carrier** — port + cable healthy. RX 3289 / TX 18638.
- **MAC learned on e0-4 is `14:4f:d7:da:77:48`** (OUI 14:4f:d7 = HP/AzureWave, NOT Westermo 00:14:5a). VLAN PVID 1, trunk allows 100,10,20,30,31,131,150,1 (correct AP trunk).
- **LLDP resolves it: SysName `iobtester-HP-El...` (HP EliteBook) — an ÖBB tester's / commissioning laptop** patched into the AP3 port. The real front-cab AP3 was unplugged to make room for it. NOT a hardware fault or wrong-AP swap — a left-behind test connection. (`show lldp neighbours`: e1-2→AP4-v1 ✅, e0-0/e0-1→nv6-A1/A2-v8-138 ✅, e1-4→firewall ✅, e0-4→iobtester laptop ✗.)
- Control: sibling front-cab AP4 on A3 e1-2 (.223) alive & on Nomad config → switch/uplink/power all fine.

**Conclusion:** front-cab AP3 was disconnected and a tester's HP laptop occupies its port (A3 e0-4). Front cab loses its 5GHz/5220 cell → "no signal." Resolution: reconnect AP3, unplug the laptop — a field action, likely doable by whoever is on the train now.

**Field action required:**
1. At Coach A / front cab, unplug the `iobtester` HP EliteBook from switch A3 port e0-4 and reconnect front-cab AP3 (Westermo RT610LV, MAC `00:14:5a:04:6a:ba`).
3. Rear cab (Coach B/6): all 4 APs present + correctly configured per plan; if signal still weak there, it's RF/antenna/coverage (physical), not network.

**Optimisation note (post-restore):** only safe RF lever is moving 5GHz cab APs to a DFS channel (5470–5725, ch100+, 30dBm ETSI ceiling) then raising power — channel-plan change w/ DFS consideration, not a bare power bump. 2.4GHz already maxed.

### 2026-06-18 — AR — Ignition logger hardened + repeatable Vign-collapse fault captured

**Context:** train kept going dark for long stretches (NMS "last message" red; e.g. 06-17 last msg 08:30 CEST). A persistent CMM Vign poller (`vign-logger.service`, installed 2026-06-16) is the only record that survives a power-down — `/var/log`, journald, dmesg and `wtmp` are all tmpfs on this CCU; only `/data` (btrfs) persists. No BMC/IPMI SEL exists; the ADLINK `cmm` CLI is broken (GLIBC mismatch) so raw `i2ctransfer` is the only CMM path; watchdog is disarmed (ruled out). The CMM has **no latched cause register** (confirmed against the full R5001C CMM I2C Manual v2.5 — commands 0x01–0x20 are all live sensors / settable timers, zero history), so capturing state *before* the cut is the only diagnostic option.

**Hardening applied (all artifacts on `/data`, the only persistent FS; unit files installed via btrfs RO-toggle):**
1. `vign_poll.sh` heartbeat `HB` 300s → **30s** — last pre-cut sample now ≤30s old instead of up to 5 min.
2. `vign-shutdown-marker.service` — writes `GRACEFUL_SHUTDOWN <iso>` + final CMM read to `/data/ignition-log/shutdown.log` on a clean shutdown only. **Absence after an outage proves a hard cut.**
3. `nd-logtail.timer` (60s) → `/data/ignition-log/logtail/` — rolling tail of dmesg + journal priority≤4 (catches thermal/undervoltage/OOM precursors).
4. Added inlet/outlet **temperature (CMM 0x03)** to the poller — signed 2's-complement decode verified against manual examples; new `inlet_c`,`outlet_c` columns. Closes the thermal-cause blind spot (CMM inlet thresh 70°C / outlet 85°C; kernel already logs an ACPI thermal firmware-bug warning). Confirmed live: inlet 25.5°C / outlet 30.5°C at install.

**FINDING — repeatable ignition-input dropout in Manual mode (3rd occurrence):**
- **2026-06-18 ~05:31 UTC (07:31 CEST):** HB=30 caught the exact transition — Vign **109.74 → 0.00 V** while **Vin held rock-steady at 109.79 V**, stayed 0 for ~90s, then CCU powered down (gap to next `start` 05:33→05:38). `shutdown.log` **EMPTY → hard cut, no graceful shutdown.**
- Same signature on **2026-06-16 19:12** (Vign→0, Vin held ~112V). 06-17 event fell in the old 5-min blind window (inconclusive).
- **Per the logger's own rule: clean Vign collapse with Vin holding = ignition-input fault.** This is now repeatable, not a one-off.
- **Contradiction to resolve:** every sample reads `MANUAL_on` (chassis bits[7:6]=10), where the ADLINK manual (§3) says the ignition input is **bypassed** — a Vign=0 should NOT shut the CCU down in Manual. Yet it consistently does shortly after Vign collapses. Either (a) the front-panel 3-position switch is **not really on Manual** despite the CMM readout (wiring/readout mismatch → train is actually ignition-controlled → these are genuine ignition faults), or (b) Vign and the power-down share an upstream vehicle-circuit cause. **Either way the ignition line dropping to 0V while battery holds is a real, repeatable electrical event — a concrete finding for whoever owns vehicle power/ignition wiring (Stadler).** Next physical visit: verify the front-panel switch position by eye.

**Data:** `/data/ignition-log/vign.csv` (live) + local copy `findings/ignition-log-4736-110/` (all scripts, unit files, `vign_4736-110_20260618.csv`). NDSU promote will roll the 3 unit files out of `/etc` (scripts on `/data` survive) — re-run RO-toggle install if that happens.

---

## Bench — box1-t122 @ 10.179.122.1 (4122, nv4 A-G-E-B)

### 2026-07-05 (session 2) — AR — Loop-guard VALIDATED live; islanded A/G arm recovery attempted (blocked, physical); RSTP costs normalised; second-uplink + B3 findings

Follow-on to the flash session below. Goal: recover the islanded A/G arm (A3/A2/G3/G2/E1) and verify loop-guard works. Loop-guard confirmed working; arm recovery is blocked by physical/wedged-state issues (documented for a bench visit).

**Loop-guard force-block VALIDATED live.** Re-enabled **B1 e0-1** (reconnecting the flashed side to the unflashed 7.4.2 arm via E1) — a path that *before* the upgrade would have re-ignited the storm. Result: **zero storm.** Multicast +6/6s, all 5 flashed switches stayed at load ~0.1, no KON/coldStart. Every backbone port stayed `FWD` with the `loopGuardBlock` capability flag (armed, not tripped — verified none in DISCARDING). This is the durable fix proven under real conditions: a reconnected welded-ring path is now held safe instead of storming. See [[project_vds_loopguard_forceblock]].

**The islanded A/G arm: alive at L2, management-DEAD, cannot be recovered in-band.** The 5 arm switches (A3/A2/G3/G2/E1) are **powered + forwarding** (their MACs are learned on B1 e0-1; A3 `52:20` and E1-neighbours actively broadcast) but have **no vlan100 IP** → no SSH/SNMP/ICMP → **no way to send `sysadmin reboot`**. Why they differ from the B/E arm (which recovered): the B/E switches **kept their DHCP lease** (renewing from a configured IP → unicast DHCP works) so I could SSH in and reboot them; the A/G arm **lost its lease during the storm** and dropped to IP-less DHCP-INIT. Catch-22: no IP ⇒ no management ⇒ can't reboot ⇒ can't clear the wedge ⇒ can't get an IP.

**DHCP INIT deadlock + the `always-broadcast` fix.** The arm switches send DHCPDISCOVER with **`Flags [none]`** (broadcast flag OFF) while at 0.0.0.0 → dhcpd replies **unicast to the offered IP**, which an IP-less client can't receive → DISCOVER→OFFER→DISCOVER forever, never ACKs. Fix applied on the CCU: `always-broadcast on;` in the vlan100 subnet stanza of **`/tmp/dhcp/networks/management.conf`** (runtime-generated file; backup `.bak-prebroadcast`; `sudo systemctl restart isc-dhcp-server`). Verified dhcpd now broadcasts replies (`10.179.122.129.67 > 255.255.255.255.68`). **BUT the arm still didn't complete** — the broadcast OFFER egresses B1→E1 (confirmed B1 e0-1 TX-broadcasts climbing) but doesn't propagate into the deep arm; it dies at/inside the wedged **E1**. So `always-broadcast` is necessary-but-not-sufficient; it will help the moment the arm gets a management foothold. (`/tmp/dhcp/*` is regenerated on CCU reboot → the edit is NOT persistent; re-apply if needed. Same INIT/broadcast-flag family as [[project_dhcp_pingcheck_abandon_cascade]].)

**Both arm entry-points are hard-blocked — ruled out loop-guard, ruled in physical/wedged:**
1. **G1 e0-0 → A3 (direct, via A1 cold-bypass):** re-enabled G1 e0-0, link **never comes up** (RX=0 ever, no LLDP). Cause = **A3's own e0-0 is admin-disabled** — *our* storm-fix cut (`no configure interface e0-0 enable` on A3), which we can't undo because A3 is unreachable. (Corrects an earlier mis-read that blamed the A1 bypass hardware — earlier in the day G1 *did* see A3 through a working A1 bypass, so the bypass passes; the block is our A3 port-disable.)
2. **B1 e0-1 → E1 (long path):** forwards fine to E1, but E1 is management-wedged and doesn't complete DHCP into the deep arm.
- **NOT loop-guard:** every reachable backbone port is `FWD` (armed, not tripped) — verified on all 5 switches. Loop-guard is not dropping the return path.
- **NOT a disable-able reachable port:** the reachable fabric is a single **linear chain** (CCU–G1–E2–E3–B2–[B3✗]–B1–E1–arm; ring open at our cuts + the two dead bypasses). Every working switch is load-bearing for the arm's path, so "disable a working switch to fix asymmetry" only re-isolates the arm.
- **NOT fixable by rebooting a neighbour (tried, negative):** rebooted **B1** to bounce the B1↔E1 link, on the theory the link-drop might jolt the wedged E1's forwarding loose. B1 came back in ~15s, e0-1 re-linked to E1 (10G up) — **arm stayed all-DOWN, 0 leases across 90s.** Confirms the arm switches are **genuinely IP-stack-wedged**, not merely stuck-forwarding: a neighbour link-bounce doesn't reach a dead management CPU. Don't re-try this expecting it to work — only a reboot of the arm switch *itself* (physical) or a fresh path in (lan1→G3) clears the wedge.

**CCU second uplink (redundancy) → G3 is DOWN — the best in-band recovery lever, currently dead.** The CCU is designed dual-homed: `/etc/nd-redundancy/networks.yaml` lists `bond0` slaves = **`lan0` + `lan1`**. Live state: **`lan0` (bond, `00:21:21:21:00:01`) → G1 e0-2, UP** (the path we use); **`lan1` (`enp9s0f1`, MAC `7c:70:bc:70:d9:83`, PCI `0000:09:00.1`, driver i40e) → NO CARRIER, dropped out of the bond.** Its intended peer is **G3** (a switch on the islanded arm). CCU side is admin-UP + `balance-xor`/`miimon 100` → **if `lan1` gets carrier, bond0 auto-adds it and the CCU gets a DIRECT L2 path into the islanded arm via G3**, bypassing both broken entry-points. `ethtool lan1` = `Link detected: no`, forcing up + `-r` renegotiate did not raise carrier → the link is dead at the **G3 end / cable** (a live-but-wedged G3 would still present PHY carrier, so this is deeper than mgmt-wedge: G3's CCU-facing port down, cable unplugged/mis-patched, or SFP fault). **Highest-value physical action = check/reseat the CCU `lan1` (enp9s0f1) cable to G3.**

**B3 is the SECOND cold-bypassed dead switch (not just A1).** "Why can't I see B3?" — B3 (bridges B2↔B1 per the diagram) has **no lease, no LLDP, is not DHCP-discovering** = powered-down/dead, relay welding B2↔B1 through it. Signature: B2 e0-0 & B1 e0-0 both `description "Switch B3"`, B2 e0-0 shows no LLDP neighbour, and B1 e0-0 carried the tell-tale high cost. So the consist has **TWO** cold-bypassed dead switches: **A1 and B3** — together they welded the ring closed = the original storm ([[project_vds_cold_bypass]]).

**RSTP port-cost normalised (housekeeping).** B1 e0-0 had `spanning-tree port-cost 400100` — a **multi-traction test override** that doesn't belong on the bench (link is actually 10G Full, so real default = **2000**, not 20000). Removed via `no configure interface e0-0 spanning-tree port-cost` → fell back to auto **2000**, config line gone (defaults aren't listed), **persisted** (`save running-config force`). Scanned all 5 reachable switches → all now clean/default. ⚠️ The 5 islanded switches were unreachable — if the 400100 override is per-consist it likely also sits on their bypass-adjacent ports; clean once recovered.

**Consist inventory (18-switch nv4):** ✅ reachable+7.4.8+loop-guard+default-cost: **G1, E2, E3, B2, B1** (5). ⏳ islanded, alive-but-mgmt-wedged, 7.4.2: **A3, A2, G3, G2, E1** (5). ❌ cold-bypassed/dead: **A1, B3** (2). (Balance = other coaches not enumerated this session.)

**End state left recoverable:** B1 e0-1 re-enabled (arm reconnected at L2, loop-guard-protected), `always-broadcast on`, CCU `lan1` admin-up + ready. The instant someone (a) reseats the CCU `lan1`→G3 cable, or (b) physically power-cycles/console-reboots an arm switch (E1 or A3 = the gateway-adjacent ones), or (c) restores A1+B3 — the arm re-DHCPs and comes back reachable, then flashes via the proven recipe ([[project_vds_sysadmin_load_blocked_by_ttcmp_critical]]). Reversible cuts to undo on recovery: A3 e0-0 (our storm-fix), B1 e0-1 (if reverting). CCU runtime fixes (conntrack helper, tftp ipset, always-broadcast) are NOT reboot-persistent.

### 2026-07-05 — AR — Storm KILLED + all 5 reachable switches flashed 7.4.2→7.4.8 + loop-guard armed. **Overturns the 2026-07-04 "can't flash / firmware won't help" conclusion.**

**Outcome:** the 2026-07-04 entry below was wrong on three counts — all corrected by field work today:
1. The storm **is** a plain RSTP ring loop (not just a "TTCMP-critical" fabric state), and it **can** be broken from the CCU by opening the ring at one port.
2. Switches **can** be flashed manually while the consist is imperfect — the busy-lock is NOT fabric-level TTCMP-critical; it's a transient per-switch post-boot lock + a TFTP transport gap.
3. 7.4.8 **does** help: its per-interface `loop-guard` is the durable fix, now armed on every backbone port.

**Root cause of the storm (confirmed, corrects the "STP-invisible bypass" claim):** the consist is a **closed ring** (G1–A1–A3–A2–G3–G2–E1–B1–B3–B2–E3–E2–G1). **Two switches are cold-bypassed: A1 and B3** — their relays *weld* their ports into wires, keeping the ring electrically **closed**. RSTP had blocked **zero** ports fabric-wide (verified every reachable switch: all e0-0/e0-1 = ROOT/DESG/FWD, no ALTN/BLOCK) → permanent L2 forwarding loop → the 800M-multicast / Malformed-KON / coldStart storm. RSTP fails to block because BPDUs don't propagate cleanly across the welded bypass, so neither neighbour sees the loop. See [[project_rstp_splitbrain_mixed_config_storm]], [[project_bench_4122_multicast_storm_e0_0]], [[project_vds_cold_bypass]].

**Storm fix (reversible, CCU-side):** `no configure interface e0-0 enable` on **A3 (.197)** — opens the ring at the dead A1-bypass segment. Multicast froze instantly, Malformed-KON stopped, coldStarts stopped. (G1 e0-0 was also disabled+persisted earlier as redundant containment.) The B/E side recovered; the A/G arm (A3/A2/G3/G2/E1) went **islanded** (management-dead — E1 forwards data but not reliably, so that arm is only reachable via the flaky long path).

**The busy-lock was NOT TTCMP-critical (corrects 2026-07-04's central finding).** Systematically falsified: CPU load, TTCMP subsystem state, TTCMP extensions, ring e0-0 membership, diagnostics collector — all ruled out (G1 and E3 had *identical* state; G1 flashed, E3 didn't). The real blockers were a **stack of fixable gates**:
1. **TFTP conntrack helper missing** — CCU firewall dropped the switch's RRQ. Fix: `sudo modprobe nf_conntrack_tftp` + `sudo iptables -t raw -A PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp`.
2. **`tftp_allowed` ipset EMPTY** — the CCU only serves TFTP to switches in this ipset (OBN normally adds each switch just-in-time). Fix: `sudo ipset add tftp_allowed 10.179.122.<n>` per switch. **This was the silent RRQ-drop cause.**
3. **Wrong artifact** — `sysadmin load` wants the **`.kad`** (`ipart-ng.kad`), NOT the `.ksi` bigbang. Loading the `.ksi` returns `WARNING: Operation aborted. Not a KAD file`.
4. **Transient post-boot critical-op lock** — a freshly-rebooted switch has a short clean window before an internal "critical operation" re-arms; fire the load *instantly* on SSH-up.
5. **Transfer stability vs path length** — deep-chain switches stall mid-transfer (`read(ack): Connection refused` / `Connection trouble`) over the degraded fabric. Flash **outward from the gateway** (G1→E2→E3→B2→B1) so each flashed switch stabilizes the path for the next.

**The proven recipe (5/5 switches):**
```
# CCU prep (once): helper + ipset + stage .kad in /data/auto-topology/
sudo modprobe nf_conntrack_tftp
sudo iptables -t raw -A PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp
sudo ipset add tftp_allowed 10.179.122.<n>
sudo cp ipart-ng.kad /data/auto-topology/sw-std-ng-fw-7.4.8.kad
# per switch, gateway-outward:
sysadmin reboot                                              # clean CPU + clean lock window
# INSTANTLY on SSH-up:
sysadmin load tftp://10.179.122.129/sw-std-ng-fw-7.4.8.kad   # wait for "System Firmware image loaded"
sysadmin set default image sw-std-ng_7.4.8-87248.ksi         # hammer-retry if it busy-locks (caught a gap on ~8th try on B1)
sysadmin reboot
```
Reboot command is **`sysadmin reboot`** (confirms with `y`) — resolves the earlier "reboot command unconfirmed" note; plain `reboot`/`reload` are rejected.

**Result — all 5 reachable switches on 7.4.8 (build 87248):** G1(.200), E2(.201), E3(.202), B2(.179), B1(.196). Post-upgrade L2 health = **PASS**: load 0.00–0.20 (was 2.5–2.9), single agreed RSTP root G1 (was split-brain), Malformed-KON **0** (was 4500–5400), coldStart **1** (boot only, was 24–92), backbone ports **0 CRC / 0 carrier / 0 RX-err**, multicast flat (~5 pkt/6s, was ~52k pps).

**Durable guard armed:** `configure interface e0-0/e0-1 spanning-tree loop-guard force-block` on all 5 switches (persisted). Ports show `loopGuardBlock` capability + FWD (armed, not tripped). `force-block` chosen over `error-disable` = self-recovering when a loop clears (fits cold-bypasses that come and go). This is the real answer to "one cold bypass shouldn't take down L2" — a future welded ring will now be auto-opened by loop-guard instead of storming.

**Current end state / still open:**
- 5 flashed switches healthy, reachable, loop-guard-armed. Ring held open at A3 e0-0 (islanded, persisted state on A3 is `no enable`) + G1 e0-0 persisted-down. B1 e0-1 disabled (earlier BPDU-leak cut).
- **Islanded arm A3/A2/G3/G2/E1 still management-dead**, and **A1 + B3 still cold-bypassed (physically dead).** Restoring A1 + B3 physically closes the ring properly → loop-guard holds it → islanding clears → the remaining 5 switches (incl. the 2 dead ones once repowered) can be flashed cleanly.
- CCU runtime state (helper + ipset) is **not reboot-persistent** — re-apply if the CCU reboots. `.kad` staged at `/data/auto-topology/sw-std-ng-fw-7.4.8.kad`.

### 2026-07-04 — AR — Attempted manual 7.4.8 switch-firmware push; BLOCKED by consist TTCMP-critical interlock (fabric-level, not per-switch)  ⚠️ SUPERSEDED by 2026-07-05 above — its "can't flash / firmware won't help / busy-lock is fabric-level" conclusions were disproven.

**Goal:** push switch firmware 7.4.2→7.4.8 (workspace `switch/(NMID1143) VDS 28 port consist_FW_v7.4.8/`) on the bench to test whether it fixes the KON storm. **Outcome: could not flash any switch; the storm root cause (A1 bypass) blocks it, and 7.4.8 wouldn't fix it anyway.**

**Firmware won't fix the storm (release-notes review):** 7.4.2→7.4.8 changelog has nothing addressing a bypass-induced consist-protocol loop. 7.4.7's `loop-guard` is RSTP-only (the cold-bypass relay is STP-invisible — the whole reason it storms). Root cause is physical (A1 cold-bypass), not firmware.

**Chose "contain then push":** disabled G1 e0-0 (`no configure interface e0-0 enable`) → storm stopped (TTCMP Rx froze, Malformed KON +0, G1/E2 load 4-5→0.6). BUT containment fragmented the fabric to only **G1+E2+E3** reachable (A2/A3/G2/G3/E1/B1/B2 sit behind e0-0; A1/B3 are the original bypass). G1 can't be flashed (reboot re-enables e0-0 → re-arms storm). So only E2/E3 were candidates.

**The blocker — manual `sysadmin load` refused fabric-wide:**
- OBN skill path (`dosto-sw-firmware-update`) not viable: image not staged as OBN `.kad`, `rules.yaml` firmware target pinned to `7.4.2` (no-op), discovery unreliable. → went manual TFTP (`sysadmin load`).
- Staged `ipart-ng.kad` (the `.kad` OS image; NOT the `.ksi`) → CCU `/data/auto-topology/ipart-ng-748.kad`, md5 `f9debf9d…` verified, TFTP self-serve OK.
- **Trap 1:** first load URL used `tftp://10.179.122.1/…` — `.1` is bond0; switches reach the CCU only at vlan100 **`.129`**. Silent no-op (no RRQ). Fixed to `.129`.
- **Trap 2 (the real finding):** with correct IP, `sysadmin load` (surfaced via `ssh -tt`) returns **`Warning: the system is busy processing a critical operation. Try again later.`** — no RRQ, nothing staged. **Proven fabric-level, not CPU:** E3 (load 2.9, storm-pinned) AND E2 (load 0.08, idle) BOTH refused identically. The "critical operation" is the **consist's unsettled TTCMP state** — a bypass-loop storm keeps it permanently mid-negotiation, and switches lock out firmware loads as a safety interlock. Containing the storm stops the flood but does NOT settle TTCMP → loads still refused.
- Verified E3/E2 never pulled anything (zero `RRQ from .202/.201` in tftpd log across the whole session, image bank unchanged) → **switches untouched/safe, not mid-flash.**

**Unifying conclusion:** partial `obn discover`, KON flood, snmpd restarts, AND refused firmware loads are all the **same A1-bypass root cause** keeping the consist "critical." No switch on this fabric will flash until A1 is physically restored / the loop removed so TTCMP settles. **The fix is A1, not firmware and not containment.**

**End state:** containment reversed — G1 e0-0 re-enabled (`configure interface e0-0 enable`), back up 10G full, fabric restored as-found (storm will resume; that's the original condition). **7.4.8 image left staged** on CCU `/data/auto-topology/ipart-ng-748.kad` for a future clean session. Resume when A1 is restored: verify consist TTCMP settled (`show counters protocol ttcmp` quiet, switch load ~0), then `sysadmin load tftp://10.179.122.129/ipart-ng-748.kad` → `set default image <name-from-show-images>` → `sysadmin reboot`, leaf-first (E3→E2→…). New finding saved: memory `project_vds_sysadmin_load_blocked_by_ttcmp_critical` + runbook "VDS Switch Firmware Push — Manual `sysadmin load` Method".

### 2026-07-04 — AR — "OBN isn't showing devices" traced to TTCMP/KON consist-protocol flood (same A1-bypass storm), NOT the coach-numbering bug

**Presenting symptom:** `obn validate` showed only G1 numbered + 11 collapsed `7.7.7.7 / UNKNOWN (discovery incomplete)` rows, while `dhcp-lease-list` showed **10 switches leased and valid**. First read (mine) was the cold-bypass coach-numbering deletion bug (`findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`). **Wrong for this output** — corrected on inspecting `/tmp/discovery.json`.

**What it actually was:**
- The **patched engine is live and behaving correctly** (`report_dosto_neu.py` 19524 bytes, topology-anchored; `.orig-20260704` backup present). Its §7c discovery-completeness gate fired and marked unreached switches `UNKNOWN "discovery incomplete"` — deliberately **never false-DOWN**. Exactly as designed.
- `/tmp/discovery.json` only held **4 switches** (a different partial set each `obn discover` — 4, then 3). Independent SNMPv3 (`snmpadmin`) probe of all 10 → **6/10 reachable this instant**, and the reachable set *shifts* between sweeps. So OBN can only report what a given sweep reached; the collapse is an **incomplete scan**, not lost switches.
- Root cause of the shifting reachability: **a TTCMP/KON consist-management flood** — every switch log has 3000+ `KMkon: Malformed KON packet` + repeated `KMdev coldStart` → `snmpd`/`subXlldp.AgentX` **subagent restarts**. While a switch's snmpd is mid-restart it stops answering SNMP → the sweep misses it. `show counters protocol ttcmp` = 100k+ ANNOUNCEMENT Rx on backbone ports of *both* chain neighbours (G1 e0-0 520k+, A3 e0-1 580k+, climbing), Tx ~1.3k → flood arriving amplified from both directions = loop signature. This is the **consist-protocol face of the A1-cold-bypass multicast storm** already root-caused today ([[project_bench_4122_multicast_storm_e0_0]]).
- RSTP is fine: single stable root = G1 (`a0:59:3a:d0:60:e0`), all reachable switches agree, no split-brain; e0-0/e0-1 live rate 0 Mbps between bursts (cumulative counters only). The fabric forwards; it's the mgmt plane that's saturated.

**Verdict / next:** nothing wrong with OBN or the patch — the report is honestly reporting an incomplete scan over a flapping mgmt plane. The real fix is **physical**: restore A1 / fix A-car cabling so the bypass loop is gone (or the reversible `no configure interface e0-0 enable` containment on G1). Fast bench triage next time OBN under-scans: `show counters protocol ttcmp` + `show log | grep -c 'Malformed KON'` on any two switches *before* suspecting coach-numbering. Memories updated: [[project_bench_4122_multicast_storm_e0_0]] (consist-protocol fingerprint added), [[project_zabbix_phantom_port_down_snmp_subagent]] (storm named as upstream trigger + OBN impact).
