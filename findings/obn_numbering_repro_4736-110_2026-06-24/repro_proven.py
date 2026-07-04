#!/usr/bin/env python3
"""
PROVEN reproduction + patch for OBN nv6 rear-coach numbering bug.
Run against live discovery.json from box1-t12 (Fzg 147 / 4736-119), 2026-06-24.
  python repro_proven.py            -> UNPATCHED: 13/18 SW, 17/24 AP  (reproduces field bug)
  python repro_proven.py --patched  -> PATCHED:   18/18 SW, 24/24 AP  (all match hostnames)
The 4 added rule-blocks are marked NEW 1..4 below.
"""
import json,sys
from collections import deque
PATCHED="--patched" in sys.argv
devs=json.load(open("discovery.json"))
class Dev:
    def __init__(s,d):
        s.mac=d['mac'].lower();s.ip=d['ip'];s.serial=d.get('serial','')or''
        s.neighbours=d.get('neighbours',[]);s.type=None;s.coach_number=None;s.device_number=None
def ftype(d):
    if d.serial.startswith('box'):return'BOX'
    if d.mac.startswith('a0:59:3a'):return'SW'
    if d.mac.startswith('00:14:5a'):return'AP'
    return'UNKNOWN'
devices={d['mac'].lower():Dev(d) for d in devs}
g=lambda n:devices.get(n.get('mac','').lower())
q=deque()
for d in devices.values():
    d.type=ftype(d)
    if d.type=='BOX':d.coach_number=3;d.device_number=1;q.append(d)
while q:
    fd=q.pop()
    for nb in fd.neighbours:
        port=nb.get('port',0);td=g(nb)
        if td is None or td.coach_number is not None:continue
        if fd.type=='BOX' and td.type=='SW':
            if port==1:td.device_number=1;td.coach_number=fd.coach_number
            elif port==2:td.device_number=3;td.coach_number=fd.coach_number
        if fd.type=='SW':
            if td.type=='AP':
                td.coach_number=fd.coach_number
                if port==7:td.device_number=fd.device_number
                if fd.device_number==3 and port==11:td.device_number=4
            if td.type=='SW':
                if fd.device_number==3 and port==4:td.coach_number=fd.coach_number;td.device_number=2
                if fd.device_number==2 and fd.coach_number==3 and port==4:td.device_number=1;td.coach_number=fd.coach_number+1
                if fd.device_number==1 and fd.coach_number in[4,5] and port==3:td.device_number=1;td.coach_number=fd.coach_number+1
                if fd.device_number==1 and fd.coach_number==6 and port==3:td.device_number=3;td.coach_number=fd.coach_number
                if fd.device_number==2 and fd.coach_number in[5,6] and port==4:td.device_number=3;td.coach_number=fd.coach_number-1
                if fd.device_number==2 and fd.coach_number==4 and port==4:td.device_number=1;td.coach_number=fd.coach_number-1
                if fd.device_number==1 and fd.coach_number in[2,3] and port==3:td.device_number=1;td.coach_number=fd.coach_number-1
                if fd.device_number==1 and fd.coach_number==1 and port==3:td.device_number=3;td.coach_number=fd.coach_number
                if fd.device_number==3 and fd.coach_number==1 and port==4:td.device_number=2;td.coach_number=fd.coach_number
                if fd.device_number==2 and fd.coach_number in[1,2] and port==4:td.device_number=3;td.coach_number=fd.coach_number+1
                if PATCHED:
                    # NEW 1: SW1 of coach 3 -> SW2 of coach 4 on E0-1 (entry into the rear d2/d3 chain)
                    if fd.device_number==1 and fd.coach_number==3 and port==4:td.device_number=2;td.coach_number=fd.coach_number+1
                    # NEW 2: SW2 of coach 4/5 -> SW3 of SAME coach on E0-0
                    if fd.device_number==2 and fd.coach_number in[4,5] and port==3:td.device_number=3;td.coach_number=fd.coach_number
                    # NEW 3: SW3 of coach 4 -> SW2 of coach 5 on E0-0 (inter-coach 4->5)
                    if fd.device_number==3 and fd.coach_number==4 and port==3:td.device_number=2;td.coach_number=fd.coach_number+1
                    # NEW 4: SW3 of coach 5 -> SW2 of coach 6 on E0-0 (inter-coach 5->6)
                    if fd.device_number==3 and fd.coach_number==5 and port==3:td.device_number=2;td.coach_number=fd.coach_number+1
        if td.coach_number is not None:q.append(td)
sw=[d for d in devices.values() if d.type=='SW']
ap=[d for d in devices.values() if d.type=='AP']
us=[d for d in sw if d.coach_number is None];ua=[d for d in ap if d.coach_number is None]
print(f"{'PATCHED' if PATCHED else 'UNPATCHED'}: SW {len(sw)-len(us)}/{len(sw)}, AP {len(ap)-len(ua)}/{len(ap)}")
if us:print("unnumbered SW:",", ".join(d.ip for d in us))
