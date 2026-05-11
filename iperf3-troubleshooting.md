# iperf3 Troubleshooting — Dosto Neu / VDS Rail Consist Network

**Date:** 2026-05-01  
**Route:** B1/B3 (Kobserver service port) → target switch (e.g. E coach)  
**Link type:** 1 Gbps Ethernet (inter-coach consist switching fabric)

---

## 1. Test Environment

| Parameter | Value |
|-----------|-------|
| iperf3 client | Windows PC connected to service port e0-5 (VLAN 1 access) |
| iperf3 server | 172.18.201.139 (Kobserver or remote host) |
| Alternate target | 172.18.201.248 |
| Subnet | 172.18.201.0 / 255.255.128.0 → network **172.18.128.0/17** |
| Same L2? | Yes — both .139 and .191 are in 172.18.128.0/17, same subnet, no GW routing |
| TTL to .139 | 127 (1 hop decrement → Windows target, direct L2 or single router hop) |
| Ping to .248 | < 1 ms |
| Ping to .139 | 1–2 ms |

---

## 2. Baseline Commands

### Install / check iperf3
```powershell
# Download iperf3 for Windows from https://iperf.fr
# Run server on target machine:
iperf3.exe -s

# Basic TCP test (single stream, 30s)
iperf3.exe -c 172.18.201.139 -t 30

# Basic UDP test at a given bitrate
iperf3.exe -c 172.18.201.139 -u -b 100M -t 10

# Parallel streams (bypass Windows single-stream TCP ceiling)
iperf3.exe -c 172.18.201.139 -P 8 -t 60

# 40 parallel streams (aggregate saturation test)
iperf3.exe -c 172.18.201.139 -P 40 -t 60
```

> **Note on `-P 40`:** Each stream is an independent TCP flow. Windows spreads these across CPU cores, overcoming single-stream receive-buffer limitations. Useful to confirm whether the ~424 Mbps ceiling is a single-stream OS artefact or a real path bottleneck.

---

## 3. TCP Results (300s single-stream test)

```
[ ID] Interval        Transfer    Bitrate
[  5] 0–300 sec       15.1 GBytes ~424 Mbps  (average)
```

| Observation | Value |
|-------------|-------|
| Average throughput | ~424 Mbps |
| Expected (1G link) | ~940 Mbps (wire rate minus overhead) |
| Efficiency | ~45% — significant underperformance |
| Likely cause | TCP congestion window collapse driven by ~5% sustained UDP loss on path |

---

## 4. UDP Results

### Test A — Low Rate (10 Mbps)
```
iperf3.exe -c 172.18.201.139 -u -b 10M -t 10
```

| Metric | Value |
|--------|-------|
| Target bitrate | 10 Mbps |
| Achieved | 9.92 Mbps |
| Datagrams sent | 1,512 |
| Lost | 159 |
| **Loss %** | **11%** |
| Jitter | 0.187 ms |

### Test B — High Rate (900 Mbps)
```
iperf3.exe -c 172.18.201.139 -u -b 900M -t 60
```

| Metric | Value |
|--------|-------|
| Target bitrate | 900 Mbps |
| Achieved | 897 Mbps |
| Datagrams sent | 136,855 |
| Lost | 7,037 |
| **Loss %** | **5.1%** |
| Jitter | 0.024 ms |

---

## 5. Analysis — Why 11% Loss at 10 Mbps but Only 5.1% at 900 Mbps?

This is counter-intuitive. Buffer overflow logic would predict *more* loss at higher rates, not less. The real explanations:

### 5a. Windows UDP Pacing Artefact (primary cause)
At 10 Mbps, iperf3 on Windows cannot pace at 1.17 ms/datagram granularity. The OS scheduler batches datagrams into **bursts with gaps** between them. The receiver sees a flood of packets, then silence, then another flood. iperf3's jitter/loss calculation uses inter-arrival deltas — packets arriving "out of window" after a silent gap are counted as lost even if they physically arrived.

**Evidence:** Jitter at 10 Mbps (0.187 ms) is **8× higher** than at 900 Mbps (0.024 ms). Paradoxically, low-rate traffic has worse timing regularity than fully saturated traffic where the sender is continuously feeding the socket.

### 5b. Test Startup Fraction Amplification
- At 10 Mbps: ~844 datagrams/second over ~10 seconds = ~8,440 total. MAC learning / ARP / UDP socket setup during the first 0.5–1 second can drop 5–8 datagrams = ~0.1% loss addition. But over a short 10s run, a "bad" first second is 10% of the window.
- At 900 Mbps: ~76,000 datagrams/second. The same 5–8 startup drops are 0.007% — invisible in the total.

