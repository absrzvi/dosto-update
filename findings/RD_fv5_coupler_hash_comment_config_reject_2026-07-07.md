# fv5 coupler templates contain `#` comments the VDS switch rejects — breaks config load

**Date:** 2026-07-07
**Found on:** box1-t41 (4705-103 / Fzg 231), fv5, switch firmware 7.4.2, nd-obn 2.3.6
**Severity:** blocks v8 config on ALL coupler switches (A1, A3, B1, B3) fleet-wide on fv5
**Affects:** `nomad-obn-template-fv5` templates `fv5-100-A1.cfg`, `fv5-100-A3.cfg`, `fv5-600-B1.cfg`, `fv5-600-B3.cfg`

## Symptom
Config push (OBN **or** manual TFTP+SNMP) to a coupler switch fails; the switch reports:
```
"Not running. <file>.cfg not loaded (Error testing the configuration file at line N)"
```
with N = 85 (A3), 92 (A1), 93 (B1/B3). The switch keeps its old config (safe — no reboot).
The 11 non-coupler switches load fine. This is **also why `obn update c` hangs/fails**
on an fv5 consist — OBN hits the same config-test rejection on the coupler switches.

## Root cause
The VDS Rail Consist Switch CLI **does not accept `#` comment lines**. Any `#` line —
even a lone comment — returns `Error in command, param is "#" [wrong]` and fails the
whole config-test at that line. Proven directly via CLI (paramiko, `admin`/`Nom@dCome1n`):
```
# any comment   ->   Error in command, param is "#" [wrong]
```
The fv5 **coupler** templates (A1/A3/B1/B3) each carry two `#` comments inside the
`interface e0-2` (Frontkupplung) block, added during the v9 coupler-containment work:
```
  # v9: load-bearing coupler allow-set 5,15 + native-999 containment (do not 'tidy')
  switchport mode trunk native vlan 999 prune allow 5,15
  # v9: flat symmetric coupler cost (was train_id-derived) — see PLAN_v9
  spanning-tree port-cost 20000
```
The **actual coupler commands are valid** — each applies cleanly when entered via CLI
(`native vlan 999` even auto-creates the vlan). Only the `#` comment lines break it.
The 11 non-coupler fv5 templates have **zero** `#` comments, so they load.

## Fix
Strip the `#` comment lines from the four fv5 coupler templates (keep the commands).
The comments are documentation only — the switch can't store them anyway.

- **Immediate (box1-t41, done 2026-07-07):** the manual pusher
  (`scripts/manual_sw_config_push.sh`) now strips `^\s*#` lines before push. All 4
  coupler switches (A1/A3/B1/B3) then loaded + persisted → **15/15 on fv5-*-v8-231**.
- **Durable (repo):** remove the `# v9:` comment lines from
  `fv5-100-A1.cfg` / `fv5-100-A3.cfg` / `fv5-600-B1.cfg` / `fv5-600-B3.cfg` in
  `nomad-obn-template-fv5`, bump version, publish, deploy (same pipeline as the
  rules.yaml fix → `project_fv5_rules_template_shift_fixed_0019`). This also unblocks
  OBN's own `obn update c` on fv5 coupler switches.
  ⚠️ Check fv6 (and nv4/nv6 v9 coupler templates) for the same `#` comments — likely
  the same bug wherever the v9 coupler block was added with `#` documentation.
- **CONFIRMED on fv6 (2026-07-09, box1-t15 / 4706-102 / Fzg 190, templates 0.0.18):**
  all four fv6 coupler templates (`fv6-100-A1/A3.cfg`, `fv6-600-B1/B3.cfg`) carry the
  same two `# v9:` comment lines and were the cause of the 4-head-switch config-reject
  observed 2026-07-06 (B3 "boots back on OLD startup-config" despite exit-0 push).
  Same `#`-strip manual push → all 4 loaded first try → 18/18 `fv6-*-v8-190`.
  The durable repo fix must therefore cover **nomad-obn-template-fv6 as well as fv5**.

## Why it went unnoticed
The `#` comments were added as v9 documentation ("do not 'tidy'") assuming the switch
tolerates them. It doesn't. Non-coupler switches were unaffected (no comments), so a
partial consist would look "mostly working" while every coupler switch silently
refused its config — exactly the box1-t41 state before the fix (11/15 v8, 4 couplers
stuck).
