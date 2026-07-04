# Knowledge base change log

## 2026-07-04
* **Creation**: Initialised `.kb/` OKF bundle — root `index.md`, `HOW-TO-USE.md`, `log.md`, and the category skeleton (`components/`, `topics/`, `fleet/`, `deliverables/`, `tickets/`, `assets/`).
* **Creation**: First component doc — `components/vds-consist-switch/cli-and-management.md` (CLI/SNMP/reboot/traps/syslog + 6 proven dead ends), field-validated.
* **Creation**: Full first pass — 89 docs total. Components (10): VDS switch (cli, l2-counters-rstp, firmware-flashing) + Westermo AP (factory-config, firmware-activation) + Nomad Connect/OBN (bug-suite, discover-report-update, ndsu-chroot-persistence, tftp-conntrack-helper, publish-to-puppet-pipeline). Topics (5): vlan7-addressing, l2-health-methodology, coupled-rstp-tc-storm, fzg-id-two-namespaces, zabbix-nms-model. Fleet (8 records), Tickets (4), Deliverables (5 resource-stubs), Assets (46 per-train allocation stubs). Every concept doc carries a `type`, a `# Proven dead ends` section, and `# Citations`.
* **Validation**: OKF conformance pass — 79/79 concept docs have parseable frontmatter + non-empty `type`; 0 problems. Dangling fleet links pruned from asset stubs.

## 2026-07-04 (later)
* **Expansion**: Fleet records built out to **51 train-records** (one per fleet-status row across all 5 categories — 4736/4734/4705/4706 + bench context). Each carries train name, Fzg ID, box-id, CCU 10.179.x.x IP, `box1-t<box>` host, Zabbix host group `50_6<box-id>` (with box=Fzg migration-rename note), computed vlan7 IPs, and a topology link (per-series `_shared` reference or the new fv5/fv6 topic). 43 generated from fleet-status via `scripts/gen_kb_fleet_records.py`; 8 hand-written rich records preserved.
* **Creation**: `topics/fv5-topology.md` — 4705 (fv5 CAT) + 4706 (fv6) layout, sources, and the asymmetric-cfg-description dead end.
* **Validation**: full bundle now 133 docs — 123/123 concept docs conformant, 0 problems, 0 broken internal links.
