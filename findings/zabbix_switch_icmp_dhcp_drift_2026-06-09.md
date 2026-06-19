# Finding — Zabbix "SW R# SW# unavailable by ICMP" alarms = DHCP lease drift, not switch faults

**Date:** 2026-06-09
**Train:** 4736-115 / Fzg 143 / box **6018** (CCU `10.179.18.1`)
**Zabbix:** `https://trainzabbix-obb-alpin.nomadrail.com` (API), host group `50_6018`
**Author:** Abbas Rizvi
**Status:** Confirmed (read-only). No changes made.

## Symptom

NMS alarm burst: ~17 of 18 consist switches flipped to **High: "SW R# SW# is unavailable by ICMP"**
at **09/06 05:06–05:07**, preceded by three Medium **"Port e2-0/e2-4 DOWN (admin-enabled)"**
at 08/06 22:09–22:10. The train is **powered up and healthy** at the time of investigation.

Engineer hypothesis: Zabbix is pinging the wrong switch IPs — same failure class as the earlier
AP alarm that pinged a factory `192.168.1.20` address.

## Verdict

Hypothesis is **right in class, wrong in mechanism.**

- It is **not** a wrong hardcoded / factory / wrong-subnet IP. The Zabbix switch targets are all
  in the correct `10.179.18.x` management subnet.
- It **is** a monitoring-target-vs-live-IP mismatch — caused by **DHCP lease drift**: the switch
  addresses are handed out from a purely **dynamic** pool (no per-MAC reservations), so every
  train power-cycle reshuffles which switch holds which IP. Zabbix's per-host interface IPs are
  **static**, frozen at provisioning-time addresses, so after a power-cycle most of them point at
  addresses no switch currently holds → false ICMP-down.
- **SNMP being healthy is irrelevant** to these triggers — they are ICMP-availability triggers.
  ICMP is the correct liveness check; do **not** disable it.

## Evidence

### Live switch leases on CCU (2026-06-09 04:22–04:23, all 18/18 present, OUI `a0:59:3a`)

```
.138 nv6-C1   .139 nv6-E3   .140 nv6-B2   .178 nv6-A2   .194 nv6-C2   .196 nv6-B3
.197 nv6-C3   .198 nv6-F2   .199 nv6-F3   .200 nv6-D1   .201 nv6-B1   .202 nv6-D2
.203 nv6-E2   .204 nv6-A3   .205 nv6-A1   .206 nv6-D3   .207 nv6-E1   .208 nv6-F1
```

### Zabbix switch host interface IPs (group `50_6018`, type SNMP/ICMP target)

```
R1_SW1 .181  R1_SW2 .178  R1_SW3 .195
R2_SW1 .189  R2_SW2 .182  R2_SW3 .190
R3_SW1 .183  R3_SW2 .186  R3_SW3 .184
R4_SW1 .179  R4_SW2 .188  R4_SW3 .187
R5_SW1 .192  R5_SW2 .185  R5_SW3 .180
R6_SW1 .193  R6_SW2 .191  R6_SW3 .196
```

### Diff
Only **`.178` and `.196`** appear in both lists. The other **16 Zabbix switch hosts ping
addresses no switch currently holds** (`.179,.180,.181,.182,.183,.184,.185,.186,.187,.188,
.189,.190,.191,.192,.193,.195`), while the live switches at `.194,.197–.208` and the three at
`.138–.140` are effectively **unmonitored**. This matches the ~16–17 simultaneous ICMP alarms.

### APs — NO drift (this cycle)
Live AP leases `.218–.241` (OUI `00:14:5a`) match the 24 Zabbix AP host interfaces **exactly**.
The APs happened to land on their provisioned addresses this power-cycle. They are **equally
exposed** to the same drift on a future cycle — they were simply not contended this time.

## Root cause — CCU `/etc/dhcp` (ISC dhcpd)

`/etc/dhcp/networks/management.conf`, subnet `10.179.18.128/25`, three **dynamic range** pools,
**no `fixed-address` reservations**:

| Pool (class)  | Range          | Match (class def)                         |
|---------------|----------------|-------------------------------------------|
| `switch`      | `.178 – .208`  | OUI `a0:59:3a` (+ 28:60:46/00:90:e8/74:8f:4d) |
| `accesspoint` | `.218 – .248`  | OUI `00:14:5a` (+ others)                 |
| `devices`     | `.138 – .168`  | negative match (everything not above)     |

