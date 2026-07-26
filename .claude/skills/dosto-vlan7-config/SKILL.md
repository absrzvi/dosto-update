---
name: dosto-vlan7-config
description: Verify and (manually) fix the CCU's vlan7 IP on a DOSTO train. Computes the expected IP from the Fzg ID using the bit-packed addressing scheme, reads live state, diffs against /etc/nd-redundancy/networks.yaml and /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection, and prints the exact nd-systemupdate.sh shell recipe to make the fix permanent across reboots. Use when a CCU's vlan7 IP is suspect, before any L2 health check (since FW reachability depends on it), or as Step 4b of the train-login workflow during commissioning. The skill never writes to either file or triggers the chroot — the engineer runs the recipe themselves.
---

# DOSTO vlan7 Configuration Check

This skill is the canonical procedure for verifying and fixing the **CCU's vlan7 IP** on a DOSTO NEU train.

The CCU has a vlan7 interface (the OBS / Stadler-firewall transit VLAN). The IP is set in two places that must agree, and must match what the IP-Port-Allocation PDF defines for the train. Getting this wrong silently breaks Stadler-side reachability — the L2 fabric looks healthy but TCP probes to the Stadler FW peer (`172.19.X.1` even Fzg / `172.19.X.129` odd Fzg) fail.

## When to use

- **Commissioning a new train (Step 4b in [train-login-checklist.md](train-login-checklist.md))** — verify vlan7 is correct *before* attempting any OBN config push or L2 health check.
- **Debugging "Stadler firewall unreachable" on an otherwise-healthy train** — vlan7 misconfigured is one of the more common causes.
- **After a CCU reboot** — verify the IP survived the btrfs snapshot rollback.
- **Whenever [fleet-status.md](fleet-status.md) shows `vlan7 ok` as ❓ or 🔴** — fill it in.

## Output modes

Both default (check) and verify modes support two output flavours:

- **default — engineer-readable.** Diagnostic table + verdict + recipe-when-needed. What you see when running this manually.
- **`--json` — machine-readable.** A single JSON line on stdout matching the `skill_outputs[]` shape from [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md). Subagents pass `--json`; engineers don't.

The diagnostic procedure is identical in both modes — `--json` is purely a formatter switch.

### `--json` shape

Subagent emits this as one element of `skill_outputs[]`:

```json
{
  "skill": "dosto-vlan7-config",
  "mode": "check",
  "schema_version": "1",
  "verdict": "all_match|nmconnection_correct_live_wrong|live_correct_nmconnection_wrong|both_wrong",
  "raw": {
    "fzg_input": 132,
    "expected": "172.19.194.2/17",
    "expected_octet3": 194,
    "expected_octet4": 2,
    "live": "172.19.194.2/17",
    "yaml_formula": "172.19.{{ 128 + ((128+train_id) // 2) }}.2",
    "nmconnection": "172.19.194.2/17",
    "live_decoded_fzg": 132,
    "live_decoded_device": 2,
    "yaml_consistent_with_fzg": false,
    "vlan7_link_errors_rx": 0,
    "vlan7_link_errors_tx": 0,
    "vlan7_carrier_false": 0,
    "fw_peer_ip": "172.19.194.1",
    "fw_peer_arp_state": "reachable|stale|failed|none",
    "fw_peer_icmp_replies": 0,
    "fw_peer_icmp_sent": 5,
    "fw_peer_tcp80": "open|closed|timeout|filtered",
    "fw_peer_tcp22": "open|closed|timeout|filtered",
    "fw_commission_state": "commissioned|uncommissioned|path_broken|unknown"
  },
  "recipe": null
}
```

`fw_commission_state` is the per-train answer to *"has Stadler finished configuring the firewall?"* — derived per CLAUDE.md Phase 6 (Q1 + Q2):

