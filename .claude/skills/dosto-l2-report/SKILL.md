---
name: dosto-l2-report
description: Generate a customer-ready Word docx report from a DOSTO L2 health check. Takes a findings.json produced by the dosto-l2-health skill (plus optional context like the train's IPv4 schema PDF and customer name) and writes a fully-formatted, branded report ready for review and tracked-changes editing. Use whenever the user asks for "a report from this health check", "a report for ÖBB", "/dosto-l2-report", "write up the train health check as a docx", or after a dosto-l2-health run completes and the user wants to share the result with a customer or with a colleague who will review it. Don't draft the report by hand — this skill encodes the standard report layout, branding, and Nomad/ÖBB review-friendly conventions so the output is consistent across trains.
---

# DOSTO L2 Health Check Report Generator

This skill turns a structured `findings.json` (produced by the `dosto-l2-health` skill) into a polished, customer-ready Word document. The companion playbook is in the project's `CLAUDE.md`.

## When you use this skill

Right after a health check, when the user wants a deliverable for a customer (typically ÖBB, but could be any operator) or for internal review with tracked-changes / comments. Typical triggers:

- "Generate the ÖBB report for that health check"
- "Turn this into a docx I can send to the customer"
- "/dosto-l2-report"
- "Write up Fzg. 146's results"

## What you produce

A single `.docx` file at a path the user specifies (or the project root by default). The document is structured for collaborative review: a revision history table, an approvals table, and an open reviewer-notes table at the end. Reviewers should turn on Track Changes in Word.

## Inputs you need

| Input | Required? | Notes |
|-------|-----------|-------|
| Path to `findings.json` | Yes | The structured output of `dosto-l2-health` Step 9. |
| Customer name | Yes | E.g., "ÖBB", "SBB", "Stadler". Defaults to "ÖBB" if unspecified, since this is the most common case in the project. |
| Trainset Fzg. ID and Fzg. Nr. | Yes | E.g., "146" and "4736-118". If `findings.json` doesn't carry these (it doesn't yet), ask. |
| Output path | Optional | Defaults to `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/<Customer>_Fzg<ID>_Network_Health_Check_Report_v1.0.docx` |
| IPv4 schema PDF | Optional | If you have it, mention it in the references section. The report works without it. |
| Author name + organisation | Optional | Defaults to "Abbas Rizvi, Nomad Digital". |

If anything required is missing, ask the user before generating. Don't guess customer names or Fzg. numbers — getting them wrong is embarrassing in a customer-facing document.

## How to run

A single Node.js script does the generation. Pass a small JSON config on the command line; the script merges it with defaults and writes the docx.

```bash
node scripts/generate_report.js \
  --findings <path-to-findings.json> \
  --customer "ÖBB" \
  --fzg-id 146 \
  --fzg-nr 4736-118 \
  --consist-size 6-car \
  --output "C:/path/to/output.docx" \
  [--author "Abbas Rizvi"] \
  [--organisation "Nomad Digital"] \
  [--schema-pdf-name "ND-DEL-OBB-035-IPA-146_NV_6Teiler.pdf"]
```

Required first-time setup (one command, persists):

```bash
npm install -g docx
```

## What the generated report contains

The script renders a 6-section + appendices layout:

1. **Title page** — branding, customer name, trainset metadata
2. **Document control** — revision history, approvals (with blank rows for reviewers to sign off)
3. **Executive summary** — headline verdict + bullet findings
4. **Scope and methodology** — what was checked, the 8-phase methodology, tools used
5. **Architecture overview** — topology, schema-to-IP map, VLAN plan, routing notes
6. **Detailed findings** — one subsection per check (switch inventory, inter-coach trunks, RSTP, per-port error scan, Stadler trunks, ZFR, front couplers, throughput, end-to-end FW probe)
7. **Risk assessment & recommendations** — risk table, recommendations, open questions for the customer
8. **Appendices** — sample CLI output, VLAN config sample, glossary, references, reviewer notes table

The script picks up findings from the JSON for the dynamic sections (counts, verdict, anomalies). Static content (methodology description, glossary, recommendations boilerplate) is templated in the script.

## Design principles for the document

