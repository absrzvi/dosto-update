# DOSTO Train L2 Network Health Check Playbook

This is the project guide for running consistent L2 network health checks on Stadler DOSTO trainsets equipped with VDS Rail Consist Switches and a Nomad Digital CCU. It's based on the methodology validated against Fzg. 146 (6-car) on 2026-05-02.

## When you log into a train — read these three files first

The v8 rollout is a stateful, multi-train workflow. Trains get powered off mid-update, Stadler cable fixes take days, and engineers must be able to pick up where the last person left off.

**For a project-wide view first** — if you're not sure which workstream you're picking up, or you want the bird's-eye "what's done / open / blocked" across everything (commissioning, SDD docs, Zabbix/NMS, OBN bugs, 6040/GPS, hardware faults), start at **[PROJECT-STATUS.md](PROJECT-STATUS.md)**. It's a derived summary that indexes every scoped tracker; for train-session work, the three files below remain the read-first.

1. **[fleet-status.md](fleet-status.md)** — single source of truth for "where did we leave off" on every train in the fleet. **Read the row for the train you're working on before doing anything else.** Update the row at the end of every session (Step 11 of the checklist below). Holds **current state only** — at-a-glance table + per-train diagnostic-state bullet lists.
2. **[fleet-journal.md](fleet-journal.md)** — narrative companion to fleet-status. Per-train append-only history: recovery sequences, discovered lessons, session context, Stadler investigation notes. Where fleet-status answers *"what is the current state"*, the journal answers *"what happened, in what order, and why."* Entries graduate to this file's "Pitfalls" section once observed on a second train.
3. **[train-login-checklist.md](train-login-checklist.md)** — the canonical 11-step procedure for any train session. Even on a fully-known train, follow it; the steps in order prevent the patches/cabling/AP-config issues that have caused real outages in this rollout.

The rest of this file is the *methodology* (how to read schemas, what counters mean, what "healthy" looks like). The checklist is the *workflow* (what to do, in what order). fleet-status is the *current state* (which trains are where). fleet-journal is the *history* (how each train got there).

## Knowledge base (`.kb/`) — component knowledge & "what already failed"

**[`.kb/`](.kb/)** is an [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)-format knowledge base: markdown docs, each with `type:` YAML frontmatter, organised **by component** (not by folder) so the distilled technical knowledge is reusable — including on a non-DOSTO project. Start at [`.kb/index.md`](.kb/index.md) (or [`.kb/HOW-TO-USE.md`](.kb/HOW-TO-USE.md)).

**When to read it:** troubleshooting a switch / AP / CCU-OBN, or picking up a cross-cutting subject (vlan7, RSTP, Zabbix, Fzg-ID). **Every component/topic doc has a `# Proven dead ends` section — check it before attempting a fix, so you don't re-test what's already been disproven on live hardware.** Structure: `components/` (VDS switch, Westermo AP, Nomad-Connect/OBN), `topics/` (vlan7, L2-health, coupled-RSTP, Fzg-ID, Zabbix, fv5/fv6 topology), `fleet/` (51 per-train identity records), `tickets/`, `deliverables/`, `assets/` (per-train PDF/cfg indexes).

**It complements, does not replace, the read-first files.** `fleet-status.md` remains the live source of truth; `.kb/fleet/*` records hold *stable identity + topology* and link back to it — never edit fleet-status from a KB record.

**Maintaining it** (do this as you learn things — the KB is meant to grow): see **[`.kb/MAINTENANCE.md`](.kb/MAINTENANCE.md)** for the doc format, the `type:` vocabulary, how to regenerate fleet records (`scripts/gen_kb_fleet_records.py`) and fv5/fv6 topology (`scripts/extract_fv_topology.py`), and the conformance check. Golden rule: it's **additive** — `.kb/` never moves or rewrites files outside itself (several scripts parse `fleet-status.md`/`CLAUDE.md` positionally). A newly-proven dead end is the single highest-value thing to add.

## Orchestration architecture (multi-train days)

For a multi-train commissioning day, the engineer doesn't drive each train manually. Instead they invoke `/dosto-orchestrate` with a list of **Train#** values (the Nomad-internal primary identifier, e.g. `4736-104`). The skill runs **inline in the engineer's top-level Claude session** — that session IS the orchestrator. It spawns N parallel `dosto-train-worker` subagents, one per train, and drives the cycle loop (gate prompts, fleet-status writes, Confluence pushes) until convergence.

```
Engineer types: /dosto-orchestrate trains=4736-102,4736-104,4736-120
       │
       ▼
[Engineer's top-level Claude session — running /dosto-orchestrate inline]
   • Validates train list against fleet-status.md (Train# row keys)
   • Resolves Fzg per train by reading the row (halts if Fzg cell is ❓)
   • Reconciles per-train (Train#, CCU IP) pairs; updates fleet-status if needed
   • Emits MANDATORY PRE-FLIGHT BLOCK for engineer approval
   • Spawns N workers in a single Agent multi-tool-use message
   • Drives cycle loop: notifications → gate prompts → SendMessage responses
   • Writes fleet-status.md per cycle (sole writer during runtime)
   • Pushes Confluence on gates + terminal states + cycle digests
       │
       ├─► Agent({subagent_type: "dosto-train-worker", name: "train-4736-102"})
       │      └─► /dosto-commission-train --train-number 4736-102 --ccu-ip 10.179.47.1 ...
       │            └─► dosto-device-discovery, dosto-obn-patches, dosto-fzg-id-check,
       │                dosto-vlan7-config, dosto-tftp-helper-check, dosto-ap-config-update,
       │                dosto-ap-firmware-update, dosto-sw-config-update, dosto-sw-firmware-update,
       │                dosto-l2-health, dosto-l2-report
       │
       ├─► Agent({subagent_type: "dosto-train-worker", name: "train-4736-104"})
       │      └─► /dosto-commission-train ...
       │
       ├─► Agent({subagent_type: "dosto-train-worker", name: "train-4736-120"})
       │      └─► /dosto-commission-train ...
       │
       ├─► Skill: dosto-confluence-sync --push  (on gates + terminals + cycle digests)
       │
       └─► writes fleet-status.md  (orchestrator-as-sole-writer during runtime)
```

**Roles, top to bottom:**

| Role | Purpose | Talks to |
|---|---|---|
| Engineer | Provides train list, answers approval gate prompts | Their top-level Claude session |
| Engineer's top-level Claude session (running `/dosto-orchestrate`) | Validates the train list, spawns workers in parallel, drives cycle loop, surfaces gates, writes fleet-status, pushes Confluence | Engineer + N workers |
| `dosto-train-worker` subagent (one per train) | Drives one train through the 19-stage pipeline by invoking `dosto-commission-train` | The engineer's session (parent) |
| `dosto-commission-train` skill | The 19-stage pipeline; sequences per-device skills | The worker that invokes it |
| Per-device skills (`dosto-obn-patches`, `dosto-ap-firmware-update`, etc.) | Single-purpose CCU operations | `dosto-commission-train` |
| `dosto-confluence-sync` skill | Pushes fleet-status.md → Confluence page 5410684933 | The engineer's session |