Each pool carries **both** `allow members of "<class>"` **and** `allow known-clients`, with
`max-lease-time 120` (2-min leases — matches the playbook's "DHCP lease lifetime is 2 minutes").

Two compounding effects:
1. **Intra-pool reshuffle:** the switch pool is range-allocated, so a power-cycle re-hands `.178–.208`
   in whatever order clients re-request. No switch is pinned to its old address → Zabbix's static
   IPs go stale even though both sides use the same range.
2. **Pool leak:** three switches (`nv6-C1/E3/B2`) landed in the **`devices` pool `.138–.168`**, not
   the switch pool. The `allow known-clients` line lets a previously-seen switch fall through to the
   `devices` pool when the switch pool has no immediately-free lease (stale 2-min leases from the
   prior boot not yet expired during the simultaneous power-on).

The provisioning itself is **correct** — Zabbix switch hosts were set to `.178–.196` (inside the
switch pool) and AP hosts to `.218–.241` (inside the AP pool). The breakage is purely that the
pools are dynamic, so the IP→device binding is not stable across reboots.

### CONFIRMED in GitLab — this is the fleet template, by design (not a per-train glitch)

Source of truth = Puppet env repo `git@git-nc.nomadrail.com:env/environment-dostoneu.git`
(local clone `.tmp/gitlab-repos/environment-dostoneu`, HEAD `d79f96d`).

`hieradata/files/nd_redundancy/networks.epp` → `management` network (`vlan100`, `.128/25`) defines
the three pools as **address offsets off the `.128` subbase**, rendering identically on every train:

| Pool        | Offsets (low–high) | Rendered range (`.128` base) | Size |
|-------------|--------------------|------------------------------|------|
| switch      | 50 – 80            | `.178 – .208`                | 31   |
| accesspoint | 90 – 120           | `.218 – .248`                | 31   |
| devices     | 10 – 40            | `.138 – .168`                | 31   |

Every pool is `allow: [known-clients, members of "<class>"]`, `max_lease_time: 120`. Classes
(`switch` = OUI a0:59:3a etc., `accesspoint` = 00:14:5a etc.) are in
`hieradata/files/nd_redundancy/dhcp.yaml` — fleet-common, no IPs.

**There is NOT a single `fixed-address` / `host {}` / reservation / hostname→IP map anywhere in the
repo** (grep for `fixed-address|hardware ethernet|reservation` returns only the two class-match
`host-name` substrings). So the dynamic, non-deterministic IP→device binding is **designed-in
fleet-wide** — every DOSTO-NEU CCU on this environment behaves this way, and Zabbix's static
per-host IPs cannot track it across reboots. This is the root cause, not a one-train accident.

## Recommended fix (durable → stopgap)

1. **DHCP reservations (proper fix) — add to the Puppet template.** The fix belongs in
   `environment-dostoneu` `hieradata/files/nd_redundancy/networks.epp` (and possibly the
   `nd_redundancy` Puppet module that consumes `pools`/renders dhcpd), NOT hand-edited on each CCU.
   Pin each device MAC to a fixed offset so the switch/AP always lands on the address Zabbix expects
   — i.e. add a reservations construct (`host <name> { hardware ethernet <mac>; fixed-address <ip>; }`)
   keyed off the per-train MAC→position map. Source of truth for MAC→position = the per-train
   IP-Port-Allocation PDF / extracted topology. This makes Zabbix's existing static config correct
   **and stable across every power-cycle**, fleet-wide. **R&D ticket** — the `nd_redundancy` module
   currently has no reservation path at all.
   - **Caveat:** the playbook (`CLAUDE.md`) currently *relies on* 2-min dynamic leases + `dhcp-lease-list`
     for discovery. Reservations change that operational assumption — coordinate with R&D before
     baking into Puppet. Reservations and discovery aren't mutually exclusive (reserved leases still
     show in `dhcp-lease-list`), but the change should be deliberate.

2. **One-time Zabbix reconcile (stopgap only).** Rewrite the 18 switch (and verify AP) host interface
   IPs to today's live leases via `host.update`. Restores monitoring immediately but **re-breaks on
   the next power-cycle** without #1. Do not rely on this alone.

3. **Do NOT disable the ICMP triggers.** They are the correct liveness check and are independent of
   SNMP. Disabling hides a real "monitoring the wrong address" condition.

4. **Keep the Medium "Port e2-0/e2-4 DOWN (admin-enabled)" triggers** — those are genuine per-port
   state, not power-cycle noise.

5. **Optional noise reduction (orthogonal):** add a trigger dependency so per-switch ICMP triggers
   are suppressed when the CCU host is unreachable, so a real train power-off raises one alarm not 18.

## Fleet-wide implication

Every train with class-based dynamic switch pools (i.e. all NV6/NV4 CCUs on this dhcpd template) has
the same exposure. Switches drift on power-cycle; APs will too when contended. The 49-train SNMP-cred
fix (2026-06-08) corrected SNMP polling but did **not** touch the ICMP target binding — this is a
separate, still-open fleet issue. Recommend auditing switch-pool reservations across the fleet.

## Related

- AP factory `192.168.1.20` alarm (different mechanism: factory AP never got a Nomad lease) —
  see `dosto-ap-factory-recover` skill.
- `project_dhcp_lease_discovery` memory (2-min leases, use `dhcp-lease-list`).
- `project_nms_zabbix_snmp_cred_model` (49-train SNMP cred fix, 2026-06-08).
