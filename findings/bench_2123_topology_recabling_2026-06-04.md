# OEBB Bench 2123 — topology fault analysis & re-cabling worklist

**Date:** 2026-06-04
**CCU:** box1-t123 (`10.179.123.1`) — OEBB-251 bench, config **v3 / train_id 251**
**Method:** live LLDP sweep of all 6 VDS switches + Zabbix host inventory; compared against the intended NMS topology diagram and a live commissioned 4-wagon train (Fzg 21 / 4734-121, `10.179.50.1`).
**Diagram:** [trackers/topology_2123_bench.svg](../trackers/topology_2123_bench.svg) (corrected target)

---

## Context — why this came up

The bench rendered all-red / "Last online: Unknown" in the NMS. **Root cause of the NMS gap was a Zabbix proxy mis-assignment on the sibling 4122 bench** (separate issue, fixed). On 2123 the monitoring chain is healthy (all 8 hosts fresh, on live proxy `dostoneu-bench-zproxy-2123a`/12608) — but inspecting the topology revealed the **physical wiring is wrong** vs. the intended bench design.

---

## Switch inventory (live, DHCP + LLDP)

| Switch | IP | MAC | Config |
|---|---|---|---|
| A1 | .186 | `a0:59:3a:d0:62:60` | 2t-A1-v3-251 |
| A2 | .181 | `a0:59:3a:d0:56:20` | 2t-A2-v3-251 |
| A3 | .179 | `a0:59:3a:d0:56:00` | 2t-A3-v3-251 |
| B1 | .183 | `a0:59:3a:d0:3c:00` | 2t-B1-v3-251 |
| B2 | .182 | `a0:59:3a:d0:3c:20` | 2t-B2-v3-251 |
| B3 | .178 | `a0:59:3a:d0:5b:a0` | 2t-B3-v3-251 |

CCU box1-t123 MAC `7c:70:bc:70:d4:f4`. **No Westermo APs connected** (all `e0-4` down except the B2↔B3 jumper). The four `50_2123_R2_AP*` Zabbix hosts have no live hardware.

---

## Intended topology (per NMS diagram + final CCU decision)

- **A ring (intra-coach):** A1 ↔ A3, A3 ↔ A2
- **B ring (intra-coach):** B2 ↔ B3, B3 ↔ B1
- **Inter-coach:** **A1 ↔ B2** (top), **A2 ↔ B1** (bottom)
- **CCU:** A2 **e0-3** (dedicated access port)
- **APs:** AP-A1→A1, AP-A2→A2, AP-A3→A3 e0-4, AP-A4→A3 e1-2; AP-B1→B1, AP-B2→B2, AP-B3→B3 e0-4, AP-B4→B3 e1-2

---

## Live state vs. intended

| Link | Intended | Live (actual) | OK? |
|---|---|---|---|
| A1 e0-0 ↔ A3 | A3 | A3 (`…56:00`) | ✅ |
| A3 e0-1 ↔ A2 | A2 | A2 (`…56:20`) | ✅ |
| **A1 e0-1 (top inter-coach)** | **B2** | **B1** (`…3c:00`) | ❌ wrong neighbour |
| **A2 e0-1 (bottom inter-coach)** | **B1** | **CCU** (`7c:70:bc…`) | ❌ CCU on trunk port |
| **CCU attach** | **A2 e0-3** | **A2 e0-1** (e0-3 admin-disabled) | ❌ |
| B3 e0-0 ↔ B1 | B1 | B1 (`…3c:00`) | ✅ |
| **B2 in ring (B3 e0-1 ↔ B2)** | real trunk | **B3 e0-4 ↔ B2 e0-4 jumper**; B2 e0-0/e0-1 DOWN | ❌ AP port reused |
| APs (8) | connected | none | ❌ (bench has none) |

---

## Comparison to a real 4-wagon train (Fzg 21 / 4734-121, live)

A real consist order is **A → G → E → B**, so:
- A's inter-coach uplinks go to **G** (Fzg 21: A1 e0-1→G1, A2 e0-1→G3).
- B's inter-coach uplinks go to **E** (Fzg 21: B1 e0-1→E1, B2 e0-1→E3).
- B2 sits properly in the ring (B3 e0-1→B2 trunk).
- All 8 A/B APs live.

The bench has **no G/E coaches**, so it short-loops A directly to B (A1↔B2, A2↔B1) — a valid bench design, but it must use the correct ports. The **intra-coach** rings (A3↔A1, A3↔A2, B3↔B1) match the real train exactly, confirming the bench switches are genuine A/B-coach hardware wired correctly *within* each coach. The faults are confined to the inter-coach links, the CCU port, and B2's jumper.

---

## Re-cabling worklist (current → intended)

| # | Fault | Action |
|---|---|---|
| 1 | CCU on **A2 e0-1** | Move CCU cable to **A2 e0-3**; `enable` A2 e0-2/e0-3 (currently admin-disabled) |
| 2 | **A1 e0-1 → B1** (wrong top link) | Re-patch A1 e0-1 → **B2 e0-1** |
| 3 | A2 e0-1 freed by step 1 | Patch A2 e0-1 → **B1 e0-1** (bottom inter-coach) |
| 4 | **B2** via B3 e0-4 jumper; ring ports DOWN | Pull B3 e0-4 ↔ B2 e0-4 jumper; patch **B3 e0-1 ↔ B2 e0-1** on real trunk ports; re-enable B2 e0-0/e0-1 |
| 5 | No APs | Bench has none — informational only |

**Post-fix verification:** re-run LLDP on all 6 switches and confirm A1 e0-1→B2, A2 e0-1→B1, B3 e0-1→B2, and CCU on A2 e0-3, with B2 e0-0/e0-1 up.

---

## Notes
- Bench is on **v3 / train_id 251**; real fleet trains are at v8. Consistent with the OEBB-251 v4 push that was left mid-flight (see `project_oebb251_bench_v4_push.md`). Re-cabling should happen before/alongside any further config push so head-of-train port-role changes don't isolate the CCU.
- Switch CLI: legacy SSH algos required; one command per session (no `;`-chaining). Admin pw `Nom@dCome1n`.
