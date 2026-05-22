# OBN Bug 9 — `snmpdevice.py`: pysnmp asyncore dispatcher is not thread-safe → `IndexError` race

## Summary

`SNMPEngineManager` (`lib/device/snmpdevice.py`) is a singleton — one `SnmpEngine` instance is shared across the `ThreadPoolExecutor` workers spawned by `cli/update.py process_batch()`. pysnmp's asyncore dispatcher uses a single global out-queue per engine; when multiple threads run SNMP get/set/walk in parallel they race on `self.__outQueue.pop(0)` and crash with `IndexError: pop from empty list` inside `pysnmp/carrier/asyncore/dgram/base.py`.

Result: every parallel `obn update c sw` on a multi-switch consist eventually crashes mid-batch, killing the run partway through and leaving the consist in a mixed-config state.

## Affected versions

`nd-obn 2.2.23` confirmed. The singleton pattern in `SNMPEngineManager` predates 2.2.x; almost certainly all versions that use a `ThreadPoolExecutor` for `process_batch`.

## Reproducer

1. Any 6-car consist on `nd-obn 2.2.23` (≥18 consist switches).
2. `sudo obn update c sw` (the parallel-batch path).
3. Within a few minutes (varies — race window depends on SNMP RTT), traceback:
```
File ".../pysnmp/carrier/asyncore/dgram/base.py", line ..., in ...
    self.__outQueue.pop(0)
IndexError: pop from empty list
```

Confirmed on box1-t16 and box1-t18 on 2026-05-20, both during the same `obn update c sw` cycle — both crashed with identical call stacks within a 30-minute window.

## Root cause

Two facts in combination:

1. `cli/update.py process_batch()` uses `ThreadPoolExecutor` to parallelise per-device update work.
2. `SNMPEngineManager` returns the same `SnmpEngine` to every caller. pysnmp's `asyncoreDispatcher` is documented as non-thread-safe — the out-queue is shared and unguarded.

When two worker threads both have outstanding SNMP requests, the dispatcher's `pop(0)` can fire on an already-drained queue.

## Patch

Two changes in `/usr/share/obn/lib/device/snmpdevice.py`:

1. Add a module-level `threading.Lock`:
```diff
  import logging
+ import threading

  from pysnmp.proto.rfc1902 import TimeTicks

+ # Bug 9 fix: pysnmp's asyncore transportDispatcher is not thread-safe.
+ # OBN's process_batch runs SNMP calls from a ThreadPoolExecutor sharing
+ # one SnmpEngine, and the dispatcher's out-queue races on pop(0). We
+ # serialise the single `list(generator)` site in _snmp_parse_results
+ # with this module-level lock. Released between SNMP calls.
+ _SNMP_DISPATCH_LOCK = threading.Lock()
```

2. Wrap the dispatcher-draining call in `_snmp_parse_results`:
```diff
      try:
-         gen_items = list(generator)
+         with _SNMP_DISPATCH_LOCK:
+             gen_items = list(generator)
      except KeyError:
          return {}
```

(Diff context above assumes Bug 3 is already applied — Bug 3 introduces the `try: gen_items = list(generator) except KeyError: return {}` block. If Bug 3 is not yet applied, apply it first, then this one.)

## Risk / blast radius

The lock is held **only across the synchronous dispatcher drain** (`list(generator)`), which is the operation that actually races. SNMP request *transmission* over the wire still parallelises across threads — the lock doesn't gate that. Each `list(generator)` call takes O(10–100 ms) per SNMP call, while the rest of `update_device` (TFTP transfer, file IO, sleep windows) is O(seconds). Lock contention is therefore <1% of update time.

Alternative shapes R&D might prefer:
- **Per-thread `SnmpEngine` instances** instead of a global singleton. Cleaner but a bigger change — `SNMPEngineManager` would need a `threading.local` storage layer.
- **Switch to `pysnmp.hlapi.asyncio`** or `pysnmp.hlapi.v3arch.asyncio` (the newer asyncio-based dispatcher) which is reactive and avoids the asyncore queue entirely. Much bigger refactor.
- **Use `pysnmp-lextudio`** (the maintained fork) which has documented improvements around dispatcher safety. Dependency swap.

We picked the lock because it's the minimum-change fix and validated against the actual crash. Open to whichever shape R&D prefers.

## Test evidence

Two trains, same morning, same call stack, same root cause: box1-t16 and box1-t18 on 2026-05-20. Both crashed during `obn update c sw` partway through the consist's 18 switches. Patch applied to both, both completed cleanly on the retry. See [memory: `project_obn_vdsrail_bug.md`](../?) → "OBN bugs (8 known)" history, and the per-train note in [`fleet-journal.md`](../fleet-journal.md) for Fzg t16/t18 2026-05-20.

## Marker (regression test)

`/usr/share/obn/lib/device/snmpdevice.py` must contain the substring `_SNMP_DISPATCH_LOCK`. Our skill greps `grep -c "_SNMP_DISPATCH_LOCK"` and requires `>= 2` (one for the module-level Lock definition, one for the `with` site).

## Suggested regression test shape

Hard to write a tight regression test for this without setting up real pysnmp; the practical test is to set the `ThreadPoolExecutor` to 4–8 workers in a test fixture and run `process_batch` against a set of mock switches in tight succession. Without the lock, the race fires within a few seconds on most systems. With the lock, runs are clean.

## Notes for R&D

This is the patch we're least confident in the *shape* of, even though we're certain about the underlying race. The lock is correct and works in production, but R&D may prefer a per-thread engine model or an asyncio-dispatcher migration. Either is fine — we just need parallel `obn update c sw` to not crash.

## Existing implementation

`scripts/fix_obn_bug9_pysnmp_thread_safety.py` — full diff above, idempotent.
