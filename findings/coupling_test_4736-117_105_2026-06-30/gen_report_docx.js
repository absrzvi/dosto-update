// Generator for the 2026-06-30 coupled-train test report (4736-117 + 4736-105)
// Matches the structure/branding of the 2026-06-12 June report (gen_report_docx.js in the 110_119 folder).
const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, LevelFormat, HeadingLevel, BorderStyle,
        WidthType, ShadingType, PageNumber, PageBreak } = require("docx");

const MONO = "Consolas";

function h1(t){ return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing:{ before: 240, after: 120 }, children:[new TextRun(t)] }); }
function h2(t){ return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing:{ before: 160, after: 80 }, children:[new TextRun(t)] }); }
function p(...runs){ return new Paragraph({ spacing:{ after: 120 }, children: runs.map(r => typeof r === "string" ? new TextRun(r) : r) }); }
function b(t){ return new TextRun({ text: t, bold: true }); }
function bullet(t){ return new Paragraph({ numbering:{ reference:"bullets", level:0 }, spacing:{ after: 60 }, children:[ new TextRun(t) ] }); }
function num(t){ return new Paragraph({ numbering:{ reference:"numbers", level:0 }, spacing:{ after: 60 }, children:[ new TextRun(t) ] }); }
function code(lines){
  return lines.map(l => new Paragraph({
    spacing:{ after: 0 },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children:[ new TextRun({ text: l || " ", font: MONO, size: 15 }) ]
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
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 60 }, children:[ new TextRun({ text: "\u00d6BB DOSTO 4736-117 (Fzg 145) + 4736-105 (Fzg 133)", size: 26 }) ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 240 }, children:[ new TextRun({ text: "Test date: 2026-06-30  |  Nomad Digital  |  Prepared for: \u00d6BB / Stadler / VDS Rail Support  |  v1.0", size: 20, color: "555555" }) ] }),

  // 1. EXEC SUMMARY
  h1("1. Executive Summary"),
  p("On 2026-06-30 Nomad Digital performed a controlled coupling test of two 6-car DOSTO units \u2014 4736-117 (Fzg 145) and 4736-105 (Fzg 133), 36 consist switches combined \u2014 to validate the proposed v9 switch-configuration changes against the multi-traction faults seen previously (the June 2026-06-12 test on 4736-110 + 4736-119), and to confirm whether they resolve the coupled-operation CCTV degradation. Key outcomes:"),
  num("The two v9 changes tested were validated end-to-end and made persistent on both trains: (M1) a flat, symmetric coupler port-cost of 20,000, and (M2) a dedicated coupler native VLAN 999. Both survive a cold restart."),
  num("M1 (symmetric coupler cost) eliminated the continuous RSTP topology-change (TC) storm that was the central finding of the June test. With the symmetric cost in place, coupling produced a clean single-root topology with zero MAC-flush churn \u2014 confirmed both on a live (hot) coupling and on a cold boot."),
  num("The coupled CCTV latency / HMI degradation seen previously was resolved by the cost fix alone, with no firewall or VLAN-5 change. This revises the earlier hypothesis: the degradation was driven primarily by the TC storm (continuous MAC-table flushing forcing the camera traffic to flood), not by a firewall interaction."),
  num("M2 (coupler native VLAN 999) was found to be necessary, not optional. A previously-unseen fault was root-caused during this test: with the default native VLAN 1 on the coupler, the two trains' switch-management subnets (192.168.1.0/24, shared) bridge across the coupler and break the switches' own DHCP, so switches progressively lose their management IP while coupled. Applying native VLAN 999 closed this bridge and fixed switch DHCP."),
  num("One issue remains open and is being investigated by Nomad: on 4736-117 only, roughly half the consist switches do not complete their management-DHCP while coupled (they recover within one minute of decoupling). This is a Nomad-side management-visibility matter \u2014 it does not affect the Layer-2 data path, the CCTV, or any Stadler service \u2014 and is being pursued with the switch vendor (VDS)."),
  num("A single-firewall VLAN-5 routing change was trialled on 4736-105 as a confirmation step and then deliberately rolled back; it was not required, as the cost fix had already resolved the CCTV symptom."),

  // 2. TEST CONFIG
  h1("2. Test Configuration"),
  table([2300, 3363, 3363], [
    ["Item", "4736-117 (Fzg 145) \u2014 \u201cmaster\u201d", "4736-105 (Fzg 133) \u2014 \u201cbackup\u201d"],
    ["CCU", "box1-t32, 10.179.32.1", "box1-t1, 10.179.1.1"],
    ["Consist switches", "18 (nv6-*-v8-145)", "18 (nv6-*-v8-133)"],
    ["vlan7 (Stadler FW transit)", "172.19.200.130/17 (FW peer .200.129)", "172.19.194.130/17 (FW peer .194.129)"],
    ["Priority-0 bridge", "nv6-D1-v8-145 (a0:59:3a:d0:76:e0)", "nv6-D1-v8-133 (a0:59:3a:d0:6c:80)"],
    ["Coupler ports", "e0-2 on A1, A3, B1, B3", "e0-2 on A1, A3, B1, B3"],
    ["Coupler trunk (baseline)", "native VLAN 1, allowed VLANs 5 and 15", "native VLAN 1, allowed VLANs 5 and 15"],
    ["Coupler cost (baseline, v8)", "144,999,999 (A1, B3); default (A3, B1)", "132,999,999 (A1, B3); default (A3, B1)"],
  ]),
  p(""),
  p(b("vlan7 correction during commissioning: "), "On arrival, 4736-117's CCU vlan7 address was found misrendered as 172.19.208.2/17 (which decodes to Fzg 160). It was corrected to the value for Fzg 145, 172.19.200.130/17, via the standard persistent-edit procedure and verified after reboot (firewall peer 172.19.200.129 reachable at ARP level, ICMP filtered as expected for a commissioned firewall). 4736-105's vlan7 was already correct (172.19.194.130/17)."),
  p(b("Monitoring method: "), "RSTP, Coupled-Mode, switching and IGMP debug logging (configure system logging debug rstp,coupled,switch,igmp) enabled on the coupler switches; switch spanning-tree, MAC-address-table and interface-counter harvests taken via SSH from each CCU; CCU-side DHCP server logs and packet captures (tcpdump) on the management VLAN. The TC-churn measurement counts \u201cFlushing all entries\u201d / topology-change log events over a fixed interval and compares samples taken 30\u201390 s apart (a frozen count = converged; a rising count = active churn)."),

  // 3. METHODOLOGY
  h1("3. Methodology"),
  p("The test was structured to isolate one variable at a time and to obtain, where possible, a clean before/after contrast on a single coupling event. The sequence was:"),
  num("Decouple to two solo trains; confirm each converges to a clean single root and that all four coupler ports read link-DOWN (a precaution against the \u201cphantom live coupler\u201d effect seen in June)."),
  num("Capture the baseline coupler port-costs (for exact rollback) and the RSTP topology, solo."),
  num("Apply the symmetric coupler cost (20,000) on all eight coupler ports while solo and stable, and persist it to start-up configuration."),
  num("Recouple and measure: confirm a single merged root, one forwarding coupler link with its redundant twin blocked, and the TC-churn count over a sustained window."),
  num("Observe the CCTV feed on the cab HMI throughout, correlating it with the measured Layer-2 state."),
  num("Where a fault appeared (switch-DHCP loss while coupled), instrument the DHCP exchange directly on the CCU and in the switch forwarding tables to root-cause it, then apply and persist the corresponding fix (native VLAN 999) and re-verify."),
  num("Restart both trains while coupled to confirm the persisted configuration produces a clean cold-boot convergence."),

  // FIGURE 1 \u2014 topology
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ before: 160, after: 40 },
    children:[ new ImageRun({ type: "png", data: fs.readFileSync("topology_coupled_2026-06-30.png"), transformation: { width: 624, height: 395 } }) ] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing:{ after: 160 },
    children:[ new TextRun({ text: "Figure 1 \u2014 Coupled 2x6 fabric after the v9 changes: a single merged RSTP root (4736-105 D1), one forwarding coupler link (117 B1 to 105 A1) with its redundant twin blocked, and the v9 coupler-port settings (cost 20000 and native VLAN 999) that the test validated.", italics: true, size: 17, color: "555555" }) ] }),

  // 4. FINDINGS
  h1("4. Findings"),

  h2("F1 \u2014 Symmetric coupler cost (M1) eliminates the TC storm \u2014 VALIDATED"),
  p("The central fault of the June test was a continuous RSTP topology-change condition: every switch in both trains flushed its MAC table approximately every two seconds, traced to the active coupler link whose two ends carried mismatched administratively-configured port-costs. The v9 remedy is a flat, symmetric cost of 20,000 on every coupler port."),
  p("In this test the symmetric cost was applied to all eight coupler ports while the trains were decoupled, then the trains were coupled. The merged network converged cleanly:"),
  bullet("Single root: nv6-D1-v8-133 (a0:59:3a:d0:6c:80). 4736-117 reached the root across the coupler."),
  bullet("Active coupler link: 4736-117 B1 e0-2 = ROOT / FORWARDING \u2194 4736-105 A1 e0-2 = DESIGNATED / FORWARDING, both ends at cost 20,000 (equal). The remaining coupler links were down or blocked \u2014 one forwarding link, correctly."),
  bullet("TC churn = zero. Two samples taken ~90 s apart, across switches on both trains, showed a topology-change / flush count of 0. The switch logs contained only the expected boot-time RSTP-handler and cold-start lines \u2014 no \u201cFlushing all entries\u201d, no proposal duel, no topology-change events."),
  p("This is the direct contrast with June, where the same 36-switch coupling logged \u201cFlushing all entries\u201d every ~2 seconds continuously. With the symmetric cost in place the storm does not occur. The result was reproduced on a cold restart (see F5)."),

  h2("F2 \u2014 Coupled CCTV degradation resolved by the cost fix alone"),
  p("Shortly after the symmetric cost was applied and the churn stopped, the cab HMI on 4736-117 showed the CCTV feeds from both trains, with no latency \u2014 and no change had been made to VLAN 5 or to either firewall. The supporting Layer-2 evidence, captured while coupled and healthy:"),
  bullet("The VLAN-5 forwarding table on the active coupler switch was stable (119 MAC entries, identical across two samples 8 s apart) \u2014 i.e. camera frames were being forwarded, not flooded. In June the equivalent table was being flushed every ~2 s."),
  bullet("The coupler carried roughly symmetric video traffic (~95 Mbps each direction) \u2014 healthy bidirectional CCTV, not flood traffic."),
  p(b("Interpretation: "), "the coupled CCTV latency/HMI degradation seen previously was caused primarily by the TC storm \u2014 the continuous MAC-table flushing turned forwarded camera traffic into flooded traffic and overwhelmed the path. The June investigation could not separate this from a suspected firewall interaction because the only mitigation available at the time (a full physical decouple) also stopped the churn. This test isolates the variable: the churn was stopped without decoupling and without touching either firewall, and the CCTV recovered."),
  p(b("Confirmation step (single-firewall VLAN-5 routing): "), "to positively rule the firewall in or out, the VLAN-5 camera gateway on 4736-105 was repointed to the master train's firewall (so all VLAN-5 traffic would route through one firewall), first on one coach and then on all 18 switches. The CCTV continued to work with no degradation, confirming the firewall routing was not the bottleneck. This change was a confirmation only and was subsequently rolled back \u2014 the cameras on 4736-105 are back on their own firewall (172.18.194.129), persisted."),

  h2("F3 \u2014 Coupler native VLAN 1 breaks switch DHCP while coupled (M2 necessary) \u2014 ROOT-CAUSED"),
  p("During the test a previously-undocumented fault was observed and root-caused. With the coupler trunk left at its default native VLAN (VLAN 1), the consist switches on 4736-117 progressively lost their own management IP address while coupled: the count of switches holding a valid management lease fell from 18 to about 9. The switches remained electrically present and forwarding throughout (visible in ARP, RSTP root stable) \u2014 only their management-plane DHCP failed."),
  p("The CCU DHCP server log showed the precise failure: each affected switch repeatedly sent a DHCP Discover, received a valid DHCP Offer, and then sent no DHCP Request \u2014 the four-way handshake never completed and the switch looped:"),
  ...code([
    "10:40:04  DHCPDISCOVER from a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:40:04  DHCPOFFER   on 10.179.32.202 to a0:59:3a:d0:79:60 (nv6-A1-v8-145)",
    "10:40:17  DHCPDISCOVER from a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100   <-- again, no Request",
    "10:40:17  DHCPOFFER   on 10.179.32.202 to a0:59:3a:d0:79:60 (nv6-A1-v8-145)",
    "  (no DHCPREQUEST, no DHCPACK \u2014 the handshake never completes)",
  ]),
  p(""),
  p(b("Root cause: "), "the coupler's native (untagged) VLAN was VLAN 1. The end-wagon switches carry an interface on VLAN 1 with an address in 192.168.1.0/24, and every train uses that same subnet. With native VLAN 1 on the coupler, the two trains' VLAN-1 (switch-management) segments bridge directly across the coupler. This was confirmed in the forwarding tables: the VLAN-1 MAC table on a 4736-117 coupler switch held 57 entries learned via the coupler port, including the management MACs of 4736-105's switches. The switches' DHCP Request is a broadcast that travels on this bridged VLAN-1 path; with the two 192.168.1.0/24 segments overlapping, the Request/Acknowledge exchange is disrupted and the switch never completes its lease."),
  p(b("Fix and verification (M2): "), "VLAN 999 was created on the coupler switches and the coupler trunk set to native VLAN 999 (a dead \u201cblackhole\u201d VLAN), keeping the allowed set 5 and 15 unchanged. The effect was immediate and measurable:"),
  bullet("On the active coupler switch the VLAN-1 cross-train MAC count fell from 57 \u2192 39 \u2192 10 as the foreign entries aged out \u2014 the cross-train VLAN-1 bridge closed."),
  bullet("Switches began completing the full DHCP handshake (Request \u2192 Acknowledge) again."),
  bullet("On decoupling, 4736-117 recovered from 9 to 18 switches within about one minute \u2014 directly confirming that the native-VLAN-1 bridge was the cause."),
  p("M2 is therefore a required part of the v9 change, not an optional hardening step. Both M1 and M2 are now persisted on both trains."),

  h2("F4 \u2014 Residual switch-DHCP issue on 4736-117 (open, Nomad-side, not service-affecting)"),
  p("After M2 was applied, 4736-117 still does not bring all 18 switches to a completed management lease while coupled \u2014 roughly half complete, the rest show the same Discover\u2192Offer\u2192loop pattern, and they recover within a minute of decoupling. This is distinct from the native-VLAN-1 cause (which is fixed): the management VLAN itself does not cross the coupler, the DHCP server offers valid addresses, and the following were each ruled out by direct measurement \u2014 DHCP pool exhaustion, a second/rogue DHCP server, and a transient broadcast flood from a test device that was present earlier in the day and has since been disconnected."),
  p(b("Impact: "), "this is a management-visibility issue on the Nomad side only. The switches are electrically present and forwarding; the Layer-2 data path, the CCTV, and all Stadler services are unaffected. 4736-105 did not exhibit this behaviour (it reached a full 18/18 coupled and on cold boot)."),
  p(b("Next step: "), "the remaining lead is switch-side DHCP-client behaviour while coupled (the switch accepting an offer but not issuing the Request). Because the affected switches have no stable management address to connect to while in this state, the investigation is being taken to the switch vendor (VDS) with the captured evidence."),

  h2("F5 \u2014 Cold-boot validation with the full v9 configuration"),
  p("With both M1 (cost 20,000) and M2 (native VLAN 999) saved to start-up configuration, both trains were restarted while coupled. The configuration rendered correctly from start-up on every switch that came up, with no topology churn and no VLAN-1 cross-train leak \u2014 i.e. the fix is durable across a power cycle. 4736-105 returned to a full, clean 18/18 coupled. 4736-117 again showed the residual F4 behaviour (about half its switches not completing a management lease while coupled), consistent with F4 being independent of the coupling configuration."),

  h2("F6 \u2014 CCTV session recovery after a mass camera-port operation (operational note)"),
  p("When the VLAN-5 confirmation change on 4736-105 was rolled back, all of that train's camera ports were bounced at once to force the cameras to pick up the restored gateway. This briefly removed every camera simultaneously and disrupted the Stadler firewall's session/routing state for the camera-to-display path; the cab HMI then showed no CCTV even though the Layer-2 path was healthy (cameras streaming, gateway correct, firewall trunk up). A port-level bounce of the firewall trunk did not recover it; a full restart of the train did. This is recorded as an operational lesson: camera-port operations across a whole train should be staggered, or a firewall/display session refresh planned, to avoid this transient."),

  // 5. RECOMMENDATIONS
  h1("5. Recommendations"),
  num("Adopt the v9 coupler changes fleet-wide via the switch-configuration templates: (M1) flat symmetric coupler port-cost 20,000 on all coupler ports, and (M2) coupler native VLAN 999 with a matching blackhole VLAN 999 defined. Both were validated and persisted in this test. Delivering them through the templates makes them survive a configuration re-push, not only a power cycle."),
  num("Apply the RSTP timer widening (forward-delay 20, then max-age 38) fleet-wide as part of the same change. This was not exercised today (the test was deliberately limited to the coupler-cost and native-VLAN variables) but remains required to give the 2-train composition adequate BPDU-horizon margin, per the June finding."),
  num("Confirm the operational envelope: the validated and supported multi-traction case is up to two coupled 6-car units. Three-unit composition exceeds the RSTP node/diameter limits and is not supported without a different inter-consist mechanism."),
  num("Stadler: note the camera-to-display (VLAN 5 to VLAN 3) firewall session behaviour after a mass camera change (F6); a session refresh path would avoid the need for a full train restart in that situation."),
  num("Nomad / VDS: continue the F4 investigation into the residual coupled-state switch-DHCP behaviour on 4736-117. It is not service-affecting but should be closed out."),

  // 6. CONFIG STATE LEFT ON THE TRAINS
  h1("6. Configuration State Left on the Trains"),
  p("At the end of the test both trains were shut down. The following changes are persisted in switch start-up configuration and will be present on next power-up:"),
  table([3000, 3000, 3026], [
    ["Change", "Scope", "State"],
    ["Coupler port-cost 20,000 (M1)", "8 coupler ports (A1/A3/B1/B3 \u00d7 both trains)", "Persisted (start-up config)"],
    ["Coupler native VLAN 999 (M2)", "8 coupler ports (A1/A3/B1/B3 \u00d7 both trains)", "Persisted (start-up config)"],
    ["VLAN-5 camera gateway", "4736-105, all 18 switches", "Rolled back to own firewall 172.18.194.129 (persisted)"],
    ["vlan7 address (4736-117)", "CCU", "Corrected to 172.19.200.130/17 (persisted)"],
    ["RSTP max-age / forward-delay", "\u2014", "Not changed (recommended via templates, see \u00a75)"],
  ]),
  p(""),
  p("Note: these per-switch changes are persisted against a power cycle. A future OBN configuration push from the current (v8) templates would re-render the switch configuration and revert them \u2014 which is why Recommendation 1 asks for the changes to be carried into the templates (v9)."),

  // 7. APPENDIX - EVIDENCE
  new Paragraph({ children:[ new PageBreak() ] }),
  h1("7. Appendix \u2014 Evidence and Logs"),

  h2("A1 \u2014 RSTP topology after coupling (symmetric cost), 4736-117 active coupler"),
  ...code([
    "nv6-B1-v8-145 (117, active coupler port e0-2):",
    "  Root bridge : 0/a0:59:3a:d0:6c:80      (= 105 D1; 105 is merged-fabric root)",
    "  Root port   : e0-2",
    "  e0-2  128.3  ROOT  FWD  cost 20000  rstp,p2p,adminEdgeOff",
    "",
    "nv6-A1-v8-133 (105, active coupler peer e0-2):",
    "  e0-2  128.3  DESG  FWD  cost 20000  rstp,p2p,adminEdgeOff",
    "",
    "TC / flush count (both trains, 2 samples 90 s apart): 0  and  0   -> converged, no churn",
  ]),

  h2("A2 \u2014 Coupler port-cost: before and after (start-up configuration)"),
  ...code([
    "BEFORE (v8 template, asymmetric):",
    "  117  A1/B3 e0-2 = 144999999    A3/B1 e0-2 = (default)",
    "  105  A1/B3 e0-2 = 132999999    A3/B1 e0-2 = (default)",
    "",
    "AFTER (v9 M1, symmetric, persisted in start-up config):",
    "  117  A1 = port-cost 20000   A3 = port-cost 20000   B1 = port-cost 20000   B3 = port-cost 20000",
    "  105  A1 = port-cost 20000   A3 = port-cost 20000   B1 = port-cost 20000   B3 = port-cost 20000",
  ]),

  h2("A3 \u2014 Coupler native VLAN: before and after (start-up configuration)"),
  ...code([
    "BEFORE:  e0-2  up  native 0001  prune allow 5,15        (native VLAN 1 = the fault)",
    "AFTER :  e0-2  up  native 0999  prune allow 5,15        (native VLAN 999, allowed set unchanged)",
    "",
    "Verified in start-up config on all 8 coupler ports, both trains, with cost AND native together:",
    "  A1: [port-cost 20000] [native vlan 999]",
    "  A3: [port-cost 20000] [native vlan 999]",
    "  B1: [port-cost 20000] [native vlan 999]",
    "  B3: [port-cost 20000] [native vlan 999]",
  ]),

  h2("A4 \u2014 Switch-DHCP failure with native VLAN 1 (CCU DHCP server log, 4736-117)"),
  ...code([
    "10:39:56  DHCPOFFER   on 10.179.32.202 to a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:40:04  DHCPDISCOVER from a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:40:04  DHCPOFFER   on 10.179.32.202 to a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:40:17  DHCPDISCOVER from a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:40:17  DHCPOFFER   on 10.179.32.202 to a0:59:3a:d0:79:60 (nv6-A1-v8-145) via vlan100",
    "10:41:20  DHCPDISCOVER from a0:59:3a:d0:76:e0 (nv6-D1-v8-145) via vlan100",
    "10:41:22  DHCPOFFER   on 10.179.32.201 to a0:59:3a:d0:76:e0 (nv6-D1-v8-145) via vlan100",
    "  Pattern: DISCOVER -> OFFER -> (no REQUEST, no ACK) -> DISCOVER again, looping.",
  ]),

  h2("A5 \u2014 Native-VLAN-1 cross-train bridge (VLAN-1 MAC table, 4736-117 active coupler)"),
  ...code([
    "show mac-address vlan 1  (count, learned via coupler port e0-2):",
    "  Before M2:  57 MACs  (incl. 4736-105 switch MACs d0:2c.. d0:2e.. d0:34.. d0:38.. learned via e0-2)",
    "  After  M2:  39 -> 10  (foreign 105 entries age out; cross-train VLAN-1 bridge closed)",
    "",
    "Sample foreign (105-side) entries seen on 117 VLAN-1 before the fix:",
    "  a0:59:3a:d0:2c:e0  Dynamic  e0-2",
    "  a0:59:3a:d0:34:e0  Dynamic  e0-2",
    "  a0:59:3a:d0:38:00  Dynamic  e0-2",
  ]),

  h2("A6 \u2014 Switch recovery on decouple (the confirming test)"),
  ...code([
    "4736-117 management-lease count:",
    "  Coupled (native VLAN 1):   9 / 18",
    "  ~1 minute after decouple: 18 / 18",
    "Repeated consistently across the day -> the loss is coupled-state-specific, not switch power.",
  ]),

  h2("A7 \u2014 Cold-boot result with full v9 (M1 + M2 persisted)"),
  ...code([
    "After restart, both trains coupled:",
    "  4736-105: 18 / 18 switches, single root, no churn  -> clean cold-boot convergence.",
    "  4736-117: v9 config rendered from start-up (B1 e0-2 native 999 + cost 20000);",
    "            VLAN-1 cross-train leak absent; the switches that came up leased cleanly;",
    "            residual F4 (about half not completing a lease while coupled) still present.",
  ]),

  h2("A8 \u2014 CCTV path health while coupled (4736-105 cameras)"),
  ...code([
    "VLAN-5 camera ports up across coaches (A1/C1/D1/F1): 5/5 each.",
    "Camera video rate (e1-0, representative): 4.1 - 7.1 Mbps  (healthy stream).",
    "Stadler firewall MAC learned on VLAN 5; A3 e1-4 firewall trunk up, 1G full,",
    "carrying VLANs 2,3,5,6,7,8,9,12,15.",
  ]),

  h2("A9 \u2014 Attachment list"),
  p("The following raw evidence accompanies this report:"),
  bullet("EVIDENCE_raw_harvests_2026-06-30.txt \u2014 consolidated raw harvests: device inventory; vlan7 correction; coupler port-cost before/after; RSTP topology and TC-count samples; VLAN-5 forwarding-table stability; the CCU DHCP-server log showing the Discover-to-Offer loop; the VLAN-1 cross-train MAC table (root-cause proof); the native-VLAN-999 fix and verification; decouple-recovery and cold-boot results; and the final persisted configuration state."),
  bullet("Full switch spanning-tree, MAC-address-table and interface-counter dumps, CCU DHCP logs and management-VLAN packet captures are retained and available on request."),

  p(""),
  new Paragraph({ spacing:{ before: 200 }, children:[ new TextRun({ text: "Prepared by Abbas Rizvi, Nomad Digital \u2014 2026-06-30.", italics: true, size: 18, color: "555555" }) ] }),
];

