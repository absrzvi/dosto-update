# Live iptables validation — all 4 fleet families

**Captured:** 2026-06-01, via `sudo iptables-save` (backend = nf_tables, iptables v1.8.9).
**Purpose:** validate the L3 Firewall Matrix (Tab 3) of `DOSTO_NEU_Network_Communications_Matrix` against ground truth on every consist family.

| Family | CCU | Box | Fzg | Raw dump |
|---|---|---|---|---|
| 4736 nv6 (NV 6-car) | 10.179.21.1 | box1-t21 | 146 | [t21](iptables-save_box1-t21_20260601.txt) |
| 4736 nv6 (NV 6-car) | 10.179.47.1 | box1-t47 | 130 | (structure-checked) |
| 4734 nv4 (NV 4-car) | 10.179.39.1 | box1-t39 | 11 | [t39](iptables-save_box1-t39_20260601.txt) |
| 4706 (FV 6-car) | 10.179.15.1 | box1-t15 | 190 | [t15](iptables-save_box1-t15_20260601.txt) |
| 4705 fv5 (CAT 5-car) | 10.179.42.1 | box1-t42 | 229 | [t42](iptables-save_box1-t42_20260601.txt) |

## Verdict: the core firewall is FLEET-COMMON across all 4 families (Puppet-driven, default-DROP, same zone chains). 6 corrections + several enrichments found; 2 family-specific deltas.

### Cross-family structural diff (filter table, train-IPs normalised)

All 4 families share: `INPUT DROP / FORWARD DROP / OUTPUT ACCEPT`; the zone chains `PASSENGER_INPUT/FORWARD`, `MGMTI/F`, `FISI/F`, `PDA1I/F`, `MAR3TUNI/F`, `VENI/F`, `LAN2I`; RFC1918-drop-before-Internet; captive-portal DNAT; QoS/TOS marking. **vlan10 = /22 on all 4.** `nf_conntrack_tftp` NOT loaded on any of them.