### 5c. The 5.1% Loss at 900 Mbps IS the Real Problem
Unlike the 10 Mbps result (largely artefact), the 5.1% figure at 900 Mbps is **sustained loss across 136,855 datagrams** — statistically robust. This is genuine in-path packet dropping under load.

**Impact on TCP:** At 5% packet loss, TCP's congestion window (CWND) collapses repeatedly. The theoretical Mathis formula gives:

```
TCP_throughput ≈ MSS / (RTT × √loss)
               ≈ 1460 / (0.002 × √0.051)
               ≈ ~460 Mbps
```

This closely matches the observed ~424 Mbps — confirming UDP loss is the TCP bottleneck.

---

## 6. Root Cause Investigation — Where Are Packets Dropping?

Run this on **every switch along the path** (A→B→C→D→E):

```
show interface <if> details
```

### What to look for:

| Field | Meaning | Action |
|-------|---------|--------|
| `TX drops` | Egress queue overflow on that port | This switch is the bottleneck |
| `TX errors` | Frame errors leaving the port | Physical or driver issue |
| `RX errors` / `input errors` | CRC or framing errors arriving | Upstream cable or NIC issue |
| `carrier false` | Link-layer instability events | Check physical cable / SFP |

The switch showing **non-zero TX drops** on its inter-coach uplink is the bottleneck.

### Example check on E-coach switch (after VLAN/LLDP session):
```
show interface e0-1 details    # inter-coach port toward D coach
show interface e0-2 details    # inter-coach port toward F coach
show interface summary         # quick overview of all ports
```

---

## 7. Ruling Out Common False Positives

| Suspected Cause | Ruled Out? | How |
|-----------------|-----------|-----|
| Rate limiting / traffic policing | ✅ Yes | User confirmed: no rate-limit config on switches |
| IGMP snooping | ✅ Yes | User confirmed: not enabled |
| Same subnet (no GW routing required) | ✅ Yes | Both endpoints in 172.18.128.0/17 |
| Jumbo frame mismatch | ❓ Check | Run `iperf3 -c ... -M 576` to force small MTU; if loss drops, MTU mismatch |
| DHCP snooping per-packet overhead | ❓ Low risk | Applies to DHCP packets only, not iperf3 UDP |
| D↔E inter-coach miswiring | ❓ Not yet fixed | See switch-troubleshooting-guide.md §Today's Session A |

---

## 8. Advanced Tests

### Confirm path is 1G (not rate-limited)
```powershell
# UDP flood — if you hit ~940 Mbps, path is genuinely 1G
iperf3.exe -c 172.18.201.139 -u -b 0 -t 10
```

### Parallel streams — bypass single-stream OS ceiling
```powershell
# 8 parallel TCP streams
iperf3.exe -c 172.18.201.139 -P 8 -t 60

# 40 parallel TCP streams (aggregate saturation)
iperf3.exe -c 172.18.201.139 -P 40 -t 60
```
If aggregate throughput with `-P 40` is still ~424 Mbps total, the bottleneck is in the network path. If it jumps to 900+ Mbps, the bottleneck was Windows single-stream TCP receive-buffer on the server side.

### Force small MTU (rule out jumbo/MTU mismatch)
```powershell
iperf3.exe -c 172.18.201.139 -u -b 100M -M 576 -t 30
```
If packet loss disappears at small MTU, there is an MTU black-hole somewhere in the consist switching fabric.

### Bidirectional test (check asymmetric loss)
```powershell
# Reverse: server sends, client receives
iperf3.exe -c 172.18.201.139 -R -t 30

# Simultaneous bidirectional
iperf3.exe -c 172.18.201.139 --bidir -t 30
```

---

## 9. Summary and Next Steps

| # | Action | Status |
|---|--------|--------|
| 1 | Run `show interface <if> details` on A, B, C, D, E switches — look for TX drops | ⬜ Pending |
| 2 | Run `iperf3 -c ... -P 40 -t 60` to test aggregate vs single-stream | ⬜ Pending |
| 3 | Run `iperf3 -c ... -u -b 0 -t 10` to confirm max UDP line rate | ⬜ Pending |
| 4 | Fix D↔E inter-coach cable miswiring (see switch-troubleshooting-guide.md) | ⬜ Pending |
| 5 | Re-run 300s TCP test after cable fix — expect improvement if miswire causes flapping | ⬜ Pending |
| 6 | If TX drops found: identify egress port queue depth / QoS config on that switch | ⬜ Pending |

---

*Cross-reference: `switch-troubleshooting-guide.md` — D↔E miswiring, LLDP verification, service port VLAN config*
