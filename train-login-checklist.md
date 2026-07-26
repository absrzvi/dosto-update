# Train Login Checklist

What to do, in order, every time you SSH into a DOSTO train CCU. Designed so an engineer who has never seen this specific train can pick up where the last person left off.

**Always start by reading [fleet-status.md](fleet-status.md)** — find the row for the train you're about to log into. That tells you *why* the previous person stopped and *what command* you should be running next. If the row is blank or says `UNKNOWN`, this is a fresh visit and you're following the full checklist below.

---

## Step 0 — Before you SSH in (on your laptop)

1. **Identify the train.** From the train sticker / job ticket: train# (e.g. `4736-120`) and Fzg ID (e.g. `Fzg 148`). For 4736 series: `Fzg = train# + 28`.
2. **Read the fleet-status row.** Open [fleet-status.md](fleet-status.md), find the row, read the per-train notes section if there is one. **Don't skip this** — half the trains in the rollout are mid-something.
3. **Locate the schema PDF** if available: `docs/ND-DEL-OBB-035-IPA-NNN_NV_*.pdf` for the Fzg.
4. **CCU IP**: from the fleet table, or from the IP-Allocation PDF in `train-ip-allocation-commission/<series>/<train#>/`.

If the fleet table says `BLOCKED — Stadler`: confirm Stadler has actually fixed the cabling fault before logging in. If they haven't, there's nothing to do on the CCU and you'll just be repeating the same diagnosis.

