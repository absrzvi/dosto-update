---
type: guide
title: OKF organisation plan (superseded)
description: First plan — applying OKF additively to the markdown corpus. Superseded by the component-oriented KB.
project: dosto-neu
tags: [design-history, planning, meta]
timestamp: 2026-07-04T00:00:00Z
---

# Plan: Organise the DOSTO knowledge corpus with OKF v0.1

**Author:** Abbas Rizvi
**Date:** 2026-07-04
**Method:** [Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
**Status:** Proposed — no files changed yet.

---

## 0. Decisions locked in (from scoping)

| Question | Decision |
|---|---|
| What does OKF apply to | **Knowledge layer only** — the markdown docs. Binaries, scripts, PDFs, `.docx`/`.xlsx`, `node_modules`, SSH keys stay exactly where they are. |
| Which files | **This repo only** (`dosto-troubleshooting/`). Not the whole `Documents` folder. |
| Risk posture | **Non-destructive / additive.** Nothing referenced by path gets moved or renamed. We *add* frontmatter + `index.md`/`log.md`; we do not restructure the tree. |

---

## 1. What OKF actually is (and what it is NOT)

OKF is **not a filesystem-organisation scheme.** It is a *knowledge metadata format*: a directory of markdown files, each carrying a small YAML frontmatter block, readable by both humans and AI agents, version-controllable and diffable. There is **no schema registry, no central authority, no required tooling.**

**Consequences for "organise ALL my files":**

- You **cannot** put OKF frontmatter on `.tar.gz`, `.docx`, `.xlsx`, `.pptx`, `.ppk`, `openssh`, `.py`, `.js`, or `.html`. OKF governs `.md` only.
- Therefore "organise all files with OKF" resolves to: **make the markdown corpus a conformant OKF bundle, and let that bundle's `index.md` files *point at* the non-markdown assets** (PDFs, spreadsheets, scripts) as `resource:` links. The binaries stay put; the knowledge layer describes them.

**The one hard conformance rule** (SPEC §9): every non-reserved `.md` file must have parseable YAML frontmatter with a **non-empty `type:` field.** Everything else (`title`, `description`, `tags`, `timestamp`, `index.md`, `log.md`, cross-links) is *soft guidance* — a consumer must not reject the bundle for missing any of it.

---

## 2. Scope: what's in, what's out

**Corpus is ~322 `.md` files on disk, but most are noise.** Filter:

### OUT — never touch (not knowledge, or not ours)
- `node_modules/` — dependency tree.
- `.git/` — VCS internals.
- `.claude/worktrees/*` — three throwaway git-worktree clones of the whole repo. Ignore entirely; they duplicate ~200 of the 322.
- `.tmp/gitlab-repos/*` — transient upstream checkouts (`obn`, template repos, their `.venv` site-packages LICENSE.md files). Not our knowledge.
- `.archive/` — already-retired scratch. Leave as-is (it's *already* the archive).

### OUT of OKF frontmatter, but referenced BY it
Non-markdown assets that the bundle's index files should link to as `resource:`:
- Schema/allocation PDFs under `docs/`, `train-ip-allocation-commission/`.
- `.docx` deliverables (SDD, BID, tunnel template), `.xlsx` (fleet control sheet, phase plan, PROJECT-STATUS), `.pptx`, `dashboard.html`.
- `scripts/*.py`, `*.js`, `*.sh`.
- Credentials (`openssh`, `pvt_key.ppk`) — **linked, never described in detail; never committed content.**

### IN — the OKF knowledge bundle (~90–100 real docs)
Grouped by existing cluster (we keep the clusters — additive):

| Existing dir | Role | OKF `type:` candidates |
|---|---|---|
| root `*.md` (CLAUDE, runbook, checklist, handoffs, iperf3, fleet-journal, PROJECT-STATUS) | project spine | `playbook`, `runbook`, `checklist`, `handoff`, `status`, `journal` |
| `findings/` | investigations & RCAs | `finding`, `rca`, `analysis`, `plan`, `report`, `spec`, `runbook`, `email`, `tasklist` |
| `rd-handoff/` | upstream bug handoffs | `bug-report`, `companion-fix`, `plan` |
| `reports/` | deliverables | `report` (sub-typed customer/internal/stadler via `tags`) |
| `OEBB-251/` | bench enablement | `plan`, `reference` |
| `design freeze/` | SDD correspondence | `correspondence`, `reference` |
| `train-ip-allocation-commission/extracted/` | per-train extracts | `train-data`, `topology` |
| `.claude/skills`, `.claude/contracts`, `.claude/agents` | **operational config, NOT knowledge** | *see §6 — recommend EXCLUDE* |

---

## 3. Target structure (additive — no moves)

We do **not** create a new top-level tree. The repo root *becomes* the OKF bundle root. We overlay OKF artifacts into the existing directories:

```
dosto-troubleshooting/                 ← bundle root
├── index.md            (NEW)  okf_version: "0.1"; top-level directory listing
├── log.md              (NEW)  change history of the knowledge base itself
├── CLAUDE.md           (+frontmatter)  type: playbook
├── troubleshooting-runbook.md (+fm)    type: runbook
├── train-login-checklist.md   (+fm)    type: checklist
├── fleet-journal.md    (+fm)           type: journal
├── PROJECT-STATUS.md   (+fm)           type: status
├── handoff*.md         (+fm)           type: handoff
├── findings/
│   ├── index.md        (NEW)  lists every finding w/ its description
│   ├── log.md          (NEW, optional)
│   └── *.md            (+fm each)
├── rd-handoff/
│   ├── README.md → keep, OR add index.md alongside (see §5)
│   └── bug-*.md, companion-*.md  (+fm each)  type: bug-report / companion-fix
├── reports/
│   ├── index.md        (NEW)
│   └── {customer,internal,stadler}/*.md (+fm each)  type: report; tags: [customer|internal|stadler]
├── OEBB-251/  · design freeze/  · train-ip-allocation-commission/extracted/
│   └── (+fm each; add index.md per dir)
└── … binaries/scripts/PDFs unchanged, referenced from index.md files …
```

**Nothing moves. Nothing is renamed.** Every `git mv` is avoided precisely because CLAUDE.md, the 20 skills, and the scripts reference these paths literally (e.g. `openssh`, `fleet-status.md`, `scripts/fix_obn.py`, `.claude/sample1.txt`). See §7.

---

## 4. Frontmatter convention for this corpus

Minimum conformant block (only `type` is required):

```yaml
---
type: finding
title: OBN report BFS infinite-loop RCA
description: Root-cause of the number_coaches BFS hang; one-line guard fix.
tags: [obn, rca, bug10]
timestamp: 2026-06-02T00:00:00Z
---
```

**Rules we adopt for consistency (soft, but house style):**
1. `type` — lower-kebab, from the controlled list in §2. Descriptive, self-explanatory (SPEC requirement).
2. `title` — human display name; if omitted, consumers derive from filename (many of our filenames are already good: `RCA_obn_report_bfs_infinite_loop_2026-06-02`).
3. `description` — one sentence, reused verbatim in the parent `index.md` entry (SPEC §6 recommends this).
4. `tags` — cross-cutting: fleet (`4736`, `4734`), subsystem (`obn`, `vlan7`, `zabbix`, `rstp`), doc-nature (`rca`, `plan`, `email`).
5. `timestamp` — ISO-8601. **Derive from the date already in the filename** where present (most `findings/` files end `_YYYY-MM-DD`), else file mtime.
6. `resource:` — for docs that *are about* a specific binary/PDF/ticket, point at it: `resource: /docs/ND-DEL-OBB-035-IPA-133.pdf` or an external Jira URL.

**Cross-links:** convert ad-hoc `[x](../foo.md)` to **bundle-absolute** `[x](/findings/foo.md)` (SPEC "recommended" form — stable under future moves). Broken links are explicitly tolerated by the spec, so this is best-effort, not blocking.

---

## 5. `index.md` and `log.md` (reserved files)

- **`index.md`** — no frontmatter *except* the root one may carry `okf_version: "0.1"`. Body is grouped bulleted links: `* [Title](rel-url) - description`. One per meaningful directory (`root`, `findings/`, `rd-handoff/`, `reports/`, `OEBB-251/`).
  - **Collision note:** `rd-handoff/`, `OEBB-251/nv2-template-src/`, `findings/TRIAG-8585-patches/`, and several others already have `README.md`. OKF's reserved index file is `index.md`, not `README.md`. Options: (a) add `index.md` *alongside* the README (README stays for GitHub rendering); (b) leave READMEs as ordinary concept docs with `type: reference`. **Recommend (a)** — additive, no loss.
- **`log.md`** — ISO-8601 `## YYYY-MM-DD` headings, `* **Creation/Update**: …` bullets. One at root tracking the knowledge base's own evolution. Optional per-dir.

---

## 6. Open recommendation: exclude `.claude/` from the bundle

The 20 `SKILL.md` files, 5 contracts, and 2 agent defs under `.claude/` are **operational configuration consumed by the Claude Code harness**, not human knowledge artifacts. They already have their own frontmatter schema (skill `name`/`description`) that OKF's `type:` requirement would collide with or clutter.

**Recommendation:** leave `.claude/` **out of the OKF bundle.** If you want them catalogued, reference them from the root `index.md` under a "Tooling" heading as `resource:` links rather than rewriting their frontmatter. *(Decision needed from you — flagged in §9.)*

---

## 7. Reference-integrity guardrails (why additive is safe)

Before writing any frontmatter, we confirm no consumer breaks:

1. **Frontmatter is invisible to path references.** Adding a YAML block to the *top* of `CLAUDE.md` or `fleet-status.md` does not change its path, so every `[fleet-status.md](fleet-status.md)` link and every `scripts/fleet_status_lookup.py` read still works.
   - ⚠️ **One real risk:** any script that *parses* these `.md` files positionally (e.g. `fleet_status_lookup.py` parsing the fleet-status table, or `regenerate_bootstrap.py` embedding CLAUDE.md verbatim). Adding frontmatter shifts line numbers and prepends YAML. **Action:** audit `scripts/*.py` and the bootstrap regenerator for any file that reads these `.md`s, and **exclude those specific files** (`fleet-status.md`, `CLAUDE.md`, anything embedded in `BOOTSTRAP_DOSTO_v1.md`) from frontmatter injection, OR make the parser skip a leading `---…---` block. This is the single most important pre-flight check.
2. **New files only add.** `index.md`/`log.md` are new paths — nothing references them yet, so they can't break anything.
3. **No `git mv`.** Zero rename churn in the diff.

---

## 8. Execution phases (when you approve)

**Phase A — Pre-flight audit (read-only, ~15 min)**
- Grep `scripts/` + `BOOTSTRAP_DOSTO_v1.md` + `regenerate_bootstrap.py` for every `.md` filename that is *parsed or embedded* rather than merely linked. Produce an **exclusion list** (files that must NOT get frontmatter, or whose parser must tolerate it).
- Confirm the final IN list (§2) file-by-file.

**Phase B — Frontmatter injection (mechanical, batchable)**
- For each IN file not on the exclusion list: prepend a `---…---` block. `type` mandatory; `title`/`description`/`tags`/`timestamp` derived from filename + first heading + git log date.
- Do it in cluster batches (`findings/` first — biggest, most uniform), review the diff per batch.

**Phase C — Index + log generation**
- Generate `index.md` per directory from the freshly-written `description` fields (script reads each file's frontmatter, emits the grouped bullet list).
- Root `index.md` gets `okf_version: "0.1"` and a "Tooling / assets" section linking the non-md resources.
- Seed root `log.md` with a `## 2026-07-04` "Creation" entry.

**Phase D — Cross-link normalisation (optional, best-effort)**
- Rewrite intra-bundle links to bundle-absolute `/path` form. Skip if time-boxed — spec tolerates the relative form and broken links.

**Phase E — Conformance check**
- Tiny validator script: every non-reserved `.md` in the bundle has parseable frontmatter + non-empty `type`. Report violations. (This is the *only* thing that determines OKF-conformance.)

---

## 9. Decisions I still need from you

1. **`.claude/` in or out of the bundle?** Recommend OUT (§6).
2. **Which clusters to include in v1?** Recommend: root spine + `findings/` + `rd-handoff/` + `reports/` first (the highest-value, most-referenced knowledge). Add `OEBB-251/`, `design freeze/`, `train-ip-allocation-commission/extracted/` in v2. Or all at once?
3. **Frontmatter on the load-bearing files** (`fleet-status.md`, `CLAUDE.md`, `BOOTSTRAP_DOSTO_v1.md`)? Recommend: **exclude until Phase A proves the parsers tolerate a leading YAML block.** These are the ones that can actually break tooling.

---

## 10. What this buys you

- A **conformant OKF bundle** an agent (or teammate) can traverse from `index.md` → concept, with typed, described, tagged docs — without moving a single existing file or breaking a single script.
- Non-md assets (PDFs, docx, scripts) remain in place but become **discoverable through the knowledge layer** via `resource:` links.
- Fully **reversible**: every change is either a prepended YAML block or a brand-new `index.md`/`log.md`. `git revert` restores the pre-OKF state exactly.
```
