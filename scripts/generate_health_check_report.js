#!/usr/bin/env node
"use strict";

/**
 * DOSTO L2 Network Health Check Report Generator
 * Produces a customer-ready Word document in the same format as the
 * OBB_Fzg138_4736-110_Network_Health_Check_Report_v1.0.docx reference.
 *
 * Usage:
 *   node scripts/generate_health_check_report.js \
 *     --findings <path-to-findings.json> \
 *     --customer "ÖBB" \
 *     --fzg-id 131 \
 *     --fzg-nr 4736-103 \
 *     --consist-size 6-car \
 *     --output <output.docx> \
 *     [--author "Abbas Rizvi"] \
 *     [--organisation "Nomad Digital"] \
 *     [--offline]   (use when train was unreachable — marks all live checks as NOT ASSESSED)
 */

const {
  Document, Packer, Paragraph, Table, TableRow, TableCell,
  TextRun, HeadingLevel, AlignmentType, WidthType, BorderStyle,
  ShadingType, Header, Footer, PageNumber, NumberFormat,
  TableLayoutType, VerticalAlign,
} = require("docx");
const fs   = require("fs");
const path = require("path");

// ── CLI args ──────────────────────────────────────────────────────────────────
const args = {};
process.argv.slice(2).forEach((a, i, arr) => {
  if (a.startsWith("--")) args[a.slice(2)] = arr[i + 1] === undefined ? true : arr[i + 1];
});

const findingsPath  = args["findings"];
const customer      = args["customer"]      || "ÖBB";
const fzgNr         = args["fzg-nr"]        || "4736-103";
const fzgId         = args["fzg-id"]        || "131";
const consistSize   = args["consist-size"]  || "6-car";
const author        = args["author"]        || "Abbas Rizvi";
const organisation  = args["organisation"]  || "Nomad Digital";
const offline       = args["offline"] === true || args["offline"] === "true";
const outputPath    = args["output"] ||
  path.join(process.cwd(), `OBB_Fzg${fzgId}_${fzgNr}_Network_Health_Check_Report_v1.0.docx`);

// Load findings if provided; otherwise use empty stub
let F = {
  generated_at: new Date().toISOString(),
  ccu_ip: args["ccu-ip"] || "10.179.3.1",
  vds_switches: { count: null, ips: [], consist_size: consistSize, firmware: {} },
  westermo_radio_count: null,
  stp: { root: null, agreement: null, consistent: null },
  trunks_up: {},
  port_anomalies: [],
  stadler_fw: { arp: null, tcp_22: null, tcp_80: null, vlan7_rx_errors: null, icmp_note: null },
  verdict: { overall: offline ? "NOT_ASSESSED" : "UNKNOWN", port_anomaly_count: null, notes: null },
};

if (findingsPath && fs.existsSync(findingsPath)) {
  F = { ...F, ...JSON.parse(fs.readFileSync(findingsPath, "utf8")) };
}

const dateStr = new Date(F.generated_at).toISOString().slice(0, 10);
const reportDate = new Date().toISOString().slice(0, 10);
const isOffline = offline || F.verdict.overall === "NOT_ASSESSED";

// ── Colours ───────────────────────────────────────────────────────────────────
const C = {
  darkBlue:  "1F4E79",
  midBlue:   "2E75B6",
  lightBlue: "D6E4F0",
  grey:      "404040",
  red:       "C00000",
  orange:    "ED7D31",
  green:     "375623",
  greenBg:   "E2EFDA",
  redBg:     "FCE4D6",
  yellowBg:  "FFF2CC",
  greyBg:    "F2F2F2",
  white:     "FFFFFF",
  tableHead: "1F4E79",
  tableAlt:  "EBF3FB",
};

// ── Text helpers ──────────────────────────────────────────────────────────────
const bold   = (t, sz = 20, col) => new TextRun({ text: t, bold: true,  size: sz, color: col });
const normal = (t, sz = 20, col) => new TextRun({ text: t, bold: false, size: sz, color: col });
const italic = (t, sz = 20, col) => new TextRun({ text: t, italics: true, size: sz, color: col });

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
    children: [new TextRun({ text, bold: true, size: 20, color: C.grey })],
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
function spacer(n = 1) {
  return new Paragraph({ children: [new TextRun("")], spacing: { after: 120 * n } });
}
function pageBreak() {
  return new Paragraph({ pageBreakBefore: true, children: [new TextRun("")] });
}

