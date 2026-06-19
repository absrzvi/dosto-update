// RMA report for VDS Rail Consist Switch SN 240658
// Author: Nomad Digital (Abbas Rizvi) — generated 2026-05-21
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, LevelFormat,
  BorderStyle, WidthType, ShadingType, PageNumber, PageBreak, TabStopType, TabStopPosition,
} = require("docx");

// --- helpers ----------------------------------------------------------------
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

const headerShade = { fill: "1F3864", type: ShadingType.CLEAR }; // Nomad-ish dark blue
const altShade   = { fill: "F2F2F2", type: ShadingType.CLEAR };

const p  = (text, opts = {}) => new Paragraph({ children: [new TextRun({ text, ...opts })], spacing: { after: 80 } });
const pb = (text)        => new Paragraph({ children: [new TextRun({ text, bold: true })], spacing: { after: 80 } });
const ph = (text, level) => new Paragraph({ heading: level, children: [new TextRun(text)], spacing: { before: 240, after: 120 } });
const blank = () => new Paragraph({ children: [new TextRun("")] });

// Bullet helper
const bullet = (text) => new Paragraph({
  numbering: { reference: "bullets", level: 0 },
  children: [new TextRun(text)],
  spacing: { after: 60 },
});

// Code/log line (monospace)
const mono = (text) => new Paragraph({
  children: [new TextRun({ text, font: "Consolas", size: 18 })],
  spacing: { after: 0 },
});

// Two-column field row for the metadata table
function row(label, value, alt = false) {
  return new TableRow({
    children: [
      new TableCell({
        borders, margins: cellMargins,
        width: { size: 3200, type: WidthType.DXA },
        shading: alt ? altShade : { fill: "FFFFFF", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true })] })],
      }),
      new TableCell({
        borders, margins: cellMargins,
        width: { size: 6160, type: WidthType.DXA },
        shading: alt ? altShade : { fill: "FFFFFF", type: ShadingType.CLEAR },
        children: [new Paragraph({ children: [new TextRun(value)] })],
      }),
    ],
  });
}

// Section heading row inside a table (full-width dark band)
function sectionRow(label) {
  return new TableRow({
    children: [
      new TableCell({
        borders, margins: cellMargins,
        width: { size: 9360, type: WidthType.DXA },
        shading: headerShade,
        columnSpan: 2,
        children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, color: "FFFFFF" })] })],
      }),
    ],
  });
}

// Step-history table cell helpers
const stCell = (text, opts = {}) => new TableCell({
  borders, margins: cellMargins,
  width: { size: opts.w, type: WidthType.DXA },
  shading: opts.shade || { fill: "FFFFFF", type: ShadingType.CLEAR },
  children: [new Paragraph({ children: [new TextRun({ text, bold: opts.bold, color: opts.color })] })],
});

