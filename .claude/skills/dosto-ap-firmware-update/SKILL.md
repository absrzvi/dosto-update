---
name: dosto-ap-firmware-update
description: Push a Westermo AP firmware image via OBN, with the verification, stuck-state detection, and 15-minute completion poll that OBN's own implementation lacks. Use when pushing firmware to one AP, when an engineer says "obn update f" against an AP, or when an AP has been stuck across reboots and needs the SSH-reboot recovery path. Uses journalctl RRQ verification (handoff lesson 12), single-AP serial pushes only (lesson 11 — batches > 2-3 are unreliable on the current fleet image), automatic SSH-reboot recovery for stuck-state APs (lesson 13), and 15-minute polling rather than OBN's optimistic 5-minute internal wait (lesson 14). Default mode (--prepare) is read-only diagnostic + recipe print; opt-in --execute mode drives one AP through the full push autonomously, stopping at gates for engineer approval. Pairs with dosto-tftp-helper-check (precondition: must return all_present or puppet_persisted).
---

# DOSTO AP Firmware Update

This skill pushes a Westermo AP firmware image via OBN's `obn update f <ap-ip>` flow, but adds the verification and recovery layers that OBN itself doesn't implement. It exists because OBN reports "Successful" the moment the AP acknowledges the SSH command — long before any firmware bytes have actually transferred — so without skill-side verification, fleet-wide updates silently leave a fraction of APs in a half-flashed state.

This is **firmware push only**. AP config push (especially the factory-config LuCI HTTP bypass) is a separate skill — see [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md). On freshly-commissioned trains, config push runs first.

## When to use

- **Step 7 of [train-login-checklist.md](../../../train-login-checklist.md)** — after device discovery, OBN patches, vlan7/Fzg-id fixes, and TFTP helper verification.
- **One AP at a time, serially** — the skill rejects batch invocation. If you have 24 APs to update, you invoke this skill 24 times.
- **When `obn validate -t ap` shows mismatched firmware** — the per-AP firmware column reads `<current> (<staged>) ✗` if a previous flash partially landed; this skill resolves both fresh pushes and partial-flash recoveries.
- **When retrying APs that hung from a previous attempt** — stuck-state APs require the SSH-reboot workaround (handoff lesson 13).
- **Never on more than one AP at a time without explicit engineer override.** The handoff lesson 11 finding (parallel batches > 2-3 are unreliable) is the reason the skill is single-AP-only by design.

## Preconditions (skill aborts if any are not met)

The skill verifies all of these before any push:

| Precondition | Verified by | Failure verdict |
|---|---|---|
| `dosto-tftp-helper-check` ∈ {`all_present`, `puppet_persisted`} | inline SSH probe (same logic as that skill) | `preconditions_unmet` 🔴 |
| `dosto-obn-patches` ∈ {`all_patched`, `all_persisted`} | inline grep markers (same logic as that skill) | `preconditions_unmet` 🔴 |
| AP visible in fresh `obn discover` with Nomad-form config | parse `/tmp/discovery.json` after `sudo obn discover`; pass if entry has `config: AP[1-4]m?-v1-...` and non-null `firmware`. Standalone `snmpget` only as fallback when discover.json data is missing/stale | `ap_in_factory_config` 🔴 |
| `<ap-ip>` is a Westermo AP (MAC OUI `00:14:5a`) | `ip neigh` lookup on vlan100 from CCU | `ap_not_found` 🔴 |
| Single AP only — no batch glob | argument parser | error before any SSH |

Without TFTP helper, even a single push can fail at the data-return-flow stage. Without OBN patches (specifically Bug 5 — pre-populated `tftp_allowed` ipset), the push itself drops below 100% reliability and Bugs 4/8 expose crash paths in the report layer. Without Nomad SNMP responding, the AP is in factory config — `dosto-ap-config-update` runs first; do not push firmware to a factory-config AP, the SSH credentials and config layout are wrong.