Real differences found:
1. **4705 (CAT, fv5): vending VLAN is 48, not 47.** nv4 + nv6 bind `VENI/VENF` to vlan46 **+ vlan47**; the CAT 5-car binds them to vlan46 **+ vlan48** (no vlan47 interface). So the earlier "vlan47/48 mislabel" is actually **family-dependent**: NV/FV-6 use 47, CAT-5 uses 48. (Both also keep vlan48-or-47 as an unused SVI.)
2. **VLAN-7 forward wide-open on 2 of 6 sampled trains — TRAIN-SPECIFIC, runtime-injected, NOT nv4-wide and NOT design.**
   Follow-up survey of 5 nv4 CCUs (2026-06-01):
   | Box | Fzg | VLAN-7 FORWARD |
   |---|---|---|
   | box1-t39 | 11 | ⚠ `-o vlan7 ACCEPT` + `-i vlan7 ACCEPT` (rules #2/#3) **then** `FISF` (#14) |
   | box1-t37 | 12 | ⚠ same — stray ACCEPTs on top of FISF |
   | box1-t49 | 20 | ✅ `FISF` only (RFC1918-drop, = nv6 baseline) |
   | box1-t50 | 21 | ✅ `FISF` only |
   | box1-t61 | 15 | ✅ `FISF` only |
   - The design/Puppet baseline is the **`FISF` RFC1918-drop chain** (every box has FISF with 4 rules). nv6 boxes match this.
   - On t39 & t37 two stray `FORWARD … vlan7 … ACCEPT` rules sit at the **top** of FORWARD (before FISF). iptables is first-match → the ACCEPTs win → **VLAN-7 forwarding is unconditionally open in both directions, bypassing the RFC1918 drops.**
   - These rules are **runtime-only**: present in the live nft ruleset but **absent from `/etc/iptables*`, `/etc/nftables*`, `/etc/network*`** → they would not survive a reboot / Puppet re-apply. Signature of a **manually-injected debug rule left behind** (`iptables -I FORWARD … vlan7 … ACCEPT`), not a manifest difference.
   - ⚠ **Security observation (operational, not a matrix item):** on Fzg 11 & 12 the Stadler VLAN-7 transit can currently forward to RFC1918 (10/8, 172.16/12, 192.168/16) that the design intends to drop. Not a customer-matrix change — the matrix correctly documents the intended FISF posture.
   - ✅ **REMEDIATED 2026-06-01:** flushed the stray rules on both boxes via `sudo iptables -D FORWARD -o vlan7 -j ACCEPT` + `-D FORWARD -i vlan7 -j ACCEPT` (box1-t39 / 10.179.39.1 and box1-t37 / 10.179.37.1). Before-snapshots: `findings/forward-before_box1-39_*.txt`, `findings/forward-before_box1-37_*.txt`. After flush both FORWARD chains start at `ACC_IN` (= nv6 baseline), FISF active, established/related rule intact, default DROP, vlan7 ARP to Stadler FW still REACHABLE (t39: 172.19.133.129 confirmed). These rules were runtime-only (not in `/etc`), so the fix is also self-healing on next reboot/Puppet run. Rollback if ever needed: `iptables -I FORWARD 1 -o vlan7 -j ACCEPT; iptables -I FORWARD 2 -i vlan7 -j ACCEPT`.
3. **4706 (Fzg 190)** lacks the vlan32 Diagnostics chain and the passenger blocking-page rule, and has fewer cellular modems populated (ce0/ce2 only) — a reduced/earlier ruleset, not a contradiction.
4. **4706 (Fzg 190) vlan7 IP is stale/misimaged:** live `172.19.199.130/17` decodes to Fzg 142 (odd), but the train is Fzg 190 (even, expected `172.19.223.2`). Classic pre-commissioning wrong-`train_id` symptom — the formula is correct, the live box isn't yet fixed. Confirms the "never trust live vlan7 pre-commissioning" rule.

---

## (Detail below is from the box1-t21 / Fzg 146 baseline)
## Verdict: matrix is directionally correct; live ruleset is more precise. 6 corrections + several enrichments found.

---

## ✅ Confirmed exactly as the matrix / SDD state

| Matrix claim | Live evidence |
|---|---|
| Default policy = DROP on INPUT and FORWARD | `:INPUT DROP`, `:FORWARD DROP` (filter table) |
| OUTPUT = (unstated) | `:OUTPUT ACCEPT` — **add to matrix** |
| Passenger VLANs may never reach RFC1918 | `PASSENGER_FORWARD` drops 10/8, 172.16/12, 192.168/16 (lines 204-206) |
| Passenger client isolation + captive portal | `PASSENGER_INPUT` allows only 53/80/443 tcp + 53/67 udp, else DROP (210-212); unauthorised mark 0xffffffff → DROP (203); DNAT :80 → portal 192.168.208.1 (244) |
| CCU = DHCP/DNS/NTP server | `PASSENGER_INPUT`/`PDA1I`/`MGMTI` accept 53,67,123 |
| Management VLAN is the broadest | `MGMTI` allows 8005, ICMP, 21/22/53/80/443, SNMP 161, OBN REST 1800, Train-Info 1818, MAR3 7070, Zabbix 10050/1, NTP/VRRP, FreeRadius 1812-4, tftp/69, redundancy 5000 |
| VLAN 7 (Stadler transit) drops private dests, allows rest | `FISI`/`FISF`: src 172.19.128.0/17 → DROP to 10/8,172.16/12,192.168/16, ACCEPT rest (169-176) |
| Stadler→Internet is NAT'd via CCU | `POSTROUTING -s 172.19.128.0/17 -o mar5-tun MASQUERADE` (263) |
| No direct Internet; all via MAR5 tunnel | egress only on `ce0p0/ce1p0/ce2p0/ce3p0` (cellular) + `mar5-tun`; RFC1918 dropped before Internet (119-134) |
| Staff (vlan30) gets Eng-Page/GPS/NTP | `PDA1I` allows 123, 8005, 2947, 53/80/443, 53/67 udp, ICMP (217-223) |
| NTP relay for Stadler / engineering svcs | DNAT on vlan30 + bond0 for 53/123/8005/2947 (245-254) |

---

## ⚠ Corrections to make to the matrix (Tab 1 / 2 / 3)

1. **vlan10 (1st class) live mask is `/22`, not `/20`.**
   Live: `vlan10 192.168.208.1/22` and FORWARD rules use `192.168.208.0/22`. Matrix Tab 1/2 say `192.168.208.0/20`. The SDD itself says /20 in one place and /22 in the Network tab — **live wins: /22**. (2nd-class 192.168.224.0/20 not verifiable here — vlan20 not instantiated on this train.)

2. **vlan30 (staff) source range is `10.205.{train}.0/24` — confirmed `/24`** (PDA1F `10.205.21.0/24`). Matrix correct. ✓ (kept for completeness)

3. **The "vending payment" VLAN is 47, not 48, on this train's ruleset comments.**
   Lines 229-233: rules for `192.168.47.0/24` are commented *"vlan 48"* (a label bug in the ruleset), and **vlan48 has no FORWARD chain at all** — only vlan46 and vlan47 jump to `VENF`/`VENI` (100-101, 117-118). So on Fzg 146 the **active vending VLANs are 46 and 47**; 48 is defined as a CCU interface (`192.168.48.1/24`) but carries no firewall rules. Matrix Tab 1 lists 46/47/48 — **flag that 48 may be unused / mislabelled in firmware**.

4. **ICMP to the CCU is allowed on more VLANs than the matrix implies.**
   Matrix marks ICMP INPUT `deny` for passenger (correct — not in PASSENGER_INPUT) but `MGMTI`, `PDA1I` (staff), `DIAGNOSTICI`, `DOCKERI` all explicitly ACCEPT ICMP type-8. So ICMP-to-CCU is allowed from management, staff, diagnostics, docker — matrix's per-VLAN ICMP column should reflect this.

5. **There is a dedicated DIAGNOSTIC zone on `vlan32` not in the matrix at all.**
   `vlan32` → `DIAGNOSTICI/F`, allows gpsd 2947, ICMP, NTP 123, DNS 53, Eng-Page 8005 (142-147). vlan32 is not in the design-freeze VLAN list. **Add as "Diagnostics" VLAN (Nomad).**

6. **MQTT/GPS/CPAPI etc. are CCU-internal (Docker) services, reached through the tunnel — not passenger/Stadler-facing.**
   `DOCKERI` (158-168) allows 25(SMTP),53,1816(GPS),1820(CPAPI),1883(MQTT),8883(MQTTS),6001/6002(MA API),8443. `DOCKERF` allows 80/443 portal. Matrix Tab 3 MQTT column is fine as "management/tunnel only" but the **ports list should cite 1883/8883 + the MA-API ports**.

---

## ➕ Live-only detail worth adding (enrichment, not in any design doc)

- **QoS / TOS marking — validated fleet-wide 2026-06-01** (6 CCUs: nv6 t21, nv4 t39/t49/t50, 4706 t15, 4705/fv5 t42). The mangle-table `--set-tos` values are **identical on every train and every family**:

  | Class chain | Matched by | TOS byte | DSCP (TOS≫2) | 802.1p CoS | Status |
  |---|---|---|---|---|---|
  | `TOS_MANAGEMENT` | subnet `10.<proj>.<train>.128/25` (mgmt, src+dst) | `0xe0` | **CS7 (56)** | 7 | ✅ ACTIVE (subnet-matched) |
  | `TOS_STAFF` | subnet `10.205.<train>.0/24` (staff) | `0xc0` | **CS6 (48)** | 6 | ✅ ACTIVE (subnet-matched) |
  | `TOS_GOLD` | ipset `tos_gold` | `0x40` | **CS2 (16)** | 2 | ⚠ defined but ipset EMPTY (0 members, all CCUs) |
  | `TOS_CF1` | ipset `tos_cf1` | `0x40` | **CS2 (16)** | 2 | ⚠ defined but ipset EMPTY |
  | `TOS_SILVER` | ipset `tos_silver` | `0x20` | **CS1 (8)** | 1 | ⚠ defined but ipset EMPTY |
  | `TOS_CF2` | ipset `tos_cf2` | `0x20` | **CS1 (8)** | 1 | ⚠ defined but ipset EMPTY |

  Key correction to earlier note: only **management and staff are actually marked today** — they match by explicit subnet. **gold/silver/cf1/cf2 are `hash:ip` sets (static, no timeout) with 0 members on every CCU checked** → those tiers are scaffolded but unused (nothing is currently classified gold/silver). The framework exists; the passenger/service-tier classification is not yet populated. So the *marking scheme* is frozen-able (4 CS classes), but the *VLAN/host→gold-or-silver assignment* is not defined on the live fleet.
- **Per-modem egress**: 4 cellular interfaces `ce0p0..ce3p0`, each MASQUERADE'd, each with the RFC1918-drop-then-accept Internet pattern. (bond0 aggregates them.)
- **MAR5 tunnel interface = `mar5-tun`**; `MAR3TUNI` accepts ALL from tunnel; `MAR3TUNF` only forwards to mgmt net. Backend-initiated mgmt confirmed.
- **VPN return-traffic rule (RD-9860)**: `MGMTF` permits onboard→VPN `192.168.69.130` on 22/443/ICMP — a specific R&D ticket rule.
- **Docker DNAT**: host :5000→portal-collector 172.15.0.2, :443→172.15.0.3 (portal). Two containers.
- **`lan2` zone** (`LAN2I`): SSH 22 + ICMP — a wired service LAN; allows engineer laptop access.
- **Blocking/redirect page**: vlan20 DNAT of public IPs 198.251.90.72 / 45.54.28.15 → 172.16.192.5 (filter-block landing page).

## ⚠ Operational note (not a matrix item)
- **`nf_conntrack_tftp` is NOT loaded** on this CCU right now — the documented TFTP-helper gap. The `MGMTI` tftp/69 ipset rule (line 199) is present but the conntrack helper that makes the TFTP data channel work is absent. Consistent with [[project_tftp_conntrack_helper]]. AP firmware batch pushes will silently fail until `modprobe nf_conntrack_tftp` + CT helper rule are (re)applied.
- **Per-train caveat**: only VLANs 7,10,30,46,47,48,100 are instantiated on Fzg 146. vlan20/31/131/150/200/202/90 are in the design but **not present as CCU interfaces on this train** — likely because no devices/SSIDs for them are provisioned here. The matrix is the fleet *design*; any single train may instantiate a subset.
