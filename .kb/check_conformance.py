#!/usr/bin/env python3
"""OKF conformance + link check for the .kb/ bundle.

Passes when every non-reserved .md has parseable YAML frontmatter with a non-empty `type`,
and every bundle-absolute link (/.kb/... or /train-ip-allocation-commission/...) resolves.
Run from the repo root: python .kb/check_conformance.py
"""
import glob, re, os, sys
try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

RESERVED = {"index.md", "log.md"}
LINK_RE = re.compile(r'\]\((/(?:\.kb|train-ip-allocation-commission)/[^)#]+\.md)')

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    problems, targets, types, concept = [], set(), {}, 0
    files = sorted(glob.glob(".kb/**/*.md", recursive=True))
    for f in files:
        txt = open(f, encoding="utf-8").read()
        for m in LINK_RE.finditer(txt):
            targets.add(m.group(1))
        if os.path.basename(f) in RESERVED:
            continue
        concept += 1
        m = re.match(r'^---\s*\n(.*?)\n---\s*\n', txt, re.S)
        if not m:
            problems.append(f"{f}: no frontmatter block"); continue
        try:
            d = yaml.safe_load(m.group(1))
        except Exception as e:
            problems.append(f"{f}: YAML error: {e}"); continue
        t = (d or {}).get("type")
        if not t:
            problems.append(f"{f}: missing/empty `type`")
        else:
            types[t] = types.get(t, 0) + 1
    broken = sorted(t for t in targets if not os.path.exists("." + t))

    print(f"docs: {len(files)}  concept: {concept}  types: {dict(sorted(types.items(), key=lambda x:-x[1]))}")
    print(f"conformance problems: {len(problems)}  broken links: {len(broken)}")
    for p in problems:
        print("  PROBLEM:", p)
    for b in broken:
        print("  BROKEN LINK:", b)
    if problems or broken:
        print("RESULT: FAIL")
        sys.exit(1)
    print("RESULT: PASS — OKF-conformant, all internal links resolve")

if __name__ == "__main__":
    main()
