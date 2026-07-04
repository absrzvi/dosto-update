---
name: dosto-device-discovery
description: Discover all switches and APs reachable from a DOSTO CCU via DHCP leases, count them against the per-consist expected total (12+16 for nv4, 18+24 for nv6), and pinpoint missing devices to a specific switch+port using the topology reference at train-ip-allocation-commission/extracted/_shared/<schema>-topology.md. Use as the first step (sub-stage of initial_diagnostics) of any train commissioning workflow — if devices are missing, downstream consist-wide operations like obn update c all are unsafe and must wait for Stadler. Use in --check mode for an engineer-readable report or --json mode for subagents.
---

# DOSTO Device Discovery

The first thing every train workflow does. Verifies the CCU sees the **expected number of switches and APs** for the consist size, and if any device is missing, **pinpoints which switch+port should host it** so Stadler can be told exactly where to look. Reads the per-series topology file as ground-truth.

## Why this skill exists

If a switch or AP isn't visible in `dhcp-lease-list`, the consist is incomplete. Running `obn update c all` against an incomplete consist pushes config to the visible switches and leaves the missing one in a partial-state when it eventually shows up — exactly the mixed-state RSTP storm we built `dosto-obn-patches` to avoid. **Discovery has to gate consist-wide operations.**

The "tell Stadler exactly where to look" requirement is what makes this a skill rather than just a `dhcp-lease-list` wrapper. The orchestrator/engineer needs to be able to escalate "Coach D AP4 — switch D3 port e1-2" not "an AP is missing somewhere."

## When to use

- **Step 4c (sub-stage of `initial_diagnostics`) of [train-login-checklist.md](../../../train-login-checklist.md)** — every train, every visit, before any other diagnostic.
- **Whenever fleet-status `aps` cell shows an AP-count mismatch** — re-run to confirm and pinpoint.
- **After Stadler claims a cable fix is done** — re-run to verify the missing device now shows up.

## Modes

| Mode | Purpose |
|---|---|
| `/dosto-device-discovery <ccu-ip>` (default `--check`) | Read-only diagnostic. Prints engineer-readable verdict + per-coach breakdown + missing-device localisation. Updates fleet-status `aps` and `switches_v8` cells (suggested values). |
| `/dosto-device-discovery <ccu-ip> --json` | Same data, emitted as the `skill_outputs[].raw` block from [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md). Subagent consumes this. |

Subagents always pass `--json`. Engineers running interactively use `--check`.

## Inputs

- **`<ccu-ip>`** — required. The CCU's IP (e.g. `10.179.10.1`).
- **`<train#>`** — optional. The Nomad-internal primary identifier (e.g. `4736-104`). When given, the skill resolves Fzg + consist + series from the fleet-status row. When omitted, infer from `train-id` template on CCU OR from the box1-tNN hostname (per fleet-status reverse lookup by CCU IP).

The skill reads the appropriate topology reference based on the consist:
- `train-ip-allocation-commission/extracted/_shared/nv4-topology.md` for 4-car
- `train-ip-allocation-commission/extracted/_shared/nv6-topology.md` for 6-car

## Procedure

### Step 1: SSH to CCU and gather discovery data (one round-trip)

```bash
ssh -i "C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh" developer@<ccu-ip> '
echo "=== HOST ==="
hostname; uptime
echo "=== train_id template (single hardcoded value expected) ==="
grep -h "^{%- set train_id" /etc/obn/template/nv*-*.cfg 2>/dev/null | sort -u
echo "=== schema (nv4 vs nv6) ==="
ls /etc/obn/template/ | grep -oE "^nv[46]" | sort -u
echo "=== SWITCHES ==="
sudo dhcp-lease-list 2>/dev/null | grep -i "a0:59:3a" | sort -t. -k4 -n
echo "=== APs ==="
sudo dhcp-lease-list 2>/dev/null | grep -i "00:14:5a" | sort -t. -k4 -n
'
```

### Step 2: Determine expected counts from schema

| Schema | Switches | APs | Coaches |
|---|---|---|---|
| nv4 (4-car) | 12 | 16 | A, G, E, B |
| nv6 (6-car) | 18 | 24 | A, C, D, E, F, B |

