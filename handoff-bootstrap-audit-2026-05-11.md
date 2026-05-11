# Bootstrap Audit — 2026-05-11 — First-run findings on the orchestrator stack

**Type:** one-shot handoff artifact (not regenerated into bootstrap)
**Author:** AR
**Run:** first end-to-end test of orchestrator → train-worker → commission-train stack on real CCUs
**Trains touched:** Fzg 130 (4736-102, 10.179.47.1, 6-car) recovery run; Fzg 20 (4734-120, 10.179.49.1, 4-car) partial probe; Fzg 131 (4736-103) train-offline, skipped
**Goal of the run:** find loopholes in the bootstrap-defined process. NOT to update trains.

---

## How to read this file

Each finding `Fn` has the same five fields:

1. **Reproducer** — exact event/command that triggered it. Verbatim where possible.
2. **Impact** — what the orchestration stack does wrong as a result. Severity classification.
3. **Proposed fix** — concrete change. Should be implementable from this description alone.
4. **Target** — which file(s) in the bootstrap need to change. Bootstrap-relevant ✅ or downstream-only 🟢.
5. **Status** — `OPEN` / `FIXED` / `WONTFIX` / `NEEDS-DESIGN`.

Severity legend:
- 🔴 **Critical** — blocks the architecture as documented; multi-train runs can't work without this fixed.
- 🟡 **High** — workable around but bleeds tokens / engineer attention / correctness signal.
- 🟢 **Medium/Low** — quality-of-life or edge case.

---

## F1 — Harness denies subagent Bash on specific patterns (SCP, heredoc, reboot trigger)

**Reproducer.**
Three distinct denials observed on `train-fzg-130` worker during one run:

1. SCP from subagent:
   ```
   scp -i .../openssh .../scripts/fix_obn.py developer@10.179.47.1:/var/tmp/
   → denied
   ```
   (Worker tried to stage fix scripts during `apply_obn_patches`.)

2. Python heredoc piped over SSH:
   ```
   ssh developer@10.179.47.1 'python3 - <<PYEOF
   ... idempotent re-run of fix_obn.py ...
   PYEOF'
   → denied
   ```
   (Worker tried to verify 8/8 markers via Python re-run.)

3. Reboot trigger:
   ```
   ssh -o ConnectTimeout=10 developer@10.179.47.1 'sudo /usr/local/sbin/safe_reboot'
   → denied
   ```
   (Worker tried to execute the Gate-2 approved reboot.)

Plain `ssh ... 'sudo grep -c "..." /path'` one-liners worked fine. The denial appears tied to specific *command shapes*, not to SSH-to-the-CCU as a general capability.

**Impact.** 🔴 **Critical.**
- The `dosto-commission-train` pipeline requires SCP (script staging), interactive-like heredocs (chroot recipe), and reboot triggers. Workers cannot drive the pipeline end-to-end as the contracts assume.
- Every denial requires a parent-side workaround. We did three in one run on one train. At scale (2+ trains in parallel), the parent becomes the bottleneck — defeating the architecture's parallelization premise (Principle 5).
- Worse: each denial caused a worker turn to exit with an `ERROR` status JSON, requiring a fresh `SendMessage` from parent to resume. Each resume costs tokens (see F2).

**Proposed fix.** Three layers, pick at least one:

