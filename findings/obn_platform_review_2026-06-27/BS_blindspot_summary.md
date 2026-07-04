# BS — Blind-spot sweep of high-blast-radius central modules (origin/master v2.3.12)

**Why this exists:** the GenericReport miss had a signature — a central, high-blast-radius component the
earlier sweeps cited as *context* but never audited as a *target*. This sweep targeted every module matching
that signature: snmpdevice.py (SNMP base, all devices), walker.py (discovery factory), util/decorators.py
(caching), validate.py (commissioning gate), ccudevice.py/context.py (CCU identity), obn.py (CLI). 6
auditors + adversarial verification, 29 agents.

## Outcome: 23 raw → 6 confirmed, 13 needs-runtime, 4 refuted, 0 dup
The verifiers did real filtering: they **refuted 4** overstatements and **re-scoped most "fleet-wide" claims
down** to narrower/realistic blast radius. Net read: the central modules are **broadly careful but not
flawless** — the sweep found genuine defects the earlier passes skipped, but most are LOW or narrower than
first claimed. No new HIGH/critical platform-wide bug. This both (a) closes the GenericReport-class gap and
(b) raises confidence that the core is solid.

## Confirmed (6)
| Sev | Location | Class | Finding | Real blast radius (post-verify) |
|---|---|---|---|---|
| MED | validate.py:47 | validation_gap | TGV topology/coach/media checks never run via `obn validate` (subclass unused + unregistered) | TGV2020 fleet only — NOT DOSTO |
| MED | validate.py:136 | validation_gap | No positive structural assertion — a non-empty but wrong/short device list reads healthy | `obn validate` diagnostic only; does not gate destructive ops |
| MED | context.py:39 | identity_root_logic | CCUContext silently defaults an unmapped box to coach 1 → whole-consist misnumber | multi-CCU types (TGV-M) only — NOT DOSTO/standard |
| LOW | decorators.py:48 | silent_noop | Disk cache is a fleet-wide **no-op**: default dir `/tmp/obn` is never created, shelve can't create parent | every `@disk_cached_property`, but fails safe to live SNMP |
| LOW | backbone_validate.py:146 | error_masking | `obn validate` always exits 0 — `run_all()` failures never reach exit code | every train, but human-facing diagnostic (no CI gate found) |
| LOW | validate.py:190 | none_deref | `test_incomplete_devices` checks key presence only — accepts present-but-None SNMP fields | `obn validate` completeness report only |

## Most decision-relevant of these
- **`obn validate` is a weak commissioning gate** (validate.py:47/136/190 + backbone_validate.py:146): always
  exits 0, no structural assertion, real topology checks never wired in. A broken/short consist can validate
  as "OK". Directly relevant — the team runs `obn validate` during commissioning. (All LOW/MED individually,
  but together they mean: don't trust `obn validate` exit code or a green table as proof a train is correct.)
- **The disk cache is dead code with two armed traps** (decorators.py:48 + needs-runtime :101/:75): the cache
  silently does nothing today (so no live harm), but it hides a MAC-key collision (`00:00:00:00:00:00`
  default → one device's serial served to another) and empty-string poisoning that would **activate the
  moment someone "fixes" the cache path**. A trap for a future maintainer.

## Needs-runtime (13, highlights)
snmpdevice.py: generic_get returns `''` (not None) on walk-miss → device_stats None-guard misses it →
telemetry TypeError for the one walk-prefer brand (Westermo) (:278, MED); cached_property freezes a
failed read for the process (:234); engine singleton no-lock — latent, telemetry threadpool was *removed*
this version (:156). walker.py: shared-IP devices silently dropped (new MAC + seen IP fails the AND gate)
(:24, MED — contradicts ZFR/Sprechstelle redundancy reality); is_new_mac/is_new_ip purity (:18).
backbone_telemetry.py: loop derefs instantiate_device() with no None guard (:56, MED). obn.py: APScheduler
overrun cycles silently dropped (:123).

## Refuted (4) — credibility of the pass
cfg["train_type"] KeyError abort (guarded upstream); CCUContext stale-singleton-poisons-serve_api
(serve_api re-derives per request); CCUDevice.mac caches "unknown" forever (re-checked false);
NomadCCU global engine no-lock (no threads in this version). Verifiers refuted these, not rubber-stamped.

## Bearing on the review
- **Verdict unchanged: IMPROVE.** Nothing here is a rewrite trigger; all are in-place fixes, mostly LOW.
- The recurring **None/empty-string + stale-cache + validation-gap** patterns are the *same* systemic classes
  Part B already names — so this reinforces (doesn't expand) the "two systemic patterns, common fix" thesis,
  now shown to reach the central modules too.
- **Methodology close-out:** the report can now honestly say every high-blast-radius component was audited as
  a first-class target (not just cited as context). The GenericReport-class blind spot is closed.

## Honesty note
These were NOT in the original review — the central modules were treated as context, exactly the GenericReport
failure mode. Found only after the engineer pushed on "what else like GenericReport did we miss." Lesson
recorded: shared/base/factory/gate modules must be audited as targets, weighted by blast radius, not assumed
clean because they are "infrastructure."
