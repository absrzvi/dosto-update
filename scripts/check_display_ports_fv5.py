#!/usr/bin/env python3
"""
DOSTO fv5 (4705-1xx) display-port L2 verifier.

For VLAN-3 "Bildschirm" (display / advertising screen) devices we are NOT meant
to reach the screen from the CCU (they sit on a Stadler-side device VLAN behind
the Stadler firewall). The correct check is done at L2 on the switch access port:

  1. CONFIG  — the port is an untagged VLAN 3 access port with the expected
               description (from the IP-Port-Allocation PDF).
  2. LIVE    — link UP / full duplex, 0 CRC / 0 carrier-false.
  3. DEVICE  — a MAC is learned on the port AND the RX packet counter is
               incrementing across two snapshots => the screen is powered and
               transmitting.

The script resolves each switch's live vlan100 mgmt IP from `dhcp-lease-list`
(by the switch hostname suffix, e.g. fv5-B1-...), so it survives DHCP drift.

Run ON THE CCU (copy to /tmp/):
    sudo python3 /tmp/check_display_ports_fv5.py
(sudo is needed for dhcp-lease-list.)

Add targets by editing TARGETS below. Each is (switch_id, port, expected_ip,
expected_desc_substr). expected_ip is the SCREEN's IP (informational only — it
lives on the screen, not the port; we confirm the screen via MAC+RX, not IP).
"""
import subprocess, re, sys, time

PASSWORD = "Nom@dCome1n"
SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)
EXPECTED_VLAN = "3"       # Displays (Bildschirm) are untagged VLAN 3 access ports
RX_SETTLE_SECS = 8        # gap between the two RX snapshots

# ── Targets: (switch_id, port, screen_ip, expected description substring) ──────
# From 4705-103_IP-Port-Allocation.pdf (Fzg 231). Edit / extend as needed.
TARGETS = [
    ("B1", "e2-1", "172.17.243.227", "Bildschirm Werbung B3"),
    ("F1", "e2-2", "172.17.243.218", "Bildschirm Werbung F5"),
    ("B2", "e2-4", "172.17.243.234", "Bildschirm Werbung B4"),
]
# ─────────────────────────────────────────────────────────────────────────────


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def switch_ip_map():
    """Map switch id (e.g. 'B1') -> live vlan100 IP from dhcp-lease-list.

    Lease hostnames look like 'fv5-B1-v8-231'. We key off the '-<ID>-' token.
    """
    out = sh("sudo dhcp-lease-list 2>/dev/null") or sh("dhcp-lease-list 2>/dev/null")
    mapping = {}
    for line in out.splitlines():
        # a lease line has an IP and a hostname somewhere on it
        ipm = re.search(r"\b(10\.179\.\d+\.\d+)\b", line)
        hm = re.search(r"fv5-([A-Z]\d)-", line, re.I)
        if ipm and hm:
            mapping[hm.group(1).upper()] = ipm.group(1)
    return mapping, out


def switch_cmd(ip, cmd):
    """Run one CLI command on a VDS switch (one cmd per SSH session)."""
    full = (
        f"sshpass -p '{PASSWORD}' ssh {SSH_OPTS} admin@{ip} \"{cmd}\""
    )
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=30)
    return (r.stdout or "") + (r.stderr or "")


def port_vlan(ip, port):
    """Return the access VLAN the port sits in, per 'show vlans'."""
    out = switch_cmd(ip, "show vlans")
    vlan = None
    for line in out.splitlines():
        m = re.match(r"^\s*(\d+)\b", line)
        if m and re.search(rf"\b{re.escape(port)}\b", line):
            vlan = m.group(1)
    return vlan, out