const doc = new Document({
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style:{ paragraph:{ indent:{ left: 360, hanging: 260 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style:{ paragraph:{ indent:{ left: 360, hanging: 260 } } } }] },
  ]},
  styles: { paragraphStyles: [
    { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run:{ size: 28, bold: true, color: "1F4E79" } },
    { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run:{ size: 23, bold: true, color: "2E74B5" } },
  ]},
  sections: [{
    properties: { page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    headers: { default: new Header({ children:[ new Paragraph({ alignment: AlignmentType.RIGHT, children:[ new TextRun({ text: "Nomad Digital \u2014 \u00d6BB DOSTO Coupled-Train Test, 2026-06-30", size: 16, color: "888888" }) ] }) ] }) },
    footers: { default: new Footer({ children:[ new Paragraph({ alignment: AlignmentType.CENTER, children:[ new TextRun({ text: "Page ", size: 16, color: "888888" }), new TextRun({ children:[ PageNumber.CURRENT ], size: 16, color: "888888" }), new TextRun({ text: " \u2014 Confidential", size: 16, color: "888888" }) ] }) ] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = process.argv[2] || "DOSTO_Coupled_Train_Test_Report_2026-06-30_v1.0.docx";
  fs.writeFileSync(out, buf);
  console.log("WROTE " + out + " (" + buf.length + " bytes)");
});
