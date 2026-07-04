---
type: index
title: The Evidence-First Knowledge Method
description: A portable, project-agnostic method + template for turning troubleshooting into a compounding knowledge base.
timestamp: 2026-07-04T00:00:00Z
---

# The Method (portable)

This folder is the **reusable** part of the KB — copy it to any project.

* [METHOD.md](METHOD.md) - the written methodology: evidence-first, repro-driven, record dead ends, distill by component, capture as you go.
* [`_TEMPLATE/`](_TEMPLATE/index.md) - an empty OKF skeleton to copy into a new repo as `.kb/`. Includes HOW-TO-USE, MAINTENANCE, a frontmatter cheatsheet, category placeholders, and a portable conformance checker.

## How to start a new project

1. Copy `_TEMPLATE/` into the new repo as `.kb/`.
2. Adjust `components/` and `topics/` to your domain.
3. Add a one-line pointer to `.kb/` in the repo's top-level guide, with the rule: **check
   `# Proven dead ends` before attempting a fix.**
4. Work the loop in [METHOD.md](METHOD.md).

## The reference implementation

The rest of this `.kb/` (outside `method/`) is a **fully-populated example** of the method applied
to a real project — [start here](/.kb/index.md).