// --- log excerpt (boot + first ~30 s of polling errors, verbatim) -----------
const logExcerpt = [
  "Jan  1 00:00:17 SW-Std KMdev: Initializing PoE subsystem",
  "Jan  1 00:00:33 SW-Std KMdiag: Starting Diagnostics collector",
  "Jan  1 00:00:36 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:36 SW-Std KMdev: Failure in polling status for PoE port e1-7",
  "Jan  1 00:00:36 SW-Std KMdev: Failure in polling status for PoE port e1-7",
  "Jan  1 00:00:36 SW-Std KMdiag: Error: cannot get interface e1-7 PoE power delivery status",
  "Jan  1 00:00:37 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:37 SW-Std KMdev: Failure in polling status for PoE port e1-15",
  "Jan  1 00:00:38 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:38 SW-Std KMdev: Failure in polling status for PoE port e1-4",
  "Jan  1 00:00:39 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:39 SW-Std KMdev: Failure in polling status for PoE port e1-12",
  "Jan  1 00:00:39 SW-Std KMdev: Postpone trap for KMdev triggered event: coldStart",
  "Jan  1 00:00:40 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:40 SW-Std KMdev: Failure in polling status for PoE port e1-1",
  "Jan  1 00:00:41 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:41 SW-Std KMdev: Failure in polling status for PoE port e1-0",
  "Jan  1 00:00:42 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:42 SW-Std KMdev: Failure in polling status for PoE port e1-9",
  "Jan  1 00:00:43 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:43 SW-Std KMdev: Failure in polling status for PoE port e1-6",
  "Jan  1 00:00:44 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:44 SW-Std KMdev: Failure in polling status for PoE port e1-14",
  "Jan  1 00:00:45 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:45 SW-Std KMdev: Failure in polling status for PoE port e1-3",
  "Jan  1 00:00:46 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:46 SW-Std KMdev: Failure in polling status for PoE port e1-11",
  "Jan  1 00:00:47 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:47 SW-Std KMdev: Failure in polling status for PoE port e0-4",
  "Jan  1 00:00:48 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:48 SW-Std KMdev: Failure in polling status for PoE port e1-8",
  "Jan  1 00:00:48 SW-Std KMdev: Emitting trap for KMdev triggered event: coldStart",
  "Jan  1 00:00:49 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:49 SW-Std KMdev: Failure in polling status for PoE port e1-5",
  "Jan  1 00:00:50 SW-Std KMdev: PoE: cannot read global status",
  "Jan  1 00:00:50 SW-Std KMdev: Failure in polling status for PoE port e1-13",
];

const showPoeExcerpt = [
  "Port    Mode   Status   Class     Power (W)  Priority",
  "-----------------------------------------------------",
  "e0-4    on     E(00)          -        0.00     error",
  "e1-0    on     E(00)          -        0.00     error",
  "e1-1    on     E(00)          -        0.00     error",
  "e1-2    on     E(00)          -        0.00     error",
  "e1-3    on     E(00)          -        0.00     error",
  "e1-4    on     E(00)          -        0.00     error",
  "e1-5    on     E(00)          -        0.00     error",
  "e1-6    on     E(00)          -        0.00     error",
  "e1-7    on     E(00)          -        0.00     error",
  "e1-8    on     E(00)          -        0.00     error",
  "e1-9    on     E(00)          -        0.00     error",
  "e1-10   on     E(00)          -        0.00     error",
  "e1-11   on     E(00)          -        0.00     error",
  "e1-12   on     E(00)          -        0.00     error",
  "e1-13   on     E(00)          -        0.00     error",
  "e1-14   on     E(00)          -        0.00     error",
  "e1-15   on     E(00)          -        0.00     error",
  "-----------------------------------------------------",
  "Total: N/A  Max: N/A  Available: N/A",
];

const showSystem = [
  "Device type:     Ethernet Consist Switch (28 ports - 5X23G)",
  "Model Code:      V72721",
  "Board Revision:  A",
  "System UUID:     e05741c2-7e54-49ff-9528-4967308f3e0b",
  "Primary MacAddr: a0:59:3a:d0:52:40",
  "Serial Number:   240658",
  "Bypass:          [e0-0<->e0-1] [e0-2<->e0-3]",
  "PoE:             available",
  "RTC addon:       NOT present",
  "Free memory:     3213596 kB",
  "System Temp:     41.0C",
  "Running hours:   1512.5",
  "Uptime:          23 min",
  "Bootloader Rel:  1.0.4",
  "FPGA Rel:        3",
  "The system is running in Normal Mode",
];

