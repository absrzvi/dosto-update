# RCA — `obn report` infinite loop in `number_coaches()` (DOSTO NEU)

**Document ID:** RCA-OBN-BFS-001
**Date:** 2026-06-02
**Author:** Abbas Rizvi (Nomad Digital)
**Severity:** High — single unreachable/miswired switch hangs `obn report` indefinitely, which blocks the entire `discover → report → update` commissioning workflow and consumes the CCU's memory toward OOM.
**Affected component:** `nd-obn` `2.2.23` — `/usr/share/obn/lib/report/report_dosto_neu.py`, method `DostoNeuReport.number_coaches()`
**Affected train types:** `nv4` (4-car) and `nv6` (6-car) DOSTO NEU. Same code path for both.
**Status:** Reproduced live; root cause confirmed in source; local hand-patch exists but is not upstreamed.

---

## 1. Summary

`obn report` enters an unbounded loop in `number_coaches()` whenever the discovered
device graph contains one or more switches/APs that cannot be assigned a coach
number — for example when an inter-coach trunk is physically unconnected, a switch
is unreachable, or a switch is misimaged so its LLDP adjacency doesn't match the
hard-coded DOSTO NEU topology model.

The breadth-first traversal re-enqueues such devices **unconditionally** on every
pass. They never acquire a `coach_number`, so they are popped and re-pushed
forever. Observed effect on a live CCU: **one core pinned at 99.9% CPU and RSS
growing without bound (47 GB measured) until the process is killed or the box
OOMs.**

The defect is not "the topology is incomplete" — incomplete topology is a normal,
expected field condition (Stadler cabling faults, staged commissioning,
powered-off coaches). The defect is that the algorithm **has no termination guard
for that condition**. A device it cannot place should be reported as an error, not
looped on.

---

## 2. Observed incident (ground truth)

Captured live on **2026-06-02** from CCU `box1-t54` (`10.179.54.1`), train
**4734-190 / Fzg 90**, a 4-car `nv4` consist.

| Signal | Value | Note |
|---|---|---|
| Hung process | `obn report` (PID 28456) | `/usr/share/obn/venv/bin/python /usr/local/bin/obn report` |
| CPU | **99.9%** (state `R`) | one core fully pinned |
| CPU time consumed | **101 min** | over a 1h47m uptime — almost the entire boot |
| Resident memory | **~47 GB RSS (72% of RAM)** | unbounded `deque.appendleft` growth |
| Switches discovered | **12/12 present**, all named `nv4-{A,B,E,G}{1,2,3}-v8-090` | topology is otherwise *complete* |
| Known fault on this train | **G2 (`10.179.54.191`) port `e0-0` has no inter-coach LLDP neighbour** | Stadler cabling fault, logged in fleet-status since 2026-05-22 |

**Important nuance:** all 12 switches were present and correctly imaged. The loop
was *not* caused by a missing or duplicate switch hostname (the earlier-suspected
trigger). It was caused by a single **unconnected trunk port** (G2 `e0-0`), which
breaks the B1→E1→G2 numbering chain. That is enough to leave those switches'
`coach_number = None` and trigger the loop. The bug is therefore broader than
"misimaged switches" — **any** break in the modelled adjacency chain triggers it.

History of recurrence (from engineering memory / fleet-status):
- Fzg 130 (`box1-t47`) — 2026-05-12 — first observed; 3 misimaged switches with duplicate hostnames.
- Fzg 8 (`box1-t29`) — 2026-05-22 — recurred; local patch written.
- Fzg 90 (`box1-t54`) — 2026-06-02 — this incident; unconnected trunk, no misimaging.

---

## 3. Root cause (source-level)

File: `/usr/share/obn/lib/report/report_dosto_neu.py`, method `number_coaches()`.

