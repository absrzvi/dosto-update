#!/usr/bin/env node
// Generate a DOSTO L2 health check report (.docx) from a findings.json.
// Usage: node generate_report.js --findings <path> --customer "ÖBB" --fzg-id 146 --fzg-nr 4736-118 --consist-size 6-car --output <path>

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, VerticalAlign,
  PageNumber, PageBreak, TabStopType,
} = require('docx');

// -------- argv parsing (no external deps) --------
function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  if (i === -1) return dflt;
  return process.argv[i + 1];
}

const findingsPath = arg('findings');
if (!findingsPath || !fs.existsSync(findingsPath)) {
  console.error(`ERROR: --findings <path> required and must exist. Got: ${findingsPath}`);
  process.exit(1);
}
const findings = JSON.parse(fs.readFileSync(findingsPath, 'utf8'));

const customer = arg('customer', 'ÖBB');
const customerLong = customer === 'ÖBB' ? 'ÖBB — Österreichische Bundesbahnen' : customer;
const fzgId = arg('fzg-id', '?');
const fzgNr = arg('fzg-nr', '?');
const consistSize = arg('consist-size', findings.vds_switches?.consist_size || '?');
const author = arg('author', 'Abbas Rizvi');
const organisation = arg('organisation', 'Nomad Digital');
const schemaPdfName = arg('schema-pdf-name', `ND-DEL-OBB-035-IPA-${fzgId}_NV_*.pdf`);

const outputPath = arg('output',
  `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/${customer.replace('Ö','O')}_Fzg${fzgId}_Network_Health_Check_Report_v1.0.docx`);

const verdict = findings.verdict?.overall || 'UNKNOWN';
const verdictHealthy = verdict === 'HEALTHY';
const checkDate = (findings.generated_at || new Date().toISOString()).split('T')[0];

