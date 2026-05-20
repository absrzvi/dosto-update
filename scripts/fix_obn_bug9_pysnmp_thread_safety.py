#!/usr/bin/env python3
"""
OBN Bug 9 fix: pysnmp asyncore dispatcher is not thread-safe.

Problem
-------
SNMPEngineManager (lib/device/snmpdevice.py) is a singleton — one SnmpEngine
instance is shared across the ThreadPoolExecutor workers spawned by
cli/update.py process_batch(). pysnmp's asyncore dispatcher uses a single
global out-queue per engine; when multiple threads run SNMP get/set/walk
in parallel they race on `self.__outQueue.pop(0)` and crash with
`IndexError: pop from empty list` inside pysnmp/carrier/asyncore/dgram/base.py.

Observed on box1-t18 and box1-t16 during `sudo obn update c sw` on
2026-05-20 — both crashed mid-batch with the same call stack, killing
the parallel `obn update c sw` cycle partway through.

Fix
---
Serialise the dispatcher call. Add a module-level threading.Lock and wrap
the single `list(generator)` site in `_snmp_parse_results` with it.
SNMP request/response over the wire is still parallel-able (the lock is
released as soon as the generator drains) but only one thread runs the
asyncore reactor at a time. The lock has minimal contention because each
SNMP get/set completes in O(10-100 ms) while the rest of update_device
(TFTP, file IO, sleeps) is much longer.

This is idempotent: if the patch is already applied (marker line
present) it exits 0 with no changes.

Run inside the chroot (or directly on a writable rootfs) like the other
fix_obn*.py scripts.
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

    if MARKER in src:
        print("Bug 9 (pysnmp thread safety): ALREADY APPLIED")
        return 0

    # ------------------------------------------------------------------
    # Step 1 — add `import threading` next to the other stdlib imports,
    # and define the module-level lock just after the imports block.
    # ------------------------------------------------------------------
    if "import threading" not in src:
        src = re.sub(
            r"(\nimport logging\n)",
            r"\1import threading\n",
            src,
            count=1,
        )

    # Insert the lock after the last `from ... import ...` line near the top.
    # We anchor on the `from pysnmp.proto.rfc1902 import TimeTicks` line which
    # is the last import in the current snmpdevice.py.
    lock_block = (
        "\n"
        "# Bug 9 fix: pysnmp's asyncore transportDispatcher is not thread-safe.\n"
        "# OBN's process_batch runs SNMP calls from a ThreadPoolExecutor sharing\n"
        "# one SnmpEngine, and the dispatcher's out-queue races on pop(0). We\n"
        "# serialise the single `list(generator)` site in _snmp_parse_results\n"
        "# with this module-level lock. Released between SNMP calls.\n"
        f"{MARKER} = threading.Lock()\n"
    )

    anchor = "from pysnmp.proto.rfc1902 import TimeTicks"
    if anchor not in src:
        print(f"ERROR: anchor not found: {anchor!r}")
        return 2

    # Insert the lock block after the line that contains the anchor.
    src = src.replace(
        anchor + "\n",
        anchor + "\n" + lock_block,
        1,
    )

    # ------------------------------------------------------------------
    # Step 2 — wrap the `gen_items = list(generator)` call with the lock.
    # ------------------------------------------------------------------
    old = "        try:\n            gen_items = list(generator)\n"
    new = (
        "        try:\n"
        f"            with {MARKER}:\n"
        "                gen_items = list(generator)\n"
    )
    if old not in src:
        print(f"ERROR: anchor for list(generator) not found")
        return 3
    src = src.replace(old, new, 1)

    SNMPDEVICE.write_text(src)
    print("Bug 9 (pysnmp thread safety): PATCHED")
    print(f"  - added `import threading`")
    print(f"  - added module-level `{MARKER}`")
    print(f"  - wrapped `list(generator)` in _snmp_parse_results with the lock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