The method seeds a queue with the CCU (`type == "BOX"`, known coach number) and
walks neighbours, assigning each discovered switch/AP a `coach_number` and
`device_number` according to a large set of **hard-coded port-adjacency rules**
specific to the DOSTO NEU consist layout.

### 3.1 The enqueue guard at the top of the loop (lines ~46–48)

```python
to_device = self.get_device(neighbour)
# If we can't match the neighbour's MAC ... skip. If the target device already
# has a coach number, skip it as well.
if to_device is None or to_device.coach_number is not None:
    continue
```

This guard only short-circuits devices that **already have** a coach number. It
does nothing for a device that *cannot be assigned* one.

### 3.2 The unconditional re-enqueue at the bottom of the loop (line 282)

```python
                    # nv6 - END

                # Add to_device to queue
                queue.appendleft(to_device)
                continue
```

`queue.appendleft(to_device)` runs for **every** neighbour that passed the line-48
guard — regardless of whether any of the intervening `if` branches actually set
`to_device.coach_number`.

### 3.3 Why it loops forever

The numbering logic is a chain of conditionals of the form
"if `from_device` is SW N of coach C and the neighbour is on port P, then the
neighbour is SW M of coach C±1." These rules assume a **fully-connected,
correctly-imaged** consist. When the real topology deviates:

1. A device `D` is reached as a neighbour, passes the line-48 guard (its
   `coach_number` is still `None`).
