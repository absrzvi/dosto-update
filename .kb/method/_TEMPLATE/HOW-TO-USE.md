---
type: guide
title: How to use this knowledge base
description: Orientation for a human or AI agent picking up this project's knowledge base.
tags: [meta, onboarding]
timestamp: <YYYY-MM-DDT00:00:00Z>
---

# What this is

A knowledge base for **<PROJECT>**, built with the Evidence-First Knowledge Method. It exists so
anyone (human or AI agent) can learn the system and troubleshoot it **without repeating work that's
already been done** — especially approaches already proven not to work.

It follows the **OKF v0.1** format: markdown files, each with a small YAML frontmatter block. No
tooling required — read the `.md` files directly.

# How to read it

Start at [index.md](index.md), then drill into the category you need:

- **`components/`** — how each device/subsystem behaves. Read these first when troubleshooting one.
- **`topics/`** — cross-cutting subjects that span components.
- **`evidence/`** — what has been proven, with a link to the raw artifact that proves it.
- **`tools/`** — instruments built for this project (diagnostics, generators).

# The two conventions that make this worth reading

1. **⛔ Proven dead ends.** Every component/topic doc lists what was tried and disproven on real
   systems. **Check it before you attempt a fix** — don't re-test what already failed.
2. **`resource:` links.** Facts that come from a specific file (a capture, a config, a script)
   carry a link to it, so you're one hop from the source evidence.

# What to trust

- `maturity: field-validated` — observed on real hardware/systems; a `# Citations` block names how.
- `maturity: reported` — believed true from docs but not personally re-verified.
- `maturity: draft` — provisional.

Per OKF, treat broken links and missing optional fields as tolerable — this KB grows incrementally.
