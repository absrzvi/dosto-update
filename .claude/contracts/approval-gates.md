# Approval Gate Protocol

**Status:** v2, updated 2026-05-11 per audit finding F8-L1 (engineer-UX / cognitive-load fix).

**v2 changes from v1:**
- New "Compact prompt template" (default format) — single screen, scannable in <5 seconds.
- Old verbose multi-line "What the orchestrator shows the human" section retained as the **expanded form**, shown only when the engineer types `?` after a compact prompt.
- No protocol/response-shape changes — v1 and v2 use identical SendMessage and approval semantics.

How a subagent's approval request reaches the human and the answer gets back. This is the wiring; the policy of *what* needs approval is in [autonomy-boundary.md](autonomy-boundary.md).

## Design constraints

1. **Approvals fire immediately when needed** — not batched, not tied to the 5-min progress cycle. A subagent waiting for chroot approval shouldn't sit idle for 4 minutes because of a cycle boundary.
2. **5-min progress digest is separate** — that's status reporting, not an interactive prompt. Reading a digest is one-way; approving a gate is two-way.
3. **The human is the only humanish interface** — no Slack, no email, no extra integrations. The human is at the laptop, sees the orchestrator's prompt, types yes/no.
4. **The orchestrator is the only entity that talks to the human** — subagents emit JSON, orchestrator translates that JSON into a human-readable approval prompt and types the response back to the subagent.

## Sequence diagram

```
SUBAGENT                     ORCHESTRATOR                          HUMAN
   │                              │                                   │
   │  emit JSON report:           │                                   │
   │  status=NEEDS_APPROVAL       │                                   │
   │  approval_needed={...}       │                                   │
   │─────────TaskOutput──────────▶│                                   │
   │                              │  format approval prompt           │
   │                              │  (rationale + command_preview)    │
   │                              │──────────print to terminal───────▶│
   │                              │                                   │
   │                              │                                   │
   │                              │   ◀──────────"y" or "n"───────────│
   │                              │                                   │
   │                              │  encode response                  │
   │  ◀──SendMessage("approve")───│                                   │
   │                              │                                   │
   │  proceed with gate command   │                                   │
   │  emit next JSON report       │                                   │
   │─────────TaskOutput──────────▶│                                   │
```

## What the orchestrator shows the human

### Compact prompt template (default — v2)

This is what the orchestrator emits by default. One header line, three meta cells, one rationale sentence, command preview as a one-liner, options line. Scannable in <5 seconds:

```
[Gate 1] promote_snapshot — Fzg 132 — 8/8 OBN patches confirmed; persisting via chroot promote
  destructive: ✅   reversible: ❌   command: sudo /usr/sbin/nd-systemupdate.sh shell + fix_obn.py + exit
Options: y | n | defer | ?
```

Sizing rules (contract terms — orchestrator MUST enforce):
- Header line ≤ 100 chars: `[Gate N] <gate-name> — Fzg <NN> — <one-sentence rationale>`. Rationale truncates with `…` if over.
- Meta cells line: literally `destructive: <✅|❌>   reversible: <✅|❌>   command: <one-line preview>`.
  - Command preview ≤ 80 chars. Multi-step recipes summarise with `+` joiners. Full recipe lives behind `?` (expand).
- Options line: exactly the response tokens (no prose), separated by `|`. Last option is always `?` (expand).

Default response is **`n` (deny)** for binary gates; `partial` for the three-way Gate 5 (matches v1 semantics).

### Expanded form (`?` triggers this from the compact prompt)

If the engineer types `?` after a compact prompt, the orchestrator emits the v1 verbose form for that gate. The verbose form lets the engineer read full rationale + full command preview before deciding:

```
─── APPROVAL NEEDED (expanded) ──────────────────────
Train:        Fzg 132 / 4736-104 (10.179.10.1)
Gate:         promote_snapshot
Reversible:   ❌ No (changes default GRUB target)
Destructive:  ✅ Yes

Rationale:
  All 8 OBN patches applied outside chroot, verified
  8/8 markers present. Need to re-apply inside
  nd-systemupdate.sh shell so they survive reboot.

Will execute:
  sudo /usr/sbin/nd-systemupdate.sh shell
  # inside chroot: sudo python3 /tmp/fix_obn.py
  # inside chroot: sudo python3 /tmp/fix_obn_bug8.py
  # inside chroot: exit
  # promotes work → release → run<N>

Approve? [y/N]:
```

Engineer's response after `?` is interpreted with v1 semantics (same options, same defaults). The expansion is **per-prompt** — the next gate fires its own compact prompt again, NOT pre-expanded.

### When to skip the compact form

If `approval_needed.rationale` exceeds 200 chars OR `command_preview` has more than 5 meaningful steps, the orchestrator MAY emit the expanded form directly — but should still offer a one-line summary at the top. This is an escape hatch for genuinely complex gates (rare).

