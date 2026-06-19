# dosto-orchestrate Enhancement Notes — 2026-05-21

Observed during first real multi-train test run (Fzg 139, 147, 148, 19 — 2026-05-21).
Engineer: Abbas Rizvi. Record these before implementing so priority can be assessed.

---

## #1 — Auto-resolve CCU IPs from fleet-status when `@<ip>` omitted

**Area:** Input parsing (Step 1)

**Observed:** Engineer typed `/dosto-orchestrate fzg=139,147,148,19,21` without `@<ip>` suffixes. Skill spec hard-errors in this case. Orchestrator manually resolved all 5 IPs from fleet-status to proceed.

**Proposed fix:** When `@<ip>` is omitted for a Fzg, look up the CCU IP from the fleet-status row. If found and non-❓, use it with a one-line warning per train:
```
ℹ️  Fzg 139: using IP 10.179.24.1 from fleet-status (no @<ip> supplied) — correct? [Y/n]
```
Only hard-error when the IP is genuinely unknown (❓ in fleet-status or row absent).

**Why the friction still matters:** The existing rationale for requiring `@<ip>` is to catch stale IPs. Auto-resolve with a per-train confirmation achieves the same safety goal with far less typing for the common case (returning engineer, all IPs already filed).

---

## #2 — Clean up `## Pending Fzg assignment` when IP gets confirmed

**Area:** fleet-status hygiene (Step 2 reconciliation)

**Observed:** `10.179.45.1` appeared in both the Fzg 19 series table row (confirmed) AND the `## Pending Fzg assignment` section (added by morning-brief sweep). The reconciliation step didn't notice or clean it up.

**Proposed fix:** During Step 2, after confirming each train's IP, check the `## Pending Fzg assignment` section. If the confirmed IP appears there, remove that row from Pending automatically (surgical edit, one row). Print a one-line note in the plan summary.

---

## #3 — DONE train prompt should read `Next action` before alarming the engineer

**Area:** Step 2 DONE-train gate

**Observed:** Fzg 21 was DONE but had `Customer report: ⬜`. The current prompt says "Including it would re-run all 19 stages on a healthy train" — alarming and inaccurate when the only remaining item is report generation.

**Proposed fix:** Before showing the DONE gate, read the train's `Next action` from fleet-status. If the only outstanding item is `customer report only`, show:
```
⚠️  Fzg 21 is DONE but has Customer report: ⬜.
    Include to run report generation only? [y/n]
```
Reserve the "re-run all 19 stages" warning for trains with genuinely non-trivial remaining work.

---

## #4 — Auto-compute vlan7 IPs in pre-flight success criteria

**Area:** Step 5 Pre-Flight block

**Observed:** The success criteria block listed expected vlan7 IPs (e.g. `vlan7=172.19.197.130`) — these were manually computed. The skill already has the formula. No reason the engineer should verify bit-packing math at pre-flight time.

**Proposed fix:** Compute all vlan7 IPs inline during Step 5 using the formula:
```python
octet3 = 128 + (fzg // 2)
octet4 = (128 if fzg % 2 == 1 else 0) + 2
```
Show the computed value in the success criteria block. No manual input needed.

---

## #5 — Use fping + ARP OUI match for pre-flight device count, not DHCP

**Area:** Step 5.5 Network pre-flight

**Observed:** First pre-flight attempt used `dhcp-lease-list` and returned sw=0 for all trains. VDS switches have 2-minute DHCP lease lifetimes — switches that haven't recently renewed don't appear. The second attempt using `fping` + `ip neigh show` OUI match gave accurate counts.

**Proposed fix:** Replace DHCP-based device count with:
```bash
fping -a -q -g <subnet>.128 <subnet>.255 2>/dev/null   # refresh ARP
ip neigh show dev vlan100 | grep 'a0:59:3a' | wc -l   # VDS switches
ip neigh show dev vlan100 | grep '00:14:5a' | wc -l   # Westermo APs
```
Same wall-clock time (~15s), no DHCP timing dependency.

---

## #6 — Distinguish soft-warn from hard-FAIL in pre-flight results

**Area:** Step 5.5 Network pre-flight

**Observed:** Pre-flight classified Fzg 147 (1 AP missing) and Fzg 148 (1 sw + 2 APs missing) as FAIL alongside genuinely unreachable trains. In practice both were timing issues (APs mid-reboot, DHCP not yet renewed). The prompt implied a cable fault when none existed.

**Proposed fix:** Two-tier classification:

| Condition | Classification |
|---|---|
| CCU unreachable on TCP/22 | 🔴 hard-FAIL — do not dispatch |
| Missing devices, count below threshold (e.g. >20% absent) | 🔴 hard-FAIL — prompt engineer |
| Missing 1-2 APs on an otherwise healthy train | 🟡 soft-warn — dispatch with note |
| All devices present | ✅ PASS |

Soft-warn trains dispatch automatically; they'll hit Gate 5 (device_count_mismatch) in Stage 2 if the count doesn't improve, which gives a targeted per-train prompt with specifics.

---

## #7 — Auto-dispatch when all trains are PASS or soft-warn

**Area:** Step 5.5 Network pre-flight

**Observed:** When all trains had plausible-timing shortfalls (no hard-FAILs), the skill still stopped for a `[Y/n/all]` prompt. Unnecessary friction — the engineer had just confirmed the plan 30 seconds earlier.

**Proposed fix:** Only prompt when ≥1 hard-FAIL exists. If all trains are PASS or soft-warn, print the results block and dispatch immediately:
```
All 4 trains passed pre-flight (2 with soft warnings — see above). Dispatching.
```

