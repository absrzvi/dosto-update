// Generate ÖBB-facing status report for trainset 4736-114 / Fzg 142.
// House style matches existing OBB_Fzg*_Network_Health_Check reports.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
  WidthType, ShadingType, PageNumber, TableOfContents,
} = require("docx");

const BLUE = "1F4E79";
const LIGHT = "D5E8F0";
const GREY = "CCCCCC";
const border = { style: BorderStyle.SINGLE, size: 1, color: GREY };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, w, opts = {}) {
  const runs = Array.isArray(text) ? text : [new TextRun({ text: String(text), bold: opts.bold, color: opts.color })];
  return new TableCell({
    borders,
    width: { size: w, type: WidthType.DXA },
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: runs })],
  });
}
function hrow(cells, widths) {
  return new TableRow({ children: cells.map((c, i) => cell(c, widths[i], { bold: true, fill: LIGHT })) });
}
function row(cells, widths, opts = {}) {
  return new TableRow({ children: cells.map((c, i) => cell(c, widths[i], opts)) });
}
function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, ...opts })] });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 },
    children: typeof text === "string" ? [new TextRun(text)] : text });
}
function h(text, level) {
  return new Paragraph({ heading: level, children: [new TextRun(text)] });
}

const CW = 9360; // content width, US Letter 1" margins

