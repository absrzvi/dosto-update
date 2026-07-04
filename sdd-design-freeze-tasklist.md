# SDD Design-Freeze — Task List

**Purpose:** single come-back-to-it tracker for completing the DOSTO SDD design-freeze deliverables (SDD-002 freeze + SDD-003 ÖBB comment review). Update the **Status** and **Last touched** fields at the end of every session.

**Last updated:** 2026-06-21

## Documents in play

| Doc | Latest file | State |
|---|---|---|
| **SDD-002** (design-freeze technical description) | [design freeze/ND-DEL-OBB-035-SDD-002-01_v2.3.docx](design%20freeze/ND-DEL-OBB-035-SDD-002-01_v2.3.docx) | Freeze-ready for ordered scope **except QoS/DSCP write-back** (T1) |
| **SDD-003** (under ÖBB review) | [design freeze/ND-DEL-OBB-035-SDD-003-01_v3.10-tracked.docx](design%20freeze/ND-DEL-OBB-035-SDD-003-01_v3.10-tracked.docx) | **25/26 comments done; 0 blocked; 1 deferred (P4 commercial).** All answerable comments closed. **v3.10 is the single working version** (all authors "Abbas Rizvi", no "Claude"). Older versions v3–v3.9 in `design freeze/_archive_sdd003_versions/`. |
| Comment tracker | [design freeze/OEBB_SDD-003_Comment_Tracker.xlsx](design%20freeze/OEBB_SDD-003_Comment_Tracker.xlsx) | Source of truth for SDD-003 comment status |
| Coverage analysis | [findings/SDD-v2.2_vs_PM-deliverable-chain_20260601.md](findings/SDD-v2.2_vs_PM-deliverable-chain_20260601.md) | Why QoS is the one in-scope SDD-002 gap |

**Status key:** ☐ todo · ◐ partial/in-progress · ✅ done · 🔴 blocked (need input) · ⏸ deferred

---

## A. SDD-002 — design-freeze doc

- [⏸] **T1 — QoS / DSCP-per-VLAN policy write-back** — SKIPPED for now (decision 2026-06-21)
  - No ÖBB comment asks for QoS/DSCP details (confirmed: not in comment tracker or SDD-003 comments). T1 was a self-identified SDD-002 freeze-gap from the coverage analysis, not a review-comment response. Since the SDD-003 comment review is complete and nothing requires it, left out. **Revisit only if ÖBB requests QoS detail.**
  - If revived: add a real per-VLAN priority/DSCP section (not just the switch datasheet capability line). Values known from live fleet (verified t21 mangle TOS chains): mgmt `0xe0`, staff `0xc0`, gold/cf1 `0x40`, silver/cf2 `0x20`. Implemented via CCU mangle TOSMARK_SRC/DST chains + ipsets (tos_gold/silver/cf1/cf2). Output would be SDD-002 v2.4.
  - *Last touched: 2026-06-21 (skipped)*

---

## B. SDD-003 — items WE can complete (no external input)

> All 15 mechanical/reply items are already done in `v3-tracked`. Nothing open in this bucket right now.
> If ÖBB returns new comments, log them here.

- [x] (15 comments) ✅ done in v3-tracked — cross-refs, GPS re-nest, Remedyforce→ServiceNow, Fleetview→Nomad Insights, NTP chain, multitraction RSTP confirmations, portal window, Masterwagen def, network-planning xlsx ref, etc.

---

## C. SDD-003 — BLOCKED on inputs (the long pole)

Each needs an artifact or confirmation before the doc edit/reply can land. Comment #s are from the tracker.

- [x] ✅ **T2 — Data-center dimensioning sheet** → closed comments **#17, #137, #138** (2026-06-21)
  - Sheet filled: [design freeze/BMS-BDEV-FOR-028 CDC Dimensioning Sheet_OEBB-DOSTO-Neu.xlsx](design%20freeze/BMS-BDEV-FOR-028%20CDC%20Dimensioning%20Sheet_OEBB-DOSTO-Neu.xlsx).
  - Result: 5 MAR5 HA × 2 gbps = **10 gbps total**; **~10 trains/HA**; **120 Mbit/s guaranteed floor / ~230 Mbit/s typical peak** per train; fault case (4 HA) = 8 gbps, 120 floor held; 6th HA = capacity + N+1.
  - Replies drafted in [design freeze/SDD-003_replies_T2-dimensioning_2026-06-21.md](design%20freeze/SDD-003_replies_T2-dimensioning_2026-06-21.md); doc edits applied as tracked changes (§3.2.2.3, §5.6.2) in v3.2-tracked.
- [x] ✅ **T3 — Public-IP / NAT sharing ratio** → completed comment **#135** (2026-06-21)
  - 5 TUN-IPs `77.237.62.210–218` (one per HA); ~10 trains per public NAT IP; SNAT double-NAT model. Doc edit applied to §5.6.1 in v3.2-tracked.
- [x] ✅ **T4 — Wi-Fi channel plan / ACS policy** → closed comment **#11** (2026-06-21, v3.3)
  - Static plan from OBN templates: 2.4 GHz Ch 1/11, 5 GHz Ch 36/44, 80/20 MHz, 15 dBm, **no ACS** (statically assigned per coach type). Doc edit applied to §3. *(Internal-only, not surfaced to ÖBB: known 36/44 80 MHz overlap — optimisation item.)*