If the CCU's templates aren't recognisable as nv4 or nv6, **stop and surface to engineer** — non-DOSTO-NEU consists aren't supported by this skill.

### Step 3: Parse switch hostnames

Each lease line has hostname like `nv6-A1-v8-132`. Extract:
- **Position** (e.g. `A1`) — second segment after `-`
- **Coach letter** (e.g. `A`) — first character of position
- **Switch number in coach** (e.g. `1`) — second character of position

If any hostname pattern doesn't match `nv[46]-[A-Z][1-3]-v[0-9]+-[0-9]+`, flag it (e.g. `dosto-00000000` means a switch never received OBN config).

### Step 4: Match against expected switch list from topology file

Read `train-ip-allocation-commission/extracted/_shared/<schema>-topology.md`, parse the "Switches" table for expected positions. For each expected position, check if a hostname with that position exists in the lease list.

| Outcome | Verdict |
|---|---|
| All expected positions present | ✅ all switches reachable |
| 1+ missing position(s) | 🔴 **switch missing** — escalate immediately, this is worse than missing APs |

A missing switch is more severe than a missing AP because:
- Switches host the network. Missing one means a coach has no connectivity.
- Likely a power issue, a dead switch, or a fundamental cabling fault — not a typical "AP not installed" issue.

### Step 4b: Classify each missing switch — cold bypass vs cabling error (VDS-specific)

**Do this for every switch flagged missing in Step 4.** A missing switch is NOT necessarily a cabling fault. VDS Rail Consist Switches have **cold bypass**: when a switch is powered off or failed, its backbone trunk ports (`e0-0`/`e0-1`) are relay-passed-through, so its two chain-neighbours end up LLDP-adjacent to *each other* across the dead switch's position. This is indistinguishable from "switch removed and re-cabled" **unless you check the LLDP reciprocal.** (See memory `vds-switch-cold-bypass`; mis-called twice — Fzg 137 2026-06-12, bench A1 2026-07-04 — before the reciprocal check was formalised here.)

OBN's own `number_coaches` walk (`report_dosto_neu.py`) has NO expected-topology model — it follows live LLDP only, so a bypass gap silently dead-ends the walk and `normalise_devices()` **deletes every device the walk couldn't reach past the gap**. They vanish from the report entirely rather than showing as "down." This step is where *our* tooling recovers the "switch DOWN" verdict OBN can't produce (Option 3, 2026-07-04 — the engine-side fix that would make OBN itself show a DOWN switch is a separate R&D ask).

**The expected-adjacency source of truth** is the "Inter-coach trunks (LLDP topology) — aliasing resolved" table in `_shared/<schema>-topology.md`. For each missing switch `X`, read off its two expected chain-neighbours `L` (via `X e0-0`) and `R` (via `X e0-1`) from that table — the switches that sit either side of `X` in the A-G-E-B (nv4) / A-C-D-E-F-B (nv6) chain.

Then SSH to `L` and `R` (both must be present/leased) and read LLDP on the ports that face `X`:

```bash
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<L-ip> "show lldp neighbours"      # the port toward X
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<R-ip> "show lldp neighbours"
# and the physical link state on those ports:
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<L-ip> "show interface <port-toward-X> details" \
  | grep -iE "Speed|Duplex|carrier|RX errors|crc"
```

Classify from the signatures:

| Signature at L and R (ports facing X) | Classification | `bypass_status` |
|---|---|---|
| L LLDP-sees **R** and R LLDP-sees **L** (reciprocal), both links UP, clean (0 CRC) | **Cold bypass** — X is powered off / failed in place, backbone relayed through it | `cold_bypass` |
| One neighbour's port is **UP but shows NO LLDP peer**, ± CRC/RX errors | **Dead / half-connected** — X powered off at a chain end (no second neighbour to bypass to), or a bad patch cable to X | `dead_link` |
| Neighbour port **DOWN / no carrier** | **Physically disconnected** — cable to X pulled or never landed | `link_down` |
| L/R see some *other, unexpected* switch (not each other, not X) | **Genuine miscable** — Stadler wired the wrong port | `miscable` |

