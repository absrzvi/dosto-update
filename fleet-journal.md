# DOSTO Fleet — Per-Train Journal

Narrative companion to [`fleet-status.md`](fleet-status.md). Where `fleet-status.md` answers *"what is the current state of every train"* in scannable table form, this file answers *"what happened on this train, in what order, and why."*

## What goes here

- Recovery sequences worked out for a specific train
- Session-specific context for the next engineer: train history, partial work in progress, things to verify
- Stadler-facing investigation notes (raw, before they become a customer report)
- Anything that previously lived as prose in `fleet-status.md` per-train detail blocks

## What does NOT go here

- **Current state** of any train — `fleet-status.md`
- **Cross-train architectural findings, gap audits, post-mortems** — these are *one-shot dated handoff docs* (`handoff-<topic>-<date>.md`). When a finding from a handoff doc is observed on a second train, it graduates to `CLAUDE.md` "Pitfalls."
- **Fleet-wide pitfalls** — `CLAUDE.md`
- **Skill behaviour** — the relevant `.claude/skills/<skill>/SKILL.md`
- **Cabling faults** — `cable-issues-register.md` (filed once Stadler diagnoses cause)

## File conventions

- One section per Fzg ID, in numeric order, grouped by series (4736 first, then 4734).
- Within each Fzg section, entries are append-only and dated. Most recent at the top. Never edit a prior session's entry — add a new one above it.
- Each entry starts with a `### <YYYY-MM-DD> — <initials> — <one-line summary>` header.
- Each entry answers: *what changed*, *what we learned*, *what's next*. Keep it tight; cross-reference handoff docs for cross-train findings rather than duplicating.

## Related handoff docs

- **2026-05-11 first-run audit** — [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md). Architectural findings F1–F8 from the first orchestrator-stack test.

---

## 4736 series

### Fzg 130 — 4736-102

#### 2026-05-11 — AR — CCU-local recovery executed via orchestrator-stack test run

**Session goal.** Test the orchestrator → train-worker → commission-train flow end-to-end. Recovery of Fzg 130 was a means to that end, not the primary goal. Findings on the stack are in [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md).

**Train-specific outcome.**

- Stage 1 `initial_diagnostics` confirmed prior state: 0/8 OBN patches, broken `128 + train_id` template, vlan7 = `172.19.215.130/17` (encoded Fzg 175). Plus a new finding: **4 switches missing** from vlan100 — D2, E2, E3, F2. Only 14/18 visible.
- Gate 5 (`device_count_mismatch`) approved as `partial`: proceed with CCU-local fixes only, halt before consist-wide pushes.
- Three-fix fold-in chroot promote (patches + vlan7 + train_id) into snapshot run1. Verified read-only mount confirmed correct contents before reboot.
- Post-reboot verify (parent-driven, 05:46 UTC, uptime 15 min): all green except expected TFTP-helper loss. Boot snapshot run1. vlan7 live = `172.19.193.2/17`. train_id = `130` uniform across 18 templates. OBN markers 8/8 (bug 6 count=2 per F7). **Stadler FW path: confirmed clean, commission state not confirmed** — ARP REACHABLE to `00:90:e8:bb:9d:67` (Westermo OUI); TCP 80 + 22 OPEN; ICMP not tested. Per CLAUDE.md Phase 6, the deciding test for a commissioned Stadler FW is ICMP (configured FW drops echo-request by policy), not TCP. Next session: run `ping -c 5 172.19.193.1` to determine actual FW state.

**Train-specific learnings.**

- Recovery sequence in fleet-status worked exactly as written.
- Template filenames on this CCU are `nv6-NNN-XX.cfg` (e.g. `nv6-100-A1.cfg`, `nv6-200-C1.cfg`), not `nv6-XX-vY.cfg`. Glob the templates, don't hardcode.
- D2/E2/E3/F2 missing pattern: D2 and F2 are mid-of-pair missing (peers present), E2+E3 missing together (broader E-coach issue). Not filed in cable-issues-register yet — pending Stadler diagnosis (power vs cabling vs switch fault).
- Stadler FW path is clean to `172.19.193.1` (ARP REACHABLE, TCP 80/22 OPEN) but FW commission state is **not confirmed** — we didn't run the deciding test (ICMP). A commissioned Stadler FW drops echo-request; an uncommissioned one wouldn't. Re-test next session before claiming FW state in customer reports.

