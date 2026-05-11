# L2 Network Health Check Report
**Train:** Fzg 133 / 4736-105 (6-car DOSTO)  
**CCU:** `10.179.1.1` (`box1-t1`)  
**Date:** 2026-05-05  
**Engineer:** Abbas Rizvi / Nomad Digital  
**OBN Package:** `nd-obn-template-dostoneu-nv6` v0.0.19 / `nd-obn` v2.2.23  

---

## Verdict

**OVERALL: NEEDS ATTENTION**

The L2 fabric is **structurally healthy** — all 18 switches are reachable, all inter-coach trunks are UP at 10G full-duplex, STP has a single stable root, and all error counters are zero. Two issues require follow-up:

1. **Coach 5 AP2 missing from the network** — not visible via OBN discover or ARP. This AP has never appeared since commissioning began. **Stadler must perform a physical cable/patch check on the AP2 port in coach 5.**
2. **Stadler firewall (172.19.196.1) unreachable** — TCP probes on port 80 and 22 both return "No route to host". The vlan7 interface on the CCU is UP with clean counters, indicating the fault is on the Stadler side (gateway powered off or not yet commissioned for this train).

---

## Headline Metrics

| Metric | Value |
|--------|-------|
| Switches reachable | 18 / 18 |
| Switches on v8-133 config | 18 / 18 ✓ |
| Switches on firmware 7.4.2 | 18 / 18 ✓ |
| Inter-coach trunks UP at 10G full | 16 / 16 active ✓ |
| Per-port error counters non-zero | 0 / 36 trunks checked ✓ |
| STP root consistent across fleet | Yes — single root ✓ |
| APs visible | 20 / 21 |
| APs on firmware 6.11.2-0 | 20 / 20 visible ✓ |
| Stadler FW (172.19.196.1) TCP reachability | **FAILED** ✗ |
| Coach 5 AP2 | **MISSING** ✗ |

---

## 1. Switch Overview (OBN Validate)

All 18 switches confirmed on correct config and firmware at time of check:

| Coach | Device | IP | Firmware | Config |
|-------|--------|----|----------|--------|
| 1 | 1 (A1) | 10.179.1.201 | 7.4.2 ✓ | nv6-A1-v8-133 ✓ |
| 1 | 2 (A2) | 10.179.1.192 | 7.4.2 ✓ | nv6-A2-v8-133 ✓ |
| 1 | 3 (A3) | 10.179.1.191 | 7.4.2 ✓ | nv6-A3-v8-133 ✓ |
| 2 | 1 (C1) | 10.179.1.200 | 7.4.2 ✓ | nv6-C1-v8-133 ✓ |
| 2 | 2 (C2) | 10.179.1.197 | 7.4.2 ✓ | nv6-C2-v8-133 ✓ |
| 2 | 3 (C3) | 10.179.1.205 | 7.4.2 ✓ | nv6-C3-v8-133 ✓ |
| 3 | 1 (D1) | 10.179.1.186 | 7.4.2 ✓ | nv6-D1-v8-133 ✓ |
| 3 | 2 (D2) | 10.179.1.184 | 7.4.2 ✓ | nv6-D2-v8-133 ✓ |
| 3 | 3 (D3) | 10.179.1.208 | 7.4.2 ✓ | nv6-D3-v8-133 ✓ |
| 4 | 1 (E1) | 10.179.1.207 | 7.4.2 ✓ | nv6-E1-v8-133 ✓ |
| 4 | 2 (E2) | 10.179.1.203 | 7.4.2 ✓ | nv6-E2-v8-133 ✓ |
| 4 | 3 (E3) | 10.179.1.202 | 7.4.2 ✓ | nv6-E3-v8-133 ✓ |
| 5 | 1 (F1) | 10.179.1.204 | 7.4.2 ✓ | nv6-F1-v8-133 ✓ |
| 5 | 2 (F2) | 10.179.1.178 | 7.4.2 ✓ | nv6-F2-v8-133 ✓ |
| 5 | 3 (F3) | 10.179.1.193 | 7.4.2 ✓ | nv6-F3-v8-133 ✓ |
| 6 | 1 (B1) | 10.179.1.206 | 7.4.2 ✓ | nv6-B1-v8-133 ✓ |
| 6 | 2 (B2) | 10.179.1.188 | 7.4.2 ✓ | nv6-B2-v8-133 ✓ |
| 6 | 3 (B3) | 10.179.1.198 | 7.4.2 ✓ | nv6-B3-v8-133 ✓ |

