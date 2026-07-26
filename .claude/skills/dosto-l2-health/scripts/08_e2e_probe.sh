#!/bin/bash
# Step 8 — end-to-end CCU ↔ Stadler firewall probe.
# Runs ICMP, ARP, and TCP probes. ICMP is usually filtered; do not call FAIL on ICMP alone.
# Usage: ./08_e2e_probe.sh <CCU_IP> [FW_IP, default 172.19.196.1]
# ALWAYS pass FW_IP explicitly: 172.19.<128+Fzg//2>.<128*(Fzg%2)+1>
# (even Fzg -> .1, odd Fzg -> .129 — the FW carries the same odd-Fzg +128 bit
# as the CCU; field-verified 2026-07-09 on Fzg 231/box1-t41, FW=172.19.243.129).
# The default below only matches an even-Fzg train on octet3 196 (Fzg 136/137 -> 136).
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP> [FW_IP]}"
FW_IP="${2:-172.19.196.1}"

section "Step 8 — CCU↔Stadler FW end-to-end probe (FW=$FW_IP)"

ccu_run "$CCU_IP" "
  echo '--- vlan7 interface ---'
  ip -br addr show vlan7 2>&1
  echo
  echo '--- vlan7 counters (errors/drops should be 0) ---'
  ip -s link show vlan7 2>&1 | head -8
  echo
  echo '--- ARP entry for FW ---'
  ip neigh show dev vlan7 | grep $FW_IP || echo 'no ARP entry'
  echo
  echo '--- ICMP (100 packets, expected 100% loss if FW filters ICMP) ---'
  ping -c 100 -i 0.05 -q -W 1 $FW_IP 2>&1 | tail -2
  echo
  echo '--- TCP probes ---'
  for port in 22 80 443; do
    if timeout 3 bash -c \"echo > /dev/tcp/$FW_IP/\$port\" 2>/dev/null; then
      echo \"  TCP/\$port: OPEN\"
    else
      echo \"  TCP/\$port: closed/filtered\"
    fi
  done
"
