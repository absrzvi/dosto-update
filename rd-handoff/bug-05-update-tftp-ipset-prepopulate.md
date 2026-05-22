# OBN Bug 5 — `update.py`: `tftp_allowed` ipset not pre-populated → silent failure on restart

## Summary

`obn update f all` adds each device's IP to the `tftp_allowed` ipset **as it processes that device**. If the run crashes (e.g. via any of Bugs 2/3/6/7/9 above), devices not yet reached have no ipset entry. On restart, those devices' TFTP fetches are silently dropped by iptables — switch logs `"Connection trouble or invalid URL"`, OBN never sees an error because the fetch never starts, and `obn update f all` reports success on those devices anyway.

This is the **highest-severity silent failure** in the suite: there is no log line, no exception, and no obvious symptom — you only find out by running `obn discover` afterwards and noticing some devices are still on the old firmware.

## Affected versions

`nd-obn 2.2.23` confirmed. The ipset-add-as-we-go pattern is old; almost certainly all 2.2.x.

## Reproducer

1. A consist of >5 switches on `nd-obn 2.2.23` with any of the crash-causing bugs unpatched.
2. `sudo obn update f all` — let it crash partway (or kill it with Ctrl-C after a few devices).
3. `sudo obn update f all` again.
4. Check `sudo ipset list tftp_allowed` — only devices touched in the first run will be present.
5. The second run will "succeed" but devices missing from the ipset will not actually flash. Confirm with `sudo obn discover` showing old firmware on those devices.

## Root cause

`/usr/share/obn/cli/update.py`, `update()` function — IP addition happens inside `process_batch()` per device, not upfront for the whole `update_set.firmware_updates` list. A crashed run leaves the set partially populated.

## Patch

```diff
  logger.info("calculated the update order")

+ # Bug 5 fix: pre-populate tftp_allowed ipset for all targets so that a
+ # mid-run restart doesn't leave devices unable to fetch firmware.
+ import subprocess as _sp
+ for _dev in update_set.firmware_updates:
+     _sp.run(["ipset", "add", "tftp_allowed", _dev.ip, "-exist"],
+             capture_output=True)
+
  # Now, for each batch, we check if they contain devices we need to update.
```

`-exist` makes the add idempotent — already-present IPs are a no-op (not an error).

## Risk / blast radius

This expands the TFTP-allowed window. Currently the ipset only contains devices OBN is *actively* flashing right now; with the fix it contains everything OBN *intends* to flash this run. Practical impact: a slightly longer window (~minutes per batch) during which an unintended device on the management VLAN could fetch from our TFTP server — but those IPs are the consist's own switches/APs, on a private vlan100 with no external access, so the security implication is negligible.

`subprocess.run` shelling out to `ipset` is consistent with how OBN currently manipulates the ipset (also via shell-out). A native Python ipset library exists (`python3-ipset`) but importing it would add a dependency.

## Test evidence

Reproduced on 4734-120 and 4736-103 — both had silent partial-update states until the ipset was pre-populated manually. Once Bug 5 lands, the bash-side fallback (`ipset add tftp_allowed $ip -exist` for all targets) becomes unnecessary.

## Marker (regression test)

`/usr/share/obn/cli/update.py` must contain the literal comment line `# Bug 5 fix: pre-populate tftp_allowed ipset`. (Comment marker is fine for a regression test; the only way the comment disappears is if the patch is reverted.)

## Suggested regression test shape

```python
def test_update_prepopulates_tftp_ipset(mock_ipset_run, update_set_with_5_devices):
    update(update_set_with_5_devices)
    # Pre-population should have added all 5 IPs before any batch processing.
    add_calls = [call for call in mock_ipset_run.call_args_list
                 if call.args[0][:2] == ["ipset", "add"]]
    assert len(add_calls) >= 5  # at least the pre-pop
```

## Notes for R&D

This is one of the patches where **the fix shape is open**. Alternatives R&D may prefer:
- Move the ipset population into a context manager that cleans up on exit.
- Use the Python `python3-ipset` library and avoid the shell-out.
- Restructure `process_batch` to take a callable that adds-then-flashes per device, so the add-and-flash stay atomic per device but happen for the whole set upfront.

Any of those is fine — we just need the post-restart-still-works behavior.

## Existing implementation

`scripts/fix_obn.py` `fix_bug_5()` — the simplest possible diff (shell out, before the batch loop). Tradeoff is the new `import subprocess as _sp` at function scope; R&D may want to lift to module level.