**Why "trust obn discover, not standalone snmpget":** validated 2026-05-09 on Fzg 132 / box1-t10 — `snmpget -v2c -c NomadStayOut! -t 3 -r 1 <ap-ip>` timed out on a known-Nomad AP (.226) that `obn discover` had successfully polled 30 seconds earlier. OBN's SNMP library evidently uses different timing/retry parameters than vanilla `snmpget`. Treating the standalone probe as authoritative produced a false `ap_in_factory_config` verdict and would have aborted a legitimate push. The fix: read the AP's row from `/tmp/discovery.json` (refreshed via `sudo obn discover`); if `.config` matches the Nomad form `AP[1-4]m?-v1-...` and `.firmware` is non-null, the AP is reachable enough for OBN to push. Only fall back to `snmpget` when discover.json has no recent entry for the AP.

## Output modes

The skill has **two execution modes** plus the standard `--json` formatter switch:

- **`--prepare` (default) — read-only.** Verify preconditions, capture live state, print the equivalent shell recipe an engineer would run manually. No CCU writes, no AP changes. Same family shape as the diagnostic skills.
- **`--execute` (opt-in) — autonomous driver.** Drives one AP through the full state machine: push, RRQ verification, stuck-state detection + recovery, 15-min completion poll, second-reboot decision. Stops at three explicit approval gates for irreversible actions. Without `--execute`, no destructive command runs.

Both modes support `--json` for machine-readable output. In `--execute` mode, JSON is streamed one event per line as the state machine progresses.

### `--prepare` `--json` shape

```json
{
  "skill": "dosto-ap-firmware-update",
  "mode": "prepare",
  "schema_version": "1",
  "verdict": "ready_to_push|already_at_target|partial_flash_detected|preconditions_unmet|ap_in_factory_config|ap_not_found",
  "raw": {
    "ccu_ip": "10.179.10.1",
    "ap_ip": "10.179.10.222",
    "ap_mac": "00:14:5a:01:23:45",
    "ap_hostname": "ap-A1.1",
    "current_firmware": "6.10.0-0",
    "staged_firmware": null,
    "target_firmware": "6.11.2-0",
    "ap_config_state": "nomad|factory|unknown",
    "obn_patches_verdict": "all_persisted",
    "tftp_helper_verdict": "all_present",
    "fix_obn_bug5_active": true,
    "ipset_tftp_allowed_has_ap": true,
    "last_obn_log_for_ap": "2026-05-09T11:13:42Z Successful: upgrade tftp request initiated"
  },
  "recipe": "..."
}
```

`verdict` semantics:

- `ready_to_push` — preconditions ✅, current ≠ target, no staged image. Standard fresh push path.
- `partial_flash_detected` 🟡 — current ≠ target BUT staged == target. A previous flash uploaded but didn't activate. Force-second-reboot resolves it; no fresh push needed. Skill recommends Gate-3-style flow (engineer ack to reboot) rather than re-pushing.
- `already_at_target` ✅ — current == target. No-op.
- `preconditions_unmet` 🔴 — TFTP helper or OBN patches not in good state. Fix those first.
- `ap_in_factory_config` 🔴 — SNMP doesn't respond. Run `dosto-ap-config-update` first.
- `ap_not_found` 🔴 — `<ap-ip>` not in `ip neigh` on vlan100, or MAC OUI isn't Westermo. Wrong IP or AP is unreachable.

`staged_firmware` is parsed from `obn validate -t ap`'s `(<staged>) ✗` form (handoff lesson 16). `null` when no staged image exists (clean state).

`target_firmware` defaults to whatever OBN's discovery considers the target (parsed from `/tmp/discovery.json` or `obn validate` output). Engineer can override with `--target <version>`.

`fix_obn_bug5_active` confirms the patched `update.py` will pre-populate `tftp_allowed` for this AP before the push. Cross-checks with `ipset_tftp_allowed_has_ap` (the live ipset state).

`recipe` is the engineer-runnable shell script. Non-null whenever `verdict ∈ {ready_to_push, partial_flash_detected}`.

### `--execute` `--json` event stream

In `--execute` mode the skill emits one JSON event per state transition. Each event has `event`, `timestamp`, `ap_ip`, plus event-specific fields. Terminal events have a `final: true` marker.

