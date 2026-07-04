---
type: component-knowledge
title: Nomad Connect / CCU — TFTP conntrack helper gap
description: The CCU firewall is missing the nf_conntrack_tftp helper on udp/69, silently failing most APs in an obn update f ap batch — the diagnostic, runtime workaround, and why it isn't reboot-persistent.
component: nomad-connect-obn
project: dosto-neu
tags: [ccu, firewall, iptables, conntrack, tftp, ap, firmware, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

TFTP is a two-flow protocol: the client sends an RRQ to udp/69, and the server replies with data
**from a random high port back to the client**. For that return flow to pass a default-deny firewall,
conntrack must recognise it as RELATED to the original RRQ — which requires the `nf_conntrack_tftp`
**helper** module loaded AND a CT-helper rule marking udp/69 traffic.

On the current CCU image **neither is present**. The kernel module isn't loaded and there's no
raw-PREROUTING rule. Result: the TFTP data flows from OBN's server back to each AP are **silently
dropped** by the CCU firewall's default-deny (`INPUT policy DROP`), because conntrack never associated
them with the RRQ.

**This is a CCU firewall gap, NOT an OBN bug.** OBN is doing the right thing; the packets die in the
kernel's netfilter layer before they matter.

> **Portability note.** `60-allow-management`, the `10.179.x` VLAN, `box1-tNN`, and dates below are
> DOSTO-NEU specifics. The two-flow-TFTP-needs-a-conntrack-helper behaviour is generic to any
> default-deny Linux gateway running a TFTP server.

# Symptom — the silent partial AP firmware batch

`obn update f ap` against a multi-AP batch sees only **~5 of ~15 APs succeed** — the ones whose data-port
choice happens to race past conntrack's UDP heuristics. The rest silently fail. **OBN reports
"Successful"** for all of them because it never sees an error (compounded by Bug 11 — OBN trusts the
SNMP SET echo, not an activation read-back). You only discover the failures via a follow-up
`obn discover` showing the failed APs still on old firmware.

- **Single-AP** pushes occasionally succeed (conntrack UDP heuristics sometimes let the return flow
  through). **Batched** pushes mostly fail. This "single works, batch fails" pattern is the tell.

# Diagnostic (from the CCU)

```bash
lsmod | grep nf_conntrack_tftp                                   # empty  = helper absent (bug present)
sudo iptables -t raw -L PREROUTING -n -v | grep -i "helper tftp" # empty  = no CT rule (bug present)
sudo iptables -L INPUT -n -v | grep tftp_allowed                 # KB-scale bytes = failing; GB = a healthy batch
```

The `tftp_allowed` byte counter is the clearest live signal: a successful multi-AP firmware batch
pushes gigabytes through that rule; a broken one shows only kilobytes.

# Runtime workaround (does NOT survive reboot)

```bash
sudo modprobe nf_conntrack_tftp
sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
```

After this, `obn update f ap` works against every AP in the batch. **Apply it before every AP firmware
batch.** It is wiped on **every CCU reboot** — it is a runtime rule, not part of the btrfs snapshot,
and even an NDSU chroot promote won't carry a live iptables rule. Re-apply each boot until the Puppet
fix lands.

The `dosto-tftp-helper-check` skill encodes both the diagnostic and this recipe (read-only by default).

# Persistent fix (the actual ask — Puppet)

Two parts, both in Puppet (module `60-allow-management` or a sibling), so they apply at boot before
NetworkManager/nftables resets the chain:

1. `nf_conntrack_tftp` in `/etc/modules-load.d/` so the helper loads at boot.
2. A raw-PREROUTING rule marking udp/69 for TFTP CT-helper handling (the `iptables` line above,
   expressed via Puppet's iptables resource type).

Hand-editing `/etc/21net-security.d/60-allow-management` on the CCU has the same
persistence problem as OBN patches: it's Puppet-managed and gets clobbered on the next btrfs promote
unless applied via the NDSU chroot — and even then it's fragile because the chain is rebuilt at boot.
The durable answer is the Puppet change, not a CCU-side edit.

# Relationship to OBN Bug 5

This helper is the **dependency for OBN Bug 5 to work end-to-end**. Bug 5 pre-populates the
`tftp_allowed` ipset with the right target IPs so a restarted batch doesn't skip devices. This helper
ensures the kernel's conntrack layer actually associates those IPs' TFTP data flows so the transfers
arrive. **Both must be present** for a reliable AP-firmware batch — the ipset having the right IPs is
useless if the return flows are dropped. See
[/.kb/components/nomad-connect-obn/bug-suite.md](/.kb/components/nomad-connect-obn/bug-suite.md).

# Proven dead ends — do NOT repeat these

> Approaches tried and disproven on live CCUs.

1. **Do NOT read `obn update f ap` "Successful" as done.** With the helper absent, most APs silently
   fail while OBN reports success (it prints on RRQ initiation / SNMP SET echo, not on completed
   transfer — see Bug 11). Confirm with a post-run `obn discover` showing actual firmware strings.
2. **Do NOT conclude the batch path is flaky at the OBN/AP level.** The flakiness is the CCU firewall's
   conntrack gap, not OBN and not the APs. "Single AP works, batch mostly fails" is the conntrack-race
   signature, not an OBN bug.
3. **Do NOT expect the runtime `modprobe` + iptables fix to survive a reboot.** It is a live rule
   outside the btrfs snapshot; every reboot loses it. Re-apply each session until the Puppet fix ships.
4. **Do NOT expect an NDSU chroot promote to persist the iptables rule.** The chroot persists filesystem
   state; a live iptables rule is runtime state. Persistence must come from Puppet (module + rule that
   apply at boot before the chain is reset).
5. **Do NOT rely on OBN Bug 5 alone to fix batch AP firmware.** Bug 5 fills the ipset; without this
   conntrack helper the return flows are still dropped. Both are required together.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- **Puppet module:** `60-allow-management` (file `/etc/21net-security.d/60-allow-management` on the CCU),
  or a sibling — the module that already manages the management-VLAN firewall stance.
- **Management VLAN:** `vlan100` (`10.179.X.128/25`), where the consist switches/APs live; a private
  subnet with no external access, so the widened TFTP-allowed window carries negligible security risk.
- **Skill:** `.claude/skills/dosto-tftp-helper-check/SKILL.md` — the read-only check + recipe printer.
- **Upstream:** tracked as the *infra* (section B) item under **TRIAG-8585** — distinct from OBN code
  bugs; owner is Puppet, not `nd-obn`.
- **Evidence:** validated 2026-05-09 on box1-t10 (5/15 without, then reliable batch-of-3 after loading
  the helper) and 2026-05-20 on Fzg 143 (15/15 with the runtime fix pre-push).

# Related

- [Nomad Connect / OBN — the 11-bug suite](/.kb/components/nomad-connect-obn/bug-suite.md) (Bug 5, Bug 11)
- [Nomad Connect / OBN — NDSU chroot persistence](/.kb/components/nomad-connect-obn/ndsu-chroot-persistence.md)
- [Nomad Connect / OBN — publish → Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)

# Citations

[1] `rd-handoff/companion-01-tftp-conntrack-helper-puppet.md` — root cause, reproducer, runtime + Puppet fix, Bug 5 dependency.
[2] Memory `project_tftp_conntrack_helper.md` — diagnostic commands, `INPUT policy DROP`, box1-t10 evidence.
[3] `.claude/skills/dosto-tftp-helper-check/SKILL.md` — encoded check + recipe.
