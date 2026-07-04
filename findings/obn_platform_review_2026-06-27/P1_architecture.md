# P1 — Architecture Baseline (origin/master v2.3.12, HEAD 8042c8d)

All citations are `file:line` under `src/usr/share/obn/`. Verified against the worktree.

## Layered structure

```
CLI (obn.py, Click group)
  │  command → module dispatch (obn.py:63–199)
  ├─ discover  → backbone_discovery.py → lib/walker/{walker,lldp,lldparp,dhcp}walker.py
  ├─ report    → getattr(lib.report, cfg["report_module"])().run_report()   (obn.py:82–90)
  ├─ validate  → backbone_validate.py → lib/validate/validate.py
  ├─ update    → cli/update.py → lib/tree.py (OBNTree leaf-first ordering)
  ├─ telemetry → backbone_telemetry.py (APScheduler)
  └─ serve_api → lib/server/server.py (FastAPI) → routers/{consist,actions}.py

Device factory:  Walker.instantiate_device(mac,ip)  (walker.py:30–67)
  → Configuration.find_brand(mac)  (configuration.py:174–183)
  → getattr(lib.device.vendor, class_name)(...)   ← edit-core-files plugin model

Device inheritance:  Device(ABC)  (device.py)
  → SNMPDevice (snmpdevice.py, 723 LOC)
    → AccessPointDevice (accesspointdevice.py)
      → 11 vendor classes (acksys, eltec_cybox, extreme, lantech, lantech_6000,
        tipg541, tng4500, vdsrail, vsc7429, westermo)
    → NomadCCUDevice
```

## FINDING A (decisive) — the report layer has no abstraction
- `Report.number_coaches` is `@abstractmethod` (report.py:237).
- **All 15 report modules** (base stub + 14 customer variants) define their own `number_coaches()`
  (verified: report_ace, ccjpa_wd1, ccjpa_wd2, daisy_cybox, dani, dhcp, dosto_neu, dsb, generic,
  luna, queensland, tgv, tgv2020, via).
- Each implementation is 90–150 LOC of bespoke topology logic; only a ~5-line queue-init prologue is
  copy-pasted between variants. Shared code is limited to leaf utilities (`find_type`, `get_device`,
  `find_neighbour`).
- This is exactly where the complexity hotspots concentrate (P0): `VIAReport.number_coaches` F(59),
  `DostoNeuReport.number_coaches` F(41), CCJPA E(35), Queensland E(34).
- **Implication:** the single hardest, most defect-prone algorithm in OBN (topology walk → coach
  numbering) is hand-rolled 14 times with no shared, tested core. Bug 10 (DOSTO BFS loop) and the new
  numbering-fallback feature both live here; the same defect *class* is latent in the other 13 variants.
  This is the strongest architectural argument — and it points to "improve + extract a shared numbering
  engine," not "rewrite the platform."

## FINDING B (root cause) — None-propagation is the dominant error design
- `_snmp_parse_results` (snmpdevice.py:283) logs and `continue`s on SNMP error, returning the
  accumulated dict (empty on total failure).
- `_snmp_get` returns `result.get(oid)` → **`None` on any failure** (snmpdevice.py:340).
- Device properties (`serial_number`, `firmware_version`, `configuration_version`) propagate `None`
  upward silently; no exception is raised.
- Downstream report code must defensively guard every dereference. Where a guard is missing, you get
  the exact field-bug class we hit in the field (`None.endswith()`, `None.startswith()`).
- **Implication:** the ~11 field bugs are not 11 independent defects — they are one systemic design
  pattern (silent `None` on SNMP failure + unguarded consumers) surfacing in many call sites. Enforced
  typing (mypy, absent in CI) + a typed "result-or-error" return would collapse most of the class.

## FINDING C (security) — no API authentication
- `lib/server/server.py` mounts `/consist` (read) and `/actions` routers with **no auth** (no API key,
  JWT, or dependency guard observed). `routers/actions.py` exposes state-changing ops
  (`reset_device`, `togglepoe`, `power_cycle`, `getlog`). Bound to localhost by config, but there is no
  in-app authn/authz. → P2 to assess exposure/exploitability.

## FINDING D (extensibility) — "edit core files" plugin model
- New vendor: write `vendor/xyz.py`, **edit `vendor/__init__.py`**, add YAML `vendor_specific` block;
  class name must match config string exactly (duck-typed, no interface validation).
- New customer: write `report_xyz.py`, **edit `report/__init__.py`**, set `report_module` in YAML.
- No factory registry / entry-point discovery. Moderate friction; not broken, but not self-service.

## End-to-end trace — `obn report` (DostoNeu)
1. `obn.py:89` `getattr(lib.report,"DostoNeuReport")()`
2. `report.py:623` `load_json()` — read discovery.json → `device_instances`, load prev snapshot
3. `report.py:624` → `report_dosto_neu.py:31` `number_coaches()` — BFS from CCU, per-port coach/device
   numbering (the guard `to_device is None or to_device.coach_number is not None` is at line 61)
4. `report.py:627` `apply_firmware_and_configuration_rules()` → `rules_engine.py` sets `device.target`
5. `report.py:630` `compare_json()` — diff vs previous snapshot
6. `report.py:635` `store_report()` — write `discovery.prev.json` (cfg.report_file)
7. `report.py:639/641` `publish_consist_to_mqtt("obn/consist")` + per-device add/remove events
- **State files:** `discovery.json` (discover writes), `discovery.prev.json` (report commits). Confirms
  the "always run discover→report before update/validate" rule.

## Cross-cutting
- **Configuration** (configuration.py): singleton; merges all `/etc/obn/*.yaml` (later overrides
  earlier); `__getitem__` fail-fast (KeyError) but `.get()` soft. MAC→brand lookup cached, longest-prefix.
- **Logging** (lib/logging.py): YAML-driven; MQTT + watched-file handlers; file handler swallows OSError
  (won't crash OBN on disk-full) — consistent with the "never raise" philosophy that also produces B.

## Net architecture read (for the decision)
- Discovery/device/tree layers are **clean and reasonably abstracted**. The **report layer is the
  liability** (no shared numbering core). Complexity is low everywhere (P0: avg CC 3.8, all MI grade A),
  so this is a *fragility/abstraction* problem in a *simple* codebase — the classic profile of "improve"
  (extract + harden + type) rather than "rewrite."
