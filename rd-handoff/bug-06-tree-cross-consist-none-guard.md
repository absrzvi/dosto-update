# OBN Bug 6 — `tree.py`: `AttributeError` crash when a coupled consist's switches appear as LLDP neighbours

## Summary

When two consists are physically coupled (front-coupler trunks live), the end-car switches (B1, B3 on a 6-car) learn LLDP entries for the *neighbouring* consist's switches. Those switches are on a different management subnet (e.g. `10.179.11.x` when we're working on `10.179.2.x`) and are not part of the local `discovery.json`. The tree builder tries to look them up, gets `None`, then immediately dereferences `.type` → `AttributeError: 'NoneType' object has no attribute 'type'`. `obn update c <ip>` and `obn update c all` crash immediately after `[+] creating TFTP firmware folder`.

## Affected versions

`nd-obn 2.2.23` confirmed. Latent on every CCU — only triggers when the consist is actually coupled to another live unit.

## Reproducer

1. Two coupled DOSTO NEU consists, both powered, front-coupler trunks live.
2. On one CCU: `sudo obn discover && sudo obn report && sudo obn update c all`
3. Traceback:
```
File "/usr/share/obn/lib/tree.py", line 34, in create_tree
    if neighbour_device.type == "BOX":
AttributeError: 'NoneType' object has no attribute 'type'
```
4. Confirm via `sudo obn validate` showing:
```
⚠ test_unnumbered_devices: couldn't assign coach number to 10.179.11.x, 10.179.11.y
```
Those `.11.x` IPs belong to the coupled consist.

## Root cause

`/usr/share/obn/lib/tree.py`, `OBNTree.create_tree()`:

```python
neighbour_device = next((x for x in devices if x.mac == neighbour["mac"]), None)
if neighbour_device.type == "BOX":   # ← crashes if neighbour_device is None
    continue
```

`next(..., None)` returns `None` for any neighbour MAC not in the local device list. The immediate `.type` access has no guard.

## Patch

```diff
+ if neighbour_device is None:
+     continue  # neighbour not in this consist (e.g. coupled train on another subnet)
  if neighbour_device.type == "BOX":
      continue
  if neighbour_device.mac not in tree:
```

## Risk / blast radius

Skipping unknown neighbours is the correct semantics — we cannot build tree edges to devices we know nothing about. The current behavior (crash on first such neighbour) gives us strictly less information; the patched behavior at worst loses a tree edge to a coupled-consist device we wouldn't have been able to use anyway.

Worth flagging: the cross-consist neighbour data is itself useful (it tells us the consists are coupled and which ports are seeing each other). A future enhancement could log a debug-level "skipped cross-consist neighbour: <mac> <ip>" so the data isn't silently discarded. Not blocking for this MR.

## Test evidence

First confirmed on 4736-120 (Fzg 148, 2026-05-04) coupled to a neighbouring consist on `10.179.11.x`. Reproduced on every coupled-consist scenario since — the bug is deterministic when the condition is met.

## Marker (regression test)

`/usr/share/obn/lib/tree.py` must contain the comment string `neighbour not in this consist`. Our skill greps for that literal.

## Suggested regression test shape

```python
def test_create_tree_skips_unknown_neighbour_mac(devices_with_unknown_neighbour):
    # devices_with_unknown_neighbour: a device list where one device's LLDP
    # neighbour MAC doesn't appear in the device list itself.
    tree = OBNTree(devices_with_unknown_neighbour)
    tree.create_tree()
    # Should not raise.
    # The unknown neighbour should simply not appear in the tree edges.
```

## Existing implementation

`scripts/fix_obn.py` `fix_bug_6()` (canonical) and `scripts/fix_obn_bugs67.py` (fallback that handles the case where Bug 6 has already been partially applied by an earlier `fix_obn.py` run — see audit finding F7 in `handoff-bootstrap-audit-2026-05-11.md` for the idempotency interaction).