---

## #8 — Workers cannot SCP or SSH — pre-stage scripts during Step 5.5

**Area:** Worker capability / orchestration design

**Observed:** Both Fzg 139 and Fzg 147 workers escalated to the orchestrator when they needed to SCP fix scripts to the CCU. The harness denies Bash/SCP in the subagent context. The orchestrator had to SCP the files and re-spawn the worker with context.

**Proposed fix (preferred — option B):** During Step 5.5, after confirming reachability for each accepted train, the orchestrator pre-stages all fix scripts to every CCU:
```bash
scp fix_obn.py fix_obn_bug8.py fix_obn_bug9_pysnmp_thread_safety.py developer@<ccu>:/tmp/
ssh developer@<ccu> "sudo cp /tmp/fix_obn*.py /var/tmp/"
```
Workers then never need SCP — scripts are guaranteed present at `/var/tmp/` when they start. Include a note in the worker spawn prompt confirming scripts are staged.

**Option A (alternative):** Add SCP to the allowed tool list in `.claude/agents/dosto-train-worker.md`. Simpler but gives workers broader access than they need.

---

## #9 — Detect IP conflicts across series table AND detail blocks during reconciliation

**Area:** Step 2 reconciliation

**Observed:** `10.179.12.1` was listed in the Fzg 147 at-a-glance row AND in the Fzg 140 detail block header. The reconciliation step only checked the at-a-glance table row, not detail blocks. Worker correctly caught it — but only after spawning.

**Proposed fix:** During Step 2, after resolving each train's IP, grep the full fleet-status file for that IP string. If it appears in any detail block header (`**CCU:** \`<ip>\``) for a different Fzg, surface a warning before spawning:
```
⚠️  IP 10.179.12.1 also appears in the Fzg 140 detail block.
    Confirm which train owns this IP before proceeding.
```
This catches the conflict at reconciliation time, not after a worker has been spawned and consumed 45s of context.

---

## #10 — Workers exit after emitting NEEDS_APPROVAL instead of waiting

**Area:** Worker gate behaviour / platform constraint

**Observed:** Every worker that emitted `NEEDS_APPROVAL` completed immediately rather than staying alive to receive the `SendMessage` response. This means every gate requires a full worker re-spawn with all accumulated state re-passed in the prompt.

**Root cause:** Platform constraint — background agents cannot block awaiting a message. They complete and the harness notifies the orchestrator.

**Mitigation (codify the pattern):** Update `.claude/agents/dosto-train-worker.md` to document the re-spawn pattern explicitly:
1. Worker emits gate JSON and exits.
2. Orchestrator receives notification, surfaces gate to engineer, gets response.
3. Orchestrator re-spawns worker with: original train spec + all `fields` from prior reports + gate response + "resume from stage X" instruction.
4. Worker reads the resume stage from its prompt and picks up from there.

This is already happening informally — making it explicit in the agent definition will make re-spawn prompts consistent and prevent context loss.

---

## #11 — `/tmp` vs `/var/tmp` chroot bind-mount mismatch

**Area:** SCP / chroot workflow

**Observed:** Fix scripts were SCP'd to `/tmp/` (only writable path for the `developer` user without sudo). The CCU chroot (`nd-systemupdate.sh.dont shell`) bind-mounts `/var/tmp/`, not `/tmp/`. Scripts at `/tmp/` are invisible inside the chroot.

**Fix:** After every SCP to `/tmp/`, immediately run:
```bash
ssh developer@<ccu> "sudo cp /tmp/fix_obn*.py /var/tmp/"
```
This should be a named step in the orchestrator's pre-staging sequence (Enhancement #8). Document in `troubleshooting-runbook.md` under "CCU script staging".

---

## #12 — Orchestrator should proactively SCP scripts during Step 5.5

**Area:** Step 5.5 / SCP responsibility

**Observed:** Workers encountered SCP-denied errors mid-pipeline, causing them to escalate and re-spawn. The orchestrator is the only entity that can SCP. The right time to do it is during Step 5.5 (after CCU reachability is confirmed, before workers spawn) — not reactively when a worker hits the wall.

**Proposed fix:** After each train passes TCP/22 reachability in Step 5.5, the orchestrator immediately stages all required scripts:
```bash
# For each passing CCU in parallel:
scp fix_obn.py fix_obn_bug8.py fix_obn_bug9_pysnmp_thread_safety.py developer@<ccu>:/tmp/
ssh developer@<ccu> "sudo cp /tmp/fix_obn*.py /var/tmp/ && echo STAGED"
```
Log staging result per train. If staging fails for a train, demote it to soft-warn in the pre-flight results. Add `scripts_staged: true/false` to each train's spawn prompt so workers know whether to expect the files.

---

## Summary — implementation priority

| # | Impact | Effort | Priority |
|---|---|---|---|
| 8 + 12 | Eliminates worker re-spawns for SCP | Low | **High** |
| 9 | Catches IP conflicts before spawn | Low | **High** |
| 1 | Removes biggest input friction | Low | **High** |
| 5 | Fixes false FAIL counts in pre-flight | Low | **High** |
| 10 | Codifies re-spawn pattern | Low | Medium |
| 11 | Prevents chroot staging failures | Low | Medium |
| 6 + 7 | Reduces unnecessary prompts | Medium | Medium |
| 3 | Better DONE train UX | Low | Medium |
| 2 | fleet-status hygiene | Low | Low |
| 4 | Auto-compute vlan7 in pre-flight | Low | Low |
