# DHCP `ping-check` abandons switch IPs on every CCU-only reboot → stranded switches (C3 on 4736-109)

**Author:** Abbas Rizvi
**Date:** 2026-07-04
**Observed on:** 4736-109 / Fzg 137, CCU box1-t28 (`10.179.28.1`), nd-obn 2.2.23
**Component:** CCU `isc-dhcp-server` config (Puppet-rendered `/etc/dhcp/`)
**Status:** root cause confirmed; guard proposed (not yet deployed)

---

## 1. Symptom

Switch **C3** (`a0:59:3a:d0:62:a0`, `nv6-C3-v8-137`) is healthy and forwarding on the data plane (C2 e0-0→C3 UP 10G, RX 9.9 GB / TX 280 GB, 0 CRC) but has **no working management IP**:
- Not in `dhcp-lease-list`; DHCP server has **never** logged its MAC.
- LLDP-advertises mgmt addr `10.179.28.189`, but `.189` is **unreachable** (ICMP 100% loss, ARP INCOMPLETE, arping 0 replies).
- Invisible to the CCU sweep and to NMS/Zabbix (no host provisioned) → part of the 16/18 monitoring blind spot.

## 2. Root cause — `pinged before offer` abandonment cascade after a CCU-only reboot

The CCU rebooted ~18:22 today (all `/etc/dhcp/` files re-rendered 18:22–18:25). ISC `dhcpd` defaults to **`ping-check true`**: before offering a pool address it ICMP-pings it and, if anything answers, marks it **abandoned**.

On a **CCU-only reboot the switches never rebooted** — they hold their prior IPs in RAM. So dhcpd came up cold, ping-checked each pool address, got a reply from the switch still using it, and abandoned it. Log evidence (18:23):

```
dhcpd: Abandoning IP address 10.179.28.197: pinged before offer
dhcpd: Abandoning IP address 10.179.28.195: pinged before offer
... 14 addresses total (.181 .189 .195 .196 .197 .198 .199 .200 .201 .202 .203 .205 .206 .207)
```

The `.189` lease record confirms the mechanism:
```
lease 10.179.28.189 {
  binding state abandoned;
  client-hostname "nv6-C2-v8-137";   ← C2 previously held .189; it drifted to .193, .189 abandoned
}
```

Most switches limp onto a *different* free address after their old one is abandoned. **C3 is the one that got stranded** — its RAM-held `.189` was abandoned server-side, and it has not completed a fresh DISCOVER since. Result: a healthy switch with a dead mgmt IP.

**This is deterministic and recurs on every CCU reboot** — not a one-off. It's the mechanism behind the recurring "restart dhcpd to let switches complete" band-aid already noted in `.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp.md` and the `zabbix-switch-icmp-dhcp-drift` finding.

## 3. Immediate remedy (per-incident band-aid — do NOT rely on this)

```
sudo systemctl restart isc-dhcp-server     # clears the ping-abandon state; frees the 14 addresses
sudo journalctl -u isc-dhcp-server -f | grep d0:62:a0   # watch C3 re-lease
sudo dhcp-lease-list | grep C3             # expect nv6-C3-v8-137 with a fresh, reachable IP
```

Restart is non-disruptive to the data plane (switches keep forwarding; only DHCP renewals pause briefly).

## 4. The guard (permanent, fleet-wide) — disable `ping-check`

The ping-check exists to avoid handing an address to an *unknown* host already using it. On the DOSTO management VLAN the only "conflict" it ever detects is **the legitimate owner holding its own IP across a CCU reboot** — so the check does net harm. Disable it:

```
# global scope of the Puppet-rendered dhcpd.conf / include.conf
ping-check false;
```

Effect: on the next CCU reboot dhcpd offers each address straight back to the same device (matched by client-id/MAC) instead of abandoning it. No cascade, no stranded switches.

**Where — traced to the actual source (2026-07-04, on vmpuppet01):** `/etc/dhcp/dhcpd.conf` is NOT rendered by a Puppet template. The Puppet class `nd_redundancy::config` writes `/etc/nd-redundancy/*.yaml` then runs `python nd_redundancy.py network`, and **that generator (`/usr/share/nd_redundancy/nd_redundancy.py`, shipped in the `nd-redundancy` .deb) is what emits `/etc/dhcp/dhcpd.conf` + `include.conf` + `networks/*.conf`.** `nd_redundancy` also owns the `isc-dhcp-server` package. So:

- ❌ A Puppet-env template edit won't work — the env has no dhcpd.conf template (confirmed: only `nd_redundancy` manifests reference `/etc/dhcp`, none render the body).
- ❌ A hand-edit to `/etc/dhcp/dhcpd.conf` on the CCU is wiped whenever `nd_redundancy.py network` re-runs (Puppet notifies it on any network-yaml change, and on boot).
- ✅ **The guard is a code change in the `nd-redundancy` package's DHCP-config generator** — add `ping-check false;` (and confirm `authoritative;`) to the **global scope** it writes into `dhcpd.conf`. Deploy via the .deb → apt-repo (vmrepo01) → Puppet version-pin chain, same shape as nd-obn (memory `project_obn_deb_publish_process` + `project_puppet_deploy_chain_vmpuppet01`).

**This is a SHARED Nomad-Connect component.** `nd-redundancy` is the common HA-DHCP layer used across fleets (not DOSTO-specific), so the fix protects every fleet at once — see §4b. Scope the change as a global-scope default (harmless to any fleet); no per-fleet hieradata needed. Raise it as an R&D ticket against `nd-redundancy` (owner: the Nomad-Connect / 2SD team that owns ND Redundancy).