```json
{"event":"started","timestamp":"...","ap_ip":"10.179.10.222","target_firmware":"6.11.2-0"}
{"event":"pre_check_passed","timestamp":"...","ap_ip":"10.179.10.222","current_firmware":"6.10.0-0"}
{"event":"gate_1_awaiting_ack","timestamp":"...","ap_ip":"10.179.10.222","action":"obn update f 10.179.10.222"}
{"event":"gate_1_acked","timestamp":"...","ap_ip":"10.179.10.222"}
{"event":"push_command_returned","timestamp":"...","ap_ip":"10.179.10.222","obn_says":"Successful: upgrade tftp request initiated","push_command_exit":0}
{"event":"rrq_seen","timestamp":"...","ap_ip":"10.179.10.222","journalctl_line":"in.tftpd: RRQ from 10.179.10.222 filename WeOSv5_RT-6.11.2-0.cfg"}
{"event":"polling_completion","timestamp":"...","ap_ip":"10.179.10.222","current_firmware":"6.10.0-0","staged_firmware":"6.11.2-0","poll_count":3,"elapsed_seconds":270}
{"event":"completed","timestamp":"...","ap_ip":"10.179.10.222","current_firmware":"6.11.2-0","total_elapsed_seconds":487,"final":true}
```

Failure-mode events:
- `gate_2_awaiting_ack` — no RRQ within 60s; engineer must approve SSH-reboot recovery
- `gate_3_awaiting_ack` — 15-min poll exhausted without target firmware visible; engineer chooses force-reboot, abort, or extend-poll
- `aborted` — terminal failure with `final: true` and `reason` field

## The state machine

```
                ┌──────────────┐
                │   pre_check  │
                └──────┬───────┘
                       │
      preconditions OK ▼
                ┌──────────────┐         GATE 1
                │     push     │◄────  engineer acks
                └──────┬───────┘
                       │
      `obn update f` returned (any output)
                       │
                       ▼
                ┌──────────────┐
                │ verify_rrq   │  poll journalctl every 5s for 60s
                └──┬─────────┬─┘
        RRQ seen   │         │   no RRQ in 60s
                   │         │
                   │         └────► GATE 2 (engineer acks SSH-reboot)
                   │                     │
                   │                ┌────▼─────────┐
                   │                │ stuck_recover│  ssh ap reboot, sleep 90s
                   │                └────┬─────────┘
                   │                     │
                   │                     └─► back to push (one retry)
                   ▼
            ┌──────────────────┐
            │ poll_completion  │  fresh `obn discover` every 90s, up to 15 min
            └──┬──────────────┬┘
   target seen │              │  15 min elapsed
               │              │
               │              └────► GATE 3 (engineer chooses)
               │                          │
               │                          ├─► force-reboot ─┐
               │                          ├─► extend-poll  ─┤
               │                          └─► abort ────────┴──► aborted (final)
               ▼
        ┌──────────────┐
        │ verify_done  │  one final `obn discover`, confirm
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │   completed  │  (final: true)
        └──────────────┘
```

### Stage details

**`pre_check`** — Run all five preconditions in one SSH heredoc to the CCU. AP-reachability check uses fresh `sudo obn discover` + `jq` parse of `/tmp/discovery.json`, NOT standalone `snmpget`. The standalone probe times out on Nomad APs that OBN's own SNMP library can poll (validated 2026-05-09 on Fzg 132 / box1-t10 — false-positive `ap_in_factory_config` on AP .226). Pass criterion: discover.json has the AP with `config` matching `^AP[1-4]m?-v1-` (Nomad form) AND non-null `firmware`. If the AP is missing from discover.json entirely, fall back to `snmpget -v2c -c NomadStayOut! -t 8 -r 2` with longer timeout/retry as a second-chance check before aborting. If any precondition fails, emit `aborted` with `reason: "preconditions_unmet:<which>"` and exit. No further state.

**`push` (Gate 1)** — Emit `gate_1_awaiting_ack` with the exact command. Wait for ack. On ack, run `sudo obn update f <ap-ip>` over SSH from the CCU. Capture stdout/stderr. Emit `push_command_returned` with the captured "Successful: ..." line (or whatever OBN said). Note: even an exit-code-zero "Successful" line does NOT mean the push worked — the next stage verifies that.

