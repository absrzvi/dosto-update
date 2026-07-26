#!/bin/bash
# Step 8 — end-to-end CCU ↔ Stadler firewall probe.
# Runs ICMP, ARP, and TCP probes. ICMP is usually filtered; do not call FAIL on ICMP alone.
# Usage: ./08_e2e_probe.sh <CCU_IP> [FW_IP]
# When FW_IP is omitted it is DERIVED LIVE from the CCU's own vlan7 address: the Stadler FW
# is device 1 on the same /17, and the CCU is device 2, so FW = (CCU vlan7 host octet) - 1.
# This is parity-correct without knowing the Fzg: even Fzg -> CCU .2 / FW .1, odd Fzg ->
# CCU .130 / FW .129 (the FW carries the same odd-Fzg +128 bit as the CCU; field-verified
# 2026-07-09 on Fzg 231/box1-t41, FW=172.19.243.129 while .1 was no-route). Pass FW_IP
# explicitly only to override the live derivation.
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP> [FW_IP]}"

if [[ -n "${2:-}" ]]; then
  FW_IP="$2"
else
  # Derive the FW IP from the CCU's live vlan7 address (FW = device 1 = CCU host octet - 1).
  VLAN7_ADDR=$(ccu_run "$CCU_IP" "ip addr show vlan7 2>/dev/null | awk '/inet /{print \$2; exit}'" 2>/dev/null | tr -d '[:space:]')
  if [[ -z "$VLAN7_ADDR" ]]; then
    die "Could not read vlan7 address from CCU $CCU_IP to derive FW IP — pass FW_IP explicitly (172.19.<octet3>.1 even Fzg / .129 odd Fzg)"
  fi
  CCU_VLAN7_IP="${VLAN7_ADDR%/*}"          # strip /17
  o4="${CCU_VLAN7_IP##*.}"                  # CCU host octet (.2 even Fzg / .130 odd Fzg)
  FW_IP="${CCU_VLAN7_IP%.*}.$((o4 - 1))"    # FW = device 1 -> .1 (even) / .129 (odd)
fi

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
