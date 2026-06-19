#!/usr/bin/env python3
"""
Zabbix interface-IP reconciler for DOSTO-NEU fleet (DHCP drift fix).

Scope: explicit enrolment of (CCU-IP -> Zabbix host group) pairs. DOSTO 50_* ONLY.
Action: hostinterface.update — rewrites a host's interface IP to its live DHCP lease,
        matched by MAC. NEVER touches templates, triggers, items, or host names.
        NEVER uses host.update with an interfaces[] block (ZBX-13589 deletes+re-adds
        the interface and fails when a template is linked).

Default = DRY RUN (prints intended updates, writes nothing). --commit to write.
Bootstrap = derive MAC->interfaceid map by joining on the CURRENT IP (valid only
            when bindings are correct), then persist MAC into host inventory
            (macaddress_a) so future runs are IP-independent.

Safety rails:
  - absent != unreachable: zero leases / SSH error => abort that train, write nothing.
  - match on OUI (a0:59:3a switch, 00:14:5a AP) — NOT pool range (devices-pool leak).
  - read-modify-write interface (type-2 SNMP needs both ip+dns); never blank dns.
"""
import json, subprocess, sys, os, ssl, time, urllib.request, argparse, re
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1252 chokes on ✓/— otherwise
except Exception:
    pass

# --- Credentials: env first, then optional JSON config, then (last) inline fallback ---
# Set ZBX_RECONCILE_USER / ZBX_RECONCILE_PASS in the environment for production, or drop
# a JSON {"user":..,"pass":..} at scripts/.zbx_reconcile_creds.json (gitignored).
ZBX_URL  = os.environ.get("ZBX_RECONCILE_URL",
                          "https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php")
SSH_KEY  = os.environ.get("ZBX_RECONCILE_SSHKEY",
                          "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh")
_CRED_FILE = Path(__file__).with_name(".zbx_reconcile_creds.json")
def _load_creds():
    u, p = os.environ.get("ZBX_RECONCILE_USER"), os.environ.get("ZBX_RECONCILE_PASS")
    if u and p:
        return u, p
    if _CRED_FILE.exists():
        c = json.loads(_CRED_FILE.read_text())
        return c["user"], c["pass"]
    return "okapi", "5te8x7Dg5pweMu4R"   # fallback for interactive proof runs only
ZBX_USER, ZBX_PASS = _load_creds()

# --- EXPLICIT FLEET ENROLMENT (DOSTO 50_* ONLY; enzo 111_* deliberately absent) ---
ENROLMENT = [
    # (label,    ccu_ip,         zabbix_group)
    ("4736-115", "10.179.18.1",  "50_6018"),
    ("4736-112", "10.179.40.1",  "50_6040"),
]

SWITCH_OUI = "a0:59:3a"
AP_OUI     = "00:14:5a"

# --- Self-monitoring: heartbeat trapper item (the watcher-for-the-watcher) ---
# Send a per-run heartbeat via zabbix_sender so a trigger can alarm if THIS script dies.
# host = the trapper host in Zabbix; key = a trapper item. Both optional (skip if unset).
HEARTBEAT_HOST   = os.environ.get("ZBX_RECONCILE_HB_HOST", "")    # e.g. "zbx-reconciler"
HEARTBEAT_KEY    = os.environ.get("ZBX_RECONCILE_HB_KEY",  "reconcile.lastrun")
ZBX_SENDER       = os.environ.get("ZBX_SENDER_BIN", "zabbix_sender")
ZBX_SERVER       = os.environ.get("ZBX_RECONCILE_SERVER", "")     # zabbix_sender -z target

# Two-snapshot lease confirmation: require two identical reads this far apart (s) before
# writing, to ride out the 2-min DHCP lease race after a power-cycle.
SNAPSHOT_GAP_S   = int(os.environ.get("ZBX_RECONCILE_SNAPSHOT_GAP", "125"))

LOG_FILE = Path(__file__).with_name("zbx_reconcile.jsonl")
def log(event, **kw):
    """Append one structured JSONL line + echo a human line."""
    rec = {"event": event, **kw}
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass

