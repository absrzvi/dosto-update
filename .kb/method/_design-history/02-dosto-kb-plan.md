---
type: guide
title: DOSTO KB build plan
description: Plan of record for the project-specific KB build (structure, ingestion, generators).
project: dosto-neu
tags: [design-history, planning, meta]
timestamp: 2026-07-04T00:00:00Z
---

# Plan: DOSTO NEU project knowledge base (OKF v0.1, project-specific)

**Author:** Abbas Rizvi · **Date:** 2026-07-04 · **Method:** [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
**Decision:** DOSTO-specific build, hybrid-extractable (generic component bodies so a portable KB can be lifted out later). Folder-level stubs for per-train PDF/cfg sets; deep stubs only for high-value docs.

---

## 1. Location & safety

- Bundle root: **`.kb/`** at repo root. Self-contained → copy-outable; version-controlled with the source.
- **Additive only.** The KB *links to* existing files; it never moves, renames, or injects frontmatter into them.
- **Load-bearing files stay untouched.** `fleet-status.md` is parsed positionally by `scripts/fleet_status_lookup.py` (and 9 other scripts read it / `CLAUDE.md`). The KB references these via `resource:` links only. Confirmed 2026-07-04.

## 2. Structure

```
.kb/
├── index.md                     okf_version:"0.1", project:dosto-neu — top nav
├── log.md                       KB's own change history
├── HOW-TO-USE.md                entry doc for the consuming agent
├── components/                  generic-core device knowledge (portable-extractable)
│   ├── vds-consist-switch/      cli-and-management ✓, l2-counters-rstp, firmware-flashing, snmp-traps
│   ├── westermo-ap/             factory-vs-nomad-config, luci-http-push, firmware-activation, factory-recovery
│   └── nomad-connect-obn/       bug-suite, discover-report-update, ndsu-chroot-persistence,
│                                tftp-conntrack-helper, publish-to-puppet-pipeline
├── fleet/                       one doc per commissioned train (Fzg, CCU IP, its cfgs/PDFs/reports/tickets)
│   └── index.md + 4736-105.md …
├── topics/                      cross-cutting: vlan7-addressing, coupled-rstp-tc-storm,
│                                zabbix-nms-model, fzg-id-two-namespaces, l2-health-methodology, lldp-cabling
├── deliverables/               resource-stubs → SDD .docx, control sheet .xlsx, health reports, dashboards
├── tickets/                     RD-*, TRIAG-*, OEBB-* — status + linked evidence
└── assets/                      folder-level stubs for train-ip-allocation-commission/** (PDF+cfg per train)
```

## 3. Frontmatter (only `type:` required by OKF)

```yaml
type: <component-knowledge|train-record|topic|deliverable-ref|ticket|asset-index>
title: … · description: … (reused verbatim in parent index.md)
project: dosto-neu
component / fzg / train / ticket: <entity key where relevant>
resource: /path/to/real-file            # for stubs — one hop to the binary
tags: [4736, vlan7, obn, rca, …]
maturity: field-validated | reported | draft
timestamp: <ISO-8601, from filename date or mtime>
```

## 4. The two load-bearing conventions

- **⛔ Proven dead ends** — every component/topic doc carries an explicit "what we tried that did NOT work" list (with train IDs inline). This is the anti-repeat payload — the whole point.
- **resource-stubs** — each non-md asset gets a small `.md`: frontmatter + 1-para summary + extracted key facts + `resource:` link. Agent reads the stub, opens the binary only if needed.

## 5. Non-md ingestion depth (agreed)

| Source | Count | Treatment |
|---|---|---|
| `train-ip-allocation-commission/**` PDFs + cfgs | 211 PDF / 74 cfg | **Folder-level**: one `assets/<train>.md` per train summarising its PDF/cfg set + resource links. Not one stub per file. |
| SDD / BID / tunnel-arch `.docx` | few | **Deep** stub each (section map, supersedes, sign-off). |
| Fleet control sheet, phase plan, PROJECT-STATUS `.xlsx` | few | **Deep** stub each (what each sheet holds). |
| `fix_obn*`, `lldp_check*`, report/scan generators | ~93 scripts | **Deep** for the fix_obn suite (ties to bug docs); light index for the rest. |
| customer/internal/stadler reports, dashboards, findings JSON | many | Light stubs, grouped by index.md. |
| `memory/` project facts | ~90 | Folded into the relevant component/topic/fleet doc as sourced facts. |

## 6. Build order

1. `.kb/` skeleton + root `index.md`/`log.md` + `HOW-TO-USE.md`.
2. **components/** — port the 3 device categories (switch doc already drafted; move + expand). Generic-core.
3. **topics/** — vlan7, coupled-rstp, zabbix, fzg-id, l2-health (richest memory-backed material).
4. **fleet/** — start with commissioned trains that have real history (4736-105, 4734-119, box1-t47…).
5. **tickets/** + **deliverables/** deep stubs.
6. **assets/** folder-level train stubs (scripted from the directory tree).
7. Conformance pass: every non-reserved `.md` has parseable frontmatter + non-empty `type`.

## 7. Reversible

Every change is a new file under `.kb/`. Nothing outside `.kb/` is modified. `rm -rf .kb` or `git revert` restores exactly.
