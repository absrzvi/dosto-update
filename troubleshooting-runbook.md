# DOSTO Troubleshooting Runbook

Operational procedures for troubleshooting and reconfiguring DOSTO trainset onboard systems. Each section is a self-contained procedure — copy/paste-friendly.

## Contents

- [LLDP Cabling / Topology Check](#lldp-cabling--topology-check-obn--auto-topology-failure)
- [OBN Bugs 1–7 — Known Crashes and Fixes](#obn-firmware--config-update--known-bugs-and-fixes-gitlab-rd)
  - [How to apply all fixes](#how-to-apply-fixes-on-a-ccu-manually-until-gitlab-release)
- [CCU Firewall — TFTP conntrack helper missing (silent batch firmware failures)](#ccu-firewall--tftp-conntrack-helper-missing-silent-batch-firmware-failures)
- [OBN train_id — Verify and Fix Before Any Config Push](#obn-train_id--verify-and-fix-before-any-config-push)

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