_ctx = ssl.create_default_context(); _ctx.check_hostname=False; _ctx.verify_mode=ssl.CERT_NONE
_auth = None
def zbx(method, params):
    global _auth
    pl = {"jsonrpc":"2.0","method":method,"params":params,"id":1}
    if _auth and method != "user.login": pl["auth"] = _auth
    req = urllib.request.Request(ZBX_URL, data=json.dumps(pl).encode(),
                                 headers={"Content-Type":"application/json-rpc"})
    r = json.load(urllib.request.urlopen(req, context=_ctx, timeout=30))
    if "error" in r: raise RuntimeError(f"{method}: {r['error']}")
    return r["result"]

# nv6 coach order front->back: A C D E F B  => positional R1..R6 (nv6-topology.md).
# Advisory cross-check only: warns if the live lease-hostname's coach/slot doesn't agree
# with the Zabbix host's R#/SW# name. The MAC join remains authoritative regardless.
_COACH_TO_R = {"A":"R1","C":"R2","D":"R3","E":"R4","F":"R5","B":"R6"}
def _hostname_xcheck(zbx_host, lease_host):
    """True if lease-host coach/slot agrees with Zabbix R#/SW#|AP# name (or can't tell)."""
    # lease_host e.g. nv6-A2-v8-143  or  AP3m-v1-00145a / AP4-v1
    mz = re.search(r"_R(\d)_(SW|AP)(\d)", zbx_host)
    if not mz:
        return True  # can't evaluate -> don't warn
    r_num, kind, num = mz.group(1), mz.group(2), mz.group(3)
    if kind == "SW":
        ml = re.search(r"nv6-([A-F])(\d)", lease_host)
        if not ml:
            return True
        coach, sw = ml.group(1), ml.group(2)
        return _COACH_TO_R.get(coach) == f"R{r_num}" and sw == num
    # APs: lease-host is AP<slot>[m]-v1...; only the slot number is checkable, not the coach.
    ml = re.search(r"AP(\d)", lease_host)
    return True if not ml else (ml.group(1) == num)

