# Runtime test plan — Option A symmetric coupler cost (pre-v9 validation)

**Date drafted:** 2026-06-20 · **Author:** AR + Claude · **Status:** PLAN ONLY — nothing executed.
**Purpose:** Prove Option A (flat symmetric coupler port-cost = 20000) on a real coupled pair at **runtime** before committing it to the template repos as **switch-config v9**. If it passes, the same change becomes the git MR across nv6/nv4/fv5/fv6.

## Why runtime-first
- `save running-config force` is reversible: the next `obn update c` from the *current* (v8) package re-renders the old `train_id × N` formula and wipes the test change. So this is a safe, no-commit field test.
- The June 2026-06-12 test already proved cost=20000 stops the churn — **but only on the active link** (B3-138 + B1-147). Option A sets **all four coupler ports on both trains**. This test validates the full Option A scheme, not just the one link.

## Goal (success criteria — must all hold to greenlight v9)
- [ ] All four coupler ports on **both** trains read `port-cost 20000` (no train_id value) in `show spanning-tree` and `show running-config`.
- [ ] Both ends of **each** coupler link show **equal** cost (the asymmetry is gone).
- [ ] Topology still correct: single root, one coupler link FWD, its redundant twin ALTR/BLK.
- [ ] **Zero TC churn**: with `system logging debug rstp,coupled` on, the per-switch "Flushing all entries" / TC cycle does NOT recur (frozen count over a sustained window, e.g. ≥10 min). Compare against the pre-change churning baseline.
- [ ] No new errors on coupler ports (CRC / carrier-false stay 0).

## Preconditions
- A coupled pair, both trains powered, B-to-B (or whichever orientation is available — note it).
- Reference pair from June: **4736-110 (Fzg 138) = box1-t23 / 10.179.23.1** and **4736-119 (Fzg 147) = box1-t12 / 10.179.12.1**. Confirm live CCU IPs and that the pair is actually coupled (verify coupler port link-state UP — "cables on" ≠ link up, per F5/A6 lesson).
- Switch IPs rotate on 2-min DHCP leases — **always resolve fresh via `sudo dhcp-lease-list`**, never reuse IPs.

## Access
```bash
# CCU:
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip>
# switch via sshpass from CCU (one command per session — CLI rejects ; chaining):
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"
swcmd() { sshpass -p 'Nom@dCome1n' ssh $SSH_OPTS admin@"$1" "$2"; }
```

## Target ports & current (pre-test) costs to revert to

Coupler ports = `e0-2` on **A1, A3, B1, B3** of each train. Current rendered values (v8, from 2026-06-12 harvest; the live values may differ slightly — capture them in Step 1 before changing):

| Switch | Current cost (v8) | Notes |
|---|---|---|
| A1 | train_id × 1,000,000 − 1 | =137,999,999 on Fzg 138 / 146,999,999 on Fzg 147 pattern |
| A3 | train_id × 2,000,000 − 1 | high |
| B1 | train_id × 2,000,000 − 1 | high (was the active end on 147) |
| B3 | train_id × 1,000,000 − 1 | low (was the active end on 138) |

Target (Option A): **all four = 20000** on both trains.

## Procedure

### Step 0 — Arm observation
On **both** CCUs, start a churn watcher and enable RSTP debug on the cab switches (extend to all 36 if quick):
```bash
# per coupled train, resolve cab switches:
sudo dhcp-lease-list 2>/dev/null | grep -E "nv6-(A1|A3|B1|B3)-"
# enable debug on each cab switch:
swcmd $SW "configure system logging debug rstp,coupled"
# baseline: capture a churning sample BEFORE the change (proves the test is valid)
swcmd $SW "show log" | tail -40    # expect repeating TC / "Flushing all entries"
```

### Step 1 — Capture current state (for revert + before/after)
For each coupler switch on both trains:
```bash
swcmd $SW "show spanning-tree"              # record role/state/cost of e0-2
swcmd $SW "show interface trunks"           # record e0-2 native + prune set
swcmd $SW "show running-config" | grep -A3 "interface e0-2"   # exact current cost line
```
Record the exact per-port cost so revert is precise.

