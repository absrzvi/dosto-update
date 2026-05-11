#!/usr/bin/env node
"use strict";

const {
  Document, Packer, Paragraph, Table, TableRow, TableCell,
  TextRun, HeadingLevel, AlignmentType, WidthType, BorderStyle,
  ShadingType, Header, Footer, PageNumber, NumberFormat,
  TableLayoutType, VerticalAlign,
} = require("docx");
const fs   = require("fs");
const path = require("path");

const args = {};
process.argv.slice(2).forEach((a, i, arr) => {
  if (a.startsWith("--")) args[a.slice(2)] = arr[i + 1];
});

const findingsPath  = args["findings"];
const customer      = args["customer"]      || "Stadler Rail";
const fzgNr         = args["fzg-nr"]        || "4736-109";
const fzgId         = args["fzg-id"]        || "109";
const consistSize   = args["consist-size"]  || "6-car";
const author        = args["author"]        || "Abbas Rizvi";
const organisation  = args["organisation"]  || "Nomad Digital";
const checkDate     = args["date"]          || new Date().toISOString().slice(0, 10);
const outputPath    = args["output"]        ||
  path.join(path.dirname(findingsPath || "."),
    `Stadler_${fzgNr}_L2_Health_Check_Report_v1.0.docx`);

const F = findingsPath ? JSON.parse(fs.readFileSync(findingsPath, "utf8")) : {};