**Next.** Mark Fzg 130 `🔴 BLOCKED — awaiting Stadler on D2/E2/E3/F2`. No customer report until consist-wide work resumes. TFTP CT helper not re-applied yet — only needed before AP firmware push, which is blocked anyway.

### Fzg 131 — 4736-103

#### 2026-05-11 — AR — Train offline, session skipped

CCU `10.179.11.1` unreachable (ping + ssh timeout) at attempt time. Fzg 130 on the same VPN was reachable, so the issue is train-side, not network-side. Worker spawned then killed cleanly. Fleet-status row reflects offline status.

### Fzg 132 — 4736-104

*(Journal entries to be migrated from `fleet-status.md` per-train block on next session visit. The Fzg 132 block currently contains the canonical record of: two-step promote requirement, TFTP CT helper runtime fix, AP firmware push parallelism failure, dosto-ap-firmware-update skill bugs found+fixed.)*

### Fzg 133 — 4736-105

*(Journal entries to be migrated. Current state: DONE w/ Stadler — Coach 5 AP2 missing, Stadler FW not commissioned.)*

### Fzg 136 — 4736-108

*(Journal entries to be migrated. Current state: BLOCKED on cable register #2 + #3.)*

### Fzg 137 — 4736-109

*(Journal entries to be migrated. Current state: BLOCKED on cable register #4. Stadler L2 fault report v1.0 already filed.)*

### Fzg 148 — 4736-120

*(Journal entries to be migrated. Current state: PAUSED mid-`obn update c all` 2026-05-04.)*

---

## 4734 series

### Fzg 1 — 4734-101

*(Journal entries to be migrated. Current state: BLOCKED on cable register #1.)*

### Fzg 20 — 4734-120

#### 2026-05-11 — AR — Partial Stage-1 probe via orchestrator-stack test; worker stalled mid-diagnostics

**Session goal.** Second parallel target of the orchestrator-stack test run. Architectural findings in [`handoff-bootstrap-audit-2026-05-11.md`](handoff-bootstrap-audit-2026-05-11.md).

**Train-specific findings (from worker's sub-check 5/6 report before it stalled):**

- ✅ Switches: 12/12 visible, all on `nv4-*-v8-020`, FW `7.4.2`
- ✅ APs: 16/16 visible, all on FW `6.11.2-0`, Nomad v1 config (0 in factory)
- ✅ vlan7: live + nmconnection both `172.19.138.2/17`
- 🟡 OBN patches: standard grep found no markers; not yet investigated whether CCU is genuinely vanilla or whether nv4 paths differ

**Open question.** If switches AND APs are already at target state but OBN patches grep returned empty, possibilities are: (a) someone commissioned this train without patches (risky, but apparently survived); (b) patches were applied, persisted, then a `release` rollback wiped them; (c) the canonical grep markers differ for nv4 platforms. Worth a deeper inspection next session — but not via a fresh worker until the F1/F2 fixes from the audit doc are in place.

**Next.** No fleet-status flip yet; defer further work on this train until the bootstrap-audit fixes land. Current state in fleet-status remains `⚪ UNKNOWN`.

---

## How to add an entry

1. Find the Fzg section (or create it if the train doesn't have one).
2. Insert a new dated `### YYYY-MM-DD — <initials> — <one-line summary>` header **at the top** of that train's section.
3. Keep it to *what changed / what we learned / what's next*. Cross-reference handoff docs for architectural findings rather than duplicating.
4. Update `fleet-status.md`'s per-train row only for state changes; the journal does not replace the table.