const doc = new Document({
  creator: "Nomad Digital",
  title: "DOSTO 4736-114 (Fzg. 142) — Commissioning Status",
  styles: {
    default: { document: { run: { font: "Arial", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, color: BLUE, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: BLUE, font: "Arial" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 1 } },
    ],
  },
  numbering: {
    config: [{ reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 460, hanging: 260 } } } }] }],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BLUE, space: 1 } },
      children: [
        new TextRun({ text: "Nomad Digital", bold: true, color: BLUE, size: 20 }),
        new TextRun({ text: "    Connected Transport, Intelligent Solutions", italics: true, color: "808080", size: 16 }),
      ] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      tabStops: [{ type: "right", position: CW }],
      children: [
        new TextRun({ text: "Confidential — for ÖBB and Nomad Digital review", size: 16, color: "808080" }),
        new TextRun({ text: "\tPage ", size: 16, color: "808080" }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "808080" }),
      ] })] }) },
    children: [
      // ---------- Title block ----------
      new Paragraph({ spacing: { before: 600, after: 0 }, children: [
        new TextRun({ text: "Trainset Commissioning Status Report", bold: true, size: 40, color: BLUE }) ] }),
      new Paragraph({ spacing: { after: 240 }, children: [
        new TextRun({ text: "DOSTO Nahverkehr 6-car", size: 24, color: "808080" }) ] }),

      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [3120, 6240], rows: [
        row(["Trainset (Fzg. Nr.)", "4736-114"], [3120, 6240]),
        row(["Fahrzeug-ID (Fzg.)", "142"], [3120, 6240]),
        row(["Configuration", "6-car (A/B/C/D/E/F)"], [3120, 6240]),
        row(["Status date", "20 June 2026"], [3120, 6240]),
        row(["Prepared by", "Abbas Rizvi, Nomad Digital"], [3120, 6240]),
        row(["Prepared for", "ÖBB — Österreichische Bundesbahnen"], [3120, 6240]),
        row(["Document version", "1.0"], [3120, 6240]),
      ] }),

      new Paragraph({ spacing: { before: 360 }, children: [] }),

      // ---------- 1. Status summary ----------
      h("1. Status Summary", HeadingLevel.HEADING_1),
      p("The on-board Layer-2 network for trainset 4736-114 (Fzg. 142) is commissioned and healthy. The consist switching fabric — all backbone switches and access points — is in service on the target software baseline, and the interface to the Stadler network (VLAN 7) is correctly configured, up, and carrying traffic. Two items remain open:"),
      bullet([
        new TextRun({ text: "Access-point firmware (Nomad action, in progress): ", bold: true }),
        new TextRun("the 24 Wi-Fi access points are on the correct configuration and are being updated to the target firmware release."),
      ]),
      bullet([
        new TextRun({ text: "Passenger-display / energy-meter ports (verification requested): ", bold: true }),
        new TextRun("14 switch ports designated for on-board passenger displays and one energy meter show no network link. Nomad has confirmed the switch side is healthy; we ask ÖBB / Stadler to verify the end devices are fitted and powered (Section 4)."),
      ]),
      p("No fault was found in the consist switching fabric itself.", { italics: true }),

      // ---------- 2. Network fabric ----------
      h("2. Network Fabric — Commissioned", HeadingLevel.HEADING_1),
      p("The backbone switching fabric and access points are fully in service on the target baseline. Each item below was verified live on the train on 20 June 2026; the evidence noted is the result observed during that check."),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [2700, 1400, 5260], rows: [
        hrow(["Element", "State", "Verification evidence"], [2700, 1400, 5260]),
        row(["Backbone switches", "18 / 18", "Device validation (obn validate) confirms all 18 switches across coaches A–F report the correct configuration (nv6-X-v8-142) and firmware (7.4.2)."], [2700, 1400, 5260]),
        row(["Wi-Fi access points", "24 / 24", "All 24 access points hold a management-network lease and report the correct Nomad configuration. Firmware update outstanding — see Section 3."], [2700, 1400, 5260]),
        row(["Inter-coach trunks", "OK", "All inter-coach backbone links established; consistent with the device count above (all 18 switches reachable across the consist)."], [2700, 1400, 5260]),
        row(["Spanning Tree (RSTP)", "Stable", "A single, stable spanning-tree root is shared across the consist (no topology instability observed)."], [2700, 1400, 5260]),
        row(["Stadler interface (VLAN 7)", "Up", "Correct IP address configured for this trainset; interface up and carrying traffic (inbound and outbound, no errors); Stadler firewall reachable."], [2700, 1400, 5260]),
        row(["Network monitoring", "Reporting", "All consist devices (switches and access points) are visible and reporting in the network monitoring system."], [2700, 1400, 5260]),
      ] }),
      p("The interface to the Stadler network (VLAN 7) is configured with the correct IP address for this trainset and is up and carrying traffic — at the time of the check the interface had received and sent traffic with no errors. The Stadler firewall is reachable from the Nomad CCU and is responding in line with its configured security policy, confirming the Stadler-facing transit link is in service."),

      // ---------- 3. Open Nomad item ----------
      h("3. Open Nomad Item — Access-Point Firmware", HeadingLevel.HEADING_1),
      p("Device validation confirms all 24 access points are present on the management network and on the correct Nomad configuration. They currently carry firmware 6.10.0-0; the update to the target release (6.11.2-0) is in progress as part of normal commissioning. This is a Nomad-side software task requiring no ÖBB or Stadler action, and it does not affect backbone availability."),

      // ---------- 4. Verification requested ----------
      h("4. Verification Requested — Passenger-Display and Energy-Meter Ports", HeadingLevel.HEADING_1),
      p("During commissioning Nomad observed that 14 switch ports designated for on-board passenger displays (Fahrgast­anzeigen / Bildschirme) and one energy meter (Energiezähler) show no network link. The ports are enabled and configured correctly per the consist design, but no connection is established at the device end."),

      h("4.1 What Nomad has verified", HeadingLevel.HEADING_2),
      p("Nomad has carried out a full set of switch-side checks and confirmed the network side is healthy for each affected port:"),
      bullet("Each port is enabled and configured correctly per the approved consist design."),
      bullet("On every affected switch, other identical display ports are linked and passing traffic — confirming the switch hardware and configuration are good."),
      bullet("The affected ports show no link, no traffic, and no error counters — consistent with no device connected at the far end, rather than a switch fault."),
      bullet("A port reset (disable/enable) was performed on all 14 ports; none recovered."),
      p("These ports carry data only (the displays are independently powered), so the device's power state cannot be confirmed from the network side. The display network (a Stadler-side device VLAN) is not visible to Nomad equipment."),

      h("4.2 Affected ports, shown against the working ports on the same switches", HeadingLevel.HEADING_2),
      p("The table below lists, for each affected switch, the device ports that are not connected (no link) alongside the device ports on that same switch that are connected and working. On every switch, neighbouring display ports of identical type are up and passing traffic — which is the basis for concluding the switch hardware and configuration are sound and the issue lies at the device end."),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [1500, 4030, 3830], rows: [
        hrow(["Coach / switch", "Working device ports (link up)", "Not connected (no link)"], [1500, 4030, 3830]),
        row(["A — A1", "Bildschirm A5, A3; ADU A; Audio Amp. A1 (4)", "Bildschirm A7, A1 (2)"], [1500, 4030, 3830]),
        row(["C — C1", "Bildschirm C7, C1, C; Audio Amp. C1 (4)", "Bildschirm C5, C3 (2)"], [1500, 4030, 3830]),
        row(["C — C2", "Bildschirm C8, C2, C4, C11; Audio Amp. C2 (5)", "Bildschirm C6 (1)"], [1500, 4030, 3830]),
        row(["D — D2", "Bildschirm D6, D2, D4, D11; Audio Amp. D2 (5)", "Bildschirm D8 (1)"], [1500, 4030, 3830]),
        row(["E — E1", "Bildschirm E5, E1, E3, E; Audio Amp. E1 (5)", "Bildschirm E7 (1)"], [1500, 4030, 3830]),
        row(["E — E2", "Bildschirm E8, E6, E4, E11; Audio Amp. E2 (5)", "Bildschirm E2 (1)"], [1500, 4030, 3830]),
        row(["E — E3", "(no other device ports on this switch)", "Energiezähler E — energy meter (1)"], [1500, 4030, 3830]),
        row(["F — F1", "Bildschirm F7, F5, F1, F; Audio Amp. F1 (5)", "Bildschirm F3 (1)"], [1500, 4030, 3830]),
        row(["B — B1", "Bildschirm B1; ADU B; Audio Amp. B1 (3)", "Bildschirm B7, B5, B3 (3)"], [1500, 4030, 3830]),
        row(["B — B2", "Bildschirm B8, B6, B4; Audio Amp. B2 (4)", "Bildschirm B2 (1)"], [1500, 4030, 3830]),
        row([[new TextRun({ text: "Total", bold: true })], [new TextRun({ text: "40 device ports up", bold: true })], [new TextRun({ text: "14 not connected (13 displays + 1 energy meter)", bold: true })]], [1500, 4030, 3830], { fill: LIGHT }),
      ] }),

      h("4.3 Requested action", HeadingLevel.HEADING_2),
      p("Nomad asks ÖBB / Stadler to confirm, for each listed port, that the passenger display or energy meter is installed, powered, and its network connection in place. Where a device is connected and powered but still shows no link, the cable or the device's network interface should be checked at the device end."),
      p("Once a device is connected and powered, Nomad can re-verify the link remotely on request. If any of these devices are not yet installed as part of ongoing fit-out, the corresponding ports are expected to be inactive and no action is required for those.", { italics: true }),

      // ---------- 5. Summary table ----------
      h("5. Summary", HeadingLevel.HEADING_1),
      new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: [4680, 2000, 2680], rows: [
        hrow(["Item", "Owner", "Status"], [4680, 2000, 2680]),
        row(["Backbone switches & configuration", "Nomad", "Complete"], [4680, 2000, 2680]),
        row(["Access points — configuration", "Nomad", "Complete"], [4680, 2000, 2680]),
        row(["Access points — firmware update", "Nomad", "In progress"], [4680, 2000, 2680]),
        row(["Passenger-display / energy-meter ports", "ÖBB / Stadler", "Verification requested"], [4680, 2000, 2680]),
      ] }),
      new Paragraph({ spacing: { before: 240 }, children: [
        new TextRun({ text: "Prepared by Abbas Rizvi, Nomad Digital — 20 June 2026.", italics: true, size: 18, color: "808080" }) ] }),
    ],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  const out = "reports/customer/OBB_Fzg142_4736-114_Commissioning_Status_v1.0.docx";
  fs.writeFileSync(out, buf);
  console.log("wrote " + out + " (" + buf.length + " bytes)");
});
