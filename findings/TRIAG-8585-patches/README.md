# TRIAG-8585 — drop-in patch set for DevOps

https://nomad-digital.atlassian.net/browse/TRIAG-8585

Upstreams the v8 DOSTO field hand-patches (11 OBN code bugs + 1 Puppet infra
fix) so a stock CCU image passes the `dosto-obn-patches` 11-marker check with no
hand-patching.

## How to apply (OBN application repo)

These are **unified diffs against the OBN package layout** (`/usr/share/obn/...`
maps to repo `lib/`, `cli/` — adjust `-p` level to your repo root). Paths in the
hunks are repo-relative (`lib/...`, `cli/...`).

```
cd <obn-repo-root>
git apply --3way findings/.../01-vdsrail.py.patch
git apply --3way 02-snmpdevice.py.patch
git apply --3way 03-device.py.patch
git apply --3way 04-update.py.patch
git apply --3way 05-tree.py.patch
git apply --3way 06-report_dosto_neu.py.patch
git apply --3way 08-westermo.py.patch
```

(`07-puppet-60-allow-management-tftp-helper.patch` is the Puppet infra fix and
applies in the `environment-dostoneu` Puppet repo, not the OBN repo — see the
infra row in the table below.)

The hunks use **descriptive `@@ ... @@` headers instead of line numbers** because
the field workspace does not hold the upstream OBN source — they were derived
from the verified field patcher scripts (`scripts/fix_obn*.py`,
`scripts/fix_bug1_regex.py`). If `git apply` can't place a hunk, the context
lines (3 above/below each change) are exact; apply by context or use
`git apply --3way`. After applying, confirm with the markers in the table below.

## Bug → file → patch → marker map

| # | Patch file | Source file | Marker (field detector greps for this) |
|---|---|---|---|
| 1 | 01-vdsrail.py.patch | lib/device/vendor/vdsrail.py | `default image is now\|image loaded` |
| 2a/2b | 01-vdsrail.py.patch | lib/device/vendor/vdsrail.py | `if not result:` + `continue` before `re.search("Not running"...)` (x2) |
| 7 | 01-vdsrail.py.patch | lib/device/vendor/vdsrail.py | `if hostname is not None:` before `_snmp_set` |
| 3 | 02-snmpdevice.py.patch | lib/device/snmpdevice.py | `except KeyError:` / `return {}` |
| 9 | 02-snmpdevice.py.patch | lib/device/snmpdevice.py | `_SNMP_DISPATCH_LOCK` |
| 4 | 03-device.py.patch | lib/report/device.py | `bool(self.firmware) and not self.firmware.endswith` |
| 8 | 03-device.py.patch | lib/report/device.py | `bool(self.config) and not self.config.endswith` |
| 5 | 04-update.py.patch | cli/update.py | `Bug 5 fix: pre-populate tftp_allowed ipset` |
| 6 | 05-tree.py.patch | lib/tree.py | `neighbour not in this consist` |
| 10 | 06-report_dosto_neu.py.patch | lib/report/report_dosto_neu.py | `NDP-PATCH-BUG10-BFS-GUARD` |
| 11 | 08-westermo.py.patch | lib/device/vendor/westermo.py | `NDP-PATCH-BUG11-FW-VERIFY` |
| infra | 07-puppet-60-allow-management-tftp-helper.patch | Puppet `60-allow-management` (env `dostoneu_migration_mar5`) | `nf_conntrack_tftp` module + raw/PREROUTING `--helper tftp` rule |

## Points for R&D review (called out inline in the patches)

- **Bug 7 (vdsrail.py)** — two field patcher generations disagree on whether the
  pre-patch hostname line has an `or ""` suffix. The primary hunk assumes it does
  (the current `fix_obn_bugs67.py`); an alternate hunk for the no-`or ""` tree is
  commented at the bottom of `01-vdsrail.py.patch`.
- **Bug 5 (update.py)** — shells out to `ipset ... -exist` via subprocess. R&D may
  prefer routing through the existing firewall/ipset helper instead.
- **Bug 9 ordering** — Bugs 3 and 9 both wrap the same `list(generator)` site in
  `snmpdevice.py`; apply 3's try/except first, then 9's lock inside it. The single
  combined hunk in `02-snmpdevice.py.patch` already reflects the final state.
- **Silent `obn update c` exit-0 when `Device.target is None`** (ticket §A note) —
  not separately patched here; ticket asks R&D to confirm whether Bug 10 + the
  `discover → report → update` ordering covers it or whether a `cli/update.py`
  guard is also warranted.

## Acceptance (from the ticket)

A stock CCU image pulled from Puppet passes all 11 markers above with zero
hand-patching, and `obn update f ap` batch completes for all APs (Bug 11 +
the infra TFTP-helper fix). At that point the `dosto-obn-patches` skill flips
from "apply" to "verify".

## Bug 11 (westermo.py) — added 2026-06-08, after the original ticket

Bug 11 (`08-westermo.py.patch`, marker `NDP-PATCH-BUG11-FW-VERIFY`) was found
during the 2026-06-08 9-train run, AFTER this ticket was first filed with 10
code bugs + the Puppet infra fix. It is the AP-firmware activation-verify fix:
`obn update f <ap>` reports success off the SNMP SET echo without ever
read-checking that the flash activated, so a downloadError/flashError — or a
genuine RT-610 flash-trigger hang — is recorded as success while the AP keeps
booting the old image. Patch polls the real `rpcFwFlash` status + sysUpTime
until terminal. NOT yet live-validated end-to-end across a full consist
(single-AP confirmed on 4736-109 .236 → activated; .226-class hang correctly
reported as failure). R&D review note: the ~10 min poll window is deliberately
generous because the legitimate slow-flash case exceeds 5 min — tune the bound
if upstream has a better activation signal than uptime-reset.
