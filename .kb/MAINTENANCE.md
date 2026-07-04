---
type: guide
title: Maintaining this knowledge base
description: How to add, update, regenerate, and validate .kb/ docs — format, type vocabulary, scripts, and the conformance check.
project: dosto-neu
tags: [meta, maintenance, okf, contributing]
timestamp: 2026-07-04T00:00:00Z
---

# Maintaining the `.kb/` knowledge base

This KB follows **OKF v0.1**. The one hard rule: every non-reserved `.md` file has a parseable
YAML frontmatter block with a **non-empty `type:`**. Everything else is soft. Keep it that way and
the bundle stays conformant.

## Golden rules

1. **Additive only.** `.kb/` never moves, renames, or rewrites a file outside `.kb/`. Several
   scripts (`scripts/fleet_status_lookup.py`, `scripts/regenerate_bootstrap.py`, others) parse
   `fleet-status.md` / `CLAUDE.md` positionally — injecting content into them breaks parsing.
   The KB **links** to those files; it never edits them.
2. **`fleet-status.md` is the live source of truth.** `.kb/fleet/*` records hold *stable identity
   + topology* and link back. Never write live commissioning state into a KB record.
3. **A newly-proven dead end is the highest-value addition.** When something is tried and
   disproven on live hardware, add it to the relevant `# Proven dead ends` section — that is the
   whole point of this KB (stop the next agent repeating it).
4. **Generic-core, DOSTO-in-examples.** Component/topic bodies stay generic so they're portable;
   project-specific values go in a marked `# EXAMPLE (DOSTO NEU)` block. This lets a portable KB
   be lifted out later.

## Doc format

```yaml
---
type: <see vocabulary below>          # REQUIRED, non-empty
title: <human title>
description: <one sentence — reused verbatim in the parent index.md entry>
project: dosto-neu
tags: [<component/topic/fleet/subsystem tags>]
maturity: field-validated | reported | draft
timestamp: <ISO-8601>
# plus type-specific keys: component, vendor, train, fzg, box_id, ccu_ip,
# zabbix_host_group, series, schema, ticket, status, resource
---
```
Body: generic-core prose. Component & topic docs MUST include a `# Proven dead ends — do NOT
repeat these` section and a `# EXAMPLE (DOSTO NEU)` block where project specifics exist. End with
`# Related` (bundle-absolute `/.kb/...` links) and `# Citations` (tie each fact to the session/doc
that proved it).

**Cross-links:** use bundle-absolute form — `[title](` + `/.kb/path/to/doc.md` + `)` — stable if docs move.
Broken links are tolerated by OKF, but the conformance check below flags them so we can fix real ones.

## `type:` vocabulary (current)

| type | used for |
|---|---|
| `component-knowledge` | device behaviour (switch / AP / CCU-OBN) |
| `topic` | cross-cutting subject (vlan7, RSTP, Zabbix, Fzg-ID, fv5/fv6 topology) |
| `train-record` | a per-train identity/topology record under `fleet/` |
| `ticket` | a Jira/TRIAG/OEBB/SA ticket stub |
| `deliverable-ref` | pointer-stub to a `.docx`/`.xlsx` deliverable (`resource:` link) |
| `asset-index` | per-train index of allocation PDFs + switch cfgs under `assets/` |
| `guide` | meta docs (HOW-TO-USE, this file) |
| `index` / `fleet-index` / `component-index` | directory `index.md` files (any non-empty type is fine) |

Types are not registered centrally — a new descriptive one is fine, just add it here.

## Adding a doc

1. Create the `.md` with the frontmatter above under the right category dir.
2. Add a bullet to that directory's `index.md`: `* [Title](file.md) - <the description>`.
3. Add `# Related` links both ways where it helps navigation.
4. Append a line to [`log.md`](log.md) under today's `## YYYY-MM-DD` heading.
5. Run the conformance check (below).

## Regenerating the generated docs

Some docs are **generated** — edit the generator + source, not the output:

- **Fleet records** (`fleet/*.md`): `python scripts/gen_kb_fleet_records.py`
  Reads `fleet-status.md` (authoritative Fzg + CCU IP), computes box-id (= CCU-IP 3rd octet),
  Zabbix host (`50_6<box-id>`), vlan7 IPs, and links per-series topology. **Preserves the 8
  hand-written rich records** (listed in `RICH_TRAINS` in the script) — do not clobber those.
- **fv5/fv6 topology** (`_shared/{fv5,fv6}-topology.md`):
  `python scripts/extract_fv_topology.py`
  Parses the IP-Port-Allocation PDFs' `e0-0`/`e0-1` FIS-Switch rows (authoritative backbone; the
  raw `.cfg` descriptions are asymmetric — do not trust them).
- **Per-train asset stubs** (`assets/*.md`): were generated inline from the
  `train-ip-allocation-commission/` tree (one stub per train folder). Re-run that generation if the
  allocation tree changes.

## Conformance check (run before committing)

```bash
python .kb/check_conformance.py
```
Passes when every non-reserved `.md` has parseable frontmatter + non-empty `type`, and every
bundle-absolute link resolves on disk. Fix real broken links; genuinely-tolerable ones (per OKF)
can stay, but prefer zero.

# Related

- [HOW-TO-USE](HOW-TO-USE.md) — reader's orientation
- [Root index](index.md)
- [Change log](log.md)
- Project playbook: [CLAUDE.md](/CLAUDE.md)
