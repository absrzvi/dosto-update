# Repo plan — landing the v8 patch suite in `nd-obn` and shipping it via `nd-systemupdate`

This is a recommendation, not a prescription. The goal is to give an R&D engineer enough structure to start tomorrow without re-deriving the suite shape, and to make the OBN-patch-to-CCU pipeline visible end-to-end so nobody asks "why doesn't this just work via nd-systemupdate already?"

## End-to-end pipeline (what has to happen for our patches to reach a CCU)

```
nd-obn repo                      Puppet env                      CCU
─────────────                    ─────────                       ───
[MR per bug] ─────merge─────► [tag release 2.2.24] ──pin bump──► [nd-auto-system-update.timer fires]
                                                                  │
                                                                  ▼
                                                            [download new snapshot]
                                                                  │
                                                                  ▼
                                                            [next reboot loads it]
                                                                  │
                                                                  ▼
                                                        [/dosto-obn-patches --check]
                                                          reports 10/10 natively
```

Without a step in this chain, the patches don't reach a CCU. We currently substitute the chroot-promote workflow for steps 2 and onwards, but that's the workaround we want to retire.

## Recommended branch + commit + MR structure (in `nd-obn`)

There are two reasonable shapes:

### Shape A — one MR per bug

- 10 branches: `fix/bug-NN-shortname` (matches the filenames in this handoff folder)
- Each MR contains: the patch + a regression test + a CHANGELOG entry
- Pros: easy partial acceptance, parallel review, can prioritise (Bug 10 first)
- Cons: 10x review overhead

**Recommended for this suite** because Bugs 5, 9, 10 may need shape discussion that shouldn't block Bugs 1, 2, 3, 4, 6, 7, 8 (which are all "narrow None guard" patches with no shape ambiguity).

### Shape B — one MR for the whole suite

- 1 branch: `fix/v8-rollout-patch-suite`
- 10 commits in suggested order (see below)
- 1 MR with all 10 + regression tests
- Pros: single review, coherent story
- Cons: all-or-nothing acceptance; one shape disagreement blocks all 10

Useful as a fallback if R&D wants the whole thing at once.

## Commit order (regardless of MR shape)

Apply in this order to avoid diff conflicts:

1. Bug 4 — `device.firmware` None guard (independent)
2. Bug 8 — `device.config` None guard (independent — could be folded into the same commit as Bug 4)
3. Bug 1 — `vdsrail` firmware regex (independent)
4. Bug 2 — `vdsrail` polling None guards (independent)
5. Bug 6 — `tree.py` cross-consist None guard (independent)
6. Bug 7 — `vdsrail.reboot` hostname None guard (independent)
7. Bug 3 — `snmpdevice` pysnmp KeyError guard (introduces `try: gen_items = list(generator)` block)
8. Bug 9 — `snmpdevice` pysnmp Lock (modifies the `list(generator)` line introduced by Bug 3 — **must come after**)
9. Bug 5 — `update.py` TFTP ipset pre-population (depends on Companion 1 for end-to-end correctness but is independent at code level)
10. Bug 10 — `report_dosto_neu.py` BFS guard (independent)

Bug 3 + Bug 9 are the only two with a real ordering dependency in `snmpdevice.py`.

## Per-bug test plan

| Bug | Test class | Mock seam | Test data |
|---|---|---|---|
| 1 | parse-only (regex match) | none — pure string check | both SNMP response strings as literals |
| 2 | unit test against `set_firmware_version` / `set_configuration_version` | `_snmp_get` returns `None` then a valid string | sequence of returns from a mock |
| 3 | unit test against `_snmp_parse_results` | generator that raises `KeyError("errorIndication")` | hand-rolled generator |
| 4 | parse-only (method returns) | construct `Device(firmware=None)` | `target={"firmware": "X"}` |
| 5 | integration test against `update()` | mock `subprocess.run` for `ipset`; mock `update_set.firmware_updates` with 5 devices | list of 5 mock devices |
| 6 | unit test against `OBNTree.create_tree` | construct a device list where one neighbour MAC doesn't exist | hand-rolled `Device` + neighbour dict |
| 7 | unit test against `VdsRailSwitch.reboot` | `_snmp_get` returns `None`; `_snmp_set` is a mock | none beyond the mocks |
| 8 | parse-only (method returns) | construct `Device(config=None)` | `target={"config": "X"}` |
| 9 | concurrency test using `ThreadPoolExecutor` | run multiple `_snmp_parse_results` calls in parallel against a mock dispatcher | mocked dispatcher with race-prone out-queue |
| 10 | unit test against `number_coaches` with `signal.alarm` watchdog | construct consist with at least one unassignable device | hand-rolled Device list |

