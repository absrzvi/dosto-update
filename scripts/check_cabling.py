#!/usr/bin/env python3
"""
DOSTO nv6 cabling mismatch checker.

Connects to a CCU, auto-discovers all VDS switches on vlan100, pulls LLDP
from every switch, identifies each switch by its car/position label
(e.g. A1, D3, F2), and compares e0-0 / e0-1 against the expected topology
from the IP Port Allocation schema.

Produces a plain-English remediation report telling Stadler exactly which
cables are wrong and how to fix them.

Usage (run on the local machine):
    python3 check_cabling.py <CCU_IP> [--key <ssh_key_path>]

Examples:
    python3 check_cabling.py 10.179.11.1
    python3 check_cabling.py 10.179.47.1 --key /path/to/openssh

The script reads the nv6 expected topology from the hard-coded schema below
(derived from the 4736-103 IP Port Allocation document, valid for all
DOSTO NEU 6-car consists with car labels A–F).

Requirements:
    pip install paramiko sshpass    # or: apt install sshpass
    sshpass must be available on PATH (used for switch SSH with password)
"""

import argparse
import re
import subprocess
import sys
import time

# ── Constants ────────────────────────────────────────────────────────────────

SWITCH_PASSWORD = "Nom@dCome1n"
CCU_USER        = "developer"
CCU_KEY         = "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"
SWITCH_USER     = "admin"
SWITCH_OUI      = "a0:59:3a"
VLAN100_OFFSET  = 128   # vlan100 subnet starts at .128

