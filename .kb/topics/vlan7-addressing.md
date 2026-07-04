---
type: topic
title: vlan7 Bit-Packed Addressing & Stadler-FW Reachability
description: How the per-train vlan7 IP is derived from the Fzg ID, why the on-CCU formula is wrong, and how to read the ICMP result to a Stadler firewall as a commission-state signal rather than a fault.
project: dosto-neu
tags: [vlan7, addressing, stadler-firewall, fzg-id, icmp, commissioning, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

`vlan7` is the transit link between the Nomad CCU and the Stadler firewall/gateway on a
DOSTO NEU consist. It is the only Stadler-side VLAN the CCU sees directly — every device
VLAN behind the firewall (cameras, displays, AFZ, intercom, RDC, energy meter) is routed
by the Stadler firewall and is invisible from the CCU. So vlan7 reachability is the single
CCU-side gate on "can we reach anything Stadler-side."

Two things make vlan7 a repeated source of wrong conclusions:

1. Its IP is **per-train**, derived by a **bit-packed formula** — and the formula rendered on
   the live CCU is frequently wrong pre-commissioning.
2. A correctly-commissioned Stadler firewall **drops ICMP by policy**, so "ping fails" is the
   *healthy* state and "ping succeeds" is the *not-yet-commissioned* state. Both directions of
   that fact have burned engineers.

> **Portability note.** The bit-packing scheme and the ICMP-as-commission-signal logic are
> generic to the DOSTO NEU / Stadler interconnect. All literal subnets and per-train numbers
> live in the `EXAMPLE (DOSTO NEU)` block and must be re-derived for any other deployment.

# The bit-packed addressing scheme

DOSTO NEU IPs on the Stadler side pack four fields into a 32-bit address:

```
bits  1-12 : 172.19          static prefix (always 172.19.x.x/17 for DOSTO NEU)
bits 13-17 : VLAN ID         5 bits, 1-31   (vlan7 = 0b00111)
bits 18-25 : Fzg ID          8 bits, 1-255  (the ÖBB customer vehicle number)
bits 26-32 : device          7 bits, 1-127  (CCU on vlan7 = device 2; firewall = device 1)
```

## CCU vlan7 IP — the working formula

For the CCU's own vlan7 address this packs to:

```
octet3 = 128 + (Fzg // 2)
octet4 = 2            if Fzg is even
octet4 = 128 + 2 = 130 if Fzg is odd
IP     = 172.19.<octet3>.<octet4>/17
```

- **Even Fzg → host `.2`. Odd Fzg → host `.130`.**
- The Stadler firewall is device 1 on the same `/17`. Even Fzg → FW host `.1`. **Odd Fzg → FW
  host `.129`** (device 1 + the 128 odd-offset), *not* `.1`. This odd-Fzg case is a live trap —
  see dead end 4.

The input is the **Fzg ID**, never the Nomad-internal train_id. See
[Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md) — conflating the two is
exactly what produces a wrong vlan7 IP.

# Where the active IP actually comes from (and where it does NOT)

There are three places a vlan7 IP appears on a CCU. Only one is authoritative.

| Source | Authoritative? | Notes |
|---|---|---|
| `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection` | ✅ **Yes** | This is the live IP. Set per-train via `nd-systemupdate.sh shell` (chroot). |
| `/etc/nd-redundancy/networks.yaml` (rendered from Puppet `networks.epp`) | ❌ No | Formula is **broken** — computes from `train_id`, not Fzg. See dead end 1. |
| The formula in your head | verify only | Compute the *expected* IP, then diff against the live nmconnection file. |

**Durability caveat.** A hand-edit to the nmconnection file survives a plain reboot and survives
`obn update c` (OBN never touches CCU NetworkManager files). It does **NOT** survive a
snapshot promote / `nd-systemupdate up` / image refresh — those re-render the Puppet formula
back into the file. The durable fix is to correct the Puppet template to key off the Fzg (as a
`fzg_id`/`train_id`-is-Fzg value, per the box=Fzg decision), after which Puppet re-asserts the
correct IP every run and the hand-fix becomes verify-only.

# Reading Stadler-FW reachability — three separate questions

Do not collapse these into one "can I reach the firewall" check. Each has its own probe and its
own success criterion; conflating them produces wrong customer-report verdicts.

### Q1 — Path health (ARP)
```bash
ip neigh show dev vlan7 | grep <fw-ip>     # want: REACHABLE, FW MAC (Westermo OUI 00:90:e8:…)
ip -s link show vlan7                       # want: errors/drops = 0
```
`REACHABLE` = traffic flows to the FW. `FAILED`/no neighbour = path broken (vlan7 IP wrong,
vlan not trunked through, or FW absent). **If Q1 fails, stop — Q2/Q3 are meaningless.**

### Q2 — Commission state (ICMP) — the deciding test
```bash
ping -c 5 <fw-ip>
```
| ICMP result (with Q1 = REACHABLE) | Verdict |
|---|---|
| 100 % loss | ✅ FW **commissioned** — Stadler policy is dropping echo-request as designed |
| replies | 🟡 FW responding but **NOT yet commissioned** — bare Westermo default, no Stadler policy |

> **ICMP is the only authoritative commission-state test from the CCU side.** ping-fail (with
> ARP reachable) = fully commissioned. ping-success = Stadler-side work still pending.

### Q3 — Service availability (TCP)
```bash
nc -zv -w 5 <fw-ip> 80
nc -zv -w 5 <fw-ip> 22
```
TCP tells you only whether *something* answers on a port — it **cannot** distinguish
"commissioned with a tight policy" from "not yet commissioned." Use it only after Q1+Q2, to
confirm a specific service path, never to decide commission state.

**Do not write a `FW reach` verdict from TCP alone.** Any train marked `FW reach: ✅` on the
basis of a TCP-OPEN result without an ICMP test needs re-verification.

# Proven dead ends — do NOT repeat these

> This section exists so a fresh agent does not re-derive a wrong vlan7 IP or mis-read a ping.

1. **Trusting `networks.yaml` / the Puppet `networks.epp` formula.** It templates vlan7 from a
   `train_id`-based expression (`128 + ((fis_id+train_id)//2)`), not from the Fzg. On any CCU
   where the internal train_id ≠ Fzg (i.e. most of them pre-commissioning) it renders the wrong
   subnet. The live IP is in the **nmconnection file**, set by `nd-systemupdate.sh`. Verify
   there; do not read `networks.yaml` and believe it.
2. **Reading ping-FAIL to the FW as a fault.** A commissioned Stadler FW drops ICMP echo-request
   by policy. 100 % loss *with ARP REACHABLE* is the healthy, commissioned state.
3. **Reading ping-SUCCESS to the FW as health.** The newer trap (audit F9): replies mean you are
   hitting a bare Westermo box that Stadler has not yet applied policy to — i.e. commissioning is
   *incomplete*, not complete.
4. **Assuming the FW is always host `.1`.** True only for even Fzg. **Odd Fzg puts the FW at
   `.129`** (device 1 + 128 odd-offset), and the CCU at `.130`. Probing `.1` on an odd-Fzg train
   gives a false path_broken. (Verified: Fzg 147 FW = `172.19.201.129`, not `.1`.)
5. **Letting the l2-health probe use its hardcoded default FW IP.** The `08_e2e_probe.sh` script
   defaults the FW IP to `172.19.196.1`. For any train not at that address it reports a false
   `path_broken`. Always pass the FW IP explicitly:
   `bash 08_e2e_probe.sh <ccu-ip> <fw-ip>`.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- Static prefix `172.19.0.0/17`; vlan7 = VLAN 7; CCU = device 2, FW = device 1.
- **Even Fzg:** CCU `172.19.<128+Fzg//2>.2`, FW `172.19.<128+Fzg//2>.1`.
  Example Fzg 132 → CCU `172.19.194.2`, FW `172.19.194.1`.
- **Odd Fzg:** CCU `172.19.<128+(Fzg-1)//2>.130`, FW `…​.129`.
  Example Fzg 147 → CCU `172.19.201.130`, FW `172.19.201.129` (live-verified 2026-06-12).
- Stadler FW MAC OUI `00:90:e8:…` (Westermo). Verified 2026-05-12 on Fzg 130 (FW `172.19.193.1`)
  where the `08_e2e_probe.sh` default (`172.19.196.1`) produced a false path_broken.

# Related

- [Fzg-ID two-namespace problem](/.kb/topics/fzg-id-two-namespaces.md)
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)
- [VDS Consist Switch — CLI & management](/.kb/components/vds-consist-switch/cli-and-management.md)
- [Coupled-train RSTP TC-storm](/.kb/topics/coupled-rstp-tc-storm.md) — odd-Fzg FW IP found during coupling test
- [Fleet: trains where these facts were observed](/.kb/fleet/index.md)