2. **No** conditional branch matches `D`'s actual (port, device_number,
   coach_number) situation — because the chain feeding it was broken upstream
   (e.g. G2's `e0-0` peer is absent, so nothing ever assigns G2/E1/B1 a coach).
3. `D.coach_number` is therefore still `None` at line 282.
4. Line 282 re-enqueues `D` anyway.
5. `D` is popped again; its neighbours are re-walked; `D` (and its still-unnumbered
   neighbours) are re-enqueued again. **Go to 2.**

There is no `visited` set, no per-device enqueue cap, and no overall iteration
bound. The `deque` grows on every `appendleft`, which is the source of the
unbounded memory growth, while the CPU spins on the repeated neighbour walk.

---

## 4. Impact

- **Workflow blocker.** `obn report` commits the discovery scan into
  `discovery.prev.json`, which `obn update c`, `obn update f`, and `obn validate`
  all read from. A hung `obn report` blocks the entire commissioning pipeline for
  the affected train — no config push, no firmware push, no validation.
- **Resource exhaustion.** Unbounded RSS growth drives the CCU toward OOM; other
  CCU services (telemetry, redundancy, mqtt-bridge) are put at risk on a
  production box.
- **Silent failure mode.** `obn report` prints nothing and never returns. An
  engineer who walks away assumes it's "still working." There is no log line, no
  timeout, no error — the opposite of the desired behaviour.
- **Masks the real, actionable fault.** The genuine field problem (a Stadler
  cabling fault, a misimaged switch) is exactly what the report *should* surface.
  Instead it's hidden behind a hang.

---

## 5. Expected vs. actual behaviour

| | Behaviour |
|---|---|
| **Expected** | `obn report` completes in bounded time. If one or more devices cannot be assigned a coach number, it logs/reports them by MAC/IP/hostname as "could not be placed in consist topology" and produces a report for the devices it *could* place (or exits non-zero with a clear diagnostic). |
| **Actual** | `obn report` spins one core at 100%, grows memory without bound, never returns, emits no diagnostic. Must be killed manually. |

---

## 6. Recommended fix

### 6.1 Minimal, immediate (matches the field hand-patch)

Guard the enqueue so only devices that were actually numbered this pass are
re-queued:

```python
                    # nv6 - END

                # Bug 10 fix: only enqueue if a coach_number was assigned in one
                # of the branches above. Without this, switches/APs whose
                # adjacency didn't match (broken trunk, misimaged switch,
                # unreachable device) get re-enqueued forever and hang obn report.
                if to_device.coach_number is not None:
                    queue.appendleft(to_device)
                continue
```

This terminates the loop: a device that can't be placed is simply not re-enqueued,
the queue drains, and `normalise_devices()` (already called at the end) removes the
unplaced devices.

> This exact patch is staged locally as
> `scripts/fix_obn_bug10_report_dosto_neu_bfs.py` (idempotent, marker
> `# NDP-PATCH-BUG10-BFS-GUARD`). It has been hand-applied on Fzg 8 and is needed
> again on Fzg 90. It is **not** upstream, so it is wiped by every Puppet/auto-update
> and must be re-applied after each CCU reboot — which is the reason this ticket
> exists.

### 6.2 Recommended additional hardening (do in the same change)

The minimal fix stops the hang but still *silently drops* unplaced devices via
`normalise_devices()`. To meet the "report it, don't loop on it" goal:

1. **Emit a diagnostic for every unplaced device.** After the BFS, iterate
   `self.device_instances.values()` and for each non-BOX device with
   `coach_number is None`, log a `WARNING`/`ERROR` with its MAC, IP, hostname, and
   discovered neighbours — e.g. *"Could not assign coach number to nv4-G2-v8-090
   (10.179.54.191); no modelled adjacency from a numbered switch. Check inter-coach
   trunk cabling / switch image."* This turns the cabling fault into an actionable
   report line instead of a hang.
2. **Add a hard iteration cap as a backstop** (defence in depth): bound the
   `while queue` loop at, e.g., `O(len(device_instances) * max_neighbours)` and
   raise/log if exceeded, so any *future* graph pathology can never reproduce an
   unbounded loop.
3. **Consider a `visited` set / processed-edge tracking** so the BFS is provably
   terminating regardless of input graph shape, rather than relying on the
   coach_number side-effect as the loop variant.

### 6.3 Scope note

`number_coaches()` exists per-project (`report_ace.py`, `report_dsb.py`,
`report_tgv.py`, etc. all define their own). This RCA covers **only**
`report_dosto_neu.py`. R&D should check whether the same unconditional-enqueue
pattern exists in the sibling report classes and apply the same guard/backstop
where applicable.

---

## 7. Reproduction

1. Take any DOSTO NEU consist (nv4 or nv6) and break one inter-coach trunk in the
   numbering chain — physically disconnect a switch's `e0-0`/`e0-1` trunk peer, or
   power off / misimage one switch so its LLDP adjacency no longer matches the
   model. (Live repro: Fzg 90, G2 `e0-0` unconnected.)
2. On the CCU run `sudo obn discover` then `sudo obn report`.
3. Observe `obn report` pinned at ~100% CPU with continuously growing RSS, never
   returning. `ps -o pcpu,rss,etime -C python` confirms the climb.

---

## 8. Workaround (operational, until fix ships)

- Kill the hung process: `sudo kill <pid>` (escalate to `-9` if needed).
- Apply the local guard patch via `scripts/fix_obn_bug10_report_dosto_neu_bfs.py`
  (or `dosto-obn-patches`), then re-run `sudo obn discover && sudo obn report`.
- **Re-apply after every reboot** — the patch is not persisted upstream. (For Fzg
  90 specifically, the underlying G2 `e0-0` cabling fault should also be fixed by
  Stadler; the patch lets `obn report` complete and *report* the fault meanwhile.)

---

## 9. References

- Source: `/usr/share/obn/lib/report/report_dosto_neu.py:282` (`nd-obn 2.2.23`)
- Local fix: `scripts/fix_obn_bug10_report_dosto_neu_bfs.py`
- Skill: `dosto-obn-patches` (Bug 10), `dosto-commission-train`
- Fleet-status: row `4734-190 / Fzg 90` (BLOCKED on G2 e0-0 since 2026-05-22)
- Prior occurrences: Fzg 130 (box1-t47, 2026-05-12), Fzg 8 (box1-t29, 2026-05-22)
