#!/usr/bin/env python3
"""
LLDP topology checker for 4734-119 (Fzg. 119, 6-car DOSTO, CCU box1-t47).
Derived from OBN templates at /etc/obn/template/nv6-*.cfg on box1-t47.

Run on the CCU:  python3 /tmp/lldp_check_4734-119.py
"""
import pexpect, re, sys

PASSWORD = "Nom@dCome1n"
SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)

# VDS switch IPs from sudo dhcp-lease-list on box1-t47 (2026-05-08)
# Hostnames confirmed from DHCP leases (nv6-XX-v5-130 naming).
# Note: .185 = nv6-E1-v5-man, .186 = nv6-B1-v5-man, .189 = nv6-F1-v5-man
# are separate management switches (not in the main spine topology).
# E2 and E3 may still be getting leases — add if they appear.
SWITCHES = {
    "A1": "10.179.47.181",
    "A2": "10.179.47.179",
    "A3": "10.179.47.187",
    "C1": "10.179.47.191",
    "C2": "10.179.47.182",
    "C3": "10.179.47.188",
    "D1": "10.179.47.184",
    "D2": "10.179.47.192",
    "D3": "10.179.47.183",
    "E1": "10.179.47.180",
    "F1": "10.179.47.194",
    "F2": None,  # NOT in DHCP lease — switch offline or disconnected
    "F3": "10.179.47.178",
    "B1": "10.179.47.190",
    "B2": "10.179.47.195",
    "B3": "10.179.47.193",
    # E2 and E3 also NOT in DHCP lease — switches offline or disconnected
    "E2": None,
    "E3": None,
}

# Expected topology from /etc/obn/template/nv6-*.cfg
EXPECTED_TOPOLOGY = {
    "A1": {"e0-0": "A3", "e0-1": "C1"},
    "A2": {"e0-0": "A3", "e0-1": "C3"},
    "A3": {"e0-0": "A1", "e0-1": "A2"},
    "C1": {"e0-0": "A1", "e0-1": "D1"},
    "C2": {"e0-0": "C3", "e0-1": "D3"},
    "C3": {"e0-0": "A2", "e0-1": "C2"},
    "D1": {"e0-0": "C1", "e0-1": "E2"},
    "D2": {"e0-0": "D3", "e0-1": "E1"},
    "D3": {"e0-0": "C2", "e0-1": "D2"},
    "E1": {"e0-0": "F1", "e0-1": "D2"},
    "E2": {"e0-0": "E3", "e0-1": "D1"},
    "E3": {"e0-0": "F2", "e0-1": "E2"},
    "F1": {"e0-0": "B1", "e0-1": "E1"},
    "F2": {"e0-0": "F3", "e0-1": "E3"},
    "F3": {"e0-0": "B2", "e0-1": "F2"},
    "B1": {"e0-0": "B3", "e0-1": "F1"},
    "B2": {"e0-0": "B3", "e0-1": "F3"},
    "B3": {"e0-0": "B1", "e0-1": "B2"},
}


def run_cmd(ip, cmd):
    try:
        child = pexpect.spawn(f"ssh {SSH_OPTS} admin@{ip}", timeout=15, encoding="utf-8")
        child.expect(r"[Pp]assword")
        child.sendline(PASSWORD)
        child.expect(r"[#>]\s*$", timeout=12)
        child.sendline(cmd)
        child.expect(r"[#>]\s*$", timeout=20)
        output = child.before
        child.sendline("exit")
        child.close()
        return output.strip()
    except pexpect.exceptions.TIMEOUT:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def parse_lldp(output):
    """Return {port: peer_sysname} from 'show lldp neighbours' output."""
    neighbours = {}
    for line in output.splitlines():
        # e.g.: e0-0   aa:bb:cc:dd:ee:ff   nv6-A3-v5-130   TTCMP...
        m = re.match(r"^(e\d+-\d+)\s+[\da-f:]+\s+(\S+)", line, re.I)
        if m:
            neighbours[m.group(1)] = m.group(2)
    return neighbours


def extract_switch_id(sysname):
    """'nv6-A3-v5-130' -> 'A3'"""
    if not sysname:
        return None
    m = re.match(r"nv6-([A-Z]\d+)-", sysname)
    return m.group(1) if m else sysname


print("=" * 70)
print("DOSTO 4734-119 (box1-t47) LLDP Topology Check")
print("=" * 70)

live_data = {}
for switch_id, ip in sorted(SWITCHES.items()):
    if ip is None:
        live_data[switch_id] = {"ip": "OFFLINE", "neighbours": {}, "raw": "NO IP — not in DHCP leases"}
        print(f"\n[{switch_id}@OFFLINE]  *** NOT IN DHCP LEASES — switch unreachable ***")
        continue
    raw = run_cmd(ip, "show lldp neighbours")
    neighbours = parse_lldp(raw)
    live_data[switch_id] = {"ip": ip, "neighbours": neighbours, "raw": raw}

    print(f"\n[{switch_id}@{ip}]")
    for port in sorted(neighbours):
        peer = neighbours[port]
        print(f"  {port} -> {peer}  [{extract_switch_id(peer)}]")
    if not neighbours:
        print(f"  (no neighbours)  raw={raw[:100]!r}")

print("\n" + "=" * 70)
print("TOPOLOGY MISMATCH REPORT  (inter-switch trunk ports e0-0 / e0-1)")
print("=" * 70)

oks, mismatches = [], []

for switch_id, d in sorted(live_data.items()):
    expected = EXPECTED_TOPOLOGY.get(switch_id, {})
    for port in ["e0-0", "e0-1"]:
        live_peer = extract_switch_id(d["neighbours"].get(port))
        expect_peer = expected.get(port)
        label = f"[{switch_id}@{d['ip']}] {port}"
        if live_peer == expect_peer:
            oks.append(f"  OK       {label}  ->  {live_peer}")
        else:
            mismatches.append(
                f"  MISMATCH {label}  live={live_peer or 'NO NEIGHBOUR'}  expected={expect_peer}"
            )

if oks:
    print("\nCorrect links:")
    for l in oks:
        print(l)

if mismatches:
    print("\n*** MISMATCHES — likely cabling errors: ***")
    for l in mismatches:
        print(l)
    sys.exit(1)
else:
    print("\nAll trunk port LLDP neighbours match OBN expected topology. Cabling OK.")

print("\nDone.")