## Step 1 — SSH into the CCU

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
```

If it hangs or refuses: CCU not on the network yet (wait), train powered off (check), cellular drop (retry), or wrong subnet (check fleet table for the right IP).

## Step 2 — First-30-seconds sanity check

```bash
hostname              # should be box1-tNN
uptime                # how long has CCU been up? recent reboot may have wiped patches
ip -br addr show vlan100
ip -br addr show vlan7
sudo dhcp-lease-list  # AUTHORITATIVE current IPs/hostnames for switches and APs
```

`dhcp-lease-list` is the source of truth — switches and APs have **2-minute DHCP leases**, ARP is unreliable. Don't skip this. The hostname column tells you what config each switch is currently running (e.g. `nv6-A1-v8-133` = correct; `nv6-A1-v3-133` = old config; `dosto-00000000` = no OBN config at all).

## Step 3 — Verify OBN patches are still in place

`btrfs` snapshot rollback can wipe `/etc/obn/` and `/usr/share/obn/` patches on every reboot, unless they were baked in via `nd-systemupdate.sh shell`. Run the check:

```
/dosto-obn-patches <ccu-ip>
```

The skill SSHs in, greps all 10 known-bug markers in one round-trip, and returns a status table plus a verdict. **Don't proceed past this step until the verdict is `10/10 patched`.** Partial patches are worse than vanilla — they leave latent crash/hang modes (Bug 10 is the only patch that prevents the `obn report` 100% CPU + 27GB RSS leak when a device is missing).

If the verdict is 🔴 (any bugs missing), the engineer runs:

```
/dosto-obn-patches <ccu-ip> --apply
```

…which prints the exact `scp` + `btrfs ro=false` + `python3 /tmp/fix_obn*.py` + `ro=true` recipe. Run it, then re-check.

To make patches **persist across CCU reboots** (recommended for any train you'll revisit), follow up with:

```
/dosto-obn-patches <ccu-ip> --persist
```

Prints the `nd-systemupdate.sh shell` recipe to bake patches into a new btrfs snapshot. Reboot via `sudo /usr/local/sbin/safe_reboot` afterwards, then re-run `/dosto-obn-patches <ccu-ip>` to confirm 10/10 markers survived. Update fleet-status `OBN patches` cell to `persisted (run<N>)`.

Full skill documentation: [.claude/skills/dosto-obn-patches/SKILL.md](.claude/skills/dosto-obn-patches/SKILL.md). Bug catalogue: [troubleshooting-runbook.md](troubleshooting-runbook.md) → "OBN Firmware & Config Update — Known Bugs and Fixes".

## Step 4 — Verify the Fzg ID is set correctly

The Fzg ID lives **only** in `/etc/obn/template/nv6-*.cfg` — never `backbone-discovery.yaml` (mar5 migration workaround, deliberate decoupling).

```bash
grep -h '^{%- set train_id' /etc/obn/template/nv6-*.cfg | sort -u
# Expected: a single line, e.g.   {%- set train_id = 148 -%}
# If multiple values appear, templates are inconsistent — fix before pushing config.
```

If templates need fixing, see [troubleshooting-runbook.md](troubleshooting-runbook.md) → "OBN train_id" section. **Don't `sed` `backbone-discovery.yaml`** — leave it alone whatever it currently says.

On DOSTO NEU the Fzg ID does not need to match the CCU's IP subnet (e.g. `10.179.10.x` may legitimately have `train_id: 132`). Don't "fix" that mismatch.

## Step 4b — Verify the CCU vlan7 IP is correct

The CCU's vlan7 interface (the OBS / Stadler-firewall transit VLAN) has a per-train static IP that must match what the IP-Port-Allocation PDF defines. Wrong vlan7 silently breaks Stadler reachability — the L2 fabric looks healthy but TCP probes to `172.19.X.1` fail. This is a separate concern from the Fzg ID in the OBN templates (Step 4) — the two are independent settings, both per-train, both static, both persisted via `nd-systemupdate.sh shell`.

**From your laptop:**

```
/dosto-vlan7-config <fzg-or-train#>
```

The skill computes the expected IP from the Fzg ID (using the bit-packed addressing scheme — see [.claude/skills/dosto-vlan7-config/SKILL.md](.claude/skills/dosto-vlan7-config/SKILL.md)), reads live state from the CCU, diffs against `/etc/nd-redundancy/networks.yaml` and `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection`, and prints the exact `nd-systemupdate.sh shell` recipe if a fix is needed.

**Quick formula reference** (CCU is always device 2):
```
octet 3 = 128 + (Fzg // 2)
octet 4 = (128 if Fzg is odd else 0) + 2
IP      = 172.19.<octet3>.<octet4>/17
```

Even Fzg → host `.2`. Odd Fzg → host `.130`. The Stadler FW peer is device 1 with the same odd-Fzg +128 bit: even Fzg → FW `.1`, odd Fzg → FW `.129` (`FW octet4 = 128*(Fzg%2)+1`; field-verified 2026-07-09 on Fzg 231 / box1-t41).

If the skill reports 🔴 mismatch: run the printed recipe inside `sudo /usr/sbin/nd-systemupdate.sh shell`, then `sudo /usr/local/sbin/safe_reboot`. After reboot, re-run the skill in verify mode. **Don't proceed to Step 5 until vlan7 is right** — Step 7's FW reachability check will give misleading results otherwise.

Update [fleet-status.md](fleet-status.md) `vlan7 ok` column when you confirm the state (✅ / 🔴 / 🟡 reboot-pending).

## Step 5 — Check the live network state

```bash
# Are all expected switches reachable on vlan100?
sudo dhcp-lease-list | grep -i 'a0:59:3a' | sort -t. -k4 -n
# Count: 18 (6-car) or 12 (4-car)

# Are all expected APs reachable?
sudo dhcp-lease-list | grep -i '00:14:5a' | sort -t. -k4 -n
# Count: ~21 (6-car) or ~16 (4-car)

# Did anything come back with old config or no config?
sudo dhcp-lease-list | grep -E 'dosto-0|nv6-.*-v[0-7]-'
```

What you're looking for:

| Symptom | Meaning | Action |
|---|---|---|
| Switch count short by 1+ | Switch off / rebooting / cabling fault | Wait 5 min; if still missing, run `scripts/lldp_topology_check.py` |
| AP count short by 1+ | "AP missing despite link up" pattern | Check switch port `e0-4` of the relevant FIS unit (PoE drawing? link UP?). If link UP but no AP, log in `cable-issues-register.md`, set fleet status `BLOCKED — Stadler` |
| Mixed `nv6-*-v8-NNN` and `nv6-*-v3-NNN` (or `v4-NNN`) | Partial v8 push — RSTP storm risk | Resume push: `sudo obn discover && sudo obn update c all`. Status → `IN PROGRESS` until done |
| `dosto-00000000` hostname on any switch | Switch never received OBN config | Either `train_id` not set in templates (Step 4) or cabling error preventing OBN from reaching it. Run `scripts/lldp_topology_check.py` |
| AP hostname starts with `RT610LV-…-v1-FD` | Factory config — silently blocks OBN SNMP | Apply LuCI bypass: see [troubleshooting-runbook.md](troubleshooting-runbook.md) → "Westermo AP Config Push" |

## Step 6 — Run OBN status check

```bash
sudo obn discover     # refreshes /tmp/discovery.prev.json
sudo obn validate     # green/red per device against target config/firmware
```

`obn validate` is lenient (substring match); `obn update` is strict (`endswith`). They can disagree. Trust `dhcp-lease-list` hostnames over both.

## Step 7 — Decide what to do based on what you see

Decision tree:

| What you see | What to do |
|---|---|
| All switches on `nv6-*-v8-NNN` + FW `7.4.2`, all APs on `6.11.2-0` config `v1` | Healthy. If you came for a health check go to Step 8, else log out cleanly |
| Mixed v3/v4/v8 config (any switch on old config) | **Resume v8 push.** Single switch: `sudo obn update c <ip>`. All: `sudo obn discover && sudo obn update c all`. Set status `IN PROGRESS`. Watch for crash → if any of Bugs 1–8 trigger, you skipped Step 3 |
| Switches missing entirely from discover | **Cabling fault suspected.** Copy `scripts/lldp_topology_check.py` to CCU `/tmp/`, edit `SWITCHES` / `EXPECTED_TOPOLOGY` for this consist, run. If MISMATCH found → log in `cable-issues-register.md`, set status `BLOCKED — Stadler` |
| APs in factory `RT610LV-…-v1-FD` | **AP factory bypass.** Use `scripts/push_ap_config.sh` + `scripts/apply_ap_configs.sh`. Procedure in [troubleshooting-runbook.md](troubleshooting-runbook.md) → "Westermo AP Config Push" |
| AP "link up but never appeared" | Stadler cable issue — log in `cable-issues-register.md`, set status `BLOCKED — Stadler`. Don't try to fix in software |
| `obn update c` crashes mid-run | **You skipped Step 3.** Apply patches and retry |

## Step 8 — (If asked) run the L2 health check

From your laptop:

```bash
/dosto-l2-health
```

The skill does the canonical 7-phase sweep (discovery → schema mapping → error counters → Stadler-facing trunks → throughput → FW reachability → aggregate utilisation) and writes a `findings_<train>_<date>.json` to the project root. **Move it into `findings/` afterwards.**

## Step 9 — (If asked) write the customer report

```bash
/dosto-l2-report
```

Reads the findings JSON, produces an `OBB_Fzg<NN>_*_Network_Health_Check_Report_v1.0.docx`. Save into `reports/customer/`.

## Step 10 — Log out cleanly

```bash
exit
```

If you made code changes that need to survive reboot, **double-check** they were done via `nd-systemupdate.sh shell` (not direct edits). Otherwise btrfs snapshot rollback wipes them on next reboot. The persistent-patch script lives at `/data/persist_all_patches.sh` on patched CCUs.

## Step 11 — UPDATE [fleet-status.md](fleet-status.md) — DO NOT SKIP

This is the difference between a checklist that scales across the team and one that doesn't.

1. Open [fleet-status.md](fleet-status.md). Find your train's row.
2. Update the columns that changed: `OBN patches`, `Switches v8`, `APs`, `Stadler cabling`, `FW reach`, `Health check`, `Customer report`, `Last touched`.
3. Update the `Status` column. The status set is small on purpose:
   - `DONE` — all v8 work complete, no Nomad action remaining
   - `DONE w/ Stadler` — Nomad work complete, awaiting Stadler on cabling/FW
   - `IN PROGRESS` — actively being worked on this session (only if you didn't finish but will return same day)
   - `PAUSED` — partial work; train powered off mid-run; resume on next visit
   - `BLOCKED` — Stadler cabling fault must be fixed before we can continue
   - `UNKNOWN` — visited but state not captured (only ever a placeholder, never a final state)
4. Update the `Next action` column to the **exact next command** the next person should run. Not "investigate" or "check" — a command, or a clearly-named procedure. Examples: `sudo obn discover && sudo obn update c all`, `wait for Stadler on register #4`, `run scripts/lldp_topology_check.py after re-cable`.
5. If the train is `PAUSED` or `BLOCKED` or `DONE w/ Stadler`, write or update the per-train notes section at the bottom of [fleet-status.md](fleet-status.md). Three lines minimum: what you did, why you stopped, what to verify before resuming.
6. Update the `Last updated:` line at the top of the file with today's date and your initials.

**Acid test:** if the next person to log into this train can't see "what's the next command to run" from the fleet-status row alone, you're not done with Step 11.

---

## Common false alarms (don't be fooled)

- **`ping 172.19.196.1` returns 100% loss** — Stadler firewall drops ICMP by policy. Confirm with `nc -zv 172.19.196.1 80` (should be OPEN). If TCP works, path is healthy.
- **End-of-train switches show `e0-1` DOWN** — those are physical end-of-train, no neighbour. Expected.
- **Front-coupler trunks (`e0-2` on A1/A3/B1/B3) DOWN when train solo** — expected.
- **B3 ZFR `e1-11` RX = 0** — B1 is primary, B3 is silent standby. Both share one IP. Expected.
- **`show system` returns no hostname** — VDS switches don't expose hostname this way. Use config fingerprint (see [CLAUDE.md](CLAUDE.md) Phase 2 mapping).
- **`obn validate` shows green but config is wrong** — `obn validate` uses substring match, `obn update` uses `endswith`. They disagree. Trust `dhcp-lease-list` hostname.

## Real red flags

- **Non-zero `RX crc errors` (sustained)** → cable / SFP fault at link end-points
- **Non-zero `carrier false`** → physical-layer instability (vibration, surge protection)
- **Non-zero `pause frames received`** → upstream egress congestion
- **Multiple STP roots** → RSTP unstable, find the link causing TCNs
- **`obn update c` crashes** when you thought patches were applied → check Step 3 again, partial patches leave crash modes open
- **TCP probe to FW fails AND vlan7 has drops** → real path break, escalate to Stadler

## Reference paths

- [CLAUDE.md](CLAUDE.md) — methodology, architecture, schema reading
- [troubleshooting-runbook.md](troubleshooting-runbook.md) — detailed procedures (LLDP cabling check, OBN bug fixes, AP factory bypass, train_id rules)
- [cable-issues-register.md](cable-issues-register.md) — fleet-wide cabling fault log
- [fleet-status.md](fleet-status.md) — **per-train rollout status (read first, update last)**
- `scripts/fix_obn.py` — patches OBN bugs 1–7 (idempotent); plus `fix_obn_bug8.py`, `fix_obn_bug9_pysnmp_thread_safety.py`, `fix_obn_bug10_report_dosto_neu_bfs.py` for the remaining 3 (all 10 needed; 9 prevents parallel-SNMP crash, 10 prevents `obn report` hang+leak)
- `scripts/lldp_topology_check.py` — verify Stadler trunk cabling
- `scripts/push_ap_config.sh` / `apply_ap_configs.sh` — AP factory-config bypass
- `docs/switch_user_manual.pdf` — full VDS switch reference
- `docs/ND-DEL-OBB-035-IPA-NNN_NV_*.pdf` — per-train IPv4 schema (one per Fzg ID we have)