**What this classification is for:** it starts the investigation pointed the right way — it is a **strong lead, not proof.** LLDP alone cannot fully separate a genuine cold bypass from a bypass-shaped miswire (Stadler patched L straight to R and X is actually fine on a dangling cable) — both show the same reciprocal. That's acceptable: the `cold_bypass` verdict tells the field tech **"check power/health of X first,"** and if they find X powered and healthy, the investigation pivots to the cable on its own. Either outcome is better than the device silently vanishing with no localisation. Two things sharpen the lead (use them when present, don't block on them): (a) the reciprocal must land on the **port the schema says faces X** — bypass is a relay, so L sees R on L's normal toward-X port; a peer seen on the *wrong* port leans `miscable`; (b) if X is later independently confirmed powered (a lease, ICMP on a stub, physical LED, Stadler says it's energised), then "neighbours bridged **and** X alive" flips the call to `miscable`. Phrase the Stadler instruction as a starting hypothesis ("cold-bypass signature — check power/health of X first; if X is powered, inspect the L↔X / X↔R cabling"), never as a settled fact.

Notes:
- **Two neighbours vs one.** Most switches have two chain-neighbours (an intra-coach and an inter-coach one) — a cold bypass there gives the clean **reciprocal** signature (e.g. bench A1: A3 via e0-0 intra-coach ↔ G1 via e0-1 inter-coach both see each other). A true chain **terminus** (last-coach SW3, e.g. B3 on nv4) has only ONE neighbour, so there's nothing to bypass *to* — a dead terminus shows as **link-up-no-LLDP on that single neighbour** (the `dead_link` signature), not a reciprocal. Classify a terminus as `cold_bypass` only if the single link is clean (0 CRC); `dead_link` if CRC/RX errors are present (points at the switch being crashed or the cable being bad).
- Cold bypass covers **backbone trunks only.** Any AP hanging off the bypassed switch (its `e0-4` / `e1-2`) stays dark — expect a correlated missing-AP finding for that coach.
- The engineer/Stadler instruction differs by class: `cold_bypass`/`dead_link` → "check **power/health** of switch X" (NOT re-cabling); `miscable`/`link_down` → "check the **cable** to X."

### Step 5: Parse AP config names and slots

Lease hostnames look like `AP1-v1-00145a04...` or `AP1m-v1-00145a04...`. Extract:
- **Slot number** (`1`/`2`/`3`/`4`) — digit after `AP`
- **`m-` flag** — present or absent
- **MAC suffix** — last 12 chars (used to correlate with switch LLDP later if needed)

