#!/usr/bin/env python3
"""
Fix OBN Bug 10: `obn report` infinite loop in number_coaches BFS on DOSTO NEU.

Symptom: `obn report` runs at 100% CPU forever, leaks memory (27 GB+ RSS).
Trigger: Devices in the discovery graph (especially APs and edge-of-consist
switches) get enqueued via line 282's unconditional `queue.appendleft(to_device)`
even when no conditional branch assigned them a coach_number. They're then
popped, their neighbours re-walked, and re-enqueued — forever.

Fix: Only enqueue to_device if a coach_number was assigned to it during this
iteration. The early-iteration guard at line 47-48 already skips devices
whose coach_number is already set, so this prevents the unbounded re-enqueue.

File:   /usr/share/obn/lib/report/report_dosto_neu.py
First seen: Fzg 130 box1-t47 2026-05-12 (memory: project_obn_update_target_catch22)
Recurred: Fzg 8 box1-t29 2026-05-22 (this fix)

Idempotent — safe to run twice.
"""
from pathlib import Path
import sys

TARGET = Path("/usr/share/obn/lib/report/report_dosto_neu.py")
MARKER = "# NDP-PATCH-BUG10-BFS-GUARD"

OLD = """                    # nv6 - END

                # Add to_device to queue
                queue.appendleft(to_device)
                continue
"""

NEW = f"""                    # nv6 - END

                # Add to_device to queue {MARKER}
                # Bug 10 fix: only enqueue if coach_number was assigned in
                # one of the branches above. Without this, APs and edge
                # switches whose conditions didn't match get re-enqueued
                # forever, hanging obn report at 100% CPU.
                if to_device.coach_number is not None:
                    queue.appendleft(to_device)
                continue
"""

def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found")
        sys.exit(1)
    content = TARGET.read_text()
    if MARKER in content:
        print(f"Bug 10 (report_dosto_neu BFS guard): ALREADY APPLIED")
        return
    if OLD not in content:
        print(f"ERROR: expected pattern not found in {TARGET}")
        print("Likely the file has been modified upstream; review manually before patching.")
        sys.exit(2)
    new_content = content.replace(OLD, NEW)
    TARGET.write_text(new_content)
    print(f"Bug 10 (report_dosto_neu BFS guard): PATCHED")

if __name__ == "__main__":
    main()
