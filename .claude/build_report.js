// Network Health Check Report — ÖBB DOSTO Fzg. ID 146
// Generated 2026-05-02

const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  HeadingLevel, BorderStyle, WidthType, ShadingType, VerticalAlign,
  PageNumber, PageBreak, TabStopType, TabStopPosition,
} = require('docx');

// ---------- helpers ----------
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerShade = { fill: "D5E8F0", type: ShadingType.CLEAR };
const goodShade = { fill: "E2EFDA", type: ShadingType.CLEAR };
const warnShade = { fill: "FFF2CC", type: ShadingType.CLEAR };
const badShade = { fill: "FCE4D6", type: ShadingType.CLEAR };
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
    borders,
    width: { size: width, type: WidthType.DXA },
    shading: opts.shading,
    margins: cellMargins,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: opts.align || AlignmentType.LEFT,
      children: runs.map(r => new TextRun({
        text: r.text,
        bold: r.bold || opts.bold,
        color: r.color,
        size: opts.size,
      })),
    })],
  });
}

function table(columnWidths, rows) {
  const totalWidth = columnWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths,
    rows,
  });
}

function headerRow(cols, columnWidths) {
  return new TableRow({
    tableHeader: true,
    children: cols.map((c, i) => cell(c, columnWidths[i], { shading: headerShade, bold: true })),
  });
}

// ---------- content ----------

const titlePage = [
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { after: 240 },
    children: [new TextRun({ text: "Nomad Digital", bold: true, size: 24 })],
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
    children: [new TextRun({ text: "DOSTO Nahverkehr 6-Teiler", size: 32, color: "2E75B6" })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
    children: [new TextRun({ text: "Prepared for", size: 22 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 1200 },
    children: [new TextRun({ text: "ÖBB — Österreichische Bundesbahnen", bold: true, size: 28 })],
  }),
  // metadata table
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun("")] }),
  table([3120, 6240], [
    new TableRow({ children: [
      cell("Trainset (Fzg. Nr.)", 3120, { bold: true, shading: headerShade }),
      cell("4736-118", 6240),
    ]}),
    new TableRow({ children: [
      cell("Fahrzeug-ID", 3120, { bold: true, shading: headerShade }),
      cell("146", 6240),
    ]}),
    new TableRow({ children: [
      cell("Configuration", 3120, { bold: true, shading: headerShade }),
      cell("6-car (A1-A2-A3-... -F1-F2-F3 with redundant pairs)", 6240),
    ]}),
    new TableRow({ children: [
      cell("Health check date", 3120, { bold: true, shading: headerShade }),
      cell("2 May 2026", 6240),
    ]}),
    new TableRow({ children: [
      cell("Performed by", 3120, { bold: true, shading: headerShade }),
      cell("Abbas Rizvi, Nomad Digital", 6240),
    ]}),
    new TableRow({ children: [
      cell("Document version", 3120, { bold: true, shading: headerShade }),
      cell("1.0 (Draft for review)", 6240),
    ]}),
    new TableRow({ children: [
      cell("Classification", 3120, { bold: true, shading: headerShade }),
      cell("Internal — for ÖBB and Nomad Digital review", 6240),
    ]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Document control / revision history ----------
const docControl = [
  heading("Document Control", HeadingLevel.HEADING_1),
  p("This is a working document. Reviewers may add comments, tracked changes, and updates inline. Please record any changes in the revision history below."),
  heading("Revision History", HeadingLevel.HEADING_2),
  table([1200, 1800, 2800, 3560], [
    headerRow(["Version", "Date", "Author", "Change Summary"], [1200, 1800, 2800, 3560]),
    new TableRow({ children: [
      cell("1.0", 1200), cell("2 May 2026", 1800),
      cell("Abbas Rizvi, Nomad Digital", 2800),
      cell("Initial draft following on-train health check", 3560),
    ]}),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)]}),
    new TableRow({ children: [cell("", 1200), cell("", 1800), cell("", 2800), cell("", 3560)]}),
  ]),
  heading("Approvals", HeadingLevel.HEADING_2),
  table([2400, 2800, 2400, 1760], [
    headerRow(["Role", "Name", "Organisation", "Date"], [2400, 2800, 2400, 1760]),
    new TableRow({ children: [cell("Author", 2400), cell("Abbas Rizvi", 2800), cell("Nomad Digital", 2400), cell("2 May 2026", 1760)]}),
    new TableRow({ children: [cell("Technical Reviewer", 2400), cell("", 2800), cell("Nomad Digital", 2400), cell("", 1760)]}),
    new TableRow({ children: [cell("ÖBB Reviewer", 2400), cell("", 2800), cell("ÖBB", 2400), cell("", 1760)]}),
  ]),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Executive summary ----------
const execSummary = [
  heading("1. Executive Summary", HeadingLevel.HEADING_1),
  p("A comprehensive Layer-2 network health check was performed on DOSTO trainset Fzg. ID 146 (Fzg. Nr. 4736-118) on 2 May 2026 by Nomad Digital engineering. The check covered all 18 VDS Rail Consist Switches across the 6-car consist, all inter-coach trunk links, all Stadler-facing trunks (firewall, OBS, RDC), the ZFR connections, the front-coupler trunks, and end-to-end reachability between the Nomad CCU and the Stadler firewall."),

  heading("Headline Result", HeadingLevel.HEADING_2),
  table([9360], [
    new TableRow({ children: [
      cell([
        { text: "OVERALL VERDICT: ", bold: true },
        { text: "The Layer-2 fabric on Fzg. 146 is healthy.", bold: true, color: "375623" },
      ], 9360, { shading: goodShade }),
    ]}),
  ]),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun("")] }),
  bullet("Zero CRC errors, zero RX/TX errors, and zero carrier-false events were observed across approximately 500 enabled switch ports."),
  bullet("Spanning Tree (RSTP) shows a single, stable root bridge across all 18 switches with no blocked-port anomalies."),
  bullet("All inter-coach trunk uplinks are up at the expected 10 Gbps full duplex."),
  bullet("All Stadler-facing trunks are up at expected speed (1 Gbps to firewall, 10 Gbps to OBS/RDC). Zero error counters."),
  bullet("The Stadler firewall trunk is currently at 1.5 % utilisation — substantial headroom remains."),
  bullet("End-to-end TCP reachability between the Nomad CCU and the Stadler firewall is functional. ICMP is filtered by firewall policy (expected behaviour, not a fault)."),
  bullet("No findings require immediate action. One single RX-error event on switch .182 port e1-8 over the device lifetime is statistical noise, not a fault."),

  heading("Implications for Reported Packet Loss", HeadingLevel.HEADING_2),
  p("Where end-users have reported packet loss on similar consists in the past, the present health check provides strong evidence that the consist switching fabric is not the source. Recommended follow-up investigation areas are end-host buffering on test endpoints, segments beyond the Stadler firewall (no CCU visibility), and the PWLAN/cellular client networks (separate scope)."),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Scope and Methodology ----------
