# OBN Bug 4 — `device.py`: `.endswith()` on None firmware crashes `needs_firmware_update`

## Summary

`Device.needs_firmware_update()` returns `not self.firmware.endswith(self.target["firmware"])`. If `self.firmware` is `None` (device that's rebooting, has SNMP auth issues, or just hasn't returned its firmware reading yet), the `.endswith()` call raises `AttributeError: 'NoneType' object has no attribute 'endswith'`. This crashes `obn update f all` immediately during the pre-batch "what needs updating" pass, before any device has been touched.

## Affected versions

`nd-obn 2.2.23` confirmed. Most likely affects all 2.2.x.

## Reproducer

1. Any consist with at least one AP that doesn't respond to SNMP firmware-version query (factory-config AP, AP mid-reboot, AP with bad cable).
2. `sudo obn discover && sudo obn update f all`
3. Traceback ends at `device.py needs_firmware_update`: `AttributeError: 'NoneType' object has no attribute 'endswith'`

## Root cause

`/usr/share/obn/lib/report/device.py`:

```python
def needs_firmware_update(self) -> bool:
    return not self.firmware.endswith(self.target["firmware"])
```

`self.firmware` is `None` when discovery couldn't read a firmware string from the device. No guard.

## Patch

```diff
- return not self.firmware.endswith(self.target["firmware"])
+ return bool(self.firmware) and not self.firmware.endswith(self.target["firmware"])
```

Semantics: a device with unknown firmware returns `False` (does not need update) — defensible because we genuinely don't know if it needs one, and a `True` here would cause us to try to flash it without confirming current state.

## Risk / blast radius

A device with truly-unknown firmware will no longer be flashed in this pass. That's arguably *safer* than the current "crash before doing anything" behavior — at minimum it lets `obn update f all` proceed on the devices we *can* verify. The device with unknown firmware will be picked up on the next discover/update cycle once SNMP is responding.

## Test evidence

Confirmed on multiple trains — any consist with a transient AP SNMP failure triggers it. The pattern (`bool(x) and ...`) is the standard short-circuit defensive guard for this kind of None-on-attribute access; we reuse it in Bug 8 for `self.config`.

## Marker (regression test)

`/usr/share/obn/lib/report/device.py` must contain the substring `bool(self.firmware) and not self.firmware.endswith`. Our skill greps for that literal.

## Suggested regression test shape

```python
def test_needs_firmware_update_returns_false_on_none_firmware():
    d = Device(firmware=None, target={"firmware": "7.4.2"})
    assert d.needs_firmware_update() is False  # not True, not exception
```

## Existing implementation

`scripts/fix_obn.py` `fix_bug_4()` — straight diff above.

## Related

Bug 8 ([`bug-08-device-config-none.md`](bug-08-device-config-none.md)) is the exact same pattern for `self.config` in `needs_configuration_update`. R&D could fix both in one MR if they prefer; the diff is parallel.