**`verify_rrq`** — Capture pre-push timestamp using `date +"%Y-%m-%d %H:%M:%S"` (space-separated form — `journalctl --since` rejects ISO-8601 with `+HH:MM` offset; validated 2026-05-09 on box1-t10). Loop: every 5s, run `sudo journalctl -u tftpd-hpa --since "<pre_push_timestamp>" --no-pager 2>/dev/null | grep "RRQ from <ap-ip>"`. If a match appears, emit `rrq_seen` with the matched line and proceed to `poll_completion`. If 60s elapses with no match, emit `gate_2_awaiting_ack` with the diagnostic context and stop.

**`stuck_recover`** (only after Gate 2 ack) — Run `sshpass -p NomadComeIn ssh -o StrictHostKeyChecking=no nomad@<ap-ip> reboot` (Nomad-config AP credentials). Sleep 90s (handoff lesson 13). Re-enter `push` *exactly once*. If `verify_rrq` fails again after the recovery push, emit `aborted` with `reason: "stuck_state_recovery_failed"` — do not loop further; this is engineer territory.

**`poll_completion`** — Loop: every 90s (lesson 15: faster polling is wasted SNMP storm), run `sudo obn discover` and parse the AP's firmware version. Emit `polling_completion` event with `current_firmware`, `staged_firmware`, `poll_count`, `elapsed_seconds`. Loop until either:
- `current_firmware == target_firmware` → emit `completed` and exit successfully, OR
- `elapsed_seconds >= 900` (15 min) → emit `gate_3_awaiting_ack` with the current/staged/target tuple.

