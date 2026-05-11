---
name: dosto-tftp-helper-check
description: Diagnostic check for the CCU firewall TFTP conntrack helper gap that silently breaks `obn update f ap` batch firmware pushes. Verifies that the `nf_conntrack_tftp` kernel module is loaded AND a CT helper rule exists on udp/69 in iptables raw PREROUTING. If either is missing, prints the runtime workaround (`modprobe` + iptables rule) — knowing it will not survive reboot until R&D ships the Puppet fix into `60-allow-management`. Use as Step 4d of train-login-checklist before any AP firmware push, when an AP firmware batch silently fails for most APs (only ~5 of 15 succeed by conntrack-race luck), or whenever a CCU reboot may have wiped the runtime fix. The skill is read-only by default — even `--apply-runtime` mode prints the recipe and lets the engineer run it.
---

# DOSTO TFTP Conntrack Helper Check

This skill is the canonical diagnostic for the **CCU firewall TFTP conntrack helper gap** — a known issue in the shipped CCU image that causes silent failures during AP firmware batch pushes.

It's a **firewall config gap, not an OBN bug.** The fix belongs in Puppet (`/etc/21net-security.d/60-allow-management`). Until R&D ships it, the runtime workaround must be re-applied on every CCU reboot.

## When to use

- **Step 4d of [train-login-checklist.md](../../../train-login-checklist.md)** — every train, every visit, before any AP firmware push.
- **Before any `obn update f ap` batch push** — even one stuck AP can mask the gap; this skill catches it pre-push.
- **When an AP firmware batch silently fails for most APs** (typical pattern: ~5 of 15 succeed by lucky conntrack race, the rest hang). Diagnose with this skill before trying again.
- **After every CCU reboot** — the runtime fix is in-memory only and is lost on reboot. The persistent Puppet fix is not yet shipped.
- **When [fleet-status.md](../../../fleet-status.md) shows `tftp helper` as ❓ or 🔴** — fill it in.

## Output modes

Both default and `--json` modes share the same diagnostic procedure — `--json` is purely a formatter switch.

- **default — engineer-readable.** Diagnostic table + verdict + recipe-when-needed.
- **`--json` — machine-readable.** A single JSON line on stdout matching `skill_outputs[]` from [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md). Subagents pass `--json`; engineers don't.

### `--json` shape

```json
{
  "skill": "dosto-tftp-helper-check",
  "mode": "check",
  "schema_version": "1",
  "verdict": "all_present|module_missing|rule_missing|both_missing|nft_compat_no_op|puppet_persisted",
  "raw": {
    "module_loaded": true,
    "module_name": "nf_conntrack_tftp",
    "ct_helper_rule_present": true,
    "ct_helper_rule_count": 1,
    "ct_helper_rule_text": "CT        udp  --  *      *       0.0.0.0/0            0.0.0.0/0            udp dpt:69 helper tftp /* TFTP conntrack helper for in.tftpd */",
    "tftp_allowed_ipset_exists": true,
    "tftp_allowed_byte_counter": 0,
    "iptables_backend": "nf_tables|legacy|unknown",
    "puppet_60_allow_management_has_fix": false,
    "ccu_uptime_seconds": 8520,
    "last_modprobe_in_dmesg": null
  },
  "recipe": null
}
```

`verdict` semantics:
- `all_present` — module loaded AND helper rule present AND backend is not the silent-no-op nft compat shim. ✅
- `module_missing` — helper module not loaded. 🔴 First packet of TFTP transfer accepted, return data flow falls through to `INPUT policy DROP`.
- `rule_missing` — module loaded but no `CT --helper tftp` rule on udp/69 in raw PREROUTING. 🔴 Same effective failure as above.
- `both_missing` — neither present. 🔴 Most common state on a fresh CCU image.
- `nft_compat_no_op` — module loaded AND a `CT --helper tftp` line is visible in iptables output, BUT the iptables backend is `nf_tables` and the rule is silently a no-op (the iptables-nft compat shim does not honour the `CT --helper` extension). 🔴 The CCU appears configured but pushes still fail. Workaround needs native nftables `ct helper set` syntax — see "iptables-nft caveat" below.
- `puppet_persisted` — `all_present` AND the Puppet-managed `/etc/21net-security.d/60-allow-management` already contains the `modprobe nf_conntrack_tftp` and `CT --helper tftp` lines. ✅✅ This is the end-state we want fleet-wide; until R&D ships it, this verdict is unreachable.

`recipe` is non-null only when verdict is `module_missing`, `rule_missing`, `both_missing`, or `nft_compat_no_op`. Contains the runtime-fix shell commands.

