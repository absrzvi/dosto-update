# Subagent Autonomy Boundary

**Status:** v2, 2026-05-20 (added `ensure_v8_templates` auto-reboot carve-out). v1 locked 2026-05-09.

What a per-train subagent may do without asking, and what it must request human approval for. This is workflow-level policy — distinct from Claude Code's tool-permission prompts (which are configured separately via `.claude/settings.json`).

## TL;DR

> **Anything reversible without rebooting → autonomous. Anything that survives reboot or affects passenger-facing service → approval gate.**

## What the subagent does without asking

### Read-only operations (always allowed)

- SSH to the CCU using the project key
- `cat`, `grep`, `ip addr`, `ip neigh`, `ip -s link`, `dhcp-lease-list`, `mount`, `uptime`, `hostname`
- `obn validate`, `obn discover` (these are read-mostly — `discover` writes `/tmp/discovery.prev.json` but doesn't change persistent state)
- `nc -zv` TCP probes
- `ping`
- All `--check` modes of project skills (`dosto-obn-patches --check`, `dosto-vlan7-config <train#>` — skill resolves Fzg from fleet-status row)
- Read project files: PDFs in `docs/`, anything in `train-ip-allocation-commission/`, `fleet-status.md`

### Reversible writes (autonomous)

- `sudo btrfs property set / ro false` followed by edits followed by `sudo btrfs property set / ro true`
- Apply OBN bug-fix scripts (`fix_obn.py`, `fix_obn_bugs67.py`, `fix_obn_bug8.py`, `fix_bug1_regex.py`) — these edit `/usr/share/obn/*.py` files which btrfs reverts on reboot if the snapshot isn't promoted
- Edit `train_id` line in `/etc/obn/template/nv6-*.cfg` — same reversibility property
- Edit `address1=` line in `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection`
- Clear stale rendered configs in `/data/auto-topology/upload/`
- `sudo nmcli con down vlan7 && sudo nmcli con up vlan7` (reapplies nmconnection — visible to live traffic but trivially re-runnable)

**Reversibility property:** these all live inside the active btrfs subvolume. If we don't promote via `nd-systemupdate.sh shell`, the next reboot lands on the previous snapshot and all edits are gone. The CCU is recoverable to the pre-edit state with a simple reboot.

### Local file writes

- Append/update rows in local `fleet-status.md` (orchestrator only — subagents emit JSON reports, never write the file)
- Push event-driven updates to Confluence page `5410684933` (orchestrator only — see [confluence-sync.md](confluence-sync.md))

## Approval gates (subagent stops, asks orchestrator, orchestrator asks human)

There are exactly **five** gates. Hitting any of them sets `status = NEEDS_APPROVAL` in the JSON report, sets `stage.id` to the corresponding `await_*` value, and pauses the subagent until a response is relayed back.

| Gate name | `stage.id` that emits it | Response shape |
|---|---|---|
| `promote_snapshot` | `await_promote_snapshot` | binary (`approved` / `denied` / `deferred`) |
| `safe_reboot` | `await_safe_reboot` | binary |
| `obn_update_c` | `await_obn_update_c` | binary |
| `obn_update_f` | `await_obn_update_f` | binary |
| `device_count_mismatch` | `await_device_count_mismatch` | **three-way** (`wait` / `partial` / `continue_full`) |

Four gates are binary: subagent wants to do a destructive thing, human says yes/no. The fifth is different in shape — see below.

The full stage list is in [subagent-report.md](subagent-report.md) → "Commissioning stage list".

### Gate 5: `device_count_mismatch` — three-way, not binary

**Trigger:** subagent's `dosto-device-discovery` skill found one or more missing devices (switch or AP missing from the expected count for the consist size).

**Why approval needed:**
- Consist-wide operations (`obn update c all`, `obn update f all`, L2 health check) are unsafe with an incomplete consist — pushing config to N-1 of N switches leaves the missing one in mixed-state when it eventually comes online (RSTP storm risk).
- The decision "wait for Stadler vs. proceed with what's there" is a judgment call about urgency vs. completeness — not something the subagent can make alone.

**Three-way response options** (per project requirement — see chat history 2026-05-09):

| Response | What the subagent does next |
|---|---|
| `wait` | Set `status = BLOCKED`, stop subagent, escalate to Stadler. Train waits for cable fix; nothing further happens autonomously. Human re-runs subagent after Stadler confirms fix. |
| `partial` | **Recommended default.** Proceed with CCU-local fixes only — OBN patches, train_id template, vlan7. Stop *before* `await_obn_update_c` and `await_obn_update_f`. Re-run discovery on next cycle to see if missing devices have appeared. |
| `continue_full` | Accept consequences. Subagent proceeds through every stage, including consist-wide pushes. Missing devices will be in unsynchronised state when they eventually come online. Used rarely — when human knows the missing device is being deliberately omitted, e.g. coach removed from service. |

The `--json` output of `dosto-device-discovery` (per [.claude/skills/dosto-device-discovery/SKILL.md](../skills/dosto-device-discovery/SKILL.md)) already structures the data the orchestrator needs to format this prompt — list of missing devices with their expected switch+port and a Stadler-actionable instruction per device.

**What the subagent has done before this gate:**
- Run all `--check` skills against the CCU
- Localised each missing device to a specific switch+port using the topology reference
- Produced an actionable Stadler instruction for each missing device

**What approval costs the human:** ~30 seconds reading the per-device Stadler-actionable instructions and choosing the default (`partial`) or one of the alternatives.

### What about the `ensure_v8_templates` reboot?

Per spec (2026-05-20): **not a gate, despite involving a reboot.** When `initial_diagnostics` finds no `nv6-*-v8-*.cfg` (or `nv4-*-v8-*.cfg`) files in `/etc/obn/template/`, the subagent autonomously runs `sudo /usr/sbin/nd-systemupdate.sh.dont up` (pulls v8 templates from Puppet via chroot), then `sudo systemctl reboot`, then probes TCP/22 every 10s for up to 300s, then re-verifies templates are present, then resumes at `apply_obn_patches`.

**Why this reboot doesn't need Gate-2 treatment:**
- Stage runs *before* `apply_obn_patches`, so runtime state worth preserving (TFTP CT helper, in-memory iptables, OBN patches in `/usr/share/obn/*.py`) hasn't been applied yet. Reboot wipes nothing valuable.
- The Puppet `up` apply is idempotent and the v8 templates are baseline-configurable — if the apply or reboot fails, recovery is "engineer SSHes in, re-runs `up`", same as the regular Gate 2 failure mode.
- Train-power-during-passenger-service consideration applies the same as Gate 2 — but the orchestrator can't disambiguate "engineer wants minimal interruptions" from "engineer doesn't want this specific reboot." Per the 2026-05-20 spec call, the carve-out is explicit: this reboot is auto, no prompt.

**Failure handling:** if `nd-systemupdate.sh.dont up` exits non-zero, OR templates are still missing after reboot, OR SSH doesn't return within 300s, the subagent sets `status = ISSUE`, adds the failure mode to `issues[]`, and halts *that one worker*. Other workers in the cycle keep running. No gate prompt to the engineer — they pick the failed train back up manually.

### What about AP factory-config bypass?

Per spec: **not a gate.** AP factory-config bypass via LuCI HTTP push happens autonomously inside `APPLYING_FIXES` / stage `ap_factory_bypass`. Reasoning: it's per-AP (not consist-wide), reversible by re-pushing a different config, and necessary before OBN can do anything with the APs. Treating it as a gate would block on something the engineer always wants done.

### Gate 1: `promote_snapshot`

**Trigger:** subagent is ready to run `sudo /usr/sbin/nd-systemupdate.sh shell` and exit, which promotes the new btrfs snapshot to default GRUB target.

**Why approval needed:**
- Once promoted, this is the new `release` snapshot. Reverting requires GRUB-level intervention on the physical CCU.
- A broken snapshot promotion = unrecoverable from remote. Engineer needs physical access to recover.

**What the subagent has done before this gate:**
- Verified all intended changes apply cleanly outside the chroot
- Re-checked that markers/values are correct on the live filesystem
- Confirmed the changes are necessary (skipped if already-persisted state)

**What approval costs the human:** ~30 seconds reading a `command_preview` and saying yes/no.

### Gate 2: `safe_reboot`

**Trigger:** subagent is ready to run `sudo /usr/local/sbin/safe_reboot`.

**Why approval needed:**
- Train CCU is offline for ~3 minutes during reboot
- Train may be carrying passengers — "is this an OK time to reboot" is a people decision, not a technology decision
- If the snapshot promoted in Gate 1 is broken, this is when you find out — by the train not coming back

**What the subagent has done before this gate:**
- Promoted the snapshot (Gate 1 already passed)
- Confirmed the new snapshot is set as default

**What approval costs the human:** confirming "yes, this train can be offline for 3 min right now."

### Gate 3: `obn_update_c`

**Trigger:** subagent wants to run `sudo obn update c all` or `sudo obn update c <ip>` — pushes config to one or more switches.

**Why approval needed:**
- Writes config to up to 18 switches in a 6-car consist
- Mid-run failure leaves the consist in a mixed v3/v4/v8 state — RSTP topology storms
- Cannot be aborted cleanly mid-run; you finish or you brick

**What the subagent has done before this gate:**
- Verified 10/10 OBN patches present (otherwise the run will crash, or hang at 100% CPU / leak RAM, mid-way)
- Verified `train_id` template is hardcoded to the right Fzg
- Verified vlan7 IP is correct (otherwise post-push verification fails)

**What approval costs the human:** confirming the consist can be touched right now (no other engineer working on it, no in-flight passenger systems that depend on a stable network).

### Gate 4: `obn_update_f`

**Trigger:** subagent wants to run `sudo obn update f all` or `sudo obn update f <ip>` — pushes firmware to switches or APs.

**Why approval needed:**
- Same blast radius as Gate 3 but with firmware-flash failure modes (longer per device, harder to recover if interrupted)
- Switches reboot during firmware push — full consist offline serially

**What approval costs the human:** confirming firmware push is intentional (vs. accidentally triggered by an `obn` rule update).

## What is NEVER autonomous, not even with approval

These are the boundaries of the entire workflow, not just the subagent:

- **GRUB-level recovery** — physical-access only, not in scope for any Claude session
- **Stadler cable fixes** — physical layer; subagent's job is to detect cable faults, not fix them
- **Customer-facing communication** — escalation to ÖBB / Stadler is a human responsibility
- **Editing this contracts directory or skill SKILL.md files** — subagents don't modify their own rules

## How approval works

See [approval-gates.md](approval-gates.md) for the full protocol. Short version:

1. Subagent emits JSON report with `status: NEEDS_APPROVAL` and `approval_needed: {...}`
2. Orchestrator surfaces it immediately to the human (not waiting for next 5-min cycle)
3. Human responds yes/no
4. Orchestrator relays to subagent via `SendMessage`
5. Subagent proceeds (or marks `BLOCKED` if denied) and continues

## Why this boundary, not tighter or looser

**Tighter (more gates) would slow the workflow without safety benefit.** Outside-chroot edits are reversible by reboot — there's no irreversible state to protect against. Adding gates for them is friction without value.

**Looser (fewer gates, e.g. autonomous chroot promotion) is too risky.** A bad chroot promotion makes the CCU non-bootable to the engineer's remote view; recovery requires console access on the physical train. The 30-second approval cost is well worth that protection.

**Specifically: not gating outside-chroot fixes is deliberate.** If `fix_obn.py` reports `PATTERN NOT FOUND` or vlan7 mismatch persists after the autonomous fix, the subagent reports the failure as an `issue` in the next cycle and the human sees it. No silent failures.

## Validating compliance

The subagent prompt should explicitly enumerate the four gates and require the subagent to set `status: NEEDS_APPROVAL` before *any* command matching:

- `nd-systemupdate.sh`
- `safe_reboot`
- `obn update c`
- `obn update f`

A subagent that runs any of those without an approval gate is a contract violation. The orchestrator should detect this in the SSH command log (capturing all subagent SSH commands and grepping for the four patterns) and escalate immediately.