// ── Colours ───────────────────────────────────────────────────────────────────
const C = {
  darkBlue:  "1F4E79",
  midBlue:   "2E75B6",
  lightBlue: "D6E4F0",
  headerGrey:"404040",
  red:       "C00000",
  orange:    "ED7D31",
  green:     "375623",
  greenBg:   "E2EFDA",
  redBg:     "FCE4D6",
  yellowBg:  "FFF2CC",
  white:     "FFFFFF",
  tableHead: "1F4E79",
  tableAlt:  "EBF3FB",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
const bold   = (t, sz=20, col) => new TextRun({ text: t, bold: true,  size: sz, color: col });
const normal = (t, sz=20, col) => new TextRun({ text: t, bold: false, size: sz, color: col });
const italic = (t, sz=20, col) => new TextRun({ text: t, italics: true, size: sz, color: col });

function para(runs, opts = {}) {
  return new Paragraph({ children: Array.isArray(runs) ? runs : [runs], ...opts });
}
function h1(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 32, color: C.darkBlue })],
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 300, after: 120 },
  });
}
function h2(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 24, color: C.midBlue })],
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 80 },
  });
}
function h3(text) {
  return new Paragraph({
    children: [new TextRun({ text, bold: true, size: 20, color: C.headerGrey })],
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 160, after: 60 },
  });
}
function bullet(text, lvl = 0) {
  return new Paragraph({
    children: [normal(text)],
    bullet: { level: lvl },
    spacing: { after: 40 },
  });
}
function spacer(lines = 1) {
  return new Paragraph({ children: [new TextRun("")], spacing: { after: 120 * lines } });
}
function pageBreak() {
  return new Paragraph({ pageBreakBefore: true, children: [new TextRun("")] });
}
function cell(children, opts = {}) {
  const { bg, bold: isBold, color, width, vAlign, colSpan } = opts;
  return new TableCell({
    children: Array.isArray(children) ? children : [
      new Paragraph({
        children: [new TextRun({ text: String(children), bold: !!isBold, size: 18, color: color || "000000" })],
        alignment: opts.align || AlignmentType.LEFT,
        spacing: { before: 40, after: 40 },
      })
    ],
    shading: bg ? { type: ShadingType.CLEAR, fill: bg } : undefined,
    width: width ? { size: width, type: WidthType.DXA } : undefined,
    verticalAlign: vAlign || VerticalAlign.CENTER,
    columnSpan: colSpan,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
  });
}
function headerRow(cols) {
  return new TableRow({
    children: cols.map(c => cell(c, { bg: C.tableHead, bold: true, color: C.white })),
    tableHeader: true,
  });
}
function simpleTable(headers, rows, widths) {
  return new Table({
    width: { size: 9200, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    rows: [
      headerRow(headers),
      ...rows.map((r, ri) =>
        new TableRow({
          children: r.map((c, ci) =>
            typeof c === "object" && c._isCell ? c :
            cell(c, { bg: ri % 2 === 1 ? C.tableAlt : C.white, width: widths?.[ci] })
          ),
        })
      ),
    ],
  });
}
function statusCell(label, bg, textColor) {
  return new TableCell({
    children: [new Paragraph({
      children: [new TextRun({ text: label, bold: true, size: 18, color: textColor || C.white })],
      alignment: AlignmentType.CENTER,
      spacing: { before: 40, after: 40 },
    })],
    shading: { type: ShadingType.CLEAR, fill: bg },
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
  });
}
const passCell = () => statusCell("PASS",    C.green,  C.white);
const warnCell = () => statusCell("WARNING", C.orange, C.white);
const naCell   = () => statusCell("N/A",     "808080", C.white);

// ── Document ──────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [{
      reference: "default-bullets",
      levels: [{ level: 0, format: NumberFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
    }],
  },
  styles: {
    default: { document: { run: { font: "Calibri", size: 20 } } },
  },
  sections: [{
    properties: {
      page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            bold("Nomad Digital", 18, C.midBlue),
            normal("  |  Confidential — Draft for Review", 18, "808080"),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: C.midBlue } },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            normal(`${fzgNr} L2 Health Check Report  |  ${author}, ${organisation}  |  Page `, 16, "808080"),
            new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" }),
            normal(" of ", 16, "808080"),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: "808080" }),
          ],
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 6, color: C.midBlue } },
        })],
      }),
    },
    children: [

      // ── Title page ────────────────────────────────────────────────────────
      spacer(4),
      new Paragraph({
        children: [new TextRun({ text: "Onboard Network", bold: true, size: 56, color: C.darkBlue })],
        alignment: AlignmentType.CENTER,
      }),
      new Paragraph({
        children: [new TextRun({ text: "L2 Health Check Report", bold: true, size: 52, color: C.midBlue })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Trainset ${fzgNr}  ·  ${consistSize}  ·  DOSTO NEU (Nahverkehr)`, size: 28, color: C.headerGrey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Prepared for: ${customer}`, size: 24, color: C.headerGrey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Date: ${checkDate}  ·  Author: ${author}, ${organisation}`, size: 20, color: "808080" })],
        alignment: AlignmentType.CENTER,
      }),
      spacer(2),

      // Verdict banner — HEALTHY with one open item
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [new TableRow({ children: [new TableCell({
          children: [
            new Paragraph({ children: [new TextRun({ text: "✓  L2 FABRIC HEALTHY — 1 OPEN ITEM FOR STADLER", bold: true, size: 28, color: C.white })], alignment: AlignmentType.CENTER }),
            new Paragraph({ children: [new TextRun({ text: "All inter-coach trunks, RSTP, Stadler-facing trunks and firewall path are healthy. One Wi-Fi AP port is down at B3 — requires physical inspection.", size: 20, color: C.white })], alignment: AlignmentType.CENTER }),
          ],
          shading: { type: ShadingType.CLEAR, fill: "375623" },
          margins: { top: 160, bottom: 160, left: 200, right: 200 },
        })]})],
      }),

      pageBreak(),

      // ── 1. Document Control ───────────────────────────────────────────────
      h1("1.  Document Control"),
      h2("1.1  Revision History"),
      simpleTable(
        ["Version", "Date", "Author", "Description"],
        [["1.0", checkDate, `${author}, ${organisation}`, "Initial issue — L2 health check results for Stadler review"]],
        [1200, 1500, 2500, 4000]
      ),
      spacer(),
      h2("1.2  Document Information"),
      simpleTable(
        ["Field", "Value"],
        [
          ["Document title",    `${fzgNr} Onboard Network L2 Health Check Report`],
          ["Customer",          customer],
          ["Trainset",          fzgNr],
          ["Fzg. ID",           "137"],
          ["Consist type",      `DOSTO NEU Nahverkehr ${consistSize}`],
          ["CCU hostname",      "box1-t28"],
          ["CCU IP",            "10.179.28.1"],
          ["Check date",        checkDate],
          ["Author",            `${author}, ${organisation}`],
          ["Status",            "Draft for review"],
        ],
        [3000, 6200]
      ),

      pageBreak(),

      // ── 2. Executive Summary ──────────────────────────────────────────────
      h1("2.  Executive Summary"),
      para([
        normal(`On ${checkDate}, Nomad Digital performed a Layer-2 network health check on trainset `),
        bold(fzgNr),
        normal(` (Fzg. ID 137, 6-car DOSTO NEU Nahverkehr). The check covered switch discovery, RSTP topology, per-port error counters, Stadler-facing trunks, ZFR ports, and CCU-to-Stadler-firewall reachability.`),
      ], { spacing: { after: 120 } }),
      para([
        normal("The onboard L2 fabric is "),
        bold("healthy", 20, C.green),
        normal(". All 18 VDS Consist Switches are reachable. All inter-coach trunks are UP at 10 Gbps full-duplex with zero error counters. RSTP has converged on a single root. All Stadler-facing trunks are UP and clean. The CCU-to-Stadler-firewall path is confirmed reachable. "),
      ], { spacing: { after: 120 } }),
      para([
        normal("One item requires Stadler's attention: the "),
        bold("Wi-Fi Access Point trunk on switch B3 (e0-4) is admin-enabled but has no link"),
        normal(". The PoE subsystem confirms the port is powered but drawing 0 W, and the port has never seen any traffic. The AP at car-B3 position appears to not be physically connected to the switch."),
      ], { spacing: { after: 120 } }),

      h2("Headline Results"),
      simpleTable(
        ["Check", "Result", "Detail"],
        [
          ["Switches reachable",           passCell(), "18 / 18 VDS switches, 22 Westermo radios"],
          ["Inter-coach trunks (e0-0/e0-1)","" , ""],
          ["  Speed",                      passCell(), "All 32 active trunk ports at 10 Gbps full-duplex"],
          ["  Error counters",             passCell(), "RX errors / CRC / carrier-false = 0 on all 32 ports"],
          ["RSTP",                         passCell(), "Single root a0:59:3a:d0:65:20 (D1) agreed by all 18 switches"],
          ["A3 e1-4 — Stadler firewall trunk", passCell(), "UP 1G full-duplex, 0 errors"],
          ["D1/D3 e0-2 — OBS trunks",     passCell(), "UP 10G full-duplex, 0 errors"],
          ["D1/D3 e0-3 — RDC trunks",     passCell(), "UP 10G full-duplex, 0 errors"],
          ["B1/B3 e1-11 — ZFR ports",     passCell(), "UP 1G full-duplex, 0 errors. B3 RX=0 (standby — normal)"],
          ["CCU ↔ Stadler firewall",       passCell(), "TCP port 80 + 22 OPEN on 172.19.196.129, ARP REACHABLE, vlan7 0 errors"],
          ["Inter-coach utilisation",      passCell(), "Peak ~49 Mbps = 0.49% of 10G capacity"],
          ["B3 e0-4 — Wi-Fi AP trunk",     warnCell(), "Admin-enabled, link DOWN. PoE on, 0 W drawn. AP not connected."],
        ],
        [3200, 1400, 4600]
      ),

      pageBreak(),

      // ── 3. Scope & Methodology ────────────────────────────────────────────
      h1("3.  Scope and Methodology"),
      para([normal(
        "The check was performed remotely via SSH to the Nomad CCU (box1-t28). " +
        "All switch commands were issued from the CCU using the standard VDS Consist Switch CLI over SSH with legacy key-exchange algorithms. " +
        "No configuration changes were made to any device."
      )], { spacing: { after: 120 } }),

      h2("Phases Executed"),
      simpleTable(
        ["Phase", "Description"],
        [
          ["1 — Discovery",             "fping sweep of vlan100 (10.179.28.128/25). ARP table inspected for VDS switches (OUI a0:59:3a) and Westermo radios (OUI 00:14:5a)."],
          ["2 — Switch fingerprinting", "show interface trunks and show vlans run on all switches to identify A3 (firewall), D1/D3 (OBS+RDC), B1/B3 (ZFR) by config fingerprint."],
          ["3 — Interface summary",     "show interface summary run on all 18 switches. Link states and speeds recorded."],
          ["4 — RSTP check",            "show spanning-tree run on all 18 switches. Root bridge MAC and agreement verified."],
          ["5 — Error counter scan",    "show interface <port> details run on all e0-0 / e0-1 inter-coach trunk ports across all 18 switches."],
          ["6 — Critical trunk detail", "show interface <port> details run on A3 e1-4, D1/D3 e0-2, D1/D3 e0-3, B1/B3 e1-11, B3 e0-4."],
          ["7 — Throughput sample",     "Two byte-counter snapshots 138 s apart on all inter-coach trunk ports. Per-port Mbps derived."],
          ["8 — End-to-end FW probe",   "ARP, vlan7 counters, and TCP probes (port 80 + 22) to Stadler firewall peer on 172.19.196.129."],
          ["9 — AP investigation",      "show interface e0-4 details and show poe interface e0-4 on B3. show log inspected for link history."],
        ],
        [2800, 6400]
      ),

      pageBreak(),

      // ── 4. Detailed Findings ──────────────────────────────────────────────
      h1("4.  Detailed Findings"),

      h2("4.1  Switch Inventory"),
      para([normal("All 18 VDS Consist Switches and 22 Westermo radios were discovered on vlan100 (10.179.28.128/25). Switch count is consistent with a 6-car DOSTO NEU.")], { spacing: { after: 80 } }),
      simpleTable(
        ["IP Address", "Role (fingerprint)", "e0-0", "e0-1", "Reachable"],
        [
          ["10.179.28.178", "B1",         "10G UP", "10G UP", passCell()],
          ["10.179.28.179", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.180", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.181", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.182", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.183", "A3",         "10G UP", "10G UP", passCell()],
          ["10.179.28.185", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.186", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.187", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.188", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.189", "B3",         "10G UP", "10G UP", passCell()],
          ["10.179.28.190", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.191", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.192", "D1 (root)",  "10G UP", "10G UP", passCell()],
          ["10.179.28.193", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.194", "—",          "10G UP", "10G UP", passCell()],
          ["10.179.28.195", "D3",         "10G UP", "10G UP", passCell()],
          ["10.179.28.196", "—",          "10G UP", "10G UP", passCell()],
        ],
        [1800, 1400, 1400, 1400, 1200]
      ),

      spacer(),
      h2("4.2  RSTP"),
      para([
        normal("RSTP is running on all 18 switches. A single bridge root was elected and agreed upon by all switches. No topology change notifications or root flapping were detected."),
      ], { spacing: { after: 80 } }),
      simpleTable(
        ["Parameter", "Value"],
        [
          ["Root bridge MAC",    "a0:59:3a:d0:65:20"],
          ["Root bridge IP",     "10.179.28.192 (D1)"],
          ["Root bridge priority", "0 (explicitly lowest)"],
          ["Agreement across fleet", "18 / 18 switches"],
          ["Verdict",            "PASS — single stable root"],
        ],
        [3500, 5700]
      ),

      spacer(),
      h2("4.3  Inter-Coach Trunk Error Counters"),
      para([normal(
        "show interface <port> details was run on e0-0 and e0-1 across all 18 switches (36 port checks total). " +
        "All ports showed zero on every error counter. The table below shows a representative sample of the active inter-coach trunks."
      )], { spacing: { after: 80 } }),
      simpleTable(
        ["Switch", "Port", "Speed", "RX Errors", "CRC", "Carrier-false", "Result"],
        [
          ["10.179.28.179 (—)",  "e0-0", "10G", "0", "0", "0", passCell()],
          ["10.179.28.179 (—)",  "e0-1", "10G", "0", "0", "0", passCell()],
          ["10.179.28.183 (A3)", "e0-0", "10G", "0", "0", "0", passCell()],
          ["10.179.28.183 (A3)", "e0-1", "10G", "0", "0", "0", passCell()],
          ["10.179.28.192 (D1)", "e0-0", "10G", "0", "0", "0", passCell()],
          ["10.179.28.192 (D1)", "e0-1", "10G", "0", "0", "0", passCell()],
          ["10.179.28.195 (D3)", "e0-0", "10G", "0", "0", "0", passCell()],
          ["10.179.28.195 (D3)", "e0-1", "10G", "0", "0", "0", passCell()],
          ["All other 14 switches", "e0-0 / e0-1", "10G", "0", "0", "0", passCell()],
        ],
        [2000, 800, 800, 1000, 800, 1200, 1000]
      ),

      spacer(),
      h2("4.4  Stadler-Facing Trunks and ZFR"),
      simpleTable(
        ["Port", "Role", "Switch IP", "Speed", "RX Err", "CRC", "Carrier-false", "Notes", "Result"],
        [
          ["e1-4",  "A3 Firewall trunk",  "10.179.28.183", "1G",  "0", "0", "0", "TX >> RX: normal (routed traffic)", passCell()],
          ["e0-2",  "D1 OBS trunk",       "10.179.28.192", "10G", "0", "0", "0", "",                                  passCell()],
          ["e0-3",  "D1 RDC trunk",       "10.179.28.192", "10G", "0", "0", "0", "Low RX bytes — RDC idle/off",       passCell()],
          ["e0-2",  "D3 OBS trunk",       "10.179.28.195", "10G", "0", "0", "0", "",                                  passCell()],
          ["e0-3",  "D3 RDC trunk",       "10.179.28.195", "10G", "0", "0", "0", "Low RX bytes — RDC idle/off",       passCell()],
          ["e1-11", "B1 ZFR R (active)",  "10.179.28.178", "1G",  "0", "0", "0", "RX active — B1 is primary ZFR",    passCell()],
          ["e1-11", "B3 ZFR (standby)",   "10.179.28.189", "1G",  "0", "0", "0", "RX = 0 — standby, expected",       passCell()],
        ],
        [700, 1700, 1600, 600, 700, 600, 1200, 1700, 800]
      ),

      spacer(),
      h2("4.5  Throughput — Inter-Coach Trunks"),
      para([normal(
        "Two byte-counter snapshots were taken 138 seconds apart on all active inter-coach trunk ports. " +
        "The train was idle (no passengers). Peak utilisation across all 32 active trunk ports was approximately 49 Mbps, which is 0.49% of the 10 Gbps link capacity. No saturation risk."
      )], { spacing: { after: 80 } }),
      simpleTable(
        ["Metric", "Value"],
        [
          ["Sample interval",       "138 seconds"],
          ["Active trunk ports sampled", "32 (16 switches × 2 ports; B1/B3 end-of-consist not included)"],
          ["Peak rate (single port)", "~49 Mbps (10.179.28.193 e0-1)"],
          ["Average active trunk rate", "~25 Mbps"],
          ["Peak utilisation",       "0.49% of 10 Gbps"],
          ["Baseline vs. Fzg. 146",  "Consistent — Fzg. 146 idle baseline was ~140 Mbps per active trunk"],
          ["Verdict",                "PASS — well within capacity"],
        ],
        [3500, 5700]
      ),

      spacer(),
      h2("4.6  CCU ↔ Stadler Firewall Reachability"),
      para([normal(
        "The Stadler firewall peer on this trainset is 172.19.196.129 (not .1 as in the standard template). " +
        "This is consistent with the per-train IP allocation for Fzg. 109."
      )], { spacing: { after: 80 } }),
      simpleTable(
        ["Probe", "Result", "Detail"],
        [
          ["ARP on vlan7",         passCell(), "172.19.196.129 — REACHABLE, MAC 00:90:e8:c5:3d:ba (Westermo)"],
          ["vlan7 RX errors",      passCell(), "0"],
          ["vlan7 TX errors",      passCell(), "0"],
          ["TCP port 80",          passCell(), "OPEN"],
          ["TCP port 22",          passCell(), "OPEN"],
          ["ICMP to 172.19.196.1", naCell(),   "No route — .1 is not the deployed peer IP on this train. Not a fault."],
        ],
        [2200, 1400, 5600]
      ),

      pageBreak(),

      // ── 5. Open Item for Stadler ──────────────────────────────────────────
      h1("5.  Open Item for Stadler"),
      para([normal(
        "The following item was identified during the health check and requires a physical inspection by Stadler. " +
        "It does not affect the L2 fabric health — all switching, routing and connectivity between onboard systems is functional."
      )], { spacing: { after: 120 } }),

      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [
          new TableRow({ children: [
            cell("Field",   { bg: C.tableHead, bold: true, color: C.white, width: 2200 }),
            cell("Detail",  { bg: C.tableHead, bold: true, color: C.white, width: 7000 }),
          ], tableHeader: true }),
          new TableRow({ children: [
            cell("Priority",          { bg: C.yellowBg }),
            cell("Medium — no service impact, but Wi-Fi coverage in car B is absent until resolved", { bg: C.yellowBg }),
          ]}),
          new TableRow({ children: [
            cell("Switch",            { bg: C.white }),
            cell("B3 — 10.179.28.189", { bg: C.white }),
          ]}),
          new TableRow({ children: [
            cell("Port",              { bg: C.tableAlt }),
            cell("e0-4  (Wi-Fi Access Point trunk, VLAN 100/10/20/30/31/131/150)", { bg: C.tableAlt }),
          ]}),
          new TableRow({ children: [
            cell("Observed state",    { bg: C.white }),
            cell("Admin-enabled, line protocol DOWN. PoE mode = on, PoE status = off, power drawn = 0.0 W.", { bg: C.white }),
          ]}),
          new TableRow({ children: [
            cell("Traffic history",   { bg: C.tableAlt }),
            cell("RX bytes = 0, TX bytes = 0. The port has never seen any traffic. No link-up events in the switch log.", { bg: C.tableAlt }),
          ]}),
          new TableRow({ children: [
            cell("PoE budget",        { bg: C.white }),
            cell("22 W total drawn out of 202 W available — PoE budget is not a constraint.", { bg: C.white }),
          ]}),
          new TableRow({ children: [
            cell("Assessment",        { bg: C.yellowBg }),
            cell("The Wi-Fi AP at car-B3 position is either not physically installed, or the patch cable between the AP and switch B3 port e0-4 has not been connected. The switch is ready to power and serve the AP — the missing element is the physical connection.", { bg: C.yellowBg }),
          ]}),
          new TableRow({ children: [
            cell("Required action",   { bg: C.lightBlue }),
            cell("Please confirm whether the AP at car-B3 is physically installed. If installed, check that the patch cable is run from the AP to switch B3 port e0-4. If the AP is not yet installed, please advise the expected installation date.", { bg: C.lightBlue }),
          ]}),
          new TableRow({ children: [
            cell("How to verify fix",  { bg: C.white }),
            cell("After patching: SSH to 10.179.28.189, run 'show poe interface e0-4'. Status should change to 'on' with a class 4 power draw (~15–18 W). Run 'show interface e0-4' — line protocol should be 'up' at 1000 Mbps.", { bg: C.white }),
          ]}),
        ],
      }),

      spacer(),
      // Compare with other B-car AP
      para([
        bold("Reference — B1 e0-4 (same port, working AP): ", 20, C.darkBlue),
        normal("Switch B1 (10.179.28.178) shows e0-4 UP at 1G — confirming the port config and PoE provisioning are correct on this switch type. The B3 port config is identical; the only difference is the missing physical cable/device."),
      ], { spacing: { after: 120 } }),

      pageBreak(),

      // ── 6. Summary ────────────────────────────────────────────────────────
      h1("6.  Summary"),
      simpleTable(
        ["Check", "Verdict", "Notes"],
        [
          ["Switch discovery (18/18)",      passCell(), "All VDS switches reachable"],
          ["Inter-coach trunk speeds",       passCell(), "All 32 active trunks at 10G full-duplex"],
          ["Inter-coach trunk error counters",passCell(),"Zero errors across all 36 port checks"],
          ["RSTP convergence",              passCell(), "Single stable root (D1, priority 0)"],
          ["A3 Firewall trunk",             passCell(), "1G UP, 0 errors"],
          ["D1/D3 OBS trunks",              passCell(), "10G UP, 0 errors"],
          ["D1/D3 RDC trunks",              passCell(), "10G UP, 0 errors (RDC idle — expected)"],
          ["B1/B3 ZFR ports",               passCell(), "1G UP, 0 errors; B3 standby (RX=0) — expected"],
          ["Inter-coach utilisation",       passCell(), "Peak 0.49% of 10G — no capacity concern"],
          ["CCU ↔ Stadler firewall",        passCell(), "TCP 80+22 OPEN, ARP REACHABLE, vlan7 clean"],
          ["B3 e0-4 — Wi-Fi AP",            warnCell(), "Port admin-enabled, no link, PoE 0W. AP not connected — see Section 5"],
        ],
        [3200, 1400, 4600]
      ),

      spacer(2),
      para([
        bold("Overall verdict: ", 20, C.darkBlue),
        bold("HEALTHY", 20, "375623"),
        normal(" — the onboard L2 fabric is operating correctly. The single open item (B3 AP not connected) does not affect L2 switching, Stadler-side device connectivity, or passenger information systems.", 20),
      ], { spacing: { after: 120 } }),

      pageBreak(),

      // ── 7. Reviewer Notes ─────────────────────────────────────────────────
      h1("7.  Reviewer Notes"),
      para([italic(
        "For reviewers who prefer structured written feedback. Add rows as needed. Return to the author before sign-off."
      )], { spacing: { after: 120 } }),
      simpleTable(
        ["#", "Reviewer", "Section", "Comment", "Resolution"],
        [
          ["1", "", "", "", ""],
          ["2", "", "", "", ""],
          ["3", "", "", "", ""],
        ],
        [400, 1400, 1000, 3600, 2800]
      ),

      spacer(2),
      new Paragraph({
        children: [italic(`End of document  ·  ${fzgNr} L2 Health Check Report  ·  ${checkDate}  ·  ${author}, ${organisation}`, 18, "808080")],
        alignment: AlignmentType.CENTER,
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputPath, buf);
  console.log("Report written to:", outputPath);
});