- [x] ✅ **T5 — VLAN 47 purpose + per-fleet applicability (FV/NV/CAT)** → closed comment **#141** (2026-06-21, v3.3)
  - VLAN 47 = ÖBB vending/payment ("Zahlung Verpflegungsautomat"), **family-dependent**: NV/FV (4734/4736/4706) use 47; CAT (4705) uses 48. Added VLAN 47 + VLAN 15 (multitraction transit) rows to §5.7 table; annotated VLAN 48 as CAT-only. Source: `vlans.j2` + `findings/iptables-validation_box1-t21_20260601.md`. *(VLAN 32 diagnostics also exists in templates but is per-train/optional — left out of the design-freeze table; raise separately if ÖBB wants it.)*
- [x] ✅ **T6 — Confirm internal Project ID = 51** → closed comment **#134** (already done v3-tracked; verified in v3.3)
  - No live "515" in body — ÖBB's 515 edit was rejected, 51 restored; address-range note reconciled. Replies 314/315.
- [x] ✅ **T7 — Updated VLAN / comm-flow diagram** → closed comment **#146** (2026-06-21, v3.5)
  - Replaced the 2024 diagram at §5.7.1 with a current SVG ([diagrams/SDD-003_5.7.1_VLAN_commflow_v3_2026-06-21.svg](design%20freeze/diagrams/SDD-003_5.7.1_VLAN_commflow_v3_2026-06-21.svg)): structured VLAN table (Stadler/Nomad domains) + end-to-end flow strip. Adds VLAN 15 + 47, marks 48 CAT-only; all Nomad VLANs → MAR5 tunnel → Internet (firewall-verified t21/t39/t42, RFC1918 dropped).
  - **v3.5 adds a second figure**: Komponenten-Kommunikationsmatrix ([diagrams/SDD-003_5.7.1_component_matrix_2026-06-21.svg](design%20freeze/diagrams/SDD-003_5.7.1_component_matrix_2026-06-21.svg)) — recovers the old bus diagram's interconnect detail (which components talk in which flow class: ZFR-hub / FIS→RCU / TCMS / Landseite) as a clean grid with H=hub/Z=target markers. Both figures embedded as SVG + PNG fallback, tracked changes.
- [x] ✅ **T8 — Correct Portal-Lite screenshots + on-train URLs** → closed comment **#72** (2026-06-21, v3.9)
  - Replaced the reviewer-deleted old screenshots with 5 current Portal-Lite page captures (index, connecttoweb, terms, wifisuccess, imprint), each with its on-train URL, + a standalone comment. Source: `dosto.lite.cms.nomadrail.com` (engineer-supplied URLs), captured via headless Chrome → [design freeze/portal_screenshots/](design%20freeze/portal_screenshots/).
- [x] ✅ **T9 — ÖBB portal spec (Vorgabe)** → closed comment **#70** (2026-06-21, v3.10)
  - Engineer confirmed the as-built Portal-Lite (screenshots #72/v3.9) **conforms to the ÖBB-Vorgabe**. Added body sentence ("Die dargestellte Portal-Lite-Lösung entspricht der ÖBB-Vorgabe.") + standalone comment in §3.3.1.
- [x] ✅ **T10 — portal naming + ~03:00 maintenance window** → closed comments **#60, #61, #62** (2026-06-21)
  - Naming disambiguated in body (Captive Portal = Portal Lite; Railnet Portal = Engage Portal); ~03:00 window aligned to Cityjet/Railjet (#61/#62 already in v3-tracked).
- [x] ✅ **T11 — Confirm authoritative NTP source** → closed comment **#148** (already done v3-tracked; verified in v3.3)
  - Chain: switches/APs → CCU 10.179.x.1 → public internet NTP; CCU serves vlan7 Stadler via SNAT. Reply 316. *(Internal note: ZUG-LAND Row 21 "backend 10.178.13.1" is a planning-doc error — flagged, xlsx/SDD left untouched per your instruction.)*

---

## D. Watch / deferred

- ⏸ **#154 (P4) — commercial dispute** on the "after-3-years Variation Order" framing.
  - Handled by you via separate email; doc left as-is. Tracked here for visibility only — not a doc task.

---

## E. Next actions (rolling)

1. **T1 (QoS write-back)** — only SDD-002 item we can close now without waiting on anyone. Produces v2.4.
2. ~~T2 (dimensioning sheet)~~ ✅ done 2026-06-21 — cleared #17/#137/#138 + #135 (T3). Now in v3.2-tracked.
3. ~~T4/T5/T6/T10/T11~~ ✅ done 2026-06-21 (v3.3-tracked) — Wi-Fi plan, VLAN 47/15 table + fleet split, Project ID 51, portal naming/window, NTP source.
4. ~~T7 (#146 diagram)~~ ✅ done 2026-06-21 (v3.4-tracked).
5. ~~T8 (#72 Portal screenshots)~~ ✅ done 2026-06-21 (v3.9).
6. ~~T9 (#70 Portal Vorgabe)~~ ✅ done 2026-06-21 (v3.10) — conformance confirmed.
7. **SDD-003 is COMPLETE** — all 25 answerable comments closed; only #154 (P4 commercial dispute) deferred, handled by you via email. Next design-freeze work is **T1 (QoS write-back on SDD-002 → v2.4)**, the only remaining freeze-gap item.
