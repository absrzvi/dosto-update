#!/bin/bash
# check-poe.sh — Zabbix UserParameter helper. Reads the poe_poll cache (instant; no switch SSH)
# and emits a rolled-up status distinguishing PoE-failure from plain link-down.
#
#   check-poe.sh count_poe_fail  -> # of ports that are a PoE FAILURE (poe off/fault AND link down)
#   check-poe.sh count_link_down -> # of ports that are LINK-DOWN with PoE fine (poe on AND link down)
#   check-poe.sh worst           -> 0 OK / 1 link-down-only / 2 PoE-failure present (for a single alarm item)
#
# A "PoE failure" = a port that was powering a device (poe on) whose PoE went off/fault while the
# link is down — the powered device lost power. A "link down" with poe still on = cable/peer issue.
# We only flag ports whose PoE is a REAL state (on/off/fault), i.e. PoE-capable ports.
#
# Stale guard: if the cache is older than 15 min (poller stuck / switches unreachable), return 0
# for the alarm rollup (don't assert PoE faults on stale data) but the counts still reflect cache.
set -u
JSON=/data/poe-monitor/poe_status.json
mode="${1:-worst}"
[ -f "$JSON" ] || { echo 0; exit 0; }

python3 - "$JSON" "$mode" <<'PY'
import json,sys,datetime
j=json.load(open(sys.argv[1])); mode=sys.argv[2]
poe_fail=0; link_down=0; newest=None
for sw,d in j.items():
    iso=d.get("iso");
    if iso:
        try:
            t=datetime.datetime.strptime(iso.replace("Z",""),"%Y-%m-%dT%H:%M:%S")
            newest=t if (newest is None or t>newest) else newest
        except: pass
    for port,st in d.get("ports",{}).items():
        poe=st.get("poe","?"); link=st.get("link","?"); flag=st.get("flag","")
        # PoE-failure = a port that WAS powering a device and lost it: the poller sets flag
        # 'poe_lost' on an on->off transition. An always-off/empty port never transitions, so no
        # false alarm. (Behaviourally-sound signal that needs no external expected-PoE map.)
        #
        # NOTE: the switch also reports an error-ish poe status "E(1e)" on some ports (link up,
        # power 0) — seen systemically on ~e1-9 across several healthy switches, so its meaning is
        # UNKNOWN/possibly-benign. It is CAPTURED in the cache (poe field) for study but deliberately
        # does NOT raise an alarm until confirmed a real fault (avoid false alarms on healthy trains).
        if flag=="poe_lost":
            poe_fail+=1
        elif link=="down" and poe=="on":
            link_down+=1           # PoE still supplying but no link = cable/peer (link fault)
        # empty ports (poe off), E(1e) unknowns, and healthy ports = ignored for the alarm
# stale guard for the rollup only
stale=False
if newest is not None:
    age=(datetime.datetime.utcnow()-newest).total_seconds()
    if age>900: stale=True
if mode=="count_poe_fail": print(poe_fail)
elif mode=="count_link_down": print(link_down)
else:  # worst
    if stale: print(0)
    elif poe_fail>0: print(2)
    elif link_down>0: print(1)
    else: print(0)
PY
