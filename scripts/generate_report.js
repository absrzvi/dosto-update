#!/usr/bin/env node
"use strict";

const {
  Document, Packer, Paragraph, Table, TableRow, TableCell,
  TextRun, HeadingLevel, AlignmentType, WidthType, BorderStyle,
  ShadingType, Header, Footer, PageNumber, NumberFormat,
  TableLayoutType, VerticalAlign, PageOrientation,
} = require("docx");
const fs   = require("fs");
const path = require("path");

// ── CLI args ──────────────────────────────────────────────────────────────────
const args = {};
process.argv.slice(2).forEach((a, i, arr) => {
  if (a.startsWith("--")) args[a.slice(2)] = arr[i + 1];
});

const findingsPath  = args["findings"]      || process.argv[2];
const customer      = args["customer"]      || "Stadler Rail";
const fzgNr         = args["fzg-nr"]        || "4736-108";
const fzgId         = args["fzg-id"]        || "108";
const consistSize   = args["consist-size"]  || "6-car";
const author        = args["author"]        || "Abbas Rizvi";
const organisation  = args["organisation"]  || "Nomad Digital";
const outputPath    = args["output"]        ||
  path.join(path.dirname(findingsPath),
    `Stadler_Fzg${fzgId}_Cabling_Fault_Report_v1.0.docx`);

if (!findingsPath || !fs.existsSync(findingsPath)) {
  console.error("Usage: node generate_report.js --findings <path> [options]");
  process.exit(1);
}

const F = JSON.parse(fs.readFileSync(findingsPath, "utf8"));
const dateStr = new Date(F.generated_at).toISOString().slice(0, 10);

