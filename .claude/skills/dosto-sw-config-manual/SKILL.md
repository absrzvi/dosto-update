---
name: dosto-sw-config-manual
description: Push VDS Rail Consist Switch config via raw TFTP+SNMP, fully bypassing OBN. Use when OBN's config push has FAILED — `obn update c sw all` hangs, or `obn update c <ip>` silently no-ops (exits 0, switch stays on old config) — and switches must still be brought to their target v8 config. Replicates OBN's own push mechanism (render cfg via OBN's Jinja env → stage in TFTP dir → SNMP set-location + trigger → poll load → hostname-commit → SNMP reboot → verify), one switch at a time, head-of-train LAST. Runs the actual push DETACHED on the CCU (setsid) so a flaky cellular link can't interrupt a 10-15 min multi-switch run. Default --prepare mode is read-only (confirms OBN really failed, renders + validates configs, prints the recipe); --execute launches the detached pusher. This is the OBN-independent fallback to dosto-sw-config-update / dosto-sw-config-update-batch (which both wrap OBN). Config only — firmware manual push (sysadmin load .kad) is a different mechanism. Validated box1-t41 / Fzg 231 / 2026-07-07 (11 switches after OBN hung) and Fzg 123 bench 2026-05-21.
---

# DOSTO Switch Config Update — Manual (OBN bypass)

Pushes v8 config to VDS Rail Consist Switches via **raw TFTP + SNMP**, replicating
what OBN does internally — but without OBN. This is the fallback for when OBN's
config-push path is broken on a consist.

**Config only.** Switch firmware uses a different mechanism (`sysadmin load <img>.kad`
over the switch CLI) — see memory `project_vds_sysadmin_load_blocked_by_ttcmp_critical`.

## When to use — OBN must have actually FAILED first

Do NOT reach for this by default. The normal path is
[`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md) (single) or
[`dosto-sw-config-update-batch`](../dosto-sw-config-update-batch/SKILL.md) (parallel),
both of which drive `obn update c`. Use this skill only when OBN's push has
demonstrably failed on the consist, in one of these two ways:

1. **`obn update c sw all` hangs** — the process runs but logs no `updating
   configuration on...` lines and moves zero switches for minutes, with no child
   ssh/tftp/snmp process (blocked inside Python). Killing + re-running hangs the
   same way.
2. **`obn update c <ip>` silently no-ops** — exits 0, prints nothing, switch stays
   on its old config. (Distinct from the empty-target no-op that a missing
   `obn report` causes — here the switch IS in the report snapshot with a correct
   `target_config`, verified via `obn validate`, and it *still* won't push.)

Both were hit on box1-t41 (Fzg 231, nd-obn 2.3.6, fv5) 2026-07-07 — OBN patched
11/11, positions correct via `obn validate`, targets correct, discovery fresh, and
`update c` still failed in both modes. Manual push then brought all switches to
v8-231 cleanly.

`--prepare` mode's first job is to **confirm OBN really failed** (see below) so this
skill isn't used to paper over a fixable OBN issue.

## Preconditions (verify in --prepare)

- **OBN positions are correct.** `obn validate` must show each switch mapped to the
  right coach/device with the right `target_config`. If positions are scrambled,
  STOP — pushing a wrong-position template cements a wrong config. Cross-check
  against the physical LLDP ring (`scripts/lldp_from_discovery.py` /
  `scripts/fv5_ring_positions_t41.py`) — a degree-2 ring anchored at the CCU-facing
  switches (port 5 → `.1`) is normal for fv5; it is NOT miscabling (verified
  identical on healthy box1-t42).
- **train_id hardcode present** (for Fzg > 127 box=Fzg trains): templates must carry
  `{%- set train_id = <Fzg> -%}` or hostnames render the box-id, not the Fzg. See
  `dosto-fzg-id-check` and memory `project_box_fzg_breaks_127_octet_limit`.
- **rules.yaml template refs resolve** (fv5: memory `project_fv5_rules_template_shift_fixed_0019`).

## The validated push mechanism (per switch)

Replicates OBN's `update_device()` for `action="c"`. Uses the **vlan100 SVI**
(`10.179.<box>.129`), NOT bond0 `.1`, as the TFTP source. All OIDs + creds come from
`/etc/obn/vendors.yaml` (vdsrail block) — read them live, don't hardcode across fleets.

1. **Render** the cfg with OBN's own Jinja env (byte-identical to what OBN produces):
   ```python
   from jinja2 import Environment, FileSystemLoader, StrictUndefined
   env=Environment(loader=FileSystemLoader("/etc/obn/template"),autoescape=False,undefined=StrictUndefined)
   env.get_template("<stem>.cfg").render(train_id=<Fzg>)
   ```
   Only `train_id` is required. Write to `/data/auto-topology/upload/<stem>-<mac-no-colons>.cfg`.
2. **3 CCU-side bypasses** (OBN normally does these; runtime-only, wiped on reboot):
   ```bash
   modprobe nf_conntrack_tftp
   iptables -t raw -I PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp
   iptables -I MGMTI 1 -p udp --dport 69 -j ACCEPT      # tftp_allowed ipset is empty w/o OBN
   ipset add tftp_allowed <switch-ip>                    # per switch
   ```
   The `-i vlan100` on the raw rule is load-bearing — without it the switch's RRQ is
   dropped and the switch reports `"Not running. Last error: Connection trouble or
   invalid URL"`.
3. **SNMP push** (v3, user `snmpadmin`, authPriv SHA/AES, pass `NomadStayOut!`):
   - `snmpset <config_tftp_location_oid> s "tftp://<ccu-vlan100>/upload/<file>"`
   - `snmpset <config_update_trigger_oid> i 3`
   - poll `<config_task_running_oid>` until `"configuration .* loaded"` (success) or
     `"Last error"` (fail). RRQ should appear in `journalctl -t in.tftpd`.
4. **Commit + reboot** — the critical gotcha:
   - `snmpget <get_hostname_oid>` → `$cur`
   - `snmpset <set_hostname_oid> s "$cur"`  ← **required commit trigger.** The reboot
     OID alone does NOT reboot; setting the hostname OID to its current value is
     OBN's commit-pending-config trigger (`vdsrail.reboot()`).
   - `snmpset <reboot_oid> i 3`
5. **Verify** — poll `<get_hostname_oid>` until the new `fv5-<pos>-v8-<Fzg>` hostname
   appears post-reboot (persisted in startup-config). The reboot is what persists.

### OIDs (box1-t41 / vdsrail — read live from vendors.yaml per train)

| purpose | OID |
|---|---|
| config TFTP location | `.1.3.6.1.4.1.8072.1.3.2.2.1.3.7.108.111.97.100.117.114.108` |
| config update trigger (value 3) | `.1.3.6.1.4.1.8072.1.3.2.2.1.7.7.108.111.97.100.117.114.108` |
| config task running (poll) | `.1.3.6.1.4.1.8072.1.3.2.3.1.2.9.99.104.101.99.107.116.97.115.107` |
| get hostname | `.1.3.6.1.2.1.1.5.0` |
| set hostname (commit) | `1.3.6.1.4.1.8072.1.3.2.2.1.3.6.114.101.98.111.111.116` |
| reboot (value 3) | `.1.3.6.1.4.1.8072.1.3.2.2.1.7.6.114.101.98.111.111.116` |

## Ordering — head-of-train LAST

Push leaf/mid switches first; push the **head-of-train A1 (device 1 of the A coach)
LAST**. v8 templates reassign the CCU-facing port versus v3 — an A1 reboot mid-run
can island the CCU from everything downstream (memory `project_bench_v8_cabling_trap`).
Derive true positions from `obn validate` cross-checked against the LLDP ring, never
from stale switch hostnames (which lag / mislabel during a half-finished push).

## Run DETACHED — the link will drop

A full-consist manual push is 10-15 min of SSH/TFTP/SNMP. On a train cellular link
that drops every ~2 min, an SSH-tethered loop dies repeatedly. **Launch the pusher
detached** so it survives session loss:

```bash
scp scripts/manual_sw_config_push.sh developer@<ccu>:/tmp/
ssh developer@<ccu> 'sudo chmod +x /tmp/manual_sw_config_push.sh; \
  sudo setsid bash /tmp/manual_sw_config_push.sh >/dev/null 2>&1 & disown; echo FIRED'
```

The script logs to `/var/tmp/manual_sw_config_push.log` and drops
`/var/tmp/manual_sw_config_push_done` when finished. Monitor drop-tolerantly by
polling the log/marker through whatever connectivity windows exist — do not hold a
session. Keep the `setsid` launch command minimal (one line) so a mid-command drop
doesn't truncate it before `setsid` forks.

## Modes

| Mode | Does |
|---|---|
| `--prepare` (default) | Read-only. Confirms OBN failed (hang/no-op). Runs `obn validate` + LLDP-ring cross-check. Renders every target cfg and byte-validates (hostname line = `fv5-<pos>-v8-<Fzg>`, non-empty). Prints the ordered switch list (head-of-train last) and the exact `--execute` recipe. Touches nothing on switches. |
| `--execute` | scp's + launches the detached pusher. Verifies each switch post-reboot. Reports converged / stragglers. |

## Verify (Goal-Driven)

Success = **every targeted switch reads `fv5-<pos>-v8-<Fzg>`** via SNMP `get_hostname`
(authoritative — leases lag), persisted through its reboot. Cross-check count against
`dosto-device-discovery`. A straggler that reported a load-success but wrong final
hostname → re-push that one switch (idempotent).

## Pairs with

- [`dosto-sw-config-update`](../dosto-sw-config-update/SKILL.md) / [`dosto-sw-config-update-batch`](../dosto-sw-config-update-batch/SKILL.md) — the OBN-driven paths this falls back from
- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — the conntrack-helper gap this skill applies as bypass #2
- [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md) — train_id hardcode precondition
- memory `project_manual_tftp_obn_bypass` (the origin recipe), `project_bench_v8_cabling_trap` (head-of-train), `project_tftp_conntrack_helper`
