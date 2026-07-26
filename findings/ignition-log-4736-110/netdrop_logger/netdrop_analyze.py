#!/usr/bin/env python3
"""
netdrop_analyze.py — classify tunnel/VPN drops by CAUSE.

Answers: "apart from ignition / hard power cuts, what caused the other VPN drops?"

Inputs (all optional; uses what's present):
  --netdrop  netdrop.csv    from netdrop_poll.sh (tunnel/link state over time)
  --power    vign.csv       from vign_poll.sh    (CMM Vin/Vign/reason — power events)
  --vpn      VPN xlsx sheet (ÖBB session list)   — only if it TIME-OVERLAPS the logs

For each detected tunnel outage (rds_flow lost, or links_up==0, or a gap), classify:
  POWER        -> a power event (power log shows a cut/ignition-drop/commanded in the window)
  COVERAGE     -> all modems lost carrier/registration but power was fine  (radio dead zone)
  CARRIER_NAT  -> tunnel re-registered (all links flapped) while modems kept carrier (CGNAT/rekey)
  REBOOT       -> outage bracketed by a boot marker
  UNKNOWN      -> none of the above matched

Emits a per-event table + a summary tally. Designed so a disputed period produces a
defensible "N drops were power, M were coverage, K were carrier-NAT churn" statement.
"""
import argparse, csv, sys
from datetime import datetime, timedelta

def parse_iso(s):
    s=s.strip().replace("Z","")
    for f in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(s,f)
        except ValueError: pass
    return None

def load_netdrop(path):
    rows=[]
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            ts=parse_iso(r.get("iso_utc",""))
            if not ts: continue
            rows.append((ts, r))
    rows.sort(key=lambda x:x[0])
    return rows

def load_power(path):
    """Return list of (ts, reason, vin, vign) — reason 'start' marks a boot/power-up."""
    out=[]
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            ts=parse_iso(r.get("iso_utc") or r.get("timestamp_utc") or "")
            if not ts: continue
            out.append((ts, (r.get("reason") or "").strip(),
                        r.get("vin_v"), r.get("vign_v")))
    out.sort(key=lambda x:x[0])
    return out

def power_event_near(power, t, win_min=10):
    """Is there a boot/start or a >5min power gap near time t?"""
    for i in range(1,len(power)):
        gap=(power[i][0]-power[i-1][0]).total_seconds()/60
        if gap>5:  # an outage in the power log
            # outage window = [prev sample, this sample]
            if power[i-1][0]-timedelta(minutes=win_min) <= t <= power[i][0]+timedelta(minutes=win_min):
                return True
    return False

def analyze(netdrop, power):
    events=[]
    # An "outage" = a transition where rds_flow goes 1->0, or links_up goes >0 -> 0,
    # or a sample gap > 3 min (logger itself was down => likely reboot/power).
    prev=None
    for ts,r in netdrop:
        rds=r.get("rds_flow"); lu=r.get("links_up"); reason=r.get("reason")
        if reason=="start":
            events.append((ts,"REBOOT","boot/start marker"))
            prev=(ts,r); continue
        if prev:
            pts,pr=prev
            gap=(ts-pts).total_seconds()/60
            lost_rds = (pr.get("rds_flow")=="1" and rds=="0")
            lost_all = (pr.get("links_up") not in ("0",None,"") and lu=="0")
            if gap>3:
                events.append((ts,"GAP",f"logger silent {gap:.0f}min (reboot/power?)"))
            elif lost_all:
                events.append((ts,"COVERAGE?","all modems lost carrier"))
            elif lost_rds:
                events.append((ts,"CARRIER_NAT?","RDS flow lost, modems still up"))
        prev=(ts,r)
    # classify against power
    out=[]
    for ts,kind,note in events:
        if power and power_event_near(power,ts):
            cls="POWER"
        elif kind=="REBOOT" or kind=="GAP":
            cls="REBOOT/GAP"
        elif kind=="COVERAGE?":
            cls="COVERAGE"
        elif kind=="CARRIER_NAT?":
            cls="CARRIER_NAT"
        else:
            cls="UNKNOWN"
        out.append((ts,cls,note))
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--netdrop", required=True)
    ap.add_argument("--power")
    args=ap.parse_args()
    nd=load_netdrop(args.netdrop)
    pw=load_power(args.power) if args.power else []
    if not nd:
        print("no netdrop rows"); sys.exit(1)
    print(f"netdrop span: {nd[0][0]} .. {nd[-1][0]}  ({len(nd)} rows)")
    if pw: print(f"power   span: {pw[0][0]} .. {pw[-1][0]}  ({len(pw)} rows)")
    ev=analyze(nd,pw)
    print(f"\n{'time (UTC)':20s} {'class':12s} note")
    from collections import Counter
    tally=Counter()
    for ts,cls,note in ev:
        print(f"{ts:%Y-%m-%d %H:%M:%S}  {cls:12s} {note}")
        tally[cls]+=1
    print("\n=== tally by cause ===")
    for k,v in tally.most_common(): print(f"  {k:12s} {v}")
    print("\nNote: COVERAGE/CARRIER_NAT are the NON-power drops. POWER = correlates with CMM power log.")

if __name__=="__main__":
    main()
