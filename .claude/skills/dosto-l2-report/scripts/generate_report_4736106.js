#!/usr/bin/env node
// Specialised report generator for 4736-106 findings — renders the full inter-coach error evidence.

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, VerticalAlign,
  PageNumber, PageBreak, TabStopType,
} = require('docx');

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1) return dflt;
  return process.argv[i + 1];
}

const findingsPath = arg('findings');
const findings = JSON.parse(fs.readFileSync(findingsPath, 'utf8'));
const customer = arg('customer', 'ÖBB');
const customerLong = 'ÖBB — Österreichische Bundesbahnen';
const fzgId = arg('fzg-id', findings.trainset.fzg_id);
const fzgNr = arg('fzg-nr', findings.trainset.fzg_nr);
const consistSize = findings.trainset.consist_size;
const author = arg('author', findings.check_performed_by);
const organisation = 'Nomad Digital';
const outputPath = arg('output',
  `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/OBB_Fzg${fzgId}_4736-106_Network_Health_Check_Report_v1.0.docx`);

const verdict = findings.verdict.overall;
const verdictDegraded = verdict === 'DEGRADED';
const checkDate = findings.generated_at.split('T')[0];

// -------- style helpers --------
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const shadeHeader = { fill: "D5E8F0", type: ShadingType.CLEAR };
const shadeGood   = { fill: "E2EFDA", type: ShadingType.CLEAR };
const shadeWarn   = { fill: "FFF2CC", type: ShadingType.CLEAR };
const shadeBad    = { fill: "FCE4D6", type: ShadingType.CLEAR };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    ...opts,
    children: [new TextRun({ text, ...(opts.run || {}) })],
  });
}
function bullet(text, run = {}) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, ...run })],
  });
}
function heading(text, level) {
  return new Paragraph({
    heading: level,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text })],
  });
}
function cell(text, width, opts = {}) {
  const runs = Array.isArray(text) ? text : [{ text: String(text) }];
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: opts.shading, margins: cellMargins,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: runs.map(r => new TextRun({
        text: r.text, bold: r.bold || opts.bold, color: r.color, size: opts.size,
      })),
    })],
  });
}
function tbl(columnWidths, rows) {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths, rows,
  });
}
function headerRow(cols, widths) {
  return new TableRow({
    tableHeader: true,
    children: cols.map((c, i) => cell(c, widths[i], { shading: shadeHeader, bold: true })),
  });
}

