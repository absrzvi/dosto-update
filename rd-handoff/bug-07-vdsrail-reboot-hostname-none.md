# OBN Bug 7 — `vdsrail.py`: `reboot()` crashes when SNMP-get hostname returns None mid-reboot window

## Summary

During `obn update c all`, after a batch of switches has just received their config push and is starting to reboot, OBN calls `vdsrail.reboot()` on each one. That method first SNMP-gets the current hostname, then SNMP-sets it back (a "preserve hostname through reboot" step), then sends the reboot OID. If the switch has already started rebooting between the get and the set (a few hundred milliseconds), the get returns `None`. The subsequent `_snmp_set({oid: None})` calls into pyasn1 which raises `TypeError: cannot convert 'NoneType' object to bytes`. The whole `obn update` process crashes — same blast radius as Bugs 2/3.

## Affected versions

`nd-obn 2.2.23` confirmed. Same code path back to at least 2.2.20.

## Reproducer

1. Any consist of ≥6 switches on `nd-obn 2.2.23`.
2. `sudo obn discover && sudo obn report && sudo obn update c all`
3. Second batch (typically A1/A2/A3/B1/B2/B3 or similar) — one of the earlier switches in the batch will reboot during the SNMP-get/set window for a later switch.
4. Traceback:
```
File "/usr/share/obn/lib/device/vendor/vdsrail.py", line 124, in reboot
    self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
File "/usr/share/obn/venv/lib/python3.11/site-packages/pyasn1/type/univ.py", line 886, in prettyIn
    return bytes(value)
TypeError: cannot convert 'NoneType' object to bytes
```

## Root cause

`/usr/share/obn/lib/device/vendor/vdsrail.py`, `reboot()` ~line 122:

```python
def reboot(self) -> bool:
    hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])
    self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})   # ← hostname may be None
    self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})
```

## Patch

```diff
  def reboot(self) -> bool:
      hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])
-     self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
+     if hostname is not None:
+         self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
      self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})
```

Skip the hostname round-trip if the get failed — the reboot OID is still sent. Worst case the switch reboots with whatever hostname it currently has (which is the *same value* we would have re-set), so functionally identical.

## Risk / blast radius

Functionally a no-op compared to the intended behavior — the get-then-set pattern is "preserve hostname"; if get returns None we just skip the preserve, the hostname stays whatever it already is. Strictly safer than the current crash.

## Test evidence

Confirmed on 4736-120 (Fzg 148, 2026-05-04). The handoff note in the original runbook calls out: *"A unified `_snmp_get_with_retry()` helper that returns a sentinel on failure would eliminate this entire bug class (2, 3, 4, 7, 8)."* — that's a more invasive refactor for R&D to consider; this MR is the minimum surgical fix.

## Marker (regression test)

`/usr/share/obn/lib/device/vendor/vdsrail.py` must contain `if hostname is not None:` followed (on the next line, possibly with whitespace) by `self._snmp_set`. Our skill greps `grep -c "if hostname is not None:"` and requires `>= 1`.

## Suggested regression test shape

```python
def test_reboot_skips_hostname_set_on_none(mock_snmp_get, mock_snmp_set):
    mock_snmp_get.return_value = None  # simulate switch already rebooting
    sw = VdsRailSwitch(...)
    assert sw.reboot() is True
    # Only the reboot OID set should have been called, not the hostname set.
    set_oids = [call.args[0] for call in mock_snmp_set.call_args_list]
    assert all("set_hostname" not in str(oid) for oid in set_oids)
```

## Existing implementation

`scripts/fix_obn.py` `fix_bug_7()` (canonical) and `scripts/fix_obn_bugs67.py` (fallback for the partial-state case).
