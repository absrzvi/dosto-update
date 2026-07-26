---
name: dosto-l2-health
description: Run a Layer-2 network health check on a Stadler DOSTO trainset by SSHing into its Nomad CCU, sweeping the VDS Rail consist switches on vlan100, and checking error counters, STP topology, trunk states, and end-to-end Stadler firewall reachability. Use whenever the user wants to assess network health on a DOSTO train, mentions a CCU IP, asks for a packet-loss investigation on a train, says things like "check the L2 fabric on this train", "run a health check on Fzg. NNN", "is this train's network healthy", "/dosto-l2-health", or whenever a CCU jumpbox like box1-tNN comes up in the context of a network problem. Produces a console-formatted report and saves a findings.json file that the dosto-l2-report skill can later turn into a docx report. Don't reinvent the procedure ad-hoc — this skill captures the validated playbook so results are repeatable across trains.
---

# DOSTO L2 Network Health Check

This skill runs the standard Nomad Digital L2 network health check on a DOSTO trainset. The methodology is documented in `CLAUDE.md` at the project root — read it for the architecture background. This skill encodes the runnable procedure.

## When you use this skill

The user has access to a DOSTO trainset's Nomad CCU and wants to know whether the on-board Layer-2 network is healthy. Typical triggers:

- "Run an L2 health check on the train at 10.179.X.1"
- "Is the network on Fzg. 146 healthy?"
- "Check the consist switches on this train"
- "/dosto-l2-health 10.179.8.1"
- After connecting to a CCU and noticing something looks off

## What you produce

Two artefacts:

1. **A console report** — colour-free Markdown tables the user reads in the chat. Headline verdict, per-trunk status, error counters, STP root, throughput, end-to-end reachability.
2. **A `findings.json` file** — saved to the project root (or a path the user specifies). Structured data the `dosto-l2-report` skill picks up later to generate a Word document.

## Inputs you need

Before running, confirm or gather:

| Input | Where it comes from |
|-------|---------------------|
| **CCU IP** | User provides, e.g., `10.179.8.1`. If they only say "this train", ask. |
| **SSH key** | Default: `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh`. If missing, ask. |
| **Switch admin password** | Default: `Nom@dCome1n`. Don't print to the console; pass via `sshpass`. |
| **Fzg. ID / number** | Optional. If the user has the matching IPv4 schema PDF, ask for it — useful for mapping switch IPs to schema IDs. If not provided, the skill still works; switches are identified by config fingerprint instead. |

If the user says "use the project defaults", assume the SSH key path and password above.

## Modes — `--stadler-trunks-only`

The full check (default) runs all 9 steps and takes ~5–10 min on a 6-car consist (sweeps every port on every switch). For the auto-scanner's Tier-2 use case (per [auto-scanner-boundary.md](../../contracts/auto-scanner-boundary.md)) the heavy fabric-wide sweep is overkill — only Stadler-facing trunks matter for cabling-fault detection.

`--stadler-trunks-only` is a scoped mode that runs **only the steps relevant to Stadler-facing trunk health**:

| Step | Default | `--stadler-trunks-only` |
|---|---|---|
| 1. Connectivity sanity | ✅ | ✅ |
| 2. Discover switches | ✅ | ✅ |
| 3. Identify special switches by fingerprint | ✅ | ✅ — only A3, B1, B3, D1, D3 needed |
| 4. Per-port error scan, all switches | ✅ | ❌ skipped |
| 5. Stadler-facing trunks (A3 e1-4, D1/D3 e0-2/e0-3, B1/B3 e1-11) | ✅ | ✅ |
| 6. STP topology check | ✅ | ❌ skipped |
| 7. Live throughput sample | ✅ | ❌ skipped |
| 8. End-to-end CCU↔Stadler firewall | ✅ | ✅ |
| 9. Aggregate findings.json | ✅ | ✅ — partial schema (only Stadler-trunk + FW-reach blocks populated; other blocks `null`) |

Wall time on `--stadler-trunks-only`: ~30–60 seconds. Output is a strict subset of the full findings.json — consumers (the auto-scanner classifier in particular) read only the populated blocks. The `dosto-l2-report` skill rejects partial findings.json (the customer report needs the full sweep).

The scoped mode is **read-only against switches** like the full mode — no destructive ops, no approval gates. Safe for unattended invocation by the auto-scanner.

## How to run the check

Run the steps in order. Each step has a script under `scripts/`. The scripts are designed to be re-run independently if a step fails — they don't depend on shared shell state, only on command-line arguments.

### Step 1 — Connectivity sanity check

Verify SSH to the CCU works, identify the CCU hostname, and read its vlan100 address.

