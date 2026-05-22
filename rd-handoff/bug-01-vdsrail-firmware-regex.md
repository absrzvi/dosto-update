# OBN Bug 1 — `vdsrail.py`: Firmware regex misses "default image is now" SNMP response

## Summary

After `obn update f all` flashes a switch with a new firmware image, OBN polls the switch's task-status OID to detect "flash done, ready to set as boot default." The current regex only matches the older `"image loaded [X]"` response; the post-flash response on the current Westermo firmware is `"default image is now sw-std-ng_..."`. The regex never matches, so `set_firmware_set_default` is never called, the switch reboots back into the old image bank, and **`obn update f all` reports success.** Silent no-op.

## Affected versions

`nd-obn 2.2.23` confirmed (current fleet). Earlier 2.2.x versions almost certainly affected — the response-string change is on the Westermo side, not OBN.

## Reproducer

1. Fresh CCU on `nd-obn 2.2.23`, consist switches at firmware `< target` (e.g. `7.4.1` with target `7.4.2`).
2. `sudo obn discover && sudo obn report && sudo obn update f all`
3. Observe: every switch reboots, `obn update f all` prints "Successful" for each, exits 0.
4. After reboot completes, `sudo obn discover` shows each switch is still on the old firmware.

## Root cause

`/usr/share/obn/lib/device/vendor/vdsrail.py`, `set_firmware_version()` around line 80:

```python
matchstr = r"Not running. System Firmware image loaded \[(.*)\]"
```

The actual SNMP response during a firmware flash on current Westermo firmware is:

```
"Not running. System Firmware default image is now sw-std-ng_7.4.2-77411.ksi"
```

The regex never matches → the `if search:` branch is never entered → `set_firmware_set_default_oid` is never written → switch boots back into old image bank.

After the set-default OID *has* been applied on a subsequent successful run, the status OID does return the old `"image loaded [X]"` format. So both formats must be handled.

## Patch

```diff
- matchstr = r"Not running. System Firmware image loaded \[(.*)\]"
+ matchstr = r"Not running. System Firmware (?:default image is now|image loaded \[)(.*?)\]?$"
```

Marker for grep-based regression check: the literal string `default image is now` should appear in `vdsrail.py`.

## Risk / blast radius

Pure regex widening — accepts the existing format AND the new one. No behavior change for switches that already return the old format. The capture group is unchanged in semantics (image name), only the surrounding pattern differs.

## Test evidence

Confirmed on 4736-120 (Fzg 148, CCU `10.179.2.1`) 2026-05-04 — every switch in the consist failed to take the new firmware on the first pass, then took it cleanly after the regex was patched. Subsequently reproduced on every train we've patched from a vanilla state.

## Marker (regression test)

`/usr/share/obn/lib/device/vendor/vdsrail.py` must contain the substring `default image is now` in a regex line. Suggested test: parse `vdsrail.set_firmware_version`'s `matchstr` and assert it matches both literal SNMP responses above. Our skill currently uses `grep -c "default image is now"` — count `>= 1` means patched.

## Existing implementation

`scripts/fix_obn.py` `fix_bug_1()` — straight diff above. Alternative: `scripts/fix_bug1_regex.py` (variant that handles the case where the file is in a partial state from a prior incomplete patch run).
