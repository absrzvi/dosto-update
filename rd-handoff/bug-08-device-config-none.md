# OBN Bug 8 — `device.py`: `.endswith()` on None config crashes `needs_configuration_update`

## Summary

Exact same shape as Bug 4, but for `self.config` instead of `self.firmware`. `Device.needs_configuration_update()` returns `not self.config.endswith(self.target["config"])`. If `self.config` is `None`, `.endswith()` raises `AttributeError`. This crashes `obn update c all` immediately during the pre-batch "what needs updating" pass.

## Affected versions

`nd-obn 2.2.23` confirmed. Same fix family as Bug 4 — almost certainly the same range of versions.

## Reproducer

1. Any consist with at least one device whose config string can't be read (typically a factory-config AP or a switch mid-reboot during discover).
2. `sudo obn discover && sudo obn update c all`
3. Traceback ends at `device.py needs_configuration_update`: `AttributeError: 'NoneType' object has no attribute 'endswith'`

## Root cause

`/usr/share/obn/lib/report/device.py`:

```python
def needs_configuration_update(self) -> bool:
    return not self.config.endswith(self.target["config"])
```

`self.config` is `None` when discovery couldn't read a config-version string.

## Patch

```diff
- return not self.config.endswith(self.target["config"])
+ return bool(self.config) and not self.config.endswith(self.target["config"])
```

## Risk / blast radius

Identical to Bug 4. Device with unknown config returns `False` (does not need update). Strictly safer than crashing.

## Test evidence

Confirmed on multiple trains where a factory-config AP returned `config: None` from discover. R&D should consider Bugs 4 and 8 as one MR with parallel diffs.

## Marker (regression test)

`/usr/share/obn/lib/report/device.py` must contain the substring `bool(self.config) and not self.config.endswith`.

## Suggested regression test shape

```python
def test_needs_configuration_update_returns_false_on_none_config():
    d = Device(config=None, target={"config": "v8-132"})
    assert d.needs_configuration_update() is False
```

## Existing implementation

`scripts/fix_obn_bug8.py` — minimal standalone script (Bug 8 is not in `fix_obn.py` for historical reasons; could trivially be folded in).

## Related

Bug 4 ([`bug-04-device-firmware-none.md`](bug-04-device-firmware-none.md)) is the exact mirror for `self.firmware`. One MR for both is the obvious move.
