# OBN Bug 2 — `vdsrail.py`: `re.search` crash when SNMP poll returns None

## Summary

Both `set_firmware_version()` and `set_configuration_version()` in `vdsrail.py` enter a 120-iteration polling loop reading an SNMP task-status OID. When the switch is mid-reboot, the SNMP-get returns `None`. The very next line is `re.search("Not running", result)`, which raises `TypeError: expected string or bytes-like object, got 'NoneType'`. This propagates out of the thread pool and **kills the entire `obn update f all` / `obn update c all` process mid-run**, leaving the remaining devices unupdated and the consist in a mixed-firmware state.

## Affected versions

`nd-obn 2.2.23` confirmed. Same code path in both update modes — single root cause, two crash sites.

## Reproducer

1. Any consist with at least 3 switches, all running OBN 2.2.23.
2. `sudo obn discover && sudo obn report && sudo obn update f all`
3. As soon as the first switch in a batch finishes flashing and starts to reboot, the polling loop on the second switch in the batch will eventually hit an SNMP get-timeout that returns `None`.
4. Traceback ends at one of:
   - `vdsrail.py` ~line 76 (firmware loop): `search = re.search("Not running", result)`
   - `vdsrail.py` ~line 114 (config loop): `search = re.search("Not running", result)`

## Root cause

```python
result = self._snmp_get(self.device_config["snmp_firmware_task_running_oid"])
search = re.search("Not running", result)   # ← crashes when result is None
```

`_snmp_get` returns `None` on timeout / SNMP error. No guard exists.

## Patch

Add a `None` guard in **both** polling loops:

```diff
  result = self._snmp_get(self.device_config["snmp_firmware_task_running_oid"])
+ if not result:
+     continue
  search = re.search("Not running", result)
```

Same fix in `set_configuration_version()` for the config-task polling loop. There are **two distinct sites** — patching only one leaves the other crash mode live.

## Risk / blast radius

Pure addition of a None-handling guard. The `continue` simply re-polls on the next iteration of the existing 120-iteration loop. Worst case (SNMP returns None for all 120 iterations) is a clean fall-through to the loop-exit error handler, which already exists for the "switch never came back" case. No new failure modes.

## Test evidence

Confirmed on 4736-120 (Fzg 148, 2026-05-04) and reproduced on every multi-switch consist where we've run a fresh `obn update`. The two sites must be patched together; we hit Bug 2b (config loop) after patching Bug 2a (firmware loop) on the same train.

## Marker (regression test)

`/usr/share/obn/lib/device/vendor/vdsrail.py` must contain **two** instances of the line `if not result:` — one in `set_firmware_version`, one in `set_configuration_version`. Our skill greps `grep -c "if not result:"` and requires count `>= 2`. A count of 1 means partial patch — same crash mode still latent in the other update path.

## Suggested regression test shape

```python
def test_set_firmware_version_handles_none_snmp_response(mock_snmp_get):
    mock_snmp_get.side_effect = [None] * 5 + ["Not running. System Firmware default image is now foo"]
    # Should not raise; should successfully complete after the 6th poll.
    ...
```

## Existing implementation

`scripts/fix_obn.py` `fix_bug_2()` — both sites patched in one function, with a post-check re-pass to handle the case where 2a applied but 2b's marker matched 2a's so it would have been falsely skipped.