---

## 2. STP Topology

**Result: HEALTHY — single root, stable**

| Switch | IP | Bridge Priority | Role |
|--------|----|-----------------|------|
| D1 | 10.179.1.186 | **0** | **STP ROOT** |
| D3 | 10.179.1.208 | 4096 | Non-root |
| All others | — | 32768 | Non-root |

Single RSTP root at `10.179.1.186` (D1, MAC `a0:59:3a:d0:6c:80`). All 18 switches agree on the same root. No TCN events observed during the check window.

---

## 3. Inter-Coach Trunk Error Scan

**Result: CLEAN — all counters zero**

Checked `e0-0` and `e0-1` on all 18 switches (36 trunk ports total):

| Counter | Result |
|---------|--------|
| RX errors | 0 on all 36 ports |
| RX CRC errors | 0 on all 36 ports |
| Carrier false events | 0 on all 36 ports |
| Pause frames received | 0 on all 36 ports |
| Collisions / late collisions | 0 on all 36 ports |

No physical-layer faults detected on any inter-coach trunk.

---

## 4. Critical Stadler-Facing Trunks

### A3 (10.179.1.191) — Stadler Firewall Trunk

Identified by trunk fingerprint: has `e0-0`, `e0-1`, `e0-2` (front coupler), `e0-4` (AP), `e1-2`, `e1-4` (FW trunk), `e2-5`.

| Port | Speed | State | Notes |
|------|-------|-------|-------|
| e1-4 | 1G | UP full-duplex ✓ | Stadler FW trunk — link UP |
| e0-2 | 10G | enabled, **DOWN** | Front coupler — train solo, expected |

e1-4 link is UP at 1G. However the Stadler FW at the far end (`172.19.196.1`) is not responding — see Section 6.

### D1 (10.179.1.186) — OBS + RDC Trunks

| Port | Speed | State | Notes |
|------|-------|-------|-------|
| e0-2 | 10G | UP full-duplex ✓ | OBS trunk |
| e0-3 | 10G | UP full-duplex ✓ | RDC trunk |
| e0-0 | 10G | UP full-duplex ✓ | Inter-coach |
| e0-1 | 10G | UP full-duplex ✓ | Inter-coach |

### D3 (10.179.1.208) — OBS + RDC Trunks

| Port | Speed | State | Notes |
|------|-------|-------|-------|
| e0-2 | 10G | UP full-duplex ✓ | OBS trunk |
| e0-3 | 10G | UP full-duplex ✓ | RDC trunk |

### B1 (10.179.1.206) — ZFR Primary

Identified by `e1-11` UP at 1G (ZFR access port) and `e1-4` UP (FW path).

| Port | Speed | State | Notes |
|------|-------|-------|-------|
| e1-11 | 1G | UP full-duplex ✓ | ZFR primary — active |
| e0-2 | 10G | enabled, DOWN | Front coupler — train solo, expected |

### B3 (10.179.1.198) — ZFR Standby

Identified by `e1-11` UP at 1G and `e2-5` trunk.

| Port | Speed | State | Notes |
|------|-------|-------|-------|
| e1-11 | 1G | UP full-duplex ✓ | ZFR standby — RX=0 expected |

ZFR redundant pair (B1 primary, B3 standby) both show e1-11 UP. B3 RX=0 is normal — it shares one IP with B1 and is silent while B1 is active.

---

## 5. Inter-Coach Throughput (30s sample window)

Snapshot interval: ~480s effective (sequential sweep + 30s sleep).

