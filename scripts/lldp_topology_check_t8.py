#!/usr/bin/env python3
"""
DOSTO consist LLDP topology checker — train 4736-108 (CCU box1-t8, 10.179.8.1)
6-car consist: cars 100=A, 200=C, 300=D, 400=E, 500=F, 600=B
OBN template: nv6-*  train_id=136 (= 128 + 8)
"""
import pexpect, re, sys

PASSWORD = "Nom@dCome1n"
SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)

SWITCHES = [
    "10.179.8.178", "10.179.8.179", "10.179.8.180",
    "10.179.8.181", "10.179.8.182", "10.179.8.183",
    "10.179.8.184", "10.179.8.185", "10.179.8.186",
    "10.179.8.187", "10.179.8.188", "10.179.8.189",
    "10.179.8.190", "10.179.8.191", "10.179.8.192",
    "10.179.8.193", "10.179.8.194", "10.179.8.195",
]

# Derived from nv6-* OBN template descriptions on e0-0 / e0-1
# 6-car chain: A <-> C <-> D <-> E <-> F <-> B
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

# ─────────────────────────────────────────────────────────────────────────────

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
    hostname = None
    for line in output.splitlines():
        m = re.match(r"^(e\d+-\d+)\s+[\da-f:]+\s+(\S+)", line, re.I)
        if m:
            neighbours[m.group(1)] = m.group(2)
        m2 = re.search(r"@(nv6-[A-Z]\d+-\S+)", line)
        if m2:
            hostname = m2.group(1)
    return hostname, neighbours

def extract_switch_id(sysname):
    if not sysname:
        return None
    m = re.match(r"nv6-([A-Z]\d+)-", sysname)
    return m.group(1) if m else sysname

print("=" * 70)
print("DOSTO LLDP Topology Check — 4736-108 (box1-t8)")
print("=" * 70)

live_data = {}
for ip in SWITCHES:
    raw = run_cmd(ip, "show lldp neighbours")
    hostname, neighbours = parse_lldp(raw)
    switch_id = extract_switch_id(hostname) if hostname else None
    live_data[ip] = {"hostname": hostname or ip, "switch_id": switch_id, "neighbours": neighbours}

    label = f"[{ip}]  {hostname or 'UNREACHABLE'}  (id={switch_id})"
    print(f"\n{label}")
    for port in sorted(neighbours):
        peer = neighbours[port]
        print(f"  {port} -> {peer}  [{extract_switch_id(peer)}]")
    if not neighbours:
        print(f"  (no neighbours)  raw={raw[:80]!r}")

print("\n" + "=" * 70)
print("TOPOLOGY MISMATCH REPORT  (inter-switch trunk ports e0-0 / e0-1)")
print("=" * 70)

oks, mismatches, unknowns = [], [], []

for ip, d in live_data.items():
    my_id = d["switch_id"]
    expected = EXPECTED_TOPOLOGY.get(my_id)
    if expected is None:
        unknowns.append(
            f"  UNKNOWN  {d['hostname']}@{ip}  — switch id '{my_id}' not in topology table"
        )
        continue
    for port in ["e0-0", "e0-1"]:
        live_peer   = extract_switch_id(d["neighbours"].get(port))
        expect_peer = expected.get(port)
        label = f"[{my_id}@{ip}] {port}"
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

if unknowns:
    print("\nUnmapped / unidentified switches (OBN config not loaded yet, or duplicate hostname):")
    for l in unknowns:
        print(l)

if mismatches:
    print("\n*** MISMATCHES — likely cabling errors causing OBN/auto-topology failure: ***")
    for l in mismatches:
        print(l)
    sys.exit(1)
elif not unknowns:
    print("\nAll trunk port LLDP neighbours match OBN expected topology. Cabling OK.")

print("\nDone.")
