// Network Health & Port-Fault report for Fzg 146 / Train 4736-118 (Zabbix host 50_6021)
// Customer-facing: Stadler + ÖBB. Built with docx-js.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, PageBreak, VerticalAlign
} = require("docx");

const NAVY = "1F3864", BLUE = "2E75B6", HDRFILL = "D5E8F0", GREY = "F2F2F2";
const RED = "C00000", AMBER = "BF8F00", GREEN = "375623";
const border = { style: BorderStyle.SINGLE, size: 1, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const CW = 9360; // content width, US Letter, 1" margins

function cell(text, { w, fill, bold, color, align } = {}) {
  const runs = Array.isArray(text) ? text : [text];
  return new TableCell({
    borders,
    width: { size: w, type: WidthType.DXA },
    shading: fill ? { fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 110, right: 110 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: align || AlignmentType.LEFT,
      children: runs.map(t => new TextRun({ text: t, bold: !!bold, color: color || "000000", size: 18 }))
    })]
  });
}
function hcell(text, w) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: { fill: NAVY, type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 110, right: 110 },
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 18 })] })]
  });
}
function P(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 120, before: opts.before ?? 0 },
    alignment: opts.align,
    children: (Array.isArray(text) ? text : [new TextRun({ text, size: 22, ...opts.run })])
  });
}
function bullet(text, run = {}) {
  return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 },
    children: [new TextRun({ text, size: 22, ...run })] });
}
function H1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] }); }
function H2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] }); }

