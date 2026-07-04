# DOSTO Troubleshooting Runbook

Operational procedures for troubleshooting and reconfiguring DOSTO trainset onboard systems. Each section is a self-contained procedure — copy/paste-friendly.

## Contents

- [LLDP Cabling / Topology Check](#lldp-cabling--topology-check-obn--auto-topology-failure)
- [OBN Bugs 1–7 — Known Crashes and Fixes](#obn-firmware--config-update--known-bugs-and-fixes-gitlab-rd)
  - [How to apply all fixes](#how-to-apply-fixes-on-a-ccu-manually-until-gitlab-release)
- [CCU Firewall — TFTP conntrack helper missing (silent batch firmware failures)](#ccu-firewall--tftp-conntrack-helper-missing-silent-batch-firmware-failures)
- [OBN train_id — Verify and Fix Before Any Config Push](#obn-train_id--verify-and-fix-before-any-config-push)
- [NMS & Zabbix Operations](#nms--zabbix-operations) — hosts, both auth paths, switch template (10723), SNMP creds, host-IP/DHCP behaviour, factory-AP recovery
- [NMS Train-Type Config: consist diagram via the API](#nms-train-type-config-creatingupdating-a-consist-diagram-via-the-api)

---

## LLDP Cabling / Topology Check (OBN & Auto-Topology Failure)

If OBN fails to push configs or auto-topology doesn't converge, the first thing to verify is that Stadler have cabled the inter-switch trunks correctly. Each switch's e0-0 and e0-1 must connect to exactly the neighbours specified in the OBN templates — any mismatch causes OBN and auto-topology to fail silently.

### What the check does

- SSHs into every VDS switch on vlan100
- Runs `show lldp neighbours` on each
- Compares the live e0-0 / e0-1 LLDP peer against the expected neighbour from the OBN template descriptions
- Reports MISMATCH for any port where the cable doesn't match what OBN expects

### Prerequisites

- `pexpect` must be available on the CCU (`python3 -c 'import pexpect'` to verify — it was present on box1-t4)
- `sshpass` is NOT required (pexpect handles the password prompt)

### Prepare the expected topology table

Read the OBN templates on the CCU to get the trunk descriptions:

```bash
for f in /etc/obn/template/nv4-*.cfg; do
    echo "=== $f ==="
    grep -A1 'interface e0-[01]' "$f" | grep description
done
```

Map the description labels to real switch IDs for this consist's car count:

| Template label | 6-car | 4-car (100/300/400/600) |
|---|---|---|
| Switch A1/A2/A3 | A1/A2/A3 | A1/A2/A3 |
| Switch C1/C2/C3 | C1/C2/C3 | G1/G2/G3 |
| Switch D1/D2/D3 | D1/D2/D3 | G1/G2/G3 (middle) |
| Switch E1/E2/E3 | E1/E2/E3 | E1/E2/E3 |
| Switch F1/F2/F3 | F1/F2/F3 | B1/B2/B3 |
| Switch B1/B2/B3 | B1/B2/B3 | B1/B2/B3 |

### Run the check

Copy `lldp_topology_check.py` from this folder to the CCU and run it:

```bash
scp -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/lldp_topology_check.py" \
    developer@<ccu-ip>:/tmp/

ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
python3 /tmp/lldp_topology_check.py
```

Before running, edit `SWITCHES` and `EXPECTED_TOPOLOGY` at the top of the script to match the live train.

### Reading the output

```
MISMATCH [E2@10.179.4.180] e0-0  live=dosto-000000000  expected=E3
```

- `live=dosto-000000000` — neighbour has a blank/default OBN hostname. The switch exists but hasn't been provisioned yet, OR it's the wrong switch entirely (cable plugged into the wrong port).
- `live=G2  expected=G1` — cable connected to the wrong switch in the same car group.
- `NO NEIGHBOUR` — port is up but no LLDP received; cable missing, wrong port, or far-end switch is down.

### Common findings and actions

| Finding | Likely cause | Action |
|---|---|---|
| `live=dosto-000000000` | Far-end switch has no OBN config (train_id not set) | Set train_id in OBN templates (see OBN train_id section), or cable is wrong |
| Wrong switch neighbour (e.g. G2 instead of G1) | Cable plugged into wrong switch port on the far car | Ask Stadler to re-patch the cable |
| Duplicate hostname (two switches report same ID) | OBN train_id mismatch — two switches got the same config | Check `/etc/obn/template/` train_id line and re-push OBN |
| Switch unreachable (TIMEOUT) | Switch not powered, or not on vlan100 | Check fping sweep and ARP table |

---

## OBN Firmware & Config Update — Known Bugs and Fixes (GitLab R&D)

These bugs were discovered on 2026-05-04 while running `obn update f all` on train 1 (CCU `10.179.1.1`) and `obn update c all` on 4736-120 (CCU `10.179.2.1`). All have been patched in-place on the affected CCUs. **They must be fixed in the OBN GitLab repository and released** so every CCU gets them on next deployment.

**Always apply all 7 bugs together** — applying only some leaves crash modes open and can cause partial-update states that cause RSTP topology storms. Use `fix_obn.py` (idempotent, applies all 7).

### Bug 1 — `vdsrail.py`: Regex mismatch silently prevents firmware from being set as boot default

**File:** `/usr/share/obn/lib/device/vendor/vdsrail.py`, `set_firmware_version()` ~line 80

**Symptom:** Switches download the firmware via TFTP and reboot, but always come back on the old version. No error is logged — `obn update f all` reports success.

**Root cause:** The code matches the SNMP task status OID with:
```python
matchstr = r"Not running. System Firmware image loaded \[(.*)\]"
```
But the actual switch response during a firmware flash is:
```
"Not running. System Firmware default image is now sw-std-ng_7.4.2-77411.ksi"
```
The regex never matches → `set_firmware_set_default` OID is never called → switch boots back into old image bank.

Note: after the set-default OID has been applied, the status OID returns the old `"image loaded [X]"` format. Both formats need to be handled.

**Fix:**
```python
# Before:
matchstr = r"Not running. System Firmware image loaded \[(.*)\]"
# After:
matchstr = r"Not running. System Firmware (?:default image is now|image loaded \[)(.*?)\]?"
```

---

### Bug 2 — `vdsrail.py`: `re.search()` crash when SNMP returns None during switch reboot

**File:** `/usr/share/obn/lib/device/vendor/vdsrail.py`, `set_firmware_version()` ~line 76 and `set_configuration_version()` ~line 114

**Symptom:** `TypeError: expected string or bytes-like object, got 'NoneType'` crashes the whole `obn update f all` process mid-run, leaving remaining devices unupdated.

**Root cause:** When a switch is rebooting, SNMP gets return `None`. The polling loop calls `re.search("Not running", result)` without guarding against `None`.

**Fix:** Add a None guard in both polling loops:
```python
result = self._snmp_get(self.device_config["snmp_firmware_task_running_oid"])
if not result:   # ← add this
    continue     # ← add this
search = re.search("Not running", result)
```
Same fix needed in `set_configuration_version()` for the config task polling loop.

---

### Bug 3 — `snmpdevice.py`: pysnmp `KeyError` crash propagates out of thread pool

**File:** `/usr/share/obn/lib/device/snmpdevice.py`, `_snmp_parse_results()` ~line 286

**Symptom:** `KeyError: 'errorIndication'` in pysnmp's asyncore internals propagates through `concurrent.futures` and crashes the whole update process.

**Root cause:** When a switch reboots mid-SNMP-session, pysnmp's asyncore internal context dict loses `'errorIndication'`. This unhandled exception kills the thread and bubbles up.

**Fix:**
```python
# Before:
for error_indication, error_status, _, var_binds in generator:

# After:
try:
    gen_items = list(generator)
except KeyError:
    return {}
for error_indication, error_status, _, var_binds in gen_items:
```

---

### Bug 4 — `device.py`: `AttributeError` crash when device has no firmware reading

**File:** `/usr/share/obn/lib/report/device.py`, `needs_firmware_update()` ~line 65

**Symptom:** `AttributeError: 'NoneType' object has no attribute 'endswith'` crashes `obn update f all` immediately if any device in discovery has `firmware: None` (e.g. AP that is rebooting or has SNMP auth issues).

**Fix:**
```python
# Before:
return not self.firmware.endswith(self.target["firmware"])
# After:
return bool(self.firmware) and not self.firmware.endswith(self.target["firmware"])
```

---

### Bug 5 — `update.py`: `tftp_allowed` ipset not pre-populated, TFTP blocked on mid-run restart

**File:** `/usr/share/obn/cli/update.py`, `update()` function

**Symptom:** If `obn update f all` crashes mid-run and is restarted, any devices not yet reached in the first run cannot fetch firmware — their TFTP requests are silently dropped by iptables. The switch gets `"Connection trouble or invalid URL"` and the update silently fails.

**Root cause:** OBN adds device IPs to the `tftp_allowed` ipset incrementally as it processes each device. If the run crashes before reaching a device, it is never added to the ipset. On restart, those devices are still absent from the ipset.

**Fix:** Populate the full ipset for all target devices **before** starting the first batch:
```python
# After "logger.info("calculated the update order")", add:
import subprocess as _sp
for _dev in update_set.firmware_updates:
    _sp.run(["ipset", "add", "tftp_allowed", _dev.ip, "-exist"],
            capture_output=True)
```

---

### Bug 6 — `tree.py`: `AttributeError` crash when a coupled consist's switches appear as LLDP neighbours

**File:** `/usr/share/obn/lib/tree.py`, `OBNTree.create_tree()` ~line 34

**Symptom:** `obn update c <ip>` or `obn update c all` crashes immediately after `[+] creating TFTP firmware folder` with:
```
AttributeError: 'NoneType' object has no attribute 'type'
```
Full traceback ends at:
```
File "/usr/share/obn/lib/tree.py", line 34, in create_tree
    if neighbour_device.type == "BOX":
AttributeError: 'NoneType' object has no attribute 'type'
```

**Root cause:** When a second consist is coupled (e.g. front-coupler trunks are live), the end-car switches (B1, B3 on a 6-car) learn LLDP entries for the neighbour consist's switches. Those switches are on a different subnet (e.g. `10.179.11.x`) and are not part of the local `discovery.json`. The tree builder does:
```python
neighbour_device = next((x for x in devices if x.mac == neighbour["mac"]), None)
if neighbour_device.type == "BOX":   # ← crashes if neighbour_device is None
```
`next(..., None)` returns `None` for any neighbour MAC not in the local device list, and the immediate `.type` access crashes.

You can confirm this is your situation by checking `obn validate` for the warning:
```
⚠ test_unnumbered_devices: couldn't assign coach number to 10.179.11.x, 10.179.11.y
```
Those IPs belong to the coupled consist's switches — they show up in B1/B3's neighbour list via LLDP over e0-2 (front coupler port).

**Fix:** Add a `None` guard before accessing `.type`:
```python
# Before (line 34):
if neighbour_device.type == "BOX":
    continue

# After:
if neighbour_device is None:
    continue  # neighbour not in this consist (e.g. coupled train on another subnet)
if neighbour_device.type == "BOX":
    continue
```

**In-place fix on CCU:**
```bash
sudo btrfs property set / ro false
sudo python3 -c "
path = '/usr/share/obn/lib/tree.py'
with open(path) as f:
    content = f.read()
old = '''                if neighbour_device.type == \"BOX\":
                    continue
                if neighbour_device.mac not in tree:'''
new = '''                if neighbour_device is None:
                    continue  # neighbour not in this consist (e.g. coupled train on another subnet)
                if neighbour_device.type == \"BOX\":
                    continue
                if neighbour_device.mac not in tree:'''
assert old in content, 'pattern not found - check line numbers'
content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print('PATCHED OK')
"
sudo btrfs property set / ro true
```

**Affected trains:** Any consist coupled to a second unit at time of `obn update c`. The bug is latent on every CCU — it only triggers when front-coupler LLDP neighbours from another subnet appear in the discovery data.

**R&D report fields:**
- Reported: 2026-05-04, 4736-120 (CCU `10.179.2.1`)
- Triggering condition: `obn update c all` while coupled to second consist (B1 `.182` had LLDP peer `10.179.11.195`, B3 `.188` had `10.179.11.183`)
- Patch status: Applied in-place on `10.179.2.1`; needs GitLab fix + release

---

### Bug 7 — `vdsrail.py`: `reboot()` crashes when SNMP-get hostname returns None mid-reboot window

**File:** `/usr/share/obn/lib/device/vendor/vdsrail.py`, `reboot()` ~line 122

**Symptom:** During `obn update c all`, after several switches in a batch have just received their config push and are starting to reboot, the whole `obn update` process crashes with:
```
TypeError: cannot convert 'NoneType' object to bytes
```
Full traceback ends at:
```
File "/usr/share/obn/lib/device/vendor/vdsrail.py", line 124, in reboot
    self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
File "/usr/share/obn/venv/lib/python3.11/site-packages/pyasn1/type/univ.py", line 886, in prettyIn
    return bytes(value)
TypeError: cannot convert 'NoneType' object to bytes
```

**Root cause:** The `reboot()` method calls `_snmp_get` to read the current hostname, then immediately `_snmp_set`s it back. If the switch has already started rebooting by the time the get runs, SNMP returns `None`. The subsequent `_snmp_set({oid: None})` crashes pyasn1. Same root cause family as Bugs 2/3/4.

**Fix:** Skip the hostname round-trip if the SNMP-get returned None:
```python
def reboot(self) -> bool:
    hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])
    if hostname is not None:
        self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
    self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})
    return True
```

**In-place fix on CCU:**
```bash
sudo btrfs property set / ro false
sudo python3 -c "
path = '/usr/share/obn/lib/device/vendor/vdsrail.py'
with open(path) as f:
    content = f.read()
old = '''    def reboot(self) -> bool:
        hostname = self._snmp_get(self.device_config[\"snmp_get_hostname_oid\"])
        self._snmp_set({self.device_config[\"snmp_set_hostname_oid\"]: hostname})
        self._snmp_set({self.device_config[\"snmp_reboot_oid\"]: 3})'''
new = '''    def reboot(self) -> bool:
        hostname = self._snmp_get(self.device_config[\"snmp_get_hostname_oid\"])
        if hostname is not None:
            self._snmp_set({self.device_config[\"snmp_set_hostname_oid\"]: hostname})
        self._snmp_set({self.device_config[\"snmp_reboot_oid\"]: 3})'''
assert old in content, 'pattern not found'
content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print('PATCHED OK')
"
sudo btrfs property set / ro true
```

**R&D report fields:**
- Reported: 2026-05-04, 4736-120 (CCU `10.179.2.1`)
- Triggering condition: `obn update c all` second batch — A1/A2/A3/B1/B2/B3 batch crashed when one switch's SNMP timed out during reboot
- Patch status: To be applied in-place on `10.179.2.1` after current reboot completes; needs GitLab fix + release
- Related: same root cause family as Bug 2. A unified `_snmp_get_with_retry()` helper that returns a sentinel on failure would eliminate this entire bug class.

---

### How to apply fixes on a CCU manually (until GitLab release)

**ALWAYS apply all of Bugs 1–7 together at the start of any OBN troubleshooting session on any CCU.** They are interdependent — applying only some leaves crash modes open. Partial updates cause mixed RSTP/VLAN configs across switches in the same consist, which causes topology storms. The script `scripts/fix_obn.py` (relative to this repo's project root) is idempotent, applies all 7 in order, and reports which were already applied.

```bash
# 0. From your local machine, copy fix_obn.py to the CCU:
scp -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/fix_obn.py" \
    developer@<ccu-ip>:/tmp/

# 1. SSH to the CCU and make root writable
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
sudo btrfs property set / ro false

# 2. Apply all 7 fixes (idempotent)
sudo python3 /tmp/fix_obn.py

# 3. Re-lock root
sudo btrfs property set / ro true

# 4. Run updates
sudo obn discover
sudo obn update f all   # firmware first
# wait for FIRMWARE_DONE in /data/obn_update_f.log
sudo obn discover
sudo obn update c all   # then config
```

---

## CCU Firewall — TFTP conntrack helper missing (silent batch firmware failures)

**This is NOT an OBN bug. It's a CCU firewall config gap.** Discovered 2026-05-09 on box1-t10 (Fzg 132). Should be fixed in the Puppet-managed source of `/etc/21net-security.d/60-allow-management` — separate ticket from the OBN bugs.

### Symptom

`obn update f ap` (batch firmware push to multiple APs in parallel) consistently leaves most APs on the old firmware. OBN reports "firmware update applied, device rebooting" for every target. `in.tftpd` logs RRQ from each AP. `/var/log/obn/*.log` shows no errors. But ~30 minutes later, half or more of the APs are still on the old version. A subsequent push to one of the failed APs as a *single* target usually succeeds.

### Root cause

The CCU's iptables `MGMTI` chain (built on boot by `/etc/21net-security.d/60-allow-management`) has this rule for inbound TFTP:

```
$IPT -A MGMTI -p udp -m set --match-set tftp_allowed src -m udp --dport 69 -m comment --comment "tftp" -j ACCEPT
```

This allows the **first packet** of a TFTP transfer (AP's RRQ → CCU port 69). Once `in.tftpd` accepts it, the daemon opens an **ephemeral source port** and sends DATA from `CCU:<random>` → `AP:<random>`. The AP replies with ACK from `AP:<random>` → `CCU:<random>`.

For the ACK to be accepted, the kernel needs to recognise it as RELATED to the original RRQ flow — and that requires the `nf_conntrack_tftp` helper module loaded AND an explicit CT helper rule on the RRQ port. The CCU image as shipped has neither.

Without the helper, conntrack treats the data flow as a brand-new connection. It doesn't match `state RELATED,ESTABLISHED` (line 2 of INPUT) and falls through to `INPUT policy DROP`. The data transfer never completes.

A *single* AP push (`obn update f <single-IP>`) sometimes succeeds anyway because conntrack's UDP timeout heuristics can occasionally reuse the RRQ flow entry for the data port. With 15 simultaneous transfers, those heuristics fail almost every time.

### How to verify the bug is present

```bash
# 1. Module not loaded
lsmod | grep -E "nf_conntrack_tftp"   # empty = bug present

# 2. No CT helper rule
sudo iptables -t raw -L PREROUTING -n -v | grep "helper tftp"   # empty = bug present

# 3. After a batch firmware push, INPUT chain match-set tftp_allowed shows only RRQ-sized traffic
sudo iptables -L INPUT -n -v | grep tftp_allowed
#   Expected if working: hundreds of MB (firmware transfers)
#   Actual if broken:    a few KB (just RRQs)
```

Or look for the smoking gun in the journal: lots of `RRQ from <AP-IP>` lines clustered, then ~30 minutes of silence, then `tftpd: read(ack): Connection refused` for each — meaning every transfer eventually timed out without ever ack'ing.

### Runtime fix (survives until reboot)

```bash
# Load the helper module
sudo modprobe nf_conntrack_tftp

# Attach the helper to udp/69 traffic via the raw table
sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
```

This wires up the helper to recognise TFTP RRQ packets and pre-create RELATED conntrack entries for the upcoming data flow. Subsequent batch pushes work reliably.

Verify the rule is matching:
```bash
sudo iptables -t raw -L PREROUTING -n -v
#  Look for non-zero pkts/bytes on the line containing "udp dpt:69 CT helper tftp"
```

### Persistent fix (survives reboot)

Add the two commands to `/etc/21net-security.d/60-allow-management` (Puppet-managed file). Insert near the top alongside the `IPS create tftp_allowed` line and the `IPT -A MGMTI ... tftp_allowed` rule:

```bash
# Load the conntrack TFTP helper (needed for in.tftpd to serve return data flows)
modprobe nf_conntrack_tftp 2>/dev/null

# Attach the helper to incoming TFTP RRQ packets
$IPT -t raw -A PREROUTING -p udp --dport 69 -j CT --helper tftp -m comment --comment "TFTP conntrack helper for in.tftpd"
```

**This change must land in the Puppet repo, not as a hand-edit on the live CCU** — otherwise it gets wiped on next btrfs promote (same persistence pattern as our 10 OBN patches).

If you must persist on a single CCU before R&D ships the Puppet fix, do it inside `nd-systemupdate.sh.dont shell` (chroot) — same procedure as for OBN patches.

### Why it hasn't been caught before

- One-AP-at-a-time pushes worked enough of the time that engineers didn't escalate.
- OBN's `extreme.py` `set_firmware_version` only checks for "Successful" being PRESENT in the SSH output — the AP replies "Successful" as soon as the TFTP request is initiated, not when the data has fully transferred. So OBN reports success even when the actual firmware transfer never completes.
- `/var/log/obn/*.log` doesn't capture in.tftpd state, so you have to read the system journal separately to see the real story.

### Validated against

- 2026-05-09 on box1-t10 (Fzg 132). Initial 15-AP parallel push: 5 of 15 actually flashed (lucky conntrack races). Loaded helper + added CT rule: subsequent batch-of-3 succeeded reliably.

---

## OBN train_id — Verify and Fix Before Any Config Push

**Always do this before `obn update c all`.** Getting `train_id` wrong causes every switch to get a silently incorrect hostname (e.g. `nv6-A1-v8-129` instead of `nv6-A1-v8-133`). The push reports success, but you'll need a full re-run to correct it.

The OBN switch config templates render the hostname as:
```
nv6-X1-v8-{{ "%03d" | format(train_id) }}
```
So `train_id` in `/etc/obn/backbone-discovery.yaml` must equal the **Fzg ID** of the consist (from the IP allocation file — e.g. `4736-133` → `train_id: 133`).

### Watch out: the broken `128 + train_id` formula

Some templates from older OBN releases have:
```jinja
{%- set train_id = 128 + train_id -%}
```
This was a band-aid that's no longer correct. **Remove it.** The correct first line of every `nv6-*.cfg` template is:
```jinja
{%- set train_id = train_id -%}
```
(or just remove the line entirely — Jinja will pass `train_id` through from `backbone-discovery.yaml`)

### How to check

```bash
# 1. Get the Fzg ID from the IP allocation file (the number in the
#    train-ip-allocation-commission folder name).

# 2. Check what train_id OBN has configured.
grep train_id /etc/obn/backbone-discovery.yaml
# Expected: train_id = <Fzg ID>

# 3. Confirm the template doesn't have the broken "128 + train_id" formula.
head -2 /etc/obn/template/nv6-100-A1.cfg
# CORRECT:  {%- set train_id = train_id -%}
# BROKEN:   {%- set train_id = 128 + train_id -%}
```

### How to fix

```bash
sudo btrfs property set / ro false

# Set train_id to the Fzg ID
sudo sed -i "s/^train_id: .*/train_id: <FZG_ID>/" /etc/obn/backbone-discovery.yaml

# Remove the broken "128 + train_id" line from every nv6 template
for f in /etc/obn/template/nv6-*.cfg; do
    sudo sed -i '1s|{%- set train_id = 128 + train_id -%}|{%- set train_id = train_id -%}|' "$f"
done

# Re-lock root
sudo btrfs property set / ro true

# Clear stale rendered configs so they get regenerated
sudo rm -f /data/auto-topology/upload/nv6-*.cfg

# Verify
grep train_id /etc/obn/backbone-discovery.yaml
head -2 /etc/obn/template/nv6-100-A1.cfg
```

### For nv4 templates (changing to a temporary train number)

If you need to re-point `nv4-*` templates at a different train number (e.g. during commissioning when a consist is temporarily operating as a different Fzg ID):

```bash
sudo btrfs property set / ro false
cd /etc/obn/template

for f in nv4-*; do
    # Remove any existing train_id override on line 1
    sed -i '1{/^{%- set train_id = .*-%}$/d}' "$f"
    # Insert the new one at the top — replace FISID with the target number
    sed -i '1i {%- set train_id = FISID -%}' "$f"
done

# Verify
head -2 nv4-100-A1.cfg

sudo btrfs property set / ro true
```

---

## Westermo AP Config Push — Manual Method (When OBN SNMP Fails)

**When to use this:** `obn update c <ip>` silently fails on APs in factory config (`RT610LV-...-v1-FD`). The factory config's SNMP community is `admin-community` (not `NomadStayOut!`) and appears to restrict access by source IP — the CCU's SNMP sets never reach the AP even though ICMP works. OBN prints "configuration update applied, device rebooting" regardless (it doesn't check the return value of `set_configuration_version()` before printing success).

**Confirmed on:** 4734-120 (CCU `10.179.49.1`), 2026-05-05. All 16 APs were in factory config after commissioning.

### Root cause

The Westermo RT610LV factory config (`RT610LV-...-v1-FD`) has:
- SNMP community `admin-community` (OBN tries `NomadStayOut!` → all queries time out)
- HTTPS/LuCI web UI on port 443 — accessible from the CCU via the bond0 path
- Admin password: `Nom@dCome1n` (same as switch admin password)

The LuCI web UI supports config import and uses a two-step "candidate config" flow:
1. POST config file to `/cgi-bin/luci/admin/system/flashops` → config is staged as pending
2. POST `{"key":"rpcCfgApply","value":1}` to `/cgi-bin/luci/admin/rpc` → config is applied and AP reboots

### Step 1 — Render AP config files (if not already done)

OBN renders per-AP config files during `obn update c` attempts. Check first:

```bash
ls /data/auto-topology/upload/dostoneu-obn-*.cfg | wc -l
# Should be 16 (one per AP)
```

If any are missing, trigger rendering by running (it will fail at SNMP but still renders):
```bash
sudo obn discover && sudo obn update c all
```

### Step 2 — Get the IP→MAC mapping

```bash
ip neigh show | grep '00:14:5a' | sort -t. -k4 -n
```

This gives you the IP and MAC for each AP. The rendered config filename uses the MAC without colons, lowercase: `dostoneu-obn-<macslug>.cfg`.

### Step 3 — Upload config via LuCI (one AP at a time, or batch)

```bash
PASS="Nom%40dCome1n"
IP="10.179.49.94"
MAC="00145a04b350"   # MAC without colons, lowercase
CFG="/data/auto-topology/upload/dostoneu-obn-${MAC}.cfg"
COOK="/tmp/ck_${IP}.txt"

# 1. Login
rm -f $COOK
curl -s -k -c $COOK -b $COOK \
  -X POST "https://${IP}/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=${PASS}" \
  -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 12
# Expected: 302

# 2. Upload config (stages it as pending)
curl -s -k -c $COOK -b $COOK \
  -X POST "https://${IP}/cgi-bin/luci/admin/system/flashops" \
  -F "config=@${CFG};type=text/plain" \
  -F "Import=Import Configuration" \
  -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 25
# Expected: 200

# 3. Apply pending config (triggers reboot ~60-90s)
curl -s -k -c $COOK -b $COOK \
  -X POST "https://${IP}/cgi-bin/luci/admin/rpc" \
  -H 'Content-Type: application/json' \
  -d '{"key":"rpcCfgApply","value":1}' \
  -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 12
# Expected: 200

rm -f $COOK
```

### Step 4 — Batch all APs

Use the scripts in the project root:
- `scripts/push_ap_config.sh <ip> <mac_slug>` — single AP upload + apply
- `scripts/push_remaining_aps.sh` — push to all 14 remaining APs (update the IP/MAC list first)
- `scripts/apply_ap_configs.sh` — run after upload to call rpcCfgApply on any AP still showing "Config Alert"

### Step 5 — Verify config was applied

After the AP comes back up (~60-90s), check via LuCI title — it should no longer say `RT610LV-...-v1-FD`:

```bash
PASS="Nom%40dCome1n"
IP="10.179.49.94"
COOK="/tmp/ck_check.txt"
rm -f $COOK
curl -s -k -c $COOK -b $COOK -X POST "https://${IP}/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=${PASS}" -o /dev/null --connect-timeout 8
curl -s -k -c $COOK -b $COOK "https://${IP}/cgi-bin/luci/" 2>/dev/null | grep '<title>'
# Good: <title>AP4-v1-00145a04b04f - LuCI</title>
# Bad:  <title>RT610LV-00145a04b04f-v1-FD - LuCI</title>  (still factory config)
rm -f $COOK
```

Or check SNMP directly (once Nomad config is active, community `NomadStayOut!` will respond):

```bash
cd /usr/share/obn && sudo venv/bin/python3 -c "
from pysnmp.hlapi import *
ip = '10.179.49.94'
for g in getCmd(SnmpEngine(), CommunityData('NomadStayOut!'),
    UdpTransportTarget((ip,161),timeout=3,retries=1), ContextData(),
    ObjectType(ObjectIdentity('.1.3.6.1.4.1.16177.1.400.1.1.1.1.0')), lookupMib=False):
    ei,es,_,vb = g
    print('OK:', str(vb[0][1]) if not (ei or es) else 'FAIL: '+str(ei or es))
    break
"
```

### Step 6 — After all APs have Nomad config, run OBN normally

Once all APs respond to SNMP, OBN can update firmware as normal:

```bash
sudo obn discover
sudo obn validate      # all APs should now show config ✓, firmware ✗ (still needs update)
sudo obn update f all  # push firmware 6.11.2-0 to all APs
# Wait ~150-160s per AP for download + flash + reboot
sudo obn discover
sudo obn validate      # should be all green
```

### Important quirks

- **LuCI import is a two-step flow**: upload stages the config, `rpcCfgApply` commits it. If you only upload and don't call `rpcCfgApply`, the AP shows "Config Alert" in the web UI and the config is never applied — it will be reverted on next reboot.
- **The `rpcCfgApply` call causes an immediate reboot** (~60-90s downtime). The curl will likely return before the reboot completes (HTTP 200 then AP drops).
- **After config apply, the LuCI password changes**: Nomad config sets a hashed admin password (see `admin_password_hash` in the config file) and adds `user nomad / password NomadComeIn` for CLI. The `Nom@dCome1n` web UI password may no longer work — use `nomad`/`NomadComeIn` for SSH CLI instead.
- **OBN's "configuration update applied" message is unreliable**: It prints this regardless of whether the SNMP set actually reached the AP. Do not trust it — always follow up with `obn validate` or a direct SNMP check.
- **Firmware can only be pushed via OBN after config is applied**: OBN's `set_firmware_version()` also uses SNMP, so the Nomad config must be active first.

Spot-check with `head -2 nv4-*.cfg` after running — if a template already had a non-standard `train_id` line the delete step may have missed it, leaving two lines. The topmost wins in Jinja but it's cleaner to fix manually.

### Caveat: btrfs snapshots roll back `/etc/obn/` on every CCU reboot

`train_id` and template fixes need to be re-applied after every reboot until the OBN package itself is rebuilt with the correct Fzg ID baked in. See the spawned task: "Make OBN patches survive CCU reboots" for the long-term fix.

---

## NMS & Zabbix Operations

The DOSTO-NEU monitoring stack has **two** backends with **two different auth paths**, and they're easy to confuse. This section is the operational index; deep per-topic notes live in the memory files referenced inline.

### ⚠️ Get the host right first

The live ÖBB NMS is **`nms-obb.nomadrail.com`** (ONE "o" — "obb"). There is a stale/decoy **`nms-oebb.nomadrail.com`** ("oebb", two letters) that resolves and returns plausible-but-wrong data (only 3 placeholder DOSTO trains). Querying the wrong host produced a chain of false "train not provisioned" conclusions (2026-06-08). **Match the host to the browser URL before concluding any data is "missing."**

### The two auth paths

| Target | Base | Auth | Use for |
|---|---|---|---|
| **NMS API** | `https://nms-obb.nomadrail.com/nms/rest` | POST `/user/authenticate` `{username,password}` → `.token` → send as header `Auth-Token: <token>` (valid 1 week). Use your **own NMS login**, NOT okapi. | trains, train-types, monitoring/alarms, consist config |
| **Zabbix API** | `https://trainzabbix-obb-alpin.nomadrail.com/api_jsonrpc.php` | JSON-RPC `user.login` `{username:okapi, password:<from train-type zabbixConfiguration>}` → token in `auth`. (okapi creds are inside the NMS train-type config's `zabbixConfiguration` block.) | hosts, items, triggers, LLD rules, templates, problems |

Run NMS calls from the CCU (`developer@10.179.X.1`) if your laptop can't reach NMS. Zabbix API is reachable from the CCU too. Swagger: `docs/swagger_all.yaml`. **Note:** the NMS `GET /train/{relativeId}` endpoint 500s even for valid trains — use `GET /train/project/{id}` (the project-scoped list) instead.

### SNMP credential model (load-bearing — getting this wrong = fleet SNMP outage)

`NomadStayOut!` is the **SNMP** passphrase; `NomadComeIn` is the **SSH/LuCI GUI** password and must **never** appear in an SNMP field. Creds are **inverted** by device type:

| Device | SNMP user | auth/priv |
|---|---|---|
| **VDS switch** | `snmpadmin` | SNMPv3, SHA1 auth + AES128 priv, authPriv, passphrase `NomadStayOut!` (both) |
| **Westermo AP** | `admin` | same SHA1/AES128/authPriv/`NomadStayOut!` |

In the NMS train-type `dynamicConsistConfig.deviceConfigurations`, the Zabbix-6 enum is `authProtocol: 1=SHA1` and `privProtocol: 1=AES128` (NOT 2 — 2 is SHA224). After correcting host creds, switches need `systemctl restart zabbix-proxy` on the CCU (not just `config_cache_reload`) to clear stale failed-auth backoff — or let the power-cycle do it. Full history: [`project_nms_zabbix_snmp_cred_model`], [`feedback_zabbix_proxy_restart_for_stuck_snmp`].

### Switch port monitoring — `Template VDS Switch - DOSTO NEU` (Zabbix template id 10723)

ALL ~700 DOSTO-NEU switch hosts (every train type) link this **one shared template**, so template edits inherit fleet-wide automatically (each train's per-port items materialise on its own hourly LLD run, or force it with execute-now per host — `task.create [{type:6, request:{itemid:<lld-ruleid>}}]`).

The template had two bug classes, both fixed 2026-06-08 ([`project_zabbix_switch_template_wrong_oids`]):
- **Wrong OIDs / dead static items.** Static `snmp.statusoper.portN` items polled bogus ifIndex `1000001+`; firmware/software items used wrong enterprise OIDs (`31988`/`30036`). Device's real enterprise is **33658** (firmware = `.1.3.6.1.4.1.33658.1.10.2.0` → `7.4.2`). These 29 static items are now **disabled**; port monitoring comes from the LLD instead.
- **Broken LLD filter.** The correct rule `ifDescrv3` (`discovery[{#SNMPVALUE},IF-MIB::ifDescr]`) had its filter keyed on `{#IFDESCR}` (undefined) → discovered nothing. **Fixed to `{#SNMPVALUE}` matches `^e[0-9]`**, with exclusions `NOT ^e0-2$` (coupler) and `NOT ^e0-5$` (service port). Discovers all real `eN-M` ports; `ifOperStatus[{#SNMPVALUE}]` auto-uses the correct ifIndex.

Port-down trigger prototype (admin-enabled ports only, suppresses deliberately-disabled empty ports): `last(ifOperStatus[{#SNMPVALUE}])=2 and last(ifAdminStatus[{#SNMPVALUE}])=1`. Real ifIndex map on a 28-port NV6 switch: `e0-0`=3 … `e2-5`=30 (walk `ifDescr` `.1.3.6.1.2.1.2.2.1.2` to confirm). **Gotcha:** editing a trigger PROTOTYPE or LLD filter does NOT update already-instantiated per-port triggers until the LLD re-runs — force with execute-now or wait the 3600s LLD cycle.

**Benches** (2123, 4122, 4124 — bench by name even if typed NV4) are workshop units with expected disconnection noise: their `ifDescrv3` LLD rule is **disabled per-host** and discovered port items deleted, so they don't alarm. This is intentionally per-host, NOT in the shared template (so real trains still alarm).

### Host IP tracking — APs float on DHCP; don't pin a static IP

AP/switch IPs float on 2-minute DHCP leases. NMS **auto-syncs** the current lease IP into each Zabbix host interface (a batch task; all hosts are `useip=1` with the live `10.179.x` IP). So do **not** hand-edit a host IP or pin a static one — it'll go stale. After an AP recovers/reboots, expect its "cannot be pinged" alarm to **linger a few minutes** (proxy-side ARP/forwarding convergence — the CCU can ping it the whole time); fix = force re-poll of the host's `icmpping` items + wait, NOT a config change. The trigger auto-resolves once `icmpping=1`.

### Factory AP recovery (AP on 192.168.1.x, invisible to vlan100)

A never-commissioned AP sits on factory `192.168.1.x`, off the management VLAN, so OBN can't discover/render it and `dosto-ap-config-update` can't reach it. Recover via temp untagged `192.168.1.2/24` on CCU `bond0` + clone a same-variant (m / non-m) sibling's rendered config + LuCI push. **Full procedure is the `dosto-ap-factory-recover` skill** (`.claude/skills/dosto-ap-factory-recover/`); validated on 4736-115 AP4m 2026-06-08. Standard reachable factory APs (already on `10.179.x`) use the [Westermo AP Config Push](#westermo-ap-config-push--manual-method-when-obn-snmp-fails) LuCI method below instead.

### Provisioning facts (why some columns read blank / generic)

- **No project 51** in NMS — DOSTO-NEU's NMS project is **50** ("Dosto-Neu-National"). The CCU's `project_id 51` is only the Nomad-Connect MQTT topic namespace, not an NMS project; NMS keys on `rtl_project_id 50 / rtl_train_id` (e.g. 6018). [`project_nms_train_record_vs_monitoring_layer`]
- **Alarm "Device" column `C<n>`** (C2/C4/C6) = positional coach index from the Zabbix host `R<n>` (frontend R→C relabel), NOT the physical car letter or painted number. Real painted numbers require OBN `physical_coach_map_file` (a MAC→coach YAML, currently UNSET for DOSTO-NEU → all "unknown") AND `paintedCoach:true` on the project config. [`project_nms_painted_coach_number_source`]
- **Summary In-depot/Trip/Location/Next-trip** = the RTPI **journey feed** (backend MQTT), not telemetry/Zabbix. The whole pipeline is **Nomad-backend, nothing on the CCU** (verified 2026-06-30: no `rtpiJourney` consumer on the train, no DNS for the RTPI host): ÖBB REST API (`api-gateway.oebb.at/JourneyFeed_API`) → **Nomad Ingestion Service** pulls every ~4–30 min → generic JSON → RTPI DB importer → MariaDB → **RTPI Publisher** → HIVE broker (`emqx-obb`) → NMS tiles. Two backend knobs decide what you see, and they're independent (see "RTPI journey-feed mapping" below for the full trace). [`project_nms_train_record_vs_monitoring_layer`] [`project_rtpi_journey_feed_lookup_mapping`]
  - **Visibility** is gated by `journeySelectionMode: inLoadRangeInMinutes` / `loadRangeInMinutes [5,720]` — the importer only publishes journeys active within a time window. **Trains in commissioning have no live ÖBB schedule → absent by design; self-resolves on entry to revenue service.** This (not a "4736 coverage gap") is why our trains' tiles are blank.
  - **Friendly naming** is governed by `lookup.xlsx` on the importer pod. DOSTO stock is **not in it** (audited 2026-06-30: 71 rows, all Railjet/CAT/Nightjet, zero `4736`/`4734`/`4744`/`4746`/`4748`). So in-service DOSTO trains publish as **raw `T4736xxx`** until rows are added — cosmetic only, not why tiles are blank.

### Subscribing to the RTPI journey feed (verify whether a train is published)

The journey feed is a **downlink** on the same backend broker the telemetry bridge uses: `emqx-obb.nomadrail.com:8883` (TLS, per-train client certs at `/etc/mqtt-bridge/ssl/` on every NV6 CCU). Topic structure (confirmed live):

```
to/obb/train/-/<vehicle>/<vehicle>/<vehicle>-MMC-01/rtpiJourney/<subtopic>
```

`<vehicle>` is the join key — e.g. `T4744036`, `T4746113`, `CAT80`, `NGII13`, `RG001`. Run from any commissioned NV6 CCU (validated on box1-t22 / `10.179.22.1`):

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@10.179.22.1
cd /etc/mqtt-bridge/ssl
mosquitto_sub -h emqx-obb.nomadrail.com -p 8883 \
  --cafile hive-emqx-obb.nomadrail.com-ca.pem \
  --cert   hive-emqx-obb.nomadrail.com-cert.pem \
  --key    hive-emqx-obb.nomadrail.com-key.pem \
  -i br-p50-t6022-u1-sniff \
  -t "to/obb/train/#" -v
```

Quick "is my train in the feed" check — list distinct vehicle nodes:

```bash
... -t "to/obb/train/+/+/+/+/rtpiJourney/#" -v \
  | sed -E 's#^to/obb/train/[^/]+/([^/]+)/.*#\1#' | sort -u
```

Gotchas:
- Use a **unique `-i` client-id suffix** so you don't collide with the live bridge's own MQTT session (which is `br-p50-t6022-u1`).
- Journey messages are **low-cadence and largely retained** — capture for 60–90s, not a few seconds.
- The `<vehicle>` node is either a friendly Nomad ID (`RG001`, `CAT80`, `NGII13` — these are `lookup.xlsx`-mapped) or a raw `T<digits>` (unmapped, e.g. `T4744036`). Both are normal; raw `T…` just means no lookup row.
- Absence of a train is usually **inLoadRange gating** (not in service), NOT a coverage gap. Don't conclude "ÖBB doesn't carry it" from absence — confirm against the schedule window.

### RTPI journey-feed mapping (the "is there a mapping on our side?" answer)

There **is** a mapping on our side, but it is **backend, not on any CCU** — a manually-maintained `lookup.xlsx` consumed by the ÖBB RTPI importer. It only controls **friendly naming**, not whether a train appears.

**How the join works** (per Confluence OBIS "ÖBB API-JSON Data Mapping" p2009989160 + "Dani Adoption / lookup.xlsx" p4162322433 + "setting.json" p4860739585):
1. ÖBB `GetVehicleSchedules` returns `vehicle_code` (UIC, e.g. `948147361109`).
2. Importer computes `vehicleNumber = T{vehicle_code.substring(4,11)}` → `T4736110`. **So ÖBB's API does carry 4736 codes** — the digits are not the problem.
3. If `excelFileAdoption: true` and that `T…` matches the **"Schedule feed vehicle number"** column in `lookup.xlsx`, it's swapped for the **"Nomad ID"** (→ `RG001` etc.). No match → raw `T…` retained.

**`lookup.xlsx` location & update** (importer pod, repo `nd-rtpi-kubernetes-obb`, host `vmrtpi01.oebb.21net.com` — no DNS/route from the CCU):
- Path in pod: `/opt/nd/nd-rtpi-obb-importer/fleetFile/lookup.xlsx` (config `dataOutput.fleetPath`). **Must be placed manually**, not in Puppet.
- Columns: `Nomad ID`, `NMS serial number`, `Schedule feed vehicle code`, `Schedule feed vehicle number`.
- Update: `kubectl cp lookup.xlsx nd-obb-rtpi-importer-<pod>:/opt/nd/nd-rtpi-obb-importer/fleetFile/lookup.xlsx` then `kubectl rollout restart deployment nd-obb-rtpi-importer`.
- A working copy is checked into this workspace at `rtpi/lookup.xlsx`.

**Audit 2026-06-30:** the current `lookup.xlsx` has 71 rows, all Railjet (`RG`, 60) / CAT (9) / Nightjet (`NGII`/`RGII`). **Zero DOSTO rows.** Adding DOSTO-NEU rows is the only "mapping on our side" action — and it's cosmetic (friendly name vs `T4736xxx`), relevant only once trains run in service. It is **not** the cause of today's blank tiles (that's inLoadRange gating).

---

## NMS Train-Type Config: creating/updating a consist diagram via the API

When the NMS consist diagram for a train type is wrong (e.g. a bench registered with the wrong coach count) and the UI's "create new configuration" button returns **500**, drive the REST API directly. Validated 2026-06-04 building the 2-coach `NV2 - Bench` (OBB project 50) from the 4-coach NV4 template.

### Auth
NMS REST uses a token in the `Auth-Token` header (NOT basic auth, NOT a cookie — those all 401). The okapi Zabbix creds do **not** work here; use your own NMS login.
```bash
B="https://nms-obb.nomadrail.com/nms"
TOKEN=$(curl -sk -X POST "$B/rest/user/authenticate" \
  -H "content-type: application/json;charset=UTF-8" \
  -d '{"username":"<you>","password":"<pw>"}' | sed -E 's/.*"token":"([^"]+)".*/\1/')
curl -sk "$B/rest/configurations/50/traintypes" -H "Auth-Token: $TOKEN"        # list types
curl -sk "$B/rest/configurations/50/traintypes/NV2%20-%20Bench" -H "Auth-Token: $TOKEN"  # GET (returns ALL versions as a list)
```
Run curl from the CCU (`developer@10.179.X.1`) — it can reach the NMS; your laptop may not.

### Write model (non-obvious)
- The train-type endpoint accepts **GET and POST only**. PUT / PATCH / DELETE all return **405**.
- **POST = insert** (Mongo), keyed on `_id`. POSTing a body that still contains the existing `_id` → `DuplicateKeyException 11000`. **Remove `_id`** so Mongo assigns a new one.
- There is **no update or delete verb and no activate endpoint**. Versioning is by document: GET returns every version; **the version with the highest `activatedOn` is the active one** the UI loads. To "update", POST a new version with `activatedOn` set higher than the current max.
```bash
python3 -c 'import json;d=json.load(open("/tmp/new.json"));d.pop("_id",None);d["activatedOn"]=<current_max+1>;json.dump(d,open("/tmp/push.json","w"))'
curl -sk -X POST "$B/rest/configurations/50/traintypes/NV2%20-%20Bench" \
  -H "Auth-Token: $TOKEN" -H "content-type: application/json;charset=UTF-8" \
  --data-binary @/tmp/push.json
```
- The backend uses a **strict JSON parser**: any unknown top-level field (e.g. a hand-added comment field) → `UnrecognizedPropertyException 500`. Only the 27 known fields are allowed. Don't add notes inside the JSON.

### Consist-view rendering rules (the `Item 'X.pN' not found` error)
The Angular renderer (`DeviceCollection.layoutDevices` → `generateConnections` → `getDeviceItem`) has two hard requirements. Violating either throws `Item '<id>.<port>' not found` and the diagram won't draw:

1. **`dynamicConsist` must be `false` for a static-layout bench.** With `true`, the renderer ignores `staticConsistLayout` and generates its own layout from live device reports (`convertDynamicConsist2Layout`), producing connections against ports that don't exist. Set `"dynamicConsist": false`.
2. **Connection-target ordering.** `deviceLayouts` is processed in array order; a device's `connections[].target` must reference a device that appears **earlier** in the array (it must already be in `this.items`). Practically: declare each inter-device link on the *later* device pointing back to the *earlier* one, and **put the CCU/BOX last** in the array if it connects to a switch (the CCU references a switch, so the switch must come first).

Validation snippet before pushing:
```bash
python3 -c '
import json;d=json.load(open("/tmp/new.json"))
lay=d["trainConsistView"]["staticConsistLayout"]["deviceLayouts"]
idx={x["id"]:i for i,x in enumerate(lay)}
bad=[f"{x[\"id\"]}->{c[\"target\"]}" for i,x in enumerate(lay) for c in (x.get("connections") or []) if idx.get(c["target"].split(".")[0],1e9)>=i]
print("ordering violations:", bad or "NONE")'
```

### SNMP creds per device type (project 50 convention)
⚠️ **CORRECTED 2026-06-08 (verified live by `snmpget` on multiple t18/t23 devices).** An earlier version of this note said switches use SNMP passphrase `NomadComeIn` — **that was WRONG and caused a fleet-wide Zabbix mis-cred outage** (all switch+AP SNMP monitoring dead, NMS SNMP-blind while tiles showed "online" off ICMP). `NomadComeIn` is the device **SSH / LuCI GUI login password** (user `admin`), **NOT** an SNMP credential. Do not put it in any SNMP field.

The correct SNMP creds for `dynamicConsistConfig.deviceConfigurations` (and Zabbix host interfaces):

| Device | SNMP user | auth | priv | passphrase (auth & priv) | level |
|---|---|---|---|---|---|
| **SW** (VDS switch) | `snmpadmin` | SHA1 | AES128 | `NomadStayOut!` | authPriv |
| **AP** (Westermo) | `admin` | SHA1 | AES128 | `NomadStayOut!` | authPriv |
| BOX / CCU, MEDIA | — | — | — | — | `snmp:false` (agent/ICMP only) |

⚠️ **AP and SW use INVERTED SNMP usernames** (AP=`admin`, SW=`snmpadmin`) — proven mutually exclusive: the AP answers SNMP only as `admin` (`snmpadmin`→"Unknown user name"); the switch only as `snmpadmin` (`admin`→"Unknown user name"). Counter-intuitive but confirmed.

⚠️ **Zabbix-6 enum gotcha:** the NMS `authProtocol`/`privProtocol` integers map `0=MD5, 1=SHA1, 2=SHA224…` and `0=DES, 1=AES128…`. So **SHA1 = `1`** (NOT 2 — 2 is SHA224) and **AES128 = `1`**. net-snmp `-a SHA -x AES` correspond to `authProtocol:1`/`privProtocol:1`.

After correcting Zabbix host creds, switches also need a **`systemctl restart zabbix-proxy`** on the CCU (not just `config_cache_reload`) to clear stale failed-auth backoff — or let the train power-cycle do it.

Device IPs are filled by discovery at activation — leave `trainLayout` octets as-is; APs sit at `7.7.7.7` in Zabbix until discovered.

### Coach header label and canvas sizing (the `N/A` label + diagram proportions)
Both reverse-engineered from `main.d338fc0ee0b0573fffdc.bundle.js` (download to CCU, grep — non-minified, real method names) on 2026-06-04 for the 2-coach `NV2 - Bench` (train 2123, `OEBB-Bench-2C`).

**Coach header label ("A" shows as "N/A").** The `Coach` constructor (alarmObjects.js) computes:
```js
let coachName = deviceLayout.paintedCoachId !== "unknown" ? deviceLayout.paintedCoachId : deviceLayout.name;
// then renders:  new fabric.Text(this.name || 'N/A', ...)
```
`paintedCoachId` is **NOT a config field** — the backend `DeviceLayout` model has exactly 7 known properties (`connections, position, type, name, id, coach, up`); POSTing a `paintedCoachId` key → `UnrecognizedPropertyException 500`. It is attached **at draw time** in `drawConsistLayout`: for each `coach`-type layout, the renderer finds the live `data.train.deviceGroups` entry whose `name` ("Coach N", `Coach` stripped) === `layout.coach`, and copies that group's `paintedCoachId` onto the layout. A live group's `paintedCoachId` defaults to the literal string `"unknown"` unless a device reports a painted number. So:
- Coach **with** a matching live device group → gets `"unknown"` → ternary falls back to static `name` → label correct.
- Coach with **no** matching live group → `paintedCoachId` stays `undefined` → `undefined !== "unknown"` is true → `coachName = undefined` → falsy → renders **`N/A`**.

Therefore **the label is driven entirely by live device→coach mapping, never by the train-type JSON.** On bench 2123 all 8 Zabbix hosts were registered as `50_2123_R2_*` (coachId 2; `R%d` token = coach number, parsed at bundle `split[2].replace("R","")`), so no "Coach 1" group exists and coach A renders `N/A` — even though the train-type `trainLayout` correctly defines a coach-1 block (3 SW + 4 AP + BOX) and DHCP shows physical `2t-A1/A2/A3` switches online. The Zabbix skeleton is **stale** (created from an older config version; hosts still at placeholder `7.7.7.7`/`0.0.0.0` because OBN discovery never produced a consist here — `consist.yaml` empty, no `discovery.json`). **Fix path = rebuild the NMS/Zabbix host skeleton so coach-1 devices register as `R1`** (run OBN discover→report once the bench's templates match the intended consist, or correct the Zabbix host coach token). NOT a consist-view JSON change. ⚠️ This bench's OBN templates are nv4 4-coach (`nv4-100-A1`, `nv4-300-G1`, …) mid OEBB-251 v4 push — rebuilding intersects active commissioning state; coordinate before running discovery.

**Deeper root cause — OBN has no nv2 support.** `report_dosto_neu.py`'s `number_coaches()` assigns coach numbers by BFS over LLDP, seeded from the CCU via `ccu1_coach_map={"nv4":2,"nv6":3,"fv5":2,"fv6":3}` / `max_coaches={"nv4":4,...}` — **no `nv2` key**, so a 2-coach bench can't be numbered. Plus the templates + `backbone-discovery.yaml train_type` are nv4, and the bench's CCU is wired non-standard (CCU→A2/A1, inter-coach A↔B on A1.e0-1↔B1.e0-1). Full staged enablement plan + verified LLDP topology: [`OEBB-251/nv2-bench-obn-enablement-plan.md`](OEBB-251/nv2-bench-obn-enablement-plan.md).

**Canvas sizing.** `prepareCanvasDrawingContext` fits the canvas to the container while preserving the `gridSize` aspect ratio:
```js
scale = min(divWidth/gridSize.width, divHeight/gridSize.height);
canvas.width = gridSize.width*scale;  canvas.height = gridSize.height*scale;
```
Device coords come from the coach `position.bounds` (absolute) + percentage-relative child positions. House style = **625 grid-units per coach** (4-coach NV4 uses `gridSize.width 2500`, coaches at left 0/625/1250/1875, each `width:600 height:800 top:0`; 25px right + 50px bottom slack vs grid 2500×850). For the 2-coach bench, tighten `gridSize` to exactly bound the content: coaches span x:0–1225, y:0–800 → set `gridSize {width:1225, height:800}` (was 1250×850). Pushed 2026-06-04 as NV2 version `activatedOn 1780564811287`.

Reference file: [`trackers/bench_2123_nv2_template.json`](trackers/bench_2123_nv2_template.json) — the validated 2-coach NV2 bench. NOTE: the live active version drifts past this file as new versions are POSTed; always GET the highest-`activatedOn` version before editing, don't start from the reference file.

## VDS Switch Firmware Push — Manual `sysadmin load` Method (When OBN Can't)

Push firmware to one VDS switch directly via its CLI, bypassing OBN. Use when OBN's push path is unavailable — image not staged in OBN's `.kad` form, `rules.yaml` firmware target pinned to the old version (would no-op as `already_at_target`), or discovery unreliable. Pairs with memory `project_manual_tftp_obn_bypass` and `project_vds_sysadmin_load_blocked_by_ttcmp_critical`.

### The command sequence (from switch_manual.txt Ch.22, ~line 9559)

```
sysadmin load <URL>                    # pull the .kad image into the switch (non-destructive)
sysadmin set default image <NAME>      # activate it; <NAME> = full name from `sysadmin show images`
sysadmin reboot                        # required for it to take effect (prompts Y/N)
```

- **Valid URL schemes:** ftp, http, tftp, scp. On the bench, TFTP off the CCU: OBN's `tftpd-hpa` already serves `/data/auto-topology` on `:69`. Stage the `.kad` there.
- **Artifact:** use the **`.kad`** OS-image file (e.g. `ipart-ng.kad`), NOT the `.ksi` — `.ksi` is only the switch's internal stored form (what `sysadmin show images` lists). For 7.4.2→7.4.8 (both >7.0.1) this is a normal partition flash; the `bigbang-a-ng.ksi` full-USB-reinstall path is only needed upgrading from <7.0.1 (release notes p1).
- **`<NAME>`** for `set default image` is the full string from `sysadmin show images` after a successful load (e.g. `sw-std-ng_7.4.8-<build>.ksi`), not a bare version.
- `sysadmin` subcommands work fine over one-shot SSH (`sysadmin show images` returns data). Use the CLAUDE.md legacy-SSH-into-switch snippet.

### Trap 1 — use the vlan100 CCU IP, not `.1`

The CCU's `10.179.122.**1**` is **bond0** (cellular side); switches on vlan100 reach the CCU only at its **vlan100 SVI, `10.179.122.129`** (`/25`). A load URL pointing at `.1` fails **silently** — the switch issues no RRQ and stages nothing. Always: `sysadmin load tftp://10.179.122.129/<file>.kad`. (Confirm the CCU vlan100 IP with `ip -br addr show vlan100`.)

### Trap 2 — "system is busy processing a critical operation" = the CONSIST is unsettled, not the switch

If `sysadmin load` returns exit 0 with **no output** over plain SSH, re-run with `ssh -tt` (PTY) to surface the real message. If it says:

> `Warning: the system is busy processing a critical operation. Try again later.`

…the switch is refusing the load because the **consist's TTCMP subsystem is in a critical/unsettled state** — a fabric-level safety interlock, **not** local CPU. Proven 2026-07-04 on bench box1-t122: a CPU-pinned switch (E3, load 2.9) AND a fully idle one (E2, load 0.08) both refused identically. An unsettled TTCMP state is exactly what a **bypass-loop storm** ([`project_bench_4122_multicast_storm_e0_0`]) creates and sustains. **Containing the storm (disable root e0-0) stops the flood but does NOT settle TTCMP → the interlock stays engaged → loads still refused.** The only thing that unblocks the flash is making the consist healthy: restore the bypassed switch (A1) / remove the loop so TTCMP reaches a confirmed state. Then any switch accepts the load.

### Verify what actually happened (never trust exit 0)

```bash
# 1. Did the switch pull the file? (proof of a real transfer attempt)
sudo journalctl --since '-5min' --no-pager | grep "RRQ from <switch-ip>"
#    empty  = switch never started the transfer (wrong IP, or TTCMP-critical refusal) — switch UNTOUCHED, safe
# 2. Is the new image staged in the bank?
sshpass -p "$PW" ssh $SW_OPTS admin@<switch-ip> 'sysadmin show images'
#    still only old .ksi = nothing loaded
```

No RRQ + unchanged image bank = the switch is safe/untouched (not mid-flash). Only after a confirmed RRQ + the new image appearing in `sysadmin show images` do you proceed to `set default image` + `reboot`.
