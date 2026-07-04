# P3 — Comprehensive Bug & Edge-Case Sweep (origin/master v2.3.12)

Method: 6 read-only subsystem hunters (effort=high) → each finding adversarially re-verified by an
independent skeptic that re-read the code, searched the test suite, and assigned blast-radius. 53 agents,
~4.2M tokens, ~9 min. Full register: `P3_findings_register.json`.

## Outcome
**47 raw findings → 15 confirmed, 24 needs-runtime-confirmation, 8 refuted, 0 duplicate.**

The adversarial layer is credible: it **refuted 8** (e.g. a claimed operator-precedence bug in ACE and a
claimed `min(int, None)` in CCJPA — both had guards the hunter missed) and **downgraded severities**
(VDSRail silent-success high→medium, ACKSYS high→low). It did not rubber-stamp.

## Defect-class breakdown (the decisive pattern)
| Class | Confirmed | Needs-runtime | What it is |
|---|---|---|---|
| none_deref | 5 | 18 | Unguarded consumer of an SNMP-derived value (firmware/config/serial/MAC/LLDP) → NoneType crash |
| error_masking | 5 | 0 | A real failure surfaced as success/500/`{success:False}` |
| silent_noop | 4 | 2 | Operation reports success without doing/verifying the work |
| regex_assumption | 0 | 3 | Parser assumes a device response format |
| unbounded_loop | 1 | 0 | `number_coaches` BFS with no visited-set |

**~22 of 39 actionable findings are the same `none_deref` pattern** — every one traceable to the P1 root
cause (SNMP returns silent `None`; consumers don't guard). The remaining cluster is `silent_noop` /
`error_masking` — the `return True # TODO` family and the broken API error paths. **The platform's defects
are not diverse; they are two systemic patterns repeated across subsystems.**

## Confirmed findings (15)
| Sev | Location | Class | Finding |
|---|---|---|---|
| HIGH | report_dosto_neu.py:158 | unbounded_loop | `number_coaches()` re-enqueues with no visited set → infinite loop / OOM on malformed cabling (= field Bug 10, independently rediscovered) |
| HIGH | tree.py:24 | none_deref | Root selection `…startswith('box1')][0]` crashes on None serial or empty list — **untested module** |
| HIGH | vdsrail.py:74 | none_deref | Firmware-poll `re.search("Not running", None)` crashes in the reboot window (= field Bug 2) |
| HIGH | actions.py:5 | error_masking | `HTTPException` imported from `http.client` not `fastapi` → every 404/405 becomes a TypeError |
| HIGH | actions.py:48 | error_masking | `reset_device` collapses not-found / wrong-type / real-failure into `{success:False}` HTTP 200 |
| MED | vdsrail.py:96 | silent_noop | firmware/config/reboot `return True` unverified (= field Bug 11 class; same pattern in lantech/tng4500/westermo) |
| MED | report_via.py:144 | none_deref | `box_device` referenced unbound when no CCU serial matches → UnboundLocalError aborts VIA report |
| MED | actions.py:112 | none_deref | `togglepoe` derefs `parentSW.mac` when cache seeds port but loop nulls parentSW |
| MED | actions.py:57 | error_masking | `getlog` 500s (leaks report path) on missing report / unknown IP |
| MED | actions.py:25 | silent_noop | action endpoints use `@lru_cache`d device list → operate on stale consist after a re-report |
| MED | backbone_handle_ssid.py:57 | none_deref | continues after failed report load → `filter(None)` TypeError (log says "exiting", code doesn't) |
| MED | cli/update.py:276 | error_masking | empty target set → `all([])==True` → misleading "readonly devices" success (= field "update c silent no-op") |
| LOW | acksys.py:420 | error_masking | `raise AcksysDevice(...)` (not an Exception) masks the real config/file error |
| LOW | cli/update.py:276 | silent_noop | (companion to above) no-op success on mistyped/stale IP |
| LOW | backbone_handle_ssid.py:29 | silent_noop | `load_target_ssid` is a TODO stub hardcoded to `"Waffles"` — command is unfinished |

## Cross-platform spread (key whole-platform finding)
The `number_coaches` defect family is **not DOSTO-only**. Independently flagged in:
- **report_via.py** (144 unbound box_device; 180/251 unguarded get_device derefs)
- **report_ace.py** (73 unguarded master_switch), **report_dsb.py** (122), **report_dani.py** (88),
  **report_queensland.py** (43 min-over-empty), **rules_engine.py** (61)
This proves the P1 prediction: hand-rolling the hardest algorithm 14× propagates the same defect class to
every customer. GenericReport / TGV / TGV2020 / Luna / Daisy / CCJPA-wd1 are comparatively well-guarded.

## `tree.py` — the untested-critical-path payoff
P4 flagged `tree.py` as having zero tests. The sweep returned **3 high-severity crashes there**
(root-None-serial, empty-list `[0]`, unresolved-neighbour `None.type` at :37). Direct evidence that the
coverage gap ships real bugs.

## needs-runtime (24) — highlights
Mostly the same none_deref pattern in paths that require specific hardware/data to fire: vdsrail config-poll
(117), westermo/lantech6000/cybox SNMP-result derefs, lldp.py chassis-mac KeyError (52, HIGH),
tree.py unresolved-neighbour (37, HIGH), device.py needs_*_update None.endswith (66/72, HIGH — the field
Bugs 4 & 8, independently rediscovered), DSB/ACE/Dani/Queensland number_coaches derefs, dhcpwalker dotless
subnet match (41), parsers.py wrong-return (33), ospf.generate_entries silent no-op (58).

## P3 verdict
The comprehensive sweep **confirms and generalizes** the systemic-pattern thesis: OBN's real defect load is
two repeating, common-fix patterns (unguarded SNMP-None consumers + silent-success/error-masking), spread
across the device, report, tree, and API layers — and present in customer variants beyond DOSTO. This is a
*hardening* problem with *pattern* fixes, not evidence of irredeemable design. It strengthens "improve."
