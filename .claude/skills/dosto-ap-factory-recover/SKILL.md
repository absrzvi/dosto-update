---
name: dosto-ap-factory-recover
description: Recover a Westermo AP that is stuck on factory-default config AND is NOT reachable on the management VLAN (vlan100) — it sits on a factory 192.168.1.x address instead of a 10.179.x Nomad DHCP lease. Use this when an AP shows as "missing"/short-count after discovery (e.g. 23 of 24 APs present), when an NMS/Zabbix "AP cannot be pinged" alarm targets a 192.168.1.x address, when the switch port the AP hangs off is link-UP but the AP has no Nomad lease and no vlan100 presence, or when dosto-ap-config-update returns ap_unreachable / config_file_missing for an AP. This is the case dosto-ap-config-update CANNOT handle: that skill assumes the AP is already reachable on vlan100 and that OBN has rendered a per-AP config — but a factory AP on 192.168.1.x is SNMP-invisible so OBN never discovers it and never renders its config. This skill bridges that gap: reach the AP via a temporary untagged 192.168.1.x interface on the CCU's bond0, build its config by cloning an already-commissioned SIBLING AP of the SAME variant (matching the m / non-m form), push via LuCI, and verify it reboots onto Nomad config with a 10.179.x lease and working SNMP. Single AP at a time. Validated live on 4736-115 (box 6018) AP4m, 2026-06-08.
---

# DOSTO AP Factory Recovery (unreachable factory AP on 192.168.1.x)

A freshly-installed or factory-reset Westermo AP that has **never been commissioned** comes up on its factory-default address (`192.168.1.x`, typically `192.168.1.20`), not on the train's management VLAN. Because it answers nothing on vlan100, OBN's discovery never sees it — so OBN never renders a config file for it, and [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md) can't help (it needs a vlan100-reachable AP and a pre-rendered `dostoneu-obn-<mac>.cfg`). The AP just sits there as a silent "missing device": switch port link-up, but no Nomad lease, no SNMP, and an NMS ping alarm pointed at a `192.168.1.x` address that nothing can route to.

This skill is the recovery path for exactly that situation. The core trick: **you don't need OBN to discover the AP to give it a config.** You reach it directly over its factory subnet via a temp interface on the CCU, and you build its config by cloning a sibling AP that is *already* commissioned and is the *same hardware variant* — because within a variant, the rendered AP configs are identical apart from the hostname.

## When to use vs. when NOT to

**Use this skill when ALL of these hold:**
- An AP is missing from the expected count (e.g. `dosto-device-discovery` reports 23/24), AND
- The switch port it should be on is **link-up** (something is plugged in and linked — confirm via `ifOperStatus`), AND
- The device has **no Nomad DHCP lease** on `10.179.x` and is **not reachable on vlan100**, AND
- It is (or is suspected to be) on a factory **`192.168.1.x`** address.

**Do NOT use this skill — use [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md) instead — when:**
- The AP is reachable on vlan100 (has a `10.179.x` lease), even if still on factory config. That skill's LuCI bypass handles it directly and OBN can render its config.

**Stop and investigate (this is NOT a factory AP) when:**
- The switch port is **link-down** (`ifOperStatus=2`) — then nothing is plugged in, or it's a cable/hardware fault, not a commissioning gap. A port-down is a physical problem, not this.
- A non-Westermo device (OUI ≠ `00:14:5a`) is the only thing on the port — confirm what it actually is before pushing a Westermo config to it. (During the 4736-115 recovery a transient client MAC `00:26:4e` appeared in the switch FDB; the AP's real MAC `00:14:5a:04:79:b6` only showed once we ARP'd it over the temp interface. Always confirm the target is a `00:14:5a` Westermo box before pushing.)

## Why "missing AP" ≠ "port down" (read this before alarming on it)

A factory AP has **link + power**, so its switch port reads `ifOperStatus=up`. That means a port-down trigger correctly does NOT fire — and an "AP cannot be pinged" (ICMP) alarm DOES fire, against the AP's expected/stale management IP. The two together are the signature: *port up + AP unreachable on management IP* = an AP that's physically connected and powered but not commissioned. That's this skill's job. (See [`project_zabbix_switch_template_wrong_oids`] reasoning in memory: port-status alarms key on link state, ICMP alarms key on the management IP — different layers.)

## Preconditions (the skill stops if any fail)

| Precondition | Why | Verdict if missing |
|---|---|---|
| CCU SSH reachable (`developer@<ccu-ip>` with the project key) | All work runs from the CCU | `ccu_unreachable` 🔴 |
| The AP's switch port is link-UP | Confirms a device is physically present to recover | `port_down_not_factory` 🔴 (physical/cable issue, not this) |
| A commissioned **sibling AP of the SAME variant** exists on the train | The clone source. Variant (m vs non-m) MUST match | `no_sibling_variant` 🔴 |
| `sshpass`/`curl` present on CCU; CCU `bond0` exists | temp-interface + LuCI push | `tooling_missing` 🔴 |

