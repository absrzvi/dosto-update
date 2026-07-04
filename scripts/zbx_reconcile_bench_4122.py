#!/usr/bin/env python3
"""
Zabbix interface-IP reconciler for the 4122 BENCH — POSITION-keyed (swap-safe).

Why a separate script from zbx_reconcile.py: the fleet script joins live lease -> Zabbix
host by MAC. Bench switches are expected to be REPLACED (new MAC, same position/hostname),
so a MAC join breaks on every swap. This script joins by POSITION instead:

    live lease hostname  4t-A3-v3-250   --(coach A, sw 3)-->   Zabbix host  50_4122_R1_SW3

Position (coach+slot) is stable across a hardware swap; the replacement unit leases under
the same 4t-A3 hostname. Also reboot-safe: re-reads DHCP each run, so it tracks the
dynamic bench IPs (.178-.199) that drift on every lease renewal.

Scope (deliberately narrow):
  - SWITCHES ONLY. The single bench AP leases as 'v1-AP1m-...' which carries the slot but
    NOT the coach, so it cannot be position-joined from the hostname alone (would need
    switch-side LLDP to find which e0-4 it hangs off). Left for a follow-up.
  - Positions with NO live lease (e.g. A1/B3 when cold-bypassed/absent) are SKIPPED — their
    Zabbix hosts stay unreachable, which is CORRECT (they are genuinely down).

Safety (mirrors zbx_reconcile.py):
  - DRY-RUN by default; --commit to write.
  - two-snapshot lease confirmation before writing (rides out the 2-min DHCP race).
  - absent != unreachable: SSH error / zero leases => abort, write nothing.
  - hostinterface.update keyed on interfaceid (NOT host.update(interfaces[]) — ZBX-13589).
  - read-modify-write: preserve dns on the type-2 SNMP interface.
"""
import json, subprocess, sys, os, ssl, time, urllib.request, argparse, re
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ZBX_URL = os.environ.get("ZBX_RECONCILE_URL",
                         "https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php")
SSH_KEY = os.environ.get("ZBX_RECONCILE_SSHKEY",
                         "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh")
CCU_IP  = os.environ.get("BENCH_CCU_IP", "10.179.122.1")
GROUP   = os.environ.get("BENCH_GROUP", "50_4122")

def _load_creds():
    u, p = os.environ.get("ZBX_RECONCILE_USER"), os.environ.get("ZBX_RECONCILE_PASS")
    if u and p:
        return u, p
    cf = Path(__file__).with_name(".zbx_reconcile_creds.json")
    if cf.exists():
        c = json.loads(cf.read_text()); return c["user"], c["pass"]
    return "okapi", "5te8x7Dg5pweMu4R"
ZBX_USER, ZBX_PASS = _load_creds()

SWITCH_OUI = "a0:59:3a"
SNAPSHOT_GAP_S = int(os.environ.get("ZBX_RECONCILE_SNAPSHOT_GAP", "125"))

# nv4 BENCH coach order front->back: A G E B => R1..R4 (matches NMS "NV4 - Bench" template).
_COACH_TO_R = {"A": "R1", "G": "R2", "E": "R3", "B": "R4"}

_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE
_auth = None
def zbx(method, params):
    global _auth
    pl = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    if _auth and method != "user.login":
        pl["auth"] = _auth
    req = urllib.request.Request(ZBX_URL, data=json.dumps(pl).encode(),
                                 headers={"Content-Type": "application/json-rpc"})
    r = json.load(urllib.request.urlopen(req, context=_ctx, timeout=30))
    if "error" in r:
        raise RuntimeError(f"{method}: {r['error']}")
    return r["result"]

def ssh_switch_leases(ccu_ip):
    """Return {position: (ip, lease_hostname)} for switch OUI leases, keyed on POSITION
    (e.g. 'R1_SW3'), or None on SSH error. Position derived from the 4t-<coach><slot>
    lease hostname — NOT from MAC."""
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=12",
           f"developer@{ccu_ip}", "sudo dhcp-lease-list 2>/dev/null"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        return None
    if out.returncode != 0 and not out.stdout.strip():
        return None
    by_pos = {}
    for line in out.stdout.splitlines():
        m = re.match(r"([0-9a-f:]{17})\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)", line.strip(), re.I)
        if not m:
            continue
        mac, ip, host = m.group(1).lower(), m.group(2), m.group(3)
        if not mac.startswith(SWITCH_OUI):
            continue
        mp = re.match(r"[0-9a-z]+-([AGEB])(\d)", host, re.I)  # 4t-A3-... / nv4-A3-...
        if not mp:
            continue
        pos = f"{_COACH_TO_R[mp.group(1).upper()]}_SW{mp.group(2)}"
        by_pos[pos] = (ip, host)
    return by_pos or None