**Why inline rather than agent-as-orchestrator** (audit finding F5, 2026-05-11): the Claude Code platform rule "subagents cannot spawn further subagents" means a `dosto-orchestrator` agent spawned via `Agent` cannot itself call `Agent` to spawn workers — verified by the 2026-05-11 first-run test. The orchestration logic therefore lives in the skill, executed by the engineer's top-level session (which DOES have `Agent` + `SendMessage`). The previous `.claude/agents/dosto-orchestrator.md` was retired. See [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md) §F5.

**The five contracts** that pin this stack down:

| Contract | What it specifies |
|---|---|
| [`.claude/contracts/subagent-report.md`](.claude/contracts/subagent-report.md) | JSON shape every subagent emits (statuses, stages, fields, approval_needed) |
| [`.claude/contracts/autonomy-boundary.md`](.claude/contracts/autonomy-boundary.md) | Five approval gates and what subagents may do without asking |
| [`.claude/contracts/approval-gates.md`](.claude/contracts/approval-gates.md) | Engineer-facing prompt format and response protocol |
| [`.claude/contracts/confluence-sync.md`](.claude/contracts/confluence-sync.md) | One-way local → Confluence push policy + drift detection |
| [`.claude/contracts/auto-scanner-boundary.md`](.claude/contracts/auto-scanner-boundary.md) | Read-only bounds + fleet-status write-allowlist for the `dosto-auto-scan` scheduled probe (strict mutex with `/dosto-orchestrate`) |

**Single-train debug runs** skip the orchestrator skill entirely: invoke `/dosto-commission-train --train-number ... --ccu-ip ...` directly, no worker subagent, no fleet-day wrapper.

### In-flight claim and heartbeat mechanism (multi-session visibility)

The orchestrator marks each train it spawns a worker for by writing an **in-flight claim** to the row's `Nomad status` cell in `fleet-status.md`. Format:

```
🔵 IN PROGRESS — stage <stage_id> (<step>/<total>, t+<elapsed>), hb <iso8601>, sess <session-id>
```

The orchestrator refreshes this claim on four triggers: worker spawn (initial write), every stage-transition report, every step-within-stage report, and every cycle digest (5-min wall-clock liveness ping even if no worker reports arrived). When a worker reaches a terminal state (DONE / BLOCKED / PAUSED / ERROR), the orchestrator clears the claim and writes the appropriate terminal status.