- **Layer A (harness):** Update `.claude/settings.json` allowlist to grant SCP/heredoc/reboot patterns for subagents. Requires confirming whether the allowlist *applies to subagents* (this run suggests it does not, but it's worth testing with `/update-config`). See F1a sub-finding below.
- **Layer B (skills):** Rewrite per-device skills to avoid the denied patterns. E.g. `dosto-obn-patches --apply` could ship its recipe as plain `ssh ... 'sudo python3 /path/to/staged/script.py'` one-liners, with a *prior* "ensure scripts staged" step the engineer (or parent) runs once per CCU.
- **Layer C (contract):** Make the `dosto-train-worker.md` contract explicit that the worker is expected to *report and hand off* on Bash-denial rather than try alternates. Today's worker prompt added this instruction mid-run; folding it into the agent definition itself prevents the worker from spending tokens on multi-retry-then-give-up.

**Target.**
- ✅ `.claude/agents/dosto-train-worker.md` (Layer C — new "Operating discipline / Bash-denial handoff" section) — **FIXED 2026-05-11**
- ✅ `.claude/skills/dosto-obn-patches/SKILL.md` (Layer B — `--apply` recipe now flags subagent SCP gap + documents parent-handoff pattern with concrete recipe) — **FIXED 2026-05-11**
- ✅ `.claude/skills/dosto-commission-train/SKILL.md` (Layer B — Stage 3 documentation now explicitly describes the subagent SCP handoff to parent, with five-step protocol referencing F1-C) — **FIXED 2026-05-11**
- 🟢 `settings.json` (Layer A — workspace-local, NOT in bootstrap)
- 🟢 `dosto-obn-patches` CLI `--skip-step1` flag (lightweight CLI addition to support clean parent-handoff resume) — OPEN as a small follow-up

**Status.** **Layers B + C FIXED at the skill + worker layer** 2026-05-11 AR. The pattern is documented end-to-end: subagent detects denial → ERROR JSON with handoff message → parent SCPs from its session → SendMessage back → subagent resumes at STEP 2. Tested on Fzg 130 during the first-run test, worked correctly. Layer A (settings.json allowlist) remains workspace-local engineer-owned; `--skip-step1` CLI flag is a clean follow-up that would smooth the resume but isn't blocking.

### F1a — Sub-finding: parent vs subagent Bash permissions appear to differ

The parent session has had no Bash denials in this run for the *same SSH command patterns* that workers were denied on. This suggests the harness applies a tighter permission model to spawned subagents than to the top-level session. Worth documenting clearly in `dosto-train-worker.md` ("you may hit Bash denials the parent didn't — handoff, don't retry") so workers don't waste cycles assuming parity.

---

## F2 — Subagent context bloat — single worker reached 166k tokens on Stage 1

**Reproducer.**
After `train-fzg-130` emitted its Stage 1 + Gate 5 NEEDS_APPROVAL JSON, its usage was reported as `166k tokens / 17 tool uses / 17s` for that single turn. Subsequent turns dropped to 35k-40k after we told it "be concise — no historical `skill_outputs`."

**Causes (inferred):**
1. Spawn prompt was ~3000 tokens — inlined the full Fzg 130 per-train detail block from fleet-status, do-not-do rules, recovery sequence, etc. All useful context but it persists for the worker's life.
2. Worker re-read 4 contracts + agent def + fleet-status + `dosto-commission-train` SKILL + each invoked sub-skill SKILL every stage transition. Estimated 30-40k tokens of static context.
3. The Stage 1 + Gate 5 JSON the worker emitted contained full `skill_outputs[].raw` for all 6 sub-skills. That's 4-8k tokens per sub-skill × 6 = 24-48k of report content the worker also has to re-load to maintain context across turns.
4. No turn compaction — full conversation history every turn.

**Impact.** 🟡 **High.**
- A worker on Sonnet 4.6 has a 200k window. Hitting 166k on Stage 1 leaves <34k for Stages 3–19. The worker will run out of context mid-pipeline on any non-trivial recovery.
- The cost is real: each `SendMessage` to a high-context worker triggers a full-context resume. We saw a 108k-token turn produce *zero* tool uses (it just acknowledged and ended) — that's pure waste.

**Proposed fix.** Three structural changes, all bootstrap-relevant:

1. **`subagent-report.md` contract:** default `skill_outputs: []` after a stage transition. Workers explicitly do NOT echo prior stages' outputs. Parent (orchestrator) maintains the audit trail externally. Each report carries only the *current* stage's evidence.

2. **`dosto-train-worker.md` agent definition:** spawn prompts should be *pointers*, not *dumps*. The agent definition itself should say *"on spawn, read fleet-status.md row for your Fzg and the contracts at .claude/contracts/. The spawn prompt will give you Fzg ID, CCU IP, consist; everything else you read yourself."* This caps spawn-prompt size at ~500 tokens.

3. **`dosto-train-worker.md` agent definition:** add a section "**Compactness rules**":
   - Reports are append-only stage transitions, never accumulating.
   - On `SendMessage("status")`, reply with a one-line current-stage summary; do not re-load contracts or skills.
   - Do not include `skill_outputs[].raw` blocks bigger than 500 lines; truncate with a pointer to where the full output was logged on disk.

**Target.**
- ✅ `.claude/contracts/subagent-report.md` — **FIXED 2026-05-11** (bumped to v2; new "Compactness rules" section; tightened `skill_outputs` default + `raw` truncation rule; v1 reports still accepted with `schema_version_drift` flag)
- ✅ `.claude/agents/dosto-train-worker.md` — **FIXED 2026-05-11** (new "Operating discipline" section covering compactness, status-ping protocol, Bash-denial handoff; spawn-prompt convention codified; schema_version bumped to "2" in examples)
- 🟢 `.claude/skills/dosto-orchestrate/SKILL.md` (pointer spawn prompts) — must follow when F5 is decided (orchestrate skill may be rewritten anyway)

**Status.** **FIXED at the contract + worker layer** 2026-05-11 AR. Orchestrator-side adoption (whatever ends up driving spawns after F5) inherits the pointer convention automatically since it's now in the contract.

---

## F3 — In-chroot verification was unreliable — worker reported success against wrong context

**Reproducer.**
During Fzg 130 Gate 1 chroot recipe, the worker's verify-before-exit step ran:
```
grep 'train_id' /etc/obn/template/nv6-A1-v5.cfg
→ (empty output)
```
The worker reported in its Gate 2 JSON:
```
template_count_updated: 18 ✅
train_id_sample_note: nv6-A1-v5.cfg not found by that name — template naming differs; count=18 confirms all updated
```

But on this CCU the actual filenames are `nv6-100-A1.cfg`, `nv6-200-C1.cfg`, etc. — the `-v5` suffix doesn't exist. The worker silently fell back to file-count as confirmation. The actual `train_id` value across the templates was not directly verified by the worker — it was verified by the parent after-the-fact via read-only mount of run1.

When the parent then ran the same greps against the *live* filesystem (`/`, which was still on run2), it returned the OLD broken state:
```
vlan7 live:     172.19.215.130/17  ❌ unchanged
train_id live:  128 + train_id     ❌ unchanged
```

The worker's "vlan7_in_snapshot: 172.19.193.2/17 ✅" report was true *inside the chroot* (which mounted run1 at `/`) but ambiguous about which snapshot's state was being read.

**Impact.** 🟡 **High.**
- Engineer (you) could have approved Gate 2 (safe_reboot) based on the worker's report alone and rebooted into a snapshot that *might* have had a partial fix. We caught it because the parent ran a separate mount-RO check, but that should be the *contract*, not luck.
- The hardcoded sample filename (`nv6-A1-v5.cfg`) is a per-train assumption baked into a generic recipe.

**Proposed fix.**

1. **`dosto-obn-patches` SKILL.md `--persist` recipe:** verify-before-exit step must use globs, not hardcoded filenames:
   ```
   # WRONG (current):
   grep 'train_id' /etc/obn/template/nv6-A1-v5.cfg

   # RIGHT (proposed):
   echo "templates count: $(ls /etc/obn/template/nv6-*.cfg | wc -l)"
   echo "train_id unique values:"
   grep -h '^{%- set train_id' /etc/obn/template/nv6-*.cfg | sort -u
   grep '^address1=' /etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection
   ```
   With expected outputs printed inline so the worker (or engineer) can pattern-match success.

2. **`dosto-obn-patches` SKILL.md `--persist` recipe:** add an explicit **post-exit, pre-reboot snapshot verification** step:
   ```
   # After chroot exit, before safe_reboot:
   NEW_SNAPSHOT=$(btrfs subvolume list / | grep snapshots/run | tail -1 | awk '{print $NF}')
   echo "verifying $NEW_SNAPSHOT contents..."
   sudo mkdir -p /mnt/snapshot-check
   sudo mount -o subvol=$NEW_SNAPSHOT,ro /dev/sda2 /mnt/snapshot-check
   grep -h '^{%- set train_id' /mnt/snapshot-check/etc/obn/template/nv6-*.cfg | sort -u
   grep '^address1=' /mnt/snapshot-check/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection
   sudo grep -c 'default image is now' /mnt/snapshot-check/usr/share/obn/lib/device/vendor/vdsrail.py
   sudo umount /mnt/snapshot-check && sudo rmdir /mnt/snapshot-check
   ```

3. **`dosto-fzg-id-check` SKILL.md:** the skill's check-mode output should expose the actual template filename pattern observed (e.g. `nv6-NNN-XX.cfg` vs `nv6-XX-vY.cfg`) in the JSON, so downstream sed/grep recipes can adapt instead of hardcoding.

**Target.**
- ✅ `.claude/skills/dosto-obn-patches/SKILL.md` (#1 + #2 above) — **FIXED 2026-05-11** (Step 4 now uses glob explicitly; new Step 5.5 mounts the new snapshot read-only and re-verifies OBN markers + train_id + vlan7 before reboot; comments document why in-chroot verify is necessary-but-not-sufficient)
- 🟢 `.claude/skills/dosto-fzg-id-check/SKILL.md` (#3 above — expose template filename pattern in JSON output) — OPEN as a smaller follow-up

**Status.** **FIXED at the dosto-obn-patches layer** 2026-05-11 AR. The mount-RO snapshot verification step closes the worker-trusted-the-wrong-context loophole. `dosto-fzg-id-check` exposure of the filename glob pattern remains OPEN as a smaller follow-up — not blocking.

---

## F4 — Snapshot numbering surprise — promote produced `run1`, not `run3`

**Reproducer.**
Pre-promote on Fzg 130:
```
mount | grep " on / "
→ subvol=/.snapshots/run2 (ID 302)
```
Expected post-promote per engineer's mental model: `run3` (next monotonic).
Actual post-promote:
```
btrfs subvolume list / | grep snapshots/run
→ run0 (ID 261), run3 (ID 293), run2 (ID 302), run1 (ID 305 — new)
```
The chroot forked from `release`, not from `run2`. New snapshot got name `run1` (resetting/cycling).

**Impact.** 🟢 **Medium.**
- Engineer assumed run3. If verifying the right snapshot by name, would have checked the wrong one. We caught it because the parent verification step explicitly resolved the snapshot ID, not the name.
- Not destructive, just confusing.

**Proposed fix.**

1. **`dosto-obn-patches` SKILL.md `--persist`:** print expected behavior in the recipe header:
   > Note: `nd-systemupdate.sh.dont shell` forks from `release`, not from the running snapshot. The new snapshot name is whichever `runN` slot is currently unused — it does NOT increment monotonically. Verify by mounting the new snapshot via its ID (from `btrfs subvolume list / | tail -1`) rather than by guessing the name.

2. **CLAUDE.md "Pitfalls and quirks" section:** add a one-liner: *"Snapshot run names are slot-recycled, not monotonic. To know which snapshot is new after `nd-systemupdate.sh shell`, diff `btrfs subvolume list /` before and after."*

**Target.**
- ✅ `.claude/skills/dosto-obn-patches/SKILL.md` — **FIXED 2026-05-11** (snapshot-naming note folded into the Step 5.5 verify block from F3 — same physical recipe location, single visible note explains the non-monotonic naming)
- 🟢 `CLAUDE.md` — OPEN as a small follow-up (one-liner in Pitfalls section)

**Status.** **Mostly FIXED** 2026-05-11 AR — the in-skill note lives where the engineer/worker actually reads it during the chroot recipe, which is the most useful location. CLAUDE.md Pitfalls one-liner is a low-priority follow-up.

---

## F5 — Orchestrator agent cannot run as a subagent

**Reproducer.**
Spawned `dosto-orchestrator` via `Agent(subagent_type: "dosto-orchestrator")` from the engineer's top-level session. Orchestrator's agent definition declares `tools: Agent, SendMessage, Skill, Read, Write, Edit, Bash, Grep, Glob`. On its first attempt to call `Agent(subagent_type: "dosto-train-worker", ...)`, the harness returned verbatim:
```
No such tool available: Agent. Agent is not available inside subagents.
Complete the task with the tools provided and return findings to the orchestrator.
```
Subagents cannot spawn further subagents — Claude Code platform rule.

**Impact.** 🔴 **Critical (architecturally invalidating).**
- The architecture diagram in CLAUDE.md shows `engineer → dosto-orchestrate skill → dosto-orchestrator agent → N dosto-train-worker subagents`. The middle layer (orchestrator-as-subagent) doesn't work.
- We worked around it by having *the engineer's top-level session* play the orchestrator role directly. That works, but it's not what the contracts/agents document.

**Proposed fix.** Two options, pick one:

**Option A — Inline orchestration in the skill (recommended).**
- Delete `.claude/agents/dosto-orchestrator.md`.
- Rewrite `.claude/skills/dosto-orchestrate/SKILL.md` so its procedure runs *inline in the engineer's session*: parse train list, reconcile fleet-status, then spawn N `dosto-train-worker` subagents from the engineer's session directly. The skill itself acts as orchestrator.
- All references in CLAUDE.md and contracts to "orchestrator agent" become "orchestrator skill / orchestrator session" — meaning the engineer's top-level session running the skill.
- Pros: works with the platform; simpler stack (one fewer agent layer); engineer has direct control.
- Cons: the orchestrator can't run "in the background" while the engineer does other things — they share one session.

**Option B — Make the orchestrator a *script* (Python or Bash) the engineer runs in a separate shell.**
- Script handles parallel SSH-based worker invocation, JSON aggregation, fleet-status writes.
- Worker subagents become optional — script can do per-train commissioning directly via `dosto-commission-train` invocation.
- Pros: true background operation, runs independent of the chat session.
- Cons: massive rewrite. Loses the LLM-driven gate-prompt UX.

**My recommendation: Option A.** It's pragmatic, matches what already works in this run, and the bootstrap becomes simpler (one fewer agent definition).

**Target.**
- ✅ `.claude/skills/dosto-orchestrate/SKILL.md` (rewrite for inline operation) — **FIXED 2026-05-11** (folded full orchestrator runtime — pre-flight, parallel worker spawn, cycle loop, gate flow, fleet-status writer with Surgical-Changes allowlist, Confluence push policy, logging, end-of-day report, crash recovery, failure handling — into the skill body; skill now executes inline in the engineer's top-level session)
- ✅ `.claude/agents/dosto-orchestrator.md` (DELETE) — **DELETED 2026-05-11**
- ✅ `CLAUDE.md` (architecture diagram + role table) — **FIXED 2026-05-11** (diagram updated to show engineer's top-level session as orchestrator; role table revised; new "Why inline" rationale paragraph; single-train-debug note updated)
- ✅ `scripts/regenerate_bootstrap.py` (drop the orchestrator agent from embed list) — **FIXED 2026-05-11** (also updated docstring and validation messages)
- ✅ `scripts/validate_dosto_workspace.py` (cross-check C3 now reads dosto-orchestrate SKILL.md instead of the retired agent file; KNOWN_NON_SKILLS / REQUIRED_FILES updated) — **FIXED 2026-05-11**

**Status.** **Option A chosen and FIXED 2026-05-11 AR.** The architectural blocker is gone. Engineer runs `/dosto-orchestrate fzg=...` in their top-level session; that session IS the orchestrator. Workers are spawned from there via `Agent` (which the top-level session has). The pattern matches what the 2026-05-11 first-run test executed successfully end-to-end.

---

## F6 — Status pings burn 100k+ tokens for one-line replies

**Reproducer.**
Engineer asked "what stage are the workers on?" Parent first tried `TaskOutput` for both workers (returned "no task found" — they were idle between turns), then sent `SendMessage("status")` to each. Each worker resumed, re-loaded full context (~100k+ tokens), and produced a status reply.

Specifically the Fzg 130 worker's status reply was tagged `1 tool use, 166k tokens, 17s` — 166k tokens to produce a single one-line "Pre-flight emitted, awaiting confirmation" report.

**Impact.** 🟡 **High.**
- Status pings are a normal orchestrator operation. If each one costs 100k+ tokens, multi-train days will blow through Anthropic API budgets fast.
- Engineer's mental model: "what's the worker doing" should be a free question. Today it's not.

**Proposed fix.**

1. **`dosto-train-worker.md` agent definition:** add a section "Status-ping protocol":
   > When you receive a `SendMessage` whose only content is the single word `status` (or `status?` or `where are you`), reply with a one-line state summary (`stage.id`, `stage.current_step / total_steps`, `status`, last issue if any). Do NOT re-load contracts or skills. Do NOT emit a full JSON report. End your turn immediately.

2. **Engineer-facing convention** (document in CLAUDE.md): use the Tasks UI side panel for liveness checks; only use `SendMessage("status")` if the UI doesn't give enough detail.

3. **Avoid `TaskOutput` polling on local_agent tasks** — it's documented as misleading for those (it's symlinked to the full JSONL transcript and overflows context). Document the right tool: the Tasks UI panel.

**Target.**
- ✅ `.claude/agents/dosto-train-worker.md` (status-ping protocol) — **FIXED 2026-05-11** (in new "Operating discipline / Status-ping protocol" section)
- 🟢 `CLAUDE.md` (engineer convention — Tasks UI panel as the cheap status surface) — minor, defer

**Status.** **FIXED at the worker layer** 2026-05-11 AR. CLAUDE.md engineer-convention note remains OPEN as a small follow-up.

---

## F7 — `fix_obn_bugs67.py` produces bug 6 marker count of 2 (idempotency artifact)

**Reproducer.**
After applying patches via `fix_obn_bugs67.py`, the bug 6 marker grep returned count 2 in `/usr/share/obn/lib/tree.py`:
```
35:                    continue  # neighbour not in this consist (e.g. coupled train on another subnet)
37:                    continue  # neighbour not in this consist (e.g. coupled train)
```
The skill's expected count is 1. The two lines are semantically equivalent (both `continue` under the same guard condition) — the patch *works*, just produces an unexpected grep count.

**Impact.** 🟢 **Low (correctness OK, signal is muddy).**
- A naïve "count == 1 means patched" check would report bug 6 as anomalous. The skill's interpretation table doesn't currently say count==2 is also valid.
- Either `fix_obn_bugs67.py` is non-idempotent (writes both variants on each run), or it was run twice on this CCU, or it's intentional defense-in-depth.

**Proposed fix.** Pick one:

A. **Fix the script** — `fix_obn_bugs67.py` should detect either variant before writing, and only write one canonical guard line. Add an explicit idempotency assertion.

B. **Update the skill's interpretation table** — `dosto-obn-patches` SKILL.md "Interpret each grep -c count" rows should accept `1 or 2` for bug 6 with the note "two semantically equivalent guard comments may exist; both `continue` on the same condition is the correctness criterion."

**My recommendation: A.** Script-side fix is cleaner; the skill should remain strict. Investigate by re-reading `fix_obn_bugs67.py` source — likely a missing dedup check.

**Target.**
- ✅ `scripts/fix_obn_bugs67.py` — **FIXED 2026-05-11** (Option A — added cross-script idempotency check that detects either script's prior Bug 6 patch via `"neighbour_device is None" + "neighbour not in this consist"` markers, skips re-patching when found; previously the script wrote unconditionally even when no change was needed, which also caused a redundant always-write — that's fixed too by moving the file-write inside the `elif` branch)

**Status.** **FIXED 2026-05-11 AR.** Bootstrap-embedded fix-script now idempotent across runs and across cross-script collision with `fix_obn.py`. Root cause documented inline in the script: both scripts independently patch Bug 6 in `tree.py` with different anchors and different guard comments, producing the count=2 marker observed on Fzg 130.

**Investigation note (preserved for the record):** Root cause turned out to be a script collision, not a single-script idempotency bug. `fix_obn.py` line 152 writes guard comment `"...on another subnet"`; `fix_obn_bugs67.py` line 34 writes `"...coupled train"`. Both anchor matches independently succeed on a vanilla CCU, so running both scripts in sequence (as the canonical `--apply` recipe instructs) produces two functionally-equivalent guard lines back-to-back. Both `continue` on the same condition; semantically correct; grep-count surprising.

---

## F9 — Stadler FW commission state cannot be determined from TCP probes alone

**Reproducer (two-step engineer correction).**

Step 1: Post-reboot Fzg 130 vlan7 verify showed `nc -zv 172.19.193.1 80 → OPEN` and `nc -zv 172.19.193.1 22 → OPEN`. Parent (me) wrote in the audit terminal-state: *"Stadler FW fully reachable / commissioned ✅."*

Step 2: Engineer corrected: *"it means stadlers firewall isnt configured yet on this train"* — interpreting open management ports as bare/default Westermo FW behavior. I updated the records accordingly.

Step 3: Engineer corrected again: *"that was just an assumption - it could be that the FW is not configured, because typically we should not be able to ping it"* — clarifying that the open TCP ports alone don't determine commission state. The deciding test is **ICMP**, per CLAUDE.md Phase 6: *"Stadler firewall drops echo-request by policy."* A commissioned Stadler FW won't reply to ping; an uncommissioned/default-config one likely will. **We never ran ping during this session.**

**What we actually know about Fzg 130's FW:**
- ✅ ARP REACHABLE to `172.19.193.1` (MAC `00:90:e8:bb:9d:67`, Westermo OUI) — path clean, device exists
- ✅ TCP 80 OPEN, TCP 22 OPEN — *something* responds on management ports
- ❌ Commission state UNKNOWN — we didn't run the test that would distinguish configured vs default

**Impact.** 🟡 **High (methodology gap, not a one-off interpretation error).**

- The orchestrator stack would have logged "FW reachable ✅" and moved on — same mistake I made on the audit. The CCU-side checks return TCP-OPEN as a success signal; nothing in the documented post-reboot verify recipe currently mandates ICMP as the *deciding* test for commission state.
- Bigger issue: **multiple trains in the fleet may have been classified based on TCP probes alone.** Fzg 132's prior session notes record `Stadler firewall TCP-reachable on vlan7 (port 80 OPEN, port 22 OPEN)` and mark `FW reach: ✅` — but we have no record of an ICMP test there either. Same ambiguity. Same trains may need re-testing.
- CLAUDE.md Phase 6 itself is partially misleading. It correctly says *"Don't rely on ICMP alone"* (because ICMP is dropped by a configured FW, so a commissioned-FW ping fail isn't a fault). But it then promotes TCP probes as the *primary* health signal, when in reality TCP probes only confirm *path + responding device*, not *commissioned state*. The two are different questions.

**Proposed fix.**

1. **CLAUDE.md "Phase 6" rewrite — separate "path health" from "commission state":**

   *Path health* (does traffic flow to .1?):
   - ARP REACHABLE on vlan7 → ✅ path OK
   - No ARP / ARP FAILED → 🔴 path broken (cable, vlan, IP misconfig)
   - Use `ip neigh show dev vlan7` for this.

   *Commission state* (has Stadler applied policy to the FW?):
   - `ping -c 5 172.19.X.1` → **no replies, 100% loss** → ✅ commissioned (policy dropping ICMP)
   - `ping -c 5` → **replies received** → 🟡 NOT commissioned (default/bare Westermo, no policy yet)
   - This is THE deciding test, not TCP. CLAUDE.md Phase 6 should make this explicit.

   *Service availability* (does the FW expose intended services?):
   - TCP probes to whatever services Stadler is supposed to be exposing on .1 (we don't currently know what those are — Stadler-side documentation gap, separate issue).

2. **`dosto-vlan7-config` post-reboot verify recipe:** add ICMP as the commission-state test, document the expected fail-as-success interpretation. Currently the recipe runs only `nc -zv` which can't answer commission state.

3. **`dosto-l2-health` Phase 6 logic:** add a `fw_commission_state` field to the JSON output with values `commissioned | uncommissioned | path_broken | unknown`. Default `unknown` if ICMP wasn't tested. Don't infer from TCP alone.

4. **Existing fleet-status records:** any train marked `FW reach: ✅` based on TCP OPEN alone needs re-testing with ICMP before its customer report goes out. This affects Fzg 132 at minimum; possibly others.

5. **This audit's terminal-state for Fzg 130:** already corrected — `FW reach: 🟡 path clean, commission state TBD next session via ping`.

**Target.**
- ✅ `CLAUDE.md` (Phase 6 rewrite — separate path / commission / service) — **FIXED 2026-05-11**
- ✅ `.claude/skills/dosto-vlan7-config/SKILL.md` (add ICMP to post-reboot verify; new `fw_commission_state` field in `--json`) — **FIXED 2026-05-11**
- ✅ `.claude/skills/dosto-l2-health/SKILL.md` (Step 8 rewritten; `fw_reach` block now requires `fw_commission_state`; bottom-of-file pitfall corrected) — **FIXED 2026-05-11**
- 🟢 `fleet-status.md` (re-verify trains marked `FW reach: ✅` against the new rubric — next session work, not bootstrap)
- 🟢 `scripts/08_e2e_probe.sh` and `scripts/09_aggregate.sh` (must be updated to actually emit `fw_commission_state` per the new contract — downstream of the SKILL.md change, **next session**)
- 🟢 `.claude/skills/dosto-l2-report/SKILL.md` (must read `fw_commission_state` and translate `uncommissioned` to a Stadler-action item in the customer doc — **next session**)

**Status.** **FIXED at the contract layer** (CLAUDE.md + 2 SKILL.mds) **2026-05-11 AR.** Implementation in `scripts/08_e2e_probe.sh`, `scripts/09_aggregate.sh`, and `dosto-l2-report` SKILL.md remains OPEN as downstream-of-the-contract work. Fleet-status re-verification of historical `FW reach: ✅` entries also OPEN as a separate carryover task.

**Process meta-note for the audit:** F9 is also a clean illustration of *how this audit-style run finds gaps*. Two rounds of engineer correction were needed to land on the actual finding. The first correction (TCP-OPEN = uncommissioned) was sharper than my baseline assumption; the second correction (TCP alone can't determine commission state) was sharper still. Neither I nor the worker would have produced this without the engineer in the loop. The orchestrator architecture needs to bake in the assumption that the engineer's domain knowledge is *more authoritative than the LLM's interpretation of probe results* — not the other way around.

---

## F8 — Engineer-facing surface has high cognitive load (the visualization problem)

**Reproducer.**
Looking back at this session, each gate prompt I surfaced to the engineer was ~30+ lines of mixed content: rationale text, command preview, decision rubric, options menu, my commentary. The engineer had to scroll through this every time. Multiply by 5 gates × 2 trains × the parent's commentary on each = a wall of prose.

The Tasks UI side panel (which the engineer screenshotted) was actually *cleaner* than the chat surface. The engineer noted: *"i can see the tasks are completed here. why didnt the agent tell you that it had completed instead of you checking on them"* — pointing to a real gap: the chat assumes the engineer is reading every line; the UI panel is glanceable but Claude can't see it.

**Impact.** 🟡 **High (UX, not correctness).**
- The architecture was designed around an *engineer reading every prompt and typing a one-letter response*. In practice, the engineer wants a glanceable state (worker A doing X, worker B doing Y, decision needed on worker A) and to drill into only what matters.
- F8 is fundamentally different from F1–F7: those are mechanical bugs. F8 is an information-architecture problem.

**Proposed fix.** Two layers:

**Layer 1 — Tighter gate prompts.** Define a `.claude/contracts/approval-gates.md` template that constrains every gate prompt to a tight format:
```
[Gate N] <gate-name> — <train> — <one-sentence rationale>
Destructive: <y/n>  Reversible: <y/n>
Command: <one-line preview, full recipe in attached field>
Options: y | n | w | p | c | defer
```
No 30-line rationale paragraphs by default. Engineer can ask "explain more" if they want detail.

**Layer 2 — Status board.** Add to `dosto-orchestrate` skill (or as a separate `dosto-status-board` skill) an on-demand command that prints a fleet-wide one-screen status:
```
Fzg 130 / 4736-102  Stage 6/19  post_reboot_verify   ▶ verifying
Fzg 20  / 4734-120  Stage 1/19  initial_diagnostics  ▶ ⚠ paused (bash denial)
Fzg 131 / 4736-103  —           train offline         ⚪ skipped
```
One line per train. Engineer types `status` once, sees everything. Cheap because it's deterministic text rendering, not LLM-generated.

**Target.**
- ✅ `.claude/contracts/approval-gates.md` (tighter template — F8-L1) — **FIXED 2026-05-11** (bumped to v2; new "Compact prompt template" as default; verbose form retained as `?`-expansion fallback; sizing rules codified as contract terms; Gate 5 three-way compact form documented)
- ✅ `.claude/skills/dosto-orchestrate/SKILL.md` — F8-L2 status-board behavior — **FIXED 2026-05-11** (rolled into the F5 skill rewrite — "Engineer mid-run controls" section documents the `status` command, which prints a per-train one-line summary from in-memory state without waking any worker; cycle digest also serves as the rolling status board at cycle boundaries)

**Status.** **Both L1 and L2 FIXED 2026-05-11 AR.** L1 at the contract layer; L2 implementation lives in the dosto-orchestrate skill (one of two places where the cheap status surface now exists — the other is the engineer's Tasks UI panel, which works regardless and was already noted in the post-mortem of F6).

---

## Cross-finding meta-observations

### M1 — The contracts assume a uniform Bash capability across orchestrator + workers; reality is layered.

Subagent Bash permissions are stricter than parent Bash permissions in this harness. Several contracts implicitly assume workers can do everything the orchestrator can. They need an explicit "operations that may fail at the worker layer and require parent-handoff" appendix. This affects F1, F3, and to a lesser extent F2.

### M2 — Verification has been the canary every time.

Every loophole we caught was caught by *redundant verification from a different vantage point* (parent grep matched against worker's report, mount-RO snapshot check matched against in-chroot verify). The architecture should bake this in: every state-change stage emits its own assertions AND the parent independently re-verifies before approving the next gate. Today this happens by my judgment; it should be the contract.

### M3 — "Concise" prompts are achievable and cheap.

The single instruction "be concise — only include current-stage skill_outputs" dropped Fzg 130 worker context from 166k → 35k. This is overwhelming evidence that the *default* contracts emit too much. F2's fix is small in lines-of-code but massive in impact.

---

## Post-run terminal state (Fzg 130)

Captured 2026-05-11 ~05:46 UTC (CCU uptime 15 min post-reboot). Verified directly from the parent session via plain `sudo grep` and `nc -zv` one-liners — no subagent involved.

```
Boot snapshot:   /.snapshots/run1 (ID 305)            ✅ activated
vlan7 live IP:   172.19.193.2/17                      ✅ matches Fzg 130 formula (even → device 2)
vlan7 nmconn:    172.19.193.2/17,172.19.193.1         ✅ gateway recorded
train_id:        {%- set train_id = 130 -%}            ✅ single uniform line, 18/18 templates
OBN markers:     1, 2, 1, 1, 1, 2, 1, 1                ✅ 8/8 patched (bug 6 count=2 per F7)
TFTP helper:     nf_conntrack_tftp NOT loaded, no rule 🔴 expected — runtime fix lost on reboot per F1
Stadler FW ARP:  172.19.193.1 REACHABLE (00:90:e8:bb:9d:67)  ✅ Westermo OUI, path clean
Stadler FW TCP:  port 80 OPEN, port 22 OPEN           🟡 commission state NOT determined
Stadler FW ICMP: NOT TESTED                            ❌ this would have been the deciding test
```

**Bonus learning (two-step correction):** Fzg 130's path to the Stadler firewall is clean (ARP REACHABLE — confirmed). FW commission state is **NOT determined** from what we tested. I initially read TCP 80/22 OPEN as "fully commissioned ✅," then engineer flagged that interpretation; corrected to "uncommissioned 🟡"; engineer flagged that as also an assumption. Honest reading: ARP REACHABLE confirms the device exists at `.1`; TCP 80/22 OPEN tells us the FW or its underlying Westermo OS responds on management ports, but doesn't classify configured-vs-default. The actual test we should have run is **ICMP** — per CLAUDE.md Phase 6, *"Stadler firewall drops echo-request by policy"*. A commissioned FW won't reply to ping; an uncommissioned one will. We didn't ping. Fzg 130's FW state remains: path clean, commission state TBD next session.

**This is captured as audit finding F9 below — but reframed as a methodology gap, not a single-train interpretation error.**

**Outstanding (deliberately deferred at Gate 5 `partial`):**
- 4 missing switches D2/E2/E3/F2 → Stadler investigation needed
- TFTP CT helper not re-applied → only needed before AP firmware push, which we won't run until consist is complete
- `obn update c all` and `obn update f all` → blocked by missing switches
- L2 health check + customer report → blocked by incomplete consist

**Conclusion for the run.** The CCU-local recovery sequence documented in fleet-status produced the expected clean state on Fzg 130. The orchestrator-stack test itself produced findings F1–F8. The two outcomes are independent: the *commissioning* of Fzg 130 worked; the *orchestration mechanism* surfaced 8 loopholes.

---

## Recommended order of bootstrap patches (by ROI)

| # | Fix | Status | Effort | Impact |
|---|---|---|---|---|
| 1 | **F9** (CLAUDE.md Phase 6 + skills — correct FW commission-state interpretation) | ✅ FIXED 2026-05-11 | Low | **Critical correctness — affects every customer report across the fleet** |
| 2 | F2 (default `skill_outputs: []` + pointer spawn prompts) | ✅ FIXED 2026-05-11 | Low | Huge — fixes context bloat fleet-wide |
| 3 | F6 (status-ping protocol) | ✅ FIXED 2026-05-11 | Trivial | High — token savings on every status check |
| 4 | F5 (orchestrator inline, drop the agent) | ✅ FIXED 2026-05-11 | Medium | Critical — unblocks the architecture |
| 5 | F8-L1 (tight gate prompt template) | ✅ FIXED 2026-05-11 | Low | High — engineer UX |
| 6 | F1-C (worker handoff-on-denial protocol) | ✅ FIXED 2026-05-11 | Low | High — stops worker-retry waste |
| 7 | F3 (glob-not-filename in chroot verify + post-exit snapshot mount-RO) | ✅ FIXED 2026-05-11 | Low | High — correctness |
| 8 | F4 (snapshot naming note) | ✅ FIXED 2026-05-11 | Trivial | Low — folded into F3's recipe location |
| 9 | F8-L2 (status board command) | ✅ FIXED 2026-05-11 | Medium | High — engineer UX |
| 10 | F1-B (skill docs — SCP / heredoc parent-handoff pattern) | ✅ FIXED 2026-05-11 | Low | Medium — closes the handoff documentation loop |
| 11 | F7 (`fix_obn_bugs67.py` cross-script idempotency) | ✅ FIXED 2026-05-11 | Low | Low — cosmetic |

**Slate after the 2026-05-11 session: 11 of 11 items FIXED.** Every loophole the first-run test surfaced is now closed at the contract / skill / agent / CLAUDE.md / regenerator layer.

**Remaining downstream-of-the-contract work** (not loopholes; just code that needs to follow the new contracts):

- `scripts/08_e2e_probe.sh` — emit Q1 (ARP) + Q2 (ICMP) probe results per the F9 schema
- `scripts/09_aggregate.sh` — apply the F9 derivation rule to compute `fw_commission_state`
- `dosto-l2-report` SKILL.md — translate `fw_commission_state: uncommissioned` into a Stadler-action item in the customer docx
- `dosto-obn-patches` CLI — add `--skip-step1` flag for clean parent-handoff resume (F1-B follow-up)
- `dosto-fzg-id-check` SKILL.md — expose template filename pattern in JSON output (F3 follow-up)
- Fleet-status historical re-verification — for every train marked `FW reach: ✅` on TCP-OPEN evidence alone, run the new Q1 + Q2 ICMP test next session and update the row.

**F9 was the highest-priority correctness fix.** Until the downstream F9 implementation lands, any fleet train marked `FW reach: ✅` based on TCP-OPEN alone should be re-verified manually using the new CLAUDE.md Phase 6 rubric.

## Session close

All 11 audit findings closed at the contract/skill/agent layer. Bootstrap (`scripts/regenerate_bootstrap.py`) updated to reflect the v2 architecture. Next session can regenerate the bootstrap to propagate these fixes to a fresh-environment scaffold:

```bash
python scripts/regenerate_bootstrap.py            # scaffold (~127k tokens)
python scripts/regenerate_bootstrap.py --include-state   # + fleet-status / journal / runbooks (~156k tokens)
python scripts/regenerate_bootstrap.py --check    # dry run, just report sizes
```

The next fleet day can run end-to-end against the v2 stack with all loopholes from the first-run test closed.
