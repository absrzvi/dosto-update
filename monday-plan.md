# Monday Fleet-Day Plan

**Date:** _fill in Monday morning_
**Engineer:** Abbas Rizvi

## Trains for the day

Fill this in Sunday night / Monday morning before invoking the orchestrator. Each row needs Fzg ID + CCU IP. The skill will reconcile against [fleet-status.md](fleet-status.md) and prompt if anything mismatches.

| Fzg | Train# | CCU IP | Notes / current state |
|---:|---|---|---|
| | | | |
| | | | |
| | | | |
| | | | |
| | | | |

## Phase 0 — Prep (~5 min, before kicking off)

- [ ] Confirm each train above has a usable CCU IP (you typed it right, the train is online)
- [ ] Sanity-check fleet-status.md row exists for each train (the skill will catch missing rows but it's faster to know upfront)
- [ ] Smoke test SSH: `ssh -i openssh developer@<one-CCU-IP>` to one of the CCUs
- [ ] Decide concurrency — sweet spot is 4-5; >8 risks cellular SSH-flap

## Phase 1 — Bootstrap

```
/dosto-orchestrate fzg=NN@<ip>,NN@<ip>,NN@<ip>,NN@<ip>,NN@<ip>
```

Optional flags: `dry-run` (read-only first pass), `cycle=10` (slower digest), `engineer=Abbas Rizvi`.

The skill will:
1. Parse + validate every `@<ip>` pair (IPv4 syntax, no duplicates)
2. Reconcile each Fzg/IP against [fleet-status.md](fleet-status.md):
   - **Case A** — match → silent proceed
   - **Case B** — mismatch → `[f/s/a]` prompt (use fleet IP / use yours + update file / abort)
   - **Case C** — `❓` in row → auto-fill silently
   - **Case D** — no row → `[c/a]` prompt (create row / abort)
3. Print plan summary with `IP source:` line per train
4. Ask `Confirm? [Y/n]:` — type Y to spawn

For any train with `Status: DONE`, you'll get a per-train `[s/i/a]` skip/include/abort prompt — usually skip.

## Phase 2 — Approval gates (during the day)

The orchestrator runs autonomously except for **5 approval gates**, surfaced one at a time:

| Gate | Type | Default if in doubt | What you're approving |
|---|---|---|---|
| `promote_snapshot` | binary | `n` until you read rationale | Promotes new btrfs snapshot. **Irreversible without physical access.** |
| `safe_reboot` | binary | `y` if train OK to be offline 3 min | CCU reboot. Passenger-facing call. |
| `obn_update_c` | binary | `y` once 8/8 patches + train_id + vlan7 confirmed | Pushes config to up to 18 switches. |
| `obn_update_f` | binary | `y` if firmware push is intentional | Same blast radius as `obn_update_c` but firmware. |
| `device_count_mismatch` | three-way | **`p` (partial)** | `w`ait for Stadler / `p`artial CCU-local fixes / `c`ontinue full. |

**Response shortcuts:**

```
Binary gates:    y / n / defer
Three-way gate:  w / p / c / defer
```

Pressing **Enter alone** = deny on binary, `partial` on three-way. **Defaults are safe by design.** Read the rationale every time — the 30s/gate friction is the safety feature.

## Phase 2.5 — Other in-session commands

| Command | Effect |
|---|---|
| `status` | Per-train summary on demand |
| `abort` | Stop the day cleanly |
| `defer` (at any gate) | Re-prompt at next 5-min cycle |

## Phase 3 — End of day (~5 min)

- [ ] All subagents reached terminal state (`DONE` / `BLOCKED` / `ERROR`)
- [ ] Type `abort` (or close session) — orchestrator flushes final fleet-status writes + Confluence push
- [ ] Hand-edit [fleet-status.md](fleet-status.md) for columns the orchestrator doesn't own:
  - `Customer report` (when docx delivered)
  - `Health check date`
  - `Stadler cabling` notes / open faults
- [ ] Sanity-check Confluence page 5410684933 — confirm last cycle landed
- [ ] Quick log audit (optional):
  ```
  tail .claude/logs/approval-gates.jsonl
  tail .claude/logs/confluence-sync.jsonl
  ```
- [ ] Update [handoff.md](handoff.md) with anything notable for next session

## If something goes wrong

| Situation | Action |
|---|---|
| Orchestrator crashes mid-day | Re-invoke `/dosto-orchestrate` with same train list — new orchestrator offers `--resume` per train. State on CCUs (btrfs), not in session. |
| Wrong-train gate approval by accident | Subagent → BLOCKED. Re-spawn alone via `/dosto-commission-train --ccu-ip <ip> --fzg <NN> --resume <stage>` after orchestrator session ends. |
| Cellular dropped on one CCU | That subagent marks BLOCKED with "CCU unreachable". Others unaffected. Resume that one when cellular returns. |
| Confluence push drift | Orchestrator halts Confluence pushes (not workflow), surfaces drift. Fix manually, type `resume confluence`. |

## Reference

- Full workflow: see chat history (Phase 0 → Phase 4 walkthrough)
- Skill source: [.claude/skills/dosto-orchestrate/SKILL.md](.claude/skills/dosto-orchestrate/SKILL.md)
- Approval gates protocol: [.claude/contracts/approval-gates.md](.claude/contracts/approval-gates.md)
- Autonomy boundary: [.claude/contracts/autonomy-boundary.md](.claude/contracts/autonomy-boundary.md)
- Open priorities from handoff: skill-audit Tier 1 + 2 ✅ done, resume Fzg 132 (push .237 .238 .240), validate auto-scanner Tier-1 against real online train.
