# P4 — Maintainability & Test-Quality Scorecard (origin/master v2.3.12)

## Complexity (from P0 radon)
- Average cyclomatic complexity **A (3.81)** across 608 blocks. Distribution A 503 / B 78 / C 14 / D 7 / E 3 / F 3.
- Maintainability Index: **every file grade A** (worst `report.py` 34, `snmpdevice.py` 37, `acksys.py` 38).
- Hotspots are localized and named: `number_coaches()` across report variants (VIA F-59, DOSTO F-41,
  CCJPA E-35, Queensland E-34), plus `TIPG541Device._ssh` D-22, `togglepoe` C-18, `LldpArpWalker.walk` C-17.
- **Read:** low structural complexity overall — not a spaghetti rewrite candidate. The debt is concentrated
  and addressable.

## Test coverage (LOC proxy + file presence)

### Per subsystem (test LOC : source LOC)
| Subsystem | src | test | ratio | read |
|---|---|---|---|---|
| report | 3177 | 3718 | **1.17** | best-covered — correct, it's the risk center |
| util | 296 | 352 | 1.19 | good |
| validate | 284 | 219 | 0.77 | ok |
| walker | 547 | 476 | 0.87 | ok |
| device/vendor | 3820 | 2301 | 0.60 | uneven (see below) |
| device (bases) | 1432 | 586 | 0.41 | thin for snmpdevice (the None-source) |
| server | 20 | 71 | — | consist tested; **actions.py NOT** |

### Per vendor driver
| Driver | src | test | ratio |
|---|---|---|---|
| vsc7429 | 299 | 274 | 0.92 |
| eltec_cybox | 546 | 481 | 0.88 |
| lantech_6000 | 273 | 235 | 0.86 |
| acksys | 739 | 499 | 0.68 |
| extreme | 502 | 322 | 0.64 |
| westermo | 456 | 285 | 0.62 |
| vdsrail | 165 | 88 | 0.53 |
| lantech | 113 | 43 | 0.38 |
| **tipg541** | 379 | **0** | **0.00 — no test file** |
| **tng4500** | 230 | **0** | **0.00 — no test file** |

### Untested critical modules (no `test_<name>.py`)
- **`lib/tree.py`** — update-ordering / topology tree. This is where the cross-coupled-train None crash
  (field Bug 6) lives. Critical path, **zero tests.**
- **`lib/server/routers/actions.py`** — the state-changing API (reset_device / togglepoe / getlog).
  Pairs with security finding S1; **zero tests.**
- `obn.py`, `lib/walker/walker.py` (the device factory), `backbone_{handle_ssid,rules,wifi_status}.py`,
  `lib/logging.py`, `zabbix_{check,generate}.py`, `lib/device/{genericdevice,snmpporttype,device_enums}.py`.

## The silent-success smell (corroborates the bug root-cause)
Grep for acknowledged-but-unfixed silent successes:
- `lib/device/vendor/vdsrail.py:96,125,131` → `return True  # TODO: return True only on successful call`
- `lib/device/vendor/lantech.py:67,83,87` → same TODO
These are **firmware/config/reboot operations that unconditionally return True regardless of SNMP outcome.**
This is field Bug 11 (Westermo "trusts the echo") generalized — the codebase has *self-documented*
silent-success returns across multiple drivers. Strongest single evidence that the field bugs are one
systemic pattern, not isolated defects.

## TODO density
32 markers total, concentrated in `backbone_handle_ssid.py` (7, incl. `# TODO: implement` stubs),
`cli/update.py` (4), `vdsrail.py` (3), `lantech.py` (3). `backbone_handle_ssid.py:29 # TODO: implement`
is a genuine unimplemented-feature stub.

## Type safety
213/515 functions (41%) carry return annotations; **no mypy in CI.** Given that the dominant bug class is
None-propagation, enforced typing (`Optional[str]` + mypy strict-optional) would statically catch a large
fraction of the field-bug class before it ships. This is the single highest-leverage process fix.

## Bug-class recurrence (the rebuild-vs-improve signal)
The defects are **not diverse**. They reduce to two recurring shapes:
1. **None-deref on SNMP-derived values** (silent None source → unguarded consumer).
2. **Silent-success returns** (operations that report success without verifying the SNMP result).
Both are *pattern* defects with *pattern* fixes (typed optionals + a verify-after-set helper + a shared
guarded-numbering core). Recurrence-with-a-common-fix favors **improve**: a rewrite would re-derive the
same 14 topology algorithms and the same SNMP layer, re-introducing the same risk, at high cost.

## P4 verdict
Maintainability is **good-to-moderate**: low complexity, disciplined error handling, strong report-layer
tests — but real, named gaps (tree.py, actions.py, two drivers untested; no mypy; self-documented silent
successes). All gaps are closeable in place. Nothing here is a rewrite trigger.