The compact form is the default. The expanded form is the exception. v1 had it backwards — surfacing verbose by default created the engineer-UX cognitive-load problem (F8) that this v2 update addresses.

## What the human types — depends on `response_shape`

### Binary gates (`promote_snapshot`, `safe_reboot`, `obn_update_c`, `obn_update_f`)

| Input | Meaning |
|---|---|
| `y` or `yes` | Approve. Subagent proceeds. |
| `n` or `no` or *(empty)* | Deny. Subagent marks `BLOCKED` and stops working this gate. Reports back to orchestrator with rationale "human denied". |
| `defer` | Defer for later. Subagent stays in `NEEDS_APPROVAL`, will re-prompt at the next 5-min cycle. Useful when you want to think but not block the gate permanently. |
| `?` | Expand — orchestrator re-emits this same gate in the verbose form. Engineer's next input goes against the same gate with v1 semantics. |

Anything else (typo, multi-word) is treated as deny with a warning.

### Three-way gate (`device_count_mismatch` only)

| Input | Meaning |
|---|---|
| `w` or `wait` | Set `status = BLOCKED`. Stop subagent. Wait for Stadler. Human must re-spawn subagent after fix. |
| `p` or `partial` or *(empty — default)* | Proceed with CCU-local fixes only (OBN patches, train_id template, vlan7). Stop before any consist-wide push or health check. Re-run discovery on next cycle. |
| `c` or `continue_full` | Proceed through all remaining stages including consist-wide pushes. Missing devices will be in unsynchronised state when they eventually come online. |
| `defer` | Defer for later. Subagent stays in `NEEDS_APPROVAL`, re-prompts at next 5-min cycle. |
| `?` | Expand — orchestrator re-emits the gate in verbose form including per-device `missing_devices[]` detail with stadler_instructions. Engineer's next input proceeds with v1 semantics. |

Note that the three-way default is `partial` (the safest middle path), not deny — different from binary gates where empty input means deny.

**Compact prompt for Gate 5** (the three-way) looks like:

```
[Gate 5] device_count_mismatch — Fzg 130 — 4 switches missing: D2, E2, E3, F2
  destructive: ❌   reversible: ✅   action depends on response
Options: w (wait Stadler) | p (partial — CCU-local only) | c (continue full) | defer | ?
```

`?` expands to show per-missing-device Stadler instructions (cable register entries, expected port mappings, etc.).

## What the subagent gets back

Single-line response from orchestrator via `SendMessage`. Shape depends on the gate type:

### Binary gates

```
{"approval": "approved" | "denied" | "deferred", "approved_by": "human-cli", "approved_at": "2026-05-09T06:55:30Z"}
```

Anything malformed = treat as `denied`.

### Three-way gate (`device_count_mismatch`)

```
{"approval": "wait" | "partial" | "continue_full" | "deferred", "approved_by": "human-cli", "approved_at": "2026-05-09T06:55:30Z"}
```

Anything malformed = treat as `partial` (the safest middle option, not deny).

## Concurrent approval requests

If two subagents hit gates at roughly the same time, the orchestrator queues them and shows them sequentially:

```
─── APPROVAL NEEDED (1 of 2) ────────────────────
Train: Fzg 132 / 4736-104 — promote_snapshot
... (same format)
Approve? [y/N]:

─── APPROVAL NEEDED (2 of 2) ────────────────────
Train: Fzg 130 / 4736-102 — safe_reboot
... (same format)
Approve? [y/N]:
```

The human handles them one at a time. While one is being decided, the other subagent waits.

**Why sequential and not batched:** the human reads each rationale and command_preview separately. A batch prompt with "approve all 5" is exactly the pattern that leads to rubber-stamping.

## Timeout behavior

If the human doesn't respond within **30 minutes**, the orchestrator:

1. Treats the request as `deferred`
2. Subagent stays in `NEEDS_APPROVAL`, doesn't time out
3. Orchestrator keeps showing the request in the next 5-min digest
4. Other subagents (not waiting for approval) keep working

No subagent is ever auto-approved or auto-denied by inactivity. Human silence is silence — work waits.

## Logging

Every approval gate is logged to `.claude/logs/approval-gates.jsonl` (append-only):

```json
{"timestamp": "2026-05-09T06:55:30Z", "train": "4736-104", "gate": "promote_snapshot", "decision": "approved", "command_preview_hash": "sha256:...", "subagent_session_id": "...", "rationale": "..."}
```

Useful for:
- Audit trail (who approved what)
- Postmortem when a fleet operation goes wrong
- Skill-improvement (which gates get denied most often, why?)

## Rationale for not auto-approving anything

Even on a "trivial" gate (e.g. safe_reboot on a CCU with confirmed-good snapshot), human approval is mandatory. Reasons:

- Trains may be carrying passengers — "OK to be offline" is genuinely a human judgment
- Approval cost is ~10 seconds; safety value is high
- Once auto-approval is acceptable for one gate, it tends to creep to others

The 30-second-per-gate friction is the feature, not a bug.
