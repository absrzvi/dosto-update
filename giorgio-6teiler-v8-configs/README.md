# DOSTO NEU 6-Teiler — v8 Switch Configurations

VDS Rail Consist Switch configurations (config version **v8**) for two 6-car (nv6) DOSTO NEU trainsets.

## Contents

| Folder | Train# | Fzg ID | Switches |
|---|---|---|---|
| `4736-117_Fzg145/` | 4736-117 | 145 | 18 (A1–A3, C1–C3, D1–D3, E1–E3, F1–F3, B1–B3) |
| `4736-119_Fzg147/` | 4736-119 | 147 | 18 |

Each `.cfg` is one switch, named by its schema position and hostname
(`nv6-<pos>-v8-<Fzg>.cfg`). A 6-Teiler has 18 VDS switches — 3 per car across
6 cars (coaches A, C, D, E, F, B in physical order).

## Source

These are **live `show running-config` captures** pulled directly off each switch
on **2026-07-06**, via the train's Nomad CCU:

- 4736-117 (Fzg 145) — CCU `box1-t32` @ `10.179.32.1`, switches `10.179.32.178–195`
- 4736-119 (Fzg 147) — CCU `box1-t12` @ `10.179.12.1`, switches `10.179.12.178–195`

They are the actual deployed configs (as rendered by OBN from the
`nd-obn-template-dostoneu-nv6` v8 templates in the `migration_mar5` Puppet
environment), not offline-rendered templates — so they reflect exactly what
each switch is running, including per-train values (Fzg-ID in hostnames,
DHCP scopes, NTP source, RSTP priorities).

Both trainsets were the pair used in the recent multitraction / coupling test.
