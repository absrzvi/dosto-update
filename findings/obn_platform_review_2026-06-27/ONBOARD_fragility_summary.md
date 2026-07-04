# ONBOARD — Device onboarding & prestaging fragility sweep (origin/master)

**Why this exists:** Product reported that vendor firmware updates break OBN's hardcoded device support. That is real (tracked separately as the **FW_DRIFT** theme), but it raised a sharper question: *is firmware drift the only way OBN's onboarding model fails, or is it one instance of something systemic?* This sweep answers that — it audits the device **onboarding** path (how OBN recognises + manages a device) and the **prestaging** preconditions (the human/network/CCU-image state OBN assumes but does not establish or verify), deliberately **excluding** firmware-string drift so the two themes don't double-count.

**Method:** two multi-agent sweeps (6 + 2 hunters across 6 onboarding/prestaging surfaces), every finding adversarially verified against source at `.tmp/gitlab-repos/obn/src/usr/share/obn`. ~57 agents total.

## Outcome: 26 raw → 19 confirmed, 1 needs-runtime, 6 refuted
The verifiers did real filtering — **refuted 6** (including two *good-news* refutations: a fallback guard already recovers the redundant-path drop case, and the Westermo AP config path already guards its SNMP result) and **re-scoped several severities down** (PRE-3 HIGH→MED as an upstream-config precondition not an OBN bug; PRE-7 reduced to the accurate weaker claim). Net read: onboarding/prestaging is **systematically fail-silent**, and firmware drift is just the most-reported symptom of one root cause.

## The single root cause
**OBN's onboarding/prestaging path has no expectation-vs-reality reconciliation and no fail-loud seam.** It enrols whatever answers on the network, numbers whatever LLDP it walks, pushes whatever the rules/templates say, and reports success regardless. So every wrong precondition — mis-image, miscable, foreign/coupled consist, stale snapshot, transient SNMP miss, missing rule — surfaces as a *silent wrong result* instead of a *loud stop*. Firmware drift (FW_DRIFT) is the same defect on the vendor-version surface.

## Confirmed (19), by surface

### Push safety — OBN reports success when nothing happened
| Sev | Location | Class | Finding |
|---|---|---|---|
| **HIGH** | vdsrail.py:95/124/130 | false_success | `set_firmware`/`set_config`/`reboot` all `return True # TODO` without verifying the SNMP SET took |
| MED | westermo.py:76-83 | false_success | AP firmware push returns True on the SET echo — no completion poll, no reboot, no post-flash verify (partial-flash trap) |
| MED | vdsrail.py:74/116 | none_deref | poll loop `re.search` on a possibly-None SNMP result in the reboot window → uncaught TypeError mid-batch (LOUD) |
| MED | update.py:276-285 | false_success | empty target set exits as 'readonly devices' success — a mistyped/stale push IP reads as a benign no-op |

### State & persistence — a transient miss poisons the snapshot
| Sev | Location | Class | Finding |
|---|---|---|---|
| MED | snmpdevice.py:226/234 + decorators.py:36 | stale_cache | transient SNMP miss caches None/'' for firmware/config and writes it into discovery.json (only fresh `discover` clears it) |
| MED | report/device.py:23-25 + report.py:130 | stale_snapshot | `compare_json` excludes coach/device-number, so a corrected topology renumbering never republishes to NMS |

### Security / trust boundary — OBN trusts whatever answers
| Sev | Location | Class | Finding |
|---|---|---|---|
| MED | configuration.py:174 + walker.py:38 | admission_control | device identity = MAC OUI only; anything with a vdsrail/westermo OUI is onboarded as a trusted SW/AP |
| MED | report_dosto_neu.py:200-264 | admission_control | coupled neighbour consist's switches + APs enrolled over the coupler and fallback-numbered as ours (field-seen: nv4-A1-v8-015) |
| MED | update.py:84 + snmpdevice.py:488 | admission_control | no 'does this device belong to this train' gate before stamping this train's train_id config onto it (Fzg133 cascade, cross-train) |
| MED | actions.py:25-34 + vdsrail.py:129 | stale_binding | Action API reset/PoE acts on the stale report IP→MAC binding (2-min leases) with no live identity re-check |

