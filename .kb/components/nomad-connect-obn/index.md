---
type: component-index
title: Nomad Connect / OBN — component knowledge
description: How the CCU (box1-tNN Debian jump box) and OBN (the onboard-network engine) behave — the bug suite, the discover→report→update workflow, the btrfs persistence model, the CCU firewall TFTP gap, and the publish→Puppet deploy pipeline — with the dead ends already disproven on live CCUs.
component: nomad-connect-obn
project: dosto-neu
---

# Nomad Connect / OBN

The **CCU** (`box1-tNN`, a Debian jump box running a btrfs read-only root snapshot) and **OBN**
(`nd-obn`, the onboard-network engine that discovers, reports on, and updates the consist's switches
and APs). This is the stack you drive to commission a trainset. Read the bug suite and the workflow doc
before running any `obn update` — most of the pain here is silent no-ops and a hang, not loud errors.

## Engine behaviour

* [The 11-bug suite](bug-suite.md) — the 11 known OBN crash/hang/silent-no-op bugs, per-bug file + symptom + root cause + fix, detection by grep marker, and why patch state is never inferable from the version string.
* [discover → report → update workflow](discover-report-update.md) — the snapshot pipeline, why `obn report` is a hard prerequisite (the `discovery.prev.json` snapshot and the `all([]) == True` readonly-devices catch-22), and why `obn update c` exit 0 is not proof of work.

## CCU platform

* [NDSU chroot & btrfs persistence](ndsu-chroot-persistence.md) — how edits survive reboot via `nd-systemupdate.sh`, the `.dont` rename that blocks the nightly auto-update, the heredoc-not-paste chroot rule, the work-vs-run stale-subvol trap, and the update survival model (unowned `/etc` survives, `/usr/share/obn` rewritten).
* [TFTP conntrack helper gap](tftp-conntrack-helper.md) — the missing `nf_conntrack_tftp` helper on udp/69 that silently fails most APs in an `obn update f ap` batch, the diagnostic, the runtime workaround, and why it needs a Puppet fix to persist.

## Release & deploy

* [publish → Puppet deploy pipeline](publish-to-puppet-pipeline.md) — the 7-step path a change walks to reach a train, templates (no CI, hand-published) vs the `nd-obn` engine (CI on tag), and why merging git alone changes nothing (the master does not auto-sync; `dbc` is not a deploy).
