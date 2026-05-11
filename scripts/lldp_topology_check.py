#!/usr/bin/env python3
"""
DOSTO consist LLDP topology checker.
Pulls 'show lldp neighbours' from every switch, extracts hostname from the CLI
output, then compares e0-0 / e0-1 against OBN template expected topology.
Reports mismatches that explain OBN / auto-topology failure.

Usage:
  Copy to the CCU (/tmp/) and run with python3, or run locally if you have
  pexpect installed and SSH access to the CCU's vlan100 switches.

  Edit SWITCHES to match the live VDS switch IPs on vlan100 (OUI a0:59:3a).
  Edit EXPECTED_TOPOLOGY if the OBN template trunk descriptions differ.

  Reads expected topology from:  /etc/obn/template/nv4-*.cfg  (e0-0 / e0-1 descriptions)
  SSH credentials: admin / Nom@dCome1n  (legacy KEX required)
"""
import pexpect, re, sys

PASSWORD = "Nom@dCome1n"
SSH_OPTS = (
    "-o StrictHostKeyChecking=no -o ConnectTimeout=8 "
    "-o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 "
    "-o HostKeyAlgorithms=+ssh-rsa,ssh-dss "
    "-o PubkeyAuthentication=no"
)

# ── Edit these two variables for each train ───────────────────────────────────

# VDS switch IPs on vlan100 (from: fping -a -q -g <subnet> && ip neigh | grep a0:59:3a)
SWITCHES = [
    "10.179.4.179", "10.179.4.180", "10.179.4.181",
    "10.179.4.190", "10.179.4.191", "10.179.4.192",
    "10.179.4.193", "10.179.4.194", "10.179.4.195",
    "10.179.4.196", "10.179.4.197", "10.179.4.198",
]

# Expected inter-switch trunk topology from OBN templates (/etc/obn/template/nv4-*.cfg).
# Derived from the 'description' field on e0-0 and e0-1 of each template.
# Car-number mapping for this 4-car consist: 100=A, 300=G, 400=E, 600=B.
# For a 6-car consist add C and D cars per the template description mapping.
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
    """Return (hostname, {port: peer_sysname}) from 'show lldp neighbours' output."""
    neighbours = {}
    hostname = None
    for line in output.splitlines():
        # Neighbour line: "e0-0   aa:bb:cc:dd:ee:ff   nv4-A3-v4-001   TTCMP..."
        m = re.match(r"^(e\d+-\d+)\s+[\da-f:]+\s+(\S+)", line, re.I)
        if m:
            neighbours[m.group(1)] = m.group(2)
        # Own hostname appears at end of output as CLI prompt: "A@nv4-A1-v4-001"
        m2 = re.search(r"@(nv4-[A-Z]\d+-\S+)", line)
        if m2:
            hostname = m2.group(1)
    return hostname, neighbours

def extract_switch_id(sysname):
    """'nv4-A3-v4-001' -> 'A3'"""
    if not sysname:
        return None
    m = re.match(r"nv4-([A-Z]\d+)-", sysname)
    return m.group(1) if m else sysname

# ── Collect live LLDP data ────────────────────────────────────────────────────
print("=" * 70)
print("DOSTO LLDP Topology Check")
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

# ── Compare against expected topology ────────────────────────────────────────
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
        live_peer    = extract_switch_id(d["neighbours"].get(port))
        expect_peer  = expected.get(port)
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
