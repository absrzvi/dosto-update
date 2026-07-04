#!/usr/bin/env python3
"""
Diagnose why 4736-119 (6012) ICMP alarms from 12/06 haven't auto-resolved.
Read-only. Checks: host availability, assigned proxy, proxy last-seen,
and the triggers' recovery state for the stuck switch hosts.
"""
import json, ssl, time, urllib.request

ZBX_URL = "https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php"
ZBX_USER, ZBX_PASS = "okapi", "5te8x7Dg5pweMu4R"
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
        raise SystemExit(f"API error {method}: {r['error']}")
    return r["result"]

def ts(v):
    v = int(v)
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(v)) if v else "never"

def main():
    global _auth
    _auth = zbx("user.login", {"username": ZBX_USER, "password": ZBX_PASS})

    hosts = zbx("host.get", {
        "search": {"name": "6012"},
        "output": ["hostid", "name", "status", "proxy_hostid", "available",
                   "error", "errors_from", "snmp_available", "snmp_error"],
        "selectInterfaces": ["ip", "type", "available", "error"],
    })
    print(f"=== {len(hosts)} hosts for 6012 ===")
    # proxy summary
    proxyids = set(h.get("proxy_hostid", "0") for h in hosts)
    proxies = {}
    if proxyids - {"0"}:
        for p in zbx("proxy.get", {"proxyids": list(proxyids - {"0"}),
                                    "output": ["proxyid", "host", "lastaccess"]}):
            proxies[p["proxyid"]] = p
    print("\n-- proxy assignment --")
    seen = {}
    for h in hosts:
        pid = h.get("proxy_hostid", "0")
        seen.setdefault(pid, 0)
        seen[pid] += 1
    for pid, n in seen.items():
        if pid == "0":
            print(f"  {n} hosts: monitored DIRECTLY by server (no proxy)")
        else:
            p = proxies.get(pid, {})
            print(f"  {n} hosts: proxy '{p.get('host','?')}' (id {pid}) last seen {ts(p.get('lastaccess','0'))}")

    print("\n-- per-host availability (ICMP/SNMP) --")
    for h in sorted(hosts, key=lambda x: x["name"]):
        ifc = h.get("interfaces", [{}])
        ip = ifc[0].get("ip", "?") if ifc else "?"
        avail = {"0": "unknown", "1": "available", "2": "UNAVAILABLE"}.get(h.get("available", "0"), h.get("available"))
        snmp = {"0": "unknown", "1": "available", "2": "UNAVAILABLE"}.get(h.get("snmp_available", "0"), h.get("snmp_available"))
        err = (h.get("error") or h.get("snmp_error") or "").strip()
        flag = "" if avail == "available" else f"  <-- avail={avail} snmp={snmp}"
        print(f"  {h['name']:22} ip={ip:16} {flag} {('ERR:'+err) if err else ''}")

    # The stuck switch hosts from the alarm panel
    stuck = ["R4_SW2", "R4_SW3", "R5_SW2", "R5_SW3", "R6_SW2"]
    print("\n-- active problems on the 5 stuck switches --")
    sids = [h["hostid"] for h in hosts if any(s in h["name"] for s in stuck)]
    probs = zbx("problem.get", {"hostids": sids, "recent": False,
                                "output": ["eventid", "name", "clock", "r_clock", "acknowledged"]})
    for p in probs:
        print(f"  ev{p['eventid']} ack={p['acknowledged']} since {ts(p['clock'])}  {p['name']}")

if __name__ == "__main__":
    main()