def ssh_leases(ccu_ip):
    """Return {mac_lower: (ip, lease_hostname)} for switch+AP OUIs, or None on error."""
    cmd = ["ssh","-i",SSH_KEY,"-o","StrictHostKeyChecking=no","-o","ConnectTimeout=12",
           f"developer@{ccu_ip}","sudo dhcp-lease-list 2>/dev/null"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        return None
    if out.returncode != 0 and not out.stdout.strip():
        return None
    leases = {}
    for line in out.stdout.splitlines():
        m = re.match(r"([0-9a-f:]{17})\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)", line.strip(), re.I)
        if not m: continue
        mac, ip, host = m.group(1).lower(), m.group(2), m.group(3)
        if mac.startswith(SWITCH_OUI) or mac.startswith(AP_OUI):
            leases[mac] = (ip, host)
    return leases or None

def confirmed_leases(ccu_ip, require_two):
    """Read leases; if require_two, read again after SNAPSHOT_GAP_S and require the
    MAC->IP map to be identical (rides out the 2-min lease race). Returns (leases, note).
    leases is None on unreachable. note explains why a write should be withheld."""
    a = ssh_leases(ccu_ip)
    if a is None:
        return None, "unreachable"
    if not require_two:
        return a, "single-snapshot (dry-run)"
    time.sleep(SNAPSHOT_GAP_S)
    b = ssh_leases(ccu_ip)
    if b is None:
        return a, "second snapshot unreachable — WITHHOLD writes"
    am = {m:v[0] for m,v in a.items()}
    bm = {m:v[0] for m,v in b.items()}
    if am != bm:
        return b, "snapshots DIFFER (lease still churning) — WITHHOLD writes"
    return b, "two-snapshot confirmed"

def send_heartbeat(summary):
    """Emit a heartbeat to a Zabbix trapper item so a trigger can alarm if we stop running.
    No-op unless HEARTBEAT_HOST and ZBX_SERVER are configured."""
    if not (HEARTBEAT_HOST and ZBX_SERVER):
        return
    payload = json.dumps(summary)
    try:
        subprocess.run([ZBX_SENDER, "-z", ZBX_SERVER, "-s", HEARTBEAT_HOST,
                        "-k", HEARTBEAT_KEY, "-o", payload],
                       capture_output=True, text=True, timeout=15)
    except Exception as e:
        log("heartbeat_failed", error=str(e))

def main():
    global _auth
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="write changes (default: dry-run)")
    ap.add_argument("--no-two-snapshot", action="store_true",
                    help="skip the two-snapshot lease confirmation (faster; less safe)")
    args = ap.parse_args()
    mode = "COMMIT" if args.commit else "DRY-RUN"
    run_summary = {"mode": mode, "trains": [], "updates": 0, "bootstraps": 0,
                   "withheld": 0, "unreachable": 0, "warnings": 0, "ts": int(time.time())}
    _auth = zbx("user.login", {"username":ZBX_USER,"password":ZBX_PASS})

    for label, ccu_ip, group in ENROLMENT:
        print(f"\n{'='*72}\n{label}  ccu={ccu_ip}  group={group}  [{mode}]\n{'='*72}")
        ts = {"train": label, "group": group}
        run_summary["trains"].append(ts)
        # two-snapshot confirmation only when we intend to write
        leases, note = confirmed_leases(ccu_ip, require_two=args.commit)
        print(f"  lease read: {note}")
        if leases is None:
            print(f"  !! could not read leases (CCU unreachable / SSH error) — ABORT train, no writes")
            ts["status"] = "unreachable"; run_summary["unreachable"] += 1
            log("train_unreachable", train=label, ccu=ccu_ip)
            continue
        # withhold writes if the two-snapshot check didn't confirm
        write_allowed = args.commit and note == "two-snapshot confirmed"
        if args.commit and not write_allowed:
            print(f"  !! writes WITHHELD this train: {note}")
            ts["withheld"] = note; run_summary["withheld"] += 1
        print(f"  live leases (switch+AP OUI): {len(leases)}")

        gid = zbx("hostgroup.get", {"filter":{"name":group},"output":["groupid"]})
        if not gid:
            print(f"  !! group {group} not found — skip"); continue
        gid = gid[0]["groupid"]
        # Pull hosts with inventory (persisted MAC lives in inventory.macaddress_a) + interfaces.
        # Restrict to SWITCH/AP hosts: type-2 SNMP interface AND name matches _SW#/_AP#.
        # This EXCLUDES the CCU agent host (e.g. 50_6018_MAR3-B1, type-1 agent at static .1).
        hosts = zbx("host.get", {"groupids":gid,
                                 "output":["hostid","host"],
                                 "selectInterfaces":["interfaceid","ip","dns","type"],
                                 "selectInventory":["macaddress_a"]})
        targets = []  # list of dicts: host, hostid, iface(id/ip/dns), persisted_mac
        for h in hosts:
            if not re.search(r"_(SW|AP)\d", h["host"]):
                continue  # skip CCU / non-device hosts
            snmp = [i for i in h["interfaces"] if i["type"] == "2"]
            if not snmp:
                continue
            inv = h.get("inventory") or {}
            targets.append({"host":h["host"], "hostid":h["hostid"],
                            "iface":snmp[0],
                            "mac":(inv.get("macaddress_a") or "").lower().strip()})

        have_mac = sum(1 for t in targets if t["mac"])
        print(f"  device hosts (SW/AP): {len(targets)}  | with persisted MAC: {have_mac}")

        # ---- BOOTSTRAP (one-time, while binding is known-good): persist MAC by current-IP join ----
        ip_to_lease = {ip:(mac,lhost) for mac,(ip,lhost) in leases.items()}
        boot_writes, boot_skips = [], []
        if have_mac < len(targets):
            print("  -- BOOTSTRAP: deriving MAC from current IP match (requires correct bindings NOW) --")
            for t in targets:
                if t["mac"]:
                    continue
                lease = ip_to_lease.get(t["iface"]["ip"])
                if not lease:
                    boot_skips.append((t["host"], t["iface"]["ip"], "current IP has no live lease — AMBIGUOUS, cannot bootstrap"))
                    continue
                mac, lhost = lease
                # cross-check: lease-hostname position vs Zabbix host name.
                # On MISMATCH we still record it but flag xcheck=False so the write is
                # blocked (persisting a wrong MAC would mis-key the host permanently).
                xcheck = _hostname_xcheck(t["host"], lhost)
                boot_writes.append((t, mac, lhost, xcheck))
            for t,mac,lhost,xc in boot_writes:
                flag = "" if xc else "  ⚠ name/position mismatch — WRITE BLOCKED, verify manually"
                if not xc: run_summary["warnings"] += 1
                print(f"     {t['host']:<20} <= MAC {mac}  (lease-host {lhost}){flag}")
            for host,ip,why in boot_skips:
                print(f"     {host:<20} !! {why} (ip={ip})")
            if boot_skips:
                print(f"  !! {len(boot_skips)} host(s) un-bootstrappable — bindings not fully correct. "
                      f"Re-run bootstrap right after a clean power-cycle when IPs match.")

        # ---- RECONCILE (steady state): match live lease MAC -> persisted-MAC host -> update IP ----
        mac_to_target = {t["mac"]:t for t in targets if t["mac"]}
        # include just-bootstrapped MACs (only those that PASSED the position xcheck)
        for t,mac,_,xc in boot_writes:
            if xc:
                mac_to_target[mac] = t
        drift_updates, unseen = [], []
        for mac,(ip,lhost) in sorted(leases.items(), key=lambda x:x[1][0]):
            t = mac_to_target.get(mac)
            if not t:
                unseen.append((mac, ip, lhost)); continue
            if t["iface"]["ip"] != ip:
                drift_updates.append((t, ip, lhost))

        print(f"  reconcile: {len(drift_updates)} interface(s) need IP update; "
              f"{len(unseen)} live lease(s) map to no known host")
        for t,ip,lhost in drift_updates:
            print(f"     {t['host']:<20} {t['iface']['ip']}  ->  {ip}   (lease-host {lhost})")
        for mac,ip,lhost in unseen:
            print(f"     UNSEEN MAC {mac} ip={ip} lease-host={lhost} (new device? bad bootstrap?)")
        if not drift_updates and not boot_writes:
            print("  ✓ fully reconciled — no action needed.")

        ts.update(updates=len(drift_updates), bootstraps=sum(1 for *_,xc in boot_writes if xc),
                  unseen=len(unseen))

        # ---- WRITES (only with --commit AND two-snapshot confirmed) ----
        if write_allowed:
            n_boot = 0
            for t,mac,lhost,xc in boot_writes:
                if not xc:
                    continue  # blocked: position mismatch
                zbx("host.update", {"hostid":t["hostid"],
                                    "inventory_mode":0,
                                    "inventory":{"macaddress_a":mac}})
                n_boot += 1
            for t,ip,lhost in drift_updates:
                ifc = t["iface"]
                # hostinterface.update keyed on interfaceid — NOT host.update(interfaces[]) (ZBX-13589).
                # type-2 SNMP needs both ip & dns preserved; never blank dns.
                zbx("hostinterface.update", {"interfaceid":ifc["interfaceid"],
                                             "ip":ip, "dns":ifc.get("dns","")})
                log("ip_updated", train=label, host=t["host"],
                    old=ifc["ip"], new=ip, lease_host=lhost)
            run_summary["updates"] += len(drift_updates)
            run_summary["bootstraps"] += n_boot
            print(f"  [COMMITTED] {n_boot} MAC persist + {len(drift_updates)} IP update")

    # ---- run-level summary, log + heartbeat ----
    print(f"\n{'='*72}\nSUMMARY [{mode}]: "
          f"{run_summary['updates']} IP update(s), {run_summary['bootstraps']} bootstrap(s), "
          f"{run_summary['withheld']} withheld, {run_summary['unreachable']} unreachable, "
          f"{run_summary['warnings']} warning(s)\n{'='*72}")
    log("run_summary", **run_summary)
    send_heartbeat(run_summary)
    # non-zero exit if anything needs human attention (for Task Scheduler last-result)
    if run_summary["warnings"] or run_summary["unreachable"] or run_summary["withheld"]:
        sys.exit(2)

if __name__ == "__main__":
    main()
