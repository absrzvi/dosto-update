#!/usr/bin/env python3
"""
LLDP topology checker for 4734-120 (Fzg. 20, 4-car DOSTO NEU, CCU box1-t49).
Coach mapping: 100=A, 300=G, 400=E, 600=B.
Derived from OBN templates at /etc/obn/template/nv4-*.cfg on box1-t49 (2026-05-20).

Run on the CCU:  python3 /tmp/lldp_check_4734-120.py
"""
import pexpect, re, sys

PASSWORD = "Nom@dCome1n"
SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)

# Live IPs from sudo dhcp-lease-list on box1-t49 (2026-05-20)
SWITCHES = {
    "A1": "10.179.49.186",
    "A2": "10.179.49.187",
    "A3": "10.179.49.188",
    "G1": "10.179.49.184",
    "G2": "10.179.49.179",
    "G3": "10.179.49.180",
    "E1": "10.179.49.185",
    "E2": "10.179.49.182",
    "E3": "10.179.49.189",
    "B1": "10.179.49.183",
    "B2": "10.179.49.181",
    "B3": "10.179.49.178",
}

# Expected from generic 4-car ABEG topology (scripts/lldp_topology_check.py).
EXPECTED_TOPOLOGY = {
    "A1": {"e0-0": "A3", "e0-1": "G1"},
    "A2": {"e0-0": "A3", "e0-1": "G3"},
    "A3": {"e0-0": "A1", "e0-1": "A2"},
    "G1": {"e0-0": "A1", "e0-1": "E2"},
    "G2": {"e0-0": "G3", "e0-1": "E1"},
    "G3": {"e0-0": "A2", "e0-1": "G2"},
    "E1": {"e0-0": "B1", "e0-1": "G2"},
    "E2": {"e0-0": "E3", "e0-1": "G1"},
    "E3": {"e0-0": "B2", "e0-1": "E2"},
    "B1": {"e0-0": "B3", "e0-1": "E1"},
    "B2": {"e0-0": "B3", "e0-1": "E3"},
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
    neighbours = {}
    for line in output.splitlines():
        m = re.match(r"^(e\d+-\d+)\s+[\da-f:]+\s+(\S+)", line, re.I)
        if m:
            neighbours[m.group(1)] = m.group(2)
    return neighbours


def extract_switch_id(sysname):
    if not sysname:
        return None
    m = re.match(r"nv4-([A-Z]\d+)-", sysname)
    return m.group(1) if m else sysname


print("=" * 70)
print("DOSTO 4734-120 (Fzg 20, box1-t49) LLDP Topology Check")
print("=" * 70)

live_data = {}
for switch_id, ip in sorted(SWITCHES.items()):
    raw = run_cmd(ip, "show lldp neighbours")
    neighbours = parse_lldp(raw)
    live_data[switch_id] = {"ip": ip, "neighbours": neighbours, "raw": raw}
    print(f"\n[{switch_id}@{ip}]")
    for port in sorted(neighbours):
        peer = neighbours[port]
        print(f"  {port} -> {peer}  [{extract_switch_id(peer)}]")
    if not neighbours:
        print(f"  (no neighbours)  raw={raw[:120]!r}")

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
    print("\nAll trunk port LLDP neighbours match expected topology. Cabling OK.")
print("\nDone.")