def confirmed_leases(ccu_ip, require_two):
    a = ssh_switch_leases(ccu_ip)
    if a is None:
        return None, "unreachable"
    if not require_two:
        return a, "single-snapshot (dry-run)"
    time.sleep(SNAPSHOT_GAP_S)
    b = ssh_switch_leases(ccu_ip)
    if b is None:
        return a, "second snapshot unreachable — WITHHOLD"
    if {k: v[0] for k, v in a.items()} != {k: v[0] for k, v in b.items()}:
        return b, "snapshots DIFFER (lease churning) — WITHHOLD"
    return b, "two-snapshot confirmed"

def main():
    global _auth
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--no-two-snapshot", action="store_true", help="skip two-snapshot confirm")
    args = ap.parse_args()
    mode = "COMMIT" if args.commit else "DRY-RUN"
    print(f"{'='*72}\nBENCH 4122 reconcile (POSITION-keyed)  ccu={CCU_IP}  group={GROUP}  [{mode}]\n{'='*72}")

    _auth = zbx("user.login", {"username": ZBX_USER, "password": ZBX_PASS})

    leases, note = confirmed_leases(CCU_IP, require_two=(args.commit and not args.no_two_snapshot))
    print(f"  lease read: {note}")
    if leases is None:
        print("  !! CCU unreachable / SSH error — ABORT, no writes.")
        sys.exit(2)
    write_allowed = args.commit and (args.no_two_snapshot or note == "two-snapshot confirmed")
    if args.commit and not write_allowed:
        print(f"  !! writes WITHHELD: {note}")
    print(f"  live switch leases (by position): {len(leases)}")

    gid = zbx("hostgroup.get", {"filter": {"name": GROUP}, "output": ["groupid"]})
    if not gid:
        print(f"  !! group {GROUP} not found"); sys.exit(2)
    gid = gid[0]["groupid"]
    hosts = zbx("host.get", {"groupids": gid, "output": ["hostid", "host"],
                             "selectInterfaces": ["interfaceid", "ip", "dns", "type"]})

    # index Zabbix switch hosts by their position token (R#_SW#)
    zbx_by_pos = {}
    for h in hosts:
        m = re.search(r"_(R\d_SW\d)$", h["host"])
        if not m:
            continue
        snmp = [i for i in h["interfaces"] if i["type"] == "2"]
        if snmp:
            zbx_by_pos[m.group(1)] = {"host": h["host"], "hostid": h["hostid"], "iface": snmp[0]}

    updates, skipped_no_lease, unseen = [], [], []
    for pos, zh in sorted(zbx_by_pos.items()):
        lease = leases.get(pos)
        if not lease:
            skipped_no_lease.append(pos)      # A1/B3 bypassed/absent — correct to skip
            continue
        ip, lhost = lease
        if zh["iface"]["ip"] != ip:
            updates.append((zh, ip, lhost))
    for pos in leases:
        if pos not in zbx_by_pos:
            unseen.append((pos, leases[pos]))

    print(f"\n  {len(updates)} interface(s) need IP update; "
          f"{len(skipped_no_lease)} position(s) have no lease (skipped); "
          f"{len(unseen)} lease(s) map to no Zabbix host")
    for zh, ip, lhost in updates:
        print(f"     {zh['host']:<18} {zh['iface']['ip']:16} -> {ip:16} (lease {lhost})")
    if skipped_no_lease:
        print(f"     skipped (no live lease — genuinely absent/bypassed): {', '.join(sorted(skipped_no_lease))}")
    for pos, (ip, lhost) in unseen:
        print(f"     UNSEEN position {pos} ip={ip} lease={lhost} (no matching Zabbix host)")
    if not updates:
        print("  ✓ switch interfaces already reconciled — no action.")

    if write_allowed and updates:
        for zh, ip, lhost in updates:
            ifc = zh["iface"]
            zbx("hostinterface.update", {"interfaceid": ifc["interfaceid"],
                                         "ip": ip, "dns": ifc.get("dns", "")})
        print(f"\n  [COMMITTED] {len(updates)} switch IP update(s).")
        print("  NOTE: run `zabbix_proxy -R config_cache_reload` on the CCU (or wait a cycle) "
              "so the live proxy re-polls the corrected IPs.")
    elif args.commit and not write_allowed:
        print("\n  (writes withheld — see note above)")

if __name__ == "__main__":
    main()
