# OBN Bug 10 — `report_dosto_neu.py`: `number_coaches` BFS infinite-loop + 27GB RSS leak on missing/duplicate device

## Summary

`obn report` walks the DOSTO NEU consist graph via BFS in `number_coaches()` (`lib/report/report_dosto_neu.py`). The loop unconditionally enqueues every neighbour device back into the BFS queue at the end of each iteration — *even when no topology rule fired and `to_device.coach_number` was never assigned*. The early-iteration guard at line 47–48 (`if to_device.coach_number is not None: continue`) only filters devices that **already** have a number, so unassignable devices spin forever: pop → no rule matches → re-enqueue → pop → ...

**This is the only failure mode in the entire OBN suite that hangs rather than crashes.** `obn report` pins one CPU core at 100% and leaks RSS continuously (`27 GB+` observed before OOM on Fzg 130). It requires `kill -9` to recover — `Ctrl-C` doesn't reach the inner loop fast enough.

The trigger is **any DOSTO NEU consist where at least one device cannot be assigned a coach position**. In practice this happens whenever:
- An AP or switch is offline / missing from discovery (cabling fault, power-off, AP brick).
- Two switches share a duplicate position label (misimaged switch, hand-edited template gone wrong).
- A new edge-case topology that the rule set doesn't yet cover.

## Affected versions

`nd-obn 2.2.23` confirmed. The `number_coaches` function with the unconditional re-enqueue has been in the DOSTO NEU report module since the NEU consist support was added — almost certainly all 2.2.x.

## Reproducer

Easiest reproducer (literal):

1. Any DOSTO NEU consist (4734 4-car or 4736/4705/4706 6-car) on `nd-obn 2.2.23`.
2. Power off one switch or one AP — anything that creates a "missing from discovery" entry.
3. `sudo obn discover && sudo obn report`
4. Observe `obn report` running indefinitely. `top` shows ~100% CPU, RSS growing several hundred MB/minute.
5. Wait 5 minutes, check RSS. Will be several GB. Eventually OOM-killed.

Alternative reproducer (duplicate position):

1. Same consist, all devices online.
2. Manually misimage one switch so two switches both render with the same hostname (`{train_id} = X` in both their templates pointing at the same coach position).
3. Same result.

## Root cause

`/usr/share/obn/lib/report/report_dosto_neu.py` around line 280–282:

```python
                    # nv6 - END

                # Add to_device to queue
                queue.appendleft(to_device)
                continue
```

The `queue.appendleft(to_device)` is unconditional. If none of the topology-rule branches above (nv4-START, nv4-MID, nv4-END, nv6-START, nv6-MID, nv6-END) matched and assigned `to_device.coach_number`, the device sits at `coach_number = None`. The early-loop guard `if to_device.coach_number is not None: continue` (around line 47) is intended to be the cycle-breaker — but it only breaks the cycle for devices that *got* a number, never for devices that didn't.

So a device whose topology rule never fires gets re-enqueued forever:
- Iteration N: pop, no rule matches, re-enqueue
- Iteration N+1: pop, no rule matches, re-enqueue
- ...

Each iteration also walks the device's neighbours and may discover additional candidate devices to enqueue (which is what drives the unbounded memory growth — the queue grows faster than it shrinks once any device gets stuck).

## Patch

```diff
                    # nv6 - END

-               # Add to_device to queue
-               queue.appendleft(to_device)
-               continue
+               # Add to_device to queue # NDP-PATCH-BUG10-BFS-GUARD
+               # Bug 10 fix: only enqueue if coach_number was assigned in
+               # one of the branches above. Without this, APs and edge
+               # switches whose conditions didn't match get re-enqueued
+               # forever, hanging obn report at 100% CPU.
+               if to_device.coach_number is not None:
+                   queue.appendleft(to_device)
+               continue
```

## Risk / blast radius

A device that cannot be assigned a coach number is now silently dropped from the BFS queue. That's the correct behavior — there's nothing useful the BFS can do with such a device, and the existing post-BFS `test_unnumbered_devices` validation in `obn validate` already surfaces the "couldn't assign coach number to X" warning that tells the engineer something is wrong with the consist.

Functional change: `obn report` now **completes** on a not-fully-online consist, surfacing the unassignable device as a warning rather than as a hang. This is a strict improvement: today we cannot run `obn report` at all on Fzg 130 and Fzg 191 (both have known missing devices); after the patch we can.

A future improvement (not blocking) would be to log `DEBUG: skipping unassignable device <ip> <mac> (no topology rule matched)` at the skip point so the engineer can see what was dropped. We left that out of the minimum-surgical fix.

## Test evidence

- **Fzg 130 (box1-t47), 2026-05-12** — first observed. Duplicate switch positions from three misimaged switches. `obn report` hung, RSS climbed past 27 GB before we killed it. Patch applied, `obn report` then completed in ~12 seconds.
- **Fzg 191 (box1-t? — 4706-103), 2026-05-20** — recurred. Missing switches C1/C3 (powered off). Same hang. Same patch worked.
- **Fzg 8 (box1-t29 — 4734-108), 2026-05-22** — recurred. Patch applied via chroot promote, `obn report` then completed.

See memory entries [`project_obn_update_target_catch22.md`](../?) and [`project_obn_bug10_bfs_fix.md`](../?) for the original investigation and fix derivation.

## Marker (regression test)

`/usr/share/obn/lib/report/report_dosto_neu.py` must contain the comment string `# NDP-PATCH-BUG10-BFS-GUARD`. Our skill greps for that literal.

## Suggested regression test shape

```python
def test_number_coaches_terminates_with_unassignable_device(consist_with_missing_switch):
    # consist_with_missing_switch: a Device list where one device has no
    # topology rule that will match (e.g. a switch in a position the
    # rule set doesn't cover, or a device with no neighbours).
    import signal
    def timeout_handler(signum, frame):
        raise TimeoutError("number_coaches did not terminate")
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 seconds is generous; should complete in <1s
    try:
        result = number_coaches(consist_with_missing_switch)
    finally:
        signal.alarm(0)
    # Unassignable device should be flagged (coach_number is None), not crash, not hang.
    unassigned = [d for d in result if d.coach_number is None]
    assert len(unassigned) >= 1
```

The `signal.alarm`-based timeout is crude but is the only way to assert termination on a function that previously didn't terminate.

## Priority

**Highest in the suite.** This is the only patch that:
- Stops a memory leak (27 GB+ RSS observed)
- Requires `kill -9` to recover (Ctrl-C is too slow)
- Blocks `obn report` entirely on any not-fully-online consist — and the v8 rollout has multiple trains with known offline devices that we can't `obn report` on at all today

If R&D can only land one of these 10 in the next release, this is the one.

## Existing implementation

`scripts/fix_obn_bug10_report_dosto_neu_bfs.py` — full diff above, idempotent, with the canonical `NDP-PATCH-BUG10-BFS-GUARD` marker.