# Citations

[1] CLAUDE.md — "vlan7 IP formula", Phase 6 (three-question FW probe).
[2] Session memory `project_vlan7_durable_fix_via_fzg_id` — broken `networks.epp` formula, snapshot-promote wipe, durable fzg_id fix (verified 9/9, 2026-06-30).
[3] Session memory `project_coupled_rstp_tc_storm` §3 — odd-Fzg FW at `.129` (Fzg 147 = `172.19.201.129`, 2026-06-12).
[4] Field validation Fzg 130 (2026-05-12) — `08_e2e_probe.sh` hardcoded default FW IP false path_broken.

<!-- OBSIDIAN-GRAPH-LINKS (auto-generated by scripts/add_obsidian_shadows.py — safe to delete) -->
> Obsidian graph edges (mirror of the Related/inline links above). The canonical links are the markdown `](/.kb/…)` ones; these `[[…]]` exist only so Obsidian's graph view connects the nodes.

- [[.kb/topics/fzg-id-two-namespaces|fzg-id-two-namespaces]]
- [[.kb/topics/l2-health-methodology|l2-health-methodology]]
- [[.kb/components/vds-consist-switch/cli-and-management|cli-and-management]]
- [[.kb/topics/coupled-rstp-tc-storm|coupled-rstp-tc-storm]]
- [[.kb/fleet/index|index]]
