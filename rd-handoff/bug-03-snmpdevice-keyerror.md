# OBN Bug 3 — `snmpdevice.py`: pysnmp `KeyError: 'errorIndication'` propagates from thread pool

## Summary

`_snmp_parse_results()` consumes a pysnmp asyncore generator. When a switch reboots mid-SNMP-session, pysnmp's asyncore internal context dict loses the `'errorIndication'` key. Iterating the generator raises `KeyError: 'errorIndication'` from deep inside pysnmp. This unhandled exception bubbles through `concurrent.futures` and kills the whole update process.

## Affected versions

`nd-obn 2.2.23` confirmed. This is pysnmp's internal state-machine quirk surfacing through OBN's iteration — fix is on OBN's side because we cannot patch pysnmp from here.

## Reproducer

1. Any consist on `nd-obn 2.2.23`.
2. `sudo obn update c all` against a multi-switch batch where any switch reboots during SNMP polling.
3. Traceback bottom shows `KeyError: 'errorIndication'` in pysnmp's asyncore dispatcher; the immediate OBN frame is `_snmp_parse_results` iterating `generator`.

## Root cause

`/usr/share/obn/lib/device/snmpdevice.py`, `_snmp_parse_results()`:

```python
for error_indication, error_status, _, var_binds in generator:
    ...
```

If the generator raises `KeyError` partway through, there's no guard — exception propagates up.

## Patch

```diff
- for error_indication, error_status, _, var_binds in generator:
+ try:
+     gen_items = list(generator)
+ except KeyError:
+     return {}
+ for error_indication, error_status, _, var_binds in gen_items:
```

Returning `{}` mimics the "no SNMP data this round" path that already exists for clean timeouts.

## Risk / blast radius

Catches a narrow exception (`KeyError`) from a known-broken pysnmp path. Any *other* exception class still propagates. Forcing the generator to a list before iteration is a small memory cost (typically <10 var-binds per SNMP call); negligible compared to the cost of crashing the update.

A wider `try/except Exception` would be a code smell; `KeyError` only is correct because we've isolated the specific pysnmp failure mode.

## Test evidence

Confirmed on 4736-120 (Fzg 148, 2026-05-04). Same crash family as Bugs 2/4/7 — all are "SNMP returned a None/missing thing during a reboot window."

## Marker (regression test)

`/usr/share/obn/lib/device/snmpdevice.py` must contain the substring `except KeyError:` followed by `return {}` within `_snmp_parse_results`. Our skill greps `grep -c "except KeyError:"` and requires `>= 1`.

## Suggested regression test shape

```python
def test_snmp_parse_results_handles_pysnmp_keyerror(mocker):
    def raising_gen():
        yield None  # one good item
        raise KeyError("errorIndication")
    result = _snmp_parse_results(raising_gen(), ...)
    assert result == {}  # graceful empty dict, not exception
```

## Existing implementation

`scripts/fix_obn.py` `fix_bug_3()` — straight diff above.

## Related

Bug 9 ([`bug-09-snmpdevice-pysnmp-thread-safety.md`](bug-09-snmpdevice-pysnmp-thread-safety.md)) also touches this file and the same iteration site. Bug 9 wraps `list(generator)` with a `threading.Lock`; the lock should sit *inside* the `try` block (around `gen_items = list(generator)` only) so the KeyError still gets caught. **If both bugs land, Bug 3 must be applied first** — Bug 9's diff context includes the `gen_items = list(generator)` line that Bug 3 introduces.
