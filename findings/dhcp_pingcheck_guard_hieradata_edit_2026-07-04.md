# Ready-to-apply: `ping-check false` guard for DOSTO via hieradata (no code change)

**Author:** Abbas Rizvi
**Date:** 2026-07-04
**Scope:** DOSTO only (`dostoneu_migration_mar5`) — fast unblock for the C3-style DHCP-abandon cascade. The fleet-wide template fix stays as a separate R&D ticket.
**Root cause + why-other-fleets:** `findings/dhcp_pingcheck_abandon_cascade_2026-07-04.md`
**Risk:** very low — append-only edit to an existing `literal:` block that injects into the dhcpd.conf global scope. DOSTO-only file (other envs don't have it). Verified against nd-redundancy 2.0.14 source.

---

## The edit

**File (on vmpuppet01):**
`/etc/puppetlabs/code/environments/dostoneu_migration_mar5/hieradata/files/nd_redundancy/dhcp.yaml`

**Change** — append one 4-space-indented line to the existing `literal: |-` block:

```diff
   location: /tmp/dhcp
   literal: |-
     option AP-adoption code 191 = string;
     option AP-protocol code 186 = string;
     option AP-path code 187 = string;
+    ping-check false;
```

That's the whole change. No `.deb`, no CI, no template edit.

### Why this works (confirmed in source, 2026-07-04)
- Puppet `nd_redundancy::config` (config.pp:43) writes `/etc/nd-redundancy/dhcp.yaml` from `inline_epp($nd_redundancy::dhcp)` — i.e. straight from this hieradata block.
- nd-redundancy loads all `/etc/nd-redundancy/*.yaml` into `cfg`; `generate_dhcp_base_config()` (`lib/template.py:115`) renders `dhcpd.conf.j2` with `cfg["dhcp"]`.
- The template's `{% if literal is defined %}{{ literal }}{% endif %}` sits in the **global scope**, right after `ping-timeout 2;`. So `ping-check false;` lands exactly where the code-level fix would go.
- `/etc/dhcp` is a symlink to `/tmp/dhcp` (config.pp:20) — rendered file is `/tmp/dhcp/dhcpd.conf`.

## ⚠️ Gotcha — dhcp.yaml does NOT notify the generator

Unlike `nd-redundancy.yaml` / `netconfig.yaml` / `networks.yaml` (all `notify => Exec['generate network config']`), the `/etc/nd-redundancy/dhcp.yaml` file resource in config.pp has **no notify**. So a `puppet agent -t` will update `/etc/nd-redundancy/dhcp.yaml` but **won't automatically regenerate `dhcpd.conf`** on that same run. The new global-scope line only appears when the generator next runs.

**Handle it (pick one):**
1. **Force one regen after deploy** (belt-and-braces, takes effect immediately):
   ```
   # on the CCU, after puppet agent -t has updated /etc/nd-redundancy/dhcp.yaml:
   cd /usr/share/nd_redundancy && sudo ./venv/bin/python nd_redundancy.py network
   sudo systemctl restart isc-dhcp-server
   ```
2. **Let the next reboot pick it up** — boot re-runs the generator. Aligned with the failure mode anyway (the cascade is reboot-triggered), so the guard being live-from-next-boot is acceptable if immediate effect isn't required.

(Optional hardening for the R&D ticket: add `notify => Exec['generate network config']` to the dhcp.yaml resource so hieradata DHCP edits self-apply — a config.pp one-liner, separate from the template fix.)

## Deploy steps (no repo/CI)

```
# 1. edit on the master
vmpuppet01:/etc/puppetlabs/code/environments/dostoneu_migration_mar5/hieradata/files/nd_redundancy/dhcp.yaml
   → append `    ping-check false;` to the literal: block

# 2. deploy the env to the master's live copy
ssh admin21net@vmpuppet01.ovh2.21net.com
cd /etc/puppetlabs/code/environments/dostoneu_migration_mar5 && sudo nd-update-puppetenv.sh migration_mar5

# 3. on a target CCU
sudo puppet agent -t                # updates /etc/nd-redundancy/dhcp.yaml
cd /usr/share/nd_redundancy && sudo ./venv/bin/python nd_redundancy.py network   # regen (see gotcha)
sudo systemctl restart isc-dhcp-server

# 4. verify
grep 'ping-check' /tmp/dhcp/dhcpd.conf     # expect: ping-check false;
```

## Verification the fix actually works
After it's live, the next CCU-only reboot should produce **zero** `pinged before offer` abandonments and C3 (and any peer holding its IP) should re-lease cleanly:
```
sudo journalctl -u isc-dhcp-server -b | grep -c 'pinged before offer'   # expect 0
sudo grep -c 'binding state abandoned' /tmp/dhcp/dhcpd.leases           # trends to 0 as they age to free
sudo dhcp-lease-list | grep C3                                          # nv6-C3-v8-137 with a reachable IP
```

## ✅ Bench validation — box1-t122, 2026-07-04 (PASSED)

Deployed to `migration_mar5` (commit `b0d6e08`), persisted onto the bench via **NDSU chroot** (not a fresh catalog reboot) to preserve the run2 manual state (OBN coach-numbering PoC + bug patches). Somersault `work → release → run1`; verified run1 before reboot, then rebooted to activate + exercise the cascade scenario.

| Check | Pre-reboot (run2) | Post-reboot (run1) |
|---|---|---|
| `ping-check false` in dhcpd.conf | absent | **present** ✅ |
| `pinged before offer` in boot log | 11 abandonments last boot | **0** ✅ |
| `binding state abandoned` in leases | 11 | **0** ✅ |
| Switch re-lease | — | clean, no declines/conflicts ✅ |
| OBN PoC `report_dosto_neu.py` md5 | `0e8b9d…` | `0e8b9d…` (**intact**) ✅ |
| OBN bug patches `vdsrail.py` md5 | `b01ff8…` | `b01ff8…` (**intact**) ✅ |

**Result:** the exact reboot that previously abandoned 11 switch IPs now abandons zero. Guard confirmed effective on the triggering scenario (CCU-only reboot with devices holding IPs), and the chroot-persist preserved all bench OBN work. The DOSTO-wide hieradata fix is validated; the fleet-wide template default (R&D ticket) remains the durable close for the other 418 environments.

## Scope note
This `dhcp.yaml` exists only under `dostoneu_migration_mar5` (checked: ccjpa_2026 / caltrain / tgvm have no such file). So this edit affects DOSTO only — correct for a targeted unblock. Every other fleet is still latently exposed and wants the **template-level** `ping-check false;` default (the R&D ticket), which fixes all 419 environments at once.