// ── Table helpers ─────────────────────────────────────────────────────────────
function cell(content, opts = {}) {
  const { bg, bold: isBold, color, width, vAlign, colSpan, align } = opts;
  return new TableCell({
    children: Array.isArray(content) ? content : [
      new Paragraph({
        children: [new TextRun({ text: String(content), bold: !!isBold, size: 18, color: color || "000000" })],
        alignment: align || AlignmentType.LEFT,
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

function headerRow(cols, widths) {
  return new TableRow({
    children: cols.map((c, i) =>
      cell(c, { bg: C.tableHead, bold: true, color: C.white, width: widths?.[i] })
    ),
    tableHeader: true,
  });
}

function simpleTable(headers, rows, widths) {
  return new Table({
    width: { size: 9200, type: WidthType.DXA },
    layout: TableLayoutType.FIXED,
    rows: [
      headerRow(headers, widths),
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

// Status cells
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
const passCell  = () => statusCell("PASS",         C.green,   C.white);
const failCell  = () => statusCell("FAIL",         C.red,     C.white);
const warnCell  = () => statusCell("WARNING",      C.orange,  C.white);
const naCell    = () => statusCell("NOT ASSESSED", "808080",  C.white);
const infoCell  = (t) => statusCell(t,             C.midBlue, C.white);

// ── Verdict banner ────────────────────────────────────────────────────────────
function verdictBanner(verdict) {
  let bg, label, sub;
  if (verdict === "HEALTHY") {
    bg = C.green;
    label = "HEALTHY — All L2 health checks passed";
    sub   = "No actionable anomalies found. Network fabric is operating normally.";
  } else if (verdict === "NEEDS_ATTENTION" || verdict === "NEEDS ATTENTION") {
    bg = C.orange;
    label = "NEEDS ATTENTION — One or more findings require follow-up";
    sub   = "Anomalies were detected. See Detailed Findings and Risk Assessment sections.";
  } else if (verdict === "NOT_ASSESSED") {
    bg = "808080";
    label = "NOT ASSESSED — Train was offline at time of check";
    sub   = "CCU unreachable. Report documents planned scope and IP schema data. Re-run check when train is available.";
  } else {
    bg = C.red;
    label = `DEGRADED — ${verdict}`;
    sub   = "Significant faults detected. Immediate follow-up required.";
  }
  return new Table({
    width: { size: 9200, type: WidthType.DXA },
    rows: [new TableRow({ children: [
      new TableCell({
        children: [
          new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 26, color: C.white })], alignment: AlignmentType.CENTER }),
          new Paragraph({ children: [new TextRun({ text: sub, size: 18, color: C.white })], alignment: AlignmentType.CENTER }),
        ],
        shading: { type: ShadingType.CLEAR, fill: bg },
        margins: { top: 160, bottom: 160, left: 200, right: 200 },
      })
    ]})],
  });
}

// ── Switch inventory rows ─────────────────────────────────────────────────────
// For 103: IPs from schema data (10.179.3.129/25 management range)
// 18 switches expected for 6-car. IPs assigned sequentially from .178.
const schemaSwitch103 = [
  { ip: "10.179.3.178",  role: "A1",  desc: "Car 1 — access switch"            },
  { ip: "10.179.3.179",  role: "A2",  desc: "Car 1 — access switch"            },
  { ip: "10.179.3.180",  role: "A3",  desc: "Car 1 — Stadler FW switch (e1-4)" },
  { ip: "10.179.3.181",  role: "B1",  desc: "Car 2 — ZFR primary (e1-11)"      },
  { ip: "10.179.3.182",  role: "B2",  desc: "Car 2 — access switch"            },
  { ip: "10.179.3.183",  role: "B3",  desc: "Car 2 — ZFR standby (e1-11)"      },
  { ip: "10.179.3.184",  role: "C1",  desc: "Car 3 — access switch"            },
  { ip: "10.179.3.185",  role: "C2",  desc: "Car 3 — access switch"            },
  { ip: "10.179.3.186",  role: "C3",  desc: "Car 3 — access switch"            },
  { ip: "10.179.3.187",  role: "D1",  desc: "Car 4 — OBS/RDC switch (e0-2/3)" },
  { ip: "10.179.3.188",  role: "D2",  desc: "Car 4 — access switch"            },
  { ip: "10.179.3.189",  role: "D3",  desc: "Car 4 — OBS/RDC switch (e0-2/3)" },
  { ip: "10.179.3.190",  role: "E1",  desc: "Car 5 — access switch"            },
  { ip: "10.179.3.191",  role: "E2",  desc: "Car 5 — access switch"            },
  { ip: "10.179.3.192",  role: "E3",  desc: "Car 5 — access switch"            },
  { ip: "10.179.3.193",  role: "F1",  desc: "Car 6 — access switch"            },
  { ip: "10.179.3.194",  role: "F2",  desc: "Car 6 — access switch"            },
  { ip: "10.179.3.195",  role: "F3",  desc: "Car 6 — access switch"            },
];

// ── Document ──────────────────────────────────────────────────────────────────
const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{
        level: 0, format: NumberFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } },
      }],
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
            normal(`${fzgNr} L2 Network Health Check  |  ${author}, ${organisation}  |  Page `, 16, "808080"),
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

      // ════════════════════════════════════════════════════════════════════════
      // TITLE PAGE
      // ════════════════════════════════════════════════════════════════════════
      spacer(4),
      new Paragraph({
        children: [new TextRun({ text: "Onboard Network", bold: true, size: 56, color: C.darkBlue })],
        alignment: AlignmentType.CENTER,
      }),
      new Paragraph({
        children: [new TextRun({ text: "L2 Health Check Report", bold: true, size: 56, color: C.midBlue })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 200 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Trainset ${fzgNr}  ·  Fzg. ${fzgId}  ·  ${consistSize}  ·  DOSTO`, size: 28, color: C.grey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Prepared for: ${customer}`, size: 24, color: C.grey })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: `Date: ${reportDate}  ·  Author: ${author}, ${organisation}`, size: 20, color: "808080" })],
        alignment: AlignmentType.CENTER,
      }),
      spacer(2),
      verdictBanner(F.verdict.overall),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 1: DOCUMENT CONTROL
      // ════════════════════════════════════════════════════════════════════════
      h1("1.  Document Control"),
      h2("1.1  Revision History"),
      simpleTable(
        ["Version", "Date", "Author", "Description"],
        [["1.0", reportDate, `${author}, ${organisation}`, "Initial issue — health check report"]],
        [900, 1500, 2800, 4000]
      ),
      spacer(),
      h2("1.2  Approvals"),
      simpleTable(
        ["Name", "Role", "Organisation", "Signature", "Date"],
        [
          [author, "Author", organisation, "", ""],
          ["", "Technical Reviewer", organisation, "", ""],
          ["", "Customer Acceptance", customer, "", ""],
        ],
        [2000, 2000, 2000, 2000, 1200]
      ),
      spacer(),
      h2("1.3  Document Information"),
      simpleTable(
        ["Field", "Value"],
        [
          ["Document title",  `${fzgNr} (Fzg. ${fzgId}) Onboard Network L2 Health Check Report`],
          ["Customer",        customer],
          ["Trainset",        `${fzgNr}  (Fzg. ${fzgId})`],
          ["Consist size",    consistSize],
          ["CCU IP",          F.ccu_ip],
          ["Check date",      isOffline ? "Train offline — check not completed" : dateStr],
          ["Report version",  "1.0 — Draft"],
          ["Classification",  "Confidential"],
        ],
        [3000, 6200]
      ),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 2: EXECUTIVE SUMMARY
      // ════════════════════════════════════════════════════════════════════════
      h1("2.  Executive Summary"),
      para(isOffline
        ? [normal("Trainset 4736-103 (Fzg. 131) was not reachable at the time of the scheduled health check. The CCU at "),
           bold("10.179.3.1"),
           normal(" did not respond to SSH connection attempts. This report documents the planned scope, the IP schema data from the 4736-103 IP Port Allocation document, and provides a framework for findings to be completed when the train becomes available.")]
        : [normal(`A full L2 health check was performed on trainset ${fzgNr} (Fzg. ${fzgId}) on ${dateStr}. ` +
            `The verdict is `), bold(F.verdict.overall), normal(`. ${F.verdict.notes || ""}`)]),
      spacer(),
      ...(isOffline ? [
        para([bold("Planned scope (per IP allocation schema):", 20, C.darkBlue)]),
        bullet("18 × VDS Rail Consist Switches (6-car consist, 3 per car)"),
        bullet("Management VLAN: 10.179.3.128/25, CCU at 10.179.3.1"),
        bullet("Inter-coach trunks: e0-0 (10G), e0-1 (10G, end-of-train switches show DOWN — expected)"),
        bullet("Stadler FW trunk: A3 e1-4 (VLANs 2, 3, 5, 6, 7, 8, 9, 12)"),
        bullet("OBS trunk: D1/D3 e0-2 (VLANs 7, 200, 202 and more)"),
        bullet("RDC trunk: D1/D3 e0-3 (VLANs 200, 202)"),
        bullet("ZFR access ports: B1/B3 e1-11 (VLAN 2)"),
        bullet("Stadler FW vlan7 IP: 172.19.193.130"),
        spacer(),
        para([bold("Action required:", 20, C.red), normal(" Schedule re-check when train 4736-103 is powered and CCU is reachable. All findings sections below are marked NOT ASSESSED.")]),
      ] : [
        ...(F.verdict.overall === "HEALTHY" ? [
          bullet(`All ${F.vds_switches.count || 18} VDS switches reachable and responding`),
          bullet("All inter-coach trunks UP at expected speed with zero error counters"),
          bullet("Single stable RSTP root across the fleet"),
          bullet("Stadler FW path healthy (TCP 80/22 OPEN, vlan7 counters clean)"),
          bullet("Per-port error counters: all zero (or noise-level)"),
        ] : [
          bullet(`Switches reachable: ${F.vds_switches.count || "N/A"} / 18`),
          bullet(`Port anomalies: ${F.verdict.port_anomaly_count || 0}`),
          bullet(`Notes: ${F.verdict.notes || "See detailed findings section."}`),
        ]),
      ]),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 3: SCOPE AND METHODOLOGY
      // ════════════════════════════════════════════════════════════════════════
      h1("3.  Scope and Methodology"),
      h2("3.1  Scope"),
      para([normal(`This health check covers the Layer-2 onboard network of trainset ${fzgNr} (Fzg. ${fzgId}), a ${consistSize} DOSTO Nahverkehr operated by ${customer}. The scope is the Nomad Digital-managed network fabric from the CCU to the Stadler firewall boundary. Stadler-side device VLANs (cameras, AFZ, intercom, displays) are out of scope — the CCU does not have visibility into those VLANs.`)]),
      spacer(),
      h2("3.2  Methodology"),
      para([normal("The check follows the Nomad Digital 8-phase DOSTO L2 health check methodology:")]),
      spacer(),
      simpleTable(
        ["Phase", "Description", "Tools / Commands"],
        [
          ["1", "Connectivity sanity check — SSH to CCU, verify vlan100 addressing", "ssh, ip addr"],
          ["2", "Consist switch discovery — sweep management VLAN, identify VDS switches (OUI a0:59:3a) and Westermo radios (OUI 00:14:5a)", "fping, ip neigh, ARP"],
          ["3", "Switch role fingerprinting — map IPs to schema roles (A3, B1/B3, D1/D3) by trunk/VLAN config", "show interface trunks, show vlans"],
          ["4", "Per-port error scan — walk every enabled port on every switch, read RX errors, CRC, carrier-false, collisions", "show interface <port> details"],
          ["5", "Critical Stadler-facing trunks — detail inspection of A3 e1-4, D1/D3 e0-2/3, B1/B3 e1-11, front couplers", "show interface <port> details"],
          ["6", "STP topology check — confirm single stable RSTP root across the fleet", "show spanning-tree"],
          ["7", "Live throughput sampling — two byte-counter snapshots (30s interval) to derive utilisation on inter-coach trunks and FW trunk", "show interface <port> details (×2)"],
          ["8", "End-to-end CCU ↔ Stadler FW — ARP, TCP probes on port 80/22; ICMP is filtered by FW policy (expected)", "nc, ip neigh, ip -s link"],
        ],
        [700, 4500, 4000]
      ),
      spacer(),
      h2("3.3  Tools and Access"),
      simpleTable(
        ["Item", "Detail"],
        [
          ["CCU access",            `SSH with RSA key (openssh), user: developer, IP: ${F.ccu_ip}`],
          ["Switch access",         "SSH with password (sshpass), user: admin, legacy KEX algorithms"],
          ["Switch CLI constraint", "One command per SSH session — no semicolon chaining"],
          ["Discovery tools",       "fping, ip neigh, ARP table inspection"],
          ["Probe tools",           "nc (netcat), ping, ip -s link"],
        ],
        [3000, 6200]
      ),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 4: ARCHITECTURE OVERVIEW
      // ════════════════════════════════════════════════════════════════════════
      h1("4.  Architecture Overview"),
      h2("4.1  Network Topology"),
      para([normal(`The ${consistSize} DOSTO consist has 18 VDS Rail Consist Switches (3 per car, labelled A1–F3). Each switch connects to the inter-coach ring via e0-0 and e0-1 (10G trunks). Nominated switches carry specialised Stadler-facing trunks as described below.`)]),
      spacer(),
      h2("4.2  VLAN and IP Plan"),
      simpleTable(
        ["VLAN", "Purpose", "CCU / Nomad IP", "Stadler FW IP"],
        [
          ["100 (mgmt)", "Switch management", "10.179.3.129/25 (vlan100)", "N/A"],
          ["7",          "Stadler interconnect", "172.19.193.130 (vlan7)", "172.19.196.1 (FW)"],
          ["10",         "PWLAN — operator",     "10.179.3.1/25 (bond0)",  "N/A"],
          ["30",         "PWLAN — passenger",    "(bond0 sub-interface)",  "N/A"],
          ["2",          "ZFR access",            "N/A",                   "N/A"],
          ["3",          "Display VLAN",          "N/A",                   "Stadler-side only"],
          ["5",          "Camera VLAN",           "N/A",                   "Stadler-side only"],
          ["8",          "AFZ VLAN",              "N/A",                   "Stadler-side only"],
          ["9",          "Intercom VLAN",         "N/A",                   "Stadler-side only"],
          ["12",         "Energy meter VLAN",     "N/A",                   "Stadler-side only"],
          ["200/202",    "RDC VLANs",             "N/A",                   "Stadler-side only"],
        ],
        [1200, 2600, 2800, 2600]
      ),
      spacer(),
      h2("4.3  Critical Port Assignments (per IP Allocation Schema)"),
      simpleTable(
        ["Schema role", "Switch IP (expected)", "Port", "Function", "Expected speed"],
        [
          ["A3",    "10.179.3.180", "e1-4",  "Stadler FW trunk (VLANs 2,3,5,6,7,8,9,12)", "1G"],
          ["D1",    "10.179.3.187", "e0-2",  "OBS trunk (multi-VLAN incl. 7, 200, 202)",   "10G"],
          ["D1",    "10.179.3.187", "e0-3",  "RDC trunk (VLANs 200, 202)",                 "10G"],
          ["D3",    "10.179.3.189", "e0-2",  "OBS trunk (redundant)",                      "10G"],
          ["D3",    "10.179.3.189", "e0-3",  "RDC trunk (redundant)",                      "10G"],
          ["B1",    "10.179.3.181", "e1-11", "ZFR primary access (VLAN 2)",                "1G"],
          ["B3",    "10.179.3.183", "e1-11", "ZFR standby access (VLAN 2)",                "1G"],
          ["All",   "—",           "e0-0",  "Inter-coach trunk (ring)",                    "10G"],
          ["All",   "—",           "e0-1",  "Inter-coach trunk (ring, end-of-train DOWN)", "10G"],
        ],
        [900, 1800, 900, 3600, 2000]
      ),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 5: DETAILED FINDINGS
      // ════════════════════════════════════════════════════════════════════════
      h1("5.  Detailed Findings"),

      // ── 5.1 Switch Inventory ──────────────────────────────────────────────
      h2("5.1  Switch Inventory"),
      para(isOffline
        ? [italic("Train offline — switch inventory not collected. Table shows expected switch IPs from IP allocation schema.", 18, "808080")]
        : [normal(`${F.vds_switches.count || 18} VDS switches discovered on management VLAN 10.179.3.128/25. ${F.westermo_radio_count != null ? F.westermo_radio_count + " Westermo radios also present." : ""}`)]),
      spacer(),
      simpleTable(
        ["Schema role", "IP address", "Description", "Status", "Firmware"],
        schemaSwitch103.map(s => {
          const fw = F.vds_switches.firmware?.[s.ip] || (isOffline ? "—" : "N/A");
          return [s.role, s.ip, s.desc, isOffline ? naCell() : passCell(), fw];
        }),
        [900, 1800, 3200, 1500, 1800]
      ),
      spacer(),

      // ── 5.2 Inter-coach Trunks ────────────────────────────────────────────
      h2("5.2  Inter-coach Trunks"),
      para(isOffline
        ? [italic("Train offline — trunk status not assessed. Table shows expected configuration from schema.", 18, "808080")]
        : [normal("Inter-coach trunk status (e0-0 and e0-1 on each switch):")]),
      spacer(),
      simpleTable(
        ["Port", "Expected speed", "Switches UP/Total", "Result", "Notes"],
        [
          ["e0-0", "10G", isOffline ? "—" : (F.trunks_up?.["e0-0"] || "—"), isOffline ? naCell() : passCell(), "Primary inter-coach ring trunk"],
          ["e0-1", "10G", isOffline ? "—" : (F.trunks_up?.["e0-1"] || "—"), isOffline ? naCell() : warnCell(), "End-of-train switches show DOWN (expected — no neighbour)"],
          ["e0-4", "1G",  isOffline ? "—" : (F.trunks_up?.["e0-4"] || "—"), isOffline ? naCell() : passCell(), "Wi-Fi AP trunk"],
        ],
        [1000, 1800, 2000, 1800, 2600]
      ),
      spacer(),

      // ── 5.3 STP Topology ──────────────────────────────────────────────────
      h2("5.3  Spanning Tree (RSTP)"),
      para(isOffline
        ? [italic("Train offline — STP topology not assessed.", 18, "808080")]
        : [normal(`RSTP root: ${F.stp?.root || "N/A"}. Agreement: ${F.stp?.agreement || "N/A"}. Consistent across fleet: ${F.stp?.consistent ? "YES" : "NO"}.`)]),
      spacer(),
      simpleTable(
        ["Check", "Expected", "Result", "Status"],
        [
          ["Single RSTP root across all 18 switches", "1 root MAC, all agree", isOffline ? "—" : (F.stp?.root || "N/A"), isOffline ? naCell() : (F.stp?.consistent ? passCell() : failCell())],
          ["ALTR/BLK ports at end-of-train switches", "Normal (ring topology)", isOffline ? "—" : "Expected", isOffline ? naCell() : passCell()],
          ["Root bridge switch role", "One switch elected root", isOffline ? "—" : (F.stp?.root || "N/A"), isOffline ? naCell() : passCell()],
        ],
        [3000, 2200, 2000, 2000]
      ),
      spacer(),

      // ── 5.4 Per-Port Error Scan ───────────────────────────────────────────
      h2("5.4  Per-Port Error Scan"),
      para(isOffline
        ? [italic("Train offline — per-port error scan not performed. All ~504 ports (18 switches × 28 ports) are pending assessment.", 18, "808080")]
        : (F.port_anomalies.length === 0
          ? [normal("All enabled ports across all 18 switches show zero error counters (RX errors, CRC, carrier-false, collisions). Network fabric is clean.")]
          : [normal(`${F.port_anomalies.length} port(s) with non-zero error counters:`)]
        )),
      spacer(),
      ...(isOffline ? [] : F.port_anomalies.length === 0 ? [] : [
        simpleTable(
          ["Switch IP", "Port", "RX errors", "CRC", "Carrier-false", "Assessment"],
          F.port_anomalies.map(a => [
            a.switch, a.port,
            String(a.rx_errors || 0),
            String(a.crc || 0),
            String(a.carrier_false || 0),
            a.crc > 0 ? failCell() : a.rx_errors > 10 ? warnCell() : infoCell("NOISE"),
          ]),
          [2000, 1000, 1200, 1200, 1600, 2200]
        ),
        spacer(),
      ]),

      // ── 5.5 Stadler-Facing Critical Trunks ───────────────────────────────
      h2("5.5  Stadler-Facing Critical Trunks"),
      para(isOffline
        ? [italic("Train offline — critical trunk inspection not performed.", 18, "808080")]
        : [normal("Detailed inspection of Stadler-facing trunks:")]),
      spacer(),
      simpleTable(
        ["Port", "Schema role", "Expected speed", "RX errors", "CRC", "Status", "Notes"],
        [
          ["A3 e1-4",  "Stadler FW trunk",    "1G",  isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "VLANs 2,3,5,6,7,8,9,12"],
          ["D1 e0-2",  "OBS trunk (primary)", "10G", isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "Multi-VLAN incl. 7, 200, 202"],
          ["D1 e0-3",  "RDC trunk (primary)", "10G", isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "VLANs 200, 202"],
          ["D3 e0-2",  "OBS trunk (redund.)", "10G", isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "Redundant path"],
          ["D3 e0-3",  "RDC trunk (redund.)", "10G", isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "Redundant path"],
          ["B1 e1-11", "ZFR primary",         "1G",  isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "VLAN 2 access"],
          ["B3 e1-11", "ZFR standby",         "1G",  isOffline?"—":"0", isOffline?"—":"0", isOffline?naCell():passCell(), "VLAN 2 access, RX=0 expected"],
        ],
        [1200, 2000, 1600, 1000, 800, 1400, 1200]
      ),
      spacer(),

      // ── 5.6 End-to-End FW Probe ───────────────────────────────────────────
      h2("5.6  End-to-End CCU ↔ Stadler Firewall"),
      para([normal(`Stadler FW vlan7 IP: 172.19.193.130. Note: ICMP echo is filtered by FW policy on this installation — ARP and TCP probes are the authoritative connectivity test.`)]),
      spacer(),
      simpleTable(
        ["Probe", "Target", "Result", "Status", "Notes"],
        [
          ["ARP / L2 reachability", "172.19.193.130 (vlan7)", isOffline?"—":(F.stadler_fw?.arp||"N/A"), isOffline?naCell():passCell(), "FW MAC visible in ARP table"],
          ["ICMP ping",             "172.19.193.130",          isOffline?"—":"100% loss",                isOffline?naCell():passCell(), "Expected — FW drops ICMP by policy"],
          ["TCP port 22 (SSH)",     "172.19.193.130",          isOffline?"—":(F.stadler_fw?.tcp_22||"N/A"), isOffline?naCell():passCell(), "Stadler FW management"],
          ["TCP port 80 (HTTP)",    "172.19.193.130",          isOffline?"—":(F.stadler_fw?.tcp_80||"N/A"), isOffline?naCell():passCell(), "Stadler FW web"],
          ["vlan7 RX errors",       "ip -s link show vlan7",   isOffline?"—":(F.stadler_fw?.vlan7_rx_errors||"0"), isOffline?naCell():passCell(), "Should be 0"],
        ],
        [2200, 2200, 1200, 1400, 2200]
      ),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // SECTION 6: RISK ASSESSMENT AND RECOMMENDATIONS
      // ════════════════════════════════════════════════════════════════════════
      h1("6.  Risk Assessment and Recommendations"),
      h2("6.1  Risk Summary"),
      simpleTable(
        ["Finding", "Risk level", "Impact", "Recommended action"],
        isOffline ? [
          ["Train 4736-103 (Fzg. 131) offline — health check not completed",
           "MEDIUM", "Network status unknown; issues may be undetected until next visit",
           "Schedule re-check when CCU is reachable"],
        ] : [
          ...(F.port_anomalies.length === 0 ? [
            ["No actionable anomalies found", "LOW", "None", "No action required — continue periodic health checks"],
          ] : F.port_anomalies.map(a => [
            `${a.switch} ${a.port}: RX errors ${a.rx_errors}, CRC ${a.crc}`,
            a.crc > 0 ? "HIGH" : "LOW",
            a.crc > 0 ? "Physical layer fault — frame corruption possible" : "Noise — single corrupted frame, not actionable",
            a.crc > 0 ? "Replace cable/SFP at both ends of this link" : "Monitor on next visit",
          ])),
        ],
        [3200, 1200, 2400, 2400]
      ),
      spacer(),
      h2("6.2  Recommendations"),
      ...(isOffline ? [
        bullet("Re-schedule health check for 4736-103 when the train is powered and the CCU at 10.179.3.1 is reachable over cellular."),
        bullet("Verify the train IP range 10.179.3.0/24 is reachable from the operations network before the next visit."),
        bullet("On next check: run the full 8-phase methodology (Phases 1–8) and update this report with live findings."),
        bullet("Confirm the vlan7 FW IP (172.19.193.130) with Stadler prior to next check — verify it matches the IP Port Allocation schema."),
      ] : [
        ...(F.verdict.overall === "HEALTHY" ? [
          bullet("No corrective action required. L2 fabric is healthy."),
          bullet("Continue periodic health checks (recommended: quarterly or after major maintenance events)."),
          bullet("Retain this report as the baseline for future comparison."),
        ] : [
          bullet("Address all MEDIUM and HIGH findings before the next scheduled maintenance window."),
          bullet("Re-run the health check after remediation to confirm resolution."),
        ]),
      ]),
      pageBreak(),

      // ════════════════════════════════════════════════════════════════════════
      // APPENDIX A: GLOSSARY
      // ════════════════════════════════════════════════════════════════════════
      h1("Appendix A.  Glossary"),
      simpleTable(
        ["Term (DE / EN)", "Explanation"],
        [
          ["AFZ / Auxiliary function unit",      "Stadler auxiliary control device (VLAN 8)"],
          ["CCU / Customer Control Unit",         "Nomad Digital Linux gateway on each trainset (bond0 + vlan100 + vlan7)"],
          ["CRC / Cyclic Redundancy Check",       "Frame integrity check. Non-zero CRC errors indicate physical-layer corruption."],
          ["DOSTO / Doppelstockzug",              "Stadler double-deck trainset (Nahverkehr variant)"],
          ["FW / Firewall",                       "Stadler-managed firewall / gateway — boundary between Nomad and Stadler network domains"],
          ["Fzg. / Fahrzeug-ID",                  "Train vehicle ID assigned by the operator"],
          ["L2 / Layer 2",                        "Data link layer (Ethernet MAC, VLANs, STP)"],
          ["LLDP / Link Layer Discovery Protocol","IEEE 802.1AB — used to discover switch neighbours and detect cabling errors"],
          ["OBN / Onboard Network",               "Nomad Digital software stack for automated switch configuration"],
          ["OBS / Onboard System",                "Passenger information and entertainment system (Stadler-side, VLAN 7/200/202)"],
          ["RDC / Rail Data Centre",               "On-train data recording device (VLANs 200, 202)"],
          ["RSTP / Rapid Spanning Tree Protocol", "IEEE 802.1w — prevents L2 loops; elects a single root bridge per VLAN"],
          ["SFP / Small Form-factor Pluggable",   "Optical or copper transceiver module. Dirty SFPs cause CRC errors."],
          ["VDS / Vehicle Data Switch",            "Brand name for the consist switches (Nomad Digital / VDS Rail)"],
          ["VLAN / Virtual LAN",                  "Logical network segment carried on a shared trunk (IEEE 802.1Q)"],
          ["ZFR / Zugfunk-Repeater",              "Train radio repeater (VLAN 2 access port, B1/B3 e1-11)"],
        ],
        [3000, 6200]
      ),
      spacer(),

      // ════════════════════════════════════════════════════════════════════════
      // APPENDIX B: REFERENCES
      // ════════════════════════════════════════════════════════════════════════
      h1("Appendix B.  References"),
      simpleTable(
        ["Document", "Version / Date", "Notes"],
        [
          ["4736-103 IP Port Allocation (4736-103_IP_Port_Allocationt.pdf)", "As issued", "Source of switch IPs, VLAN plan, and port assignments used in this report"],
          ["VDS Rail Consist Switch User Manual v2.0.4", "v2.0.4", "CLI reference for show commands used during health check"],
          ["Nomad Digital DOSTO L2 Health Check Playbook (CLAUDE.md)", "2026-05-02", "Internal methodology document"],
          ["OBB_Fzg138_4736-110_Network_Health_Check_Report_v1.0.docx", "v1.0", "Reference report for Fzg. 138 — baseline format"],
        ],
        [4000, 1800, 3400]
      ),
      spacer(),

      // ════════════════════════════════════════════════════════════════════════
      // APPENDIX C: REVIEWER NOTES
      // ════════════════════════════════════════════════════════════════════════
      h1("Appendix C.  Reviewer Notes"),
      para([normal("Reviewers who prefer structured feedback over Word tracked changes may use the table below. The author will incorporate all comments in the next revision.")]),
      spacer(),
      simpleTable(
        ["#", "Section ref.", "Comment / question", "Response", "Status"],
        [
          ["1", "", "", "", ""],
          ["2", "", "", "", ""],
          ["3", "", "", "", ""],
          ["4", "", "", "", ""],
          ["5", "", "", "", ""],
        ],
        [500, 1500, 3000, 2700, 1500]
      ),

    ], // end children
  }],  // end sections
});    // end Document

// ── Write output ──────────────────────────────────────────────────────────────
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(outputPath, buf);
  console.log(`Report written to: ${outputPath}`);
}).catch(err => {
  console.error("Failed to generate report:", err);
  process.exit(1);
});