### Supporting settings (verify, don't necessarily change)
- **`authoritative;`** on the management subnet — so a drifted device gets a fast DHCPNAK back onto a correct lease rather than clinging to a stale IP. (Usually already set; confirm.)
- Lease time is already short (switch pool `.178–.208`, ~2 min observed) — fine; no change needed.

### 4b. Fleet-wide audit (vmpuppet01, 2026-07-04)

Checked all **419 Puppet environments** on the master: **`ping-check` is set in ZERO of them.** Every Nomad fleet (DOSTO, CCJPA, TGVM, CAF Regiolis, CFL, DANI, Amtrak, Caltrain, …) runs ISC `dhcpd` with the default `ping-check true` and is therefore susceptible to the same abandonment cascade on a CCU-only reboot. DOSTO is merely where it was caught, because we actively monitor switch-level reachability.

**Confluence:** no page documents `ping-check` at all (CQL `text ~ "ping-check"` → 0 real hits across the wiki). There is no existing best-practice guard to reference — this would be the first. The relevant existing pages are the fleet "IP scheme / backbone layout" pages (all say "devices lease dynamically from the CCU DHCP server", none mention ping-check) and the **ND Redundancy** page (space 2SD, id 3016097799), which confirms `nd-redundancy` owns the on-CCU DHCP server. That page/team is the right home for documenting the guard once shipped.

## 4c. Exact patch location (traced in nd-redundancy 2.0.14, the bookworm/DOSTO version)

The dhcpd.conf global scope is a Jinja2 template shipped in the .deb: **`/etc/nd-redundancy/template/dhcpd.conf.j2`**, rendered by `generate_dhcp_base_config()` in `lib/template.py:115`. Current body:

```jinja
ddns-update-style none;
authoritative;
log-facility local6;
default-lease-time 1800;
one-lease-per-client on;
ping-timeout 2;                 ← ping tuning was deliberately touched…
{% if literal is defined %}{{ literal }}{%- endif %}
include "{{ location }}/include.conf";
```

**Surprise:** `ping-timeout 2;` is explicitly set but **`ping-check` is left at its default `true`.** So the ping-before-offer behaviour isn't an untouched default — it's half-configured (someone tuned the timeout but not the check). The fix is one line next to it:

```jinja
ping-timeout 2;
ping-check false;               ← ADD
```

(There is also an `{% if literal is defined %}{{ literal }}{% endif %}` hook fed by hieradata `dhcp.literal`, so `ping-check false;` could be injected per-fleet without a code change — but the correct fix is the template line, since it's the right global default for every fleet.)

`authoritative;` is already present (both global and per-subnet in `dhcp_pool.conf.j2`) — no change needed there.

## 4d. Why other fleets don't visibly hit this (same template, same `ping-check true`)

Every fleet renders the SAME `dhcpd.conf.j2` with `ping-check` defaulting on — so the bug is fleet-wide and latent. DOSTO is where it becomes *visible and repeatable* because its device/ops profile uniquely triggers the abandonment:

1. **VDS switches persist their IP across a CCU-only reboot and keep answering ICMP.** dhcpd restarts cold, ping-checks the address, the VDS switch is still sitting there answering → abandoned. Other fleets' backbone gear (MEN NM31, Lantech, Westermo/Eltec, WING-AP) largely re-DHCP from scratch or don't hold-and-answer the same way, so the ping-check finds the address free and offers normally.
2. **`one-lease-per-client on;`** (in the same global scope) worsens it: the client can't cleanly slide onto a different address when its held one is abandoned → it gets stranded rather than re-homed.
3. **DOSTO packs the switch pool tight (18 sw + 24 AP) and reboots the CCU often** (v8 rollout, power-cycles, factory-ups). One CCU-only reboot with all devices holding IPs = a 14-address cascade. A fleet with fewer backbone devices, or whose CCU rarely reboots independently of the consist, abandons 0–1 and self-heals before anyone notices — same latent bug, below the detection threshold.
4. **DOSTO actively monitors switch-level reachability** (this workstream), so a stranded switch surfaces; elsewhere it'd be an unnoticed blip.

**Conclusion for the ticket:** other fleets aren't immune, they're under the threshold. The `ping-check false` fix is a shared-component hardening that removes the cascade for everyone, and is strictly correct even where it's currently latent.

## 5. Residual cleanup after the guard ships
The guard prevents *new* abandonment but doesn't clear the 14 already-abandoned records. One dhcpd restart (or letting them age to `free`) clears them once. After that, reboots are self-healing.

## 6. Detection (so we don't rediscover this by hand each time)
Add to the auto-scanner / morning-brief a cheap check:
- `grep -c 'binding state abandoned' /etc/dhcp/dhcpd.leases` > 0, **or**
- `journalctl -u isc-dhcp-server | grep 'pinged before offer'` in the last boot, **or**
- discovered switch count < expected AND the missing position advertises a mgmt IP via a neighbour's LLDP that is itself unreachable (the C3 signature: alive on data plane, dead mgmt IP).

Any of these → flag "DHCP abandonment cascade — restart dhcpd / confirm ping-check guard deployed."

## 7. Cross-references
- `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md` — the *other* half of the 4736-109 16/18 blind spot (E2 cold-bypass). C3 here is the DHCP-abandon half.
- `.kb/evidence/native-vlan1-coupler-bridge-breaks-dhcp.md` — prior "restart dhcpd to let switches complete" observation (same band-aid).
- `findings/zabbix_switch_icmp_dhcp_drift_2026-06-09.md` — the NMS-alarm symptom of DHCP drift; this doc is the server-side mechanism.