## The procedure

The skill walks five stages. Default `--prepare` mode is read-only (probe + print the recipe); `--execute` drives it with engineer approval at the one destructive gate (the LuCI apply that reboots the AP).

### Stage 1 — Reach the AP over a temporary factory-subnet interface

The factory AP's `192.168.1.x` rides the **untagged/native VLAN** on its switch port (the AP-trunk port config includes VLAN 1). The CCU reaches it by adding a temp **untagged** address on **bond0** — NOT vlan100, NOT a tagged vlan1 subinterface (those don't land on the native VLAN; this is the same in-band native-VLAN technique used for unreachable switches, see [`project_native_vlan1_inband_reach_miscable`] in memory).

```bash
sudo ip addr add 192.168.1.2/24 dev bond0     # temp, untagged
ping -c2 -W2 192.168.1.20                       # confirm reach (adjust IP if the AP is elsewhere in 192.168.1.x)
ip neigh show 192.168.1.20 dev bond0            # CONFIRM the MAC is Westermo (00:14:5a). Abort if not.
```

The temp interface is removed in Stage 5 regardless of outcome — never leave it on bond0.

### Stage 2 — Identify the AP and its variant (m vs non-m)

This is the step that prevents pushing the wrong config. The variant determines which sibling to clone from:
- **m-variant** (`AP*m-v1`) = dual-radio (both `wlan0` 5GHz AND `wlan1` 2.4GHz).
- **non-m** (`AP*-v1`) = single radio.

Read the factory AP's radios via LuCI to settle it (factory login is often `admin/admin`, not the Nomad password — try both; the IbexOS factory variant titles itself `Rmodem`, not always `RT610LV-...-FD`):

```bash
# factory login (try admin/admin first, then Nom@dCome1n)
curl -sk -c /tmp/ck.txt -b /tmp/ck.txt -X POST "https://192.168.1.20/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=admin" -o /dev/null -w "%{http_code}\n"
# read wireless: count radios
curl -sk -c /tmp/ck.txt -b /tmp/ck.txt \
  "https://192.168.1.20/cgi-bin/luci/admin/status/general/data?view=wireless"
# wlan0 AND wlan1 present  -> m-variant
# wlan0 only               -> non-m
```

Also derive the AP's intended role/position from the switch port it's on (e.g. B3 `e1-2` = "AP B4" / AP4 in coach B per `references/nv6-topology.md`), to sanity-check which sibling to pick. The AP's role number (AP1/2/3/4) plus variant together pick the sibling.

### Stage 3 — Build the config by cloning a same-variant sibling

OBN cannot render a config for an undiscovered AP — so clone one it already rendered for a **commissioned sibling of the same variant**. Within a variant the rendered configs are **identical except the `hostname` line** (validated: the two AP4m configs on 6018 differed by 0 lines ignoring hostname). So:

```bash
# find same-variant siblings from the DHCP leases (e.g. AP4m-v1 for an m-variant AP4)
sudo dhcp-lease-list | grep -iE "AP4m-v1"     # -> pick one, note its MAC slug
# its rendered config:
SIB=/data/auto-topology/upload/dostoneu-obn-<sibling-mac-slug>.cfg
# build target config: swap ONLY the hostname to the recovering AP's MAC
sudo sed "s/AP4m-v1-<sibling-slug>/AP4m-v1-<target-slug>/g" "$SIB" > /tmp/dostoneu-obn-<target-slug>.cfg
diff <(sudo cat "$SIB") /tmp/dostoneu-obn-<target-slug>.cfg   # MUST show only the hostname line(s)
```

If no same-variant sibling is commissioned yet, stop (`no_sibling_variant`) — do not clone across variants (m vs non-m radio config differs).

The bundled helper does Stages 2–3 mechanically: `scripts/build_ap_config.sh <target-mac-slug> <sibling-mac-slug>` (prints the diff and refuses if more than the hostname changed).

### Stage 4 — Push via LuCI (GATE: this reboots the AP)

This is the one destructive action — get engineer approval in `--execute`. Factory login uses `admin/admin` (or whatever Stage 2 found). Three steps: login → import (stages pending) → apply (reboots ~60–90s).

```bash
IP=192.168.1.20; CFG=/tmp/dostoneu-obn-<target-slug>.cfg
# 1. login
curl -sk -c /tmp/ck.txt -b /tmp/ck.txt -X POST "https://$IP/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=admin" -o /dev/null -w "login=%{http_code}\n"   # expect 302
# 2. import (stages as pending "Verify" page; the cfg diff is shown — confirm hostname + snmp version 0->1)
curl -sk -c /tmp/ck.txt -b /tmp/ck.txt -X POST "https://$IP/cgi-bin/luci/admin/system/flashops" \
  -F "config=@${CFG};type=text/plain" -F "Import=Import Configuration" -o /tmp/imp.html -w "import=%{http_code}\n"  # expect 200
# 3. apply (reboots). The flashops apply uses config_apply=1:
curl -sk -c /tmp/ck.txt -b /tmp/ck.txt -X POST "https://$IP/cgi-bin/luci/admin/system/flashops" \
  -d "config_apply=1" -o /tmp/app.html -w "apply=%{http_code}\n"   # expect 200; page may say "applying now"
```

