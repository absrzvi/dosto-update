---
type: guide
title: The Evidence-First Knowledge Method
description: A portable, project-agnostic method for turning hands-on troubleshooting into a reusable knowledge base — evidence-first testing, proven dead ends, and capture-as-you-go.
tags: [method, portable, meta, process]
timestamp: 2026-07-04T00:00:00Z
---

# The Evidence-First Knowledge Method

A repeatable way to work on any hands-on technical project (network commissioning, system
debugging, infra migration) so that the knowledge you gain **compounds** instead of evaporating —
and so a teammate or an AI agent can pick up where you left off without repeating your dead ends.

This method is **project-agnostic**. It was distilled from a rail onboard-network commissioning
project (DOSTO NEU) but names nothing specific to it. Copy [`_TEMPLATE/`](_TEMPLATE/) into any new
project's repo as `.kb/` and follow the five principles below.

## Why this exists

Most troubleshooting knowledge dies three ways:
1. **It stays in your head** — the next person (or next-you, six months later) re-derives it.
2. **It's buried in raw output** — the proof exists in a log file nobody will ever re-open.
3. **The dead ends are never written down** — so everyone re-tries the thing that doesn't work.

The fix is a small, disciplined habit, not a heavy process.

## The five principles

### 1. Evidence-first
Capture the **raw artifact** before you write a conclusion. A packet capture, an SNMP walk, a log
harvest, a config dump — the thing that would convince a skeptic. Keep it. Conclusions get
revised; evidence doesn't. When you later claim "X is broken," you can point at the capture that
proves it.

> Practice: save raw captures to an `evidence/`-style location, timestamped, named for what they
> show. Never delete them to "clean up" — they're the proof behind every report.

### 2. Repro-driven
A fault isn't understood until you can **trigger it on demand**. Turn "it sometimes fails" into a
script or a numbered procedure that makes it fail every time. The repro is worth more than the
diagnosis — it survives staff changes, it validates the fix, and it's the strongest possible
evidence for an upstream bug report.

> Practice: for any non-trivial fault, write a `repro` (a script or a step list). If you can't
> repro it, say so explicitly — an un-reproduced fault is a hypothesis, not a finding.

### 3. Record the dead ends
**What did NOT work is rarer and more valuable than what did.** Every project accumulates
approaches that seem obvious but fail — a CLI command that doesn't exist, a config that silently
no-ops, a fix that a reboot wipes. Writing these down is the single highest-leverage habit here:
it stops the whole team (and every future agent) from burning hours re-testing them.

> Practice: every component/topic doc carries a `# Proven dead ends` section. When you disprove
> something on real hardware/systems, add it there **before you move on**. One line: what you
> tried, why it failed, what to do instead.

### 4. Distill into a component knowledge base
Organise knowledge **by the thing it's about** (a device type, a subsystem, a cross-cutting
topic), not by the folder it happened to land in or the date you found it. Write the core
**generically** so it's portable; put project-specific values (IPs, names, IDs) in clearly-marked
`EXAMPLE` blocks. Use plain markdown + a tiny YAML frontmatter (`type:` is the only required
field) so any human or agent can read it with zero tooling. (This is the
[OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) format.)

> Practice: `components/` (how each thing behaves), `topics/` (cross-cutting subjects),
> `evidence/` (what's proven + the raw link), `tools/` (instruments you built). An `index.md` at
> each level for navigation. See [`_TEMPLATE/`](_TEMPLATE/).

### 5. Capture as you go
The method only works if capture is **cheap and immediate**. Don't batch it for "later" — later
never comes and the context is gone. When you prove something, disprove something, or build a
tool, it lands in the KB in the same work session. A newly-proven dead end is the highest-value
thing to add.

> Practice: end each investigation by asking "what did I learn that the KB doesn't have yet?" and
> writing that one doc. Run the conformance check. Commit.

## The workflow in one loop

```
investigate → capture raw evidence → (build a repro) → reach a conclusion
     → distill into KB (component/topic/evidence/tool) → record any dead end
     → run conformance check → commit → next investigation
```

## Harvesting an existing project

If you already have a pile of findings/reports/scripts (most projects do), do a one-time
**harvest**: read the high-value artifacts, distill each into an `evidence/` or `tools/` doc,
fold newly-found dead ends into the component/topic docs, and keep the raw files committed as
evidence. Then switch to capture-as-you-go so the pile never rebuilds.

## Starting a new project

1. Copy [`_TEMPLATE/`](_TEMPLATE/) into the new repo as `.kb/`.
2. Rename/adjust the `components/` and `topics/` to your domain's things.
3. Add a one-line pointer to `.kb/` in the repo's top-level guide (README / CLAUDE.md) so it's
   discoverable, with the rule: **check `# Proven dead ends` before attempting a fix.**
4. Work the loop. Let it grow.

# What makes this portable

Nothing here depends on a domain. "Capture evidence, build repros, record dead ends, distill by
component, capture as you go" is as true for a Kubernetes migration or a firmware bring-up as it
is for a train network. The `_TEMPLATE/` carries the structure; this doc carries the discipline.

# Related

- [`_TEMPLATE/`](_TEMPLATE/) — the empty skeleton to copy
- [The reference implementation](/.kb/index.md) — this project's fully-populated KB
- [Maintenance guide](/.kb/MAINTENANCE.md) — the operational how-to for a live KB