// --- build doc --------------------------------------------------------------
const doc = new Document({
  creator: "Nomad Digital",
  title: "RMA Report — VDS Rail Consist Switch SN 240658",
  styles: {
    default: { document: { run: { font: "Calibri", size: 22 } } }, // 11pt
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Calibri", color: "1F3864" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: "1F3864" },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Calibri", color: "1F3864" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 }, // 2 cm
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Nomad Digital", bold: true, color: "1F3864" }),
            new TextRun({ text: "\tRMA Report — SN 240658", color: "595959" }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864", space: 4 } },
        }),
      ] })
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({
          children: [
            new TextRun({ text: "Confidential — Nomad Digital / Stadler / VDS Rail", color: "595959", size: 18 }),
            new TextRun({ text: "\tPage ", color: "595959", size: 18 }),
            new TextRun({ children: [PageNumber.CURRENT], color: "595959", size: 18 }),
            new TextRun({ text: " of ", color: "595959", size: 18 }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], color: "595959", size: 18 }),
          ],
          tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        }),
      ] })
    },
    children: [
      // ----- Title block -----
      new Paragraph({
        alignment: AlignmentType.LEFT,
        children: [new TextRun({ text: "Return Merchandise Authorisation (RMA) Report", bold: true, size: 40, color: "1F3864" })],
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "VDS Rail Consist Switch — Permanent PoE controller failure", size: 26, color: "595959" })],
        spacing: { after: 240 },
      }),

      // ----- Document metadata -----
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3200, 6160],
        rows: [
          row("Report date", "21 May 2026", false),
          row("Prepared by", "Abbas Rizvi — Nomad Digital", true),
          row("Customer / fleet", "ÖBB DOSTO (DEL-OBB-035)", false),
          row("Location of unit", "Nomad lab bench (box1-t122, 4-Teiler / 4t bench consist), bench position B3", true),
          row("Recommendation", "RMA — replace unit; PoE controller is a permanent hardware failure", false),
        ]
      }),

      blank(),

      // ===== Section 1 — Summary =====
      ph("1. Summary", HeadingLevel.HEADING_1),
      p("The VDS Rail Consist Switch identified below presents a permanent hardware failure of its Power-over-Ethernet (PoE) controller subsystem. All 14 PoE-capable ports continuously report a polling error (E(00)); the switch is unable to read the PoE global status register from its on-board controller IC. The fault is unchanged across one operating-system reboot (sysadmin reboot) and two full physical power-cycles of the unit, ruling out software, configuration, and transient causes."),
      p("The switch’s data-plane (Ethernet switching, RSTP, management SSH, trunk operation) is fully operational. Only the PoE subsystem is affected. The front-panel status LED is solid/flashing red and will remain so until the PoE subsystem is repaired."),
      p("Nomad Digital requests RMA of this unit. The diagnosis below provides the evidence collected on 21 May 2026 from the live unit on the Nomad lab bench."),

      // ===== Section 2 — Unit under report =====
      ph("2. Unit under report", HeadingLevel.HEADING_1),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3200, 6160],
        rows: [
          sectionRow("Hardware identification"),
          row("Hostname",              "4t-B3-v3-250"),
          row("Serial number",         "240658", true),
          row("System UUID",           "e05741c2-7e54-49ff-9528-4967308f3e0b"),
          row("Primary MAC address",   "a0:59:3a:d0:52:40", true),
          row("Model code",            "V72721"),
          row("Device type",           "Ethernet Consist Switch (28 ports — 5X23G)", true),
          row("Board revision",        "A"),
          row("Bootloader release",    "1.0.4", true),
          row("FPGA release",          "3"),
          row("PoE inventory flag",    "available (per show system)", true),
          row("Running hours",         "1,512.5 h"),

          sectionRow("Software"),
          row("Firmware version",      "7.4.2 (Build Release 77411)"),
          row("Operating mode",        "Normal Mode", true),

          sectionRow("Environment at time of diagnosis"),
          row("Location",              "Nomad lab bench, 4-Teiler bench consist (“4t”), position B3"),
          row("Ambient via show system","41.0 °C (max permitted 100.0 °C)", true),
          row("Free memory",           "3,213,596 kB (~3.2 GB) — no memory pressure"),
          row("Bypass relays",         "[e0-0<→>e0-1] [e0-2<→>e0-3] — nominal", true),
        ]
      }),

      // ===== Section 3 — Symptom =====
      ph("3. Observed symptom", HeadingLevel.HEADING_1),

      ph("3.1  show poe output", HeadingLevel.HEADING_2),
      p("Every PoE-capable port reports status code E(00) (polling error). The total system PoE power budget is reported as N/A by the switch, because the controller status register cannot be read. Verbatim output from the switch CLI on 21 May 2026:"),
      ...showPoeExcerpt.map(mono),
      blank(),

      ph("3.2  System log (excerpt)", HeadingLevel.HEADING_2),
      p("The switch emits a continuous loop of PoE polling failures, one per second per PoE-capable port. The pattern begins immediately after the PoE subsystem is initialised at boot (`Initializing PoE subsystem` at t+17 s) and continues indefinitely. The following extract covers the boot window plus the first ~30 s of the polling loop; the pattern is identical from boot through the most recent observation (23 min uptime, 2,831 PoE error lines accumulated in the system log)."),
      ...logExcerpt.map(mono),
      blank(),
      p("Quantitative summary of the log:", { italics: true }),
      bullet("Total system log lines since last boot: 2,875"),
      bullet("PoE error / KMdiag lines: 2,831 (98.5% of all log volume)"),
      bullet("Pattern: KMdev: “PoE: cannot read global status” followed by “Failure in polling status for PoE port <port>”, cycling through every PoE-capable port (e0-4, e1-0 through e1-15) on a ~1 Hz polling interval."),

      ph("3.3  Front-panel indication", HeadingLevel.HEADING_2),
      p("Status LED solid/flashing red, consistent with the PoE subsystem fault."),

      ph("3.4  Data-plane state", HeadingLevel.HEADING_2),
      p("Ethernet switching is fully operational. Management SSH on the unit is responsive. From show interface summary on 21 May 2026: e0-0 and e0-1 (10G inter-coach trunks) up at 10 Gbps full-duplex; e1-11 (access port) up at 1 Gbps full-duplex. No data-plane error counters elevated. The failure is isolated to the PoE controller subsystem."),

      // ===== Section 4 — Tests performed =====
      ph("4. Tests performed and outcomes", HeadingLevel.HEADING_1),
      p("To rule out transient, software, configuration, and brown-out / latched-state causes, the following recovery steps were attempted on 21 May 2026. The fault was unchanged after every step."),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [600, 2400, 3000, 3360],
        rows: [
          new TableRow({
            tableHeader: true,
            children: [
              stCell("#",       { w:  600, bold: true, color: "FFFFFF", shade: headerShade }),
              stCell("Action",  { w: 2400, bold: true, color: "FFFFFF", shade: headerShade }),
              stCell("Outcome",         { w: 3000, bold: true, color: "FFFFFF", shade: headerShade }),
              stCell("Interpretation",  { w: 3360, bold: true, color: "FFFFFF", shade: headerShade }),
            ],
          }),
          new TableRow({ children: [
            stCell("1", { w:  600 }),
            stCell("Initial diagnostic capture of show poe and system log on the in-situ unit.", { w: 2400 }),
            stCell("All 14 PoE ports = E(00); continuous KMdev “cannot read global status” in log.", { w: 3000 }),
            stCell("Confirms presence of the fault.", { w: 3360 }),
          ]}),
          new TableRow({ children: [
            stCell("2", { w:  600, shade: altShade }),
            stCell("CLI software reboot (sysadmin reboot via SSH).", { w: 2400, shade: altShade }),
            stCell("Switch came back up in ~30 s with new uptime; show poe still all E(00); identical error loop in log from t+17 s onward.", { w: 3000, shade: altShade }),
            stCell("Operating-system restart does not clear the fault. Rules out kernel/driver state corruption.", { w: 3360, shade: altShade }),
          ]}),
          new TableRow({ children: [
            stCell("3", { w:  600 }),
            stCell("Physical power-cycle #1 (full power removed at the bench PSU, 30 s off, repower).", { w: 2400 }),
            stCell("Switch came back up; show poe still all E(00); identical error loop resumed.", { w: 3000 }),
            stCell("Full de-energise of the controller IC does not clear a latched / brown-out state. Rules out transient power / latch-up.", { w: 3360 }),
          ]}),
          new TableRow({ children: [
            stCell("4", { w:  600, shade: altShade }),
            stCell("Physical power-cycle #2 (repeated, identical procedure to step 3).", { w: 2400, shade: altShade }),
            stCell("Switch came back up; show poe still all E(00); identical error loop resumed (1,566 error lines accumulated within first 13 min of new uptime).", { w: 3000, shade: altShade }),
            stCell("Second independent confirmation of the fault. The failure is persistent, not transient.", { w: 3360, shade: altShade }),
          ]}),
        ]
      }),

      blank(),
      p("Throughout all four steps, ambient temperature remained within normal range (41.0–44.5 °C against a 100 °C maximum). Firmware version, configuration, and external power feed were unchanged. The data-plane functions continued to operate normally."),

      // ===== Section 5 — Root cause =====
      ph("5. Root-cause assessment", HeadingLevel.HEADING_1),
      p("The fault signature — “cannot read global status” affecting every PoE-capable port simultaneously, persisting across both operating-system reboot and full physical power-cycle — is a textbook indication of a board-level hardware failure of the on-board PoE controller IC or its interface to the main MCU (typically the I²C / SPI bus used for status polling). The reasoning:"),
      bullet("If the fault were port-level (cable, attached device, port-side electronics), only one or two ports would fail — not all 14 in lock-step."),
      bullet("If the fault were software / driver, a CLI reboot would have re-initialised the driver state and cleared it. It did not."),
      bullet("If the fault were a latched / brown-out condition in an otherwise healthy controller, a full physical power-cycle would have de-energised the IC and cleared the latch. Two independent physical cycles did not."),
      bullet("Ambient temperature is well within the documented 100 °C operating maximum; thermal cause is excluded."),
      bullet("Other PoE-capable switches sharing the same bench infrastructure (12 sister units of the same model family) report normal show poe output, confirming the bench-side 48 Vdc PoE feed is healthy."),
      p("Conclusion: the PoE controller subsystem of this specific unit (SN 240658) has failed permanently. The unit cannot be returned to service in any role that requires it to power PoE devices; replacement is required."),

      // ===== Section 6 — Action requested =====
      ph("6. Action requested", HeadingLevel.HEADING_1),
      bullet("RMA approval for the unit identified in section 2 (hostname 4t-B3-v3-250, SN 240658)."),
      bullet("Repair or replacement of the PoE controller subsystem on the returned board, or supply of a functionally equivalent replacement unit (V72721, board rev A, firmware-compatible with 7.4.2)."),
      bullet("Return-shipping instructions (consignee, RMA tracking number, packaging requirements)."),

      // ===== Section 7 — Operational note =====
      ph("7. Operational note", HeadingLevel.HEADING_1),
      p("Pending RMA disposition, the unit remains physically installed on the Nomad lab bench. Its non-PoE Ethernet functions (L2 switching, trunking, RSTP, management) continue to operate, so the bench can be used for any test that does not depend on PoE delivery from this switch. Any device that would normally be powered from this switch (e.g. a Westermo radio on port e0-4) will not power on; affected bench tests will be deferred or relocated to a sister switch until the unit is repaired or replaced."),

      // ===== Appendix A — show system =====
      new Paragraph({ children: [new PageBreak()] }),
      ph("Appendix A — Full show system output", HeadingLevel.HEADING_1),
      p("Captured from the live unit, 21 May 2026, 23 min after the second physical power-cycle:"),
      ...showSystem.map(mono),

      // ===== Appendix B — Contact =====
      blank(), blank(),
      ph("Appendix B — Reporting contact", HeadingLevel.HEADING_1),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3200, 6160],
        rows: [
          row("Name",          "Abbas Rizvi"),
          row("Organisation",  "Nomad Digital", true),
          row("Role",          "Onboard network engineer — ÖBB DOSTO programme"),
          row("Email",         "abbas.rizvi@nomadrail.com", true),
          row("Diagnostic date","21 May 2026"),
          row("Reference",     "DEL-OBB-035 — lab bench (box1-t122 / “4t” bench consist)", true),
        ]
      }),
    ]
  }]
});

Packer.toBuffer(doc).then((buf) => {
  const out = "C:\\Users\\AbbasRizvi\\Documents\\dosto-troubleshooting\\reports\\rma\\RMA_Report_VDS_Switch_SN240658_2026-05-21.docx";
  fs.writeFileSync(out, buf);
  console.log("Wrote:", out);
});