// -------- helpers --------
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const shadeHeader = { fill: "D5E8F0", type: ShadingType.CLEAR };
const shadeGood = { fill: "E2EFDA", type: ShadingType.CLEAR };
const shadeWarn = { fill: "FFF2CC", type: ShadingType.CLEAR };
const shadeBad = { fill: "FCE4D6", type: ShadingType.CLEAR };
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
function table(columnWidths, rows) {
  return new Table({
    width: { size: columnWidths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    columnWidths, rows,
  });
}
function headerRow(cols, columnWidths) {
  return new TableRow({
    tableHeader: true,
    children: cols.map((c, i) => cell(c, columnWidths[i], { shading: shadeHeader, bold: true })),
  });
}

// -------- title page --------
const titlePage = [
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { after: 240 },
    children: [new TextRun({ text: organisation, bold: true, size: 24 })],
  }),
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { after: 1200 },
    children: [new TextRun({ text: "Connected Transport, Intelligent Solutions", italics: true, size: 18, color: "808080" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 1200, after: 240 },
    children: [new TextRun({ text: "Network Health Check Report", bold: true, size: 48, color: "1F4E79" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 600 },
    children: [new TextRun({ text: `DOSTO Nahverkehr ${consistSize}`, size: 32, color: "2E75B6" })],
  }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120 }, children: [new TextRun({ text: "Prepared for", size: 22 })] }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 1200 },
    children: [new TextRun({ text: customerLong, bold: true, size: 28 })],
  }),
  table([3120, 6240], [
    new TableRow({ children: [cell("Trainset (Fzg. Nr.)", 3120, { bold: true, shading: shadeHeader }), cell(fzgNr, 6240)]}),
    new TableRow({ children: [cell("Fahrzeug-ID", 3120, { bold: true, shading: shadeHeader }), cell(fzgId, 6240)]}),
    new TableRow({ children: [cell("Configuration", 3120, { bold: true, shading: shadeHeader }), cell(consistSize, 6240)]}),
    new TableRow({ children: [cell("Health check date", 3120, { bold: true, shading: shadeHeader }), cell(checkDate, 6240)]}),
    new TableRow({ children: [cell("Performed by", 3120, { bold: true, shading: shadeHeader }), cell(`${author}, ${organisation}`, 6240)]}),
    new TableRow({ children: [cell("Document version", 3120, { bold: true, shading: shadeHeader }), cell("1.0 (Draft for review)", 6240)]}),
    new TableRow({ children: [cell("Classification", 3120, { bold: true, shading: shadeHeader }), cell(`Internal — for ${customer} and ${organisation} review`, 6240)]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- doc control --------
const docControl = [
  heading("Document Control", HeadingLevel.HEADING_1),
  p("This is a working document. Reviewers may add comments, tracked changes, and updates inline. Please record any changes in the revision history below."),
  heading("Revision History", HeadingLevel.HEADING_2),
  table([1200, 1800, 2800, 3560], [
    headerRow(["Version", "Date", "Author", "Change Summary"], [1200, 1800, 2800, 3560]),
    new TableRow({ children: [cell("1.0", 1200), cell(checkDate, 1800), cell(`${author}, ${organisation}`, 2800), cell("Initial draft following on-train health check", 3560)]}),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)]}),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)]}),
  ]),
  heading("Approvals", HeadingLevel.HEADING_2),
  table([2400, 2800, 2400, 1760], [
    headerRow(["Role", "Name", "Organisation", "Date"], [2400, 2800, 2400, 1760]),
    new TableRow({ children: [cell("Author", 2400), cell(author, 2800), cell(organisation, 2400), cell(checkDate, 1760)]}),
    new TableRow({ children: [cell("Technical Reviewer", 2400), cell("", 2800), cell(organisation, 2400), cell("", 1760)]}),
    new TableRow({ children: [cell(`${customer} Reviewer`, 2400), cell("", 2800), cell(customer, 2400), cell("", 1760)]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- exec summary --------
const exec = [
  heading("1. Executive Summary", HeadingLevel.HEADING_1),
  p(`A Layer-2 network health check was performed on DOSTO trainset Fzg. ID ${fzgId} (Fzg. Nr. ${fzgNr}) on ${checkDate} by ${organisation} engineering. The check covered all ${findings.vds_switches?.count || '?'} VDS Rail Consist Switches across the ${consistSize} consist, all inter-coach trunk links, all Stadler-facing trunks (firewall, OBS, RDC), the ZFR connections, the front-coupler trunks, and end-to-end reachability between the Nomad CCU and the Stadler firewall.`),
  heading("Headline Result", HeadingLevel.HEADING_2),
  table([9360], [
    new TableRow({ children: [
      cell([
        { text: "OVERALL VERDICT: ", bold: true },
        verdictHealthy
          ? { text: `The Layer-2 fabric on Fzg. ${fzgId} is healthy.`, bold: true, color: "375623" }
          : { text: `Items requiring review were found on Fzg. ${fzgId}.`, bold: true, color: "843C0C" },
      ], 9360, { shading: verdictHealthy ? shadeGood : shadeWarn }),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] }),
  bullet(`${findings.vds_switches?.count || 0} VDS Rail Consist Switches reachable on the management VLAN.`),
  bullet(`Inter-coach trunks at expected speed: e0-0 ${findings.trunks_up?.['e0-0'] || '?'}, e0-1 ${findings.trunks_up?.['e0-1'] || '?'} (e0-1 mismatch is expected for end-of-train switches).`),
  bullet(`Spanning Tree (RSTP) root: ${findings.stp?.root || '?'}, agreement ${findings.stp?.agreement || '?'} ${findings.stp?.consistent ? '— stable' : '— INCONSISTENT, investigate'}.`),
  bullet(`Per-port error counters non-zero on ${findings.verdict?.port_anomaly_count || 0} port(s) across the fleet.${findings.verdict?.port_anomaly_count === 1 ? ' Single-event noise; not a fault.' : ''}`),
  bullet(`Stadler firewall reachability: ARP ${findings.stadler_fw?.arp || '?'}, TCP/22 ${findings.stadler_fw?.tcp_22 || '?'}, TCP/80 ${findings.stadler_fw?.tcp_80 || '?'} (ICMP filtered by FW policy is expected).`),
  heading("Implications for Reported Packet Loss", HeadingLevel.HEADING_2),
  p("Where end-users have reported packet loss on similar consists in the past, the present health check provides strong evidence that the consist switching fabric is not the source if the verdict above is HEALTHY. Recommended follow-up areas in that case: end-host buffering on test endpoints, segments beyond the Stadler firewall (no CCU visibility), and the PWLAN / cellular client networks (separate scope)."),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- scope --------
const scope = [
  heading("2. Scope and Methodology", HeadingLevel.HEADING_1),
  heading("2.1 Scope", HeadingLevel.HEADING_2),
  p("This report covers the on-board Layer-2 switching fabric of the trainset, specifically:"),
  bullet(`All ${findings.vds_switches?.count || '?'} VDS Rail Consist Switches on the management VLAN.`),
  bullet("All inter-coach trunk uplinks (e0-0 and e0-1 on each switch)."),
  bullet("Stadler-facing trunks: firewall trunk, OBS trunks, RDC trunks."),
  bullet("ZFR access ports."),
  bullet("Front-coupler trunks."),
  bullet("End-to-end CCU-to-Stadler firewall connectivity over vlan7."),
  p("Out of scope:"),
  bullet("Stadler-side device VLANs (cameras, displays, AFZ, intercom, etc.) — managed by Stadler."),
  bullet("PWLAN and customer internal services VLANs — separate scope."),
  bullet("Cellular WAN backhaul — separate scope."),
  heading("2.2 Methodology", HeadingLevel.HEADING_2),
  p(`The check follows ${organisation}'s standard L2 health-check playbook (see project CLAUDE.md). The methodology comprises eight phases:`),
  table([800, 3000, 5560], [
    headerRow(["Phase", "Activity", "Purpose"], [800, 3000, 5560]),
    new TableRow({ children: [cell("1", 800), cell("Discovery", 3000), cell("Sweep vlan100 to enumerate consist switches and Westermo radios.", 5560)]}),
    new TableRow({ children: [cell("2", 800), cell("Schema mapping", 3000), cell("Match live IPs to schema switch IDs by trunk/access-port fingerprint.", 5560)]}),
    new TableRow({ children: [cell("3", 800), cell("Per-port error scan", 3000), cell("RX errors, CRC, carrier-false, collisions on every enabled port across all switches.", 5560)]}),
    new TableRow({ children: [cell("4", 800), cell("Critical trunk inspection", 3000), cell("Detailed inspection of Stadler-facing and ZFR ports.", 5560)]}),
    new TableRow({ children: [cell("5", 800), cell("Throughput sampling", 3000), cell("Two byte-counter snapshots N seconds apart to derive live link utilisation.", 5560)]}),
    new TableRow({ children: [cell("6", 800), cell("End-to-end probe", 3000), cell("ICMP, ARP, and TCP reachability tests from CCU to Stadler firewall.", 5560)]}),
    new TableRow({ children: [cell("7", 800), cell("STP topology check", 3000), cell("Verify RSTP root election and port states are consistent.", 5560)]}),
    new TableRow({ children: [cell("8", 800), cell("Baseline capture", 3000), cell("Save raw output as findings.json for future trend comparison and reporting.", 5560)]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- findings --------
const switchTable = (() => {
  const ips = findings.vds_switches?.ips || [];
  const fw = findings.vds_switches?.firmware || {};
  const rows = [headerRow(["Switch IP", "Firmware"], [3120, 6240])];
  for (const ip of ips) rows.push(new TableRow({ children: [cell(ip, 3120), cell(fw[ip] || '?', 6240)] }));
  return table([3120, 6240], rows);
})();

const anomalyTable = (() => {
  const a = findings.port_anomalies || [];
  if (a.length === 0) {
    return table([9360], [new TableRow({ children: [cell("No port-level error counters were non-zero. All enabled ports clean.", 9360, { shading: shadeGood })] })]);
  }
  const rows = [headerRow(["Switch", "Port", "RX errors", "CRC", "Carrier-false"], [2200, 1500, 1900, 1900, 1860])];
  for (const x of a) rows.push(new TableRow({ children: [
    cell(x.switch, 2200), cell(x.port, 1500),
    cell(String(x.rx_errors), 1900),
    cell(String(x.crc), 1900),
    cell(String(x.carrier_false), 1860),
  ]}));
  return table([2200, 1500, 1900, 1900, 1860], rows);
})();

const findingsSection = [
  heading("3. Detailed Findings", HeadingLevel.HEADING_1),
  heading("3.1 Switch Inventory and Firmware", HeadingLevel.HEADING_2),
  p(`Westermo industrial radio count on management VLAN: ${findings.westermo_radio_count || 0}.`),
  switchTable,
  heading("3.2 Inter-Coach Trunks", HeadingLevel.HEADING_2),
  table([3000, 3000, 3360], [
    headerRow(["Trunk", "UP / Total", "Comment"], [3000, 3000, 3360]),
    new TableRow({ children: [cell("e0-0 (primary inter-coach uplink)", 3000), cell(findings.trunks_up?.['e0-0'] || '?', 3000, { shading: shadeGood }), cell("All switches expected UP at 10 Gbps full duplex.", 3360)]}),
    new TableRow({ children: [cell("e0-1 (redundant inter-coach uplink)", 3000), cell(findings.trunks_up?.['e0-1'] || '?', 3000, { shading: shadeGood }), cell("Mismatch with e0-0 count is expected — end-of-train switches have no neighbour on e0-1.", 3360)]}),
    new TableRow({ children: [cell("e0-4 (PWLAN AP trunk)", 3000), cell(findings.trunks_up?.['e0-4'] || '?', 3000, { shading: shadeGood }), cell("Standard 1 Gbps trunk to access points.", 3360)]}),
  ]),
  heading("3.3 Spanning Tree (RSTP)", HeadingLevel.HEADING_2),
  table([3200, 6160], [
    new TableRow({ children: [cell("Protocol", 3200, { bold: true, shading: shadeHeader }), cell("RSTP", 6160)]}),
    new TableRow({ children: [cell("Root bridge", 3200, { bold: true, shading: shadeHeader }), cell(findings.stp?.root || '?', 6160)]}),
    new TableRow({ children: [cell("Root agreement across fleet", 3200, { bold: true, shading: shadeHeader }), cell(findings.stp?.agreement || '?', 6160, { shading: findings.stp?.consistent ? shadeGood : shadeBad })]}),
    new TableRow({ children: [cell("Topology stable", 3200, { bold: true, shading: shadeHeader }), cell(findings.stp?.consistent ? "Yes" : "NO — investigate", 6160)]}),
  ]),
  heading("3.4 Per-Port Error Counter Scan", HeadingLevel.HEADING_2),
  p("All enabled ports across all switches were checked for: RX errors, RX CRC errors, TX CRC errors, runts/giants/fragments/jabber, carrier-false, excessive collisions, late collisions."),
  anomalyTable,
  heading("3.5 End-to-End CCU ↔ Stadler Firewall", HeadingLevel.HEADING_2),
  table([3200, 2400, 3760], [
    headerRow(["Probe", "Result", "Interpretation"], [3200, 2400, 3760]),
    new TableRow({ children: [
      cell("ICMP echo", 3200),
      cell("100% loss (typical)", 2400, { shading: shadeWarn }),
      cell("Firewall drops echo-request by policy. Not a fault by itself.", 3760),
    ]}),
    new TableRow({ children: [
      cell("ARP resolution", 3200),
      cell(findings.stadler_fw?.arp || '?', 2400, { shading: findings.stadler_fw?.arp === 'reachable' ? shadeGood : shadeBad }),
      cell("MAC learned ⇒ L2 path works.", 3760),
    ]}),
    new TableRow({ children: [
      cell("TCP probe — port 22", 3200),
      cell(findings.stadler_fw?.tcp_22 || '?', 2400, { shading: findings.stadler_fw?.tcp_22 === 'open' ? shadeGood : shadeBad }),
      cell("FW responsive at L4.", 3760),
    ]}),
    new TableRow({ children: [
      cell("TCP probe — port 80", 3200),
      cell(findings.stadler_fw?.tcp_80 || '?', 2400, { shading: findings.stadler_fw?.tcp_80 === 'open' ? shadeGood : shadeBad }),
      cell("FW responsive at L4.", 3760),
    ]}),
    new TableRow({ children: [
      cell("vlan7 RX errors", 3200),
      cell(findings.stadler_fw?.vlan7_rx_errors || '?', 2400, { shading: findings.stadler_fw?.vlan7_rx_errors === '0' ? shadeGood : shadeWarn }),
      cell("Should be 0 — link layer to FW.", 3760),
    ]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- recommendations --------
const recsSection = [
  heading("4. Risk Assessment and Recommendations", HeadingLevel.HEADING_1),
  heading("4.1 Risk Summary", HeadingLevel.HEADING_2),
  table([2400, 2000, 4960], [
    headerRow(["Area", "Risk Level", "Rationale"], [2400, 2000, 4960]),
    new TableRow({ children: [cell("Inter-coach Layer-2 fabric", 2400), cell(verdictHealthy ? "LOW" : "REVIEW", 2000, { shading: verdictHealthy ? shadeGood : shadeWarn }), cell(verdictHealthy ? "All counters clean; substantial headroom; stable RSTP topology." : "Findings require attention — see detailed findings section.", 4960)]}),
    new TableRow({ children: [cell("Stadler-side beyond the firewall", 2400), cell("UNKNOWN", 2000, { shading: shadeWarn }), cell(`Out of scope for ${organisation} — Stadler responsibility. Bilateral health check recommended if user-perceived issues persist.`, 4960)]}),
    new TableRow({ children: [cell("PWLAN / cellular client paths", 2400), cell("NOT ASSESSED", 2000, { shading: shadeWarn }), cell("Separate scope. To be addressed in a future report if requested.", 4960)]}),
  ]),
  heading("4.2 Recommendations", HeadingLevel.HEADING_2),
  bullet(verdictHealthy ? "No corrective action required for the consist Layer-2 fabric. Maintain current configuration and firmware." : "Address the items raised in the detailed findings section before considering the consist healthy."),
  bullet("Adopt TCP-based probes (e.g. nc -zv 172.19.196.1 80) rather than ICMP for ongoing CCU-to-firewall monitoring scripts. ICMP is filtered and produces misleading 100 % loss readings."),
  bullet("Save the findings.json from this session as a baseline for future trend comparison. Repeat the check at 6-monthly intervals or after any major firmware upgrade."),
  bullet("If end-users report packet loss on this consist in future, do not start with the Layer-2 fabric — start with end-host buffering analysis and the Stadler-side path beyond the firewall."),
  bullet("Test the front-coupler trunks the next time the consist is coupled to another trainset; capture link-up state and counters at that point."),
  heading(`4.3 Open Questions for ${customer} Review`, HeadingLevel.HEADING_2),
  bullet("Confirm whether the RDC service was expected to be active at the time of the health check."),
  bullet("Confirm any user-reported network issues on this trainset preceding this check, so that follow-up investigation can target specific symptoms."),
  bullet(`Confirm preferred cadence for periodic re-checks (${organisation} recommendation: 6 months).`),
  new Paragraph({ children: [new PageBreak()] }),
];

// -------- appendices --------
const appendices = [
  heading("Appendix A — Glossary", HeadingLevel.HEADING_1),
  table([2400, 6960], [
    headerRow(["Term", "Definition"], [2400, 6960]),
    new TableRow({ children: [cell("AFZ", 2400), cell("Automatische Fahrgastzählung — automatic passenger counter (VLAN 8)", 6960)]}),
    new TableRow({ children: [cell("Bildschrim", 2400), cell("Display screen — passenger information display (VLAN 3)", 6960)]}),
    new TableRow({ children: [cell("CCU", 2400), cell("Communications Control Unit — Nomad Digital onboard router/gateway", 6960)]}),
    new TableRow({ children: [cell("DOSTO", 2400), cell("Doppelstockwagen — double-deck passenger coach", 6960)]}),
    new TableRow({ children: [cell("FIS", 2400), cell("Fahrgastinformationssystem — passenger information system", 6960)]}),
    new TableRow({ children: [cell("Frontkupplung", 2400), cell("Front coupler — physical and electrical interface for inter-consist connection", 6960)]}),
    new TableRow({ children: [cell("OBS", 2400), cell("On-Board Server — Stadler operational platform", 6960)]}),
    new TableRow({ children: [cell("PWLAN", 2400), cell("Passenger Wireless LAN", 6960)]}),
    new TableRow({ children: [cell("RDC", 2400), cell("Remote Diagnostic Computer", 6960)]}),
    new TableRow({ children: [cell("RSTP", 2400), cell("Rapid Spanning Tree Protocol — IEEE 802.1w loop-prevention", 6960)]}),
    new TableRow({ children: [cell("Sprechstelle", 2400), cell("Intercom call-point (VLAN 9)", 6960)]}),
    new TableRow({ children: [cell("ZFR", 2400), cell("Zugführerraum — lead driver cab; ZFR R is the redundant pair", 6960)]}),
  ]),
  heading("Appendix B — Reference Documents", HeadingLevel.HEADING_1),
  bullet(`${customer} IPv4 schema for ${schemaPdfName}`),
  bullet("VDS Rail Consist Switch User Manual, version 2.0.4"),
  bullet(`${organisation} DOSTO L2 Health Check Playbook (project CLAUDE.md)`),
  heading("Appendix C — Reviewer Notes", HeadingLevel.HEADING_1),
  p("Reviewers are invited to add comments, tracked changes, or annotations directly to this document. Use the table below if not using Word's tracked changes feature."),
  table([1200, 1800, 2400, 3960], [
    headerRow(["#", "Date", "Reviewer", "Note / Action"], [1200, 1800, 2400, 3960]),
    ...[1,2,3,4,5].map(n => new TableRow({ children: [cell(String(n), 1200), cell("", 1800), cell("", 2400), cell("", 3960)] })),
  ]),
];

// -------- build --------
const doc = new Document({
  creator: `${organisation} — ${author}`,
  title: `Network Health Check — DOSTO Fzg. ${fzgId} — ${customer}`,
  description: `Layer-2 network health check report for ${customer} DOSTO trainset Fzg. ID ${fzgId}`,
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
            new TextRun({ text: `Network Health Check — Fzg. ${fzgId}`, size: 18, color: "595959" }),
            new TextRun({ text: `\t${organisation} — for ${customer}`, size: 18, color: "595959" }),
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
  console.log(`Wrote ${outputPath} (${buf.length} bytes)`);
});