For the orchestrator to know "this AP belongs to coach X" you can't tell from the AP's own hostname (it doesn't encode coach). You have to either:
- (a) Compare to the topology table — if 4 APs of slot 1 are expected (A1, C1, D1, E1, F1, B1 = 6 of slot 1 on nv6 actually — wait, slot 1 is per coach so 6 APs of slot 1 expected) and only 5 are present, the *missing one* tells you which coach lacks AP1.
- (b) SSH to switches and read LLDP on the AP-trunk ports — definitive but slower.

For Step 5, do (a). Save (b) for the localisation step in Step 7.

**Per-config-name expected counts (nv6):**

| Config | Expected count | Coaches |
|---|---|---|
| `AP1-v1` | 3 | A, C, D |
| `AP2-v1` | 3 | A, C, D |
| `AP3-v1` | 3 | A, C, D |
| `AP4-v1` | 3 | A, C, D |
| `AP1m-v1` | 3 | E, F, B |
| `AP2m-v1` | 3 | E, F, B |
| `AP3m-v1` | 3 | E, F, B |
| `AP4m-v1` | 3 | E, F, B |
| **Total** | **24** | |

**Per-config-name expected counts (nv4):**

| Config | Expected count | Coaches |
|---|---|---|
| `AP1-v1` | 2 | A, B |
| `AP2-v1` | 2 | A, B |
| `AP3-v1` | 2 | A, B |
| `AP4-v1` | 2 | A, B |
| `AP1m-v1` | 2 | G, E |
| `AP2m-v1` | 2 | G, E |
| `AP3m-v1` | 2 | G, E |
| `AP4m-v1` | 2 | G, E |
| **Total** | **16** | |

### Step 6: Compute differences

| Symptom | Verdict |
|---|---|
| AP count == expected, all configs balanced | ✅ all APs visible |
| AP count == expected − N (1 ≤ N ≤ 3) | 🔴 N missing — proceed to localisation |
| AP count > expected | 🟡 unexpected extra (stale lease from coupled consist? duplicate?) |

### Step 7: Localise missing APs (the value-add step)

For each "1 missing AP4 plain-config" type finding, the missing AP could be in any of the candidate coaches (e.g. for missing `AP4-v1`, candidates are A, C, D on nv6).

To pinpoint exactly which: SSH to each candidate coach's third switch (A3, C3, D3 on nv6), check `e1-2` (the AP4 trunk port from the topology file):

```bash
sshpass -p "Nom@dCome1n" ssh $SSH_OPTS admin@<switch-ip> "show interface e1-2 details" \
  | grep -E "Speed|RX bytes|TX bytes"
```

The switch with `Speed: Auto / RX bytes: 0 / TX bytes: 0` is the one with no AP attached. That's the missing-AP coach.

The same pattern works for missing AP1/AP2/AP3 — they hang off `e0-4` of switches `<X>1`, `<X>2`, `<X>3` respectively.

**Topology lookup table (which switch+port hosts each AP):**

| Schema | AP slot | Switch | Port |
|---|---|---|---|
| nv6 | AP1 | `<coach>1` | `e0-4` |
| nv6 | AP2 | `<coach>2` | `e0-4` |
| nv6 | AP3 | `<coach>3` | `e0-4` |
| nv6 | AP4 | `<coach>3` | `e1-2` |
| nv4 | AP1 | `<coach>1` | `e0-4` |
| nv4 | AP2 | `<coach>2` | `e0-4` |
| nv4 | AP3 | `<coach>3` | `e0-4` |
| nv4 | AP4 | `<coach>3` | `e1-2` |

Where `<coach>` ∈ {A, C, D, E, F, B} for nv6 or {A, G, E, B} for nv4.

### Step 8: Compute Stadler-actionable instruction

For each missing AP, output a one-line instruction Stadler can act on:

```
Coach D AP4 (slot D4) — should connect to switch D3 (10.179.10.193) port e1-2.
Currently: link DOWN, RX/TX bytes = 0, no LLDP peer. Verify AP is physically
installed and powered; check patch cable to D3 e1-2.
```

This goes into:
- **`approval_needed.rationale`** of the JSON report (subagent will set `status: NEEDS_APPROVAL`, `gate: device_count_mismatch` once that gate is added to the contract)
- **The fleet-status row** (`aps` cell becomes `🔴 23/24 (D4 missing)`)
- **`cable-issues-register.md`** — the orchestrator auto-appends a new row at Step 7.5 of `dosto-orchestrate` if no matching open entry exists. This skill never writes the register directly — it emits the `ap_missing[]` / `switches_missing[]` arrays in the JSON output so the orchestrator has the structured data it needs to do the append.

### Step 9: Three-way prompt (per [autonomy-boundary.md](../../contracts/autonomy-boundary.md))

If devices are missing, emit `NEEDS_APPROVAL` with the three options the user previously specified:

```
─── DEVICE COUNT MISMATCH ────────────────────────
Train:        Fzg 132 / 4736-104 (10.179.10.1)
Consist:      6-car (nv6)
Expected:     18 switches, 24 APs
Found:        18 switches ✅, 23 APs 🔴

Missing:
  • Coach D AP4 (slot D4)
    → Should connect to: switch D3 (10.179.10.193) port e1-2
    → Currently: link DOWN, RX/TX bytes = 0, no LLDP peer

Action options (per autonomy-boundary device_count_mismatch gate):
  [w] Wait — escalate to Stadler. Set BLOCKED. Stop subagent.
  [P] Partial — proceed with CCU-local fixes (patches/vlan7) only.
                Stop before any obn update c or health check.
                Re-run discovery after Stadler fixes the cabling.
  [c] Continue full — accept consequences. obn update c will run with
                23 APs; D4 in pending state when eventually wired.

Choice [w/P/c]:  (default: P)
```

`P` (partial) is the recommended default — gets local CCU work done while waiting on Stadler, no consist-wide damage.

## Output formats

### `--check` mode (default, engineer-readable)

```
─── Device Discovery — Fzg 132 / 4736-104 (10.179.10.1) ───
CCU hostname:    box1-t10
Consist:         6-car (nv6)  ← from /etc/obn/template/nv6-*.cfg
Expected:        18 switches, 24 APs

Switches:        ✅ 18/18
  All hostnames consistent: nv6-X-v8-132
  All 6 coaches present (A, C, D, E, F, B)

APs:             🔴 23/24
  By config:
    AP1-v1:    3/3 ✅
    AP2-v1:    3/3 ✅
    AP3-v1:    3/3 ✅
    AP4-v1:    2/3 🔴  one missing
    AP1m-v1:   3/3 ✅
    AP2m-v1:   3/3 ✅
    AP3m-v1:   3/3 ✅
    AP4m-v1:   3/3 ✅
  Localising AP4-v1 missing... probing A3, C3, D3 e1-2...
    A3 e1-2: 1G full, RX=2.5MB, TX=7.5MB → AP present ✅
    C3 e1-2: 1G full, RX=2.6MB, TX=7.5MB → AP present ✅
    D3 e1-2: Auto, RX=0, TX=0 → AP MISSING 🔴

Stadler action: install/connect AP at coach D position 4 to switch D3 port e1-2.

Verdict: 🔴 1 device missing.
Recommended action: P (Partial — proceed with CCU-local fixes, stop before obn update c)
```

**With a missing switch classified via Step 4b** (real data, bench box1-t122, 2026-07-04):

```
─── Device Discovery — bench 4122 (10.179.122.1) ───
Consist:         4-car (nv4)  coaches A, G, E, B

Switches:        🔴 10/12  (A1, B3 absent)
  Classifying absent switches (Step 4b)...
    A1: expected between A3(e0-0) and G1(e0-0).
        A3 e0-0 LLDP→ G1 ✓   G1 e0-0 LLDP→ A3 ✓   (reciprocal, both UP 10G, 0 CRC)
        → COLD BYPASS — A1 powered off/failed in place. NOT a cabling fault.
        → Action: check power/health of A1.
    B3: expected as coach-B end switch, single neighbour B1(e0-0).
        B1 e0-0: link UP 10G, NO LLDP peer, RX crc 2 / TX crc 3 / 60718 RX errors.
        → DEAD LINK — B3 powered off/boot-crashed, or bad B1↔B3 cable.
        → Action: check power/health of B3; if link stays up-no-LLDP after reboot, swap B1↔B3 cable.

Verdict: 🔴 2 switches absent (1 cold_bypass, 1 dead_link) — both single-device power/health, NOT re-cabling.
```

### `--json` mode (subagent consumption)

JSON shape per [.claude/contracts/subagent-report.md](../../contracts/subagent-report.md) `skill_outputs[].raw`:

```json
{
  "skill": "dosto-device-discovery",
  "mode": "check",
  "schema_version": "1",
  "verdict": "missing_aps",
  "raw": {
    "ccu_hostname": "box1-t10",
    "ccu_uptime_seconds": 8520,
    "consist": "6-car",
    "schema": "nv6",
    "expected": {"switches": 18, "aps": 24},
    "actual": {"switches": 18, "aps": 23},
    "switches_present": ["A1", "A2", "A3", "C1", "C2", "C3", "D1", "D2", "D3", "E1", "E2", "E3", "F1", "F2", "F3", "B1", "B2", "B3"],
    "switches_missing": [],
    "ap_count_by_config": {
      "AP1-v1": 3, "AP2-v1": 3, "AP3-v1": 3, "AP4-v1": 2,
      "AP1m-v1": 3, "AP2m-v1": 3, "AP3m-v1": 3, "AP4m-v1": 3
    },
    "ap_missing": [
      {
        "slot": "AP4",
        "config": "AP4-v1",
        "candidate_coaches": ["A", "C", "D"],
        "localised_to_coach": "D",
        "expected_switch": "D3",
        "expected_switch_ip": "10.179.10.193",
        "expected_port": "e1-2",
        "live_state": {"speed": "Auto", "rx_bytes": 0, "tx_bytes": 0, "lldp_peer": null},
        "stadler_instruction": "Install/connect AP at coach D position 4 to switch D3 port e1-2."
      }
    ],
    "ap_extra": [],
    "verdict_severity": "missing_devices_recoverable"
  }
}
```

**`switches_missing[]` entry shape** (one per missing switch, populated by Step 4b). Empty `[]` when all switches present:

```json
"switches_missing": [
  {
    "position": "A1",
    "coach": "A",
    "bypass_status": "cold_bypass",
    "expected_neighbours": {"e0-0": "A3", "e0-1": "G1"},
    "probe": {
      "A3": {"port_toward_x": "e0-0", "lldp_peer": "G1", "link": "up", "speed": "10G", "crc_errors": 0},
      "G1": {"port_toward_x": "e0-0", "lldp_peer": "A3", "link": "up", "speed": "10G", "crc_errors": 0}
    },
    "reciprocal": true,
    "stadler_instruction": "Switch A1 not visible; neighbours A3 and G1 are LLDP-adjacent to each other over a clean 10G link on their expected toward-A1 ports (cold-bypass signature). Most likely A1 is powered off or failed in place — CHECK POWER/HEALTH OF A1 FIRST. If A1 is confirmed powered and healthy, this is instead a bypass-shaped miscable: inspect the A3↔A1 / A1↔G1 cabling."
  }
]
```

`bypass_status` is one of `cold_bypass` | `dead_link` | `link_down` | `miscable` (see Step 4b). It drives whether the instruction says "check power/health" vs "check the cable." A DOWN switch that is cold-bypassed is a *recoverable, single-device* condition — flag it, but it does not by itself mean the consist was re-cabled.

`verdict` is one of:
- `all_present` — counts match expected for both switches and APs
- `missing_aps` — APs short, switches OK (recoverable: partial path is safe)
- `missing_switches` — switches short (severe: localise + escalate, do not proceed)
- `missing_both` — APs AND switches short
- `unexpected_extras` — more devices than expected (rare; stale leases from coupled consist?)

Note: `verdict` still reflects raw counts (a cold-bypassed switch is genuinely missing from the fabric, so `missing_switches` is correct). The **`bypass_status` field is what lets the engineer/orchestrator downgrade the *response*** from "escalate re-cabling to Stadler" to "check power on switch X" — without it, every missing switch reads as a cabling fault, which is the trap this step exists to close.

**The "any device missing" predicate** (consumed by `dosto-commission-train` Stage 1 → Stage 2 routing): a train has missing devices iff `verdict in {"missing_aps", "missing_switches", "missing_both"}` OR `len(raw.ap_missing) > 0` OR `len(raw.switches_missing) > 0`. Belt-and-braces — check the structured arrays, not just the verdict string, in case a future verdict value gets added without an enum update. If ANY of these conditions hold, the caller MUST emit Gate 5 (`device_count_mismatch`) before any consist-wide push.

## What this skill deliberately does NOT do

- ❌ Try to fix anything — discovery is read-only
- ❌ Run consist-wide operations like `obn update c all` (doesn't have permission to)
- ❌ Wait for Stadler — surfaces the issue and lets the orchestrator/human decide
- ❌ Auto-edit fleet-status — emits the data, the orchestrator commits
- ❌ Write cable-issues-register.md — emits structured `ap_missing[]` / `switches_missing[]` arrays; `dosto-orchestrate` Step 7.5 does the append
- ❌ Trust LLDP for AP names (`AP1-v1-...` is the AP's own hostname; correlation to the *switch port hosting it* is via LLDP **on the switch**, not on the AP)

## Validated against

This skill's procedure was validated by running it manually against `10.179.10.1` (Fzg 132, 4736-104) on 2026-05-09. Found:
- 18/18 switches ✅
- 23/24 APs (D4 missing)
- Localised correctly to D3 e1-2 (LLDP confirmed: RX/TX bytes = 0, no peer)
- Topology predictions from `_shared/nv6-topology.md` matched LLDP on every sampled switch (12 of 36 inter-coach trunks sampled, 6 of 24 AP ports sampled, 1 of 1 Stadler firewall trunk)

## Reference

- Topology source: `train-ip-allocation-commission/extracted/_shared/{nv4,nv6}-topology.md`
- Output contract: `.claude/contracts/subagent-report.md` → `skill_outputs[].raw`
- Pairs with: `dosto-obn-patches`, `dosto-vlan7-config` (other diagnostic skills run from `initial_diagnostics`)
- Cable issues land in: `cable-issues-register.md`
- Live state lands in: `fleet-status.md` (orchestrator, sole writer)