### Topology & coach numbering
| Sev | Location | Class | Finding |
|---|---|---|---|
| **HIGH** | report_dosto_neu.py:61 + :158 | nontermination | `number_coaches` BFS has no visited set; unnumbered mutually-adjacent switches re-enqueue unboundedly → `obn report` hang/OOM (the bug-10 class; ~60GB on box1-t12/Fzg147) |
| MED | report_dosto_neu.py:42-43 | no_expectation_assert | numbers whatever LLDP it walks with no assertion vs the expected consist (extra/missing/reordered coaches numbered or dropped); dani report has the count-guard DOSTO-NEU lacks |
| MED | report_dosto_neu.py:88-155 | miscable_silent | mis-numbers or silently drops primary-path miscabled switches; `report_unexpected_connection` (wired into 7 sibling reports) is never called from the DOSTO walk |
| MED | report_dosto_neu.py:42 | wrong_seed | silently defaults the CCU seed to coach 2 when train_type is unset → whole nv6 consist off-by-one; GenericReport hard-exits here, DOSTO-NEU does not |

### Prestage preconditions — assumed-but-unverified CCU/network/human state
| Sev | Location | Class | Finding |
|---|---|---|---|
| MED | update.py:271 | stale_snapshot | update/validate consume `/tmp/discovery.prev.json` with no discover-before-report ordering or staleness guard |
| MED | report.py:306-318 | silent_noop | a device slot with no matching rules.yaml entry gets an empty target and is silently dropped from the update set |
| MED | snmpdevice.py:488 + backbone_validate.py:42-49 | unvalidated_identity | unvalidated train_id stamped into every config; validate self-derives from the same value, hiding a misimage |
| MED | snmpdevice.py:246-251 | crash_on_precondition | `enable_tftp_iptables` raises UnboundLocalError (not a graceful return) on a missing ipset, aborting the update (LOUD) |
| MED | ccudevice.py:61 | unvalidated_identity | CCU self-IP derived arithmetically from hieradata, never reconciled against any interface |
| LOW | validate.py:177-190 | weak_gate | incomplete-device gate is key-presence-only (`issubset`) and never checks `target` → false 'consist complete' confidence (corroborates BS sweep) |

## The fix converges to three primitives
Every confirmed finding maps to one of:
- **P1 — Closed-loop verification on every push.** Read back actual config/firmware/reboot state after the SNMP trigger; never `return True # TODO`. (Kills PUSH-01/02, ST1, and half of FW_DRIFT.)
- **P2 — Per-train device roster / membership gate before enrol + push.** Cross-check discovered serial/MAC/expected-position against an expected roster; reject/quarantine non-members. (Kills the whole security-trust cluster + coupled-consist mis-config; bounds topology-misnumber blast radius.)
- **P3 — Fail-loud on precondition/expectation mismatch.** Assert discovered-vs-expected consist, train_id/self-IP sanity, a rules target per device, stale-snapshot warning. (Covers the topology + prestage clusters.)

All three are in-place hardening — **no rewrite**, consistent with the standing IMPROVE verdict.

## Bearing on the review
- **Verdict unchanged: IMPROVE.** Nothing here is a rewrite trigger.
- These are the **same systemic classes** the existing report already names (None/empty-string, silent-success, validation-gap, stale-cache) — now shown to extend across the *entire onboarding/prestaging path*, not just the report layer. Reinforces, doesn't overturn.
- Two findings (TOPO-6 ≈ context.py coach-1 default; PRE-7 ≈ validate.py:190 issubset) were *independently* confirmed by the earlier BS blind-spot sweep — cross-validation that the pass is sound.
- The 6 refutations (and the severity down-scopes) are the credibility check: the verifiers killed overstatements rather than rubber-stamping.

## Honesty note
The topology + prestage surfaces were verified in a **second** pass — the first sweep hit a session token limit during their verify stage, so they were initially presented as *pending*. They are now fully verified (9 confirmed, 1 refuted). Two security-trust items that errored on verification in pass 1 (unauth API, cred reuse) are already established as S1/S4 in the existing security sweep and are not re-litigated here.