```bash
bash scripts/01_ccu_probe.sh <CCU_IP>
```

Expected output: hostname, vlan100 subnet, list of routed VLANs. If SSH fails, stop and report — there is no point continuing.

### Step 2 — Discover consist switches

Sweep the management VLAN, identify VDS switches by OUI `a0:59:3a` and Westermo radios by OUI `00:14:5a`.

```bash
bash scripts/02_discover.sh <CCU_IP>
```

Outputs a sorted IP list of VDS switches and a Westermo count. Sanity-check the VDS count: 12 for a 4-car, 18 for a 6-car. If the count is unexpected, flag it but proceed.

### Step 3 — Identify special switches by fingerprint

Switches don't expose a hostname; identify A3 (Stadler firewall), B1/B3 (ZFR), D1/D3 (OBS+RDC) by which trunks/access ports they have configured.

```bash
bash scripts/03_fingerprint.sh <CCU_IP>
```

This produces a mapping from live IP to schema role. Save it — Step 5 uses it.

### Step 4 — Per-port error scan across all switches

The big sweep: walk every enabled port on every switch, read RX errors, CRC, carrier-false, collisions. This is the single most important step — it is where physical-layer faults become visible.

```bash
bash scripts/04_error_scan.sh <CCU_IP>
```

This takes a few minutes (≈ 18 switches × 28 ports × ~0.5s/port). Run it in the background and check on it later. The output highlights any port with non-zero error counters.

### Step 5 — Stadler-facing trunks and ZFR

Detail-level inspection of the trunks that matter most: A3 e1-4 (firewall), D1/D3 e0-2 (OBS), D1/D3 e0-3 (RDC), B1/B3 e1-11 (ZFR), front couplers.

```bash
bash scripts/05_critical_trunks.sh <CCU_IP>
```

### Step 6 — STP topology check

Confirm a single, stable RSTP root across the fleet.

```bash
bash scripts/06_stp_check.sh <CCU_IP>
```

### Step 7 — Live throughput sample

Two byte-counter snapshots, configurable interval (default 30 s), to derive utilisation on inter-coach trunks and the Stadler FW trunk.

```bash
bash scripts/07_throughput.sh <CCU_IP> [interval_seconds]
```

### Step 8 — End-to-end CCU↔Stadler firewall

Three orthogonal checks per [CLAUDE.md Phase 6](../../../CLAUDE.md) (rewritten 2026-05-11 per audit finding F9):

- **Q1 path health:** ARP REACHABLE on vlan7 to the FW peer — `172.19.X.1` for even Fzg, `172.19.X.129` for odd Fzg (`FW octet4 = 128*(Fzg%2)+1`; probing `.1` on an odd-Fzg train false-classifies as path_broken — field-verified 2026-07-09 on Fzg 231 / box1-t41, FW at `172.19.243.129`) — link counters clean
- **Q2 FW commission state:** ICMP — **0 replies = commissioned (Stadler policy dropping ping), replies received = NOT commissioned (bare Westermo defaults).** This is the deciding test, not TCP.
- **Q3 service availability:** TCP probes — informational only; CANNOT classify commission state by themselves (a default-config Westermo also has 80/22 OPEN).

```bash
bash scripts/08_e2e_probe.sh <CCU_IP> <FW_IP>   # ALWAYS pass FW_IP — the script's default (172.19.196.1) is wrong for most trains
```

Step 8's `findings.json` block MUST include the derived `fw_commission_state`:

```json
"fw_reach": {
  "fw_peer_ip": "172.19.X.1",              // even Fzg → .1, odd Fzg → .129 (FW octet4 = 128*(Fzg%2)+1)
  "arp_state": "reachable|stale|failed|none",
  "fw_peer_mac": "00:90:e8:...",          // Westermo OUI if present
  "icmp_sent": 5,
  "icmp_replies": 0,                       // 0 with arp reachable = commissioned
  "tcp80": "open|filtered|refused|timeout",
  "tcp22": "open|filtered|refused|timeout",
  "fw_commission_state": "commissioned|uncommissioned|path_broken|unknown"
}
```

Derivation rule (must be applied in Step 9 aggregator):

