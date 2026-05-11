#!/usr/bin/env python3
"""
One-shot helper: append the three auto-scanner columns to every row of the
fleet-status.md fleet tables (header, divider, data rows).

New columns: Last reachable, Last auto-scan, Auto-detected issues.
All initialised to '—'.

Skips rows that already have 17 columns (idempotent — safe to re-run).
"""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FLEET_STATUS = REPO_ROOT / "fleet-status.md"

NEW_COLS = ["Last reachable", "Last auto-scan", "Auto-detected issues"]
OLD_COL_COUNT = 14
NEW_COL_COUNT = OLD_COL_COUNT + len(NEW_COLS)


def is_table_row(line: str) -> bool:
    return line.strip().startswith("|") and line.strip().endswith("|")


def cell_count(line: str) -> int:
    inner = line.strip().strip("|")
    return len([c for c in inner.split("|")])


def extend_header(line: str) -> str:
    return line.rstrip().rstrip("|").rstrip() + " | " + " | ".join(NEW_COLS) + " |"


def extend_divider(line: str) -> str:
    return line.rstrip().rstrip("|").rstrip() + " | " + " | ".join(["---"] * len(NEW_COLS)) + " |"


def extend_data(line: str) -> str:
    return line.rstrip().rstrip("|").rstrip() + " | " + " | ".join(["—"] * len(NEW_COLS)) + " |"


def main():
    content = FLEET_STATUS.read_text(encoding="utf-8")
    lines = content.split("\n")
    out = []

    in_table = False
    rows_extended = 0
    rows_skipped = 0

    for i, line in enumerate(lines):
        if is_table_row(line):
            count = cell_count(line)
            stripped = line.strip().strip("|").strip()

            if count == NEW_COL_COUNT:
                rows_skipped += 1
                out.append(line)
                continue

            if count != OLD_COL_COUNT:
                # Unrelated table or partial — leave alone
                out.append(line)
                continue

            # Header row?
            if stripped.startswith("Fzg "):
                out.append(extend_header(line))
                rows_extended += 1
                in_table = True
                continue

            # Divider row?
            if all(c.strip("- ") == "" for c in stripped.split("|")):
                out.append(extend_divider(line))
                rows_extended += 1
                continue

            # Data row in active table
            if in_table:
                out.append(extend_data(line))
                rows_extended += 1
                continue

            out.append(line)
        else:
            if line.strip() == "" and in_table:
                in_table = False  # blank line ends the table
            out.append(line)

    new_content = "\n".join(out)
    if new_content == content:
        print(f"no changes — already has {NEW_COL_COUNT}-column tables")
        return 0

    tmp = FLEET_STATUS.with_suffix(".md.tmp")
    tmp.write_text(new_content, encoding="utf-8")
    tmp.replace(FLEET_STATUS)
    print(f"extended {rows_extended} rows; skipped {rows_skipped} already-extended rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