**`gate_3_awaiting_ack`** — Engineer chooses:
- `force-reboot` → run `sshpass -p NomadComeIn ssh nomad@<ap-ip> reboot`, sleep 90s, re-enter `poll_completion` once with a 5-min budget. (Force-reboot helps when staged_firmware == target_firmware but current didn't activate — handoff lesson 16.)
- `extend-poll` → re-enter `poll_completion` with another 15-min budget. Use sparingly; only if the engineer has reason to believe completion is imminent.
- `abort` → emit `aborted` with `reason: "completion_timeout_15min"` and exit.

**`verify_done`** — One final `sudo obn discover`. If `current_firmware == target_firmware`, emit `completed` with the full timing summary. Otherwise (rare race condition where the poll saw target but a quick re-check disagrees) emit `aborted` with `reason: "verify_done_disagrees"` and capture full diagnostic context.

## The five canonical commands

The skill's `--execute` mode runs exactly these (all from CCU via SSH):

```bash
# 1. Force fresh discovery (don't trust the every-5-min cache — lesson 15)
sudo obn discover

# 2. Read AP firmware state from discover.json (preferred) or validate (fallback)
sudo jq -r '.[] | select(.ip=="<ap-ip>") | [.config, .firmware] | @tsv' /tmp/discovery.json
sudo obn validate -t ap | grep -E "<ap-ip>|<ap-mac>"   # fallback if jq output empty

# 3. Capture pre-push timestamp (space-separated form — journalctl --since rejects ISO-8601 +HH:MM)
PRE_TS=$(date +"%Y-%m-%d %H:%M:%S")

# 4. The actual push
sudo obn update f <ap-ip>

# 5. RRQ verification (lesson 17 — journalctl, not /var/log/obn)
sudo journalctl -u tftpd-hpa --since "$PRE_TS" --no-pager 2>/dev/null | grep "RRQ from <ap-ip>"

# 6. Stuck-state recovery (Nomad-config AP credentials)
sshpass -p NomadComeIn ssh -o StrictHostKeyChecking=no nomad@<ap-ip> reboot
```

No batch flags. No `obn update f all`. No `obn update f ap`. No glob form.

## `--prepare` recipe shape

When the verdict is `ready_to_push` or `partial_flash_detected`, the skill prints a runnable shell recipe matching what `--execute` would do. The engineer can run it manually, or pipe it through `bash -x` for a full audit trail. The recipe includes inline comments at every decision point telling the engineer when to stop and what to check.

```bash
#!/usr/bin/env bash
# === dosto-ap-firmware-update recipe (manual run) ===
# AP:    <ap-ip> (<ap-mac>, <ap-hostname>)
# From:  <current_firmware>
# To:    <target_firmware>
# Pre-flight verdict: ready_to_push

set -euo pipefail

CCU=<ccu-ip>
AP=<ap-ip>
TARGET=<target_firmware>
KEY="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"

ssh_ccu() { ssh -i "$KEY" developer@$CCU "$@"; }

# === STEP 1: PRE-CHECK (read-only) ===
echo "[1/5] Pre-check: TFTP helper, OBN patches, AP reachability via obn discover..."
ssh_ccu 'lsmod | grep -q nf_conntrack_tftp && echo "tftp_helper:OK" || { echo "tftp_helper:MISSING — abort"; exit 2; }'
ssh_ccu "sudo ipset list tftp_allowed | grep -q '$AP' && echo 'ipset:OK' || echo 'ipset:NOT_LISTED — Bug 5 patch not active'"
# Trust obn discover, NOT standalone snmpget — `snmpget -v2c -c NomadStayOut!` times out on
# Nomad APs even when OBN is successfully polling them via SNMP (validated 2026-05-09 on Fzg 132).
# Pass if discover.json has the AP with Nomad-form config and non-null firmware.
ssh_ccu "sudo obn discover >/dev/null 2>&1; sudo jq -r '.[] | select(.ip==\"$AP\") | [.config // \"null\", .firmware // \"null\"] | @tsv' /tmp/discovery.json" | \
  awk -F'\t' '
    $1 ~ /^AP[1-4]m?-v1-/ && $2 != "null" { print "ap_reachable:OK (config=" $1 ", firmware=" $2 ")"; exit 0 }
    $1 ~ /^RT610LV-/ { print "ap_in_factory_config — run dosto-ap-config-update first"; exit 3 }
    { print "ap_not_in_discover_json — verify AP is up; consider snmpget fallback"; exit 3 }'

# === STEP 2: PUSH ===
echo "[2/5] Pushing firmware..."
# Use space-separated form, NOT `date --iso-8601=seconds`. The latter produces
# `2026-05-09T15:42:18+00:00` which `journalctl --since` rejects with
# "Failed to parse timestamp" (validated 2026-05-09 on box1-t10).
PRE_TS=$(ssh_ccu 'date +"%Y-%m-%d %H:%M:%S"')
ssh_ccu "sudo obn update f $AP"

# === STEP 3: VERIFY RRQ (60s window) ===
echo "[3/5] Watching journalctl for RRQ from $AP..."
for i in {1..12}; do
  if ssh_ccu "sudo journalctl -u tftpd-hpa --since '$PRE_TS' --no-pager 2>/dev/null | grep -q 'RRQ from $AP'"; then
    echo "RRQ seen at second $((i*5))"
    break
  fi
  sleep 5
  if [ $i -eq 12 ]; then
    echo "🔴 NO RRQ IN 60s — AP is in stuck-state"
    echo "Recovery: ssh nomad@$AP reboot && sleep 90 && retry the push once"
    echo "Stop here; reinvoke the skill once you've recovered the AP."
    exit 4
  fi
done

# === STEP 4: POLL COMPLETION (up to 15 min) ===
echo "[4/5] Polling for completion (up to 15 min)..."
START=$(date +%s)
DEADLINE=$((START + 900))
while [ $(date +%s) -lt $DEADLINE ]; do
  sleep 90
  ssh_ccu 'sudo obn discover >/dev/null 2>&1'
  CUR=$(ssh_ccu "sudo obn validate -t ap 2>/dev/null | grep -E '$AP' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+' | head -1")
  echo "  poll @ $(($(date +%s) - START))s: current=$CUR target=$TARGET"
  if [ "$CUR" = "$TARGET" ]; then
    echo "✅ Target firmware reached"
    break
  fi
done
if [ "$CUR" != "$TARGET" ]; then
  echo "🔴 15 MIN ELAPSED, current=$CUR != target=$TARGET"
  echo "Decisions:"
  echo "  - force-reboot: sshpass -p NomadComeIn ssh nomad@$AP reboot, then re-poll 5 min"
  echo "  - extend-poll: re-run STEP 4 for another 15 min"
  echo "  - abort:       leave AP at $CUR and document"
  exit 5
fi

# === STEP 5: VERIFY DONE ===
echo "[5/5] Final verification..."
ssh_ccu 'sudo obn discover >/dev/null 2>&1'
FINAL=$(ssh_ccu "sudo obn validate -t ap 2>/dev/null | grep -E '$AP' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+-[0-9]+' | head -1")
[ "$FINAL" = "$TARGET" ] && echo "✅ AP $AP at $FINAL" || { echo "🔴 verify_done disagrees: $FINAL"; exit 6; }
```

The exit codes 2-6 align 1:1 with the skill's verdict / event taxonomy, so an orchestrator can branch on them.

## Failure mode catalogue

| Symptom | Verdict / event | Skill behaviour |
|---|---|---|
| `nf_conntrack_tftp` not loaded | `preconditions_unmet:tftp_helper` 🔴 | Abort. Tell engineer to run `dosto-tftp-helper-check --apply-runtime`. |
| OBN patches < 8/8 | `preconditions_unmet:obn_patches` 🔴 | Abort. Tell engineer to run `dosto-obn-patches --apply` then `--persist`. |
| `<ap-ip>` not in `ip neigh` | `ap_not_found` 🔴 | Abort. Verify the AP IP from `dosto-device-discovery`. |
| AP MAC OUI ≠ `00:14:5a` | `ap_not_found` 🔴 | Abort. The IP isn't a Westermo AP — likely a switch IP or wrong train. |
| AP not in fresh `obn discover` AND `snmpget` fallback fails | `ap_in_factory_config` 🔴 | Abort. Run `dosto-ap-config-update` first. (Note: standalone `snmpget` alone is unreliable — always check `obn discover` first; only fall back to `snmpget -t 8 -r 2` when discover.json has no recent entry.) |
| AP shows config `RT610LV-...-FD` in discover.json | `ap_in_factory_config` 🔴 | Abort. Run `dosto-ap-config-update` first. |
| `current == target` | `already_at_target` ✅ | Skip cleanly. No-op. |
| `current ≠ target` BUT `staged == target` | `partial_flash_detected` 🟡 | `--prepare` recommends force-reboot only. `--execute` jumps to Gate 3 with `force-reboot` pre-suggested. |
| `obn update f` exited non-zero | `aborted: push_command_failed` 🔴 | Capture stderr verbatim. Likely a 9th OBN bug — escalate, do not auto-retry. |
| Push reported "Successful" but no RRQ in 60s | `gate_2_awaiting_ack` 🔴 | Engineer acks → SSH-reboot the AP, retry once. If second `verify_rrq` fails, abort. |
| RRQ seen, transfer started, but `obn discover` after 15 min still shows old version | `gate_3_awaiting_ack` 🔴 | Engineer chooses: force-reboot / extend-poll / abort. |
| RRQ seen + 15-min poll succeeded + `verify_done` disagrees | `aborted: verify_done_disagrees` 🟡 | Race condition. Capture full state. Rerun the skill `--prepare` to see current truth. |

## What this skill deliberately does NOT do

- ❌ Push more than one AP per invocation (lesson 11). Engineer (or orchestrator) invokes serially.
- ❌ Use `obn update f all`, `obn update f ap`, or any glob form.
- ❌ Push to an AP in factory config — routes to `dosto-ap-config-update`.
- ❌ Force-reboot APs without explicit Gate 2 / Gate 3 ack.
- ❌ Run if `dosto-tftp-helper-check` or `dosto-obn-patches` precondition fails — abort with clear remediation pointer.
- ❌ Trust `obn`'s "Successful" parsing alone (always cross-check journalctl + fresh discover) — lessons 12, 17.
- ❌ Trust `obn validate`'s 5-min cache (always force fresh `obn discover` after a push) — lesson 15.
- ❌ Loop stuck-state recovery indefinitely — exactly one SSH-reboot + retry, then engineer territory.
- ❌ Drive native `nft` or write to firewall config (that's `dosto-tftp-helper-check`'s scope).
- ❌ Attempt switch firmware updates — that's `dosto-sw-firmware-update`, qualitatively different (a bricked switch breaks the whole consist).

## Edge cases / gotchas (each tied to a handoff lesson)

- 🔴 **Lesson 11**: Even single-AP pushes can hang if TFTP helper is missing at the kernel level. The precondition catches this before any push fires.
- 🔴 **Lesson 12**: OBN's "Successful" only confirms the AP acknowledged the SSH command, not that firmware bytes transferred. The skill always verifies via `journalctl -u tftpd-hpa` for `RRQ from <ap-ip>`. No RRQ = no transfer.
- 🔴 **Lesson 13**: APs in stuck-state silently fake-succeed on retries. The skill detects stuck state (no RRQ in 60s) and applies the SSH-reboot workaround exactly once. Multiple consecutive fake-successes = engineer territory.
- 🟡 **Lesson 14**: Real completion takes 6-10 min typical, up to 15 min worst-case observed. OBN's internal 5-min wait is too short. Skill's poll budget is 15 min; Gate 3 fires only after that elapses.
- 🟡 **Lesson 15**: `obn discover` is a 30-45s SNMP storm on a 6-car consist. Don't poll faster than every 90s. The skill enforces this minimum cadence.
- 🟡 **Lesson 16**: `current (staged) ✗` is a *positive* signal — it means TFTP transfer landed but activation didn't. Force-reboot rather than fresh push; the skill's `partial_flash_detected` verdict handles this.
- 🟡 **Lesson 17**: `/var/log/obn/*.log` does not capture in.tftpd activity. The skill captures both OBN log + journal in its diagnostic output.
- 🟡 **AP credentials depend on config state.** Nomad-config APs use SSH `nomad/NomadComeIn`; factory APs use LuCI HTTP `admin/Nom@dCome1n` (skill aborts before reaching the latter — factory APs are out of scope here).
- 🟡 **`ssh nomad@<ap-ip> reboot` returns the SSH connection cleanly before the AP's network stack tears down.** Don't assume connection-close means the reboot started; sleep the full 90s.
- 🟡 **Standalone `snmpget` is unreliable on Nomad APs.** OBN's SNMP library polls them fine; vanilla `snmpget -v2c -c NomadStayOut! -t 3 -r 1` times out. The precondition uses `obn discover` + jq parse of `/tmp/discovery.json` as the primary AP-reachability signal, only falling back to `snmpget -t 8 -r 2` when discover.json has no recent entry. Validated 2026-05-09 on Fzg 132 — false-positive `ap_in_factory_config` on AP .226 with the standalone-only probe.
- 🟡 **`journalctl --since` rejects ISO-8601 with `+HH:MM` offset.** Don't use `date --iso-8601=seconds` (produces `2026-05-09T15:42:18+00:00` → `Failed to parse timestamp`). Use `date +"%Y-%m-%d %H:%M:%S"` (produces `2026-05-09 15:42:18` → parses fine). Validated 2026-05-09 on box1-t10.

## Pairs with

- [`dosto-tftp-helper-check`](../dosto-tftp-helper-check/SKILL.md) — precondition. Must return `all_present` or `puppet_persisted`. Without it, even single-AP pushes risk silent failure.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — precondition. Bug 5 (TFTP ipset pre-populate) is required for reliable transfers; Bugs 4/8 prevent crash on the report path.
- [`dosto-ap-config-update`](../dosto-ap-config-update/SKILL.md) — runs first on freshly-commissioned trains where APs are in factory config. Aborts route here.
- [`dosto-device-discovery`](../dosto-device-discovery/SKILL.md) — produces the AP IP list. The orchestrator iterates that list and invokes this skill per-AP serially.
- `dosto-commission-train` (orchestrator, not yet built) — drives this skill once-per-AP serially through the consist's AP list, surfacing each gate to the engineer.

## Reference

- handoff lessons 11–17 — the source-of-truth for every behaviour in this skill
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "OBN Firmware & Config Update — Known Bugs and Fixes" (Bug 5 context)
- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "CCU Firewall — TFTP conntrack helper missing" (precondition rationale)
- `journalctl -u tftpd-hpa` — real diagnostic source
- `/tmp/discovery.json` (produced every 5 min by `nd-backbone-discovery.timer`) — read by `obn validate`; force fresh with `sudo obn discover`
- auto-memory `project_tftp_conntrack_helper.md`, `project_ap_factory_config.md`