### Step 2 — Apply Option A (cost only — keep native/prune test SEPARATE; see note)
**Set cost = 20000 on all four coupler ports, BOTH trains.** One command per session, leaf order doesn't matter for cost (no reboot):
```bash
# per coupler switch $SW on each train:
swcmd $SW "configure interface e0-2 spanning-tree port-cost 20000"
# DO NOT save yet — verify behaviour first (runtime change is live immediately)
```
> **Scope note:** test the **cost change alone first**. The native-vlan 999 retag is a *separate* MR item and a separate runtime change (combined-form trap: `switchport mode trunk native vlan 999 prune allow 5,15` rewrites the whole trunk def — see RECIPE lesson 2). Validate cost→churn first; only then, if you also want to validate native-999 in the same window, apply it as a distinct step and re-verify. Keeping them separate means a clean attribution of cause.

### Step 3 — Verify behaviour (the actual test)
```bash
# both ends of each link now equal?
swcmd $SW "show spanning-tree"        # e0-2 cost = 20000 on all four, both trains
# topology still safe?
#   - exactly one coupler link FWD, its twin ALTR/BLK
#   - single root across all switches
# churn stopped?
swcmd $SW "show log" | tail -40       # TC/"Flushing all entries" should STOP recurring
```
Watch for ≥10 min. The decisive signal: the TC/flush count **freezes** (as it did at 10:32Z on 2026-06-12 when the active link was set to 20000). Now it must hold with ALL four ports symmetric.

### Step 4 — Decision
- **PASS** (churn gone, topology correct, costs symmetric) → proceed to persist (Step 5) OR leave runtime-only and go straight to the git MR (v9). Persisting is optional for the test; the MR is the real durable path.
- **FAIL** (churn continues / topology breaks) → Option A insufficient; revert (Step 6), capture logs, escalate to VDS with the new evidence before any git change.

### Step 5 — (optional) Persist the runtime change
```bash
swcmd $SW "save running-config force"   # each switch; verify with show startup-config
```
> Remember: even persisted, the next `obn update c` from the v8 package reverts it. Persistence here only survives a power-cycle, not an OBN config push. The git MR (v9) is what makes it durable through `obn update c`.

### Step 6 — Revert (if test ends without committing to v9 deploy)
```bash
# restore each port's original cost captured in Step 1:
swcmd $SW "configure interface e0-2 spanning-tree port-cost <ORIGINAL>"
swcmd $SW "save running-config force"     # only if you had saved in Step 5
# disable debug logging:
swcmd $SW "no configure system logging debug"
```
Or simpler: a power-cycle clears any unsaved runtime change; an `obn update c` from v8 restores template state on all of them.

## After a PASS → v9 git MR
The runtime test validates exactly the change the MR makes. On PASS:
1. Edit the 4 coupler `.cfg` per repo (nv6/nv4/fv5/fv6): replace the `{%- if train_id < 10 %} … train_id × N … {%- endif %}` block with `spanning-tree port-cost 20000`.
2. Add `native vlan 999` to coupler trunks + `vlan 999` to vlans.j2 (if validated in Step 2 variant).
3. Bump `version` → switch-config **v9**; README line.
4. MR → review by Davud (owns v0.0.18/0.0.19 cost formula) → merge → package → Puppet → `obn update c` per train.
5. Re-verify on a coupled pair (same success criteria) → clean capture → clears the Giorgio gate.

## Risks / guard-rails
- **One command per SSH session** — CLI rejects `;` chaining.
- **Cost change does NOT reboot the switch** (unlike config push) — it's live and low-risk; revert is symmetric.
- **Do not touch e0-2 native on coupled fleet trains mid-service without the combined-form** — partial trunk reconfig briefly exposed VLAN 100 to the FW once (RECIPE lesson 2).
- **Verify coupler link is actually UP** before trusting "no churn" — a dead/half-seated coupler also shows no churn but proves nothing (F5/A6).
- **Orientation:** if the available pair couples A-to-A or A-to-B rather than B-to-B, note it — Option A should hold in all four orientations (that's its whole point), so a non-B-B test is actually a *stronger* validation.
