---
name: dosto-ap-config-update
description: Push Nomad config to a single Westermo AP. Use when pushing config to one AP, when an engineer says "obn update c" against an AP, or when a factory-config AP needs the LuCI HTTP bypass because OBN SNMP is silently blocked. Auto-detects whether the AP is on Nomad config (uses OBN's SNMP path `obn update c <ip>`) or factory config (uses LuCI HTTP bypass: login → flashops upload → rpcCfgApply). Default --prepare mode is read-only diagnostic + recipe print; opt-in --execute mode drives one AP through the full push autonomously, stopping at gates for engineer approval. Always single-AP serial — no batch glob. Pairs with dosto-ap-firmware-update (config push runs first on freshly-commissioned trains so SNMP opens up). Verifies completion via SNMP (preferred) and LuCI title (fallback).
---

# DOSTO AP Config Update

This skill pushes Nomad config to a single Westermo AP. It auto-detects whether the AP is on Nomad config (the OBN SNMP path) or factory config (the LuCI HTTP bypass) and drives the appropriate flow. On freshly-commissioned trains, **every** AP arrives in factory config — this skill is what gets each one onto Nomad config so SNMP opens up and `dosto-ap-firmware-update` becomes possible.

This is **config push only**. Firmware push is [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md) and runs after this skill on freshly-commissioned trains.

## When to use

- **Step 6 of [train-login-checklist.md](../../../train-login-checklist.md)** — after device discovery, OBN patches, vlan7/Fzg-id fixes, and *before* `dosto-ap-firmware-update`. SNMP must work for firmware push, and the only way to get factory APs answering SNMP is to push the Nomad config first.
- **One AP at a time, serially** — same family rule as firmware update. The skill rejects batch invocation.
- **When `obn validate -t ap` shows a `✗` in the config column** — that AP needs config push (regardless of whether it's already on Nomad config or still factory).
- **When a previous push left an AP in "Config Alert" state** — the upload landed but `rpcCfgApply` was never called. The skill detects this (verdict `pending_apply_only`) and runs only the cheaper apply step.
- **Never on more than one AP at a time without explicit engineer override.** Same single-AP-serial discipline as firmware update — even though config push has lower blast radius (no flash bricked on failure), parallel pushes generate concurrent reboot storms that can wedge fabric STP recalculation.

## Preconditions (skill aborts if any are not met)

| Precondition | Why | Failure verdict |
|---|---|---|
| `dosto-obn-patches` ∈ {`all_patched`, `all_persisted`} | Bug 7 (reboot-hostname guard) fires on the post-config-push reboot path; without it, OBN crashes mid-push and leaves the AP in inconsistent state. | `preconditions_unmet` 🔴 |
| AP is in `ip neigh` on vlan100 from the CCU | Confirms reachability. | `ap_not_found` 🔴 |
| AP MAC OUI is `00:14:5a` | Confirms it's a Westermo AP, not a switch IP or wrong train. | `ap_not_found` 🔴 |
| Rendered config file `/data/auto-topology/upload/dostoneu-obn-<macslug>.cfg` exists on CCU | LuCI flashops needs the file. OBN renders it during *any* `obn update c` attempt (success or failure), so the recipe says: run `sudo obn update c <ap-ip>` once to render, ignore the SNMP failure for factory APs, then re-invoke this skill. | `config_file_missing` 🔴 |
| Single AP only — no batch glob | Argument parser. | error before any SSH |

**TFTP helper is NOT a precondition.** Config push goes via SNMP (Path A) or HTTPS (Path B); neither uses TFTP. That's `dosto-ap-firmware-update`'s precondition only.

## AP state detection (the path fork)

Before deciding which execution path to take, the skill probes the AP's current state. Three SSH commands run from the CCU, in sequence:

```bash
# A. SNMP probe with Nomad community
snmpget -v2c -c NomadStayOut! -t 3 -r 1 <ap-ip> .1.3.6.1.2.1.1.1.0
#   exit 0 + value → ap_config_state = "nomad"
#   timeout/error  → likely factory; verify with B

# B. LuCI title fetch (only if A failed)
curl -k -s --connect-timeout 8 --max-time 12 "https://<ap-ip>/cgi-bin/luci/" \
  | grep -oE '<title>[^<]+'
#   "RT610LV-...-v1-FD - LuCI"  → ap_config_state = "factory"
#   "AP4-v1-...", etc.            → ap_config_state = "nomad" (SNMP gap is something else — investigate)
#   no response                   → ap_config_state = "unreachable"

# C. (only if factory) check for pending Config Alert
curl -k -s -c /tmp/ck.txt -b /tmp/ck.txt "https://<ap-ip>/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=Nom%40dCome1n" -o /dev/null
curl -k -s -b /tmp/ck.txt "https://<ap-ip>/cgi-bin/luci/" | grep "Config Alert"
#   present → previous push uploaded but didn't apply; only rpcCfgApply needed
#   absent  → fresh push needed (full Path B flow)
```

The detection drives which verdict the skill returns and which path `--execute` takes.

## Output modes

The skill has **two execution modes** plus the standard `--json` formatter switch — same shape as `dosto-ap-firmware-update`.

- **`--prepare` (default) — read-only.** Verify preconditions, run state detection, capture live state, print the equivalent shell recipe. No CCU writes, no AP changes.
- **`--execute` (opt-in) — autonomous driver.** Drives one AP through Path A or Path B, stopping at gates for engineer approval. Without `--execute`, no destructive command runs.

Both modes support `--json`. In `--execute`, JSON is streamed one event per line as the state machine progresses.

### Optional flags

| Flag | Effect |
|---|---|
| `--upload-only` | Path B only: stop after `flashops_upload`. Emits verdict `pending_apply_only` for later finishing. Useful when uploading a batch across a maintenance window then applying together. Default behaviour is full flow. |
| `--target-config <path>` | Override the config file path (default: `/data/auto-topology/upload/dostoneu-obn-<macslug>.cfg`). Used rarely — for testing alternate config rendering. |

### `--prepare` `--json` shape

```json
{
  "skill": "dosto-ap-config-update",
  "mode": "prepare",
  "schema_version": "1",
  "verdict": "ready_to_push_obn|ready_to_push_luci|pending_apply_only|already_nomad|preconditions_unmet|ap_not_found|ap_unreachable|config_file_missing",
  "raw": {
    "ccu_ip": "10.179.10.1",
    "ap_ip": "10.179.49.94",
    "ap_mac": "00:14:5a:04:b3:50",
    "ap_mac_slug": "00145a04b350",
    "ap_config_state": "nomad|factory|unknown|unreachable",
    "luci_title": "RT610LV-00145a04b350-v1-FD - LuCI",
    "config_alert_pending": false,
    "config_file_path": "/data/auto-topology/upload/dostoneu-obn-00145a04b350.cfg",
    "config_file_exists": true,
    "config_file_mtime": "2026-05-09T11:13:42Z",
    "config_file_size_bytes": 8472,
    "obn_patches_verdict": "all_persisted",
    "obn_validate_config_state": "x|✓|null",
    "snmp_probe_result": "ok|timeout|error",
    "luci_responsive": true,
    "execution_path": "obn|luci|none"
  },
  "recipe": "..."
}
```

`verdict` semantics:

- `ready_to_push_obn` ✅ — `ap_config_state=nomad`, `obn_validate_config_state=✗`. Run Path A (`obn update c <ip>`).
- `ready_to_push_luci` ✅ — `ap_config_state=factory`, no Config Alert pending. Run Path B (login → upload → apply).
- `pending_apply_only` 🟡 — `ap_config_state=factory`, Config Alert in LuCI title. Path B short-cut: skip login + upload, only `rpc_apply` + verify.
- `already_nomad` ✅ — SNMP responds AND `obn validate -t ap` shows `✓`. No-op.
- `preconditions_unmet` 🔴 — OBN patches not all good. Run `dosto-obn-patches` first.
- `ap_not_found` 🔴 — `<ap-ip>` not in `ip neigh` or MAC OUI ≠ `00:14:5a`. Wrong IP / wrong train.
- `ap_unreachable` 🔴 — Neither SNMP nor LuCI responds. AP may be mid-reboot from prior push (wait 90s and retry) or genuinely offline.
- `config_file_missing` 🔴 — `/data/auto-topology/upload/dostoneu-obn-<mac>.cfg` doesn't exist on CCU. Recipe says: `sudo obn update c <ap-ip>` once to render (ignore SNMP failure for factory APs), then re-invoke this skill.

`recipe` is non-null whenever verdict ∈ {`ready_to_push_obn`, `ready_to_push_luci`, `pending_apply_only`}. Recipe content matches the chosen execution path.

### `--execute` `--json` event stream

Same one-event-per-line streaming format as firmware update. Path A and Path B share most events with a `path` field:

```json
{"event":"started","timestamp":"...","ap_ip":"10.179.49.94","path":"luci","execution_mode":"full"}
{"event":"pre_check_passed","timestamp":"...","ap_ip":"10.179.49.94","ap_config_state":"factory","config_alert_pending":false}
{"event":"gate_1_awaiting_ack","timestamp":"...","ap_ip":"10.179.49.94","action":"luci_login"}
{"event":"gate_1_acked","timestamp":"...","ap_ip":"10.179.49.94"}
{"event":"luci_login_ok","timestamp":"...","ap_ip":"10.179.49.94","http_code":302}
{"event":"flashops_upload_ok","timestamp":"...","ap_ip":"10.179.49.94","http_code":200,"config_file":"...8472 bytes"}
{"event":"gate_2_awaiting_ack","timestamp":"...","ap_ip":"10.179.49.94","action":"rpcCfgApply (will reboot AP)"}
{"event":"gate_2_acked","timestamp":"...","ap_ip":"10.179.49.94"}
{"event":"rpc_apply_ok","timestamp":"...","ap_ip":"10.179.49.94","http_code":200}
{"event":"ap_down","timestamp":"...","ap_ip":"10.179.49.94","seconds_since_apply":18}
{"event":"ap_returned","timestamp":"...","ap_ip":"10.179.49.94","seconds_since_apply":74}
{"event":"snmp_verify_ok","timestamp":"...","ap_ip":"10.179.49.94","sysDescr":"AP4-v1-..."}
{"event":"completed","timestamp":"...","ap_ip":"10.179.49.94","total_elapsed_seconds":156,"final":true}
```

## Path A — OBN SNMP (Nomad-config APs)

State machine:

```
pre_check → push_obn (Gate 1) → verify_reboot → poll_completion → verify_done → completed
```

Two gates total: push approval, and (rare) extend-poll if AP doesn't return within 5 min.

### Stage details

**`pre_check`** — All preconditions + state detection in one SSH heredoc to the CCU. Confirm `ap_config_state == "nomad"`. If `obn_validate_config_state == "✓"`, return `already_nomad` and exit cleanly.

**`push_obn`** — Emit `gate_1_awaiting_ack` with the exact command. On ack, run `sudo obn update c <ap-ip>` over SSH from CCU. Capture stdout/stderr. Capture pre-push timestamp.

**`verify_reboot`** — Poll AP via ICMP (`ping -c 1 -W 2 <ap-ip>`) every 5s. AP should:
1. Go DOWN within ~30s (config-push reboot).
2. Come UP again within ~90s.

Emit `ap_down` and `ap_returned` events. Total budget: 5 min. If AP doesn't come back, emit `gate_2_awaiting_ack` with options: extend-poll / abort.

**`poll_completion`** — Once back up, run `sudo obn discover` then `sudo obn validate -t ap | grep <ap-ip>`. Config column should be `✓`. Poll every 60s for up to 5 min. Lesson 15 (don't poll faster than the 5-min cache rebuild) applies.

**`verify_done`** — One final `sudo obn discover` + `obn validate -t ap` confirms `✓`. Emit `completed`.

## Path B — LuCI HTTP (factory-config APs)

State machine (full flow):

```
pre_check → luci_login (Gate 1) → flashops_upload → rpc_apply (Gate 2) → verify_reboot → verify_nomad → completed
```

Three gates total: login, apply (post-upload), and (rare) extend-poll if AP doesn't return.

When verdict is `pending_apply_only`, skip directly from `pre_check` to `rpc_apply` (Gate 2). Login is skipped because we just need to confirm the prior session's cookies… actually no — the cookie file is per-session and ephemeral. **`pending_apply_only` re-runs login, then jumps straight to `rpc_apply`** (skipping `flashops_upload`).

### Stage details

**`pre_check`** — Confirm `ap_config_state == "factory"`. Detect Config Alert via the LuCI title. Confirm config file exists at `/data/auto-topology/upload/dostoneu-obn-<macslug>.cfg`. If `--upload-only` flag was passed, plan to stop after `flashops_upload`.

**`luci_login` (Gate 1)** — Emit `gate_1_awaiting_ack` with the curl command (with the URL-encoded password redacted in the event log). On ack:
```bash
COOK=/tmp/ck_<run-id>_<ap-ip>.txt
rm -f $COOK
curl -s -k -c $COOK -b $COOK \
  -X POST "https://<ap-ip>/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=Nom%40dCome1n" \
  -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 15
```
Expect HTTP 302. Anything else → emit `aborted: luci_login_failed` with the captured HTTP code (commonly 403 if the AP's password has already changed — i.e. Nomad config is partially applied; cross-check `ap_config_state` because the SNMP probe may have been a false-negative).

**`flashops_upload`** — Run from CCU:
```bash
curl -s -k -c $COOK -b $COOK \
  -X POST "https://<ap-ip>/cgi-bin/luci/admin/system/flashops" \
  -F "config=@<config_file_path>;type=text/plain" \
  -F "Import=Import Configuration" \
  -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 30
```
Expect HTTP 200. Anything else → emit `aborted: luci_upload_failed`. Common causes: malformed config file (re-render with `obn update c <ip>`), or transient HTTPS hiccup on the train cellular path (retry once before aborting).

If `--upload-only`, emit `completed_upload_only` with verdict `pending_apply_only` and exit. Engineer or the legacy `apply_ap_configs.sh` script can finish later.

**`rpc_apply` (Gate 2)** — Emit `gate_2_awaiting_ack` with the curl command (and explicit "this will reboot the AP" warning). On ack:
```bash
curl -s -k -c $COOK -b $COOK \
  -X POST "https://<ap-ip>/cgi-bin/luci/admin/rpc" \
  -H 'Content-Type: application/json' \
  -d '{"key":"rpcCfgApply","value":1}' \
  -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 15
```
Expect HTTP 200. **Connection-close after the apply call is normal** (the AP starts rebooting before the response completes). Treat 200 OR connection-close-after-200-headers as success; only treat clean non-200 responses as failure.

**`verify_reboot`** — Same as Path A: ICMP poll until down then up. Budget: 5 min.

**`verify_nomad`** — **Prefer SNMP over LuCI** (runbook quirk 3 — LuCI password may have changed post-apply, but the new SNMP community `NomadStayOut!` is deterministic):

```bash
snmpget -v2c -c NomadStayOut! -t 3 -r 1 <ap-ip> .1.3.6.1.2.1.1.1.0
```

If exit 0 with a `sysDescr` value: emit `snmp_verify_ok`, then `completed`.
If timeout: fall back to LuCI title check (login retry with `Nom@dCome1n`, then look at `<title>`). If the title no longer matches `RT610LV-...-v1-FD`, emit `luci_title_changed_only` with verdict `completed_partial` (config applied per LuCI but SNMP isn't responding — cross-reference `dosto-tftp-helper-check` and the SNMP firewall path; this is rare but real).
If both fail: emit `aborted: nomad_verify_failed` with diagnostic context.

## The canonical commands

Path A (OBN SNMP) — 5 commands, all from CCU:
- `sudo obn discover` — fresh discovery (lesson 15)
- `sudo obn validate -t ap | grep <ap-ip>` — read config column
- `sudo obn update c <ap-ip>` — the actual push
- `ping -c 1 -W 2 <ap-ip>` — reboot detection (loop)
- (final `obn discover` + `obn validate` for verify_done)

Path B (LuCI HTTP) — 5 commands, all via curl from CCU:
- `curl -X POST .../cgi-bin/luci/ -d luci_username=admin&luci_password=Nom%40dCome1n` — login
- `curl -X POST .../cgi-bin/luci/admin/system/flashops -F config=@<cfg>` — upload
- `curl -X POST .../cgi-bin/luci/admin/rpc -d '{"key":"rpcCfgApply","value":1}'` — apply
- `ping -c 1 -W 2 <ap-ip>` — reboot detection (loop)
- `snmpget -v2c -c NomadStayOut! ...` — Nomad-config verification

No batch flags. No `obn update c all`. No glob form.

## `--prepare` recipe shape

For Path B (the more elaborate of the two), the printed recipe is essentially the runbook section "Westermo AP Config Push" Step 3 + Step 5 wrapped in a script with verification:

```bash
#!/usr/bin/env bash
# === dosto-ap-config-update recipe (manual run) — Path B (LuCI HTTP) ===
# AP:           <ap-ip> (<ap-mac>, <ap-hostname>)
# State:        factory (Config Alert pending: <true|false>)
# Pre-flight verdict: ready_to_push_luci

set -euo pipefail

CCU=<ccu-ip>
AP=<ap-ip>
MAC_SLUG=<mac_slug>
PASS="Nom%40dCome1n"
KEY="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"

ssh_ccu() { ssh -i "$KEY" developer@$CCU "$@"; }

# === STEP 1: PRE-CHECK ===
echo "[1/5] Pre-check..."
ssh_ccu "ls /data/auto-topology/upload/dostoneu-obn-${MAC_SLUG}.cfg" >/dev/null \
  || { echo "🔴 config file missing — run 'sudo obn update c $AP' once on CCU to render"; exit 7; }

# === STEP 2: LuCI LOGIN ===
echo "[2/5] LuCI login..."
ssh_ccu "rm -f /tmp/ck_${AP}.txt && \
  curl -s -k -c /tmp/ck_${AP}.txt -b /tmp/ck_${AP}.txt \
    -X POST 'https://${AP}/cgi-bin/luci/' \
    -d 'luci_username=admin&luci_password=${PASS}' \
    -o /dev/null -w '%{http_code}\n' --connect-timeout 10 --max-time 15" \
  | grep -q 302 || { echo "🔴 login failed"; exit 8; }

# === STEP 3: FLASHOPS UPLOAD ===
echo "[3/5] Uploading config..."
ssh_ccu "curl -s -k -c /tmp/ck_${AP}.txt -b /tmp/ck_${AP}.txt \
  -X POST 'https://${AP}/cgi-bin/luci/admin/system/flashops' \
  -F 'config=@/data/auto-topology/upload/dostoneu-obn-${MAC_SLUG}.cfg;type=text/plain' \
  -F 'Import=Import Configuration' \
  -o /dev/null -w '%{http_code}\n' --connect-timeout 10 --max-time 30" \
  | grep -q 200 || { echo "🔴 upload failed"; exit 9; }

# === STEP 4: rpcCfgApply (REBOOTS AP) ===
echo "[4/5] Applying config (AP will reboot ~60-90s)..."
ssh_ccu "curl -s -k -c /tmp/ck_${AP}.txt -b /tmp/ck_${AP}.txt \
  -X POST 'https://${AP}/cgi-bin/luci/admin/rpc' \
  -H 'Content-Type: application/json' \
  -d '{\"key\":\"rpcCfgApply\",\"value\":1}' \
  -o /dev/null -w '%{http_code}\n' --connect-timeout 8 --max-time 15"

ssh_ccu "rm -f /tmp/ck_${AP}.txt"

# Wait for reboot
echo "  Waiting for AP to drop..."
START=$(date +%s)
while ssh_ccu "ping -c 1 -W 2 $AP >/dev/null 2>&1"; do
  sleep 5
  [ $(($(date +%s) - START)) -gt 60 ] && { echo "🔴 AP didn't drop in 60s — apply may have failed"; exit 10; }
done
echo "  AP down. Waiting for it to return..."
START=$(date +%s)
until ssh_ccu "ping -c 1 -W 2 $AP >/dev/null 2>&1"; do
  sleep 5
  [ $(($(date +%s) - START)) -gt 300 ] && { echo "🔴 AP didn't return within 5 min"; exit 11; }
done
echo "  AP back up."

# === STEP 5: VERIFY NOMAD CONFIG ===
echo "[5/5] Verifying Nomad config via SNMP..."
ssh_ccu "snmpget -v2c -c NomadStayOut! -t 3 -r 1 $AP .1.3.6.1.2.1.1.1.0" \
  && { echo "✅ AP $AP now on Nomad config"; exit 0; } \
  || { echo "🔴 SNMP verify failed — check LuCI title manually"; exit 12; }
```

Exit codes 7-12 align with the verdict / event taxonomy:
- 7 = `config_file_missing`
- 8 = `aborted: luci_login_failed`
- 9 = `aborted: luci_upload_failed`
- 10 = `aborted: rpc_apply_no_reboot` (AP didn't drop after apply)
- 11 = `aborted: ap_didnt_return`
- 12 = `aborted: nomad_verify_failed`

For Path A, the recipe is shorter: a single `ssh_ccu "sudo obn update c $AP"` followed by the same reboot-detection + verification loops.

## Failure mode catalogue

| Symptom | Verdict / event | Skill behaviour |
|---|---|---|
| OBN patches < 8/8 | `preconditions_unmet` 🔴 | Abort. Run `dosto-obn-patches` first. |
| `<ap-ip>` not in `ip neigh` / wrong OUI | `ap_not_found` 🔴 | Abort. |
| Neither SNMP nor LuCI responds | `ap_unreachable` 🔴 | Abort. AP may be mid-reboot from a prior push — wait 90s and retry. |
| `dostoneu-obn-<mac>.cfg` missing | `config_file_missing` 🔴 | Abort. Recipe says: `sudo obn update c <ip>` once on CCU (will fail at SNMP for factory APs but renders the file), then re-invoke. |
| SNMP responds + `obn validate` shows `✓` | `already_nomad` ✅ | No-op. |
| LuCI title contains "Config Alert" | `pending_apply_only` 🟡 | Path B short-cut: skip upload, only `rpc_apply` + verify. |
| `obn update c <ip>` exited non-zero (Path A) | `aborted: push_command_failed` 🔴 | Capture stderr. Likely a 9th OBN bug — escalate. |
| LuCI login returned HTTP ≠ 302 | `aborted: luci_login_failed` 🔴 | Capture HTTP code. AP password may have changed; cross-reference `ap_config_state` (a recent re-application would leave SNMP working but LuCI password rotated). |
| LuCI flashops upload returned HTTP ≠ 200 | `aborted: luci_upload_failed` 🔴 | Capture response. Check config file size/format; retry once before aborting. |
| `rpcCfgApply` returned HTTP ≠ 200 cleanly (not connection-close-after-200) | `aborted: luci_apply_failed` 🔴 | Capture response. Engineer can manually retry via `scripts/apply_ap_configs.sh`. |
| AP didn't drop after `rpcCfgApply` | `aborted: rpc_apply_no_reboot` 🔴 | Apply might have been a no-op; check LuCI title — if still `RT610LV-...-v1-FD`, the upload didn't actually stage. Restart from `flashops_upload`. |
| AP didn't return within 5 min | `gate_2_awaiting_ack` (Path A) / `aborted: ap_didnt_return` (Path B after extension exhausted) | Engineer chooses: extend-poll, abort, or manual debug. |
| Post-reboot SNMP times out (Path B) | falls back to LuCI title check; if title changed → `completed_partial`, else `aborted: nomad_verify_failed` 🔴 | Possible firewall path issue — cross-check that vlan100 SNMP firewall rule is in place. |
| Post-reboot LuCI title still `RT610LV-...-v1-FD` | `aborted: luci_title_unchanged` 🔴 | rpcCfgApply was a no-op or AP rolled back. Likely needs a fresh upload + apply (full Path B from scratch). |

## What this skill deliberately does NOT do

- ❌ Push more than one AP per invocation (same single-AP-serial discipline as firmware update). Engineer or orchestrator iterates.
- ❌ Use `obn update c all`, batch globs, or any parallel form. Even though config push is lower-blast-radius than firmware push, parallel reboots wedge fabric STP recalculation.
- ❌ Skip the `rpcCfgApply` step in Path B by default — the runbook quirk 1 explicitly warns about leaving APs in "Config Alert" state. `--upload-only` is opt-in only, with a clear verdict telling the engineer the apply still needs to happen.
- ❌ Push firmware. Routes to [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md).
- ❌ Edit config files in `/data/auto-topology/upload/`. Those are OBN-rendered from the templates in `/etc/obn/template/nv*-*.cfg`; if the rendering is wrong (e.g. wrong `train_id`), the fix is upstream (`dosto-fzg-id-check`), not here.
- ❌ Trust OBN's "configuration update applied" parsing alone — runbook quirk 4 explicitly calls this out as unreliable. Always verify post-reboot via SNMP (preferred) or LuCI title (fallback).
- ❌ Attempt to revert factory config back from Nomad. One-way push only.
- ❌ Use HTTPS certificate verification on LuCI (`-k` is intentional — Westermo APs ship with self-signed certs, and the management VLAN is the trust boundary).

## Edge cases / gotchas

- 🟡 **AP password changes after Nomad config applies** (runbook quirk 3). Post-reboot LuCI checks may need different credentials (per the rendered config's `admin_password_hash`), OR fall back to SNMP-based verification. Skill prefers SNMP for `verify_nomad` — deterministic.
- 🟡 **`Nom@dCome1n` URL-encodes to `Nom%40dCome1n`** for HTTP POST bodies. Skill encodes correctly in all recipe templates.
- 🟡 **`rpcCfgApply` HTTP response often returns before reboot completes** — sometimes 200 cleanly, sometimes connection drops mid-response. Both are normal. Don't fail on connection-close after the apply call returned 200 headers; only fail on clean non-200 responses.
- 🟡 **Cookie file names per-run** — `/tmp/ck_<run-id>_<ap-ip>.txt`. Each invocation uses a unique cookie file so concurrent invocations (rare but possible if engineer runs the recipe by hand while skill is mid-execute) don't clobber each other. Cleanup happens at the end of `--execute` regardless of success/failure.
- 🟡 **Path B's "Config Alert" detection happens BEFORE rendering decisions.** If the title says `Config Alert`, we know upload already happened in a previous session. Skip directly to `rpc_apply` (verdict `pending_apply_only`). Saves time and reduces risk (no second upload that could fail).
- 🟡 **Some factory APs have non-standard LuCI titles** (firmware-version differences). Detection matches `RT610LV-...-v1-FD` as the canonical factory marker AND falls back to "SNMP failed + LuCI responds" as a secondary factory indicator. If neither matches, emit `ap_config_state=unknown` and abort with diagnostic context.
- 🟡 **OBN rendering depends on `train_id` template state.** If `dosto-fzg-id-check` shows broken or inconsistent templates, the rendered `dostoneu-obn-<mac>.cfg` files contain the wrong hostnames. **Fix templates before pushing config**, otherwise every AP gets the wrong hostname baked in. The skill doesn't detect this directly (it only verifies file existence), so engineer must ensure `dosto-fzg-id-check` is `all_match` upstream.
- 🟡 **Path A's `obn update c <ip>` triggers an AP reboot just like Path B's `rpcCfgApply`.** Both need the 5-min reboot-detection budget. Path A doesn't show "Config Alert" because it's not staging — it pushes via SNMP and the AP applies + reboots in one step.
- 🟡 **Single-AP serial discipline applies to BOTH paths.** Even for Path A on already-Nomad APs, parallel `obn update c <ip>` invocations can cause `obn discover`'s SNMP polling to interleave with the in-flight reboots and produce confused state.

## Pairs with

- [`dosto-ap-firmware-update`](../dosto-ap-firmware-update/SKILL.md) — runs **after** this skill on freshly-commissioned trains. Every AP must be on Nomad config (SNMP responding) before firmware can push.
- [`dosto-obn-patches`](../dosto-obn-patches/SKILL.md) — precondition. Bug 7 (reboot-hostname guard) prevents OBN crash during the post-config-push reboot polling.
- [`dosto-fzg-id-check`](../dosto-fzg-id-check/SKILL.md) — must be `all_match` before config push, otherwise the rendered config files have the wrong hostnames baked in.
- [`dosto-device-discovery`](../dosto-device-discovery/SKILL.md) — produces the AP IP+MAC list to iterate.
- `scripts/push_ap_config.sh` — the existing manual upload script. Implements just login + flashops_upload. The skill's Path B `--prepare` recipe references this as the manual fallback for `flashops_upload`.
- `scripts/apply_ap_configs.sh` — the existing batch apply script. Implements login + Config Alert detection + `rpcCfgApply`. The skill's `pending_apply_only` flow is the single-AP analog.
- `dosto-commission-train` (orchestrator, not yet built) — drives this skill once-per-AP serially through the consist's AP list, then hands off to `dosto-ap-firmware-update`.

## Reference

- [troubleshooting-runbook.md](../../../troubleshooting-runbook.md) → "Westermo AP Config Push — Manual Method (When OBN SNMP Fails)" — the full manual procedure, all 6 steps
- auto-memory `project_ap_factory_config.md` — the persistent fact pointing at this issue, confirmed on 4734-120 (CCU 10.179.49.1) 2026-05-05
- `scripts/push_ap_config.sh` — single-AP upload (login + flashops_upload only; no apply)
- `scripts/apply_ap_configs.sh` — batch apply with Config Alert detection
- `scripts/push_remaining_aps.sh` — train-specific batch driver
- runbook quirk 1: LuCI import is two-step; uploading without applying leaves AP in Config Alert state (this skill's `pending_apply_only` verdict captures this)
- runbook quirk 3: AP password may change post-apply; SNMP verification is more reliable than LuCI re-login
- runbook quirk 4: OBN's "configuration update applied" message is unreliable; always verify post-reboot