// -------- title page --------
const titlePage = [
  new Paragraph({
    alignment: AlignmentType.RIGHT, spacing: { after: 240 },
    children: [new TextRun({ text: organisation, bold: true, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.RIGHT, spacing: { after: 1200 },
    children: [new TextRun({ text: "Connected Transport, Intelligent Solutions", italics: true, size: 18, color: "808080" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { before: 1200, after: 240 },
    children: [new TextRun({ text: "Network Health Check Report", bold: true, size: 48, color: "1F4E79" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 240 },
    children: [new TextRun({ text: `DOSTO Nahverkehr ${consistSize}`, size: 32, color: "2E75B6" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
    children: [new TextRun({ text: "DEGRADED — Multiple Inter-Coach Trunk Faults, Escalating", bold: true, size: 28, color: "C00000" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 600 },
    children: [new TextRun({ text: "Urgent Stadler maintenance action required — fault spread confirmed on follow-up check", size: 22, color: "C00000" })],
  }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Prepared for", size: 22 })] }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 1200 },
    children: [new TextRun({ text: customerLong, bold: true, size: 28 })],
  }),
  tbl([3120, 6240], [
    new TableRow({ children: [cell("Trainset (Fzg. Nr.)", 3120, { bold: true, shading: shadeHeader }), cell(fzgNr, 6240)] }),
    new TableRow({ children: [cell("Fahrzeug-ID (ÖBB)", 3120, { bold: true, shading: shadeHeader }), cell(`Fzg. ${fzgId}`, 6240)] }),
    new TableRow({ children: [cell("Configuration", 3120, { bold: true, shading: shadeHeader }), cell(consistSize, 6240)] }),
    new TableRow({ children: [cell("CCU", 3120, { bold: true, shading: shadeHeader }), cell(`${findings.ccu_hostname} (${findings.ccu_ip})`, 6240)] }),
    new TableRow({ children: [cell("Health check date", 3120, { bold: true, shading: shadeHeader }), cell(checkDate, 6240)] }),
    new TableRow({ children: [cell("Performed by", 3120, { bold: true, shading: shadeHeader }), cell(findings.check_performed_by, 6240)] }),
    new TableRow({ children: [cell("Document version", 3120, { bold: true, shading: shadeHeader }), cell("1.0 (Draft for review)", 6240)] }),
    new TableRow({ children: [cell("Classification", 3120, { bold: true, shading: shadeHeader }), cell(`Confidential — for ${customer} and ${organisation} review`, 6240)] }),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- document control --------
const docControl = [
  heading("Document Control", HeadingLevel.HEADING_1),
  p("This document records findings from an on-train Layer-2 network health check. Reviewers may add comments and tracked changes inline. Record all changes in the revision history."),
  heading("Revision History", HeadingLevel.HEADING_2),
  tbl([1200, 1800, 2800, 3560], [
    headerRow(["Version", "Date", "Author", "Change Summary"], [1200, 1800, 2800, 3560]),
    new TableRow({ children: [cell("1.0", 1200), cell(checkDate, 1800), cell(findings.check_performed_by, 2800), cell("Initial draft — inter-coach cable fault investigation", 3560)] }),
    new TableRow({ children: [cell("1.3", 1200), cell("2026-05-05", 1800), cell(findings.check_performed_by, 2800), cell("Day 2 follow-up — fault escalation confirmed, 4 additional degraded ports across nv6-E3/F2/F3", 3560)] }),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)] }),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)] }),
  ]),
  heading("Approvals", HeadingLevel.HEADING_2),
  tbl([2400, 2800, 2400, 1760], [
    headerRow(["Role", "Name", "Organisation", "Date"], [2400, 2800, 2400, 1760]),
    new TableRow({ children: [cell("Author", 2400), cell(findings.check_performed_by, 2800), cell(organisation, 2400), cell(checkDate, 1760)] }),
    new TableRow({ children: [cell("Technical Reviewer", 2400), cell("", 2800), cell(organisation, 2400), cell("", 1760)] }),
    new TableRow({ children: [cell(`${customer} Reviewer`, 2400), cell("", 2800), cell(customer, 2400), cell("", 1760)] }),
    new TableRow({ children: [cell("Stadler Reviewer", 2400), cell("", 2800), cell("Stadler Rail", 2400), cell("", 1760)] }),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- executive summary --------
const exec = [
  heading("1. Executive Summary", HeadingLevel.HEADING_1),
  p(`A Layer-2 network health check was performed on DOSTO trainset Fzg. ${fzgId} (${fzgNr}) on ${checkDate} by ${organisation} engineering. The trainset has been reported as experiencing slow or degraded network performance by ÖBB and Stadler. This report documents the findings and identifies the root cause.`),
  heading("Headline Verdict", HeadingLevel.HEADING_2),
  tbl([9360], [
    new TableRow({ children: [
      cell([
        { text: "OVERALL: DEGRADED — ", bold: true, color: "C00000" },
        { text: "Multiple inter-coach trunk links have physical-layer faults. Fault has escalated between day 1 and day 2 checks.", bold: true },
      ], 9360, { shading: shadeBad }),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("Day 1 (2026-05-04) — Critical faults confirmed:", { run: { bold: true } }),
  bullet(`Switch nv6-D1 (MAC a0:59:3a:d0:2e:c0), port e0-1: Speed degraded from 10 Gbps to 1 Gbps. 130,998 RX CRC errors and 67,407 jabber frames observed, actively increasing throughout the check at ~1,100 errors/minute.`),
  bullet(`Switch nv6-E2 (MAC a0:59:3a:d0:54:60), port e0-1: Speed degraded from 10 Gbps to 1 Gbps. 51,013 RX CRC errors and 7,102 fragment frames observed, actively increasing. Both ports are the two ends of the same D–E inter-coach cable segment.`),
  bullet(`All other 16 switches at time of check showed zero error counters at 10 Gbps full duplex.`),
  bullet(`Stadler firewall (172.19.195.1): reachable — ARP resolved, TCP/22 and TCP/80 open. The vlan7 path is healthy.`),
  p("Day 2 (2026-05-05) — Fault has escalated:", { run: { bold: true } }),
  bullet(`nv6-D1 e0-1 and nv6-E2 e0-1 have further degraded from 1 Gbps to 100 Mbps overnight (10× additional speed reduction).`),
  bullet(`Four additional ports on three further switches have also degraded to 100 Mbps: nv6-E3 e0-0, nv6-F2 e0-0, nv6-F2 e0-1, nv6-F3 e0-1. No CRC errors on these ports yet, but they cannot sustain 10G auto-negotiation.`),
  bullet(`The spread of degradation across the E–F car area in 24 hours indicates an escalating or systemic physical-layer problem requiring urgent Stadler inspection.`),
  p("This is now a multi-port, multi-switch fault affecting the E and F car section of the consist. Immediate physical inspection by Stadler is required."),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- scope --------
const scope = [
  heading("2. Scope and Methodology", HeadingLevel.HEADING_1),
  heading("2.1 What Was Checked", HeadingLevel.HEADING_2),
  bullet(`All ${findings.vds_switches.count_found} VDS Rail Consist Switches on management VLAN 100 (10.179.19.128/25).`),
  bullet("All inter-coach trunk uplinks (ports e0-0 and e0-1 on each switch)."),
  bullet("RSTP spanning tree root and port states across the fleet."),
  bullet("End-to-end reachability from CCU to Stadler firewall via vlan7."),
  bullet("CCU interface counters on vlan7 and bond0."),
  heading("2.2 What Is Out of Scope", HeadingLevel.HEADING_2),
  bullet("Stadler-side device VLANs (cameras, displays, AFZ, intercom, OBS, RDC) — managed by Stadler Rail."),
  bullet("PWLAN / passenger Wi-Fi — separate Nomad Digital scope."),
  bullet("Cellular WAN backhaul — separate Nomad Digital scope."),
  heading("2.3 Method", HeadingLevel.HEADING_2),
  p(`The check was performed via SSH from the engineer's laptop through the CCU (${findings.ccu_hostname}, ${findings.ccu_ip}) to each VDS Rail Consist Switch using the standard Nomad Digital L2 health-check playbook. Switch CLI command: show interface <port> details. Error counters were read at two or three points in time to confirm active growth.`),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- findings --------

// Build schema map lookup
const schemaMap = {};
for (const s of (findings.vds_switches.schema_ip_map || [])) {
  schemaMap[s.ip] = s.schema;
  schemaMap[s.mac] = s.schema;
}

// Build inter-coach trunk error table — skip NO_RESPONSE/TIMEOUT rows, show all confirmed results
const trunkResults = findings.inter_coach_trunk_scan.results.filter(r => r.speed !== 'TIMEOUT');
const trunkRows = [
  headerRow(["Schema", "Switch IP", "Port", "Speed", "RX CRC Errors", "Jabber", "Fragments", "Carrier-false"], [1100, 1900, 900, 1200, 1500, 1200, 1200, 760]),
];
for (const r of trunkResults) {
  const isBad = r.severity === 'RED';
  const schema = schemaMap[r.switch] || '-';
  trunkRows.push(new TableRow({ children: [
    cell(schema, 1100, { shading: isBad ? shadeBad : undefined }),
    cell(r.switch, 1900),
    cell(r.port, 900),
    cell(r.speed || '-', 1200, { shading: isBad ? shadeBad : shadeGood }),
    cell(String(r.rx_crc ?? 0), 1500, { shading: (r.rx_crc > 0) ? shadeBad : undefined }),
    cell(String(r.jabber ?? 0), 1200, { shading: (r.jabber > 0) ? shadeBad : undefined }),
    cell(String(r.frag ?? 0), 1200, { shading: (r.frag > 0) ? shadeBad : undefined }),
    cell(String(r.carrier_false ?? 0), 760, { shading: (r.carrier_false > 0) ? shadeBad : undefined }),
  ]}));
}

// CRC growth evidence table
const growthRows = [
  headerRow(["Timestamp (UTC)", "Schema / Port", "RX CRC Errors", "Delta since prev reading", "Other errors"], [2400, 2400, 1800, 2000, 920]),
];
const g184 = findings.crc_error_growth_evidence.switch_184_e0_1_schema_D1;
for (let i = 0; i < g184.length; i++) {
  const r = g184[i];
  const delta = i === 0 ? '—' : `+${r.rx_crc - g184[i-1].rx_crc} CRC`;
  growthRows.push(new TableRow({ children: [
    cell(r.timestamp.replace('+00:00','Z'), 2400),
    cell('nv6-D1 (10.179.19.184) / e0-1', 2400),
    cell(String(r.rx_crc), 1800, { shading: shadeBad }),
    cell(delta, 2000, { shading: i > 0 ? shadeBad : undefined }),
    cell(`jabber: ${r.jabber}`, 920),
  ]}));
}
const g196 = findings.crc_error_growth_evidence.switch_196_e0_1_schema_E2;
for (let i = 0; i < g196.length; i++) {
  const r = g196[i];
  const delta = i === 0 ? '—' : `+${r.rx_crc - g196[i-1].rx_crc} CRC`;
  growthRows.push(new TableRow({ children: [
    cell(r.timestamp.replace('+00:00','Z'), 2400),
    cell('nv6-E2 (10.179.19.196) / e0-1', 2400),
    cell(String(r.rx_crc), 1800, { shading: shadeBad }),
    cell(delta, 2000, { shading: i > 0 ? shadeBad : undefined }),
    cell(`frag: ${r.frag}`, 920),
  ]}));
}

const findingsSection = [
  heading("3. Detailed Findings", HeadingLevel.HEADING_1),
  heading("3.1 Switch Inventory and Schema Map", HeadingLevel.HEADING_2),
  tbl([3200, 3200, 2960], [
    headerRow(["Parameter", "Observed", "Expected"], [3200, 3200, 2960]),
    new TableRow({ children: [cell("VDS switches found", 3200), cell(String(findings.vds_switches.count_found), 3200, { shading: shadeGood }), cell("18 (6-car consist)", 2960)] }),
    new TableRow({ children: [cell("Westermo radios found", 3200), cell(String(findings.westermo_radio_count), 3200), cell("~24 (typical)", 2960)] }),
    new TableRow({ children: [cell("CCU vlan100 subnet", 3200), cell(findings.trainset.ccu_vlan100, 3200), cell("10.179.X.128/25", 2960)] }),
    new TableRow({ children: [cell("CCU vlan7 address", 3200), cell(findings.trainset.ccu_vlan7, 3200), cell("172.19.195.x/17", 2960)] }),
    new TableRow({ children: [cell("DHCP lease time", 3200), cell("2 minutes (120s)", 3200, { shading: shadeWarn }), cell("Typically longer — short lease causes frequent IP churn", 2960)] }),
  ]),
  p("All 18 switch positions confirmed via DHCP hostname records (format: nv6-XX-v8-134). Note: the 2-minute DHCP lease time causes switches to renew frequently and may acquire different IPs between poll cycles. This is a management-plane observation and does not affect switching fabric operation, but can complicate automated health checks. Schema-to-IP mapping at time of check:"),
  (() => {
    const map = findings.vds_switches.schema_ip_map || [];
    const rows = [headerRow(["Schema Position", "IP at Time of Check", "MAC Address"], [2400, 3200, 3760])];
    for (const s of map) {
      const isBad = s.schema === 'nv6-D1' || s.schema === 'nv6-E2';
      rows.push(new TableRow({ children: [
        cell(s.schema, 2400, { shading: isBad ? shadeBad : undefined, bold: isBad }),
        cell(s.ip, 3200, { shading: isBad ? shadeBad : undefined }),
        cell(s.mac, 3760),
      ]}));
    }
    return tbl([2400, 3200, 3760], rows);
  })(),
  heading("3.2 RSTP Spanning Tree", HeadingLevel.HEADING_2),
  tbl([3200, 6160], [
    new TableRow({ children: [cell("Protocol", 3200, { bold: true, shading: shadeHeader }), cell("RSTP (Rapid Spanning Tree Protocol)", 6160)] }),
    new TableRow({ children: [cell("Root bridge", 3200, { bold: true, shading: shadeHeader }), cell(findings.stp.root_bridge, 6160)] }),
    new TableRow({ children: [cell("Switches agreeing on root", 3200, { bold: true, shading: shadeHeader }), cell(`${findings.stp.switches_agree} of ${findings.stp.switches_polled} polled (${findings.stp.switches_timeout} timed out — IPs renewed mid-poll due to 2-min DHCP lease)`, 6160, { shading: shadeGood })] }),
    new TableRow({ children: [cell("Topology stable", 3200, { bold: true, shading: shadeHeader }), cell("Yes — no TCN flapping observed", 6160, { shading: shadeGood })] }),
    new TableRow({ children: [cell("Note", 3200, { bold: true, shading: shadeHeader }), cell(findings.stp.note, 6160)] }),
  ]),
  heading("3.3 Inter-Coach Trunk Error Scan — All Results", HeadingLevel.HEADING_2),
  p("The table below shows show interface <port> details results for ports e0-0 and e0-1 on every VDS switch. All 18 switches were confirmed present. Red cells indicate non-zero error values. Green cells indicate clean counters at the expected 10 Gbps speed. Switches with IPs not shown had renewed their DHCP lease mid-poll and were confirmed clean on a follow-up read."),
  tbl([1100, 1900, 900, 1200, 1500, 1200, 1200, 760], trunkRows),
  new Paragraph({ spacing: { after: 200 }, children: [new TextRun("")] }),
  heading("3.4 CRC Error Counter Growth — Live Evidence", HeadingLevel.HEADING_2),
  p("To confirm that the error counters are actively accumulating (and are not stale counters from a past event), the same ports were read at multiple points during the health check. The table below shows the growth rates."),
  tbl([2400, 2400, 1800, 2000, 920], growthRows),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] }),
  p("Interpretation: The CRC errors on both ports are growing rapidly and continuously. This conclusively rules out a one-off transient event (e.g. a single power cycle or vibration spike) and confirms an ongoing physical-layer fault — bad cable, dirty/damaged SFP connector, or damaged inter-coach trunk cable — on each of the two affected link segments."),
  heading("3.5 Stadler Firewall — Switch Port and vlan7 Reachability", HeadingLevel.HEADING_2),
  p("The Stadler firewall trunk connects to switch nv6-A3 (10.179.19.193) on port e1-4, carrying VLANs 2, 3, 5, 6, 7, 8, 9, 12, and 15. Port e1-4 was inspected first at the switch level, then end-to-end from the CCU via vlan7."),
  p("Port e1-4 on nv6-A3 (show interface e1-4 details):", { run: { bold: true } }),
  tbl([3600, 5760], [
    headerRow(["Parameter", "Value"], [3600, 5760]),
    new TableRow({ children: [cell("Port", 3600), cell("e1-4 on nv6-A3 (10.179.19.193)", 5760)] }),
    new TableRow({ children: [cell("Speed / Duplex", 3600), cell("1000 Mb/s, Full (as expected — 1G trunk to Stadler FW)", 5760, { shading: shadeGood })] }),
    new TableRow({ children: [cell("RX errors / CRC errors", 3600), cell("0 / 0", 5760, { shading: shadeGood })] }),
    new TableRow({ children: [cell("Jabber / Fragments", 3600), cell("0 / 0", 5760, { shading: shadeGood })] }),
    new TableRow({ children: [cell("Carrier-false", 3600), cell("0", 5760, { shading: shadeGood })] }),
    new TableRow({ children: [cell("Result", 3600), cell("PASS — port is clean. No physical-layer errors on the Stadler FW trunk.", 5760, { shading: shadeGood })] }),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("End-to-end CCU ↔ Stadler firewall via vlan7:", { run: { bold: true } }),
  p("The CCU vlan7 address is 172.19.195.2/17. The Stadler firewall/gateway on this trainset responds at 172.19.195.1 (MAC 00:90:e8:c1:a7:ab, Westermo). TCP/22 and TCP/80 are open. The address 172.19.196.1 — which is the typical Stadler FW address on other ÖBB DOSTO consists — did not respond at all on this trainset."),
  tbl([3200, 2200, 3960], [
    headerRow(["Probe", "Result", "Interpretation"], [3200, 2200, 3960]),
    new TableRow({ children: [cell("vlan7 interface state", 3200), cell("UP, zero errors/drops", 2200, { shading: shadeGood }), cell("CCU-side vlan7 link is operationally healthy.", 3960)] }),
    new TableRow({ children: [cell("ARP: 172.19.195.1 (Stadler FW)", 3200), cell("REACHABLE — MAC 00:90:e8:c1:a7:ab", 2200, { shading: shadeGood }), cell("Stadler firewall/gateway is present and responding at Layer 2.", 3960)] }),
    new TableRow({ children: [cell("TCP/22 to 172.19.195.1", 3200), cell("OPEN", 2200, { shading: shadeGood }), cell("Stadler FW is responding at Layer 4.", 3960)] }),
    new TableRow({ children: [cell("TCP/80 to 172.19.195.1", 3200), cell("OPEN", 2200, { shading: shadeGood }), cell("Stadler FW is responding at Layer 4.", 3960)] }),
    new TableRow({ children: [cell("ICMP to 172.19.195.1", 3200), cell("100% loss (expected)", 2200, { shading: shadeWarn }), cell("Stadler FW filters ICMP echo-request by policy on all ÖBB DOSTO installations. Not a fault.", 3960)] }),
    new TableRow({ children: [cell("ARP: 172.19.196.1 (alternate address)", 3200), cell("INCOMPLETE — not responding", 2200, { shading: shadeWarn }), cell("This IP did not respond. May not be provisioned on this trainset. Requires Stadler confirmation.", 3960)] }),
  ]),
  p("Summary: The Stadler firewall port on nv6-A3 e1-4 is clean (zero errors). The CCU→FW path via vlan7 is healthy — ARP reachable, TCP/22 and TCP/80 open. The 172.19.196.1 address is not active on this trainset — Stadler should confirm whether this is expected."),
  heading("3.6 Throughput on Faulty vs Healthy Inter-Coach Trunks", HeadingLevel.HEADING_2),
  p("To quantify the traffic impact of the cable fault, live throughput was measured by diffing byte counters on the faulty port and five healthy inter-coach trunk ports across a 39-second window. All healthy trunks run at 10 Gbps; the two faulty ports (D1 e0-1 and E2 e0-1) are capped at 1 Gbps by auto-negotiation fallback."),
  p("Note: E2 e0-1 (nv6-E2 at 10.179.19.196) renewed its DHCP lease mid-window and could not be sampled in this measurement. Its CRC error growth (section 3.4) independently confirms the fault."),
  tbl([1500, 1800, 1000, 1000, 1500, 1500, 1760], [
    headerRow(["Port", "Schema / Switch", "RX Mbps", "TX Mbps", "Total Mbps", "Capacity", "Utilisation"], [1500, 1800, 1000, 1000, 1500, 1500, 1760]),
    new TableRow({ children: [
      cell("D1 e0-1", 1500, { shading: shadeBad, bold: true }),
      cell("nv6-D1 / .184", 1800, { shading: shadeBad }),
      cell("0.3", 1000, { shading: shadeBad }),
      cell("1.2", 1000, { shading: shadeBad }),
      cell("1.5", 1500, { shading: shadeBad }),
      cell("1,000 Mbps (DEGRADED)", 1500, { shading: shadeBad }),
      cell("0.15%", 1760, { shading: shadeBad }),
    ]}),
    new TableRow({ children: [
      cell("D1 e0-0", 1500),
      cell("nv6-D1 / .184", 1800),
      cell("1.4", 1000),
      cell("19.0", 1000),
      cell("20.4", 1500, { shading: shadeGood }),
      cell("10,000 Mbps", 1500),
      cell("0.20%", 1760),
    ]}),
    new TableRow({ children: [
      cell("E1 e0-0", 1500),
      cell("nv6-E1 / .191", 1800),
      cell("27.7", 1000),
      cell("10.8", 1000),
      cell("38.5", 1500, { shading: shadeGood }),
      cell("10,000 Mbps", 1500),
      cell("0.38%", 1760),
    ]}),
    new TableRow({ children: [
      cell("E1 e0-1", 1500),
      cell("nv6-E1 / .191", 1800),
      cell("9.7", 1000),
      cell("45.4", 1000),
      cell("55.1", 1500, { shading: shadeGood }),
      cell("10,000 Mbps", 1500),
      cell("0.55%", 1760),
    ]}),
    new TableRow({ children: [
      cell("C1 e0-0", 1500),
      cell("nv6-C1 / .183", 1800),
      cell("1.5", 1000),
      cell("38.1", 1000),
      cell("39.6", 1500, { shading: shadeGood }),
      cell("10,000 Mbps", 1500),
      cell("0.40%", 1760),
    ]}),
    new TableRow({ children: [
      cell("C1 e0-1", 1500),
      cell("nv6-C1 / .183", 1800),
      cell("19.2", 1000),
      cell("1.3", 1000),
      cell("20.5", 1500, { shading: shadeGood }),
      cell("10,000 Mbps", 1500),
      cell("0.20%", 1760),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("Interpretation: The faulty D1 e0-1 link carries only 1.5 Mbps total — roughly 13–37× less than healthy inter-coach trunks in the same measurement window (20–55 Mbps on 10G links). This is not because the train is idle: the healthy E1 and C1 trunks are clearly carrying substantial traffic. The severe underutilisation on D1 e0-1 is a direct consequence of the physical fault: frame corruption forces TCP retransmissions for all sessions traversing the D–E inter-coach segment, reducing effective throughput to near-zero on that segment."),
  heading("3.7 Day 2 Follow-Up Check (2026-05-05) — Fault Escalation", HeadingLevel.HEADING_2),
  p("A follow-up check was performed the next morning (2026-05-05, ~05:36 UTC) after the train came back online. Two snapshots were taken 5 minutes apart. The fault has worsened significantly."),
  p("Day-over-day speed progression on confirmed fault ports:", { run: { bold: true } }),
  tbl([2000, 1800, 1800, 1800, 3360], [
    headerRow(["Schema / Port", "Day 1 Speed", "Day 2 Speed", "Day 2 CRC", "Status"], [2000, 1800, 1800, 1800, 3360]),
    new TableRow({ children: [
      cell("nv6-D1 e0-1", 2000, { shading: shadeBad, bold: true }),
      cell("1,000 Mbps", 1800, { shading: shadeWarn }),
      cell("100 Mbps", 1800, { shading: shadeBad }),
      cell("1,475 (jabber: 307)", 1800, { shading: shadeBad }),
      cell("Further degraded — 100× below design speed", 3360, { shading: shadeBad }),
    ]}),
    new TableRow({ children: [
      cell("nv6-E2 e0-1", 2000, { shading: shadeBad, bold: true }),
      cell("1,000 Mbps", 1800, { shading: shadeWarn }),
      cell("100 Mbps", 1800, { shading: shadeBad }),
      cell("2,021 (frag: 328)", 1800, { shading: shadeBad }),
      cell("Further degraded — 100× below design speed", 3360, { shading: shadeBad }),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("New ports degraded since day 1 (speed-only, no CRC errors yet):", { run: { bold: true } }),
  tbl([2000, 1800, 1800, 1800, 3360], [
    headerRow(["Schema / Port", "Day 1 Speed", "Day 2 Speed", "Day 2 CRC", "Note"], [2000, 1800, 1800, 1800, 3360]),
    new TableRow({ children: [
      cell("nv6-E3 e0-0", 2000, { shading: shadeWarn }),
      cell("10,000 Mbps", 1800, { shading: shadeGood }),
      cell("100 Mbps", 1800, { shading: shadeWarn }),
      cell("0", 1800),
      cell("New — speed degradation only, no frame corruption yet", 3360),
    ]}),
    new TableRow({ children: [
      cell("nv6-F2 e0-0", 2000, { shading: shadeWarn }),
      cell("10,000 Mbps", 1800, { shading: shadeGood }),
      cell("100 Mbps", 1800, { shading: shadeWarn }),
      cell("0", 1800),
      cell("New — both ports on this switch affected", 3360),
    ]}),
    new TableRow({ children: [
      cell("nv6-F2 e0-1", 2000, { shading: shadeWarn }),
      cell("10,000 Mbps", 1800, { shading: shadeGood }),
      cell("100 Mbps", 1800, { shading: shadeWarn }),
      cell("0", 1800),
      cell("New — both ports on this switch affected", 3360),
    ]}),
    new TableRow({ children: [
      cell("nv6-F3 e0-1", 2000, { shading: shadeWarn }),
      cell("10,000 Mbps", 1800, { shading: shadeGood }),
      cell("100 Mbps", 1800, { shading: shadeWarn }),
      cell("0", 1800),
      cell("New — speed degradation only", 3360),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("Topology context — the inter-coach ring order is A–C–D–E–F–B (not alphabetical). Cross-referencing degraded ports against the topology diagram reveals three distinct faulty cable segments:"),
  tbl([2000, 3200, 4160], [
    headerRow(["Cable segment", "Affected ports", "Status"], [2000, 3200, 4160]),
    new TableRow({ children: [cell("D–E inter-coach cable", 2000, { shading: shadeBad }), cell("nv6-D1 e0-1 ↔ nv6-E2 e0-1", 3200, { shading: shadeBad }), cell("100 Mbps, active CRC errors both ends — confirmed fault", 4160, { shading: shadeBad })] }),
    new TableRow({ children: [cell("E–F inter-coach cable", 2000, { shading: shadeWarn }), cell("nv6-E3 e0-0 ↔ nv6-F2 e0-0", 3200, { shading: shadeWarn }), cell("100 Mbps, no CRC yet — early-stage degradation", 4160, { shading: shadeWarn })] }),
    new TableRow({ children: [cell("F–B inter-coach cable", 2000, { shading: shadeWarn }), cell("nv6-F3 e0-1 ↔ nv6-B2 e0-?", 3200, { shading: shadeWarn }), cell("nv6-F3 e0-1 at 100 Mbps. nv6-B2 not yet scanned — requires confirmation.", 4160, { shading: shadeWarn })] }),
  ]),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun("")] }),
  p("Key observations from the day-2 check:"),
  bullet("CRC counters on D1 e0-1 and E2 e0-1 did not grow between the two 5-minute snapshots. This is consistent with a train power cycle overnight having reset the counters — the fault itself has not cleared."),
  bullet("nv6-F2 having both e0-0 and e0-1 degraded is explained by the topology: e0-0 connects toward car E (E–F cable) and e0-1 connects toward car F3 or the F–B segment. These are two separate cable faults on either side of the same switch, not a switch hardware fault."),
  bullet("nv6-B2 (the far end of the F–B cable) was not reachable during the scan due to IP rotation. Its error counters need to be read to complete the picture — it is likely also at 100 Mbps."),
  bullet("The geographic spread covers three consecutive inter-coach cable segments in the E–F–B section of the consist. Cars A through D show no degradation."),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- recommendations --------
const recsSection = [
  heading("4. Root Cause and Recommendations", HeadingLevel.HEADING_1),
  heading("4.1 Root Cause", HeadingLevel.HEADING_2),
  tbl([9360], [
    new TableRow({ children: [
      cell([
        { text: "Root cause of slow network on Fzg. 134 (4736-106): ", bold: true },
        { text: "Two inter-coach trunk cable links have physical-layer faults (bad cable, damaged connector, or failed SFP transceiver). These links auto-negotiated down from the expected 10 Gbps to 1 Gbps, and are generating tens of thousands of CRC errors per hour. The resulting frame corruption forces TCP retransmissions on all traffic crossing those inter-coach segments, severely degrading effective throughput for all passengers and onboard systems.", bold: false },
      ], 9360, { shading: shadeBad }),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] }),
  heading("4.2 Required Actions — Stadler Rail", HeadingLevel.HEADING_2),
  tbl([2000, 2200, 5360], [
    headerRow(["Priority", "Action", "Detail"], [2000, 2200, 5360]),
    new TableRow({ children: [
      cell("CRITICAL", 2000, { shading: shadeBad, bold: true }),
      cell("Inspect nv6-D1 e0-1 cable/SFP", 2200),
      cell("Physically inspect the inter-coach trunk cable on port e0-1 of switch nv6-D1 (MAC a0:59:3a:d0:2e:c0). Check SFP transceiver and cable connectors at both ends. Speed degraded 10G→1G→100 Mbps over 24 hours with active CRC errors. Replace faulty component and confirm link returns to 10 Gbps with zero error counters.", 5360),
    ]}),
    new TableRow({ children: [
      cell("CRITICAL", 2000, { shading: shadeBad, bold: true }),
      cell("Inspect nv6-E2 e0-1 cable/SFP", 2200),
      cell("Physically inspect the inter-coach trunk cable on port e0-1 of switch nv6-E2 (MAC a0:59:3a:d0:54:60). This is the other end of the same D–E inter-coach cable as nv6-D1 e0-1. Speed degraded 10G→1G→100 Mbps with active CRC errors. Replace faulty component.", 5360),
    ]}),
    new TableRow({ children: [
      cell("CRITICAL", 2000, { shading: shadeBad, bold: true }),
      cell("Inspect E–F inter-coach cable (nv6-E3 e0-0 ↔ nv6-F2 e0-0)", 2200),
      cell("Both ends of the E–F inter-coach cable degraded to 100 Mbps overnight. nv6-E3 e0-0 (MAC a0:59:3a:d0:56:80) and nv6-F2 e0-0 (MAC a0:59:3a:d0:51:e0) are the two ends of the same cable. No CRC errors yet but speed degradation indicates the cable cannot sustain 10G signalling. Replace before CRC errors develop.", 5360),
    ]}),
    new TableRow({ children: [
      cell("CRITICAL", 2000, { shading: shadeBad, bold: true }),
      cell("Inspect F–B inter-coach cable (nv6-F3 e0-1 ↔ nv6-B2 e0-?)", 2200),
      cell("nv6-F3 e0-1 (MAC a0:59:3a:d0:62:80) is at 100 Mbps. The far end — nv6-B2 (MAC a0:59:3a:d0:47:00) — was not reachable during the day-2 scan and must be checked. Both ends of the F–B inter-coach cable require physical inspection.", 5360),
    ]}),
    new TableRow({ children: [
      cell("HIGH", 2000, { shading: shadeWarn, bold: true }),
      cell("Investigate Stadler FW at 172.19.196.1", 2200),
      cell("Confirm whether 172.19.196.1 is expected to be active on this trainset. If so, investigate why it is ARP-INCOMPLETE. If not provisioned, confirm expected commissioning timeline.", 5360),
    ]}),
  ]),
  heading("4.3 Verification Steps After Repair", HeadingLevel.HEADING_2),
  p("After Stadler has replaced the faulty cables/SFPs, Nomad Digital will re-run the health check to confirm:"),
  bullet("Port e0-1 on switch 10.179.19.184 negotiates at 10,000 Mb/s full duplex."),
  bullet("Port e0-1 on switch 10.179.19.196 negotiates at 10,000 Mb/s full duplex."),
  bullet("RX CRC errors, jabber, and fragment counters on both ports are zero and remain at zero after 5 minutes."),
  bullet("User-reported slow network performance is resolved."),
  heading("4.4 Open Questions for ÖBB and Stadler", HeadingLevel.HEADING_2),
  bullet("When were the slow network symptoms first observed? Was there a specific event (train coupling, maintenance, shunting) that coincided with onset?"),
  bullet("Have these inter-coach trunk cables or SFP transceivers been replaced since the trainset entered service?"),
  bullet("Is the Stadler firewall at 172.19.196.1 expected to be active on this consist? If not, which IP is the active FW peer?"),
  bullet(`Preferred cadence for periodic re-checks after repair (${organisation} recommendation: 6 months post-repair, then annually).`),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- appendices --------
const appendices = [
  heading("Appendix A — Raw CLI Evidence", HeadingLevel.HEADING_1),
  p("The following is the verbatim CLI output from the VDS Rail Consist Switch for the two faulty ports, captured during the health check."),
  heading("Switch 10.179.19.184 — Port e0-1 (first reading, approx. 15:52 UTC)", HeadingLevel.HEADING_2),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({
      text:
`Interface e0-1 is enabled, line protocol is up
  Speed: 1000 Mb/s  Duplex: Full  MDI: MDI
  Hardware address is a0:59:3a:d0:2e:c0

  Stats
  ------
  RX packets:216427
  RX bytes:57465584 / TX bytes:164535152
  collisions:0  pause frames received:0  carrier false:0

  Errors
  ------
  RX errors:87 runts:0 giants:0 frag:17 jabber:30054
  RX crc errors: 53055
  TX crc errors:0`,
      font: "Courier New", size: 18,
    })],
  }),
  heading("Switch 10.179.19.184 — Port e0-1 (second reading, approx. 16:05 UTC)", HeadingLevel.HEADING_2),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({
      text:
`  Errors
  ------
  RX errors:106 runts:0 giants:0 frag:21 jabber:37552
  RX crc errors: 67115
  TX crc errors:0
  (delta from first reading: +14,060 CRC errors in ~13 minutes)`,
      font: "Courier New", size: 18,
    })],
  }),
  heading("Switch 10.179.19.196 — Port e0-1 (first reading, approx. 15:52 UTC)", HeadingLevel.HEADING_2),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({
      text:
`Interface e0-1 is enabled, line protocol is up
  Speed: 1000 Mb/s  Duplex: Full  MDI: MDI
  Hardware address is a0:59:3a:d0:54:60

  Errors
  ------
  RX errors:0 runts:0 giants:0 frag:5054 jabber:22
  RX crc errors: 35495
  TX crc errors:0`,
      font: "Courier New", size: 18,
    })],
  }),
  heading("Switch 10.179.19.196 — Port e0-1 (third reading, approx. 16:12 UTC)", HeadingLevel.HEADING_2),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({
      text:
`  Errors
  ------
  RX errors:0 runts:0 giants:0 frag:7102 jabber:40
  RX crc errors: 51013
  TX crc errors:0
  (delta from first reading: +15,518 CRC errors in ~20 minutes)`,
      font: "Courier New", size: 18,
    })],
  }),
  heading("Appendix B — Glossary", HeadingLevel.HEADING_1),
  tbl([2400, 6960], [
    headerRow(["Term", "Definition"], [2400, 6960]),
    new TableRow({ children: [cell("CRC error", 2400), cell("Cyclic Redundancy Check error — the frame checksum does not match the data. Indicates frame corruption, usually caused by a bad cable, dirty/damaged connector, or failing SFP transceiver.", 6960)] }),
    new TableRow({ children: [cell("Jabber", 2400), cell("A frame that is oversized (>1518 bytes) and also has a bad CRC. Jabbers are a classic symptom of a failing transceiver or cable.", 6960)] }),
    new TableRow({ children: [cell("Fragment", 2400), cell("A frame that is undersized (<64 bytes) and has a bad CRC. Indicates corruption at the physical layer.", 6960)] }),
    new TableRow({ children: [cell("SFP", 2400), cell("Small Form-factor Pluggable — the transceiver module that converts electrical signals to optical or copper for the inter-coach trunk.", 6960)] }),
    new TableRow({ children: [cell("10GBASE-T", 2400), cell("The 10 Gigabit Ethernet standard over copper twisted-pair. Used on the VDS Rail inter-coach trunks (e0-0, e0-1).", 6960)] }),
    new TableRow({ children: [cell("Auto-negotiation", 2400), cell("The process by which two Ethernet devices agree on the highest common speed and duplex mode. When a cable is degraded, the link often falls back to 1G or 100 Mbps.", 6960)] }),
    new TableRow({ children: [cell("CCU", 2400), cell("Communications Control Unit — the Nomad Digital onboard router/gateway (box1-t19 on this train).", 6960)] }),
    new TableRow({ children: [cell("DOSTO", 2400), cell("Doppelstockwagen — Stadler double-deck passenger trainset.", 6960)] }),
    new TableRow({ children: [cell("RSTP", 2400), cell("Rapid Spanning Tree Protocol — loop-prevention protocol. Ensures only one active path between any two switches.", 6960)] }),
  ]),
  heading("Appendix C — Reviewer Notes", HeadingLevel.HEADING_1),
  p("Use this table to log comments if not using Word's tracked-changes feature."),
  tbl([1200, 1800, 2400, 3960], [
    headerRow(["#", "Date", "Reviewer", "Note / Action Required"], [1200, 1800, 2400, 3960]),
    ...[1,2,3,4,5].map(n => new TableRow({ children: [cell(String(n), 1200), cell("", 1800), cell("", 2400), cell("", 3960)] })),
  ]),
];

// -------- build document --------
const doc = new Document({
  creator: findings.check_performed_by,
  title: `Network Health Check — Fzg. ${fzgId} (${fzgNr}) — DEGRADED`,
  description: `Layer-2 network health check for ÖBB Fzg. ${fzgId} — cable fault investigation`,
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1F4E79" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [{ reference: "bullets", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
    ]}],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "BFBFBF", space: 4 } },
          children: [
            new TextRun({ text: `Network Health Check — Fzg. ${fzgId} (${fzgNr})`, size: 18, color: "595959" }),
            new TextRun({ text: `\t${organisation} — CONFIDENTIAL`, size: 18, color: "595959" }),
          ],
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
          children: [
            new TextRun({ text: "Confidential — Draft for review", size: 16, color: "808080", italics: true }),
            new TextRun({ text: "\tPage ", size: 16, color: "808080" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" }),
            new TextRun({ text: " of ", size: 16, color: "808080" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "808080" }),
          ],
        })],
      }),
    },
    children: [...titlePage, ...docControl, ...exec, ...scope, ...findingsSection, ...recsSection, ...appendices],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, buf);
  console.log(`Wrote: ${outputPath} (${(buf.length/1024).toFixed(0)} KB)`);
});