// ── Colours ───────────────────────────────────────────────────────────────────
const C = {
  darkBlue:   "1F4E79",
  midBlue:    "2E75B6",
  lightBlue:  "D6E4F0",
  headerGrey: "404040",
  red:        "C00000",
  orange:     "ED7D31",
  green:      "375623",
  greenBg:    "E2EFDA",
  redBg:      "FCE4D6",
  yellowBg:   "FFF2CC",
  white:      "FFFFFF",
  tableHead:  "1F4E79",
  tableAlt:   "EBF3FB",
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
    children: cols.map(c =>
      cell(c, { bg: C.tableHead, bold: true, color: C.white })
    ),
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

// ── Status cell helpers ───────────────────────────────────────────────────────
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

const passCell   = () => statusCell("PASS",        C.green,  C.white);
const failCell   = () => statusCell("FAULT",       C.red,    C.white);
const naCell     = () => statusCell("NOT ASSESSED","808080", C.white);
const warnCell   = () => statusCell("WARNING",     C.orange, C.white);

// ── Build document ────────────────────────────────────────────────────────────
const mismatches = F.lldp_topology.mismatches;

// Group mismatches into 2 faults: C3 swap and D1-E2 missing
const fault1 = mismatches.filter(m => m.switch_id === "C3");
const fault2 = mismatches.filter(m => m.switch_id === "D1" || m.switch_id === "E2");

const doc = new Document({
  numbering: {
    config: [{
      reference: "default-bullets",
      levels: [{ level: 0, format: NumberFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: "Calibri", size: 20 } },
    },
  },
  sections: [{
    properties: {
      page: {
        margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 },
      },
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
            normal(`${fzgNr} Cabling Fault Report  |  ${author}, ${organisation}  |  Page `, 16, "808080"),
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

      // ── Title page ──────────────────────────────────────────────────────────
      spacer(4),
      new Paragraph({
        children: [new TextRun({ text: "Onboard Network", bold: true, size: 56, color: C.darkBlue })],
        alignment: AlignmentType.CENTER,
      }),
      new Paragraph({
        children: [new TextRun({ text: "Cabling Fault Report", bold: true, size: 56, color: C.midBlue })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Trainset ${fzgNr}  ·  ${consistSize}  ·  DOSTO`, size: 28, color: C.headerGrey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Prepared for: ${customer}`, size: 24, color: C.headerGrey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Date: ${dateStr}  ·  Author: ${author}, ${organisation}`, size: 20, color: "808080" })],
        alignment: AlignmentType.CENTER,
      }),
      spacer(2),

      // Verdict banner
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [new TableRow({ children: [
          new TableCell({
            children: [
              new Paragraph({ children: [new TextRun({ text: "⚠  ACTION REQUIRED — CABLING FAULTS FOUND", bold: true, size: 28, color: C.white })], alignment: AlignmentType.CENTER }),
              new Paragraph({ children: [new TextRun({ text: "2 cabling faults identified. Full L2 health check deferred until faults are resolved.", size: 20, color: C.white })], alignment: AlignmentType.CENTER }),
            ],
            shading: { type: ShadingType.CLEAR, fill: C.red },
            margins: { top: 160, bottom: 160, left: 200, right: 200 },
          })
        ]})],
      }),

      pageBreak(),

      // ── Section 1: Document Control ─────────────────────────────────────────
      h1("1.  Document Control"),
      h2("1.1  Revision History"),
      simpleTable(
        ["Version", "Date", "Author", "Description"],
        [["1.0", dateStr, `${author}, ${organisation}`, "Initial issue — cabling fault findings for Stadler action"]],
        [1200, 1500, 2500, 4000]
      ),
      spacer(),
      h2("1.2  Document Information"),
      simpleTable(
        ["Field", "Value"],
        [
          ["Document title",    `${fzgNr} Onboard Network Cabling Fault Report`],
          ["Customer",          customer],
          ["Trainset",          fzgNr],
          ["Consist type",      `DOSTO ${consistSize}`],
          ["CCU hostname",      F.ccu_hostname],
          ["CCU IP",            F.ccu_ip],
          ["Check date",        dateStr],
          ["OBN train_id",      String(F.obn_train_id) + " (= 128 + 8)"],
          ["OBN template family", F.vds_switches.obn_template_family],
          ["Author",            `${author}, ${organisation}`],
          ["Status",            "Draft for review"],
        ],
        [3000, 6200]
      ),

      pageBreak(),

      // ── Section 2: Executive Summary ────────────────────────────────────────
      h1("2.  Executive Summary"),
      para([
        normal(`On ${dateStr}, Nomad Digital performed an LLDP topology verification of the onboard Layer-2 network on trainset `),
        bold(fzgNr),
        normal(`. The check confirmed that all 18 VDS Rail Consist Switches are reachable on the management VLAN (vlan100, 10.179.8.128/25) and that OBN template train_id is correctly set to `),
        bold("136"),
        normal(`.`),
      ], { spacing: { after: 120 } }),
      para([
        normal("The LLDP topology check identified "),
        bold("2 cabling faults", 20, C.red),
        normal(" across "),
        bold("4 trunk port pairs"),
        normal(". These faults will prevent OBN auto-topology from converging and will cause inter-car communication failures on the affected links. A full L2 health check (STP, per-port error counters, throughput, firewall reachability) has been deferred until Stadler resolves these faults."),
      ], { spacing: { after: 120 } }),

      h2("Summary of Faults"),
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [
          new TableRow({ children: [
            cell("Fault", { bg: C.tableHead, bold: true, color: C.white, width: 400 }),
            cell("Switch", { bg: C.tableHead, bold: true, color: C.white, width: 800 }),
            cell("Port(s)", { bg: C.tableHead, bold: true, color: C.white, width: 900 }),
            cell("Description", { bg: C.tableHead, bold: true, color: C.white, width: 3600 }),
            cell("Required Action", { bg: C.tableHead, bold: true, color: C.white, width: 3500 }),
          ], tableHeader: true }),
          new TableRow({ children: [
            cell("1", { bg: C.redBg }),
            cell("C3  (10.179.8.180)", { bg: C.redBg }),
            cell("e0-0 / e0-1", { bg: C.redBg }),
            cell("Inter-coach trunk cables swapped — e0-0 connects to C2 (should be A2), e0-1 connects to A2 (should be C2)", { bg: C.redBg }),
            cell("Swap the two trunk cables on C3 ports e0-0 and e0-1", { bg: C.redBg }),
          ]}),
          new TableRow({ children: [
            cell("2", { bg: C.redBg }),
            cell("D1 (10.179.8.183)  /  E2 (10.179.8.191)", { bg: C.redBg }),
            cell("D1 e0-1  /  E2 e0-1", { bg: C.redBg }),
            cell("No LLDP neighbour on either end of the D1–E2 trunk — cable missing, unplugged, or routed to wrong port", { bg: C.redBg }),
            cell("Locate and reconnect the trunk cable between D1 port e0-1 and E2 port e0-1", { bg: C.redBg }),
          ]}),
        ],
      }),

      pageBreak(),

      // ── Section 3: Scope & Methodology ──────────────────────────────────────
      h1("3.  Scope and Methodology"),
      para([normal(
        "This report covers the LLDP inter-switch trunk topology verification phase of the standard Nomad Digital DOSTO L2 network health check. " +
        "The scope is limited to confirming that each VDS Consist Switch's inter-coach trunk ports (e0-0 and e0-1) are cabled to the correct neighbour switch as defined in the OBN templates. " +
        "Remaining health check phases (STP convergence, per-port error counters, utilisation sampling, Stadler firewall reachability) are out of scope for this report and will be performed after cabling is corrected."
      )], { spacing: { after: 120 } }),
      h2("Method"),
      bullet("SSH to CCU (box1-t8, 10.179.8.1) using the Nomad Digital developer key."),
      bullet("Swept management VLAN (vlan100, 10.179.8.128/25) with fping to enumerate all active devices."),
      bullet("Identified 18 VDS switches (OUI a0:59:3a) and 24 Westermo radios (OUI 00:14:5a) — consistent with a 6-car consist."),
      bullet("Read OBN templates from /etc/obn/template/nv6-*.cfg to derive the expected trunk topology (e0-0 and e0-1 descriptions per switch)."),
      bullet("Ran 'show lldp neighbours' on every switch via pexpect SSH and compared live LLDP peers against expected topology."),
      spacer(),

      h2("Tools Used"),
      simpleTable(
        ["Tool", "Purpose"],
        [
          ["fping",                   "Management VLAN sweep"],
          ["ip neigh",                "ARP table — MAC OUI identification"],
          ["Python 3 / pexpect 4.8",  "Automated SSH to VDS switches"],
          ["show lldp neighbours",    "VDS switch CLI — LLDP peer discovery"],
          ["lldp_topology_check.py",  "Nomad Digital topology comparison script"],
        ],
        [3000, 6200]
      ),

      pageBreak(),

      // ── Section 4: Switch Inventory ─────────────────────────────────────────
      h1("4.  Switch Inventory"),
      para([
        normal(`All ${F.vds_switches.count} VDS Consist Switches expected for a ${consistSize} DOSTO were discovered and responded to SSH. OBN hostname format confirms template family `),
        bold(F.vds_switches.obn_template_family),
        normal(`, train_id `),
        bold(String(F.obn_train_id)),
        normal("."),
      ], { spacing: { after: 120 } }),
      simpleTable(
        ["Schema ID", "IP Address", "OBN Hostname", "Reachable"],
        Object.entries(F.vds_switches.ip_to_switch_id)
          .sort((a, b) => a[1].localeCompare(b[1]))
          .map(([ip, id]) => [
            id,
            ip,
            `nv6-${id}-v7-${F.obn_train_id}`,
            cell([new Paragraph({ children: [new TextRun({ text: "YES", bold: true, size: 18, color: C.white })], alignment: AlignmentType.CENTER, spacing: { before: 40, after: 40 } })],
              { bg: "375623" }),
          ]),
        [900, 1800, 3500, 1500]
      ),

      pageBreak(),

      // ── Section 5: LLDP Topology Findings ───────────────────────────────────
      h1("5.  LLDP Topology Findings"),
      para([
        bold(`${F.lldp_topology.ok_count} / ${F.lldp_topology.total_trunk_ports_checked}`, 20, C.green),
        normal(" trunk port links matched the OBN expected topology. "),
        bold(`${F.lldp_topology.mismatch_count} / ${F.lldp_topology.total_trunk_ports_checked}`, 20, C.red),
        normal(" mismatches were found across 2 physical faults."),
      ], { spacing: { after: 120 } }),

      h2("5.1  Fault 1 — Cables Swapped on C3"),
      para([normal(
        "Switch C3 (10.179.8.180) has its two inter-coach trunk cables transposed. " +
        "The cable on e0-0 leads to C2 but should lead to A2. The cable on e0-1 leads to A2 but should lead to C2. " +
        "This is a simple swap — both physical cables are present but plugged into the wrong ports."
      )], { spacing: { after: 120 } }),
      simpleTable(
        ["Switch", "Port", "Live Neighbour", "Expected Neighbour", "Status"],
        [
          ["C3  (10.179.8.180)", "e0-0",
            cell("C2", { bg: C.redBg }),
            cell("A2", { bg: C.greenBg }),
            failCell()],
          ["C3  (10.179.8.180)", "e0-1",
            cell("A2", { bg: C.redBg }),
            cell("C2", { bg: C.greenBg }),
            failCell()],
        ],
        [2000, 1000, 1800, 1800, 1400]
      ),
      spacer(),
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [new TableRow({ children: [new TableCell({
          children: [
            para([bold("Required Action (Fault 1): ", 20, C.darkBlue), normal("Swap the two trunk cables on C3 ports e0-0 and e0-1.")]),
            para([italic("After the swap, re-run 'show lldp neighbours' on C3 to confirm e0-0 shows A2 and e0-1 shows C2.")]),
          ],
          shading: { type: ShadingType.CLEAR, fill: C.lightBlue },
          margins: { top: 120, bottom: 120, left: 160, right: 160 },
        })]})],
      }),
      spacer(),

      h2("5.2  Fault 2 — Missing / Misrouted Trunk Cable: D1 ↔ E2"),
      para([normal(
        "The inter-coach trunk link between D1 (10.179.8.183) port e0-1 and E2 (10.179.8.191) port e0-1 has no LLDP neighbour on either end. " +
        "Both switches are reachable and responding normally on all other ports. " +
        "The trunk cable between the D-car and E-car is either unplugged, missing entirely, or routed to the wrong ports."
      )], { spacing: { after: 120 } }),
      simpleTable(
        ["Switch", "Port", "Live Neighbour", "Expected Neighbour", "Status"],
        [
          ["D1  (10.179.8.183)", "e0-1",
            cell("NO NEIGHBOUR", { bg: C.redBg }),
            cell("E2", { bg: C.greenBg }),
            failCell()],
          ["E2  (10.179.8.191)", "e0-1",
            cell("NO NEIGHBOUR", { bg: C.redBg }),
            cell("D1", { bg: C.greenBg }),
            failCell()],
        ],
        [2000, 1000, 1800, 1800, 1400]
      ),
      spacer(),
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [new TableRow({ children: [new TableCell({
          children: [
            para([bold("Required Action (Fault 2): ", 20, C.darkBlue), normal("Locate the inter-coach trunk cable between the D-car and E-car. Connect it to D1 port e0-1 and E2 port e0-1.")]),
            para([italic("After reconnecting, re-run 'show lldp neighbours' on D1 and E2 to confirm each shows the other as neighbour on e0-1.")]),
            para([italic("Note: if no cable is found, a replacement cable will be needed. Nomad Digital can confirm the expected cable spec on request.")]),
          ],
          shading: { type: ShadingType.CLEAR, fill: C.lightBlue },
          margins: { top: 120, bottom: 120, left: 160, right: 160 },
        })]})],
      }),
      spacer(),

      h2("5.3  Correct Links (for reference)"),
      para([normal("The following 32 trunk port links are correctly cabled and matched the OBN expected topology:")], { spacing: { after: 80 } }),
      simpleTable(
        ["Switch", "Port", "Neighbour", "Status"],
        F.lldp_topology.ok_links.map(l => [
          l.switch, l.port, l.neighbour, passCell()
        ]),
        [2000, 1200, 2500, 1400]
      ),

      pageBreak(),

      // ── Section 6: Overall Check Status ─────────────────────────────────────
      h1("6.  Overall Check Status"),
      para([normal(
        "The table below summarises which health check phases were performed. " +
        "All deferred phases will be run by Nomad Digital after Stadler confirms the cabling faults have been resolved."
      )], { spacing: { after: 120 } }),
      simpleTable(
        ["Check Phase", "Status", "Notes"],
        [
          ["Switch discovery (18/18 reachable)", passCell(),   "All 18 VDS switches found and responding"],
          ["OBN train_id verification",          passCell(),   `train_id = ${F.obn_train_id} (128 + 8) — correct`],
          ["LLDP topology verification",         failCell(),   "2 faults found — see Section 5"],
          ["RSTP convergence check",             naCell(),     "Deferred until cabling resolved"],
          ["Per-port error counter scan",        naCell(),     "Deferred until cabling resolved"],
          ["Stadler firewall reachability",      naCell(),     "Deferred until cabling resolved"],
          ["Inter-coach throughput sampling",    naCell(),     "Deferred until cabling resolved"],
        ],
        [3500, 1500, 4200]
      ),

      pageBreak(),

      // ── Section 7: Recommended Actions ──────────────────────────────────────
      h1("7.  Recommended Actions for Stadler"),
      new Table({
        width: { size: 9200, type: WidthType.DXA },
        rows: [
          new TableRow({ children: [
            cell("Priority", { bg: C.tableHead, bold: true, color: C.white, width: 1200 }),
            cell("Action", { bg: C.tableHead, bold: true, color: C.white, width: 5000 }),
            cell("How to verify", { bg: C.tableHead, bold: true, color: C.white, width: 3000 }),
          ], tableHeader: true }),
          new TableRow({ children: [
            cell("1 — HIGH", { bg: C.redBg }),
            cell("Swap the two inter-coach trunk cables on switch C3 (10.179.8.180): e0-0 should connect to switch A2, e0-1 should connect to switch C2.", { bg: C.redBg }),
            cell("After swap: SSH to C3, run 'show lldp neighbours'. e0-0 must show nv6-A2-*, e0-1 must show nv6-C2-*.", { bg: C.redBg }),
          ]}),
          new TableRow({ children: [
            cell("2 — HIGH", { bg: C.redBg }),
            cell("Locate the missing/unplugged trunk cable between switch D1 (10.179.8.183) port e0-1 and switch E2 (10.179.8.191) port e0-1. Reconnect or replace as needed.", { bg: C.redBg }),
            cell("After reconnect: SSH to D1 and E2, run 'show lldp neighbours'. D1 e0-1 must show nv6-E2-*, E2 e0-1 must show nv6-D1-*.", { bg: C.redBg }),
          ]}),
          new TableRow({ children: [
            cell("3 — FOLLOW-UP", { bg: C.yellowBg }),
            cell("Notify Nomad Digital when both faults are resolved so the full L2 health check can be completed.", { bg: C.yellowBg }),
            cell("Nomad Digital will re-run the full check and issue an updated report.", { bg: C.yellowBg }),
          ]}),
        ],
      }),

      pageBreak(),

      // ── Section 8: Reviewer Notes ────────────────────────────────────────────
      h1("8.  Reviewer Notes"),
      para([italic(
        "This table is provided for reviewers who prefer structured written feedback over Word Track Changes. " +
        "Add rows as needed. Return to the author before sign-off."
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
        children: [italic(`End of document  ·  ${fzgNr} Cabling Fault Report  ·  ${dateStr}  ·  ${author}, ${organisation}`, 18, "808080")],
        alignment: AlignmentType.CENTER,
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputPath, buf);
  console.log("Report written to:", outputPath);
});