const doc = new Document({
  creator: "Nomad Digital",
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, color: NAVY, font: "Arial" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, color: BLUE, font: "Arial" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
    ]
  },
  numbering: { config: [
    { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 540, hanging: 280 } } } }] },
  ]},
  sections: [{
    properties: { page: {
      size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
    }},
    headers: { default: new Header({ children: [ new Paragraph({
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 4 } },
      tabStops: [{ type: "right", position: CW }],
      children: [
        new TextRun({ text: "Nomad Digital", bold: true, color: NAVY, size: 18 }),
        new TextRun({ text: "\tNetwork Health Check – L2 Fabric & Port Faults", color: "595959", size: 16 }),
      ]
    }) ] }) },
    footers: { default: new Footer({ children: [ new Paragraph({
      border: { top: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 4 } },
      tabStops: [{ type: "right", position: CW }],
      children: [
        new TextRun({ text: "Confidential – prepared for ÖBB and Stadler", color: "595959", size: 16 }),
        new TextRun({ text: "\tPage ", color: "595959", size: 16 }),
        new TextRun({ children: [PageNumber.CURRENT], color: "595959", size: 16 }),
      ]
    }) ] }) },
    children: [
      // ---------- Title block ----------
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Network Health Check & Port-Fault Report", bold: true, color: NAVY, size: 40 })] }),
      new Paragraph({ spacing: { after: 240 }, children: [new TextRun({ text: "DOSTO NEU 6-car trainset – L2 consist fabric and Stadler interconnect", color: "595959", size: 22 })] }),

      new Table({
        width: { size: CW, type: WidthType.DXA }, columnWidths: [2600, 6760],
        rows: [
          ["Vehicle (Fzg. ID)", "146"],
          ["Train number", "4736-118"],
          ["Monitoring host", "50_6021 (project 50)"],
          ["CCU", "box1-t21 (10.179.21.1)"],
          ["Consist", "6-car / 18 VDS Rail Consist Switches (nv6, config v8-146)"],
          ["Assessment date", "19 June 2026"],
          ["Prepared by", "Nomad Digital – Onboard Network Engineering"],
        ].map(([k, v]) => new TableRow({ children: [
          cell(k, { w: 2600, fill: HDRFILL, bold: true }),
          cell(v, { w: 6760 })
        ]}))
      }),

      // ---------- Executive summary ----------
      H1("1.  Executive summary"),
      P("Nomad Digital assessed the Layer-2 network on vehicle Fzg. 146 (train 4736-118) following three port-down alarms raised in the monitoring system. The assessment covered the consist switch fabric, the three alarming ports, and the Stadler firewall interconnect on VLAN 7."),
      P([
        new TextRun({ text: "Overall the L2 fabric and the Stadler interconnect are healthy. ", bold: true, size: 22 }),
        new TextRun({ text: "The vlan7 addressing is correct, the path to the Stadler firewall is up, and the firewall is confirmed commissioned. The three alarming ports are all administratively enabled and correctly configured on the switch side, with zero error counters — i.e. the consist switches are not at fault. The fault, where present, lies at the far-end device or its cabling.", size: 22 })
      ]),
      P("Of the three ports, one is a confirmed device-down fault requiring action; the other two are members of redundant device pairs whose partner is operational, and we ask Stadler/ÖBB to confirm the intended hot-standby behaviour before classifying them."),

      // findings at a glance
      H2("Findings at a glance"),
      new Table({
        width: { size: CW, type: WidthType.DXA }, columnWidths: [2100, 2100, 2860, 2300],
        rows: [
          new TableRow({ tableHeader: true, children: [
            hcell("Switch / Port", 2100), hcell("Connected device", 2100), hcell("Observation", 2860), hcell("Classification", 2300)
          ]}),
          new TableRow({ children: [
            cell("A1  e1-6", { w: 2100, bold: true }), cell("AFZ A2 (VLAN 8)", { w: 2100 }),
            cell("Admin-up, never linked", { w: 2860 }),
            cell("FAULT – action needed", { w: 2300, color: RED, bold: true })
          ]}),
          new TableRow({ children: [
            cell("A3  e1-9", { w: 2100, bold: true }), cell("Sprechstelle A2R (VLAN 9)", { w: 2100 }),
            cell("Admin-up, never linked; primary (A2) UP", { w: 2860 }),
            cell("QUERY – redundant pair", { w: 2300, color: AMBER, bold: true })
          ]}),
          new TableRow({ children: [
            cell("B1  e1-11", { w: 2100, bold: true }), cell("ZFR primary (VLAN 2)", { w: 2100 }),
            cell("Admin-up, never linked; standby (B3) UP", { w: 2860 }),
            cell("QUERY – redundant pair", { w: 2300, color: AMBER, bold: true })
          ]}),
        ]
      }),

      // ---------- Scope / method ----------
      H1("2.  Scope and method"),
      P("The following checks were performed against the live train via the onboard Nomad CCU (box1-t21):"),
      bullet("Monitoring review – active alarms for the trainset were read from the network monitoring system (Zabbix), and per-port operational/administrative status was compared against two healthy reference trains of the same build (hosts 50_6023 / Fzg 138 and 50_6018 / Fzg 143)."),
      bullet("Switch identification – each alarming switch was identified to its schema position (A1 / A3 / B1) by its configuration fingerprint and by its own reported system name (e.g. nv6-A1-v8-146), cross-checked against the IPv4 schema (ND-DEL-OBB-035-IPA-146)."),
      bullet("Per-port inspection – show interface <port> details was captured on each alarming switch for link state, auto-negotiation, traffic counters and error counters; the switch event log and uptime were also reviewed."),
      bullet("Stadler interconnect – the CCU VLAN 7 address was verified against the addressing scheme, and the Stadler firewall was assessed for path health (ARP), commission state (ICMP policy) and service availability (TCP)."),

      // ---------- L2 fabric result ----------
      H1("3.  L2 consist fabric"),
      P("All three alarming switches are healthy and were up with 2 days 4 hours uptime at the time of assessment, on the expected firmware/config (v8-146). The inter-coach 10 G trunks (e0-0 / e0-1) and the management/AP trunk (e0-4) were up on all three. No CRC errors, carrier-loss events, or runt/giant/jabber frames were observed on the inspected ports."),

      // ---------- Port faults ----------
      H1("4.  Port-fault detail"),
      P("Each alarming port is administratively enabled (the switch is actively offering the link) but shows line-protocol down with zero traffic and zero errors in either direction since the switch last booted. This is the signature of a port with no device connected, or a far-end device that is powered off — not a cabling-quality fault (which would show CRC errors, carrier-false events, or runts) and not a switch fault."),

      H2("4.1  A1 e1-6 – AFZ A2  (FAULT)"),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [2600, 6760], rows: [
        ["Switch", "A1 (nv6-A1-v8-146), 10.179.21.204"],
        ["Port / VLAN", "e1-6 / VLAN 8 (apc-net)"],
        ["Schema usage", "AFZ A2 (10 W PoE device)"],
        ["State", "Admin enabled; line protocol DOWN"],
        ["Counters", "RX 0 / TX 0 packets, 0 bytes; 0 CRC, 0 carrier-false, 0 errors"],
        ["Reference trains", "Same port (A1 e1-6) is operationally UP on Fzg 138 and Fzg 143"],
      ].map(([k, v]) => new TableRow({ children: [cell(k, { w: 2600, fill: GREY, bold: true }), cell(v, { w: 6760 })] })) }),
      P([
        new TextRun({ text: "Assessment: ", bold: true, size: 22 }),
        new TextRun({ text: "This is a non-redundant device. It is up and carrying traffic on comparable healthy trains, but is absent here. We classify A1 e1-6 / AFZ A2 as a genuine device-down fault. Recommended action: physical check of the AFZ A2 unit and its cabling on car A (power, connector, device health).", size: 22 })
      ]),

      H2("4.2  A3 e1-9 – Sprechstelle A2R  (QUERY)"),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [2600, 6760], rows: [
        ["Switch", "A3 (nv6-A3-v8-146), 10.179.21.201"],
        ["Port / VLAN", "e1-9 / VLAN 9 (call-point-net)"],
        ["Schema usage", "Sprechstelle A2R – marked “Redundanz A2” (redundant intercom)"],
        ["State", "Admin enabled; line protocol DOWN; 0/0 counters"],
        ["Partner device", "Sprechstelle A2 primary (A2 e1-8) is operationally UP"],
      ].map(([k, v]) => new TableRow({ children: [cell(k, { w: 2600, fill: GREY, bold: true }), cell(v, { w: 6760 })] })) }),
      P([
        new TextRun({ text: "Assessment: ", bold: true, size: 22 }),
        new TextRun({ text: "This is the redundant half of an intercom pair; its primary (A2) is up and the intercom function is therefore being served. By the documented Nomad convention a standby member may legitimately be silent. However, on both reference trains this redundant port is operationally UP, so the down state here is a deviation. ", size: 22 }),
        new TextRun({ text: "Query to Stadler/ÖBB: should both members of the Sprechstelle redundancy be link-up (hot standby), or is a silent standby expected?", italics: true, size: 22 })
      ]),

      H2("4.3  B1 e1-11 – ZFR primary  (QUERY)"),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [2600, 6760], rows: [
        ["Switch", "B1 (nv6-B1-v8-146), 10.179.21.184"],
        ["Port / VLAN", "e1-11 / VLAN 2 (zrp-train-repair)"],
        ["Schema usage", "ZFR primary (B3 e1-11 carries the ZFR standby)"],
        ["State", "Admin enabled; line protocol DOWN; 0/0 counters"],
        ["Partner device", "ZFR standby (B3 e1-11) is operationally UP"],
      ].map(([k, v]) => new TableRow({ children: [cell(k, { w: 2600, fill: GREY, bold: true }), cell(v, { w: 6760 })] })) }),
      P([
        new TextRun({ text: "Assessment: ", bold: true, size: 22 }),
        new TextRun({ text: "The ZFR primary is down while its standby (B3) is up; the ZFR pair shares one address and operates one-active-at-a-time, so the function is being served by the standby. As with the Sprechstelle, the reference trains show this port UP. A separate monitoring alarm (“potential split-brain” on the redundancy controller) is consistent with a primary/standby role split rather than an outage. ", size: 22 }),
        new TextRun({ text: "Query to Stadler/ÖBB: confirm whether the ZFR primary should be link-up alongside the standby, and whether the split-brain indication is expected in this state.", italics: true, size: 22 })
      ]),

      // ---------- Stadler interconnect ----------
      H1("5.  Stadler firewall interconnect (VLAN 7)"),
      P("The CCU VLAN 7 address is 172.19.201.2/17, which is correct for Fzg 146 under the DOSTO NEU addressing scheme (the Stadler firewall peer is 172.19.201.1). The interface is up with clean counters (0 errors, 0 drops)."),
      new Table({
        width: { size: CW, type: WidthType.DXA }, columnWidths: [2200, 3360, 3800],
        rows: [
          new TableRow({ tableHeader: true, children: [ hcell("Test", 2200), hcell("Result", 3360), hcell("Interpretation", 3800) ]}),
          new TableRow({ children: [
            cell("Path (ARP)", { w: 2200, bold: true }),
            cell("172.19.201.1 REACHABLE (MAC 00:90:e8:…, Westermo)", { w: 3360 }),
            cell("Path to firewall is up", { w: 3800, color: GREEN, bold: true })
          ]}),
          new TableRow({ children: [
            cell("Commission (ICMP)", { w: 2200, bold: true }),
            cell("ping = 100% loss (5/5 dropped)", { w: 3360 }),
            cell("Firewall commissioned – dropping ICMP by policy as designed", { w: 3800, color: GREEN, bold: true })
          ]}),
          new TableRow({ children: [
            cell("Services (TCP)", { w: 2200, bold: true }),
            cell("80 open, 22 open, 443 timed out", { w: 3360 }),
            cell("Services reachable; see note below", { w: 3800, color: AMBER, bold: true })
          ]}),
        ]
      }),
      P([
        new TextRun({ text: "Verdict: ", bold: true, size: 22 }),
        new TextRun({ text: "VLAN 7 is correctly addressed, the path to the Stadler firewall is healthy, and the firewall is commissioned. ", size: 22 }),
      ], { before: 100 }),
      P([
        new TextRun({ text: "Note for Stadler: ", bold: true, size: 22 }),
        new TextRun({ text: "on the firewall transit address, TCP 80 and 22 answer while 443 is filtered. This does not affect the health verdict, but we ask Stadler to confirm which services 172.19.201.1 is intended to expose, so the open 80/22 ports are recorded as intended rather than incidental.", size: 22 })
      ]),

      // ---------- Actions ----------
      H1("6.  Requested actions"),
      H2("For ÖBB"),
      bullet("Arrange a physical check of the AFZ A2 unit on car A (A1 e1-6) – confirmed device-down (section 4.1)."),
      H2("For Stadler"),
      bullet("Confirm the intended hot-standby behaviour for the Sprechstelle redundancy (A3 e1-9 / A2R) and the ZFR redundancy (B1 e1-11): should both members be link-up, or is a silent standby expected? (sections 4.2, 4.3)"),
      bullet("Confirm which services the firewall transit address 172.19.201.1 should expose (TCP 80/22 observed open) (section 5)."),
      bullet("Confirm whether the “potential split-brain” indication is expected while the ZFR primary is down and the standby is active (section 4.3)."),

      new Paragraph({ spacing: { before: 360 }, border: { top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 6 } },
        children: [new TextRun({ text: "Evidence (switch CLI captures, monitoring exports, and reference-train comparisons) is available on request.", italics: true, color: "595959", size: 18 })] }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  const out = "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/reports/customer/Fzg146_4736-118_Port-Fault_Report_v1.0.docx";
  fs.writeFileSync(out, buf);
  console.log("written:", out, buf.length, "bytes");
});
