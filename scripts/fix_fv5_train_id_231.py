#!/usr/bin/env python3
"""
Force fv5 template hostnames to render Fzg 231 (box1-t41 / 4705-103, 2026-07-07).

Fzg 229 > 127, so the box-id=Fzg strategy cannot carry it (train_id is the 3rd
IP octet, capped 0-127). This box runs backbone train_id=42 (fits the octet,
matches the .42.x subnet) and MUST keep it there — backbone-discovery.yaml is
NOT touched. Instead we hardcode the Fzg into the templates (the ONLY place a
Fzg/train_id override is allowed to live, per feedback_train_id_location), so
hostnames render fv5-*-v8-229 while the box-id stays 42.

Templates are Form-2 (line 1 is a `{# box-id ... #}` comment, no set directive)
with CRLF line endings. We replace line 1 with a Form-1 set directive, preserving
CRLF and every other byte.

Scope: /etc/obn/template/fv5-*.cfg ONLY. 15 files expected.
Aborts loudly if line 1 isn't the expected box-id comment (no double-apply).
"""
import glob
import sys

FZG = 231
OLD_LINE1 = "{# box-id = Fzg: train_id IS the Fzg, no 128+ remap #}"
NEW_LINE1 = "{%- set train_id = " + str(FZG) + " -%}"
EXPECTED = 15

paths = sorted(glob.glob("/etc/obn/template/fv5-*.cfg"))
if len(paths) != EXPECTED:
    sys.exit(f"ABORT: expected {EXPECTED} fv5 templates, found {len(paths)}")

# First pass: validate every file before writing any.
for p in paths:
    with open(p, "rb") as f:
        raw = f.read()
    # Detect line ending of the first line.
    first, sep, _ = raw.partition(b"\n")
    line1 = first.rstrip(b"\r").decode("utf-8", "replace")
    if line1 == NEW_LINE1:
        sys.exit(f"ABORT: {p} already has the set directive on line 1 (no double-apply)")
    if line1 != OLD_LINE1:
        sys.exit(f"ABORT: {p} line 1 is not the expected box-id comment:\n  {line1!r}")

# Second pass: write. Preserve CRLF (files use \r\n).
changed = 0
for p in paths:
    with open(p, "rb") as f:
        raw = f.read()
    first, sep, rest = raw.partition(b"\n")
    crlf = first.endswith(b"\r")
    newfirst = NEW_LINE1.encode("utf-8") + (b"\r" if crlf else b"")
    out = newfirst + b"\n" + rest
    with open(p, "wb") as f:
        f.write(out)
    changed += 1

print(f"PATCHED {changed} fv5 templates: line 1 -> {NEW_LINE1!r} (Fzg {FZG}); backbone train_id untouched")
