#!/usr/bin/env python3
"""
OBN nv6 coach-numbering: PRIMARY (hardcoded walk, unchanged) + FALLBACK (redundant-path).

Proposal reference implementation for R&D. Reads an OBN discovery.json and prints the
backbone-switch overview the way OBN would, but with a fallback pass that recovers
switches the hardcoded walk could not reach IF they are still reachable via some
redundant LLDP SW-SW path and self-report a valid identity (config string).

  python fallback_numbering.py <discovery.json>

Output flags each switch's provenance:
  expected   -> numbered by the primary hardcoded walk (on its designed wiring)
  FALLBACK   -> not on expected wiring, but reachable via redundant path; identity
                taken from the switch's own rendered config (e.g. nv6-E2-v8-147)
  UNREACHABLE-> no LLDP SW-SW path at all -> genuinely missing/dead (report as today)
  no-config  -> reachable but no parseable identity -> cannot place, report as today
"""
import json, re, sys
from collections import deque, defaultdict

LETTER2COACH = {'A': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'B': 6}
COACH2LETTER = {v: k for k, v in LETTER2COACH.items()}

def ident_from_config(cfg):
    m = re.match(r'nv6-([A-F])(\d)-', cfg or '')
    return (LETTER2COACH[m.group(1)], int(m.group(2))) if m else None

class Dev:
    def __init__(s, d):
        s.mac = d['mac'].lower(); s.ip = d['ip']; s.serial = d.get('serial', '') or ''
        s.config = d.get('config', '') or ''; s.neighbours = d.get('neighbours', [])
        s.type = None; s.coach_number = None; s.device_number = None; s.via = None

def ftype(d):
    if d.serial.startswith('box'): return 'BOX'
    if d.mac.startswith('a0:59:3a'): return 'SW'
    if d.mac.startswith('00:14:5a'): return 'AP'
    return 'UNKNOWN'

def number(devs):
    devices = {d['mac'].lower(): Dev(d) for d in devs}
    mac2ip = {d['mac'].lower(): d['ip'] for d in devs}
    g = lambda n: devices.get(n.get('mac', '').lower())

    # ---- PASS 1: primary hardcoded nv6 walk (transcribed verbatim from report_dosto_neu.py) ----
    q = deque()
    for d in devices.values():
        d.type = ftype(d)
        if d.type == 'BOX':
            d.coach_number = 3; d.device_number = 1; d.via = 'ccu'; q.append(d)
    while q:
        fd = q.pop()
        for nb in fd.neighbours:
            port = nb.get('port', 0); td = g(nb)
            if td is None or td.coach_number is not None: continue
            if fd.type == 'BOX' and td.type == 'SW':
                if port == 1: td.device_number = 1; td.coach_number = fd.coach_number; td.via = 'expected'
                elif port == 2: td.device_number = 3; td.coach_number = fd.coach_number; td.via = 'expected'
            if fd.type == 'SW' and td.type == 'SW':
                ch, dn, hit = fd.coach_number, fd.device_number, False
                if dn == 3 and port == 4: td.coach_number = ch; td.device_number = 2; hit = True
                if dn == 2 and ch == 3 and port == 4: td.device_number = 1; td.coach_number = ch + 1; hit = True
                if dn == 1 and ch in (4, 5) and port == 3: td.device_number = 1; td.coach_number = ch + 1; hit = True
                if dn == 1 and ch == 6 and port == 3: td.device_number = 3; td.coach_number = ch; hit = True
                if dn == 2 and ch in (5, 6) and port == 4: td.device_number = 3; td.coach_number = ch - 1; hit = True
                if dn == 2 and ch == 4 and port == 4: td.device_number = 1; td.coach_number = ch - 1; hit = True
                if dn == 1 and ch in (2, 3) and port == 3: td.device_number = 1; td.coach_number = ch - 1; hit = True
                if dn == 1 and ch == 1 and port == 3: td.device_number = 3; td.coach_number = ch; hit = True
                if dn == 3 and ch == 1 and port == 4: td.device_number = 2; td.coach_number = ch; hit = True
                if dn == 2 and ch in (1, 2) and port == 4: td.device_number = 3; td.coach_number = ch + 1; hit = True
                if hit: td.via = 'expected'
            if fd.type == 'SW' and td.type == 'AP':
                td.coach_number = fd.coach_number
                if port == 7: td.device_number = fd.device_number
                if fd.device_number == 3 and port == 11: td.device_number = 4
                td.via = 'expected'
            if td.coach_number is not None: q.append(td)

    sw = [d for d in devices.values() if d.type == 'SW']

    # ---- redundant-reachability: undirected SW-SW LLDP graph ----
    adj = defaultdict(set)
    for d in devices.values():
        if d.type != 'SW': continue
        for n in d.neighbours:
            t = g(n)
            if t and t.type == 'SW':
                adj[d.ip].add(t.ip); adj[t.ip].add(d.ip)
    reach = {d.ip for d in sw if d.coach_number is not None}
    fr = deque(reach)
    while fr:
        x = fr.popleft()
        for y in adj[x]:
            if y not in reach: reach.add(y); fr.append(y)

    # ---- PASS 2: fallback ----
    for d in sw:
        if d.coach_number is not None: continue
        if d.ip not in reach:
            d.via = 'UNREACHABLE'; continue
        ident = ident_from_config(d.config)
        if ident:
            d.coach_number, d.device_number = ident; d.via = 'FALLBACK'
        else:
            d.via = 'no-config'
    return sw

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'discovery.json'
    devs = json.load(open(path))
    sw = number(devs)
    shown = [d for d in sw if d.coach_number is not None]
    fb = [d for d in sw if d.via == 'FALLBACK']
    miss = [d for d in sw if d.via in ('UNREACHABLE', 'no-config')]
    print(f"== {path} ==")
    print(f"switches shown: {len(shown)}/{len(sw)}   (primary {len(shown)-len(fb)}, fallback {len(fb)}, unplaced {len(miss)})")
    for d in sorted(sw, key=lambda x: (x.coach_number or 99, x.device_number or 99)):
        if d.coach_number is None:
            print(f"   --   --   {d.ip}  {d.config or '(no config)'}   <-- {d.via}")
            continue
        flag = '' if d.via == 'expected' else f'   <-- {d.via} (reachable, OFF expected wiring)'
        print(f"  coach{d.coach_number} dev{d.device_number}  {d.ip}  {d.config}{flag}")

if __name__ == '__main__':
    main()
