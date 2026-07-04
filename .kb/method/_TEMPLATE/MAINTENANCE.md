---
type: guide
title: Maintaining this knowledge base
description: How to add, validate, and grow the KB — format, type vocabulary, conventions, conformance.
tags: [meta, maintenance, okf]
timestamp: <YYYY-MM-DDT00:00:00Z>
---

# Maintaining this knowledge base

Follows **OKF v0.1**. One hard rule: every non-reserved `.md` file has parseable YAML frontmatter
with a **non-empty `type:`**. Everything else is soft guidance.

## Golden rules

1. **Additive only.** The KB never moves or rewrites files outside itself — it *links* to them.
   (Some source files may be parsed positionally by scripts; injecting into them breaks parsing.)
2. **Keep one source of truth for live state.** If the project has a live-status file, the KB links
   to it and never duplicates volatile state.
3. **A newly-proven dead end is the highest-value addition.** Record it the moment you disprove
   something.
4. **Generic-core, specifics-in-examples.** Write bodies generically; put project-specific values
   in a marked `# EXAMPLE` block so the knowledge stays portable.

## Doc format

```yaml
---
type: <see vocabulary below>     # REQUIRED, non-empty
title: <human title>
description: <one sentence — reused verbatim in the parent index.md entry>
tags: [<tags>]
maturity: field-validated | reported | draft
timestamp: <ISO-8601>
resource: </path/to/source-file>   # for evidence/tool/deliverable stubs
---
```
Component & topic docs MUST include a `# Proven dead ends` section (and an `# EXAMPLE` block where
project specifics exist). End with `# Related` (bundle-absolute `/…` links) and `# Citations`.

## `type:` vocabulary (starter set — extend as needed)

| type | used for |
|---|---|
| `component-knowledge` | how a device/subsystem behaves |
| `topic` | a cross-cutting subject |
| `evidence` | a proven finding + link to the raw artifact |
| `tool` | a diagnostic/reporting instrument built for the project |
| `guide` | meta docs (this file, HOW-TO-USE) |
| `index` | directory `index.md` files |

## Adding a doc

1. Create the `.md` with frontmatter under the right category dir.
2. Add a bullet to that directory's `index.md`: `* [Title](file.md) - <description>`.
3. Add `# Related` links where they help navigation.
4. Run the conformance check.

## Conformance check

```bash
python check_conformance.py     # adjust the bundle root path inside if needed
```
Passes when every non-reserved `.md` has parseable frontmatter + non-empty `type`, and every
bundle-absolute link resolves. Broken links are tolerated by OKF, but prefer zero.