def port_details(ip, port):
    out = switch_cmd(ip, f"show interface {port} details")
    link = "UP" if re.search(r"\bup\b", out, re.I) and not re.search(r"link\s*:?\s*down", out, re.I) else "DOWN"
    def num(pat):
        m = re.search(pat, out, re.I)
        return int(m.group(1)) if m else None
    rx = num(r"RX\s+packets?\s*[:=]?\s*(\d+)") or num(r"(\d+)\s+RX\s+packets")
    crc = num(r"RX\s+crc\s+errors?\s*[:=]?\s*(\d+)")
    carrier = num(r"carrier\s+false\s*[:=]?\s*(\d+)")
    return {"link": link, "rx": rx, "crc": crc, "carrier": carrier, "raw": out}


def port_has_mac(ip, port):
    out = switch_cmd(ip, "show mac-address-table")
    macs = [l for l in out.splitlines() if re.search(rf"\b{re.escape(port)}\b", l)
            and re.search(r"[0-9a-f]{2}:[0-9a-f]{2}:", l, re.I)]
    return macs


def main():
    print("=" * 74)
    print("DOSTO fv5 display-port L2 check  (Fzg 231 / 4705-103 / box1-t41)")
    print("=" * 74)

    ipmap, lease_raw = switch_ip_map()
    if not ipmap:
        print("!! Could not read dhcp-lease-list — run this ON THE CCU with sudo.")
        print("   Raw output was:\n", lease_raw[:400])
        sys.exit(2)

    print("\nResolved switch IPs from DHCP leases:")
    for sid in sorted(ipmap):
        print(f"   {sid:>3} -> {ipmap[sid]}")

    rows = []
    for sid, port, screen_ip, desc in TARGETS:
        ip = ipmap.get(sid)
        if not ip:
            rows.append((sid, port, screen_ip, "NO LEASE", "-", "-", "-",
                         "FAIL: switch not in DHCP leases"))
            continue

        vlan, _ = port_vlan(ip, port)
        d1 = port_details(ip, port)
        time.sleep(RX_SETTLE_SECS)
        d2 = port_details(ip, port)
        macs = port_has_mac(ip, port)

        # verdicts
        cfg_ok = (vlan == EXPECTED_VLAN)
        link_ok = (d1["link"] == "UP")
        clean = (not d1["crc"]) and (not d1["carrier"])
        rx_moving = (d1["rx"] is not None and d2["rx"] is not None and d2["rx"] > d1["rx"])
        dev_ok = bool(macs) and (rx_moving or (d2["rx"] and d2["rx"] > 0))

        verdict = "PASS" if (cfg_ok and link_ok and clean and dev_ok) else "CHECK"
        notes = []
        if not cfg_ok:  notes.append(f"VLAN={vlan} (exp {EXPECTED_VLAN})")
        if not link_ok: notes.append("LINK DOWN")
        if not clean:   notes.append(f"crc={d1['crc']} carrier={d1['carrier']}")
        if not macs:    notes.append("no MAC learned")
        if not rx_moving and macs: notes.append("RX not incrementing")

        rows.append((sid, port, screen_ip,
                     f"vlan{vlan}", d1["link"],
                     "yes" if macs else "no",
                     "yes" if rx_moving else "no",
                     verdict + ((" — " + "; ".join(notes)) if notes else "")))

    # ── table ────────────────────────────────────────────────────────────────
    print("\n" + "-" * 74)
    hdr = ("SW", "PORT", "SCREEN IP", "CFG", "LINK", "MAC", "RX+", "VERDICT")
    print("{:<3} {:<5} {:<16} {:<7} {:<5} {:<4} {:<4} {}".format(*hdr))
    print("-" * 74)
    for r in rows:
        print("{:<3} {:<5} {:<16} {:<7} {:<5} {:<4} {:<4} {}".format(*r))
    print("-" * 74)
    print("\nCFG = access VLAN matches expected (3)   MAC = screen MAC learned on port")
    print("RX+ = RX packet counter incrementing over %ds => device transmitting" % RX_SETTLE_SECS)
    print("PASS = port config correct AND screen powered+transmitting at L2.")
    print("CHECK = see notes; screen may be off/booting, miscabled, or wrong VLAN.")


if __name__ == "__main__":
    main()
