#!/usr/bin/env python3
"""
Fix fv5 rules.yaml template off-by-one coach shift (box1-t42 / Fzg 42, 2026-07-07).

nd-obn-template-dostoneu-fv5 0.0.18 ships templates named by the real
A-C-E-F-B topology (fv5-400-E*, fv5-500-F*, fv5-600-B*), but /etc/obn/rules.yaml
still references the OLD names shifted one coach up:
  coach3 (E) -> fv5-300-D*  (do not exist -> obn update c crashes)
  coach4 (F) -> fv5-400-E*  (E's templates -> would push E cfg to F coach)
  coach5 (B) -> fv5-500-F*  (F's templates -> would push F cfg to B coach)
  fv5-600-B* never referenced.

The `config:` names in rules.yaml are already correct; only `template:` refs
are wrong. This corrects all 9. Each anchor must match exactly once.

Idempotent-ish: aborts loudly if any anchor count != 1 (so re-running after a
successful patch is a safe no-op-with-error, not a double-apply).
"""
from pathlib import Path
import sys

TARGET = Path("/etc/obn/rules.yaml")

REPLS = [
    ('template: "fv5-300-D1.cfg"', 'template: "fv5-400-E1.cfg"'),
    ('template: "fv5-300-D2.cfg"', 'template: "fv5-400-E2.cfg"'),
    ('template: "fv5-300-D3.cfg"', 'template: "fv5-400-E3.cfg"'),
    ('config: "fv5-F1-v8"\n      template: "fv5-400-E1.cfg"',
     'config: "fv5-F1-v8"\n      template: "fv5-500-F1.cfg"'),
    ('config: "fv5-F2-v8"\n      template: "fv5-400-E2.cfg"',
     'config: "fv5-F2-v8"\n      template: "fv5-500-F2.cfg"'),
    ('config: "fv5-F3-v8"\n      template: "fv5-400-E3.cfg"',
     'config: "fv5-F3-v8"\n      template: "fv5-500-F3.cfg"'),
    ('config: "fv5-B1-v8"\n      template: "fv5-500-F1.cfg"',
     'config: "fv5-B1-v8"\n      template: "fv5-600-B1.cfg"'),
    ('config: "fv5-B2-v8"\n      template: "fv5-500-F2.cfg"',
     'config: "fv5-B2-v8"\n      template: "fv5-600-B2.cfg"'),
    ('config: "fv5-B3-v8"\n      template: "fv5-500-F3.cfg"',
     'config: "fv5-B3-v8"\n      template: "fv5-600-B3.cfg"'),
]


def main():
    if not TARGET.exists():
        sys.exit(f"ERROR: {TARGET} not found")
    c = TARGET.read_text()
    for old, new in REPLS:
        n = c.count(old)
        if n != 1:
            sys.exit(f"ABORT: anchor matched {n}x (expected 1) — no change written: {old!r}")
        c = c.replace(old, new)
    TARGET.write_text(c)
    print("rules.yaml patched: 9 template refs corrected (coach3->E, coach4->F, coach5->B)")


if __name__ == "__main__":
    main()