**Gotchas observed live:** the apply response page can show a transient `Config apply failed!` string *and* `applying now` simultaneously — don't trust the page text. The real signal is that the AP goes unreachable (a follow-up `rpcCfgApply` returning HTTP `000` = connection refused = it's rebooting = good). Verify by outcome (Stage 5), not by the apply page. The `rpcCfgApply` JSON POST (`{"key":"rpcCfgApply","value":1}` to `/cgi-bin/luci/admin/rpc`) is a belt-and-braces alternative if the flashops apply doesn't trigger.

### Stage 5 — Verify recovery and clean up

Verify by **outcome**, polling for the AP to return on Nomad config (this is the goal-driven success criterion, not the apply HTTP code):

```bash
# poll ~90s for a Nomad DHCP lease on the AP's MAC (10.179.x, hostname AP*m-v1 / AP*-v1)
sudo dhcp-lease-list | grep -i "<target-mac>"     # want: 10.179.x ... AP4m-v1...
# SNMP now answers on Nomad v3 creds (the real proof OBN can manage it):
#   v3 / user=admin / SHA / AES / authPriv / passphrase NomadStayOut!  (NOT a v2c community)
snmpget -v3 -l authPriv -u admin -a SHA -A 'NomadStayOut!' -x AES -X 'NomadStayOut!' -Oqv <new-ip> 1.3.6.1.2.1.1.5.0
# expected AP count restored (e.g. 24/24):
sudo dhcp-lease-list | grep -c "00:14:5a"
```

**Always** remove the temp interface, success or fail:
```bash
sudo ip addr del 192.168.1.2/24 dev bond0
ip addr show bond0 | grep 192.168.1 || echo "clean"
```

## After recovery — follow-ups (surface these, don't silently skip)

- **NMS/Zabbix stale target — self-heals, then lingers briefly. Do NOT hand-edit the host IP.** The AP's Zabbix host was pinging the old `192.168.1.x`. NMS re-syncs the Zabbix host interface IP from the new DHCP lease **automatically** (an NMS batch task — all AP hosts are `useip=1` with the current `10.179.x` lease; the AP's DHCP IP floats on 2-min leases so a static IP would just go stale — don't pin one). Validated 2026-06-08: the host IP self-corrected `192.168.1.20` → `10.179.18.241` without intervention.
  - **Expect the "cannot be pinged" alarm to LINGER for a few minutes after recovery, even once the host IP is correct.** Cause: the Zabbix **proxy** can't yet ICMP the freshly-rebooted AP (its ARP/forwarding path to the new lease hasn't converged) — note the CCU *can* ping it the whole time, so the AP is healthy; it's purely proxy-side convergence. Fix = wait + force a re-poll, NOT a config change: `task.create [{type:6, request:{itemid:<icmpping itemid>}}]` (execute-now) on the host's `icmpping` items, then recheck after ~1–3 min. The trigger auto-resolves once `icmpping=1`; no manual acknowledge/close needed. (On 6018 it cleared within ~1 min of the re-poll.)
- **OBN re-inventory.** Run `sudo obn discover` next time the train is up so OBN records the now-commissioned AP (and can render its own config going forward instead of the cloned one).
- **Firmware.** Once on Nomad config + SNMP, `dosto-ap-firmware-update` can bring it to target firmware if needed.

## Credentials & facts (load-bearing)

- CCU SSH: `developer@<ccu-ip>` with `openssh` key in the project root.
- **AP SNMP (Nomad):** v3, user `admin`, SHA auth + AES priv, authPriv, passphrase `NomadStayOut!` for BOTH auth and priv. `NomadComeIn` is the SSH/GUI password, **never** an SNMP credential. (Switches use SNMP user `snmpadmin`; APs use `admin` — inverted. See [`project_nms_zabbix_snmp_cred_model`].)
- **LuCI factory login:** `admin/admin` on the IbexOS `Rmodem` factory variant; some factory images use `admin/Nom@dCome1n`. Try both. After Nomad config: SSH CLI `nomad`/`NomadComeIn`.
- **Rendered configs** live at `/data/auto-topology/upload/dostoneu-obn-<macslug>.cfg` (MAC lowercase, no colons).
- **Topology** (which port = which AP role): `references/nv6-topology.md` / `nv4-topology.md` (also under `train-ip-allocation-commission/extracted/_shared/`).

## Relationship to other skills

- [`dosto-device-discovery`](../dosto-device-discovery/SKILL.md) surfaces the missing-AP count that triggers this skill.
- [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md) is the sibling skill for factory APs that ARE reachable on vlan100; once this skill gets the AP onto Nomad config, normal `obn update c` / that skill apply.
- [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md) runs after, for firmware.
