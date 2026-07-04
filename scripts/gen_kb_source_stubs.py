#!/usr/bin/env python3
"""Generate categorised KB 'source' stub nodes for every raw project file.

Each raw .md (findings, reports, emails, plans, handoffs, ...) gets a small OKF node under
.kb/sources/<category>/ that:
  - carries a `type: source-<category>` + `resource:` link to the raw file (never moves it),
  - auto-links to related KB knowledge by matching train#s and subsystem keywords in the raw text.

This makes the raw corpus a categorised, linked layer of the graph without touching any path
(zero breakage — scripts/CLAUDE still reference the raw files where they are).

Idempotent: regenerates the whole .kb/sources/ tree each run.
"""
import glob, os, re, shutil
from collections import defaultdict

OUT = ".kb/sources"
TRAIN_RE = re.compile(r'\b(47(?:34|36|05|06)-\d{3})\b')

SKIP = {"CLAUDE.md","fleet-status.md","fleet-journal.md","troubleshooting-runbook.md",
        "train-login-checklist.md","BOOTSTRAP_DOSTO_v1.md","PROJECT-STATUS.md",
        "cable-issues-register.md","iperf3-troubleshooting.md","MEMORY.md"}

# subsystem keyword -> KB target doc (for auto-linking)
KW = [
    (r'\brstp|topology change|tc storm|coupl|traction\b', "/.kb/topics/coupled-rstp-tc-storm.md"),
    (r'\bvlan7|firewall|stadler fw\b',                    "/.kb/topics/vlan7-addressing.md"),
    (r'\bzabbix|nms|snmp|proxy\b',                        "/.kb/topics/zabbix-nms-model.md"),
    (r'\bfzg.?id|train_id|box.?id|misimage|namespace\b',  "/.kb/topics/fzg-id-two-namespaces.md"),
    (r'\bobn|discover|report bug|numbering|bfs\b',        "/.kb/components/nomad-connect-obn/index.md"),
    (r'\bswitch|vds|cli|firmware|kmdev\b',                "/.kb/components/vds-consist-switch/cli-and-management.md"),
    (r'\bap\b|westermo|luci|access point',               "/.kb/components/westermo-ap/factory-vs-nomad-config.md"),
    (r'\bl2 health|health check|counters\b',             "/.kb/topics/l2-health-methodology.md"),
    (r'\bfv5|fv6|4705|4706|cat\b',                        "/.kb/topics/fv5-topology.md"),
]

def categorize(f, b):
    up = b.upper()
    if "email" in b.lower() or up.startswith(("EMAIL","OBB_EMAIL")): return "email"
    if up.startswith(("RCA","RD_","RDTICKET","TRIAG","AUDIT")):      return "rca"
    if up.startswith(("PLAN","PROPOSAL","TASKLIST","SPEC")):         return "plan"
    if up.startswith(("RUNBOOK","RECIPE","DRIVE")):                  return "runbook"
    if "handoff" in b.lower():                                       return "handoff"
    if "reports/" in f:                                              return "report"
    if up.startswith(("REPORT","STATUS")):                          return "report"
    return "finding"

def fleet_target(train):
    p = f".kb/fleet/{train}.md"
    if os.path.exists(p): return "/" + p
    if train == "4736-112" and os.path.exists(".kb/fleet/box1-t40-fzg140.md"):
        return "/.kb/fleet/box1-t40-fzg140.md"
    return None

def slug(b):
    return re.sub(r'[^a-z0-9]+','-', b[:-3].lower()).strip('-')

def collect():
    files = []
    for pat in ["findings/**/*.md","reports/**/*.md","OEBB-251/**/*.md","rd-handoff/*.md",
                "handoff*.md","sdd-design-freeze-tasklist.md","SYSOPS_TICKET*.md"]:
        files += glob.glob(pat, recursive=True)
    out = []
    for f in sorted(set(x.replace("\\","/") for x in files)):
        b = os.path.basename(f)
        if b in SKIP: continue
        out.append(f)
    return out

def first_heading_or_name(path, b):
    try:
        for ln in open(path, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if ln.startswith("# "): return ln[2:].strip()
    except Exception: pass
    return b[:-3].replace("_"," ")

def main():
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    files = collect()
    by_cat = defaultdict(list)
    for f in files:
        b = os.path.basename(f)
        cat = categorize(f, b)
        os.makedirs(f"{OUT}/{cat}", exist_ok=True)
        try: raw = open(f, encoding="utf-8", errors="replace").read()
        except Exception: raw = ""
        low = raw.lower()
        trains = [t for t in dict.fromkeys(TRAIN_RE.findall(raw)) if fleet_target(t)]
        kw_targets = [tgt for pat,tgt in KW if re.search(pat, low)]
        kw_targets = list(dict.fromkeys(kw_targets))[:3]  # cap noise
        title = first_heading_or_name(f, b).replace('"', "'").replace(":", " -")
        s = slug(b)
        stub = f"{OUT}/{cat}/{s}.md"
        L = ["---", f"type: source-{cat}",
             f'title: "{title[:90]}"',
             f'description: "{cat.title()} source — {b}"',
             "project: dosto-neu",
             f"resource: /{f}",
             f"tags: [source, {cat}] ",
             "timestamp: 2026-07-04T00:00:00Z", "---", "",
             f"# {title}", "",
             f"**{cat.title()}** source document. Raw file: [`{b}`](/{f}).", ""]
        if trains:
            L += ["## Trains", ""] + [f"- [{t}](/.kb/fleet/{t}.md)" if fleet_target(t)==f'/.kb/fleet/{t}.md'
                                      else f"- [{t}]({fleet_target(t)})" for t in trains] + [""]
        if kw_targets:
            L += ["## Related knowledge", ""] + [f"- [{os.path.basename(t)[:-3]}]({t})" for t in kw_targets] + [""]
        L += [f"- [{cat.title()} index](/.kb/sources/{cat}/index.md)", ""]
        open(stub,"w",encoding="utf-8").write("\n".join(L))
        by_cat[cat].append((title, s, b))

    # per-category index + top sources index
    for cat, items in by_cat.items():
        idx = [f"# {cat.title()} sources", "",
               f"Categorised links to the {len(items)} raw `{cat}` documents (the raw files stay in place).",""]
        for title, s, b in sorted(items):
            idx.append(f"* [{title[:70]}]({s}.md) - `{b}`")
        open(f"{OUT}/{cat}/index.md","w",encoding="utf-8").write("\n".join(idx)+"\n")

    top = ["---","type: index","title: Sources — raw project documents by category",
           "description: Categorised, linked nodes for every raw finding/report/email/plan/handoff — the raw corpus as a navigable graph layer.",
           "project: dosto-neu","timestamp: 2026-07-04T00:00:00Z","---","",
           "# Sources — raw project documents","",
           "Every raw project document, categorised and linked to the trains + knowledge it concerns. "
           "The raw files are **not moved** — each node links to its `resource:`.",""]
    for cat in sorted(by_cat):
        top.append(f"* [{cat.title()} ({len(by_cat[cat])})]({cat}/index.md)")
    open(f"{OUT}/index.md","w",encoding="utf-8").write("\n".join(top)+"\n")

    print(f"generated {sum(len(v) for v in by_cat.values())} source stubs in {len(by_cat)} categories:")
    for cat in sorted(by_cat): print(f"  {cat}: {len(by_cat[cat])}")

if __name__ == "__main__":
    main()