SSH_LEGACY = (
    "-o StrictHostKeyChecking=no "
    "-o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)

# nv6 expected trunk topology — derived from 4736-103 IP Port Allocation schema.
# Key = switch label (e.g. "D1"), value = (e0-0 expected peer, e0-1 expected peer).
NV6_SCHEMA = {
    "A1": ("A3", "C1"),
    "A2": ("A3", "C3"),
    "A3": ("A1", "A2"),
    "C1": ("A1", "D1"),
    "C2": ("C3", "D3"),
    "C3": ("A2", "C2"),
    "D1": ("C1", "E2"),
    "D2": ("D3", "E1"),
    "D3": ("C2", "D2"),
    "E1": ("F1", "D2"),
    "E2": ("E3", "D1"),
    "E3": ("F2", "E2"),
    "F1": ("B1", "E1"),
    "F2": ("F3", "E3"),
    "F3": ("B2", "F2"),
    "B1": ("B3", "F1"),
    "B2": ("B3", "F3"),
    "B3": ("B1", "B2"),
}

# nv4 expected trunk topology — derived from 4734-101 IP Port Allocation schema.
# 4-car consist: cars A, G, E, B (12 switches total).
NV4_SCHEMA = {
    "A1": ("A3", "G1"),
    "A2": ("A3", "G3"),
    "A3": ("A1", "A2"),
    "G1": ("A1", "E2"),
    "G2": ("G3", "E1"),
    "G3": ("A2", "G2"),
    "E1": ("B1", "G2"),
    "E2": ("E3", "G1"),
    "E3": ("B2", "E2"),
    "B1": ("B3", "E1"),
    "B2": ("B3", "E3"),
    "B3": ("B1", "B2"),
}

# Human-readable car descriptions for the Stadler report
CAR_LABELS = {
    "A": "Car A (end car, Stadler FW side)",
    "B": "Car B (end car, opposite end)",
    "C": "Car C",
    "D": "Car D (CCU car)",
    "E": "Car E",
    "F": "Car F",
}

# ── SSH helpers ───────────────────────────────────────────────────────────────

def ssh_ccu(ccu_ip, key, cmd, timeout=30):
    """Run a command on the CCU and return stdout."""
    result = subprocess.run(
        ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
         "-o", f"ConnectTimeout=10",
         f"{CCU_USER}@{ccu_ip}", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()


def ssh_switch(ccu_ip, key, switch_ip, cmd, timeout=15):
    """Run a single CLI command on a VDS switch via the CCU as jump host."""
    jump = f"{CCU_USER}@{ccu_ip}"
    inner = (
        f"sshpass -p '{SWITCH_PASSWORD}' ssh {SSH_LEGACY} "
        f"{SWITCH_USER}@{switch_ip} '{cmd}'"
    )
    result = subprocess.run(
        ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
         "-o", f"ConnectTimeout=10",
         jump, inner],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip()


# ── Discovery ────────────────────────────────────────────────────────────────

def discover_switches(ccu_ip, key):
    """
    Return (switch_list, subnet, dhcp_label_map) where:
      switch_list     — sorted list of VDS switch IPs
      subnet          — e.g. "10.179.11"
      dhcp_label_map  — {ip: label}  e.g. {"10.179.11.186": "D1"}
                        derived directly from DHCP hostnames (nv6-D1-v4-131 -> D1)
    """
    print(f"  Discovering switches via DHCP lease list on {ccu_ip}...")

    lease_out = ssh_ccu(ccu_ip, key, "sudo dhcp-lease-list 2>/dev/null", timeout=60)

    ips = []
    dhcp_label_map = {}
    subnet = None

    for line in lease_out.splitlines():
        # Only VDS switches (OUI a0:59:3a)
        if SWITCH_OUI not in line.lower():
            continue
        # Format: "a0:59:3a:xx:xx:xx  10.179.x.y   nv6-D1-v4-131  ..."
        parts = line.split()
        if len(parts) < 3:
            continue
        ip       = parts[1]
        hostname = parts[2]
        label    = parse_switch_label(hostname)
        if label:
            ips.append(ip)
            dhcp_label_map[ip] = label
            if not subnet:
                m = re.match(r"(\d+\.\d+\.\d+)\.\d+", ip)
                if m:
                    subnet = m.group(1)

    ips.sort(key=lambda x: int(x.split(".")[-1]))
    print(f"  Found {len(ips)} VDS switches: {', '.join(ips)}")
    if dhcp_label_map:
        print(f"  DHCP labels resolved: { {v: k for k,v in sorted(dhcp_label_map.items())} }")
    return ips, subnet or "unknown", dhcp_label_map


# ── LLDP collection ───────────────────────────────────────────────────────────

def parse_switch_label(sysname):
    """'nv6-D1-v5-130', 'nv4-G2-v4-001' -> 'D1', 'G2'"""
    if not sysname:
        return None
    m = re.search(r"nv[46]-([A-Z]\d+)-", sysname, re.I)
    return m.group(1).upper() if m else None


def detect_schema(dhcp_label_map):
    """Return NV4_SCHEMA or NV6_SCHEMA based on which labels appear in DHCP leases."""
    labels = set(dhcp_label_map.values())
    nv4_labels = set(NV4_SCHEMA.keys())
    nv6_labels = set(NV6_SCHEMA.keys())
    nv4_hits = len(labels & nv4_labels)
    nv6_hits = len(labels & nv6_labels)
    if nv4_hits > nv6_hits:
        return NV4_SCHEMA, "nv4"
    return NV6_SCHEMA, "nv6"


def collect_lldp(ccu_ip, key, switch_ips):
    """
    Returns dict: { switch_ip: { "label": "D1", "e0-0": "C1", "e0-1": "E2", ... } }
    label may be None if not identifiable from LLDP.
    """
    print(f"\n  Collecting LLDP from {len(switch_ips)} switches (this takes ~1 min)...")
    data = {}
    for ip in switch_ips:
        raw = ssh_switch(ccu_ip, key, ip, "show lldp neighbours")
        neighbours = {}
        for line in raw.splitlines():
            m = re.match(r"^(e\d+-\d+)\s+[\da-f:]+\s+(\S+)", line, re.I)
            if m:
                port  = m.group(1)
                peer  = parse_switch_label(m.group(2))
                if peer:
                    neighbours[port] = peer
        data[ip] = {"label": None, "raw_neighbours": neighbours}
        sys.stdout.write(".")
        sys.stdout.flush()
    print()
    return data


def identify_switches(data, dhcp_label_map=None, schema=None):
    """
    Assign a schema label to each switch IP.

    Strategy:
      0. Seed from DHCP hostnames (nv6-D1-v4-131 -> D1) — most reliable.
      1. If a switch's {e0-0 peer, e0-1 peer} exactly matches a schema entry, use that.
      2. Fall back to symmetry propagation via already-identified neighbours.
    """
    if schema is None:
        schema = NV6_SCHEMA

    ip_to_label  = {}
    label_to_ip  = {}

    # Pass 0: seed from DHCP hostnames
    if dhcp_label_map:
        for ip, label in dhcp_label_map.items():
            if label in schema and ip in data:
                ip_to_label[ip]    = label
                label_to_ip[label] = ip

    # Pass 1: exact peer-set match
    for ip, d in data.items():
        peers = set(d["raw_neighbours"].values())
        for label, (s00, s01) in schema.items():
            if peers == {s00, s01}:
                ip_to_label[ip]    = label
                label_to_ip[label] = ip
                break

    # Pass 2: propagate via symmetry — if known switch X sees Y on port P,
    # and schema says X's port P peer is label Z, then Y's IP is Z.
    changed = True
    while changed:
        changed = False
        for ip, label in list(ip_to_label.items()):
            s00, s01 = schema[label]
            nb = data[ip]["raw_neighbours"]
            for port, schema_peer in [("e0-0", s00), ("e0-1", s01)]:
                actual_peer_label = nb.get(port)
                if actual_peer_label == schema_peer and schema_peer not in label_to_ip:
                    # Find which IP has this label in their neighbours pointing back
                    for ip2, d2 in data.items():
                        if ip2 in ip_to_label:
                            continue
                        if actual_peer_label in d2["raw_neighbours"].values():
                            # Check this IP sees our known switch too
                            back_peers = set(d2["raw_neighbours"].values())
                            if label in back_peers:
                                ip_to_label[ip2]           = schema_peer
                                label_to_ip[schema_peer]   = ip2
                                changed = True
                                break

    # Write labels back into data
    for ip, label in ip_to_label.items():
        data[ip]["label"] = label

    return data, ip_to_label, label_to_ip


# ── Comparison ────────────────────────────────────────────────────────────────

def compare_topology(data, label_to_ip, schema=None):
    """
    Returns:
      ok_links      — list of (label, port, peer)
      mismatches    — list of (label, ip, port, expected_peer, actual_peer)
      isolated      — list of labels with no identified IP
    """
    if schema is None:
        schema = NV6_SCHEMA

    ok_links   = []
    mismatches = []
    isolated   = []

    for label in sorted(schema):
        s00, s01 = schema[label]
        ip = label_to_ip.get(label)
        if not ip:
            isolated.append(label)
            continue
        nb = data[ip]["raw_neighbours"]
        for port, expected in [("e0-0", s00), ("e0-1", s01)]:
            actual = nb.get(port)
            if actual == expected:
                ok_links.append((label, port, expected))
            else:
                mismatches.append((label, ip, port, expected, actual))

    return ok_links, mismatches, isolated


# ── Remediation report ────────────────────────────────────────────────────────

def remediation_report(mismatches, isolated, ccu_ip, subnet, fzg_id):
    lines = []
    lines.append("=" * 70)
    lines.append(f"DOSTO nv6 Cabling Mismatch Report")
    lines.append(f"CCU: {ccu_ip}   Subnet: {subnet}.0/25   Fzg: {fzg_id}")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    lines.append("=" * 70)

    if not mismatches and not isolated:
        lines.append("\nRESULT: ALL CORRECT — topology matches schema. No cabling errors found.")
        return "\n".join(lines)

    lines.append(f"\nRESULT: {len(mismatches)} port mismatch(es) found"
                 + (f", {len(isolated)} switch(es) isolated." if isolated else "."))

    # Group mismatches by inter-car boundary for readability
    if mismatches:
        lines.append("\n── Mismatched ports ──────────────────────────────────────────────────")
        lines.append(f"  {'Switch':<6} {'IP':<18} {'Port':<6} {'Expected peer':<16} {'Actual peer':<16}")
        lines.append(f"  {'-'*5:<6} {'-'*15:<18} {'-'*5:<6} {'-'*13:<16} {'-'*13:<16}")
        for label, ip, port, expected, actual in mismatches:
            actual_str = actual if actual else "NO NEIGHBOUR (disconnected)"
            lines.append(f"  {label:<6} {ip:<18} {port:<6} {expected:<16} {actual_str:<16}")

    if isolated:
        lines.append("\n── Isolated switches (not reachable via any trunk) ───────────────────")
        for label in isolated:
            lines.append(f"  {label}  — no path into fabric; both e0-0 and e0-1 cables misrouted")

    # Plain-English fix instructions
    lines.append("\n── What Stadler needs to fix ─────────────────────────────────────────")

    # Pair up mismatches to find swapped cable pairs
    explained = set()
    fix_number = 0

    for i, (label_a, ip_a, port_a, exp_a, act_a) in enumerate(mismatches):
        if i in explained:
            continue
        # Look for the complementary swap: another mismatch where actual==exp_a and expected==label_a
        paired = None
        for j, (label_b, ip_b, port_b, exp_b, act_b) in enumerate(mismatches):
            if j <= i or j in explained:
                continue
            if act_b == label_a and act_a == label_b and port_a == port_b:
                paired = j
                break

        fix_number += 1
        if paired is not None:
            label_b, ip_b, port_b, exp_b, act_b = mismatches[paired]
            explained.add(i)
            explained.add(paired)
            lines.append(
                f"\n  Fix {fix_number}: Swap two cables at the {label_a[0]}/{label_b[0]} inter-car connector"
            )
            lines.append(
                f"    Cable currently plugged into {label_a} {port_a} should go to {exp_a} {port_a}"
            )
            lines.append(
                f"    Cable currently plugged into {label_b} {port_b} should go to {exp_b} {port_b}"
            )
            lines.append(
                f"    Action: at the coupler between cars {label_a[0]} and {label_b[0]}, "
                f"swap the {port_a} terminations on {label_a} and {label_b}."
            )
        else:
            explained.add(i)
            actual_str = act_a if act_a else "nothing (cable appears disconnected)"
            lines.append(f"\n  Fix {fix_number}: Reconnect {label_a} {port_a}")
            lines.append(f"    Currently connected to: {actual_str}")
            lines.append(f"    Should be connected to: {exp_a} {port_a}")

    # Anything still unexplained
    for i, (label, ip, port, expected, actual) in enumerate(mismatches):
        if i not in explained:
            fix_number += 1
            actual_str = actual if actual else "nothing (cable appears disconnected)"
            lines.append(f"\n  Fix {fix_number}: {label} {port}")
            lines.append(f"    Currently connected to: {actual_str}")
            lines.append(f"    Should be connected to: {expected} {port}")

    if isolated:
        fix_number += 1
        lines.append(f"\n  Fix {fix_number}: Isolated switch(es): {', '.join(isolated)}")
        lines.append(f"    Both e0-0 and e0-1 cables are misrouted — no path exists into the fabric.")
        lines.append(f"    Trace all cables connected to these switches and re-seat per schema.")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Fix Windows console encoding
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="DOSTO nv6 cabling mismatch checker")
    parser.add_argument("ccu_ip", help="CCU IP address (e.g. 10.179.11.1)")
    parser.add_argument("--key", default=CCU_KEY, help="Path to SSH private key for CCU")
    parser.add_argument("--fzg", default="unknown", help="Fzg. ID for report header (e.g. 131)")
    parser.add_argument("--out", default=None, help="Write report to file (default: stdout)")
    args = parser.parse_args()

    print(f"\nDOSTO nv6 Cabling Check — CCU: {args.ccu_ip}")
    print("-" * 50)

    # 1. Discover switches
    switch_ips, subnet, dhcp_label_map = discover_switches(args.ccu_ip, args.key)

    # Auto-detect nv4 vs nv6 from DHCP labels
    schema, schema_name = detect_schema(dhcp_label_map)
    expected_count = 12 if schema_name == "nv4" else 18
    print(f"  Detected consist type: {schema_name} ({expected_count} switches expected)")
    if len(switch_ips) != expected_count:
        print(f"WARNING: expected {expected_count} switches, found {len(switch_ips)}")

    # 2. Collect LLDP
    data = collect_lldp(args.ccu_ip, args.key, switch_ips)

    # 3. Identify switches (DHCP labels as primary seed)
    data, ip_to_label, label_to_ip = identify_switches(data, dhcp_label_map, schema)

    identified = sum(1 for d in data.values() if d["label"])
    print(f"  Identified {identified}/{len(switch_ips)} switches by label.")
    unidentified = [ip for ip, d in data.items() if not d["label"]]
    if unidentified:
        print(f"  Could not identify: {unidentified}")

    # 4. Compare
    ok_links, mismatches, isolated = compare_topology(data, label_to_ip, schema)

    # 5. Print summary table
    print(f"\n  {'Switch':<6} {'IP':<18} {'e0-0 exp':<10} {'e0-0 act':<10} {'e0-1 exp':<10} {'e0-1 act':<10} Status")
    print(f"  {'-'*5:<6} {'-'*15:<18} {'-'*8:<10} {'-'*8:<10} {'-'*8:<10} {'-'*8:<10} ------")
    for label in sorted(schema):
        s00, s01 = schema[label]
        ip = label_to_ip.get(label, "—")
        nb = data[ip]["raw_neighbours"] if ip and ip in data else {}
        a00 = nb.get("e0-0", "?")
        a01 = nb.get("e0-1", "?")
        ok  = (a00 == s00 and a01 == s01)
        flag = "OK" if ok else "MISMATCH <--"
        print(f"  {label:<6} {ip:<18} {s00:<10} {a00:<10} {s01:<10} {a01:<10} {flag}")

    # 6. Build and output report
    report = remediation_report(mismatches, isolated, args.ccu_ip, subnet, args.fzg)
    print()
    print(report)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to: {args.out}")

    sys.exit(1 if (mismatches or isolated) else 0)


if __name__ == "__main__":
    main()
