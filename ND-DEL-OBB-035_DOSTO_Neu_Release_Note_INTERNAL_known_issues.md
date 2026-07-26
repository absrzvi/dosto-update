# DOSTO Neu HW & SW Release Note — INTERNAL known-issues annex

**Companion to:** `ND-DEL-OBB-035_DOSTO_Neu_HW_SW_Release_Note_v1.0.docx` (ÖBB-issued, customer-facing)
**Audience:** Nomad internal only — **do NOT issue to ÖBB.** The customer copy's "Omissions and Restrictions" section is deliberately kept high-level and free of ticket numbers / bench / R&D detail per the project's written-comms rule.
**Baseline covered:** switch fw 7.4.2 / config V8, Westermo AP fw 6.11.2-0, Nomad Connect 2025.2.1 (nd-obn 2.2.23), all four platforms (nv4/nv6/fv5/fv6).
**Compiled:** 2026-07-05.

This annex records the fuller set of known issues, workarounds, and open items behind the customer release note. Each entry notes whether it is surfaced (in reduced form) in the customer doc.

---

## 1. Westermo AP firmware — stage-vs-activate flakiness
- **What:** RT610LV (IbexOS) firmware pushes sometimes stage the image but do not activate it; two failure modes — (a) slow-but-fine (reboots late, self-recovers) and (b) genuine flash-trigger hang (`rpcFwFlash=2`, no reboot). OBN historically reported "success" on the SET echo without verifying activation.
- **Fix/workaround:** bug-11 patch (`westermo.py` post-flash verify) makes OBN report honestly; genuine hangs need a LuCI HTTPS firmware-upload bypass or a retry.
- **Refs:** TRIAG-8585 (upstream the v8 OBN hand-patches, incl. bug 11); KB `components/westermo-ap/firmware-activation.md`.
- **Customer doc:** YES — surfaced in reduced, non-ticketed form ("some APs report firmware as staged but not activated; re-triggered on next visit").

## 2. OBN AP-firmware batch push silently fails — CCU TFTP conntrack-helper gap
- **What:** `obn update f ap` batch pushes silently fail for most APs; only ~5 of ~15 succeed by conntrack race luck. The CCU firewall lacks the `nf_conntrack_tftp` helper + udp/69 CT rule.
- **Fix/workaround:** runtime `modprobe nf_conntrack_tftp` + iptables raw PREROUTING rule (wiped on every reboot). Durable fix pending in Puppet (`60-allow-management`).
- **Refs:** `dosto-tftp-helper-check` skill; TRIAG-8585 (infra item); KB `components/nomad-connect-obn/tftp-conntrack-helper.md`.
- **Customer doc:** NO — internal commissioning detail.

## 3. OBN coach-numbering drops bypassed switches — monitoring false-negative
- **What:** when a VDS switch is cold-bypassed, OBN's coach-numbering walk mis-numbers the switch that moves into the gap, dead-ends, and `normalise_devices()` silently deletes every switch it couldn't number — including healthy, SNMP-reachable ones downstream. Dropped switches are absent from the NMS report too, so nothing alarms on them.
- **Fix:** topology-anchored numbering + DOWN/UNPLACED rows (validated engine fix, prototyped on the bench). Cross-check OBN's switch count against `dosto-device-discovery`'s discovered count.
- **Refs:** `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`; memory `project_obn_drops_bypassed_switches`.
- **Customer doc:** NO — internal engine/monitoring detail.

## 4. fv5 / fv6 empty `obn report` — backbone-discovery.yaml config drift
- **What:** on some fv5/fv6 CCUs `obn report` returns empty because `/etc/obn/backbone-discovery.yaml` fell back to deb defaults (`report_module: GenericReport`, `train_type: mq`) instead of the DOSTO overrides.
- **Fix:** per train, set `report_module: DostoNeuReport` + correct `train_type` (nv4/nv6/fv5/fv6); enforce both in the Puppet template. NOT a package-version issue.
- **Refs:** memory `project_obn_fv6_train_type_unsupported`; KB `topics/fv5-topology.md`.
- **Customer doc:** NO — internal config/commissioning detail.

## 5. Open cabling faults (Stadler-side)
- **What:** a number of per-train physical cabling faults (wrong neighbour, AP/switch not connected, PHY faults on inter-coach trunks) are tracked in the cable-issues register. As of 2026-07-05 there are ~15 rows, several `OPEN` (Stadler action pending). These are outside Nomad's scope.
- **Refs:** `cable-issues-register.md` / `trackers/cable-issues-tracker.xlsx`.
- **Customer doc:** YES — surfaced generically ("a small number of open cabling faults are outside Nomad's scope and tracked separately").

## 6. Stadler-side firewall commissioning
- **What:** vlan7 firewall commissioning is a Stadler activity; on some trains the FW is not yet commissioned (Westermo answers ARP but ICMP behaviour indicates policy not applied). Does not affect the Nomad onboard-network L2 baseline.
- **Refs:** CLAUDE.md Phase 6 (Q1/Q2/Q3 FW probe); memory `feedback_fw_commissioning_not_blocker`.
- **Customer doc:** YES — surfaced generically (grouped with cabling as out-of-scope Stadler items).

## 7. box=Fzg / >127 octet limitation on 6-car/CAT/FV
- **What:** `factory up` train-ID caps at 0–127 (3rd IP octet); Fzg for 4736/4706/4705 is 129–231, so box=Fzg only fits 4734 (nv4). The v9 templates' remap-drop assumes train_id=Fzg. Do not `obn update c` a CAT train commissioned with box-id. Needs an R&D decision (fzg_id-key path).
- **Refs:** memory `project_box_fzg_breaks_127_octet_limit`.
- **Customer doc:** NO — internal commissioning/tooling detail.

---

## Open items still needed to finalise the customer doc (6 TBDs)
1. **Document Reference number** — confirm/assign per BMS-ENGI-INS-001 (currently `ND-DEL-OBB-035-RN-001-01`, placeholder).
2. **Approver name** — cover page + Document control table (×2).
3. **iperf3 version** — pull from a live CCU (`iperf3 --version`) when a train is next online; fleet was fully powered down 2026-07-05.
4. **WiFiTestTool version** — from the test engineer who ran validation.
5. **Ekahau version** — from the test engineer who ran validation.

(NMS version 2026.1.2 is filled. Modem/GPS NMIDs 1109/720 filled. Antenna NMID = N/A, Stadler-supplied. AT-DTR column removed — Alstom field, not applicable.)
