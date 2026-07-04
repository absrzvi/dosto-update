#!/usr/bin/env python3
"""
One-off: find and (optionally) acknowledge+close stale active problems for train 4736-119 (Fzg 147).
Read-only by default. Pass --close to actually ack+close.

Targets the SW/AP unreachable alarms confirmed stale on 2026-06-24 (all rear switches
E2/E3/F2/F3/B2 and their APs verified UP via SSH; alarms dated 12/06 never cleared).
"""
import json, ssl, sys, urllib.request, time

ZBX_URL  = "https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php"
ZBX_USER = "okapi"
ZBX_PASS = "5te8x7Dg5pweMu4R"

_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE
_auth = None

def zbx(method, params):
    pl = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if _auth and method != "user.login":
        pl["auth"] = _auth
    req = urllib.request.Request(ZBX_URL, data=json.dumps(pl).encode(),
                                 headers={"Content-Type": "application/json-rpc"})
    r = json.load(urllib.request.urlopen(req, context=_ctx, timeout=30))
    if "error" in r:
        raise SystemExit(f"Zabbix API error on {method}: {r['error']}")
    return r["result"]

def main():
    global _auth
    do_close = "--close" in sys.argv
    _auth = zbx("user.login", {"username": ZBX_USER, "password": ZBX_PASS})

    # Find hosts whose visible name references 4736-119 / 6012 (the train).
    hosts = zbx("host.get", {
        "search": {"name": "4736-119"},
        "searchByAny": True,
        "output": ["hostid", "name"],
    })
    # Fallback: some installs name the train host by the 6012 fleet number
    if not hosts:
        hosts = zbx("host.get", {"search": {"name": "6012"}, "output": ["hostid", "name"]})

    if not hosts:
        print("No host matched '4736-119' or '6012'. List candidate train hosts:")
        cand = zbx("host.get", {"search": {"name": "4736"}, "output": ["hostid", "name"]})
        for h in cand:
            print(f"  {h['hostid']}  {h['name']}")
        return

    hostids = [h["hostid"] for h in hosts]
    print(f"Matched {len(hosts)} host(s):")
    for h in hosts:
        print(f"  {h['hostid']}  {h['name']}")

    # Active (unresolved) problems on those hosts.
    problems = zbx("problem.get", {
        "hostids": hostids,
        "recent": False,            # only currently-active problems
        "output": ["eventid", "name", "clock", "severity", "acknowledged"],
        "sortfield": ["eventid"],
        "sortorder": "ASC",
    })

    # Bucket A ONLY: the stale 12/06 "unreachable" outage alarms verified false on 2026-06-24.
    # We deliberately do NOT touch: today's fresh port-DOWN alarms, or the 04-01 split-brain alarm.
    def is_stale_outage(p):
        n = p["name"]
        return ("is unavailable by ICMP" in n) or ("cannot be pinged" in n)

    print(f"\n{len(problems)} active problem(s) total:")
    eventids = []
    for p in problems:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(p["clock"])))
        ack = "ACK" if p["acknowledged"] == "1" else "   "
        tgt = "CLOSE" if is_stale_outage(p) else "keep "
        print(f"  [{tgt}][{ack}] sev{p['severity']} {ts}  ev{p['eventid']}  {p['name']}")
        if is_stale_outage(p):
            eventids.append(p["eventid"])

    if not eventids:
        print("\nNothing matched the stale-outage filter to clear.")
        return
    print(f"\n{len(eventids)} stale-outage event(s) selected for ack+close.")

    if not do_close:
        print(f"\n(read-only) {len(eventids)} event(s) would be ack+closed. Re-run with --close to apply.")
        return

    # action bitmask: 1 = close problem, 2 = acknowledge, 4 = add message.
    # These triggers have manual_close=0, so we acknowledge + message only; the problem
    # auto-resolves on the next successful poll (devices are confirmed up).
    msg = ("Verified all referenced rear-coach switches (E2/E3/F2/F3/B2) and their APs "
           "UP via SSH+ICMP on 2026-06-24. Original alarms (12/06) were stale; root cause "
           "was OBN coach-numbering, not a device outage.")
    res = zbx("event.acknowledge", {
        "eventids": eventids,
        "action": 2 | 4,
        "message": msg,
    })
    print(f"\nAcknowledged + messaged: {res.get('eventids', [])}")

if __name__ == "__main__":
    main()
