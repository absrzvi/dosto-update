---
type: evidence
title: OBN platform codebase review — defect load is two systemic patterns, verdict "improve not rewrite"
description: A multi-agent, adversarially-verified review of the OBN engine (v2.3.12) establishing that its real defect load is two repeating common-fix patterns (unguarded SNMP-None consumers + silent-success/error-masking) plus a hand-rolled-14× report layer and a committed-plaintext-credentials cluster — a hardening problem, not a rewrite trigger.
project: dosto-neu
tags: [obn, codebase-review, architecture, none-deref, error-masking, number-coaches, security, credentials, improve-not-rewrite, field-validated]
maturity: field-validated
timestamp: 2026-06-27T00:00:00Z
resource: /findings/obn_platform_review_2026-06-27/
---

# OBN platform codebase review — "improve, not rewrite"

## What it proves

A structured review of the OBN engine (`origin/master` v2.3.12) establishes, with adversarial
verification, that OBN's real defect load is **two systemic, common-fix patterns** — not diverse rot and
not a rewrite trigger:

1. **Unguarded SNMP-`None` consumers (`none_deref`).** `_snmp_get` returns `None` on any SNMP failure
   and device properties propagate it silently (no exception). Consumers that don't guard crash
   (`None.endswith()`, `None.startswith()`). **~22 of 39 actionable findings are this one pattern** —
   the ~11 field bugs are one design flaw surfacing at many call sites, not 11 independent defects.
2. **Silent-success / error-masking (`silent_noop` / `error_masking`).** Operations that report success
   without doing or verifying the work (`return True # TODO`), and API paths that collapse
   not-found / wrong-type / real-failure into one response.

Structural findings:

- **The report layer has no shared core.** `number_coaches()` is `@abstractmethod` and **all 15 report
  modules hand-roll it** (90–150 LOC each), so the single hardest, most defect-prone algorithm is
  written 14× — and the same defect class is latent across customer variants (independently flagged in
  report_via / ace / dsb / dani / queensland). This is the architectural argument for **extracting a
  shared, tested numbering engine**, not rewriting the platform. (Bug 10 and both numbering-drop
  findings live exactly here — see Related.)
- **`tree.py` is an untested critical path** — the sweep returned 3 HIGH crashes there (root-None-serial,
  empty-list `[0]`, unresolved-neighbour `None.type`), direct evidence the coverage gap ships real bugs.
- **`obn validate` is a weak commissioning gate** — always exits 0, no positive structural assertion,
  the real topology checks are unwired; a broken/short consist can validate as "OK". Don't trust its
  exit code or a green table as proof a train is correct.
- **Credential-exposure cluster (all HIGH, one root).** `vendors.yaml` commits plaintext SNMP/SSH creds;
  `NomadStayOut!` is reused across 8 vendor blocks (these drive **write**/config/firmware/reboot OIDs on
  the very vdsrail switches this project commissions); the secrets are **baked into the published `.deb`**,
  land **world-readable (mode 644)** on every CCU, and **persist in git history, never rotated** — with
  **no secret scanner** in pre-commit or CI to stop recurrence.

The overall complexity is low (avg CC 3.8, all MI grade A) — a *fragility/abstraction/process* problem in
a *simple* codebase: the classic "improve (extract + harden + type + scan)" profile, not "rewrite."

## How it was captured

- Read-only, multi-agent sweeps over the worktree with **`file:line` citations verified against source**,
  each finding **adversarially re-verified** by an independent skeptic (re-read code, searched the test
  suite, assigned blast-radius). The adversary was credible — it **refuted 8** claimed bugs (guards the
  hunter missed) and downgraded severities; it did not rubber-stamp.
- P3 bug sweep: 47 raw → **15 confirmed, 24 needs-runtime, 8 refuted** (53 agents, ~4.2M tokens).
- BS blind-spot sweep of high-blast-radius central modules (snmpdevice / walker / decorators / validate /
  context / obn.py): 23 raw → **6 confirmed** — added after the engineer pushed "what else like the
  GenericReport miss did we skip," closing the "audit shared/base/gate modules as first-class targets"
  gap.
- S security/config sweep: the agent verify phase hit session limits, so **every S-cluster finding was
  re-verified directly by the engineer via read-only git/grep/sed** (first-hand evidence, not trusted
  agent output).

## Evidence

- Raw folder: [`findings/obn_platform_review_2026-06-27/`](/findings/obn_platform_review_2026-06-27/) —
  the full review. Key summaries:
  - [`P1_architecture.md`](/findings/obn_platform_review_2026-06-27/P1_architecture.md) — layered
    structure, the no-shared-numbering-core finding, None-propagation as the dominant error design,
    no-API-auth.
  - [`P3_bug_sweep_summary.md`](/findings/obn_platform_review_2026-06-27/P3_bug_sweep_summary.md) — the
    confirmed-15 table + defect-class breakdown + cross-customer spread of the numbering defect.
  - [`BS_blindspot_summary.md`](/findings/obn_platform_review_2026-06-27/BS_blindspot_summary.md) —
    central-module audit + the weak-`obn validate`-gate cluster + dead-disk-cache trap.
  - [`S_security_config_sweep.md`](/findings/obn_platform_review_2026-06-27/S_security_config_sweep.md) —
    the S3–S7 plaintext-credential cluster + the no-secret-scanner guardrail gap.
  - Registers (machine-readable): `P3_findings_register.json`, `BS_blindspot_register.json`,
    `bespoke_vs_generic_register.json`, `ONBOARD_fragility_register.json`, `FW_DRIFT_register.json`.

## So what (dead end / actionable)

- **Do NOT treat the field bugs as isolated one-offs** — fix the *pattern*: a typed "result-or-error"
  SNMP return (+ mypy in CI, currently absent) collapses most of the `none_deref` class; the
  silent-success family needs read-back verification, not `return True`.
- **Do NOT rewrite the platform** — the review's cross-checked verdict is **improve**: extract a shared
  numbering engine, harden the None consumers, wire real `obn validate` assertions, add coverage on
  `tree.py`, and stand up secret scanning + rotate the committed creds.
- **Do NOT trust `obn validate`'s exit code or a green table** as commissioning proof — it always exits 0
  and asserts nothing structural.
- **Treat the committed creds as compromised** — `NomadStayOut!` (write-capable, reused ×8) is recoverable
  from the published `.deb`, from world-readable `/etc/obn/*.yaml` on every CCU, and from git history.
  Rotate + move to an ignored secret file + `chmod 600` in postinst + add `gitleaks`/detect-secrets to
  pre-commit **and** CI.
- **Audit shared/base/factory/gate modules as first-class targets** weighted by blast radius — the
  GenericReport-class blind spot came from treating them as "context, assumed clean."

# Related

- [Nomad Connect / OBN — bug suite (the 11 field bugs this review generalizes)](/.kb/components/nomad-connect-obn/bug-suite.md)
- [OBN drops healthy switches on cold-bypass (evidence — a report-layer numbering defect)](/.kb/evidence/obn-numbering-drops-healthy-switches-on-bypass.md)
- [OBN numbering fragile to a single lost LLDP edge (evidence)](/.kb/evidence/obn-numbering-fragile-to-single-edge-loss.md)
- [Nomad Connect / OBN — publish → Puppet pipeline (where the .deb ships the creds)](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)
