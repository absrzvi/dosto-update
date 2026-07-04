const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
        WidthType, ShadingType, PageNumber, PageBreak } = require("docx");

const MONO = "Consolas";
const CW = 9026; // A4 content width with 1" margins

function h1(t){ return new Paragraph({ heading: HeadingLevel.HEADING_1, children:[new TextRun(t)] }); }
function h2(t){ return new Paragraph({ heading: HeadingLevel.HEADING_2, children:[new TextRun(t)] }); }
function p(...runs){ return new Paragraph({ spacing:{ after: 120 }, children: runs.map(r => typeof r === "string" ? new TextRun(r) : r) }); }
function b(t){ return new TextRun({ text: t, bold: true }); }
function bullet(t){ return new Paragraph({ numbering:{ reference:"bullets", level:0 }, spacing:{ after: 60 }, children:[ new TextRun(t) ] }); }
function num(t){ return new Paragraph({ numbering:{ reference:"numbers", level:0 }, spacing:{ after: 60 }, children:[ new TextRun(t) ] }); }
function code(lines){
  return lines.map(l => new Paragraph({
    spacing:{ after: 0 },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children:[ new TextRun({ text: l, font: MONO, size: 16 }) ]
  }));
}
const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const borders = { top: border, bottom: border, left: border, right: border };
function cell(t, w, hdr=false){
  return new TableCell({ borders, width:{ size: w, type: WidthType.DXA },
    shading: hdr ? { fill: "D5E8F0", type: ShadingType.CLEAR } : undefined,
    margins:{ top:60, bottom:60, left:100, right:100 },
    children:[ new Paragraph({ children:[ new TextRun({ text: t, bold: hdr, size: 18 }) ] }) ] });
}
function table(widths, rows){
  const total = widths.reduce((a,x)=>a+x,0);
  return new Table({ width:{ size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r,i) => new TableRow({ children: r.map((c,j)=>cell(c, widths[j], i===0)) })) });
}