**Why this matters for multi-session days:** on a busy commissioning day an engineer may have multiple `/dosto-orchestrate` sessions running in parallel (one for the morning's batch, another opened later when more trains come online). Every session and every other engineer reading `fleet-status.md` can see at a glance which trains are claimed right now and how fresh the claim is. The orchestrator's Step 6.0 concurrency check uses this signal to halt a spawn that would step on another session's active claim.

**Stale claims** (heartbeat age > 30 min) almost always mean the claiming session died. `/dosto-morning-brief` surfaces these as a stale-claim gate per train: engineer chooses `[c]lean` (flip to PAUSED) / `[k]eep` (still working) / `[s]kip`. The Python flag `--clean-stale-claim <TRAIN#>` does the actual write.

**Parser/formatter helpers** live in [`scripts/fleet_status_lookup.py`](scripts/fleet_status_lookup.py) as `parse_in_flight()` / `format_in_flight()` / `heartbeat_age_seconds()`. Skills consuming claim data MUST use these — the cell format is canonical and load-bearing across skills.

## Universal Principles (constitutional)

These four principles sit alongside the per-train safety rules and apply to every agent, every skill, every change. Derived from Andrej Karpathy's observations on where LLM coding agents go wrong: silent assumptions, overcomplication, drive-by refactoring, and weak success criteria. Source: https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md.

**Tradeoff:** these principles bias toward caution over speed. For trivial fixes (typo, comment update, log-line tweak) apply with judgment. For anything touching a contract, an approval gate, or a per-device skill that runs against a CCU, apply in full.

### Principle 1 — Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before any stateful action (spawning a subagent, calling a destructive skill, writing fleet-status, pushing Confluence):
- State your assumptions explicitly. If uncertain, ask — do not guess.
- If multiple interpretations exist, present them. Do not pick silently.
- If a simpler approach exists than the one requested, say so. Push back when warranted.
- If something is unclear, stop. Name what is confusing. Ask.

Operationalised as the **MANDATORY PRE-FLIGHT BLOCK** every agent must emit before its first stateful action — see [`.claude/agents/dosto-train-worker.md`](.claude/agents/dosto-train-worker.md) (the worker) and the orchestration section of [`.claude/skills/dosto-orchestrate/SKILL.md`](.claude/skills/dosto-orchestrate/SKILL.md) (the `dosto-orchestrator.md` agent was retired 2026-05-11 per audit F5 — its logic folded into that skill).

The five approval gates ([`.claude/contracts/autonomy-boundary.md`](.claude/contracts/autonomy-boundary.md)) are this principle in concrete form for destructive ops: stop, surface, ask the human.

### Principle 2 — Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No skill options that aren't currently used by any caller.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested by a real failure mode.
- No error handling for impossible scenarios.

The senior-engineer test: "would a principal engineer say this is overcomplicated?" If yes, simplify before shipping.

Special-case for our stack: **single-AP / single-switch serial pushes** (handoff lesson 11) are the canonical Simplicity First constraint at the per-device layer — never re-introduce parallel batches for `obn update f` without evidence that the underlying CCU firewall TFTP-helper gap has been fixed in Puppet.

### Principle 3 — Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code or files:
- Don't "improve" adjacent skills, contracts, or agent definitions while editing one of them.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code or stale notes, mention it — don't delete it.

When the orchestrator writes `fleet-status.md`, it edits **only the columns it owns** (the `fields` block from subagent reports — per the Surgical-Changes contract, now in `dosto-orchestrate/SKILL.md` since the `dosto-orchestrator.md` agent was retired). Engineer hand-edits to other columns (`Customer report`, `Health check date`) survive every cycle.

When `dosto-confluence-sync` detects drift on the Confluence page, it **halts** rather than auto-merging. Surgical: don't auto-resolve what wasn't the skill's mess to begin with.

The test: every changed line in a diff must trace directly to the user's request, the active stage, or the active skill's stated scope.

### Principle 4 — Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform imperative tasks into verifiable goals:

| Instead of...                  | Transform to...                                                          |
|---|---|
| "Push firmware to AP"          | "Confirm AP at target firmware via fresh `obn discover`, not OBN's 'Successful' string" |
| "Apply OBN patches"            | "Confirm 10/10 markers present in `/usr/share/obn/*.py` via grep, including post-reboot for persisted variants" |
| "Update Confluence"            | "Push, then read back the new version number; log it for next cycle's drift check" |
| "Train commissioning DONE"     | "All success criteria for this train are ticked: 10/10 OBN persisted, switches at target firmware+config, all visible APs at target firmware, vlan7 reachable to Stadler, customer report on disk" |

The orchestrator's end-of-day digest enumerates per-train success criteria as checkboxes. Don't claim DONE without ticking them.

For multi-step skill flows: state the brief plan (per-stage `expected_duration_seconds` in the contract), report `current_step / total_steps` as you go, and surface any step that exceeds its budget.

### Principle 5 — Parallelize When Independent

**Run independent operations in parallel; serialise only when there's a real dependency.**

This is a workflow extension, not part of the original four. Applied to our stack:

- The orchestrator spawns N per-train subagents in parallel (one per Fzg in the day's plan).
- Subagents in `initial_diagnostics` should batch the 5 `--check` skills into one SSH heredoc (already done partially by `dosto-commission-train` stage 1).
- Independent tool calls in the same agent message — fan out, don't sequentially `await` each.

**Counter-cases (where serial is correct):**
- AP firmware push — single-AP serial only (handoff lesson 11). Principle 1 (think before doing) wins over Principle 5 (parallelize) when there's evidence of unreliability under concurrency.
- Switch firmware/config push — leaf-first OBNTree order. Same principle: a parent reboot would isolate its children.

When in doubt, prefer serial — but document the reason. Default-parallel should be the goal once evidence supports it.

### Written comms rule (Jira / Confluence / email)

Anything written to an external audience — Jira tickets and comments, Confluence pages, email — must be **professional, concise, and warm**: no emoticons or emoji, no walls of text. Lead with the ask in 1–2 lines; use short numbered lists; put deep technical detail in a linked doc or attachment, never in the comment body. (Lesson from RD-12433, 2026-06-09: a long ticket body got "i'm not going to read this huge wall of text" from R&D.)

## Architecture cheat-sheet

A typical DOSTO consist has:

- **VDS Rail Consist Switches** — one per FIS unit (typically 3 per car: A1/A2/A3, B1/B2/B3, etc.). MAC OUI `a0:59:3a`. SSH on TCP/22 with legacy KEX/host-key algorithms. Custom CLI (not bash — commands cannot be `;`-chained over SSH). DHCP lease lifetime is 2 minutes — always run `sudo dhcp-lease-list` on the CCU for current IPs and hostnames rather than relying on stale ARP.
- **Westermo industrial radios/APs** — MAC OUI `00:14:5a`. Also on the management VLAN. Also on 2-minute DHCP leases; use `sudo dhcp-lease-list` for current state.
- **Nomad CCU (`box1-tNN`)** — Debian Linux jump box. Aggregates cellular modems on `bond0` (10.179.X.1/25) and the management VLAN on `vlan100` (10.179.X.129/25). Other interfaces are PWLAN client VLANs (10/30), ÖBB internal services (46/47/48), and Stadler interconnect (vlan7, 172.19.196.0/17).
- **Stadler firewall/gateway** — peer endpoint on vlan7, host octet `.1` (MAC `00:90:e8:...` Westermo). Performs inter-VLAN routing for all Stadler-side device VLANs (cameras VLAN 5, displays VLAN 3, AFZ VLAN 8, intercom VLAN 9, OBS VLAN 7, RDC VLAN 200/202, energy meter VLAN 12, etc.). The CCU does NOT see those device VLANs directly — only the vlan7 transit link. The vlan7 IP is **per-train** and follows a bit-packed addressing scheme — see "vlan7 IP formula" below.
- **Inter-coach trunks** are typically `e0-0` and `e0-1` on each consist switch. On modern consists these are 10 Gbps; older consists may run 1 Gbps.

Schema PDFs (one per Fzg. ID) live in `docs/`. Always read the schema for the specific train before running a check — VLAN ranges and per-port assignments change between consists.

## vlan7 IP formula

DOSTO NEU IPs use a bit-packed addressing scheme:

```
bits  1-12 : 172.19         (static prefix, always 172.19.x.x/17 for DOSTO NEU)
bits 13-17 : VLAN ID        (5 bits, 1-31; vlan7 = 0b00111)
bits 18-25 : Fzg ID         (8 bits, 1-255; from the IP-Port-Allocation PDF header)
bits 26-32 : Device          (7 bits, 1-127; CCU on vlan7 is always device 2; firewall is .1)
```

For the CCU's vlan7 IP, this packs to:

```
octet 3 = 128 + (Fzg // 2)
octet 4 = (128 if Fzg is odd else 0) + 2
IP      = 172.19.<octet3>.<octet4>/17
```

Even Fzg → host `.2`. Odd Fzg → host `.130`. The Stadler firewall is always `.1` on the same `/17` (e.g. Fzg 133 vlan7 = `172.19.194.130/17`, Stadler FW = `172.19.194.1`).

**Important:** the formula in `/etc/nd-redundancy/networks.yaml` on production CCUs is wrong (it computes from OBN's `train_id` instead of Fzg ID). The active vlan7 IP comes from `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection`, which is set per-train via `nd-systemupdate.sh shell`. Verify with [.claude/skills/dosto-vlan7-config/SKILL.md](.claude/skills/dosto-vlan7-config/SKILL.md) before any L2 health check — Stadler-side reachability depends on this being correct.

**Train#-and-Fzg convention (2026-05-22 schema reorder).** Train# (the Nomad-internal name, e.g. `4736-104`) is the **primary identifier** across all skills, scripts, contracts, and the orchestrator argument form. Fzg ID is the ÖBB customer-facing number, derived from the fleet-status row by Train#.

**Series → Fzg mapping shorthand** (reference only — runtime Fzg comes from the fleet-status row via `scripts/fleet_status_lookup.py`; the PDF header is the off-line source of truth):
- `4734-NNN → Fzg = NNN - 100`  (e.g. 4734-119 → Fzg 19)
- `4736-NNN → Fzg = NNN + 28`   (e.g. 4736-104 → Fzg 132)
- `4705-NNN → Fzg = NNN + 128`  (e.g. 4705-103 → Fzg 231)
- `4706-NNN → Fzg = NNN + 88`   (e.g. 4706-103 → Fzg 191)

⚠️ **Skills NEVER trust the formula at runtime.** Misimaged CCUs, stale Puppet images, and hand-set wrong values mean rendered Fzg values on the live CCU (in switch hostnames, `train_id` template, vlan7 IP encoding) are often wrong pre-commissioning — that's literally what commissioning fixes. If the fleet-status row's Fzg cell is `❓`, skills halt and ask the engineer to populate it (look up via PDF or physical inspection). Engineer can also pass `--fzg <N>` explicitly to override.

## Required access

- **CCU SSH key**: `openssh` (OpenSSH RSA, no passphrase) in this folder. Originally converted from `pvt_key.ppk` via PuTTYgen. To SSH: `ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>`.
- **Switch admin password**: `Nom@dCome1n` (use with `sshpass`). Switches require legacy SSH algorithms — see the connect snippet below.
- **Tools on CCU**: `sshpass`, `fping`, `ip`, standard ping, `nc`. iperf3 may or may not be installed — check with `command -v iperf3`.

## OBN / template release + deploy pipeline (how a change reaches a train)

A config/firmware/engine change is NOT live on trains until it walks the **whole** pipeline. Merging git is only step 3 of 7. (Full detail + gotchas: memory `project_obn_deb_publish_process` and `project_puppet_deploy_chain_vmpuppet01`.)

```
1 edit templates/engine → 2 bump version → 3 git push/merge → 4 build .deb →
5 publish to vmrepo01 (apt repo) → 6 pin the version in the Puppet env (hieradata) →
7 deploy the env to the vmpuppet01 MASTER → 8 factory up / puppet agent -t on the CCU (pulls from master)
```

**Two package families, two publish paths:**
- **Templates** (`nd-obn-template-dostoneu-{nv4,nv6,fv5,fv6}`): NO CI. Build with `./build.sh` (needs `fpm`; `dpkg-deb` equivalent works — see repo `PUBLISHING.md`). Publish MANUALLY: `scp <deb> admin21net@vmrepo01.ovh2.21net.com:/tmp/` then `ssh` + `sudo nd-registerpkg-bookworm.sh /tmp/<deb>` (registers into **unstable**, `-promote` moves to main). Script refuses duplicate versions — always bump `version` first.
- **OBN engine** (`onboard/obn`, package `nd-obn`): HAS CI. Release = merge MR + `make tag` (git tag) → CI builds+publishes. Do NOT hand-build/publish the engine — it's shared across all fleets and CI-gated (653-test suite).

**The deploy step (6→8) is agent/master, not CCU-pulls-git.** CCUs are Puppet agents fetching their catalog from the master `vmpuppet01.ovh2.21net.com`, which holds a git clone per branch at `/etc/puppetlabs/code/environments/<env>_<branch>` (DOSTO = `dostoneu_migration_mar5`; ALL DOSTO trains deploy from the `migration_mar5` branch). Merging to GitLab does **nothing** to trains until the master's clone is refreshed: `rake ci:deploy:remote` (= `ssh admin21net@vmpuppet01 'cd <envdir> && nd-update-puppetenv.sh migration_mar5'`). The master routinely LAGS GitLab — verify with `nd-systemupdate.sh.dont version` on a CCU (its "Remote version" = the master's copy, compare to GitLab HEAD).

**Access:** the release identity is user `admin21net` (Abbas's `~/.ssh/id_ed25519`, the same key as git-nc). As of 2026-07-03 it is on git-nc + vmrepo01 + **vmpuppet01** (all three) — so Abbas can run the full pipeline end-to-end. ⚠️ **WSL2 does not route the Windows VPN** — scp/ssh to these hosts from **Git-Bash (Windows)**, not WSL; WSL-built debs are reachable from Git-Bash at `//wsl$/Ubuntu/home/<user>/...`.

**The master does NOT auto-sync** — proven 2026-07-03: pushed to `migration_mar5`, but 3 CCUs still reported the old commit ~a day later. You MUST run the deploy after any push:
```
ssh admin21net@vmpuppet01.ovh2.21net.com
cd /etc/puppetlabs/code/environments/dostoneu_migration_mar5 && sudo nd-update-puppetenv.sh migration_mar5
```
Verify the CCU picks it up: `nd-systemupdate.sh.dont version` on a CCU → its "Remote version" should now match GitLab HEAD.

**`dbc12` / the `:9494` env API on vmpuppet01 is NOT a deploy shortcut** — it only SELECTS which branch a CCU uses (`dbc12 <fqdn> <branch>`) and clears certs (`dbc12 -c <fqdn>` — needed after a re-IP factory-up when you hit "certificate does not match its private key"). It does not refresh env code. DOSTO CCUs are already set to `migration_mar5`.

**⚠️ box=Fzg does NOT work for 6-car/CAT/FV** (memory `project_box_fzg_breaks_127_octet_limit`): `factory up` train-ID caps at 0–127 (= 3rd IP octet), but Fzg for 4736/4706/4705 is 129–231. box=Fzg only fits 4734 (Fzg 1–90). The v9 templates' remap-drop assumes train_id=Fzg → renders wrong hostnames on a box-id-commissioned 6-car/CAT/FV train. Needs an R&D decision (fzg_id-key path for those fleets). Don't `obn update c` a CAT train commissioned with box-id.

## Standard SSH-into-switch snippet

The VDS Consist Switch SSH server requires legacy algorithms. Use this from the CCU:

```bash
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no"
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "show interface summary"
```

The CLI takes ONE command per session. To run multiple commands, loop: do not use `;` chaining — that errors with `Error in command, param is "..." [wrong]`.

## Phase 1 — Discovery

```bash
# From your local machine, connect to the CCU:
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>

# On the CCU, sweep vlan100 to find consist switches and Westermo radios:
fping -a -q -g 10.179.X.128 10.179.X.255

# Then list ARP with vendor groups:
ip neigh show dev vlan100 | grep "lladdr a0:59:3a" | sort -t. -k4 -n   # VDS switches
ip neigh show dev vlan100 | grep "lladdr 00:14:5a" | sort -t. -k4 -n   # Westermo
```

Sanity-check: a 6-car DOSTO usually has 18 VDS switches (3 per car × 6 cars); a 4-car has 12.

## Phase 2 — Map switch IPs to schema positions

The schema labels switches A1/A2/A3, B1/B2/B3, ... — but the live IPs are just sequential. Match them by config fingerprint, NOT by trying to SSH-discover hostname (the switches return blank hostnames in `show system`).

Fingerprints to identify special switches:

| Schema role | Identifier (look at `show interface trunks` and `show vlans`) |
|-------------|----------------------------------------------------------------|
| **A3** (Stadler firewall switch) | `e1-4` is configured as a multi-VLAN trunk |
| **B1** / **B3** (ZFR-connected) | `e1-11` is access on VLAN 2 |
| **D1** / **D3** (OBS + RDC) | `e0-3` is configured as a trunk (RDC); `e0-2` carries OBS VLAN 7 trunk |
| End-of-train (last car each end) | `e0-1` is admin-enabled but link DOWN — this is normal |

Once you've identified A3/B1/B3/D1/D3, you have the critical Stadler-facing trunks for the rest of the check.

## Phase 3 — The L2 health sweep

These are the four canonical commands. Run on every switch.

```text
show interface summary                # all ports up/down/speed/duplex at a glance
show interface <port> details         # per-port: RX/TX errors, CRC, carrier-false, drops, collisions
show interface trunks                 # which ports are trunks, which VLANs they carry
show spanning-tree                    # RSTP root, port roles, port states (FWD/BLK/LEARN)
show vlans                            # VLAN-to-port mapping, identify access vs trunk
```

Useful supporting commands:

```text
show counters protocol lldp           # LLDP TX/RX per port, errors
show counters protocol ttcmp          # train discovery protocol
show system temperature               # ambient/internal temp (max 100°C)
show system memory                    # RAM usage
show version                          # firmware version
show log                              # event log (link flaps, STP TCNs, etc.)
```

### What to look for

| Field in `show interface <port> details` | Meaning | Threshold |
|-------------------------------------------|---------|-----------|
| `RX errors` / `runts` / `giants` / `frag` / `jabber` | Frame-level RX errors | Should be 0 — one or two over millions of packets is noise |
| `RX crc errors` | CRC mismatch on receive | Must be 0 — non-zero = bad cable / dirty connector / EMI |
| `TX crc errors` | TX side CRC | Must be 0 |
| `carrier false` | Link-layer instability events / surge protection trips | Should be 0 — non-zero = physical-layer problem (cable, SFP, vibration) |
| `Excessive collisions` / `Late collisions` | Half-duplex contention | Must be 0 on full-duplex links |
| `pause frames received` / `sent` | Flow-control pressure | Non-zero = queue overflow somewhere |

### What "healthy" looks like (for context)

In the Fzg. 146 baseline, every one of ~500 enabled ports across 18 switches showed 0/0/0/0 across all of the above. One port (`.182 e1-8`) had a single RX error against millions of packets — that's noise.

If you see a port with non-zero counters in the hundreds or higher, that port (or its physical link) is the suspect. Cross-check the port at the OTHER end of the same link too — RX errors on side A often pair with TX problems on side B.

## Phase 4 — Critical Stadler-facing trunks

Beyond the inter-coach uplinks, these are the trunks that matter for Stadler-side health:

| Schema port | Carries | What to verify |
|-------------|---------|----------------|
| **A3 e1-4** | Stadler firewall trunk (multi-VLAN: 1, 2, 3, 5, 6, 7, 8, 9, 12) | Up at 1G full, error counters 0, utilization sane |
| **D1 e0-2 / D3 e0-2** | OBS D1 trunk (huge VLAN list incl. 7, 200, 202) | Up at 10G full, error counters 0 |
| **D1 e0-3 / D3 e0-3** | RDC D1 trunk (VLANs 200, 202) | Up at 10G full, error counters 0 (often idle if RDC powered off) |
| **B1 e1-11 / B3 e1-11** | ZFR access port (VLAN 2 only) | Up at 1G full, error counters 0. ZFR R/ZFR are redundant pair sharing one IP — often only one is actively transmitting |
| **A1/A3/B1/B3 e0-2** | Front coupler trunks | Down when consist is solo (expected); zero error counters historically |
| **All e0-4** | Wi-Fi access point trunks | Up at 1G, zero errors expected |

Run `show interface <port> details` on each. Speed/duplex must match the schema's expected.

## Phase 5 — Throughput / utilization sampling

To compute live rate on any port, take two `show interface <port> details` snapshots N seconds apart and diff the byte/packet counters. Useful for the firewall trunk to confirm it's not saturated.

```bash
# Pseudo-code: sample twice with timestamps, then
rate_mbps = (rx_bytes_2 - rx_bytes_1) * 8 / (ts2 - ts1) / 1e6
```

Expected baselines (Fzg. 146 idle / passenger traffic):

| Trunk | Live rate | Utilization |
|-------|-----------|-------------|
| Per inter-coach trunk (active) | 100–155 Mbps total | ~1.5% of 10G |
| Stadler FW trunk (A3 e1-4) | ~15 Mbps total | ~1.5% of 1G |
| FW trunk asymmetry | TX ≈ 13× RX cumulative | Normal for routed traffic |
| PWLAN trunks (e0-4) | Near 0 if no clients | — |

If the FW trunk is sustained above ~700 Mbps, the 1G link is becoming a real bottleneck for Stadler-side throughput.

## Phase 6 — End-to-end CCU ↔ Stadler firewall

This phase answers **three separate questions** about the vlan7 connection to `172.19.X.1`. Don't conflate them — each has its own test and its own success criterion. Conflating them silently produces wrong customer-report classifications (audit finding F9, 2026-05-11).

### Q1 — Path health: does traffic flow to the FW peer?

```bash
ip neigh show dev vlan7 | grep 172.19.X.1   # should show REACHABLE with FW MAC (00:90:e8:... — Westermo OUI)
ip -s link show vlan7                       # errors and drops should be 0
```

| Result | Meaning |
|---|---|
| ARP `REACHABLE`, link counters clean | ✅ path OK — traffic flows to `.1` |
| ARP `FAILED` / no neighbour | 🔴 path broken — vlan7 misconfigured, vlan not trunked through, FW absent on subnet |

If Q1 fails, stop. Q2 and Q3 are meaningless without a working path. Investigate vlan7 IP (use `dosto-vlan7-config` skill), inter-coach trunks (use `lldp_topology_check.py`), or whether the Stadler FW box is even installed/powered.

### Q2 — FW commission state: has Stadler applied policy to the firewall?

This is **the deciding test for whether Stadler has commissioned the FW for this train.** It is NOT TCP. It IS ICMP.

```bash
ping -c 5 172.19.X.1
```

| Result | Meaning |
|---|---|
| 0 replies (100% loss) AND path OK from Q1 | ✅ FW **commissioned** — Stadler policy is dropping echo-request as designed |
| Replies received | 🟡 FW responding but **NOT commissioned** — bare/default Westermo behavior, no Stadler policy applied yet |
| 100% loss AND Q1 also failed | 🔴 path broken (Q1 issue, not commission state) |

**Important:** A configured Stadler FW deliberately drops ICMP. Reading "ping fails" as a fault is the long-standing trap. Reading "ping succeeds" as health is the *new* trap that F9 surfaced. The correct heuristic:

> **Ping works = FW exists but Stadler hasn't finished configuring it.**
> **Ping fails (with ARP REACHABLE) = FW is fully commissioned and applying policy.**

### Q3 — Service availability: are the FW-exposed services up?

```bash
nc -zv -w 5 172.19.X.1 80
nc -zv -w 5 172.19.X.1 22
# ...and any other Stadler-intended services for this train (camera VLAN gateways, etc.)
```

| Result | Meaning (depending on Q2 outcome) |
|---|---|
| OPEN, Q2 says "commissioned" | ✅ FW exposes 80/22 as intended (rare — typically Stadler filters these) |
| OPEN, Q2 says "uncommissioned" | 🟡 you're hitting the bare Westermo management interface, not a Stadler service |
| refused/filtered, Q2 says "commissioned" | ✅ FW applying policy as expected (80/22 not in the policy whitelist) |
| timeout, Q1 was OK | 🔴 specific service path broken — investigate FW config |

TCP probes alone **cannot** tell you whether the FW is commissioned. They tell you whether *something* responds on a given port. The Q2 ICMP test is the only authoritative commission-state test from the CCU side.

### Summary table — how to read all three together

| Q1 ARP | Q2 ICMP | Q3 TCP 80/22 | Verdict |
|---|---|---|---|
| REACHABLE | 0 replies | refused/filtered | ✅ **FW fully commissioned by Stadler** |
| REACHABLE | replies | OPEN | 🟡 **FW responding but not yet commissioned** (Stadler-side work pending) |
| REACHABLE | (any) | timeout | 🟢 path OK, specific TCP services down — investigate |
| FAILED | (any) | (any) | 🔴 **path broken** — fix vlan7 / trunks / FW presence first |

Until you've run Q1 + Q2, **do NOT write a verdict in `fleet-status.md`'s `FW reach` column.** TCP-OPEN alone is ambiguous between "commissioned with weird policy" and "not yet commissioned" — and historically the latter is more common during rollout.

**Fleet-wide note:** any train marked `FW reach: ✅` in `fleet-status.md` based on TCP-OPEN alone (without an ICMP test) may need re-verification. F9 in `handoff-bootstrap-audit-2026-05-11.md` lists this as a fleet-wide carryover task.

## Phase 7 — Aggregate L2 traffic on the fabric

For a "how busy is this train" snapshot, sample byte counters on every inter-coach trunk on every switch twice 30–60s apart. Sum per-port deltas and divide by interval.

Important: summing every inter-coach trunk **double-counts** traffic that traverses multiple cars. The headline number to report is *average per-active-trunk Mbps*, not the sum across all trunks. From the Fzg. 146 baseline: average active inter-coach trunk = ~140 Mbps total → ~1.5% utilization on a 10G link.

## Phase 8 — Recording the baseline

For every train you check:

1. Note the **Fzg. ID** (from the IPv4 schema PDF).
2. Save `show interface <port> details` output for every inter-coach trunk and every Stadler-facing trunk to a timestamped file.
3. Capture the STP root MAC and confirm it's stable (single root, all switches agree).
4. Note any anomalies (down links, non-zero error counters) — even small numbers, for trend tracking.
5. Save aggregate utilization samples (per-trunk Mbps) — useful for capacity-planning and for diff against future baselines.

A clean baseline lets you spot drift on the next visit. The Fzg. 146 baseline is captured in `.claude/sample1.txt` and `.claude/sample2.txt` (54s window) — use those as templates for output format.

## Common false alarms (don't be fooled)

| Observation | Likely cause | Verdict |
|-------------|--------------|---------|
| 100% ICMP loss to Stadler FW | FW drops ICMP echo-request by policy | Healthy if TCP probes succeed |
| `e0-1` link DOWN on a couple of switches | Those are end-of-train switches; e0-1 has no neighbour | Expected, not a fault |
| Front coupler trunks (e0-2 on A1/A3/B1/B3) DOWN | Train running solo, no second consist coupled | Expected |
| ZFR at B3 has RX = 0 packets | B1 is primary ZFR (active), B3 is standby (silent) | Expected — they share one IP |
| RDC trunk (e0-3) RX near 0 | RDC powered off / idle | Likely fine; flag if RDC service is supposed to be active |
| Single-digit RX errors over millions of packets | Noise — single corrupted frame on connect, EMI transient | Not actionable |
| Switch firmware shows version differences across the fleet | Possible — note for fleet management, but not a fault per se | Document, don't escalate unless mismatch is large |
| `show system` returns no hostname | VDS switches don't expose hostname this way | Use config fingerprint to identify them |

## Real red flags

| Observation | Action |
|-------------|--------|
| Non-zero `RX crc errors` (any sustained count) | Replace cable or SFP at the link end-points; check connectors |
| Non-zero `carrier false` (any sustained count) | Physical-layer instability — cable / vibration / surge protection tripping |
| Non-zero `pause frames received` | Egress queue overflow on the upstream switch — trace the bottleneck |
| Multiple STP roots, or root flapping | RSTP topology unstable — find the link causing TCNs |
| Inter-coach trunk speed degraded (e.g. 1G when expected 10G) | Auto-negotiation problem — check both ends |
| Sustained inter-coach utilization > 70% | Capacity issue — investigate which devices are saturating the trunk |
| TCP probe to FW peer fails AND vlan7 has drops | FW path actually broken — escalate to Stadler |

## Pitfalls and quirks (learned the hard way)

- **Switch CLI rejects `;`-chaining** — run one command per SSH session. Loop in shell, don't chain.
- **Pseudo-terminal warning** — appears whenever you run `ssh ... <command>` from a script. Harmless, ignore.
- **`show system` doesn't include hostname** — switches identify themselves only by their config fingerprint (which trunks/access ports are configured), so use Phase 2 mapping instead.
- **PuTTYgen-converted keys must have NO passphrase** — non-interactive SSH from scripts can't prompt. Re-export with empty passphrase if needed.
- **Train cellular networks drop frequently** — long-running tasks (full-fleet sweeps) should be backgrounded; if SSH dies mid-sweep, just retry the missing switches.
- **`ping` is not a useful health probe past the FW** — switch to TCP probes.
- **`show interface trunks` only lists configured trunks** — a port can be admin-enabled but the link DOWN; use `show interface summary` to see actual link state.
- **The PWLAN trunk (e0-4) is usually idle** — if e0-4 shows zero traffic on every switch, the train is empty. Not a bug.
- **Two devices sharing one IP is expected for ZFR / Sprechstelle redundancy** (`Redundanz` in the schema). Only one is active at a time.
- **`train_id` must only be set inside the per-switch `.cfg` template files (`/etc/obn/template/nv6-*.cfg`)** — never in `backbone-discovery.yaml` or any other file. Those `.cfg` files are the single source of truth for the Fzg ID rendered into switch hostnames. Setting `train_id` elsewhere (e.g. `backbone-discovery.yaml`) moves the CCU to a different IP subnet on reboot without changing the switch configs, breaking connectivity.
- **Factory-config APs block OBN SNMP silently** — Westermo RT610LV APs shipped in factory config (`RT610LV-...-v1-FD`) use SNMP community `admin-community`, not `NomadStayOut!`. OBN prints "configuration update applied, device rebooting" regardless — it does not check the return value before printing. ICMP to the AP will work fine; only SNMP is silently dropped. Use the LuCI HTTP import method (see `troubleshooting-runbook.md` → "Westermo AP Config Push") to push the Nomad config when OBN SNMP fails. LuCI admin password on factory APs is `Nom@dCome1n`. After config apply, SSH CLI uses `nomad`/`NomadComeIn`.
- **OBN canonical workflow is `discover → report → update/validate` — never skip `obn report`.** `obn update c` and `obn validate` both read from `discovery.prev.json` (the report snapshot), not `discovery.json` (raw scan output). This is by design — `obn report` commits the discovery scan into the stable snapshot that all subsequent OBN operations use. If you skip it: (a) `obn update c <ip>` finds an empty or stale device list → Python `all([]) = True` on an empty set → prints "Update not supported for readonly devices"; (b) `obn validate` shows an empty table. Always run `sudo obn discover && sudo obn report` before any `obn update` or `obn validate`. Confirmed 2026-05-12 on box1-t47 (Fzg 130).
- **`obn validate` returns an empty table when `consist.yaml` is empty or `obn report` hasn't been run** — not a fault, just means the report snapshot is empty. Run `sudo obn discover && sudo obn report` first. If you need a quick ad-hoc view of device state without waiting for report, read `/tmp/discovery.json` directly: `sudo python3 -c "import json; [print(d['ip'], d.get('firmware'), d.get('config')) for d in json.load(open('/tmp/discovery.json'))['devices']]"`.
- **A near-empty `obn validate`/`obn report` switch table on a consist you KNOW is larger = suspect a bypassed switch, NOT a small consist.** When a VDS switch is cold-bypassed (powered off, backbone relayed through it), OBN's coach-numbering walk mis-numbers the switch that moves into the gap, dead-ends, and `normalise_devices()` **silently deletes every switch it couldn't number** — including healthy, SNMP-reachable ones downstream of the gap. So OBN can report 2 switches when 10 are up and running (observed on bench box1-t122, 2026-07-04). This is a monitoring false-negative: the dropped switches aren't in the NMS report either, so nothing can alarm on them. **Always cross-check OBN's switch count against `dosto-device-discovery`'s discovered count (from `dhcp-lease-list`) — if discovery sees more switches than OBN's report shows, a bypass/mislabel is eating the difference.** `dosto-device-discovery` Step 4b classifies the bypassed switch (cold_bypass / dead_link / miscable) via reciprocal-LLDP. Root cause + validated engine fix (topology-anchored numbering + DOWN/UNPLACED rows, prototyped on the bench): `findings/RD_obn_coach_numbering_bypass_downstate_2026-07-04.md`.
- **VDS switch CLI reboot command is NOT `reboot`, `reload`, or `system reboot`** — all rejected with "Error in command, param is X [wrong]". The correct reboot command is not yet confirmed from field testing. Check `.claude/switch_manual.txt` (full CLI reference) or ask Stadler. OBN's `vdsrail.py reboot()` uses SNMP reboot OID (value `3`) — the only confirmed reboot path from the CCU side. Confirmed 2026-05-12 on Fzg 130.
- **`dosto-l2-health` script `08_e2e_probe.sh` has a hardcoded default FW IP `172.19.196.1`.** For any train where the vlan7 FW is not at that address, the script produces a false `path_broken`. Always pass the FW IP explicitly: `bash 08_e2e_probe.sh <ccu-ip> <fw-ip>`. Correct FW IP per train = `172.19.<128+Fzg//2>.1`. Confirmed 2026-05-12 on Fzg 130 (FW = `172.19.193.1`).

## Quick "is this train healthy" recipe

If someone asks "is the network on Fzg. NNN healthy?" and you have ~10 minutes:

1. Read the `ND-DEL-OBB-035-IPA-NNN_NV_*.pdf` schema. Confirm car count and identify A3/B1/B3/D1/D3.
2. SSH into the CCU. `fping` the management VLAN. Confirm expected number of VDS switches.
3. Run `show interface summary` on every switch. Confirm trunk speeds match schema and no unexpected DOWN links.
4. Run `show spanning-tree` on every switch. Confirm one stable root MAC across the fleet.
5. Run `show interface <port> details` on every inter-coach trunk + the Stadler-facing trunks (A3 e1-4, D1/D3 e0-2/e0-3, B1/B3 e1-11). Confirm 0 errors / 0 CRC / 0 carrier-false.
6. Probe the Stadler firewall on vlan7 using all three Phase 6 tests: ARP REACHABLE (Q1), `ping -c 5` ICMP result (Q2 — loss = commissioned, replies = not yet commissioned), TCP probe port 80 (Q3). See Phase 6 above for the correct interpretation of each result. Do NOT use TCP alone to determine FW commission state.
7. Sample inter-coach byte counters twice 30s apart. Confirm utilization sane (typically <5% of link capacity at idle).

If all seven steps come back clean, the L2 fabric is healthy. Reported user-perceived packet loss is then almost certainly NOT in this fabric — investigate end-host (NIC/driver/OS — see `iperf3-troubleshooting.md` for the Windows UDP pacing artefact pattern), Stadler-side beyond the FW (no CCU visibility), or PWLAN/cellular (separate scopes).

## Folder layout

The project is organised into the following subfolders. Anything not listed here lives at the root.

### Root

- `CLAUDE.md` — this file (the playbook / methodology).
- `.kb/` — **OKF knowledge base**: component knowledge (switch/AP/CCU-OBN), cross-cutting topics, 51 per-train identity records, tickets, deliverables, per-train asset indexes. Every component/topic doc has a `# Proven dead ends` section. Read [`.kb/index.md`](.kb/index.md); maintain per [`.kb/MAINTENANCE.md`](.kb/MAINTENANCE.md). Additive-only — links to `fleet-status.md`, never edits it.
- `fleet-status.md` — **per-train v8 rollout status. Read first, update last.** Status row per Fzg with `Next action` so any engineer can pick up mid-rollout.
- `train-login-checklist.md` — **canonical 11-step procedure** for any train session. Step 11 is "update fleet-status.md".
- `troubleshooting-runbook.md` — operational runbook (LLDP cabling check, OBN bug fixes, AP manual config push, etc.).
- `cable-issues-register.md` — fleet-wide register of physical cabling faults found during health checks.
- `iperf3-troubleshooting.md` — prior investigation documenting 5% UDP loss → TCP collapse via Mathis formula. Read before iperf3-ing.
- `openssh` / `pvt_key.ppk` — SSH credentials for CCU. Referenced by absolute path from the runbook and from scripts — do not move.
- `package.json` / `package-lock.json` / `node_modules/` — dependencies for the report-generation JS scripts under `scripts/`.
- `train-ip-allocation-commission/` — IP allocations and commissioning docs for all trains. Structure: `4734-xxx/4734-NNN/` and `4736-xxx/4736-NNN/` (101–120 each), plus `4705-xxx/`, `4706-xxx/`, `Bench/`, and template folders. Each per-train subfolder contains the IP-Allocation PDF, Phase2a/2b PDFs, and commissioning templates. Check here first when you need the management IP or commissioning docs for any device on any consist.

### `docs/` — reference material

- `ND-DEL-OBB-035-IPA-NNN_NV_6Teiler.pdf` — IPv4 schema for Fzg. NNN (one per train).
- `switch_user_manual.pdf` — VDS Consist Switch User Manual v2.0.4. Full-text extract cached at `.claude/switch_manual.txt`.
- `Westermo-Management-Guide-6.9.5.pdf` — Westermo AP management reference.
- `ND-DEL-OBB-035-CFG-001-01 OBB Fleet Control Sheet 20260211.xlsx` — fleet control sheet.
- `docs/reference/` — supplementary hardware/feature manuals not tied to a single train: `R5001C Rack Chassis, CMM I2C Manual_V2.5.pdf` (CCU CMM ignition/power readout), `Explainer, Ignition controlled power management_Issue1.0.pdf`.

### `scripts/` — all scripts

- `fix_obn.py` — idempotent patcher applying all known OBN bugs (1–7). Run on every CCU at the start of an OBN session. Copied to CCU `/tmp/` via scp.
- `fix_obn_templates.sh` — template fixups for OBN config templates.
- `lldp_topology_check.py` — pexpect-based script that SSHes into all VDS switches on vlan100, runs `show lldp neighbours`, and compares e0-0/e0-1 trunk peers against the expected OBN topology. Run this when OBN or auto-topology fails — wrong LLDP peers on trunk ports = cabling error by Stadler. Edit `SWITCHES` and `EXPECTED_TOPOLOGY` at the top for each train.
- `lldp_topology_check_t8.py`, `lldp_check_4734-119.py` — train-specific variants of the above.
- `check_cabling.py`, `build_cable_tracker.py` — cabling validation and tracker generation.
- `gen_report_108.py`, `generate_health_check_report.js`, `generate_report.js`, `generate_report_109.js` — report generators.
- `push_ap_config.sh` / `push_all_aps.sh` / `push_remaining_aps.sh` / `apply_ap_configs.sh` — pushing Nomad config to factory-default APs via LuCI HTTP when OBN SNMP fails.
- `zbx_reconcile.py` — fleet Zabbix interface-IP reconciler (DHCP drift). Joins live DHCP lease → Zabbix host by **MAC**. Explicit per-train enrolment; dry-run default, `--commit` to write. Fine for real trains (rare hardware swaps).
- `zbx_reconcile_bench_4122.py` — **bench** Zabbix IP reconciler, **POSITION-keyed** (swap-safe: joins lease-hostname `4t-A3` → Zabbix `R1_SW3`, not MAC — bench switches get replaced). Switches only; skips no-lease positions (bypassed/absent). Dry-run default, `--commit` + then restart the CCU's `zabbix-proxy`. See memory `bench-4122-nms-two-layer-fix`.
- `dbc12` — utility script.

### `findings/` — raw L2 health-check JSON output

- `findings_<train-or-ccu>_<date>.json` — output of the dosto-l2-health skill, one per run. Consumed by the dosto-l2-report skill.

### `reports/` — deliverables

- `reports/customer/` — latest customer-facing reports (`OBB_Fzg*_Network_Health_Check_Report_v1.x.docx/.pdf`, `Stadler_*_Cabling_Fault_Report*.docx`).
- `reports/internal/` — internal working notes (`105-update-report-*`, `105-l2-health-report-*` for Fzg 133 / 4736-105).
- `reports/_archive/` — superseded versions of customer reports (kept for reference, do not touch).

### `trackers/` — fleet trackers

- `cable-issues-tracker.xlsx` — spreadsheet companion to `cable-issues-register.md`.
- `topology_4736-106.svg` — generated topology diagrams.

### Bootstrapping a fresh workspace

If you need to recreate this workspace on a fresh machine without cloning git, paste [`BOOTSTRAP_DOSTO_v1.md`](BOOTSTRAP_DOSTO_v1.md) into a fresh Claude Code session in an empty directory. It contains every contract, agent definition, skill, and the OBN fix scripts inline — Claude reads each STEP block and recreates the file with the exact content. Once scaffolded, drop in your `openssh` SSH key and the schema PDFs separately (those are credentials/binaries, never embedded).

The bootstrap is **regenerated** from the live tree by `scripts/regenerate_bootstrap.py`. Run it after any material change to a contract, agent definition, or skill so the bootstrap stays canonical:

```bash
python scripts/regenerate_bootstrap.py            # scaffold only (~8k lines, ~127k tokens)
python scripts/regenerate_bootstrap.py --include-state   # + fleet-status, handoff, runbooks (~10k lines, ~156k tokens)
python scripts/regenerate_bootstrap.py --check    # dry run, just report sizes
```

The regenerator embeds: 4 contracts + 2 agent definitions + 14 SKILL.mds + CLAUDE.md + 5 fix scripts + the regenerator script itself (self-replicating). It does NOT embed: the SSH key, schema PDFs, IP-Port-Allocation PDFs, customer reports, log files, node_modules. Those are engineer-supplied or generated.

### `.archive/` — retired scratch (not load-bearing)

Holding ground for files that are no longer referenced by any skill, script, or contract but are kept for history rather than deleted. Nothing here is read at runtime; safe to ignore during a normal session.

- `.archive/sdd-edit-scratch/` — one-off PowerShell + `.txt` extracts from a 2026-05 SDD-docx editing session (`mar3`/`mar5`/`section510`/`internetzugang` helpers).
- `.archive/old-handoffs/` — superseded planning/handoff notes (`monday-plan.md`, `clone-disk*.md`) and a retired one-off script (`l2_error_scan_fzg12.py`).
- `.archive/enhancement-notes-*.md` — applied enhancement notes kept for provenance.

### `.claude/` — Claude harness state

- `.claude/sample1.txt`, `.claude/sample2.txt` — Fzg. 146 byte-counter snapshots (54s window). Reference output format.
- `.claude/switch_manual.txt` — full-text extract of `docs/switch_user_manual.pdf` for grep.
- `.claude/contracts/` — 4 design contracts (`subagent-report.md`, `autonomy-boundary.md`, `approval-gates.md`, `confluence-sync.md`).
- `.claude/agents/dosto-train-worker.md` — per-train commissioning subagent definition (Sonnet 4.6, JSON-only output).
- `.claude/skills/` — 14 project-local skills:
  - **Diagnostic / read-only:** `dosto-device-discovery`, `dosto-extract-train-data`, `dosto-l2-health`, `dosto-fzg-id-check`, `dosto-vlan7-config`, `dosto-tftp-helper-check`.
  - **Per-device push (single-AP/SW serial):** `dosto-ap-config-update`, `dosto-ap-firmware-update`, `dosto-sw-config-update`, `dosto-sw-firmware-update`.
  - **Per-device push (parallel batched):** `dosto-sw-config-update-batch` — default switch-config path in `dosto-commission-train`; legacy single-switch-serial path is preserved as escape hatch via `--legacy-serial-sw-config`.
  - **CCU-side persistence:** `dosto-obn-patches` (with `--persist` fold-in for vlan7 + fzg-id fixes).
  - **Orchestration / output:** `dosto-commission-train` (19-stage per-train pipeline), `dosto-l2-report` (customer docx), `dosto-confluence-sync` (push `fleet-status.md` to team Confluence page).
- `.claude/logs/` — append-only orchestration logs:
  - `confluence-sync.jsonl` — one JSON line per successful Confluence push (used by drift detection).
  - `confluence-drift.jsonl` — one JSON line per detected drift event (manual edit on Confluence between pushes).