| ARP state | ICMP replies | → `fw_commission_state` |
|---|---|---|
| `reachable` (or `stale`) | 0 | `commissioned` |
| `reachable` (or `stale`) | > 0 | `uncommissioned` |
| `failed` / `none` | (any) | `path_broken` |
| — | not tested | `unknown` (don't emit a customer verdict) |

**Customer report implication:** the `dosto-l2-report` skill must read `fw_commission_state` and present `uncommissioned` as a Stadler-action item, NOT as a Nomad-side fault. Reporting `tcp80=open` alone as ✅ is incorrect and produces wrong customer classifications.

### Step 9 — Aggregate and write findings.json

The wrap-up step. Reads outputs from steps 1–8, normalises them, and writes one structured JSON file the report skill consumes.

```bash
bash scripts/09_aggregate.sh <CCU_IP> <output_path>
```

Default `output_path`: `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/findings_<CCU_IP>_<timestamp>.json`.

## How to interpret results

The skill follows the same green/yellow/red convention from CLAUDE.md.

**Green (no action):**
- All ports zero on RX errors, CRC, carrier-false
- Single STP root, all switches agree
- Inter-coach trunks at expected speed (10 G or 1 G)
- ICMP to FW = 100% loss BUT TCP probe succeeds AND vlan7 counters clean (FW filters ICMP — design)
- Front coupler trunks DOWN with consist solo
- ZFR-B3 RX = 0 (standby member of redundant pair)

**Yellow (note, don't escalate):**
- Single-digit RX errors over millions of packets — noise
- RDC trunk near-idle — usually fine, ask ÖBB whether RDC was supposed to be active
- Firmware version differences across switches — fleet-management note

**Red (escalate):**
- Sustained CRC errors (any) — physical layer fault
- Sustained carrier-false events — link instability, surge events, vibration
- Pause frames received — egress queue overflow upstream
- Multiple STP roots or root flapping — topology unstable
- Inter-coach trunk speed degraded vs. schema (e.g., 1 G when 10 G expected)
- Inter-coach utilisation > 70% sustained
- TCP probe to FW fails AND vlan7 has drops — actual broken path
- Any non-zero error counter that grows between repeated checks

## Output format for the chat

Always end with a verdict block that looks like this:

```
## Verdict
**OVERALL: HEALTHY | NEEDS ATTENTION | DEGRADED**

Findings saved to: <path to findings.json>

Headline metrics:
- Switches reachable:    18 / 18
- Trunks UP at expected speed: 16 / 16 (excluding end-of-train)
- Per-port error counters non-zero: 0
- STP root consistent across fleet: yes
- FW trunk utilisation: X.X %
- CCU↔FW TCP reachability: OK | FAILED

Recommended next step: <one sentence>
```

If the verdict is anything other than HEALTHY, list the specific findings that drove it.

## Pitfalls and quirks

- **VDS switch CLI does not accept `;` chaining.** One command per SSH session. Loop in shell.
- **Switches require legacy SSH algorithms** — the scripts already include the right `KexAlgorithms` and `HostKeyAlgorithms` flags.
- **Train cellular networks drop frequently.** Long-running steps (Step 4, Step 7) should be run as background jobs. If they fail mid-way, just rerun.
- **Stadler firewall commission state is decided by ICMP, NOT TCP.** A commissioned FW drops echo-request (Stadler policy); an uncommissioned/default Westermo FW replies to ping AND has TCP 80/22 OPEN by default. Reading `tcp80=OPEN` as ✅ is **wrong** when ICMP also replies — that's the bare-defaults case, not a commissioned FW. See [CLAUDE.md Phase 6](../../../CLAUDE.md) for the full three-question framework.
- **Cumulative byte counters reset on switch reboot** — to convert "X TB since boot" into a useful metric, also read uptime if possible.
- **Stadler-side device VLANs are not visible from the CCU.** This skill only checks what the CCU and management VLAN can see. If the user reports a problem on a Stadler-side device (camera, AFZ, intercom), this skill cannot diagnose it directly.

## Switch CLI commands

A curated reference of the VDS switch commands this skill uses lives at `references/vds-cli-commands.md`. **Read that file when you need exact CLI syntax** — it is the focused subset that matters for L2 diagnostics, with parsing tips for each output. Don't grep through the full 12,000-line `docs/switch_user_manual.pdf` unless you need a command not listed there (which would be unusual for a health check).

The shell scripts under `scripts/` already wrap the commands correctly — including the legacy SSH algorithm flags and the one-command-per-session constraint — so for the standard flow you do not need to construct CLI calls by hand. Consult the reference when an unusual finding requires a follow-up command not in the standard flow.

## Project context

The project root is `C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/`. It contains:

- `CLAUDE.md` — methodology and playbook reference (root)
- `openssh` — SSH key for CCU access (root)
- `docs/switch_user_manual.pdf` — VDS Consist Switch user manual (full reference, 250 pages)
- `docs/ND-DEL-OBB-035-IPA-NNN_NV_*.pdf` — IPv4 schema PDFs, one per train (Fzg. NNN)

If any of these are missing, ask the user before assuming defaults.