| Switch | Port | Δ bytes | Rate (Mbps) | Utilisation (10G) |
|--------|------|---------|-------------|-------------------|
| 10.179.1.201 (A1) | e0-0 | 490,925,854 | ~8.2 | 0.08% |
| 10.179.1.201 (A1) | e0-1 | 425,445,080 | ~7.1 | 0.07% |
| 10.179.1.192 (A2) | e0-0 | 459,857,989 | ~7.7 | 0.08% |
| 10.179.1.192 (A2) | e0-1 | 691,319,506 | ~11.5 | 0.12% |
| 10.179.1.191 (A3) | e0-0 | 505,697,966 | ~8.4 | 0.08% |
| 10.179.1.191 (A3) | e0-1 | 489,725,871 | ~8.2 | 0.08% |
| 10.179.1.200 (C1) | e0-0 | 547,613,814 | ~9.1 | 0.09% |
| 10.179.1.200 (C1) | e0-1 | 349,167,041 | ~5.8 | 0.06% |
| 10.179.1.186 (D1) | e0-0 | 600,658,157 | ~10.0 | 0.10% |
| 10.179.1.186 (D1) | e0-1 | 269,287,212 | ~4.5 | 0.05% |
| 10.179.1.208 (D3) | e0-0 | 9,289,114 | ~0.15 | <0.01% |
| 10.179.1.208 (D3) | e0-1 | 554,931,885 | ~9.3 | 0.09% |
| 10.179.1.206 (B1) | e0-0 | 163,039 | ~0.003 | <0.01% |
| 10.179.1.206 (B1) | e0-1 | 2,404,782 | ~0.04 | <0.01% |
| 10.179.1.198 (B3) | e0-0 | 4,563 | ~0.0001 | <0.01% |
| 10.179.1.198 (B3) | e0-1 | 3,076,722 | ~0.05 | <0.01% |

**Summary:** Peak inter-coach trunk utilisation ~11.5 Mbps / 0.12% of 10G capacity. Train was lightly loaded during check. All trunks well within capacity. No congestion risk.

---

## 6. Stadler Firewall Reachability (vlan7 / 172.19.196.1)

**Result: UNREACHABLE — action required by Stadler**

| Test | Result |
|------|--------|
| vlan7 interface state | UP, no errors, no drops ✓ |
| ARP for 172.19.196.1 | **Not resolved** (only 172.19.192.130 in neigh table) |
| TCP port 80 | `No route to host` ✗ |
| TCP port 22 | `No route to host` ✗ |

The CCU-side vlan7 interface is healthy (RX: 146,510 pkts, TX: 25 pkts, 0 errors). The fault is on the Stadler side — the gateway `172.19.196.1` is either powered off, not yet commissioned, or the vlan7 cable/SFP is not connected on the Stadler firewall. This needs to be raised with Stadler.

> **Note:** ICMP to `172.19.196.1` was not tested separately — `No route to host` from TCP probes indicates the path is absent entirely, not just ICMP-filtered.

---

## 7. Access Point Overview

**Result: 20/21 visible — Coach 5 AP2 MISSING (action required)**