- `commissioned` — ARP REACHABLE, ICMP 100% loss (Stadler policy dropping ping as designed). TCP outcome doesn't matter for this classification.
- `uncommissioned` — ARP REACHABLE, ICMP gets replies (bare Westermo behavior, no Stadler policy yet).
- `path_broken` — ARP FAILED or no neighbour. Commission state cannot be determined.
- `unknown` — ICMP was not tested (skill running in check-only mode with no FW probe). Customer-facing classifications must NOT rely on `unknown`.

`verdict` semantics (per the diff matrix in the procedure section below):
- `all_match` — live IP, nmconnection, and expected all agree (yaml may be cosmetically wrong; doesn't change verdict)
- `nmconnection_correct_live_wrong` — 🟡 transient — NetworkManager hasn't reapplied; suggest `nmcli con down/up`
- `live_correct_nmconnection_wrong` — 🟡 cosmetic — live OK but persistent config diverges; fix on next chroot session
- `both_wrong` — 🔴 vlan7 is wrong; recipe non-null

`yaml_consistent_with_fzg` is `false` when the (broken) yaml formula would compute a different IP than the bit-packed Fzg formula. Always `false` on production CCUs (yaml uses OBN `train_id` not Fzg ID); informational only.

`live_decoded_fzg` decodes the live IP back to its encoded Fzg ID via the inverse formula:
```
fzg = ((octet3 - 128) << 1) | (octet4 >> 7)
device = octet4 & 0x7F
```
If `live_decoded_fzg != fzg_input`, the live IP encodes a different Fzg than what we expected — common during the broken-template-formula bug, or expected on DOSTO NEU `train_id ≠ Fzg ID` cases.

`recipe` is non-null only when `verdict == both_wrong`. Contains the multi-line `nd-systemupdate.sh shell` command sequence with placeholder strings already substituted with actual values.

## The addressing scheme (read this once)

Every device on the DOSTO NEU IP fabric uses a **32-bit packed address**:

```
bits  1-12 : 172.19    (static prefix — DOSTO NEU is always 172.19.x.x/17)
bits 13-17 : VLAN ID   (5 bits, range 1-31; vlan7 = 0b00111)
bits 18-25 : Fzg ID    (8 bits, range 1-255; the customer-side train ID)
bits 26-32 : Device    (7 bits, range 1-127; per-device offset within the train)
```

For the **CCU vlan7 interface, device = 2**; the Stadler firewall is **device = 1**. Both carry the odd-Fzg +128 bit in octet 4: even Fzg → FW `.1` / CCU `.2`, odd Fzg → FW `.129` / CCU `.130`. (Odd-Fzg FW `.129` field-verified 2026-07-09 on box1-t41 / 4705-103 / Fzg 231: FW at `172.19.243.129`, while `.1` was INCOMPLETE/no-route.)

That packing produces this formula for the CCU vlan7 IP:

```
octet 3 = 128 + (Fzg // 2)
octet 4 = (128 if Fzg is odd else 0) + 2
IP      = 172.19.<octet3>.<octet4>/17
```

**Validation set (verified 2026-05-09):**

| Train# | Fzg ID | Predicted | Confirmed |
|---|---|---|---|
| 4734-101 | 1 | 172.19.128.130 | ✓ from PDF |
| 4734-102 | 2 | 172.19.129.2 | ✓ from PDF |
| 4734-103 | 3 | 172.19.129.130 | ✓ from PDF |
| 4734-104 | 4 | 172.19.130.2 | ✓ from PDF |
| 4734-120 | 20 | 172.19.138.2 | ✓ from PDF |
| 4736-105 | 133 | 172.19.194.130 | ✓ from PDF |
| 4736-106 | 134 | 172.19.195.2 | ✓ from PDF |
| 4736-109 | 137 | 172.19.196.130 | ✓ from PDF |
| 4736-110 | 138 | 172.19.197.2 | ✓ from PDF |
| Bench (encoded Fzg=250) | 250 | 172.19.253.2 | ✓ from live CCU |

The "odd vs even" pattern: each octet-3 value covers 2 consecutive Fzg IDs — **even Fzg → host .2, odd Fzg → host .130**. The same rule applies to the FW peer (device 1): **even Fzg → FW `.1`, odd Fzg → FW `.129`** — i.e. `FW octet4 = 128*(Fzg%2) + 1`, or simply `expected_vlan7_ip(fzg, device=1)`.

## Fzg ID lookup

**Runtime source of truth: the [`fleet-status.md`](../../../fleet-status.md) row for the Train#.** Read it via `python scripts/fleet_status_lookup.py lookup <train#> --require-fzg`. If the row's Fzg cell is `❓`, halt and prompt the engineer to populate it (from the IP-Port-Allocation PDF or physical inspection) before proceeding.

**Reference formulas** (for engineers; never trust silently at runtime):

- **4734-NNN → Fzg = NNN - 100** (e.g. 4734-120 = Fzg 20)
- **4736-NNN → Fzg = NNN + 28**  (e.g. 4736-105 = Fzg 133)
- **4705-NNN → Fzg = NNN + 128** (e.g. 4705-103 = Fzg 231)
- **4706-NNN → Fzg = NNN + 88**  (e.g. 4706-103 = Fzg 191)

The PDF header (`Fahrzeugnummer: <train#>    Fzg. ID: <NN>`) is the off-line source of truth — that's what populates fleet-status. The formulas above are correct for the typical case but should never override an explicit fleet-status value.

## Procedure

### 0. Inputs

You need:

- **Train#** (e.g. `4736-105` — the Nomad-internal primary identifier)
- **CCU IP** (e.g. `10.179.1.1`)

Fzg ID is derived: the skill runs `python scripts/fleet_status_lookup.py lookup <train#> --require-fzg` to get the Fzg from the fleet-status row. If that returns `fzg_unknown` (cell is `❓`), the skill halts with: *"Fzg ID for `<train#>` missing in fleet-status. Look it up in `train-ip-allocation-commission/<series>-xxx/<train#>/<train#>_IP-Port-Allocation.pdf` and populate the Fzg column."*

If the user invoked this skill with an argument like `/dosto-vlan7-config 4736-105`, use that as the Train#. Engineers may also pass a bare Fzg integer (`/dosto-vlan7-config 133`) for ad-hoc checks — in that case treat Fzg as authoritative and skip the fleet-status lookup (useful for sanity-checking the math against a value you already know). When ambiguous, ask: *"Train# (e.g. 4736-105) or Fzg ID (e.g. 133)?"*.

### 1. Compute the expected IP

```python
def expected_vlan7_ip(fzg: int, device: int = 2) -> str:
    octet3 = 128 + (fzg // 2)
    octet4 = (128 if fzg % 2 == 1 else 0) + device
    return f"172.19.{octet3}.{octet4}/17"
```

Show the bit decomposition so the engineer can sanity-check (e.g. *"Fzg 133 is odd → octet 4 includes the +128 bit → expected `172.19.194.130/17`"*).

### 2. Read live CCU state — three things

SSH to the CCU and run these reads:

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
  echo "=== live ==="
  ip -br addr show vlan7
  echo "=== networks.yaml fis interface ==="
  awk "/^  fis:/,/^  [a-z]/" /etc/nd-redundancy/networks.yaml | head -20
  echo "=== nmconnection ==="
  sudo cat /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection | grep -E "^address1=|^method="
'
```

Extract:
- **Live IP**: from `ip -br addr` output (e.g. `vlan7@bond0  UP  172.19.194.130/17 ...`)
- **YAML formula**: from `networks.yaml`'s `fis:` block, the `ipaddress:` line. Note that this is a Jinja template (`172.19.{{ formula }}.X`). Production CCUs typically have a stale formula here; this file is dead code at runtime — NetworkManager is what actually applies the IP. Treat YAML disagreement as a 🟡 (cosmetic) finding.
- **nmconnection IP**: from the `address1=...` line. **This is the live-config source of truth.** If this is wrong, vlan7 is wrong.

### 3. Diff and report

Compare three values: **expected** vs **live** vs **nmconnection**. Possible outcomes:

| Live | nmconn | Verdict | What to do |
|---|---|---|---|
| ✅ expected | ✅ expected | ✅ **all match** | Nothing — flip [fleet-status.md](fleet-status.md) `vlan7 ok` to ✓ |
| ❌ wrong | ✅ expected | 🟡 transient | NetworkManager hasn't reapplied — `sudo nmcli con down vlan7 && sudo nmcli con up vlan7`. Re-check |
| ✅ expected | ❌ wrong | 🟡 cosmetic | Live is right but persistent config disagrees — fix nmconnection on next reboot cycle |
| ❌ wrong | ❌ wrong | 🔴 **WRONG** | Apply the fix recipe (Step 4) |

Always also report the YAML formula's current value, but don't gate the verdict on it — call it cosmetic.

### 4. Print the fix recipe (DO NOT EXECUTE IT)

If the verdict is 🔴, print the exact `nd-systemupdate.sh shell` recipe so the engineer runs it themselves. Use Python `assert old in content; content.replace(old, new)` style — it fails loudly if the file isn't what we expected, which is much safer than `sed -i` inside a chroot.

```bash
# === STEP 1: Drop into the persistent-edit chroot ===
sudo /usr/sbin/nd-systemupdate.sh shell

# Inside the chroot, run BOTH of these in one go:

sudo python3 -c "
path = '/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection'
with open(path) as f:
    content = f.read()
old = 'address1=<CURRENT_NMCONN_IP>'
new = 'address1=<EXPECTED_IP>'
assert old in content, f'pattern not found in {path} — current content does not match what we read pre-chroot. Aborting.'
content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print('PATCHED nmconnection')
"

# (Optional, cosmetic) — also align the yaml formula. Skip if uncertain.
sudo python3 -c "
path = '/etc/nd-redundancy/networks.yaml'
with open(path) as f:
    content = f.read()
# Replace the entire ipaddress line under the fis: block.
# Show the before/after to be sure:
import re
m = re.search(r'(\\s+ipaddress:\\s+)(\".*?\")(\\s*?\\n)', content)
if m:
    print('YAML had:', m.group(2))
    new_ip_literal = '\"<EXPECTED_IP_NO_PREFIX>\"'  # just the IP, not /17
    content = content[:m.start(2)] + new_ip_literal + content[m.end(2):]
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED yaml')
"

# Exit the chroot — promotes work → release → runN, sets default GRUB entry
exit

# === STEP 2: Reboot into the new snapshot ===
sudo /usr/local/sbin/safe_reboot
```

**Before printing the recipe, fill in `<CURRENT_NMCONN_IP>`, `<EXPECTED_IP>`, `<EXPECTED_IP_NO_PREFIX>` with the actual values.** The placeholder strings should never appear in the final output the engineer sees.

### 5. Post-Flight — verify the rendered output

**Mandatory rendered-output verification** (Karpathy Principle 4 — Goal-Driven Execution; see also [`CLAUDE.md` § Universal Principles](../../CLAUDE.md)). The nmconnection file edit is the *input*; the live `vlan7@bond0` IP + reachability to the Stadler firewall are the *output downstream consumers depend on*. Verifying the file alone is necessary but not sufficient — NetworkManager could fail to apply, the new IP could collide on the wire, or the firewall could be on a different subnet.

After reboot, the engineer (or `dosto-commission-train` stage 10 `post_reboot_verify`) MUST verify all four of:

| Assertion | Probe | Pass criterion |
|---|---|---|
| **A. Input file unchanged from intent** | `sudo cat /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection \| grep "^address1="` | Single line: `address1=<EXPECTED_IP>` |
| **B. Live interface matches expected** | `ip -br addr show vlan7` | Shows `<EXPECTED_IP>` exactly (post-NetworkManager apply) |
| **C. Path to FW peer healthy (Q1)** | `ip neigh show dev vlan7 \| grep <fw-ip>` | State is `REACHABLE` (or `STALE` is also OK), MAC has Westermo OUI `00:90:e8:` |
| **D. FW commission state (Q2)** | `ping -c 5 <fw-ip>` | See decision table below |

`<fw-ip>` = `expected_vlan7_ip(fzg, device=1)` without the `/17` — i.e. `172.19.<octet3>.1` for even Fzg, `172.19.<octet3>.129` for odd Fzg. Probing `.1` on an odd-Fzg train false-classifies as `path_broken` (field-verified 2026-07-09, Fzg 231).

**Q2 interpretation (the F9 correction — read carefully):**

| Q2 ICMP result | Q1 result | Commission state | Action |
|---|---|---|---|
| 0/5 replies (100% loss) | Q1 = REACHABLE | ✅ `commissioned` — Stadler policy dropping ICMP as designed | None |
| Replies received | Q1 = REACHABLE | 🟡 `uncommissioned` — bare Westermo defaults, no Stadler policy applied yet | Flag for Stadler — they haven't finished commissioning the FW for this train |
| 0/5 replies | Q1 = FAILED | 🔴 `path_broken` — Q1 issue, not commission state | Fix path first; Q2 doesn't apply |
| Skipped | (any) | `unknown` | Don't write a customer-facing FW verdict |

**Reading TCP probes (informational only, NOT the commission test):**
TCP `nc -zv` to port 80 / 22 tells you only whether *something* responds on that port. Open ports do NOT mean "commissioned" — a bare Westermo FW also has 80/22 OPEN by default. Use Q2 (ICMP) to classify commission state. Use TCP only to verify specific service availability after commissioning is confirmed.

**If A passes but B fails:** NetworkManager didn't reapply on boot. Run `sudo nmcli con down vlan7 && sudo nmcli con up vlan7`, re-check.

**If A, B, C pass but D shows `uncommissioned`:** the CCU side is correct; Stadler hasn't finished configuring the FW for this train. This is **not** a regression of the vlan7 fix — surface as a Stadler-action item in `fleet-status.md` under FW reach. Verdict: `ccu_ok_fw_uncommissioned`.

**If A, B, C pass but D shows `path_broken`:** Q1 failed. This contradicts B (which would have failed too). Re-check; if Q1 truly fails after B passes, investigate ARP / vlan trunking.

**If A fails but B passes:** very rare — means another nmconnection file is overriding ours, or a manual `nmcli` runtime override is active. Investigate.

**`--json` output for Post-Flight** (consumed by `dosto-commission-train`'s stage 10):

```json
{
  "skill": "dosto-vlan7-config",
  "mode": "post_flight",
  "schema_version": "1",
  "verdict": "all_match|ccu_ok_fw_uncommissioned|ccu_ok_path_broken|input_only|live_only|both_mismatch",
  "raw": {
    "fzg_input": 132,
    "expected_ip": "172.19.194.2/17",
    "input_assertion_a": {"pass": true, "nmconnection_address1": "172.19.194.2/17"},
    "rendered_assertion_b": {"pass": true, "live_ip": "172.19.194.2/17"},
    "path_assertion_c":    {"pass": true, "fw_peer_ip": "172.19.194.1", "arp_state": "reachable", "fw_peer_mac": "00:90:e8:ba:0e:bf"},
    "commission_assertion_d": {
      "pass": true,
      "fw_commission_state": "commissioned",
      "icmp_sent": 5,
      "icmp_replies": 0,
      "fw_peer_tcp80": "filtered",
      "fw_peer_tcp22": "filtered"
    },
    "vlan7_link_errors_rx": 0,
    "vlan7_link_errors_tx": 0
  }
}
```

`verdict` semantics (post-F9 update):
- `all_match` — A + B + C pass, D = `commissioned`. ✅ Fully done from our scope.
- `ccu_ok_fw_uncommissioned` — A + B + C pass, D = `uncommissioned`. ✅ for our scope; flag Stadler-action item in fleet-status (they haven't finished FW config for this train).
- `ccu_ok_path_broken` — A + B pass, C fails. 🔴 vlan7 nmconnection / live IP correct but the path to the FW peer is broken (vlan trunk, FW absent, etc.). Before concluding this, double-check you probed the correct FW host (`.1` even Fzg / `.129` odd Fzg).
- `input_only` — A passes, B fails. 🟡 NetworkManager didn't reapply (transient).
- `live_only` — B passes, A fails. 🔴 nmconnection file divergent from live.
- `both_mismatch` — A and B both wrong. 🔴 fix did not land.

`commission_assertion_d.pass = true` is set when D produced a definitive verdict (`commissioned` OR `uncommissioned`). It's `false` only when `fw_commission_state` is `path_broken` or `unknown`.

### 6. Update [fleet-status.md](fleet-status.md)

The last thing the skill does (or asks the engineer to do as part of Step 11) is update the train's row in [fleet-status.md](fleet-status.md):

- `vlan7 ok` column → ✅ if all match, 🔴 if mismatch persists, 🟡 if reboot pending
- `Last touched` column → today's date + initials
- If 🔴, add or update the per-train notes section explaining what's still wrong

## What this skill deliberately does NOT do

- ❌ Write to either file directly (the chroot is destructive — only the engineer runs that)
- ❌ Trigger `nd-systemupdate.sh shell` programmatically
- ❌ Reboot the CCU
- ❌ Touch `train_id` in `/etc/obn/backbone-discovery.yaml` (the mar5 migration rule — that file is off-limits regardless)
- ❌ Auto-extract the expected IP from the PDF (PDF parsing is fragile; the Fzg ID is the input, the formula does the rest)
- ❌ Trust the `networks.yaml` formula at runtime — it is dead code in production CCUs (the formula in current yaml templates incorrectly uses `train_id` instead of `Fzg ID`, producing wrong values on every real train)

## Edge cases / gotchas

- **DOSTO NEU `train_id` ≠ Fzg ID.** OBN's `train_id` (in `/etc/obn/template/nv6-*.cfg`) is decoupled from the Fzg ID by design (mar5 migration workaround). The vlan7 IP is computed from **Fzg ID** (from the PDF header), never from `train_id`.
- **The Stadler firewall is device 1, the CCU is device 2 — both carry the odd-Fzg +128 bit.** Even Fzg: FW `.1`, CCU `.2`. Odd Fzg: FW `.129`, CCU `.130`. Don't mix them up in the diff/recipe, and never assume the FW is `.1` (odd-Fzg trap, field-verified 2026-07-09 on Fzg 231).
- **Even Fzg → host octet starts with 0 (e.g. .2); odd Fzg → host octet starts with 128 (e.g. .130).** Sanity-check: if you're computing for an even Fzg and getting `.130`, your math is wrong.
- **The bench (`box1-t122`, train_id 122) has an encoded Fzg of 250** in its `.nmconnection`, not 122. The `train_id` value used by OBN does not feed into the vlan7 IP encoding. If you ever need to *decode* an existing IP back to its Fzg ID, that's the formula:
  ```
  fzg = ((octet3 - 128) << 1) | (octet4 >> 7)
  device = octet4 & 0x7F
  ```
- **`/17` not `/24`.** The vlan7 subnet is `172.19.128.0/17`, covering `172.19.128.0` through `172.19.255.255`. Don't write `/24`.
- **NetworkManager wins on boot, not the yaml.** If yaml says one IP and nmconnection says another, the live state will match nmconnection. The yaml is essentially documentation at this point — fix it for hygiene, not because it does anything.

## Reference files

- `scripts/fix_obn.py` — sibling skill model (read-only diagnostic + manual recipe)
- [troubleshooting-runbook.md](troubleshooting-runbook.md) — `nd-systemupdate.sh shell` flow, Python heredoc fix-script style
- [train-login-checklist.md](train-login-checklist.md) — Step 4b is where this skill fires
- [fleet-status.md](fleet-status.md) — `vlan7 ok` column tracks per-train state
