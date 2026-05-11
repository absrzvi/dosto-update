---
name: dosto-obn-patches
description: Verify and apply the 8 known OBN bug fixes on a DOSTO CCU. Reads the running OBN code via SSH, greps for each bug's patch marker, reports what's patched / what's missing, and (in --apply mode) prints the exact recipe to scp the fix scripts and run them inside btrfs ro-toggle. In --persist mode detects whether the CCU has the canonical nd-systemupdate.sh or the fleet-wide .dont rename and prints the matching shell recipe (staging scripts in /var/tmp/, which is bind-mounted into the chroot — /tmp is NOT) to bake patches into a new snapshot. Use whenever you're about to run obn update on a CCU, after every CCU reboot (patches may have been wiped), or to fill in the OBN patches column of fleet-status.md. The skill never edits the CCU directly — the engineer runs the printed recipe.
---

# DOSTO OBN Patches — Verify and Apply

The 8 known OBN bugs (documented in [troubleshooting-runbook.md](troubleshooting-runbook.md)) crash or silently corrupt `obn update f all` and `obn update c all`. Without these fixes, partial updates leave the consist in a mixed v3/v4/v8 state which causes RSTP topology storms.

**Always apply all 8 together.** Partial patches are worse than vanilla — applying only some leaves crash modes open, so an `obn update` run dies mid-way and writes the partial state to the consist.

## When to use

- **Step 3 of [train-login-checklist.md](train-login-checklist.md)** — every train, every visit.
- After any CCU reboot — btrfs may have rolled back to a pre-patch snapshot.
- Before any `obn update f all` or `obn update c all` — even if "we just did this last week".
- When fleet-status `OBN patches` column is ❓ or `<8/8`.

## Output modes

Every mode (`--check`, `--apply`, `--persist`) supports two output flavours:

- **default — engineer-readable.** Tables + verdict + recipe-when-needed. What you see when running this manually.
- **`--json` — machine-readable.** A single JSON line on stdout matching the `skill_outputs[]` shape from [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md). Subagents pass `--json`; engineers don't.

The diagnostic procedure is identical in both modes — `--json` is purely a formatter switch. The skill collects the same intermediate representation either way; the formatter decides whether to render a table or emit JSON.

### `--json` shape for `--check` mode

Subagent emits this as one element of `skill_outputs[]`:

```json
{
  "skill": "dosto-obn-patches",
  "mode": "check",
  "schema_version": "1",
  "verdict": "vanilla|partial|all_patched|all_persisted",
  "raw": {
    "ccu_hostname": "box1-t10",
    "ccu_uptime_seconds": 8520,
    "btrfs_subvol": "/.snapshots/run1",
    "bug1_count": 0,
    "bug2_count": 0,
    "bug3_count": 0,
    "bug4_count": 0,
    "bug5_count": 0,
    "bug6_count": 0,
    "bug7_count": 0,
    "bug8_count": 0,
    "patches_applied_total": 0,
    "patches_expected_total": 8,
    "is_persisted": false,
    "train_id_template": "{%- set train_id = 132 -%}",
    "train_id_template_consistent": true,
    "vlan7_live": "172.19.194.2/17",
    "obn_version": "2.2.23",
    "nd_systemupdate_path": "/usr/sbin/nd-systemupdate.sh.dont",
    "nd_systemupdate_dont_renamed": true,
    "auto_update_blocked": true
  }
}
```

`verdict` semantics:
- `vanilla` — `patches_applied_total == 0`
- `partial` — `0 < patches_applied_total < 8`
- `all_patched` — `patches_applied_total == 8` AND `is_persisted == false`
- `all_persisted` — `patches_applied_total == 8` AND `is_persisted == true` (btrfs subvol is a `release`-tier `runN`, not the temporary `run` snapshot)

`is_persisted` is computed from the btrfs subvol path — `/.snapshots/release` or `/.snapshots/runN` (where N > 1) suggests persistence; bare `/.snapshots/run` or `/.snapshots/work` doesn't.

`train_id_template_consistent` is `true` when `grep -h "^{%- set train_id" /etc/obn/template/nv6-*.cfg | sort -u` returns exactly 1 line. False = templates are mixed (partial fix from a previous session — needs cleanup).

`obn_version` from `cat /usr/share/obn/VERSION`. `null` if file doesn't exist.

### `--json` shape for `--apply` and `--persist` modes

These modes don't *do* the work themselves — they print recipes. The `--json` shape adds a `recipe` field with the multi-line shell commands the engineer should run:

```json
{
  "skill": "dosto-obn-patches",
  "mode": "apply",
  "schema_version": "1",
  "verdict": "recipe_ready",
  "raw": { ... same as --check, captured before recipe was generated ... },
  "recipe": "# === STEP 1: From your laptop ===\nscp -i ...\n\n# === STEP 2: SSH to CCU ===\n..."
}
```

For `--persist` mode with fold-in flags, `raw` additionally contains a `fold_in` block reporting the read-only sibling-skill verdicts captured during the same diagnostic SSH probe:

```json
"fold_in": {
  "vlan7": {
    "requested": true,
    "fixable": true,
    "fzg_input": 132,
    "expected_ip": "172.19.194.2/17",
    "current_nmconn_ip": "172.19.215.130/17",
    "sibling_verdict": "both_wrong"
  },
  "fzg_id": {
    "requested": true,
    "fixable": true,
    "fzg_input": 132,
    "expected_template_line": "{%- set train_id = 132 -%}",
    "variant": "nv6",
    "templates_expected": 18,
    "sibling_verdict": "broken_formula"
  }
}
```

`requested` is `true` when the engineer passed `--with-vlan7` / `--with-fzg-id`. `fixable` is `true` when the sibling skill's `--check` returned a verdict that produces a recipe (`both_wrong` for vlan7; `broken_formula`, `hardcoded_wrong`, or `inconsistent` for fzg-id). When `requested && !fixable`, the corresponding sub-block is **omitted from the recipe** and the JSON output notes "already correct, fold-in skipped" for that fix. When `!requested`, the field is `null`.