| Coach | Device | IP | Firmware | Config |
|-------|--------|----|----------|--------|
| 1 | AP1 | 10.179.1.236 | 6.11.2-0 ✓ | AP1-v1 ✓ |
| 1 | AP2 | 10.179.1.238 | 6.11.2-0 ✓ | AP2-v1 ✓ |
| 1 | AP3 | 10.179.1.234 | 6.11.2-0 ✓ | AP3-v1 ✓ |
| 1 | AP4 | 10.179.1.229 | 6.11.2-0 ✓ | AP4-v1 ✓ |
| 2 | AP1 | 10.179.1.224 | 6.11.2-0 ✓ | AP1-v1 ✓ |
| 2 | AP2 | 10.179.1.235 | 6.11.2-0 ✓ | AP2-v1 ✓ |
| 2 | AP3 | 10.179.1.231 | 6.11.2-0 ✓ | AP3-v1 ✓ |
| 2 | AP4 | 10.179.1.227 | 6.11.2-0 ✓ | AP4-v1 ✓ |
| 3 | AP1 | 10.179.1.222 | 6.11.2-0 ✓ | AP1-v1 ✓ |
| 3 | AP2 | 10.179.1.240 | 6.11.2-0 ✓ | AP2-v1 ✓ |
| 3 | AP3 | 10.179.1.232 | 6.11.2-0 ✓ | AP3-v1 ✓ |
| 3 | AP4 | 10.179.1.230 | 6.11.2-0 ✓ | AP4-v1 ✓ |
| 4 | AP1 | 10.179.1.225 | 6.11.2-0 ✓ | AP1m-v1 ✓ |
| 4 | AP2 | 10.179.1.218 | 6.11.2-0 ✓ | AP2m-v1 ✓ |
| 4 | AP3 | 10.179.1.221 | 6.11.2-0 ✓ | AP3m-v1 ✓ |
| 4 | AP4 | 10.179.1.239 | 6.11.2-0 ✓ | AP4m-v1 ✓ |
| 5 | AP1 | 10.179.1.220 | 6.11.2-0 ✓ | AP1m-v1 ✓ |
| **5** | **AP2** | **—** | **—** | **MISSING ✗** |
| 5 | AP3 | 10.179.1.233 | 6.11.2-0 ✓ | AP3m-v1 ✓ |
| 5 | AP4 | 10.179.1.228 | 6.11.2-0 ✓ | AP4m-v1 ✓ |
| 6 | AP1 | 10.179.1.219 | 6.11.2-0 ✓ | AP1m-v1 ✓ |
| 6 | AP2 | 10.179.1.226 | 6.11.2-0 ✓ | AP2m-v1 ✓ |
| 6 | AP3 | 10.179.1.223 | 6.11.2-0 ✓ | AP3m-v1 ✓ |
| 6 | AP4 | 10.179.1.237 | 6.11.2-0 ✓ | AP4m-v1 ✓ |

### ⚠ Coach 5 AP2 — ACTION REQUIRED: Stadler Cable Check

Coach 5 AP2 is completely absent from the network. It does not appear in:
- OBN discover (management VLAN sweep)
- ARP table on the CCU
- Default factory IP range (192.168.x.x) — checked separately during commissioning

The AP is not reachable in any known state. This is a **physical layer issue** — the AP is either not connected to its switch port (e0-4 on the F-car switch) or the patch cable between the AP and the switch is faulty or missing.

**Action required:** Stadler must physically inspect the AP2 installation in coach 5 (F-car). Check:
1. Cable connection at the AP2 port
2. Patch cable from AP2 to the switch e0-4 port on the F-car FIS unit
3. Whether the AP unit itself is powered and physically present

All other 20 APs are healthy and correctly configured.

---

## 8. CCU Software State

| Item | Value |
|------|-------|
| Active btrfs snapshot | run1 (gen 149710) |
| nd-obn version | 2.2.23 |
| nd-obn-template-dostoneu-nv6 | 0.0.19 (latest available) |
| train_id in .cfg templates | 133 (hardcoded, persistent) ✓ |
| CCU IP | 10.179.1.1 (stable) ✓ |
| AP config version | v1 (v7 not yet available in repo) |

---

## 9. Open Items / Action Required

| Priority | Item | Owner |
|----------|------|-------|
| **HIGH** | Coach 5 AP2 completely missing — physical cable/patch check required on F-car AP2 switch port (e0-4) | **Stadler** |
| **HIGH** | Stadler FW (172.19.196.1) unreachable via TCP — vlan7 path absent, gateway not responding | **Stadler** |
| LOW | AP config v7 not yet in package repo — APs remain on v1. No functional impact. Update when `nd-obn-template-dostoneu-nv6` ≥ 0.0.20 ships. | Nomad (future) |

---

## 10. Notes

- This check was performed after completing the OBN v8-133 config push for all 18 switches (completed 2026-05-04/05). The train is fully commissioned from an OBN perspective.
- The CCU train_id was permanently hardcoded to `133` in all 18 `/etc/obn/template/nv6-*.cfg` files to prevent subnet drift on reboot.
- Front coupler trunks (e0-2 on A1/A3/B1/B3) are enabled but link-DOWN — this is expected as the train is running as a solo consist.
- C3 switch (10.179.1.205) e1-4 port is disabled/down — this is the expected state for C3 (not a Stadler FW or ZFR switch).