const children = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 60 }, children:[ new TextRun({ text: "Coupled-Train Network Test Report", bold: true, size: 40 }) ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 60 }, children:[ new TextRun({ text: "OBB DOSTO 4736-110 (Fzg 138) + 4736-119 (Fzg 147)", size: 26 }) ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 240 }, children:[ new TextRun({ text: "Test date: 2026-06-12  |  Nomad Digital  |  Prepared for: VDS Rail Support and OBB / Stadler  |  v1.1 (port-cost finding corrected per VDS; diameter computed)", size: 20, color: "555555" }) ] }),

  h1("1. Executive Summary"),
  p("On 2026-06-12 Nomad Digital performed a controlled coupling test of two 6-car DOSTO units (36 consist switches combined) to reproduce the multicast storm observed on a coupled pair in early June, and to evaluate the RSTP max-age concern raised by VDS support. Key outcomes:"),
  num("No broadcast storm occurred. RSTP converged to a single root with the redundant coupler link correctly blocked."),
  num("A continuous RSTP topology-change (TC) condition was found: every switch in both trains flushed its MAC tables approximately every 2 seconds. It was traced to the active coupler link, whose two ends carried mismatched administratively-configured port-costs (137,999,999 on the 138 end / 146,999,999 on the 147 end), and stopped immediately when both ends were set to 20,000. VDS has since confirmed these values are within the supported range (up to 200,000,000, stored in uint32) and do not overflow; the asymmetry between the two ends of the point-to-point link is the suspected driver of the unresolving designated-role negotiation (Finding F3)."),
  num("The max-age concern is confirmed as a real and immediate risk: the merged network operated at a measured diameter of 31 hops, with the far extremity (F2-147) sitting at exactly 20 hops from the root - on the default 20-hop BPDU horizon, with effectively no margin. Root placement between the two priority-0 bridges is decided by MAC tie-break, i.e. not guaranteed (Finding F2)."),
  num("User-visible failures occurred while coupled: blank CCTV panels on the cab HMI, passenger displays reverting to the OBB logo (ZFR unreachable), and high perceived latency - while the switch fabric itself was healthy and lightly loaded. Evidence points at the interaction of the two consists' firewall-routed VLANs when VLAN 5 is bridged directly across the coupler (Finding F6). We ask Stadler to review the intended inter-consist CCTV design."),
  num("One consist switch (nv6-C2-v8-147, coach C of 4736-119) lost power mid-day and was bypassed by its hardware relays; coach C cameras and access points were down from that moment (Finding F4)."),
  num("After physical decoupling, at least two coupler links remained electrically alive and flapping, repeatedly re-merging the two networks. Link state must be verified after any decoupling (Finding F5)."),

  h1("2. Test Configuration"),
  table([2300, 3363, 3363], [
    ["Item", "4736-110 (Fzg 138)", "4736-119 (Fzg 147)"],
    ["Consist switches", "18 (nv6-*-v8-138)", "18 (nv6-*-v8-147); C2 lost during test"],
    ["RSTP timers", "Hello 2 s, Max Age 20, Fwd Delay 15 (defaults)", "identical"],
    ["Priority-0 bridge", "nv6-D1-v8-138 (a0:59:3a:d0:59:20)", "a0:59:3a:d0:73:a0"],
    ["Coupler trunk config", "native VLAN 999, allowed VLANs 5 and 15, broadcast rate-limit 1M", "allowed VLANs 5 and 15 (native VLAN statement missing - template gap)"],
    ["Coupling", "B-end to B-end, cross-wired: B1-147 to B3-138 (active), B1-138 to B3-147 (blocked)", ""],
  ]),
  p(""),
  p("Monitoring: RSTP and Coupled-Mode debug logging (configure system logging debug rstp,coupled) enabled on all 36 switches; packet-rate watchers on both CCUs; full spanning-tree and FDB harvests archived (attachment list, Section 7)."),

  h1("3. Findings"),
  h2("F1 - Convergence was correct"),
  p("All 36 switches agreed on a single root (priority 0, a0:59:3a:d0:59:20 = nv6-D1-v8-138). The redundant coupler link was blocked exactly as designed (B3-147 e0-2 ALTERNATE/BLOCKING). All four coupler ports showed zero CRC and zero carrier-false errors. Byte counters reconciled across both link pairs, confirming the cross-wired cabling map."),

  h2("F2 - Max-age operating margin (VDS advisory confirmed as a real risk)"),
  p("Root path costs harvested from all switches (root = nv6-D1-v8-138, cost 0; 2,000 cost units per 10G hop) give the true operating geometry of the merged fabric. The root sat near the centre of train 138, so that consist's far extremity (B1-138) was only 11 hops out. The far consist, reached across the coupler, was much deeper: its extremity nv6-F2-v8-147 measured a root path cost of 40,000 = exactly 20 hops - sitting precisely on the default 20-hop max-age BPDU horizon. The end-to-end network diameter (extremity of 138 to extremity of 147) was therefore 11 + 20 = 31 hops."),
  p("This is a worse position than a margin estimate would suggest: the composition was not comfortably inside the horizon, it was at it. The fabric stayed converged only because the message-age increment had not quite tipped a far-end port to discard. The margin exists at all only because the elected root happened to fall near the centre of the merged chain - each train carries a priority-0 bridge and the MAC tie-break decides which wins. An unfavourable election, or any added depth, pushes the far end past the horizon, partitions the tree, unblocks the redundant coupler link and closes a genuine L2 loop."),
  p(b("Worst-case evaluation (requested by VDS): "), "the supported max-age ceiling is 38 (the firmware enforces 2 x (ForwardDelay - 1) >= MaxAge). max-age 38 gives an effective BPDU reach of roughly 36 hops, which covers the measured 31-hop diameter of a 2 x 18 composition with usable margin. A 3 x 18 composition would add a further ~18-20 hops of diameter (roughly 50 hops total), exceeding even max-age 38 and the ~40-node ring guidance from VDS; we read this as no supported RSTP topology for 3-unit multi-traction."),
  p(b("Recommendation: "), "raise forward-delay to 20 first, then max-age to 38, on all switches (order matters - the firmware rejects max-age 38 at the default forward-delay 15). This covers all 2-train compositions regardless of root placement. It does not make 3-train compositions viable."),
  p(b("Separate physical anomaly found in the same data: "), "two switches on 4736-119 (nv6-B3-v8-147 and nv6-F3-v8-147) reported root path costs of 414,100 and 418,100 - each consistent with one sub-10G (approximately 100 Mbps Fast-Ethernet) link in its path to the root, rather than the expected 10G backbone. This is an inter-coach or intra-coach link running degraded and is unrelated to the coupler; it is logged for cabling/SFP inspection."),

  h2("F3 - Continuous topology-change condition, root-caused to asymmetric coupler port-cost"),
  p("With debug logging enabled, every switch in both trains logged a TC arrival plus \"Flushing all entries\" approximately every 2 seconds, continuously. A solo control train of the same fleet and firmware showed zero such events over the same observation method. The origin was the active coupler link: both ends repeatedly exchanged designated proposals within the same second - a role negotiation that never settled:"),
  ...code([
    "nv6-B1-v8-147 (active coupler port e0-2):",
    "  02:02:10  e0-2 sending designated proposal",
    "  02:02:11  e0-2 received designated proposal",
    "  02:02:13  e0-2 transmitting an agreement",
    "  02:02:13  e0-2 sending Tc",
    "",
    "nv6-B3-v8-138, representative 2-second cycle (continuous for >40 min):",
    "  03:40:22  e0-1 received Tc",
    "  03:40:22  e0-0 Flushing all entries.",
    "  03:40:22  e0-0 sending Tc",
  ]),
  p(""),
  p("The two ends of the active coupler link carried different administratively configured port-cost values: 137,999,999 on the 138 end (B3-138) and 146,999,999 on the 147 end (B1-147). Setting both ends to 20,000 stopped the condition at the exact second of the change - the TC/flush event count froze and never advanced again:"),
  ...code([
    "nv6-B3-v8-138 log:",
    "  03:52:44  e0-2 Changing PortCost to: 20000     <- last TC-related event in the log",
    "  (TC/flush event count frozen at 2,519 from this moment; topology unchanged,",
    "   redundant link still ALTERNATE/BLOCKING)",
  ]),
  p(""),
  p(b("VDS response (confirmed): "), "port-cost values up to 200,000,000 are supported and stored in a uint32, so the configured values do not overflow. The rate-limit feature does not apply to management packets, so BPDUs are exempt. This refutes the overflow hypothesis. The remaining open question is therefore narrower: on a point-to-point coupler link, can large but unequal port-costs on the two ends sustain the continuous designated-role re-negotiation observed here? We will standardise symmetric, sane coupler port-costs (20,000) in our templates regardless, which is already shown to stop the condition."),
  p("Operational impact of the condition while it was active: a fleet-wide MAC-table flush every 2 seconds converts forwarded unicast into flooded unicast across 36 switches. Combined with IGMP snooping being disabled (so the ~3,000 pps of VLAN-5 camera multicast floods all ports by design), the fabric ran in a permanently degraded flood state - a credible precursor to the storm observed in June."),

  h2("F4 - Consist switch failure during the test (4736-119, coach C)"),
  p("nv6-C2-v8-147 was alive at 10:02Z and gone by 11:13Z: no DHCP lease, and LLDP on its neighbours showed the backbone passing straight through (hardware bypass relays). Coach C cameras and access points were down from that point (22 of 24 APs leased). The unit needs a physical power/hardware check. Note that a switch power-cycling repeatedly would engage/disengage its bypass relays and flap the backbone - an additional train-internal source of topology churn."),

  h2("F5 - Decoupling did not disconnect the network"),
  p("After the trains were physically decoupled and coupling cables reportedly removed, the switches of 4736-119 repeatedly re-elected the root bridge of 4736-110 - the trains were still electrically connected, and the surviving link(s) were flapping:"),
  ...code([
    "nv6-C1-v8-147 root elections (local clock):",
    "  02:53:27  new Root Bridge elected: 4096/a0:59:3a:d0:75:00",
    "  02:53:27  new Root Bridge elected: 0/a0:59:3a:d0:73:a0   (own root)",
    "  02:53:28  new Root Bridge elected: 0/a0:59:3a:d0:59:20   (other train!)",
    "  02:53:38  new Root Bridge elected: 0/a0:59:3a:d0:73:a0",
    "  02:57:14  new Root Bridge elected: 0/a0:59:3a:d0:59:20   (other train, post-decoupling)",
  ]),
  p(""),
  p("Administratively disabling B1-147 e0-2 caused RSTP to fail over to the second supposedly-removed link (B3-147 e0-2) and the foreign root persisted. A marginal or half-seated coupler cable produces continuous link flaps, and every flap is a topology change that flushes MAC tables across the entire train. We recommend coupler cable/contact inspection on this pair, and that decoupling procedures include a port link-state verification."),

  h2("F6 - User-visible CCTV / passenger-display failures while coupled (for Stadler review)"),
  p("Symptoms reported by the driver while coupled: own-train CCTV panels blank on the cab HMI; passenger information displays reverting to the OBB logo (which Stadler advises indicates the ZFR is unreachable); high perceived latency. Throughout, the switch fabric was healthy: coupler utilisation ~3 Mbps on a 1G link, zero port errors, and both Stadler firewalls alive and commissioned on the vlan7 interconnect (110: 172.19.197.1; 119: 172.19.201.129 - note the .129 host address for odd vehicle numbers)."),
  p("Device addressing is static and vehicle-encoded, so duplicate IP addresses between the two trains are not possible. The anomaly we can demonstrate from the switch FDBs is the firewalls' source MACs circulating on both trains:"),
  ...code([
    "FW MACs: 00:90:e8:c5:3d:9d = FW of 4736-110, 00:90:e8:cb:5d:c9 = FW of 4736-119",
    "",
    "nv6-A3-v8-147 (FDB excerpt, while coupled):",
    "  VLAN 15  00:90:e8:c5:3d:9d  e0-1   <- other train's FW, via backbone",
    "  VLAN  5  00:90:e8:c5:3d:9d  e0-1   <- other train's FW in local camera VLAN",
    "  VLAN  9  00:90:e8:cb:5d:c9  e0-1   <- own FW arriving from backbone direction",
    "  VLAN  2  00:90:e8:cb:5d:c9  e0-1   <- own FW arriving from backbone direction",
    "",
    "After VLAN 5 was removed from the coupler trunk (11:00:40Z), the cross-train",
    "VLAN-5 entries aged out and did not return; the other train's FW MAC remained",
    "only in VLAN 15 (the transit VLAN)."
  ]),
  p(""),
  p("Working hypothesis: when the two consists are coupled, inter-consist traffic is intended to transit via VLAN 15 (relayed by the Stadler firewalls), while our coupler trunks additionally bridge VLAN 5 directly. Two parallel paths between the same endpoints - one bridged, one firewall-relayed - cannot be detected by RSTP because the legs are in different VLANs, and circulating frames disturb the firewalls' forwarding state. This would also degrade services that never cross the coupler (display-to-ZFR is routed VLAN 3 to VLAN 2 through the same firewall). Removing VLAN 5 from the coupler trunk verifiably cleaned the switch FDBs, but a lasting recovery of the displays was not confirmed before the test window ended, so this remains a well-evidenced hypothesis rather than a proven root cause - the C2 switch failure (F4) and the flapping coupler links (F5) are compounding factors in the same time window."),
  p(b("Questions for Stadler: "), "(1) What is the intended inter-consist CCTV path - direct VLAN-5 bridging across the coupler, firewall relay via VLAN 15, or both? (2) Should the passenger-display-to-ZFR path be affected by coupling at all? (3) Can the firewall logs for both vehicles for 2026-06-12 09:55Z-11:30Z be reviewed for state or routing anomalies?"),

  h2("F7 - Additional observations"),
  bullet("Odd-numbered vehicles place the Stadler firewall vlan7 address at host .129 (e.g. Fzg 147: 172.19.201.129), even-numbered at .1. Documentation and monitoring probes that assume .1 produce false 'unreachable' results for odd vehicles."),
  bullet("One coupler trunk (B1 of 4736-119) is missing the native-VLAN statement present on its counterparts - configuration template gap, will be corrected by Nomad."),
  bullet("No cross-train leakage of the CCU redundancy multicast (239.0.0.1) was observed in this composition."),

  h1("4. Timeline (UTC, 2026-06-12)"),
  table([1500, 7526], [
    ["Time", "Event"],
    ["~09:55", "RSTP/coupled debug logging enabled on cab switches and root bridges (later extended to all 36)."],
    ["~10:00", "Trains coupled, B-end to B-end. Convergence correct (F1)."],
    ["10:02-10:20", "Full STP sweep: single root, 31-hop diameter, far end at 20 hops / on the max-age horizon (F2). Continuous TC churn discovered on all switches (F3)."],
    ["~10:30", "nv6-C2-v8-147 found dead / hardware-bypassed (F4); was alive at 10:02."],
    ["10:32", "Port-cost experiment: active coupler link set to 20,000 - TC churn stops at the same second (F3)."],
    ["10:37-10:40", "First short VLAN-5 prune test (2.5 min) - no visible change on HMI."],
    ["11:00:40", "VLAN 5 removed from both coupler ports of 4736-110; by 11:07 cross-train VLAN-5 FDB entries cleared (F6). Driver initially reported partial recovery; not sustained."],
    ["~11:09", "Trains physically decoupled; foreign root re-elected repeatedly on 4736-119 via still-live flapping links (F5)."],
    ["11:19-11:25", "B1-147 coupler port disabled; failover to second live link observed; 119 CCU connectivity lost (cellular)."],
    ["16:50-17:00", "Single-cable recoupling attempted; no link on any coupler port (other train powered down). Test ended."],
  ]),

  h1("5. Recommendations"),
  h2("For VDS Rail"),
  num("Port-cost width and BPDU rate-limit exemption: answered by VDS (no overflow; BPDUs exempt) - now closed. Remaining question: whether unequal port-costs across a point-to-point link can sustain the role re-negotiation seen in F3."),
  num("Max-age: measured diameter is 31 hops for 2 x 18; we will apply forward-delay 20 / max-age 38 (effective reach ~36 hops). Please sanity-check this against the worst-case evaluation in F2, and confirm 3 x 18 (~50 hops) has no supported RSTP topology."),
  num("Review the attached RSTP debug traces for any further anomalies, once the known configuration mismatches (coupler native-VLAN, addressing) are corrected and the test re-run."),
  h2("For OBB / Stadler"),
  num("Physical inspection of consist switch nv6-C2 (coach C) of 4736-119 - lost power during the test; coach C cameras and APs down."),
  num("Coupler cable/contact inspection on this pair - links remained electrically alive and flapping after decoupling."),
  num("Clarify the intended inter-consist CCTV design (direct VLAN-5 bridge vs VLAN-15 firewall relay) - Finding F6."),
  num("Review firewall logs of both vehicles for the test window (09:55Z-11:30Z)."),
  num("Advise whether 3-unit multi-traction is operationally required for this fleet (relevant to the RSTP scaling limit)."),

  h1("6. Configuration State After the Test"),
  p("All changes made during the test are runtime-only and revert on vehicle power-cycle: RSTP debug logging on all switches of both trains; VLAN 5 removed from the coupler trunks of 4736-110; port-cost 20,000 on the active coupler ports. No startup configurations were modified."),

  h1("7. Attachments"),
  bullet("4736-110_fzg138_harvest.txt / 4736-119_fzg147_harvest.txt - full spanning-tree, FDB, interface and log harvests of all 36 switches while coupled."),
  bullet("tc_trace_138.txt / tc_trace_147.txt - per-switch RSTP debug log captures during the TC condition."),
  bullet("tc_trace_147_solo.txt - RSTP debug capture of 4736-119 after decoupling (flapping-link evidence)."),
  bullet("CCU packet-rate watcher logs, both vehicles."),
  p(""),
  p(new TextRun({ text: "Contact: Abbas Rizvi, Nomad Digital - abbas.rizvi@nomadrail.com", size: 20, color: "555555" })),
];

const doc = new Document({
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style:{ paragraph:{ indent:{ left: 540, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style:{ paragraph:{ indent:{ left: 540, hanging: 270 } } } }] },
  ]},
  styles: {
    default: { document: { run: { font: "Arial", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "1F4E79" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [ new Paragraph({ alignment: AlignmentType.RIGHT, children: [ new TextRun({ text: "Nomad Digital - DOSTO Coupled-Train Test Report - 2026-06-12", size: 16, color: "888888" }) ] }) ] }) },
    footers: { default: new Footer({ children: [ new Paragraph({ alignment: AlignmentType.CENTER, children: [ new TextRun({ text: "Page ", size: 16 }), new TextRun({ children: [PageNumber.CURRENT], size: 16 }), new TextRun({ text: " of ", size: 16 }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16 }) ] }) ] }) },
    children
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("DOSTO_Coupled_Train_Test_Report_2026-06-12_v1.1.docx", buf);
  console.log("written");
});