`tftp_allowed_byte_counter` is the byte counter on the `MGMTI` chain's `match-set tftp_allowed` rule. After a healthy AP firmware batch, this counter is in the hundreds of MB (firmware transfers). After a broken batch, it's a few KB (just RRQs). Reading this *after* a push gives a strong post-hoc signal that the gap was active.

`last_modprobe_in_dmesg` is the most recent line from `dmesg | grep nf_conntrack_tftp` if any — used to spot whether someone applied the runtime fix earlier this boot.

## Why this matters (read this once)

The CCU's iptables `MGMTI` chain (built on boot by `/etc/21net-security.d/60-allow-management`) has this rule for inbound TFTP:

```
$IPT -A MGMTI -p udp -m set --match-set tftp_allowed src -m udp --dport 69 -m comment --comment "tftp" -j ACCEPT
```

This allows the **first packet** of a TFTP transfer (AP's RRQ → CCU port 69). Once `in.tftpd` accepts it, the daemon opens an **ephemeral source port** and sends DATA from `CCU:<random>` → `AP:<random>`. The AP replies with ACK from `AP:<random>` → `CCU:<random>`.

For the ACK to be accepted, the kernel needs to recognise it as RELATED to the original RRQ flow — and that requires:
1. The `nf_conntrack_tftp` helper module **loaded**, AND
2. An explicit CT helper rule attached to udp/69 in **raw PREROUTING**.

Without both, conntrack treats the data flow as a brand-new connection. It doesn't match `state RELATED,ESTABLISHED` (line 2 of INPUT) and falls through to `INPUT policy DROP`. The data transfer never completes. The AP times out. OBN reports "Successful: upgrade tftp request initiated" because that's literally what the AP said — but the firmware bytes never arrived.

This is silent at the OBN level (handoff lesson 12) and silent at the OBN log level (handoff lesson 17). Only the system journal (`journalctl -u tftpd-hpa`) and the `tftp_allowed` byte counter expose it.

## The shipped CCU image has neither

Validated 2026-05-09 on box1-t10 (Fzg 132): module not loaded, no CT helper rule, batch firmware pushes silently failed for most APs. After applying the runtime workaround (`modprobe` + `iptables -t raw -A PREROUTING ...`), batches succeeded reliably.

This is a firewall-config gap — separate ticket from the OBN bugs. The fix lands in Puppet (`/etc/21net-security.d/60-allow-management`); until then, every CCU needs the runtime workaround re-applied after every reboot.

## Procedure

### 0. Inputs

You need:

- **CCU IP** (e.g. `10.179.10.1`)

If the user invoked this skill with `/dosto-tftp-helper-check 10.179.10.1` — that's the input. Otherwise ask: *"Which CCU IP?"*.

### 1. Read live state — single SSH heredoc

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
echo "=== module ==="
lsmod | grep nf_conntrack_tftp || echo "MODULE_NOT_LOADED"

echo "=== CT helper rule on raw PREROUTING ==="
sudo iptables -t raw -L PREROUTING -n -v 2>/dev/null | grep -E "helper tftp|CT.*tftp" || echo "RULE_NOT_PRESENT"

echo "=== iptables backend (nf_tables compat = silent-no-op risk) ==="
sudo iptables --version

echo "=== tftp_allowed ipset (existence + size) ==="
sudo ipset list tftp_allowed 2>/dev/null | head -8 || echo "IPSET_NOT_PRESENT"

echo "=== MGMTI tftp_allowed byte counter (post-push diagnostic) ==="
sudo iptables -L MGMTI -n -v 2>/dev/null | grep "tftp_allowed src" || \
  sudo iptables -L INPUT -n -v 2>/dev/null | grep "tftp_allowed src" || \
  echo "NO_TFTP_RULE_IN_MGMTI"

echo "=== puppet 60-allow-management has the fix? ==="
sudo grep -E "nf_conntrack_tftp|helper tftp" /etc/21net-security.d/60-allow-management 2>/dev/null \
  || echo "PUPPET_NOT_PERSISTED"

echo "=== last modprobe in dmesg (was the runtime fix applied this boot?) ==="
sudo dmesg --time-format iso 2>/dev/null | grep nf_conntrack_tftp | tail -1 || echo "NO_DMESG_TRACE"

echo "=== uptime ==="
cat /proc/uptime | awk "{print int(\$1)}"
'
```

Parse the output:

- `lsmod | grep nf_conntrack_tftp` → `module_loaded` (boolean: any match = true).
- `iptables -t raw -L PREROUTING -n -v | grep "helper tftp"` → `ct_helper_rule_present` (boolean), `ct_helper_rule_count`, `ct_helper_rule_text` (verbatim).
- `iptables --version` → `iptables_backend`. If the version string contains `nf_tables`, set `iptables_backend = "nf_tables"`. If `legacy`, set `"legacy"`. Otherwise `"unknown"`.
- `ipset list tftp_allowed` → `tftp_allowed_ipset_exists` (the ipset exists in the kernel), member count.
- `iptables -L MGMTI -n -v | grep tftp_allowed src` → byte counter from the `pkts bytes` columns. Store as `tftp_allowed_byte_counter` (integer bytes).
- `grep` of `60-allow-management` → `puppet_60_allow_management_has_fix`.
- `dmesg | grep nf_conntrack_tftp` → `last_modprobe_in_dmesg` (single most recent line or `null`).
- `/proc/uptime` → `ccu_uptime_seconds`.

### 2. Verdict matrix

| `module_loaded` | `ct_helper_rule_present` | `iptables_backend` | `puppet_60_allow_management_has_fix` | Verdict |
|---|---|---|---|---|
| ✅ | ✅ | `legacy` or `unknown` | ✅ | `puppet_persisted` ✅✅ |
| ✅ | ✅ | `legacy` or `unknown` | ❌ | `all_present` ✅ (runtime-only — will wipe on reboot) |
| ✅ | ✅ | `nf_tables` | any | `nft_compat_no_op` 🔴 (rule visible but silently a no-op) |
| ✅ | ❌ | any | any | `rule_missing` 🔴 |
| ❌ | ✅ | any | any | `module_missing` 🔴 |
| ❌ | ❌ | any | any | `both_missing` 🔴 |

Print a status line — e.g. on the typical broken state:

```
Module nf_conntrack_tftp:    🔴 not loaded
CT helper rule (raw udp/69):  🔴 not present
iptables backend:             nf_tables (caveat: see "iptables-nft" below)
Puppet 60-allow-management:   🔴 fix not persisted
tftp_allowed byte counter:    312 bytes  (RRQ-sized — no firmware transfers landed)
Uptime:                       4h 22m

Verdict: 🔴 both_missing
        Symptom: AP firmware batch pushes will silently fail for most APs.
        Runtime workaround available — apply with /dosto-tftp-helper-check <ccu-ip> --apply-runtime
```

### 3. Print the runtime workaround (DO NOT EXECUTE IT)

If verdict is `module_missing`, `rule_missing`, or `both_missing`, print the runtime workaround. **`--apply-runtime` mode is print-only**, same convention as the other DOSTO skills — the engineer runs the commands.

```bash
# === Runtime workaround (in-memory only — wipes on reboot) ===
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>

# Inside the CCU:
sudo modprobe nf_conntrack_tftp
sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp \
  -m comment --comment "TFTP conntrack helper for in.tftpd (runtime fix — Puppet TBD)"

# Verify it took:
lsmod | grep nf_conntrack_tftp
sudo iptables -t raw -L PREROUTING -n -v | grep "helper tftp"

# (Optional) confirm helper attaches to next RRQ. The /proc/net/nf_conntrack_expect
# table stays empty until an actual TFTP transfer fires. After kicking one AP
# firmware push you should see a transient line here:
watch -n1 'sudo cat /proc/net/nf_conntrack_expect'
exit
```

**Caveats engineer must read before running:**

- 🟡 **In-memory only.** Lost on next reboot. Re-apply after every CCU reboot until R&D ships the Puppet fix.
- 🟡 **`-I PREROUTING` (insert at top), not `-A` (append).** `-A` works in the legacy backend but ordering can matter under nft compat — inserting at the top is safer.
- 🟡 **Not a chroot/persist operation.** This is runtime config; it doesn't write to any file. `nd-systemupdate.sh` is not involved here.

### 4. The iptables-nft caveat (verdict `nft_compat_no_op`)

The iptables-nft compatibility shim (default backend on modern kernels) **does NOT honour** the `CT --helper` extension when the rule is added via `iptables`. The rule appears in `iptables -L` output as expected, but the kernel's nftables core never attaches the helper. Helper expectations stay empty (`/proc/net/nf_conntrack_expect` is blank even with active TFTP traffic), and pushes silently fail just as if the rule weren't there at all.

Workaround if you hit this: drop into native `nft` and add:

```bash
sudo nft add table ip raw 2>/dev/null || true
sudo nft add chain ip raw PREROUTING { type filter hook prerouting priority -300 \; } 2>/dev/null || true
sudo nft add rule ip raw PREROUTING udp dport 69 ct helper set "tftp"
```

Then verify the helper actually attaches:

```bash
sudo nft list ruleset | grep -A2 "udp dport 69"
sudo cat /proc/net/nf_conntrack_expect    # should populate transiently during a real RRQ
```

This is the harder case. If you see verdict `nft_compat_no_op` on a CCU, capture full `iptables -t raw -L PREROUTING -n -v` and `nft list ruleset` output and add it to [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) under the same section as the original gap — fleet may need both the legacy-iptables runtime fix AND the native-nft workaround if the kernel choice varies.

Validated against the legacy iptables backend on 2026-05-09 (box1-t10). The nft compat path is encoded here for completeness; if the fleet image is consistent, this branch will be unreachable.

### 5. After applying the runtime workaround — verify

Tell the engineer to:

1. Re-invoke the skill in `--check` mode → verdict should now be `all_present`.
2. Kick one AP firmware push as a single-AP test (do NOT batch yet). Monitor:
   ```bash
   sudo journalctl -u tftpd-hpa --since "30 seconds ago" -f
   ```
   Expected: `RRQ from <AP-IP>` followed by data transfer log lines, ending with completion. If it hangs after RRQ, the helper still isn't attaching — drop into the nft compat path.
3. Check the `tftp_allowed` byte counter grew by ~6-8 MB (one AP firmware image): `sudo iptables -L MGMTI -n -v | grep tftp_allowed src`.
4. Only after a successful single-AP push, scale to a small batch (2–3 APs).

### 6. Update [fleet-status.md](../../../fleet-status.md)

Per the orchestrator-as-sole-writer pattern:

- `tftp helper` column → ✅ if `puppet_persisted`, 🟡 if `all_present` (runtime-only), 🔴 if any missing/no-op state
- `Last touched` column → today's date + initials
- If 🟡, add a one-liner reminder: "runtime fix only — re-apply after next reboot until R&D ships Puppet"

## What this skill deliberately does NOT do

- ❌ Run `modprobe` or modify iptables on the CCU itself (engineer runs the printed recipe)
- ❌ Edit `/etc/21net-security.d/60-allow-management` (Puppet-managed — must be upstreamed, not hand-edited)
- ❌ Persist the fix into a btrfs snapshot via `nd-systemupdate.sh` shell. The runbook notes this is *possible* but advises against it: "This change must land in the Puppet repo, not as a hand-edit on the live CCU — otherwise it gets wiped on next btrfs promote." This skill therefore stays runtime-only.
- ❌ Drop into native `nft` automatically — only print the recipe if the engineer hits the rare `nft_compat_no_op` verdict

## Edge cases / gotchas

- **Module loaded but no rule, OR rule but no module.** Same effective failure as both-missing — return data flow falls through to `INPUT policy DROP`. Fix is the same: apply both lines of the runtime workaround.
- **`tftp_allowed` ipset doesn't exist at all.** Means `60-allow-management` didn't run on boot, or ran with errors. Investigate Puppet agent state — separate from this skill's scope.
- **Byte counter is high (hundreds of MB) but pushes still fail.** Different problem — likely the AP-side stuck-state described in handoff lesson 13. Cross-check with `dosto-ap-firmware-update`'s journalctl-RRQ verification (skill not yet built — for now, manually `journalctl -u tftpd-hpa | grep RRQ`).
- **Puppet has the fix but module/rule are absent at runtime.** Means Puppet ran but the `modprobe` failed (kernel module not present) OR the file's lines were rendered but skipped on boot. Re-run boot script: `sudo /etc/21net-security.d/60-allow-management`. If `modprobe` itself fails, the kernel image may be missing the module — escalate to R&D.
- **The runtime workaround "took" but pushes still fail.** Most likely the `nft_compat_no_op` case — verify with `cat /proc/net/nf_conntrack_expect` during an active transfer; if empty, drop into native nft.

## Pairs with

- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — Bug 5 pre-populates `tftp_allowed`; this skill verifies the firewall actually allows the resulting transfers. Both must be in good state for AP firmware batch pushes to work.
- [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md) — *not yet built*. Will call this skill as a precondition before any AP firmware push.
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "CCU Firewall — TFTP conntrack helper missing" — full diagnostic walkthrough and Puppet-fix recipe.
- [train-login-checklist.md](../../../train-login-checklist.md) — Step 4d invokes this skill.
- [fleet-status.md](../../../fleet-status.md) — `tftp helper` column tracks per-train state.

## Reference

- auto-memory `project_tftp_conntrack_helper.md` — the persistent fact pointing at this issue
- handoff lesson 11 — original discovery on Fzg 132 (15-AP batch with ~10 silent failures, batch-of-2 worked post-fix)
- handoff lesson 12 — why OBN's "Successful" parsing is fake-positive without firewall + journalctl verification
- handoff lesson 17 — `/var/log/obn/*.log` doesn't capture in.tftpd state; use `journalctl -u tftpd-hpa`
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "CCU Firewall — TFTP conntrack helper missing"