We can supply hand-rolled test fixtures for any of these if helpful.

## Release + Puppet sequence

Once any subset of the 10 is in `nd-obn` `main`:

1. **Tag `2.2.24-v8patches`** (or whatever R&D's release-naming convention prefers). The tag should list which bugs are included so we can correlate against our skill's `--check` output per CCU.
2. **Bump the Puppet env `dostoneu_migration_mar5`** (or the post-migration env, whichever is correct as of release date) to pin `nd-obn` at the new tag. Note: this is the env that `nd-auto-system-update.timer` pulls from on every nightly cycle — our trains will pick up the new version automatically once the env is bumped.
3. **Notify us** so we can:
   - Update the skill's marker matrix to know which bugs are now natively present (so `--check` doesn't recommend re-applying patches that are already in the package)
   - Remove the `.dont` rename workaround from `nd-systemupdate.sh` on the fleet — once the auto-update timer is delivering known-good snapshots, we want it firing again
   - Update `fleet-status.md` to track per-train `nd-obn` version instead of patch counts

We will not need any code change in the skill except marker-matrix updates — the skill is designed for this transition.

## What we're NOT asking for

- No changes to the OBN CLI shape (`obn discover`, `obn report`, `obn update`, `obn validate` — same commands, same args, same outputs).
- No changes to the chroot/btrfs persistence machinery (`nd-systemupdate.sh`, `safe_reboot`).
- No changes to OBN's data-model (Device, SNMPEngineManager, OBNTree, etc.) beyond what each bug doc specifies.

Each patch is the minimum surgical change that fixes the specific failure. R&D is welcome to refactor toward a better shape (e.g. the `_snmp_get_with_retry(returns_sentinel_on_failure)` helper that would eliminate Bug 2, 3, 4, 7, 8 in one go) but that's a bigger MR and we wouldn't block on it.

## Estimated R&D effort

For all 10 bugs as Shape A MRs, with regression tests:
- Bugs 1, 2, 4, 6, 7, 8 — ~30 min each (10-line diffs, straightforward unit tests)
- Bug 3 — ~1 hour (small diff but needs the right mock seam for pysnmp)
- Bug 5 — ~2 hours (largest diff; integration test against `update()`; possible shape discussion)
- Bug 9 — ~2 hours (lock placement is straightforward but R&D may want to discuss per-thread engines vs. lock; concurrency test is fiddly)
- Bug 10 — ~1 hour (small diff; needs the `signal.alarm` termination test)

**Total: ~1 person-day** of focused work for the suite, plus review overhead. The longest-running item is review consensus on Bugs 5 and 9 fix shapes.

## Once the suite is in: what we'd want monitored

Three failure modes our skill currently catches that we'd want OBN's own logs / metrics to surface so we don't need the skill:

1. **Partial patch state.** If a CCU somehow ends up with `nd-obn` partially patched (e.g. someone reverted one commit on a deploy branch), `obn discover` could emit a startup warning. Less important once the suite is upstream and the chroot workflow goes away.
2. **`obn report` taking longer than expected.** Bug 10 used to manifest as "ran for hours." A simple "if `number_coaches` took >30s, log a warning with the device list" would catch any future BFS-style hangs we haven't yet seen.
3. **Silent partial success on `obn update`.** Bug 5 manifested as "all looked successful but devices weren't actually flashed." A post-batch verification that re-`discover`s the targets and warns on any that didn't move would catch this and Companion 2 (factory-AP SNMP silent drop) in one shot.

None of these are blocking — they're "while you're in the code anyway" notes.
