#!/usr/bin/env python3
"""Add bidirectional evidence <-> fleet 'Observed on' relationships to the KB.

The graph was hub-and-spoke: evidence docs name the trains they were proven on, but never
link the fleet records (and vice-versa). This adds the real semantic edge "this finding was
observed on that train" in BOTH directions.

Deliberate, not spammy:
- Only links a train if it appears in the evidence doc's BODY (not just frontmatter resource path).
- Only links trains that have a fleet record on disk.
- Writes into a marker-fenced '## Observed on' (evidence) / '## Findings observed here' (fleet)
  block so it's idempotent + reversible.
- Updates the OKF markdown links (canonical); the Obsidian shadow generator run afterwards
  mirrors them into wikilinks.
"""
import glob, re, os
from collections import defaultdict

EV_MARK = "<!-- EVIDENCE-FLEET-LINKS (auto; scripts/link_evidence_to_fleet.py) -->"
TRAIN_RE = re.compile(r'\b(47(?:34|36|05|06)-\d{3})\b')

def fleet_record_for(train):
    """Return the fleet doc path for a train#, honoring the coupling/misimage special records."""
    direct = f".kb/fleet/{train}.md"
    if os.path.exists(direct):
        return direct
    # 4736-112 is documented as box1-t40-fzg140
    if train == "4736-112" and os.path.exists(".kb/fleet/box1-t40-fzg140.md"):
        return ".kb/fleet/box1-t40-fzg140.md"
    return None

def strip_block(txt, mark):
    return txt.split("\n" + mark)[0].rstrip()

def body_of(txt):
    m = re.match(r'^---\s*\n.*?\n---\s*\n', txt, re.S)
    return txt[m.end():] if m else txt

# 1. discover evidence -> trains (from body only), and reciprocal fleet -> evidence
ev_to_fleet = {}
fleet_to_ev = defaultdict(list)
for ev in sorted(glob.glob(".kb/evidence/*.md")):
    if os.path.basename(ev) == "index.md":
        continue
    txt = open(ev, encoding="utf-8").read()
    body = body_of(strip_block(txt, EV_MARK))
    trains = []
    for t in dict.fromkeys(TRAIN_RE.findall(body)):   # ordered-unique
        rec = fleet_record_for(t)
        if rec and rec not in [r for _, r in trains]:
            trains.append((t, rec))
    if trains:
        ev_to_fleet[ev] = trains
        for t, rec in trains:
            fleet_to_ev[rec].append((os.path.basename(ev)[:-3], ev))

# 2. write evidence-side blocks
def rel_link(target_path):
    # markdown bundle-absolute + display = basename
    disp = os.path.basename(target_path)[:-3]
    return f"[{disp}](/{target_path.replace(os.sep,'/')})"

ev_changed = 0
for ev, trains in ev_to_fleet.items():
    txt = open(ev, encoding="utf-8").read()
    base = strip_block(txt, EV_MARK)
    block = ["", EV_MARK, "## Observed on", "",
             "Trains where this was captured / proven (see each record for identity + live state):", ""]
    block += [f"- {rel_link(rec)}" for _, rec in trains]
    new = base + "\n" + "\n".join(block) + "\n"
    if new != txt:
        open(ev, "w", encoding="utf-8").write(new); ev_changed += 1

# 3. write fleet-side reciprocal blocks
FL_MARK = "<!-- FLEET-EVIDENCE-LINKS (auto; scripts/link_evidence_to_fleet.py) -->"
fl_changed = 0
for rec, evs in fleet_to_ev.items():
    txt = open(rec, encoding="utf-8").read()
    base = strip_block(txt, FL_MARK)
    seen = set(); uniq = []
    for name, path in evs:
        if path not in seen:
            seen.add(path); uniq.append((name, path))
    block = ["", FL_MARK, "## Findings observed here", "",
             "KB evidence docs whose captures reference this train:", ""]
    block += [f"- {rel_link(path)}" for _, path in uniq]
    new = base + "\n" + "\n".join(block) + "\n"
    if new != txt:
        open(rec, "w", encoding="utf-8").write(new); fl_changed += 1

print(f"evidence docs linked to fleet: {ev_changed}")
print(f"fleet records linked back to evidence: {fl_changed}")
for ev, trains in ev_to_fleet.items():
    print(f"  {os.path.basename(ev)} -> {', '.join(t for t,_ in trains)}")
