#!/usr/bin/env python3
"""OKF conformance + link check for a KB bundle. Portable — run from the bundle root.

Passes when every non-reserved .md has parseable YAML frontmatter with a non-empty `type`,
and every bundle-absolute link (a markdown link whose target starts with `/`) resolves on disk
relative to the bundle root.

Usage:  python check_conformance.py            # checks the dir this script lives in
        python check_conformance.py <bundle>   # checks <bundle>
"""
import glob, re, os, sys
try:
    import yaml
except ImportError:
    sys.exit("pyyaml required: pip install pyyaml")

RESERVED = {"index.md", "log.md"}
# any markdown link whose href begins with "/" and ends ".md"
LINK_RE = re.compile(r'\]\((/[^)#]+\.md)')

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(root)
    problems, targets, types, concept = [], set(), {}, 0
    files = sorted(glob.glob(os.path.join(root, "**", "*.md"), recursive=True))
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
        if not (d or {}).get("type"):
            problems.append(f"{f}: missing/empty `type`")
        else:
            types[d["type"]] = types.get(d["type"], 0) + 1
    # bundle-absolute links resolve relative to the bundle root
    broken = sorted(t for t in targets if not os.path.exists(root + t))

    print(f"root: {root}")
    print(f"docs: {len(files)}  concept: {concept}  types: {dict(sorted(types.items(), key=lambda x:-x[1]))}")
    print(f"conformance problems: {len(problems)}  broken links: {len(broken)}")
    for p in problems:
        print("  PROBLEM:", p)
    for b in broken:
        print("  BROKEN LINK:", b)
    if problems or broken:
        print("RESULT: FAIL"); sys.exit(1)
    print("RESULT: PASS — OKF-conformant, all internal links resolve")

if __name__ == "__main__":
    main()