- **A4 paper, ~2 cm margins.** European convention; avoids the awkward "this looks American" feel for ÖBB readers.
- **Sober blue accent colour (#1F4E79 / #2E75B6).** Matches Nomad Digital corporate style without screaming brand.
- **Colour-coded result cells** — green for PASS, yellow for "needs customer confirmation", orange for "out of scope". Doesn't rely on colour alone — every cell also has a clear word.
- **Tables, not paragraphs, for findings.** Reviewers can copy a row, edit one column, comment per cell.
- **Glossary in German + English.** Bridges the language gap for ÖBB engineers (DOSTO terminology is German).
- **Open reviewer-notes table** at the end. If a colleague isn't comfortable with Word's Track Changes, they can still log feedback in a structured way.
- **Footer says "Confidential — Draft for review".** Stays until someone explicitly bumps the version to 1.0 final.

## How to interpret the JSON (so the report is accurate)

The `findings.json` schema (produced by `dosto-l2-health` step 9) is roughly:

```json
{
  "generated_at": "2026-05-02T17:12:00Z",
  "ccu_ip": "10.179.8.1",
  "vds_switches": {
    "count": 18,
    "ips": ["10.179.8.178", ...],
    "consist_size": "6-car",
    "firmware": {"10.179.8.178": "Firmware Version: 7.4.2 Build Release: 77411", ...}
  },
  "westermo_radio_count": 24,
  "stp": {"root": "32768/a0:59:3a:d0:3a:40", "agreement": "18/18", "consistent": true},
  "trunks_up": {"e0-0": "18/18", "e0-1": "16/18", "e0-4": "18/18"},
  "port_anomalies": [{"switch": "10.179.8.182", "port": "e1-8", "rx_errors": 1, "crc": 0, "carrier_false": 0}],
  "stadler_fw": {"arp": "reachable", "tcp_22": "open", "tcp_80": "open", "vlan7_rx_errors": "0", "icmp_note": "..."},
  "verdict": {"overall": "HEALTHY", "port_anomaly_count": 1, "notes": "..."}
}
```

Headline rules in the report:

- **Verdict** comes straight from `verdict.overall`. If it's `HEALTHY`, the green executive summary box wins. Otherwise, `NEEDS_REVIEW` triggers the yellow box and the body text shifts to "the following items require follow-up:".
- **Trunk anomalies**: the e0-1 mismatch (e.g. 16/18 instead of 18/18) is expected — those are end-of-train switches. The report notes this explicitly so the customer doesn't read it as a fault.
- **Port anomalies**: if zero, the section reads "all ports clean". If one or two minor (single-digit RX errors over millions of packets), the section reads "noise, not actionable" — but lists them anyway for transparency.
- **TCP probes succeed AND ICMP fails**: standard FW-filtering case; describe as healthy, explain that ICMP being filtered is by design.

## Pitfalls

- **`vds_switches.count` must be the DISCOVERED count (from `dhcp-lease-list` via `dosto-l2-health`), never OBN's `obn report`/`validate` count.** OBN silently drops switches from its report when one is cold-bypassed (a mislabel dead-ends its coach-numbering walk and everything downstream is deleted — observed 2-of-12 on bench box1-t122, 2026-07-04). If a `findings.json` was ever populated from OBN's report instead of the DHCP sweep, the headline count can be a false low and the report will understate the consist. Cross-check against `dosto-device-discovery`'s discovered count; if they disagree, a bypass/mislabel is eating the difference — see CLAUDE.md pitfall and `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`.
- **Don't include the switch admin password in the report.** Ever. The methodology section can mention "admin SSH access", but never embed credentials.
- **Don't include personal email addresses or IPs that aren't part of the agreed deliverable.** The CCU IP and switch IPs are fine; user emails are not.
- **Verify Fzg. numbers.** A typo here annoys customer engineers immediately. Read it back to the user before generating if you're unsure.
- **Validate the docx after generation.** Run `python -c "import zipfile, xml.etree.ElementTree as ET; z=zipfile.ZipFile('<path>'); [ET.fromstring(z.read(n)) for n in z.namelist() if n.endswith('.xml')]; print('OK')"` to confirm the XML is well-formed. The generator script already produces valid output, but a quick sanity check is cheap insurance.

## When the user asks for a different customer or trainset

The skill is generic. Customer name (ÖBB / SBB / Deutsche Bahn / Stadler / etc.) is a parameter. The report layout doesn't change. Only the title page, the customer name in headers/footers, and the references section adapt. If a different customer wants a fundamentally different layout, that's a separate skill — not this one.

## Updating the report

The generated docx has a Revision History table. When the user says "update the report" later (e.g., after a re-check), pass the new `findings.json` and bump the version. Don't try to merge findings across runs — generate a fresh document per run, link them via the revision history.