Subagent treats `recipe` as the action plan to surface to the orchestrator. Orchestrator presents it to the human at the relevant approval gate (Gates 1-2 from the autonomy boundary).

## Modes

The skill has three modes, used in sequence:

| Mode | What it does | When to use |
|---|---|---|
| `--check` (default) | Read-only diagnostic. Reports per-bug status (✅ patched / 🔴 missing). Doesn't touch the CCU. | First. Always start here. |
| `--apply` | Prints the recipe to scp the fix scripts and run them under `btrfs ro=false`. Does NOT execute. | After `--check` shows gaps. |
| `--persist` | Prints the `nd-systemupdate.sh shell` recipe to bake patches into a new btrfs snapshot. Optional fold-in flags (`--with-vlan7 <Fzg>`, `--with-fzg-id <Fzg>`) extend the same chroot session with vlan7 IP and/or template `train_id` fixes — single-promote pattern, no second reboot. | After `--apply` succeeds, when patches need to survive reboot (recommended for any train you'll revisit). |

Invocation examples:
- `/dosto-obn-patches 10.179.1.1` → check mode
- `/dosto-obn-patches 10.179.2.1 --apply` → check then print apply recipe
- `/dosto-obn-patches 10.179.2.1 --persist` → print persistence recipe, OBN-only (assumes apply already done in this session)
- `/dosto-obn-patches 10.179.10.1 --persist --with-vlan7 132` → OBN + vlan7 fix folded into one chroot session
- `/dosto-obn-patches 10.179.10.1 --persist --with-fzg-id 132` → OBN + template `train_id` fix folded into one chroot session
- `/dosto-obn-patches 10.179.10.1 --persist --with-vlan7 132 --with-fzg-id 132` → all three folded — single-promote pattern (handoff lesson 1)

## The 8 bugs and their grep markers

The skill detects whether each bug is patched by grepping for a deterministic string the patch inserts into the file. These are the canonical markers:

| # | File | Patch marker (presence = patched) | Source script |
|---|---|---|---|
| 1 | `/usr/share/obn/lib/device/vendor/vdsrail.py` | `default image is now` (in a regex line) | `scripts/fix_obn.py` (canonical) or `scripts/fix_bug1_regex.py` (variant) |
| 2 | `/usr/share/obn/lib/device/vendor/vdsrail.py` | `if not result:` (None guard, appears in 2 polling loops) | `scripts/fix_obn.py` |
| 3 | `/usr/share/obn/lib/device/snmpdevice.py` | `except KeyError:\n            return {}` | `scripts/fix_obn.py` |
| 4 | `/usr/share/obn/lib/report/device.py` | `bool(self.firmware) and not self.firmware.endswith` | `scripts/fix_obn.py` |
| 5 | `/usr/share/obn/cli/update.py` | `Bug 5 fix: pre-populate tftp_allowed ipset` | `scripts/fix_obn.py` |
| 6 | `/usr/share/obn/lib/tree.py` | `neighbour not in this consist` | `scripts/fix_obn.py` (canonical) or `scripts/fix_obn_bugs67.py` (fallback) |
| 7 | `/usr/share/obn/lib/device/vendor/vdsrail.py` | `if hostname is not None:` (followed by `self._snmp_set`) | `scripts/fix_obn.py` (canonical) or `scripts/fix_obn_bugs67.py` (fallback) |
| 8 | `/usr/share/obn/lib/report/device.py` | `bool(self.config) and not self.config.endswith` | `scripts/fix_obn_bug8.py` |

## Procedure

### `--check` mode (always run first)

SSH to the CCU and grep all 8 markers + collect cross-check context in one round-trip:

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
echo "=== HOST ==="
hostname
uptime
echo "=== Bug 1 (vdsrail regex) ==="
sudo grep -c "default image is now" /usr/share/obn/lib/device/vendor/vdsrail.py
echo "=== Bug 2 (vdsrail None guards — expect 2 if patched) ==="
sudo grep -c "if not result:" /usr/share/obn/lib/device/vendor/vdsrail.py
echo "=== Bug 3 (snmpdevice KeyError) ==="
sudo grep -c "except KeyError:" /usr/share/obn/lib/device/snmpdevice.py
echo "=== Bug 4 (device.py firmware None) ==="
sudo grep -c "bool(self.firmware) and not self.firmware.endswith" /usr/share/obn/lib/report/device.py
echo "=== Bug 5 (update.py ipset) ==="
sudo grep -c "Bug 5 fix: pre-populate tftp_allowed ipset" /usr/share/obn/cli/update.py
echo "=== Bug 6 (tree.py cross-consist) ==="
sudo grep -c "neighbour not in this consist" /usr/share/obn/lib/tree.py
echo "=== Bug 7 (vdsrail reboot hostname) ==="
sudo grep -c "if hostname is not None:" /usr/share/obn/lib/device/vendor/vdsrail.py
echo "=== Bug 8 (device.py config None) ==="
sudo grep -c "bool(self.config) and not self.config.endswith" /usr/share/obn/lib/report/device.py
echo "=== btrfs subvol (look for run<N> ===" 
mount | grep " on / " | head -1
echo "=== train_id template (should be hardcoded number, NOT 128+train_id) ==="
grep -h "^{%- set train_id" /etc/obn/template/nv6-*.cfg 2>/dev/null | sort -u | head -3
echo "=== vlan7 live IP ==="
ip -br addr show vlan7
echo "=== nd-systemupdate (.dont rename = auto-update blocked, fleet-standard) ==="
if [ -f /usr/sbin/nd-systemupdate.sh.dont ]; then echo "NDSU=/usr/sbin/nd-systemupdate.sh.dont"; \
elif [ -f /usr/sbin/nd-systemupdate.sh ]; then echo "NDSU=/usr/sbin/nd-systemupdate.sh"; \
else echo "NDSU=MISSING"; fi
# NOTE: use `-f` (regular file exists) NOT `-x` (executable). nd-systemupdate.sh.dont
# on this fleet is mode 0500 (-r-xr--r--), owner=root — `-x` returns false for the
# `developer` user we SSH as, even though the file is fully usable via `sudo`.
# Validated 2026-05-09 on box1-t47.
'
```

The extra fields (`train_id` template line, vlan7 IP) aren't strictly part of the OBN patches check, but they cost nothing to grab in the same SSH session and they let you spot related problems that often coexist with vanilla-patch state. **Always include them** — see "Cross-checks" below.

Interpret each `grep -c` count:
- Bug 1: 1+ → patched, 0 → missing
- Bug 2: 2+ → both polling loops patched, 1 → only one of two patched (bad, partial state), 0 → missing
- Bugs 3–8: 1+ → patched, 0 → missing

Print a status table:

```
Bug | Status        | File
----|---------------|----------------------------------------
 1  | ✅ PATCHED     | vdsrail.py (set_firmware_version)
 2  | 🔴 PARTIAL 1/2 | vdsrail.py (polling loops — 1 of 2 guarded)
 3  | ✅ PATCHED     | snmpdevice.py (KeyError guard)
 4  | ✅ PATCHED     | device.py (firmware None guard)
 5  | 🔴 MISSING     | update.py (TFTP ipset)
 6  | ✅ PATCHED     | tree.py (cross-consist guard)
 7  | ✅ PATCHED     | vdsrail.py (reboot hostname)
 8  | 🔴 MISSING     | device.py (config None guard)

Verdict: 🔴 5/8 patched, 3 missing/partial — apply needed
btrfs subvolume: <whatever the mount line shows>
Uptime: <X days>  (recent reboot? then patches may have been wiped from the run<N> snapshot)
```

**Verdicts:**
- ✅ **8/8 patched** → done. Suggest `--persist` only if fleet-status doesn't yet say `persisted`. Otherwise exit clean.
- 🟡 **8/8 in this snapshot but uptime is fresh** → looks good but verify by running an `obn` command first; some users have seen patches survive in `/usr/share/obn` but lose them on next reboot.
- 🔴 **<8/8** → recommend `--apply`. Don't proceed past Step 3 of the train-login checklist until 8/8.

Update fleet-status `OBN patches` column accordingly:
- 8/8 in btrfs `release` snapshot (default GRUB) → `persisted (run<N>)`
- 8/8 in current state but not yet promoted via `nd-systemupdate.sh shell` → `8/8 (not persisted — will wipe on reboot)`
- partial → `<N>/8`
- 0/8 → `0/8 (vanilla)`

### Cross-checks (always report alongside the bug table)

The extra fields captured in `--check` mode are designed to surface related issues that frequently coexist with a vanilla-patch CCU. Always evaluate and report:

#### A. `train_id` template line — looking for the broken `128 +` formula

The `--check` SSH grabs `grep -h "^{%- set train_id" /etc/obn/template/nv6-*.cfg | sort -u`. Three possible outputs:

| Output | Meaning | Action |
|---|---|---|
| (one line, e.g. `{%- set train_id = 132 -%}`) | ✅ hardcoded Fzg, mar5-compliant | OK. Note the value reported. |
| `{%- set train_id = 128 + train_id -%}` | 🔴 broken formula — same bug that caused Fzg 133 cascade | Fix during `--persist` chroot session. Replace with hardcoded Fzg from the IP-Port-Allocation PDF. |
| (multiple different lines) | 🔴 inconsistent templates — partial fix from a previous session | Fix all 18 to a single hardcoded Fzg. |
| (empty) | 🟡 templates may be elsewhere or older format | Verify templates exist; check `nv4-*.cfg` instead. |

Don't suggest auto-applying the fix — the engineer must confirm the right Fzg from the IP-Port-Allocation PDF before any sed replacement. The skill should *report* the finding and *recommend* the fix, not perform it.

#### B. vlan7 IP — decoding back to encoded Fzg

The `--check` SSH grabs `ip -br addr show vlan7`. Decode the IP to an encoded Fzg using the inverse of the [vlan7 formula](../dosto-vlan7-config/SKILL.md):

```python
# Given live vlan7 IP "172.19.<o3>.<o4>/17":
encoded_fzg = ((o3 - 128) << 1) | (o4 >> 7)
encoded_device = o4 & 0x7F
# CCU should be device 2.
```

Compare the encoded Fzg against:
1. The `train_id` from the template (above) — usually they should match on DOSTO NEU consists, **but not always** (the auto-memory rule explicitly says they can be intentionally decoupled — e.g. box1-t11 / 10.179.11.x has `train_id 11` but cfg files say `131`). Don't flag a mismatch as wrong; flag it as **needs verification against the IP-Port-Allocation PDF**.
2. The Fzg ID from the IP-Port-Allocation PDF (if the engineer has supplied it via `--fzg <NN>` or named the train).

**Cases:**

| encoded vlan7 Fzg matches PDF Fzg? | template `train_id` matches? | Verdict |
|---|---|---|
| ✅ | ✅ | Everything aligned. ✅ all green. |
| ✅ | ❌ | vlan7 is right; template needs hardcoding to PDF Fzg. Common on freshly-commissioned CCUs. |
| ❌ | ✅ | **vlan7 is wrong** — template is right but the static vlan7 IP doesn't match the train. Stadler-side reachability broken. → `/dosto-vlan7-config <fzg>` to get fix recipe. |
| ❌ | ❌ | Both wrong — full reset needed. Fix template first, vlan7 second, in same chroot session. |

Validated example (2026-05-09, real train):
- box1-t47 / `10.179.47.1`, confirmed Fzg 130 (4736-102)
- Live vlan7 = `172.19.215.130/17` → decoded encoded-Fzg = `((215-128)<<1)|1 = 175` → 🔴 mismatch
- Template = `{%- set train_id = 128 + train_id -%}` → 🔴 broken formula
- Final verdict: 🔴 OBN 0/8 + 🔴 vlan7 wrong + 🔴 template broken — three independent fixes, must be done in order (patches → template → vlan7) inside one or two `nd-systemupdate.sh shell` sessions.

The decoding gives you the answer in seconds without needing the engineer to do mental arithmetic. Always print both the decoded value and the matching/mismatching fzg.

#### C. nd-systemupdate auto-update exposure

The `--check` SSH grabs the NDSU path. Three possible outcomes:

| Probe output | Meaning | Verdict |
|---|---|---|
| `NDSU=/usr/sbin/nd-systemupdate.sh.dont` | ✅ Fleet-standard. The `.dont` rename blocks `nd-auto-system-update.timer` (fires nightly 0,1,2,3,4:21 UTC). Persisted patches are safe across reboots. | OK. Continue. |
| `NDSU=/usr/sbin/nd-systemupdate.sh` | 🟡 **Auto-update exposed.** Next 0-4am cycle will promote a vanilla-OBN snapshot from Puppet env `dostoneu_migration_mar5` and clobber any persisted patches. | Re-rename to `.dont` ASAP, ideally inside the same `--persist` chroot session (step 3.5 of the persist recipe). |
| `NDSU=MISSING` | 🔴 Neither file exists. Wrong CCU image, hand-deleted, or wrong path. | Don't print a `--persist` recipe. Investigate. |

Confirmed exposed as of 2026-05-09: **box1-t1 (Fzg 133)** — re-rename next visit before doing anything else. Fleet convention is `.dont` everywhere until R&D upstreams the OBN patches into the Puppet env.

### Pre-recipe: detect nd-systemupdate filename and stage location

Before printing any `--apply` or `--persist` recipe, run this single SSH probe and use the result to template the recipe:

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
# NOTE: use `-f` (regular file exists) NOT `-x` (executable). On this fleet the file
# is mode 0500 owner=root — `-x` returns false for the `developer` SSH user even
# though the file works fine via `sudo`. Validated 2026-05-09 on box1-t47.
if [ -f /usr/sbin/nd-systemupdate.sh.dont ]; then
  echo "NDSU=/usr/sbin/nd-systemupdate.sh.dont"
elif [ -f /usr/sbin/nd-systemupdate.sh ]; then
  echo "NDSU=/usr/sbin/nd-systemupdate.sh"
else
  echo "NDSU=MISSING"
fi
ls -ld /var/tmp /tmp 2>/dev/null
'
```

**Interpret:**

| Output | Meaning | Recipe action |
|---|---|---|
| `NDSU=/usr/sbin/nd-systemupdate.sh.dont` | Fleet-standard. `.dont` rename blocks the nightly `nd-auto-system-update.timer` (see auto-memory `project_nd_systemupdate_dont.md`). | Use this exact path in all `sudo nd-systemupdate.sh.dont shell` invocations. |
| `NDSU=/usr/sbin/nd-systemupdate.sh` | 🟡 **Train is exposed to nightly auto-update.** Will clobber any persisted patches on next Sun/weekday-night cycle. | Recipe still works (canonical name), but **append a remediation step**: re-rename to `.dont` after the promote (see `--persist` step 3.5). |
| `NDSU=MISSING` | 🔴 Neither file exists. Wrong CCU image or hand-deleted. | Don't print a recipe — flag for engineer. |

The `--check` SSH probe (next section) folds this detection in, so the JSON `raw` block always carries:

```json
"nd_systemupdate_path": "/usr/sbin/nd-systemupdate.sh.dont",
"nd_systemupdate_dont_renamed": true,
"auto_update_blocked": true
```

When `nd_systemupdate_dont_renamed == false` AND `nd_systemupdate_path != null`, the cross-check verdict adds `🟡 auto-update exposed — re-rename .dont after promote`.

### `--apply` mode (only after `--check` showed gaps)

**Caller type matters here.** The recipe below is engineer-facing — assumes the engineer runs SCP from their laptop. **Subagents (per `dosto-train-worker.md`) cannot run SCP** — the harness denies SCP from spawned subagents. Subagent flow per audit finding F1-B (2026-05-11):

1. Subagent emits a `status: ERROR` report with `next_action: "Parent: please SCP the 4 fix scripts to /var/tmp/ on <ccu-ip>; then send results to resume."` per the F1-C handoff protocol in `dosto-train-worker.md`.
2. Parent (orchestrator / top-level session) executes the SCP recipe below from its session, then `SendMessage`'s the worker with the result.
3. Worker resumes at STEP 2 — SSH the run-the-scripts commands work fine from subagents (they're plain one-liners, not heredocs or SCP).

Engineer-facing recipe (with `<ccu-ip>` filled in):

```bash
# === STEP 1: From your laptop (engineer) OR parent session, copy the 4 fix scripts to the CCU ===
# NOTE: subagents skip this step — parent handles it. See F1-B note above.
# Stage in /var/tmp/, NOT /tmp/. Reason: the chroot used by --persist
# bind-mounts /var/tmp (per DIR_TO_MOUNT in nd-systemupdate.sh) but NOT
# /tmp. Staging here lets the same files be reused inside the chroot
# without re-scp.
# IMPORTANT: developer user can't write to /var/tmp directly — SCP to /tmp first, then sudo mv.
scp -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/fix_obn.py" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/fix_obn_bugs67.py" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/fix_obn_bug8.py" \
    "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/scripts/fix_bug1_regex.py" \
    developer@<ccu-ip>:/tmp/
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> \
    'sudo mv /tmp/fix_obn.py /tmp/fix_obn_bugs67.py /tmp/fix_obn_bug8.py /tmp/fix_bug1_regex.py /var/tmp/ && sudo chmod +x /var/tmp/fix_*.py'

# === STEP 2: SSH to the CCU and run them under btrfs ro-toggle ===
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>

# Inside the CCU:
sudo btrfs property set / ro false

# Run the canonical script first (covers Bugs 1-7)
sudo python3 /var/tmp/fix_obn.py

# If fix_obn.py reported "PATTERN NOT FOUND" for Bug 6 or Bug 7,
# the file was already in a partial state — run the fallback for those:
sudo python3 /var/tmp/fix_obn_bugs67.py

# If fix_obn.py reported "PATTERN NOT FOUND" for Bug 1 specifically,
# run the regex variant:
sudo python3 /var/tmp/fix_bug1_regex.py

# Always run Bug 8 (not in fix_obn.py):
sudo python3 /var/tmp/fix_obn_bug8.py

# Re-lock root
sudo btrfs property set / ro true

# === STEP 3: Re-run the skill in --check mode to verify 8/8 ===
exit
```

**Note on `/var/tmp/` choice:** `/var/tmp` is bind-mounted into the chroot (per `DIR_TO_MOUNT="boot/grub data dev var/cache var/tmp"` in `nd-systemupdate.sh`); `/tmp` is NOT. Staging in `/var/tmp/` lets the *same* script files be reused inside the `--persist` chroot session without re-scp. Caveat: `/var/tmp` is tmpfs on this image and **wipes on reboot** — if a reboot happens between `--apply` and `--persist`, re-scp the scripts before the chroot.

After the engineer reports back that all 8 markers are now present, the skill should suggest running `--persist` to bake the patches into a new btrfs snapshot (otherwise they wipe on next reboot).

### `--persist` mode

This is the only path to surviving CCU reboots. Direct edits to `/usr/share/obn/` are wiped when btrfs rolls back to the previous "release" snapshot.

**Substitute `<NDSU>` below with the path detected in the pre-recipe probe.**
Fleet-standard is `/usr/sbin/nd-systemupdate.sh.dont`. If the pre-recipe found canonical `/usr/sbin/nd-systemupdate.sh`, use that — and do step 3.5.

```bash
# === Persistent-patch flow via nd-systemupdate.sh shell ===

# 1. From your laptop, ensure the 4 fix scripts are still on the CCU /var/tmp/.
#    /var/tmp is tmpfs on this image — if a reboot happened between --apply
#    and --persist, re-scp the scripts before continuing.
ls /var/tmp/fix_obn*.py /var/tmp/fix_bug1_regex.py
# If missing, re-scp them (see --apply STEP 1).

# 2. SSH to the CCU and drop into the persistent-edit chroot:
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
sudo <NDSU> shell
# e.g. sudo /usr/sbin/nd-systemupdate.sh.dont shell  (fleet standard)
#      sudo /usr/sbin/nd-systemupdate.sh shell       (auto-update-exposed CCU)

# 3. INSIDE THE CHROOT, re-run the same patch sequence.
#    /var/tmp is bind-mounted in via DIR_TO_MOUNT, so the scripts staged
#    in step 1 are visible at the same path here:
sudo python3 /var/tmp/fix_obn.py
sudo python3 /var/tmp/fix_obn_bugs67.py     # only if fix_obn.py couldn't apply Bug 6/7
sudo python3 /var/tmp/fix_bug1_regex.py     # only if fix_obn.py couldn't apply Bug 1
sudo python3 /var/tmp/fix_obn_bug8.py

# 3.5. (ONLY if pre-recipe showed nd_systemupdate_dont_renamed == false —
#       i.e. <NDSU> was the canonical /usr/sbin/nd-systemupdate.sh)
#      Re-rename to .dont so the nightly nd-auto-system-update.timer doesn't
#      promote a vanilla-OBN snapshot from Puppet env and clobber these
#      patches on the next 0-4am cycle:
sudo mv /usr/sbin/nd-systemupdate.sh /usr/sbin/nd-systemupdate.sh.dont

# 4. Verify all 8 markers inside the chroot:
sudo grep -c "default image is now"     /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "if not result:"           /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "except KeyError:"         /usr/share/obn/lib/device/snmpdevice.py
sudo grep -c "bool(self.firmware)"      /usr/share/obn/lib/report/device.py
sudo grep -c "Bug 5 fix:"               /usr/share/obn/cli/update.py
sudo grep -c "neighbour not in this"    /usr/share/obn/lib/tree.py
sudo grep -c "if hostname is not None:" /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "bool(self.config)"        /usr/share/obn/lib/report/device.py
# Expected: 1, 2, 1, 1, 1, 1, 1, 1

# 5. Exit the chroot — promotes work → release → new run<N>, sets default GRUB entry
exit

# 6. Reboot into the new snapshot
sudo /usr/local/sbin/safe_reboot
```

### Fold-in mode (single-promote pattern)

The OBN-only `--persist` recipe above is correct on its own, but if the train *also* needs vlan7 or template `train_id` fixes, applying them in a separate chroot session means a second promote and a second reboot. This is the "two-promote pattern" we hit during Fzg 132 commissioning (handoff lesson 1) — wasteful, and the second promote wipes any non-bind-mounted state from the first.

The fold-in flags `--with-vlan7 <Fzg>` and `--with-fzg-id <Fzg>` extend the same chroot session with the equivalent fixes from [`dosto-vlan7-config`](../dosto-vlan7-config/SKILL.md) and [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md). One chroot, one promote, one reboot.

#### Inputs and validation

Before printing the recipe, the skill validates:

1. Both `--with-vlan7` and `--with-fzg-id` accept a positive integer Fzg in `[1, 255]`.
2. **If both flags are passed, their values must match.** A mismatch (`--with-vlan7 132 --with-fzg-id 133`) almost always means the engineer is confused about which train they're touching — abort with a clear error before printing any recipe.
3. The skill's own `--check` SSH probe is extended in fold-in mode to capture the sibling-skill diagnostic state in one round-trip:
   - For `--with-vlan7`: read `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection` (the `address1=` line) and live `ip -br addr show vlan7`.
   - For `--with-fzg-id`: list `/etc/obn/template/nv*-*.cfg` and the unique `train_id` directives.
   The skill does *not* shell out to the sibling slash-commands; it inlines the read-only logic to keep the SSH count to one (matters under flaky train cellular).
4. Compute each sibling's verdict using the diff matrix from that sibling's SKILL.md. Set `fold_in.<sub>.fixable` accordingly.
5. If a fold-in flag was requested but the sibling verdict is "already correct" (vlan7 `all_match`, fzg-id `all_match`), **omit that sub-block from the recipe** and emit a one-liner: `fold-in vlan7 skipped — already correct (live=172.19.194.2/17)`. Continue with the rest of the recipe.

This last rule matters: the sub-recipe `assert old in content` patterns will fail loudly if the live state doesn't match what we read pre-chroot, so silently emitting them when no fix is needed would just abort the chroot session for no reason.

#### Fold-in recipe shape (all three folded)

When all three fixes are folded and all three are fixable, the printed recipe becomes:

```bash
# === STEP 1: From your laptop, ensure the 4 fix scripts are on the CCU /var/tmp/ ===
ls /var/tmp/fix_obn*.py /var/tmp/fix_bug1_regex.py
# If missing, re-scp them (see --apply STEP 1).

# === STEP 2: SSH to the CCU and drop into the persistent-edit chroot ===
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
sudo <NDSU> shell

# === STEP 3a: OBN patches ===
sudo python3 /var/tmp/fix_obn.py
sudo python3 /var/tmp/fix_obn_bugs67.py     # only if fix_obn.py couldn't apply Bug 6/7
sudo python3 /var/tmp/fix_bug1_regex.py     # only if fix_obn.py couldn't apply Bug 1
sudo python3 /var/tmp/fix_obn_bug8.py

# === STEP 3b: Fzg-ID template fix (folded from dosto-fzg-id-check) ===
sudo python3 <<'PYEOF'
import glob, sys
paths = sorted(glob.glob('/etc/obn/template/<VARIANT_GLOB>'))
expected = <TEMPLATES_EXPECTED>
if len(paths) != expected:
    sys.exit(f'expected {expected} templates, got {len(paths)} — aborting')
target = '{%- set train_id = <FZG> -%}\n'
replaced = 0
unchanged = 0
for p in paths:
    with open(p) as f:
        lines = f.readlines()
    if not lines:
        sys.exit(f'{p} is empty — aborting')
    if not lines[0].startswith('{%- set train_id'):
        sys.exit(f'first line of {p} is not a train_id directive — aborting')
    if lines[0] == target:
        unchanged += 1
        continue
    lines[0] = target
    with open(p, 'w') as f:
        f.writelines(lines)
    replaced += 1
print(f'PATCHED {replaced} fzg-id templates, {unchanged} already correct, {len(paths)} total')
PYEOF

# === STEP 3c: vlan7 nmconnection fix (folded from dosto-vlan7-config) ===
sudo python3 <<'PYEOF'
path = '/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection'
with open(path) as f:
    content = f.read()
old = 'address1=<CURRENT_NMCONN_IP>'
new = 'address1=<EXPECTED_VLAN7_IP>'
assert old in content, f'pattern {old!r} not found in {path} — live state changed since pre-chroot read; aborting before any other change is committed'
content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
print('PATCHED nmconnection vlan7 IP')
PYEOF

# === STEP 3.5: Re-rename .sh → .sh.dont (only if pre-recipe found canonical name) ===
sudo mv /usr/sbin/nd-systemupdate.sh /usr/sbin/nd-systemupdate.sh.dont   # (only if applicable)

# === STEP 4: Verify all markers inside the chroot ===
# This step reads the chroot's view of /, which IS the new snapshot in-flight.
# All paths below are inside the chroot — the live (pre-reboot) filesystem is unchanged.
# OBN patches (expected counts: 1, 2, 1, 1, 1, 1, 1, 1):
sudo grep -c "default image is now"     /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "if not result:"           /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "except KeyError:"         /usr/share/obn/lib/device/snmpdevice.py
sudo grep -c "bool(self.firmware)"      /usr/share/obn/lib/report/device.py
sudo grep -c "Bug 5 fix:"               /usr/share/obn/cli/update.py
sudo grep -c "neighbour not in this"    /usr/share/obn/lib/tree.py
sudo grep -c "if hostname is not None:" /usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "bool(self.config)"        /usr/share/obn/lib/report/device.py
# Fzg-ID template — exactly one unique line, value = <FZG>:
# (Use glob — template filenames vary across CCUs: nv6-NNN-XX.cfg, nv6-XX-vY.cfg, etc. NEVER hardcode a sample filename.)
echo "template count:"
ls /etc/obn/template/<VARIANT_GLOB> | wc -l   # expect <TEMPLATES_EXPECTED>
echo "train_id unique values:"
grep -h "^{%- set train_id" /etc/obn/template/<VARIANT_GLOB> | sort -u   # expect single line: {%- set train_id = <FZG> -%}
# vlan7 nmconnection — single matching address1 line:
grep "^address1=" /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection
# expect: address1=<EXPECTED_VLAN7_IP>,...

# === STEP 5: Exit chroot — promotes work → release → new run<N> ===
exit

# === STEP 5.5: Post-exit verification — mount the new snapshot read-only ===
# Per audit finding F3 (2026-05-11): the chroot's in-chroot greps in Step 4 are
# necessary but NOT sufficient. If a sed/sub-recipe missed a file (e.g. unexpected
# template filename pattern), Step 4 inside the chroot will still report "all good"
# because it's looking at the same files the sed already processed. The chroot's
# view of "/" is the new snapshot, but we want one more verification from OUTSIDE
# the chroot, against the actual snapshot subvol, before committing the reboot.
#
# Why this matters: if we reboot into a broken snapshot, recovery requires
# bootloader-time intervention. Mount-RO checking before reboot is cheap insurance.

# Find the new snapshot — should be the one just created during exit:
NEW_SNAPSHOT=$(sudo btrfs subvolume list / | grep snapshots/run | sort -k2 -n | tail -1 | awk '{print $NF}')
echo "verifying snapshot: $NEW_SNAPSHOT"

# Mount it read-only (does NOT affect live state):
sudo mkdir -p /mnt/snapshot-check
sudo mount -o subvol=$NEW_SNAPSHOT,ro /dev/sda2 /mnt/snapshot-check

# Re-verify the three classes of fix, against the actual snapshot files:
echo "--- OBN patches in snapshot ---"
sudo grep -c "default image is now" /mnt/snapshot-check/usr/share/obn/lib/device/vendor/vdsrail.py
sudo grep -c "Bug 5 fix:"           /mnt/snapshot-check/usr/share/obn/cli/update.py
sudo grep -c "bool(self.config)"    /mnt/snapshot-check/usr/share/obn/lib/report/device.py
# (Sampling 3 of 8 markers — if any of these is 0, run the full 8-marker check.)

echo "--- train_id in snapshot templates ---"
ls /mnt/snapshot-check/etc/obn/template/<VARIANT_GLOB> | wc -l   # expect <TEMPLATES_EXPECTED>
grep -h "^{%- set train_id" /mnt/snapshot-check/etc/obn/template/<VARIANT_GLOB> | sort -u
# expect single line: {%- set train_id = <FZG> -%}

echo "--- vlan7 in snapshot ---"
grep "^address1=" /mnt/snapshot-check/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection
# expect: address1=<EXPECTED_VLAN7_IP>,...

# Cleanup the read-only mount — does NOT affect the snapshot:
sudo umount /mnt/snapshot-check
sudo rmdir /mnt/snapshot-check

# Decision point: if ANY of the above verifications failed, DO NOT REBOOT.
# Instead: re-enter the chroot, fix the missing file, exit again. The chroot
# creates a new runN each time; the old (broken) runN persists but is ignored
# on next boot because GRUB default is the latest.

# === STEP 6: Reboot into the new snapshot ===
sudo /usr/local/sbin/safe_reboot
```

**On the snapshot-naming surprise** (audit finding F4): `nd-systemupdate.sh shell` forks from `release`, not from the currently-running snapshot. The new snapshot name is whichever `runN` slot is currently unused — it does NOT increment monotonically across all chroot sessions. If pre-promote you were on `run2`, post-promote you may end up on `run1`, `run3`, or any other slot. **Don't guess by name; resolve by `btrfs subvolume list / | tail -1`** as Step 5.5 above does.

The recipe printer substitutes:
- `<NDSU>` from the same NDSU detection probe used by OBN-only `--persist`
- `<VARIANT_GLOB>` and `<TEMPLATES_EXPECTED>` from the live `ls /etc/obn/template/` (`nv6-*.cfg` / 18, or `nv4-*.cfg` / 12)
- `<FZG>` from the engineer-supplied `--with-fzg-id` value
- `<CURRENT_NMCONN_IP>` from the pre-chroot read of the `address1=` line
- `<EXPECTED_VLAN7_IP>` from the bit-packed formula applied to `--with-vlan7 <Fzg>`

#### Why fold-in is safe

- **All three sub-recipes are idempotent and assertive.** Each sub-block aborts loudly on shape mismatch (`assert old in content` for vlan7; `if not lines[0].startswith('{%- set train_id'): sys.exit(...)` for fzg-id; `PATTERN NOT FOUND` for the OBN fix-scripts). If any sub-recipe fails, the engineer sees it before `exit`, can debug, and the snapshot is not promoted.
- **Order is intentional**: OBN patches first (least likely to surprise — fix-script maturity is high), then fzg-id template (deterministic one-line edit), then vlan7 (depends on `<CURRENT_NMCONN_IP>` matching what we read pre-chroot — fastest to fail-fast if live state drifted in the gap between probe and chroot).
- **Engineer-supplied Fzg is validated against the bit-packed formula upfront**, so a typo like `--with-vlan7 1320` (extra digit) gets caught before the recipe is ever printed.

#### When fold-in is the wrong answer

- **Engineer is iterating on one fix at a time** during commissioning of a new train type. Use the standalone skills (`/dosto-vlan7-config 132 --persist`, `/dosto-fzg-id-check 132 --persist`) so each change is reviewed in isolation.
- **One sibling skill returned an unexpected verdict** (e.g. vlan7 `nmconnection_correct_live_wrong` — that's a transient state, fixed with `nmcli con down/up`, not a chroot edit). The fold-in skips these correctly, but the engineer should resolve them before the chroot rather than mixing transient runtime fixes with persistent ones.

### `--persist` pitfalls (learned 2026-05-09 on Fzg 132 / box1-t10)

- 🔴 **Don't stage in `/tmp/`** — invisible inside the chroot. Use `/var/tmp/`.
- 🔴 **Don't assume `/var/tmp/` survives reboot** — it's tmpfs. Re-scp scripts between every promote.
- 🔴 **Folder names like `run1` / `run2` recycle** — verify a promote happened by btrfs *subvolume ID*, not folder name. Run `sudo btrfs subvolume show /` before and after; the active subvol ID changes on a successful promote.
- 🟡 **If the CCU has canonical `nd-systemupdate.sh` (no `.dont`)** — re-rename it after the promote (step 3.5 above), or the next nightly auto-update timer (`OnCalendar=*-*-* 0,1,2,3,4:21:00`) will promote a vanilla-OBN snapshot from the Puppet env and wipe these patches. Confirmed exposed: box1-t1 (Fzg 133) as of 2026-05-09.
- 🟡 **Fold-in cleanups must agree on Fzg.** If `--with-vlan7` and `--with-fzg-id` are both passed, they must share a value; the skill validates this upfront. Mismatched IDs almost always indicate confusion about which train you're touching — the skill aborts before printing any recipe.

After reboot, re-invoke `/dosto-obn-patches <ccu-ip>` (check mode) to verify all 8 markers survived. Update fleet-status `OBN patches` to `persisted (run<N>)` where `<N>` is the new snapshot number (visible in `mount | grep " on / "`).

### Post-Flight — verify the rendered output

**Mandatory rendered-output verification** (Karpathy Principle 4 — Goal-Driven Execution; see also [`CLAUDE.md` § Universal Principles](../../../CLAUDE.md)). The patched `.py` files are the *input*; OBN actually running without exceptions on the next discovery cycle is the *output*. Verifying the markers alone is necessary but not sufficient — a partial patch with PATTERN-NOT-FOUND or a wrong-line edit could leave 8/8 markers grep-passing while OBN crashes at runtime.

After `--persist` + reboot, the engineer (or `dosto-commission-train` stage 10 `post_reboot_verify`) MUST verify all four of:

| Assertion | Probe | Pass criterion |
|---|---|---|
| **A. All 8 markers present** | The 8 grep counts from `--check` mode | All 8 expected (1, 2, 1, 1, 1, 1, 1, 1) |
| **B. btrfs subvol promoted** | `sudo btrfs subvolume show /` (compare ID before vs after) | Active subvolume ID changed (folder names recycle — ID is authoritative, handoff lesson 6) |
| **C. OBN runs cleanly** | `sudo obn discover` exit code | Exit 0, no Traceback / ERROR / Exception in `/var/log/obn/*.log` since reboot |
| **D. Bug 5 ipset pre-population observable** | `sudo ipset list tftp_allowed \| grep "Number of entries"` after a non-empty discover | Non-zero entry count (post-discover OBN should pre-populate the ipset with target devices) |

**If A passes but C fails:** patches grep-pass but OBN errors at runtime. Check `journalctl -u nd-backbone-discovery.service` and `/var/log/obn/*.log` for the traceback. Likely a partial patch from `fix_obn.py` reporting "PATTERN NOT FOUND" that was missed by the engineer; re-run `--check` and look at the per-bug counts.

**If A and C pass but B fails:** the chroot didn't promote. Markers exist on the running snapshot but next reboot will lose them. Re-run `--persist`.

**If A and B pass but D fails:** the Bug 5 patch is in the file but isn't firing during discover. Check that `obn discover` is the *patched* version, not a cached vanilla one (paths and module caches).

**`--json` output for Post-Flight** (consumed by `dosto-commission-train`'s stage 10):

```json
{
  "skill": "dosto-obn-patches",
  "mode": "post_flight",
  "schema_version": "1",
  "verdict": "all_match|markers_only|markers_and_promote_only|runtime_failure",
  "raw": {
    "input_assertion_a": {"pass": true, "marker_counts": [1, 2, 1, 1, 1, 1, 1, 1]},
    "promote_assertion_b": {"pass": true, "subvol_id_before": 314, "subvol_id_after": 320, "subvol_path": "/.snapshots/run2"},
    "runtime_assertion_c": {"pass": true, "obn_discover_exit": 0, "log_traceback_count": 0, "log_error_count": 0},
    "bug5_assertion_d": {"pass": true, "tftp_allowed_entry_count": 18}
  }
}
```

`verdict` semantics:
- `all_match` — all four assertions pass. ✅
- `markers_only` — A passes, others fail. 🔴 grep-pass but real failure.
- `markers_and_promote_only` — A and B pass, C fails. 🔴 OBN broken at runtime.
- `runtime_failure` — C fails for any reason. 🔴 catch-all for "patches present but OBN crashes."

## Failure modes and what to do

### `fix_obn.py` reports "PATTERN NOT FOUND" for some bug

Means the file is in a state the canonical script doesn't recognise. This happens when:
- A previous partial run left it half-patched
- A different OBN version is installed
- Someone hand-edited the file

For Bugs 1, 6, 7 there's a fallback script (see table above). For other bugs, the file needs manual review — print the full surrounding context for that file with `sed -n '70,100p' /usr/share/obn/lib/...` and read the runbook section for that bug.

### `--check` shows 8/8 but `obn update c all` still crashes

Either a 9th bug exists that we haven't yet documented, or there's an OBN version mismatch (the fix is for an older API surface). Check the OBN version: `sudo cat /usr/share/obn/VERSION` or `sudo apt list --installed | grep obn`. Capture the crash traceback and add it to [troubleshooting-runbook.md](troubleshooting-runbook.md) → "OBN bugs" section as Bug 9 (whatever it turns out to be).

### Patches present but lost on next reboot

Means `--persist` wasn't run (or `nd-systemupdate.sh shell` didn't promote the snapshot). Re-run `--persist`. Verify: `mount | grep " on / "` should show a `run<N>` higher than what was there before, and `cat /etc/snapper/configs/...` (if present) confirms the new default.

### CCU's btrfs has multiple snapshots and unsure which is active

`mount | grep " on / "` shows the active subvolume. `btrfs subvolume list /` shows all snapshots. Don't apply patches to a non-active snapshot — they'll be invisible.

## What this skill deliberately does NOT do

- ❌ Execute scripts on the CCU (engineer runs the printed recipe)
- ❌ Enter `nd-systemupdate.sh shell` programmatically (chroot promotion is irreversible)
- ❌ Reboot the CCU (`safe_reboot` is engineer-driven)
- ❌ Modify OBN code itself; only verifies known patches via deterministic grep markers
- ❌ Try to fix bugs we haven't encoded — if a new crash mode surfaces, that's a documentation/code change, not a skill change
- ❌ Update fleet-status programmatically — print the values the engineer should set, let them edit (consistent with `dosto-vlan7-config`)

## Pairs with

- [`dosto-vlan7-config`](../dosto-vlan7-config/SKILL.md) — both are "static-config-from-PDF must persist via nd-systemupdate" skills with the same diagnostic + recipe shape
- [train-login-checklist.md](../../../train-login-checklist.md) — Step 3 invokes this skill
- [fleet-status.md](../../../fleet-status.md) — `OBN patches` column tracks per-train state

## Reference

The patches themselves are documented in [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "OBN Firmware & Config Update — Known Bugs and Fixes". The fix scripts in `scripts/` are local-workspace-only (private R&D fixes, not yet upstreamed to OBN GitLab — once R&D confirms and releases, this skill becomes "verify the deployed OBN has these fixes" rather than "apply them").
