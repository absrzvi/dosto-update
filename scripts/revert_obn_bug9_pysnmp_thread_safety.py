#!/usr/bin/env python3
"""
Revert OBN Bug 9 fix.

Removes:
  - `import threading` (only if not used elsewhere — checked)
  - module-level `_SNMP_DISPATCH_LOCK = threading.Lock()` block
  - `with _SNMP_DISPATCH_LOCK:` wrapper around `list(generator)`

The lock-based patch was found to hang `obn update c sw` indefinitely
on 2026-05-20 on box1-t18 and box1-t16 (10+ min wall-clock, no progress,
no SNMP traffic logged). Suspected interaction with pysnmp's asyncore
internal state machine — the dispatcher needs to be pumped between
threads in a specific way that the simple mutex doesn't provide.

Reverting to original behaviour. The real fix (per-thread SnmpEngine or
explicit serialisation of process_batch) will be filed with R&D.

Idempotent: if the marker is absent, exits 0 with no changes.
"""
from pathlib import Path
import re
import sys

SNMPDEVICE = Path("/usr/share/obn/lib/device/snmpdevice.py")
MARKER = "_SNMP_DISPATCH_LOCK"


def main() -> int:
    if not SNMPDEVICE.exists():
        print(f"ERROR: {SNMPDEVICE} not found")
        return 1

    src = SNMPDEVICE.read_text()
    original = src

    if MARKER not in src:
        print("Bug 9 revert: ALREADY REVERTED (marker absent)")
        return 0

    # Remove the with-lock wrapper, restoring the original `list(generator)` form.
    new_wrap = (
        "        try:\n"
        f"            with {MARKER}:\n"
        "                gen_items = list(generator)\n"
    )
    old_wrap = "        try:\n            gen_items = list(generator)\n"
    if new_wrap not in src:
        print(f"WARN: wrapped list(generator) not found — partial state?")
    else:
        src = src.replace(new_wrap, old_wrap, 1)

    # Remove the module-level lock block (between the marker comment lead-in and
    # the lock line). We anchor by the comment-line + lock-line; both go.
    src = re.sub(
        r"\n# Bug 9 fix: pysnmp's asyncore transportDispatcher is not thread-safe\.\n"
        r"# OBN's process_batch runs SNMP calls from a ThreadPoolExecutor sharing\n"
        r"# one SnmpEngine, and the dispatcher's out-queue races on pop\(0\)\. We\n"
        r"# serialise the single `list\(generator\)` site in _snmp_parse_results\n"
        r"# with this module-level lock\. Released between SNMP calls\.\n"
        r"_SNMP_DISPATCH_LOCK = threading\.Lock\(\)\n",
        "",
        src,
        count=1,
    )

    # Remove the `import threading` line (it was added solely for this patch).
    src = re.sub(r"\nimport threading\n", "\n", src, count=1)

    if MARKER in src:
        print("ERROR: marker still present after revert — bailing out, no write")
        return 4

    SNMPDEVICE.write_text(src)
    print("Bug 9 revert: REVERTED")
    print("  - removed `with _SNMP_DISPATCH_LOCK:` wrapper")
    print("  - removed module-level lock + comment")
    print("  - removed `import threading`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
