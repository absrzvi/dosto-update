#!/usr/bin/env python3
"""
Fix OBN Bug 10 (nd-obn 2.3.6 variant): `obn report` infinite loop in
number_coaches BFS on DOSTO NEU / fv5.

Same bug as scripts/fix_obn_bug10_report_dosto_neu_bfs.py, but that script's
OLD anchor (`# nv6 - END` comment block) does not exist in the restructured
2.3.6 report_dosto_neu.py (162 lines, fv5/fv6 coach maps inline). This variant
matches the 2.3.6 structure.

Symptom: `obn report` at 100% CPU forever, RSS leak to 27 GB+ (OOM).
Cause:   line ~158 unconditionally `queue.appendleft(to_device)` even when no
         branch assigned to_device a coach_number. Unnumberable edge switches /
         APs on unexpected ports cycle forever (the top-of-loop guard at
         `to_device.coach_number is not None` only skips ALREADY-numbered ones).
Fix:     only re-enqueue if a coach_number was assigned this pass.

File:   /usr/share/obn/lib/report/report_dosto_neu.py
Seen on: box1-t42 (Fzg 42, fv5), nd-obn 2.3.6, 2026-07-07.
Idempotent — safe to run twice.
"""
from pathlib import Path
import sys

TARGET = Path("/usr/share/obn/lib/report/report_dosto_neu.py")
MARKER = "# NDP-PATCH-BUG10-BFS-GUARD"

OLD = """                # Add to_device to queue
                queue.appendleft(to_device)
                continue
"""

NEW = f"""                # Add to_device to queue {MARKER}
                # Bug 10 fix: only enqueue if a branch above assigned a
                # coach_number. Without this, edge switches / APs on
                # unexpected ports get re-enqueued forever, hanging obn
                # report at 100% CPU with unbounded RSS growth.
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
        print("Bug 10 (report_dosto_neu BFS guard, 2.3.6): ALREADY APPLIED")
        return
    count = content.count("queue.appendleft(to_device)")
    if OLD not in content:
        print(f"ERROR: expected pattern not found in {TARGET}")
        print(f"  ('queue.appendleft(to_device)' appears {count}x — structure changed; review manually)")
        sys.exit(2)
    if content.count(OLD) != 1:
        print(f"ERROR: OLD anchor matched {content.count(OLD)}x, expected exactly 1 — aborting to avoid double-patch")
        sys.exit(3)
    TARGET.write_text(content.replace(OLD, NEW))
    print("Bug 10 (report_dosto_neu BFS guard, 2.3.6): PATCHED")


if __name__ == "__main__":
    main()