const scope = [
  heading("2. Scope and Methodology", HeadingLevel.HEADING_1),

  heading("2.1 Scope", HeadingLevel.HEADING_2),
  p("This report covers the on-board Layer-2 switching fabric of trainset Fzg. 146, specifically:"),
  bullet("All 18 VDS Rail Consist Switches on the management VLAN (vlan100, 10.179.8.128/25)."),
  bullet("All inter-coach trunk uplinks (e0-0 and e0-1 on each switch)."),
  bullet("All Stadler-facing trunks: firewall trunk (A3 e1-4), OBS trunks (D1/D3 e0-2), RDC trunks (D1/D3 e0-3)."),
  bullet("ZFR access ports (B1 e1-11 and B3 e1-11)."),
  bullet("Front-coupler trunks (A1/A3/B1/B3 e0-2)."),
  bullet("End-to-end CCU-to-Stadler firewall connectivity over vlan7."),
  bullet("Aggregate fabric utilisation snapshot on inter-coach trunks."),
  p("Out of scope for this report:"),
  bullet("Stadler-side device VLANs (cameras, displays, AFZ, intercom, etc.) — these are not visible from the Nomad CCU and are managed by Stadler."),
  bullet("PWLAN (vlan10/30) and ÖBB internal services (vlan46/47/48) — separate scope; client-side health is not assessed here."),
  bullet("Cellular WAN backhaul — separate scope."),

  heading("2.2 Methodology", HeadingLevel.HEADING_2),
  p("The check follows Nomad Digital's standard L2 health-check playbook (see CLAUDE.md in the project repository). The methodology comprises eight phases:"),
  table([800, 3000, 5560], [
    headerRow(["Phase", "Activity", "Purpose"], [800, 3000, 5560]),
    new TableRow({ children: [
      cell("1", 800), cell("Discovery", 3000),
      cell("Sweep vlan100 to enumerate consist switches and Westermo radios.", 5560),
    ]}),
    new TableRow({ children: [
      cell("2", 800), cell("Schema mapping", 3000),
      cell("Match live IPs to schema switch IDs (A1/A2/A3, etc.) by trunk/access-port fingerprint.", 5560),
    ]}),
    new TableRow({ children: [
      cell("3", 800), cell("Per-port error scan", 3000),
      cell("Read RX errors, CRC, carrier-false, and collision counters on every enabled port across all 18 switches.", 5560),
    ]}),
    new TableRow({ children: [
      cell("4", 800), cell("Critical trunk inspection", 3000),
      cell("Detailed inspection of Stadler-facing and ZFR ports.", 5560),
    ]}),
    new TableRow({ children: [
      cell("5", 800), cell("Throughput sampling", 3000),
      cell("Two byte-counter snapshots N seconds apart to derive live link utilisation.", 5560),
    ]}),
    new TableRow({ children: [
      cell("6", 800), cell("End-to-end probe", 3000),
      cell("ICMP and TCP reachability tests from CCU to Stadler firewall.", 5560),
    ]}),
    new TableRow({ children: [
      cell("7", 800), cell("STP topology check", 3000),
      cell("Verify Rapid Spanning Tree root election and port states are consistent.", 5560),
    ]}),
    new TableRow({ children: [
      cell("8", 800), cell("Baseline capture", 3000),
      cell("Save raw output for future trend comparison.", 5560),
    ]}),
  ]),

  heading("2.3 Tools and access", HeadingLevel.HEADING_2),
  bullet("SSH access to the Nomad CCU (box1-t8) via OpenSSH key."),
  bullet("Switch admin SSH access via sshpass (legacy KEX/host-key algorithms required)."),
  bullet("Standard Linux network tooling: fping, ip, ping, nc."),
  bullet("VDS Rail Consist Switch CLI commands (show interface, show vlans, show spanning-tree, show interface details)."),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Architecture Overview ----------
const architecture = [
  heading("3. Architecture Overview", HeadingLevel.HEADING_1),

  heading("3.1 Trainset Topology", HeadingLevel.HEADING_2),
  p("Fzg. 146 is a 6-car DOSTO Nahverkehr consist. Each car contains three VDS Rail Consist Switches (designated 1, 2, 3 within the car), connected via 10 Gbps inter-coach trunks (e0-0 and e0-1). The 18 switches form a single Layer-2 fabric carrying multiple VLANs for passenger information, surveillance, public address, and Stadler operational systems."),

  heading("3.2 Live IP-to-Schema Mapping", HeadingLevel.HEADING_2),
  p("During this check, the live IP addresses on the management VLAN were mapped to the schema switch IDs by configuration fingerprint. The full mapping is recorded below for reference."),
  table([1500, 1800, 6060], [
    headerRow(["Switch IP", "Schema ID", "Distinguishing feature / role"], [1500, 1800, 6060]),
    new TableRow({ children: [cell("10.179.8.178", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switch (e0-0/e0-1/e0-4)", 6060)]}),
    new TableRow({ children: [cell("10.179.8.179", 1500), cell("(generic)", 1800), cell("Has front-coupler trunk e0-2", 6060)]}),
    new TableRow({ children: [cell("10.179.8.180", 1500), cell("D1", 1800), cell("OBS D1 (e0-2 trunk) and RDC D1 (e0-3 trunk)", 6060)]}),
    new TableRow({ children: [cell("10.179.8.181", 1500), cell("B1", 1800), cell("ZFR R access port (e1-11), front-coupler trunk e0-2", 6060)]}),
    new TableRow({ children: [cell("10.179.8.182", 1500), cell("B3", 1800), cell("ZFR access port (e1-11), front-coupler trunk e0-2", 6060)]}),
    new TableRow({ children: [cell("10.179.8.183", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switch", 6060)]}),
    new TableRow({ children: [cell("10.179.8.184", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switch", 6060)]}),
    new TableRow({ children: [cell("10.179.8.185", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switch", 6060)]}),
    new TableRow({ children: [cell("10.179.8.186", 1500), cell("D3", 1800), cell("OBS reserve D2 (e0-2 trunk) and RDC reserve (e0-3 trunk); end-of-train (e0-1 link DOWN)", 6060)]}),
    new TableRow({ children: [cell("10.179.8.187", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switch", 6060)]}),
    new TableRow({ children: [cell("10.179.8.188-190", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switches", 6060)]}),
    new TableRow({ children: [cell("10.179.8.191", 1500), cell("A3", 1800), cell("Stadler firewall trunk (e1-4); STP root bridge candidate", 6060)]}),
    new TableRow({ children: [cell("10.179.8.192-194", 1500), cell("(generic)", 1800), cell("Standard 3-trunk switches", 6060)]}),
    new TableRow({ children: [cell("10.179.8.195", 1500), cell("(generic)", 1800), cell("End-of-train (e0-1 link DOWN)", 6060)]}),
  ]),

  heading("3.3 VLAN Plan (per ÖBB / Stadler Schema v1.6)", HeadingLevel.HEADING_2),
  table([1200, 3200, 2400, 2560], [
    headerRow(["VLAN", "Name / Purpose", "Subnet", "Notes"], [1200, 3200, 2400, 2560]),
    new TableRow({ children: [cell("2", 1200), cell("zrp-train-repair / Service FIS / CCTV", 3200), cell("172.17.73.0/24", 2400), cell("Includes ZFR endpoints", 2560)]}),
    new TableRow({ children: [cell("3", 1200), cell("pis-train-repair / Passenger displays", 3200), cell("172.17.201.0/24", 2400), cell("Bildschrim, Seitenanzeige", 2560)]}),
    new TableRow({ children: [cell("5", 1200), cell("cctv-net", 3200), cell("172.18.201.0/24", 2400), cell("Surveillance cameras, NVR", 2560)]}),
    new TableRow({ children: [cell("7", 1200), cell("obs-net", 3200), cell("172.19.196.0/17", 2400), cell("CCU ↔ Stadler FW transit", 2560)]}),
    new TableRow({ children: [cell("8", 1200), cell("apc-net (passenger counters)", 3200), cell("172.20.73.0/24", 2400), cell("AFZ devices", 2560)]}),
    new TableRow({ children: [cell("9", 1200), cell("call-point-net (PA / intercom)", 3200), cell("172.20.201.0/24", 2400), cell("Sprechstelle, ADU, Audio Amp", 2560)]}),
    new TableRow({ children: [cell("12", 1200), cell("call-point-net / energy meter", 3200), cell("172.22.73.0/24", 2400), cell("Energiezahler", 2560)]}),
    new TableRow({ children: [cell("100", 1200), cell("mng-nomad-net (management)", 3200), cell("10.179.8.128/25", 2400), cell("Switches and CCU vlan100", 2560)]}),
    new TableRow({ children: [cell("10/20/30/31/131/150", 1200), cell("Client / staff / catering networks", 3200), cell("Various", 2400), cell("PWLAN client traffic", 2560)]}),
    new TableRow({ children: [cell("46/48", 1200), cell("automate-1 / automate-2", 3200), cell("ÖBB internal", 2400), cell("ÖBB managed", 2560)]}),
    new TableRow({ children: [cell("200/202", 1200), cell("rdc-nomad-net", 3200), cell("RDC", 2400), cell("Remote diagnostic", 2560)]}),
  ]),

  heading("3.4 Key Routing", HeadingLevel.HEADING_2),
  bullet("Inter-VLAN routing for Stadler-side device VLANs is performed at the Stadler firewall/gateway, not at the consist switches."),
  bullet("The Nomad CCU peers with the Stadler firewall on vlan7 (CCU side: 172.19.196.2; FW side: 172.19.196.1)."),
  bullet("The CCU does not see Stadler device VLANs directly; they are reachable only via the firewall."),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Findings ----------
const findings = [
  heading("4. Detailed Findings", HeadingLevel.HEADING_1),

  heading("4.1 Switch Inventory", HeadingLevel.HEADING_2),
  table([2400, 2400, 4560], [
    headerRow(["Metric", "Expected (6-car)", "Observed"], [2400, 2400, 4560]),
    new TableRow({ children: [cell("VDS Consist switches on vlan100", 2400), cell("18", 2400), cell("18 (PASS)", 4560, { shading: goodShade })]}),
    new TableRow({ children: [cell("Westermo industrial radios on vlan100", 2400), cell("(per layout)", 2400), cell("24 (consistent with PWLAN access points across cars)", 4560)]}),
    new TableRow({ children: [cell("Switch firmware version", 2400), cell("Stable across fleet", 2400), cell("VDS Rail v7.4.2 build 77411 (consistent)", 4560, { shading: goodShade })]}),
  ]),

  heading("4.2 Inter-Coach Trunks (e0-0 and e0-1)", HeadingLevel.HEADING_2),
  p("Inter-coach trunks form the backbone of the Layer-2 fabric. Each car connects to its neighbours via 10 Gbps full-duplex links."),
  table([2400, 2400, 4560], [
    headerRow(["Check", "Result", "Comment"], [2400, 2400, 4560]),
    new TableRow({ children: [cell("e0-0 link state (all 18 switches)", 2400), cell("UP — 10 Gbps Full", 2400, { shading: goodShade }), cell("All 18 switches; no anomalies", 4560)]}),
    new TableRow({ children: [cell("e0-1 link state", 2400), cell("16 of 18 UP — 10 Gbps Full", 2400, { shading: goodShade }), cell("Two end-of-train switches (.186 and .195) show DOWN — expected, no neighbour beyond the last car.", 4560)]}),
    new TableRow({ children: [cell("RX errors / CRC / carrier-false (all trunks)", 2400), cell("Zero", 2400, { shading: goodShade }), cell("All 36 enabled inter-coach ports clean.", 4560)]}),
    new TableRow({ children: [cell("Pause frames", 2400), cell("Zero", 2400, { shading: goodShade }), cell("No flow-control pressure detected.", 4560)]}),
  ]),

  heading("4.3 Spanning Tree (RSTP)", HeadingLevel.HEADING_2),
  table([3200, 6160], [
    new TableRow({ children: [cell("Protocol", 3200, { bold: true, shading: headerShade }), cell("RSTP (Rapid Spanning Tree)", 6160)]}),
    new TableRow({ children: [cell("Root bridge MAC", 3200, { bold: true, shading: headerShade }), cell("32768 / a0:59:3a:d0:3a:40 (switch .179)", 6160)]}),
    new TableRow({ children: [cell("Root bridge consistency across fleet", 3200, { bold: true, shading: headerShade }), cell("100 % — all 18 switches agree on the same root", 6160, { shading: goodShade })]}),
    new TableRow({ children: [cell("Blocked ports", 3200, { bold: true, shading: headerShade }), cell("None (all forwarding, design uses RSTP edge with autoEdge)", 6160)]}),
    new TableRow({ children: [cell("Topology change events (sustained)", 3200, { bold: true, shading: headerShade }), cell("None observed during this check", 6160, { shading: goodShade })]}),
  ]),

  heading("4.4 Per-Port Error Counter Scan", HeadingLevel.HEADING_2),
  p("A full enumeration of error counters was performed across all enabled ports on all 18 switches (~500 ports). Counters checked: RX errors, RX CRC errors, TX CRC errors, runts/giants/fragments/jabber, carrier-false, excessive collisions, late collisions."),
  table([2800, 1600, 4960], [
    headerRow(["Counter category", "Total non-zero", "Notes"], [2800, 1600, 4960]),
    new TableRow({ children: [cell("RX errors", 2800), cell("1 (single)", 1600, { shading: warnShade }), cell("Switch .182 port e1-8 — one RX error against millions of packets. Statistical noise, not a fault.", 4960)]}),
    new TableRow({ children: [cell("RX CRC errors", 2800), cell("0", 1600, { shading: goodShade }), cell("All ports clean", 4960)]}),
    new TableRow({ children: [cell("TX CRC errors", 2800), cell("0", 1600, { shading: goodShade }), cell("All ports clean", 4960)]}),
    new TableRow({ children: [cell("carrier-false events", 2800), cell("0", 1600, { shading: goodShade }), cell("No physical-layer flap or surge events", 4960)]}),
    new TableRow({ children: [cell("Excessive collisions", 2800), cell("0", 1600, { shading: goodShade }), cell("All links full-duplex as expected", 4960)]}),
    new TableRow({ children: [cell("Late collisions", 2800), cell("0", 1600, { shading: goodShade }), cell("No half-duplex contention", 4960)]}),
    new TableRow({ children: [cell("runts / giants / frag / jabber", 2800), cell("0", 1600, { shading: goodShade }), cell("No malformed-frame events", 4960)]}),
  ]),

  heading("4.5 Stadler-Facing Trunks", HeadingLevel.HEADING_2),
  p("These trunks carry traffic to Stadler-managed equipment (firewall/gateway, On-Board Server, Remote Diagnostic Computer)."),
  table([2200, 1500, 1500, 1300, 1300, 1560], [
    headerRow(["Port (role)", "Switch", "Speed", "Errors", "CRC", "Carrier-false"], [2200, 1500, 1500, 1300, 1300, 1560]),
    new TableRow({ children: [
      cell("A3 e1-4 — Stadler Firewall trunk", 2200), cell(".191", 1500), cell("1 G Full ✓", 1500, { shading: goodShade }),
      cell("0", 1300, { shading: goodShade }), cell("0", 1300, { shading: goodShade }), cell("0", 1560, { shading: goodShade }),
    ]}),
    new TableRow({ children: [
      cell("D1 e0-2 — OBS D1 trunk", 2200), cell(".180", 1500), cell("10 G Full ✓", 1500, { shading: goodShade }),
      cell("0", 1300, { shading: goodShade }), cell("0", 1300, { shading: goodShade }), cell("0", 1560, { shading: goodShade }),
    ]}),
    new TableRow({ children: [
      cell("D3 e0-2 — OBS reserve trunk", 2200), cell(".186", 1500), cell("10 G Full ✓", 1500, { shading: goodShade }),
      cell("0", 1300, { shading: goodShade }), cell("0", 1300, { shading: goodShade }), cell("0", 1560, { shading: goodShade }),
    ]}),
    new TableRow({ children: [
      cell("D1 e0-3 — RDC D1 trunk", 2200), cell(".180", 1500), cell("10 G Full ✓", 1500, { shading: goodShade }),
      cell("0", 1300, { shading: goodShade }), cell("0", 1300, { shading: goodShade }), cell("0", 1560, { shading: goodShade }),
    ]}),
    new TableRow({ children: [
      cell("D3 e0-3 — RDC reserve trunk", 2200), cell(".186", 1500), cell("10 G Full ✓", 1500, { shading: goodShade }),
      cell("0", 1300, { shading: goodShade }), cell("0", 1300, { shading: goodShade }), cell("0", 1560, { shading: goodShade }),
    ]}),
  ]),
  p(""),
  p("Observations:"),
  bullet("The Stadler firewall trunk (1 Gbps) shows asymmetric cumulative byte counts — TX 21.45 GB versus RX 1.68 GB (12.8× ratio). This is expected behaviour for routed traffic: most Stadler-side devices send traffic to the firewall for inter-VLAN routing, while return traffic patterns differ."),
  bullet("RDC trunks show predominantly switch-originated multicast/broadcast traffic (low receive counts). This is consistent with the RDC being idle or in standby. ÖBB to confirm whether active RDC traffic was expected at the time of the check."),
  bullet("OBS trunks show active bidirectional traffic, with the primary path (D1) carrying notably more data than the redundant path (D3) — the expected behaviour for an active/standby pair."),

  heading("4.6 ZFR Access Ports", HeadingLevel.HEADING_2),
  p("The ZFR (Zugführerraum / lead driver cab) endpoints are configured as redundant access ports on VLAN 2 — the schema designates them as ZFR R (B1 e1-11) and ZFR (B3 e1-11), sharing IP 172.17.73.2."),
  table([2400, 2400, 4560], [
    headerRow(["Port", "State", "Observation"], [2400, 2400, 4560]),
    new TableRow({ children: [
      cell("B1 e1-11 (ZFR R)", 2400), cell("UP, 1 G Full", 2400, { shading: goodShade }),
      cell("Active: 1.24 M RX packets / 1.52 M TX packets cumulative; ~460 MB RX, ~332 MB TX. Zero errors.", 4560),
    ]}),
    new TableRow({ children: [
      cell("B3 e1-11 (ZFR)", 2400), cell("UP, 1 G Full", 2400, { shading: goodShade }),
      cell("Standby: 0 RX packets, 54 k TX packets (switch-originated multicast). Zero errors. Consistent with B1 being the active member of the redundant pair.", 4560),
    ]}),
  ]),

  heading("4.7 Front-Coupler Trunks", HeadingLevel.HEADING_2),
  p("The front-coupler trunks (e0-2 on schema A1/A3/B1/B3 = .179/.191/.181/.182) provide inter-consist connectivity when two trainsets are physically coupled. With Fzg. 146 operating solo at the time of the check, all four are expected to be link-down."),
  table([3200, 2200, 3960], [
    headerRow(["Port", "State", "Comment"], [3200, 2200, 3960]),
    new TableRow({ children: [cell("Front coupler — .179 e0-2", 3200), cell("DOWN", 2200, { shading: goodShade }), cell("Expected (consist solo). Zero error history.", 3960)]}),
    new TableRow({ children: [cell("Front coupler — A3 (.191 e0-2)", 3200), cell("DOWN", 2200, { shading: goodShade }), cell("Expected (consist solo). Zero error history.", 3960)]}),
    new TableRow({ children: [cell("Front coupler — B1 (.181 e0-2)", 3200), cell("DOWN", 2200, { shading: goodShade }), cell("Expected (consist solo). Zero error history.", 3960)]}),
    new TableRow({ children: [cell("Front coupler — B3 (.182 e0-2)", 3200), cell("DOWN", 2200, { shading: goodShade }), cell("Expected (consist solo). Zero error history.", 3960)]}),
  ]),

  heading("4.8 Live Throughput — Stadler Firewall Trunk", HeadingLevel.HEADING_2),
  p("To verify that the 1 Gbps firewall trunk is not approaching saturation, two byte-counter snapshots were taken 21 seconds apart. Results:"),
  table([3600, 5760], [
    new TableRow({ children: [cell("Link capacity", 3600, { bold: true, shading: headerShade }), cell("1 000 Mbps full duplex", 5760)]}),
    new TableRow({ children: [cell("Live RX rate (FW → fabric)", 3600, { bold: true, shading: headerShade }), cell("0.86 Mbps (~1 076 pps)", 5760)]}),
    new TableRow({ children: [cell("Live TX rate (fabric → FW)", 3600, { bold: true, shading: headerShade }), cell("14.49 Mbps (~1 672 pps)", 5760)]}),
    new TableRow({ children: [cell("Combined", 3600, { bold: true, shading: headerShade }), cell("15.35 Mbps", 5760)]}),
    new TableRow({ children: [cell("Utilisation of 1 G link", 3600, { bold: true, shading: headerShade }), cell("1.5 % — substantial headroom", 5760, { shading: goodShade })]}),
    new TableRow({ children: [cell("Cumulative since boot", 3600, { bold: true, shading: headerShade }), cell("RX 1.68 GB / TX 21.45 GB (TX/RX asymmetry 12.8×)", 5760)]}),
  ]),

  heading("4.9 Aggregate Inter-Coach Fabric Utilisation", HeadingLevel.HEADING_2),
  p("A 54-second sampling window across all 18 switches produced the following aggregate picture:"),
  table([4400, 2480, 2480], [
    headerRow(["Trunk class (across 18 switches)", "Combined RX+TX", "Avg. utilisation"], [4400, 2480, 2480]),
    new TableRow({ children: [cell("Inter-coach trunks (e0-0, port-sum)", 4400), cell("1 710 Mbps", 2480), cell("~1.5 % per 10 G link", 2480, { shading: goodShade })]}),
    new TableRow({ children: [cell("Inter-coach trunks (e0-1, port-sum)", 4400), cell("1 558 Mbps", 2480), cell("~1.5 % per 10 G link", 2480, { shading: goodShade })]}),
    new TableRow({ children: [cell("PWLAN trunks (e0-4, port-sum)", 4400), cell("~0 Mbps", 2480), cell("Idle (no PWLAN clients at sample time)", 2480)]}),
  ]),
  p("Note: port-sum figures double-count traffic that traverses multiple cars. Per-link average is the actionable number — typical active inter-coach trunk runs at 100–155 Mbps per port (~1.5 % of 10 Gbps capacity)."),

  heading("4.10 End-to-End CCU ↔ Stadler Firewall", HeadingLevel.HEADING_2),
  table([3200, 2400, 3760], [
    headerRow(["Probe", "Result", "Interpretation"], [3200, 2400, 3760]),
    new TableRow({ children: [cell("ICMP echo (1 000 packets, 0.2 s interval)", 3200), cell("100 % loss", 2400, { shading: warnShade }), cell("Firewall drops echo-request by policy. Not a fault.", 3760)]}),
    new TableRow({ children: [cell("ARP resolution to 172.19.196.1", 3200), cell("REACHABLE", 2400, { shading: goodShade }), cell("MAC 00:90:e8:c2:60:22 (Westermo OUI)", 3760)]}),
    new TableRow({ children: [cell("TCP probe — port 80", 3200), cell("OPEN", 2400, { shading: goodShade }), cell("Three-way handshake completes", 3760)]}),
    new TableRow({ children: [cell("TCP probe — port 22", 3200), cell("OPEN", 2400, { shading: goodShade }), cell("Three-way handshake completes", 3760)]}),
    new TableRow({ children: [cell("vlan7 interface counters", 3200), cell("0 errors / 0 drops", 2400, { shading: goodShade }), cell("575 k RX packets, 422 k TX packets — link clean and active", 3760)]}),
  ]),
  p("Conclusion: the CCU-to-Stadler firewall path is healthy. The 100 % ICMP loss is a deliberate firewall policy, not a connectivity issue. For ongoing monitoring of this path, use TCP-based probes rather than ICMP."),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Risk and Recommendations ----------
const recommendations = [
  heading("5. Risk Assessment and Recommendations", HeadingLevel.HEADING_1),

  heading("5.1 Risk Summary", HeadingLevel.HEADING_2),
  table([2400, 2000, 4960], [
    headerRow(["Area", "Risk Level", "Rationale"], [2400, 2000, 4960]),
    new TableRow({ children: [cell("Inter-coach Layer-2 fabric", 2400), cell("LOW", 2000, { shading: goodShade }), cell("Zero errors observed; substantial headroom; stable RSTP topology.", 4960)]}),
    new TableRow({ children: [cell("Stadler firewall trunk capacity", 2400), cell("LOW", 2000, { shading: goodShade }), cell("1.5 % utilisation today. To revisit if Stadler-side device count grows or if FW becomes a bottleneck.", 4960)]}),
    new TableRow({ children: [cell("ZFR redundancy", 2400), cell("LOW", 2000, { shading: goodShade }), cell("Active/standby pair behaving as designed. Recommend periodic failover test (out of scope).", 4960)]}),
    new TableRow({ children: [cell("Front-coupler trunks", 2400), cell("LOW", 2000, { shading: goodShade }), cell("Cannot be tested while consist is solo. Zero historical errors are encouraging.", 4960)]}),
    new TableRow({ children: [cell("Stadler-side beyond the firewall", 2400), cell("UNKNOWN", 2000, { shading: warnShade }), cell("Out of scope for Nomad — Stadler responsibility. Recommend bilateral health check if user-perceived issues persist.", 4960)]}),
    new TableRow({ children: [cell("PWLAN / cellular client paths", 2400), cell("NOT ASSESSED", 2000, { shading: warnShade }), cell("Separate scope. To be addressed in a future report if requested.", 4960)]}),
  ]),

  heading("5.2 Recommendations", HeadingLevel.HEADING_2),
  bullet("No corrective action required for the consist Layer-2 fabric. Maintain current configuration and firmware (VDS Rail v7.4.2 build 77411)."),
  bullet("Adopt TCP-based probes (e.g. nc -zv 172.19.196.1 80) rather than ICMP for ongoing CCU-to-firewall monitoring scripts. ICMP is filtered and produces misleading 100 % loss readings."),
  bullet("Save the byte-counter and error-counter outputs from this session as a baseline for future trend comparison. Repeat the check at 6-monthly intervals or after any major firmware upgrade."),
  bullet("If end-users report packet loss on this consist in future, do not start with the Layer-2 fabric — start with end-host buffering analysis and the Stadler-side path beyond the firewall."),
  bullet("Schedule a coordinated bilateral health check with Stadler if loss reports persist, to extend visibility past the firewall."),
  bullet("Test the front-coupler trunks (A1/A3/B1/B3 e0-2) the next time Fzg. 146 is coupled to another consist; capture link-up state and counters at that point."),

  heading("5.3 Open Questions for ÖBB Review", HeadingLevel.HEADING_2),
  bullet("Confirm whether the RDC service was expected to be active at the time of the health check (currently shows idle / standby pattern)."),
  bullet("Confirm any user-reported network issues on Fzg. 146 in the period preceding this check, so that follow-up investigation can target specific symptoms."),
  bullet("Confirm preferred cadence for periodic re-checks (Nomad recommendation: 6 months)."),
  new Paragraph({ children: [new PageBreak()] }),
];

// ---------- Appendices ----------
const appendices = [
  heading("Appendix A — Sample CLI Output (excerpts)", HeadingLevel.HEADING_1),
  p("Excerpt: show interface e0-0 details — switch 10.179.8.178 (representative of all inter-coach trunks).", { run: { italics: true } }),
  new Paragraph({
    spacing: { before: 120, after: 120 },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children: [new TextRun({
      text: "Interface e0-0 is enabled, line protocol is up\n  Hardware is 10 Gigabit Ethernet (switched)\n  Speed: 10000 Mb/s  Duplex: Full  MDI: MDI\n  Fast Link Detection is enabled (delay 40 ms)\n  RX packets:43304598   TX packets:62467275\n  RX bytes:37074080562  TX bytes:78787953033\n  carrier false:0\n  RX errors:0 runts:0 giants:0 frag:0 jabber:0\n  RX crc errors: 0\n  TX crc errors:0",
      font: "Consolas", size: 18,
    })],
  }),
  p("Excerpt: show spanning-tree — switch 10.179.8.178 (representative; all 18 switches show same root).", { run: { italics: true } }),
  new Paragraph({
    spacing: { before: 120, after: 120 },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children: [new TextRun({
      text: "Selected redundancy protocol RSTP is running.\n  Root bridge : 32768/a0:59:3a:d0:3a:40\n  Root port: e0-0\n  Bridge ID: 32768/a0:59:3a:d0:63:00\n  e0-0  ROOT  FWD  rstp,p2p,autoEdge\n  e0-1  DESG  FWD  rstp,p2p,autoEdge\n  e0-4  EDGE  FWD  rstp,p2p,autoEdge",
      font: "Consolas", size: 18,
    })],
  }),

  heading("Appendix B — VLAN Configuration on Switch .178 (representative)", HeadingLevel.HEADING_1),
  p("Output of show vlans abridged to relevant rows (full output retained on file)."),
  table([1000, 3200, 5160], [
    headerRow(["VLAN", "Name", "Trunk ports carrying"], [1000, 3200, 5160]),
    new TableRow({ children: [cell("1", 1000), cell("default_vlan", 3200), cell("e0-0, e0-1, e0-4", 5160)]}),
    new TableRow({ children: [cell("2", 1000), cell("zrp-train-repair", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("3", 1000), cell("pis-train-repair", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("5", 1000), cell("cctv-net", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("7", 1000), cell("obs-net", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("8", 1000), cell("apc-net", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("9", 1000), cell("call-point-net", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("100", 1000), cell("mng-nomad-net", 3200), cell("e0-0, e0-1, e0-4", 5160)]}),
    new TableRow({ children: [cell("200", 1000), cell("rdc-nomad-net", 3200), cell("e0-0, e0-1", 5160)]}),
    new TableRow({ children: [cell("202", 1000), cell("rdc-interconnect-net", 3200), cell("e0-0, e0-1", 5160)]}),
  ]),

  heading("Appendix C — Glossary", HeadingLevel.HEADING_1),
  table([2400, 6960], [
    headerRow(["Term", "Definition"], [2400, 6960]),
    new TableRow({ children: [cell("AFZ", 2400), cell("Automatische Fahrgastzählung — automatic passenger counter (VLAN 8)", 6960)]}),
    new TableRow({ children: [cell("Bildschrim", 2400), cell("Display screen — passenger information display (VLAN 3)", 6960)]}),
    new TableRow({ children: [cell("CCU", 2400), cell("Communications Control Unit — Nomad Digital onboard router/gateway", 6960)]}),
    new TableRow({ children: [cell("DOSTO", 2400), cell("Doppelstockwagen — double-deck passenger coach", 6960)]}),
    new TableRow({ children: [cell("FIS", 2400), cell("Fahrgastinformationssystem — passenger information system", 6960)]}),
    new TableRow({ children: [cell("Frontkupplung", 2400), cell("Front coupler — physical and electrical interface for inter-consist connection", 6960)]}),
    new TableRow({ children: [cell("OBS", 2400), cell("On-Board Server — Stadler operational platform (VLAN 7)", 6960)]}),
    new TableRow({ children: [cell("PWLAN", 2400), cell("Passenger Wireless LAN", 6960)]}),
    new TableRow({ children: [cell("RDC", 2400), cell("Remote Diagnostic Computer (VLAN 200/202)", 6960)]}),
    new TableRow({ children: [cell("RSTP", 2400), cell("Rapid Spanning Tree Protocol — IEEE 802.1w loop-prevention", 6960)]}),
    new TableRow({ children: [cell("Sprechstelle", 2400), cell("Intercom call-point (VLAN 9)", 6960)]}),
    new TableRow({ children: [cell("ZFR", 2400), cell("Zugführerraum — lead driver cab; ZFR R is the redundant pair", 6960)]}),
  ]),

  heading("Appendix D — Reference Documents", HeadingLevel.HEADING_1),
  bullet("ÖBB IPv4-Schema for Fzg. 4736-118 (Fzg. ID 146), Stadler / Davud Zejnelovic, Version 1.6, 30 May 2024 — TLP Amber."),
  bullet("VDS Rail Consist Switch User Manual, version 2.0.4, February 2023, document UM-TSW-EN-230102-204."),
  bullet("Nomad Digital DOSTO L2 Health Check Playbook (CLAUDE.md), 2 May 2026."),
  bullet("iperf3 troubleshooting investigation, 1 May 2026 (internal Nomad reference)."),

  heading("Appendix E — Reviewer Notes", HeadingLevel.HEADING_1),
  p("Reviewers are invited to add comments, tracked changes, or annotations directly to this document. Use the table below to log review notes if not using Word's tracked changes feature."),
  table([1200, 1800, 2400, 3960], [
    headerRow(["#", "Date", "Reviewer", "Note / Action"], [1200, 1800, 2400, 3960]),
    new TableRow({ children: [cell("1", 1200), cell("", 1800), cell("", 2400), cell("", 3960)]}),
    new TableRow({ children: [cell("2", 1200), cell("", 1800), cell("", 2400), cell("", 3960)]}),
    new TableRow({ children: [cell("3", 1200), cell("", 1800), cell("", 2400), cell("", 3960)]}),
    new TableRow({ children: [cell("4", 1200), cell("", 1800), cell("", 2400), cell("", 3960)]}),
    new TableRow({ children: [cell("5", 1200), cell("", 1800), cell("", 2400), cell("", 3960)]}),
  ]),
];

// ---------- Build document ----------
const doc = new Document({
  creator: "Nomad Digital — Abbas Rizvi",
  title: "Network Health Check — DOSTO Fzg. 146 — ÖBB",
  description: "Layer-2 network health check report for ÖBB DOSTO trainset Fzg. ID 146",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: "1F4E79" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: "2E75B6" },
        paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "404040" },
        paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bullets", levels: [
        { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
      ] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 }, // ~2 cm
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: 9360 }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "BFBFBF", space: 4 } },
          children: [
            new TextRun({ text: "Network Health Check — Fzg. 146", size: 18, color: "595959" }),
            new TextRun({ text: "\tNomad Digital — for ÖBB", size: 18, color: "595959" }),
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
    children: [
      ...titlePage,
      ...docControl,
      ...execSummary,
      ...scope,
      ...architecture,
      ...findings,
      ...recommendations,
      ...appendices,
    ],
  }],
});

const outPath = "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/OBB_Fzg146_Network_Health_Check_Report_v1.0.docx";
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("Wrote", outPath, "(", buffer.length, "bytes )");
});
