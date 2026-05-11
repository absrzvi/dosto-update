#!/bin/bash
# Step 7 — live throughput sampling on inter-coach trunks and Stadler FW trunk.
# Two snapshots N seconds apart; rates derived as (delta_bytes * 8) / interval.
# Usage: ./07_throughput.sh <CCU_IP> [interval_seconds, default 30]
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP> [interval_seconds]}"
INTERVAL="${2:-30}"

section "Step 7 — Throughput sampling (interval ${INTERVAL}s)"

vds=$(vds_switch_list "$CCU_IP")

snapshot() {
  local label="$1"
  for sw in $vds; do
    for p in e0-0 e0-1 e0-4; do
      d=$(switch_run "$CCU_IP" "$sw" "show interface $p details" 2>/dev/null)
      rx=$(echo "$d" | awk '/RX bytes:/{print $2; exit}' | sed 's/[A-Za-z:]//g')
      tx=$(echo "$d" | awk '/TX bytes:/{print $2; exit}' | sed 's/[A-Za-z:]//g')
      echo "$label $sw $p $rx $tx"
    done
  done
}

ts1=$(date +%s)
snap1=$(snapshot S1)
sleep "$INTERVAL"
ts2=$(date +%s)
snap2=$(snapshot S2)

dt=$((ts2 - ts1))
echo "Sample window: ${dt}s"
echo

paste <(echo "$snap1") <(echo "$snap2") | awk -v dt=$dt '
  {
    sw=$2; p=$3; rx1=$4+0; tx1=$5+0; rx2=$9+0; tx2=$10+0
    rxbps=(rx2-rx1)*8/dt; txbps=(tx2-tx1)*8/dt
    printf "  %-15s %-5s  RX %7.2f Mbps   TX %7.2f Mbps   Sum %7.2f Mbps\n", sw, p, rxbps/1e6, txbps/1e6, (rxbps+txbps)/1e6
    if (p=="e0-0") { e00 += rxbps+txbps }
    if (p=="e0-1") { e01 += rxbps+txbps }
    if (p=="e0-4") { e04 += rxbps+txbps }
  }
  END {
    print ""
    printf "Aggregate (port-sum, double-counts multi-hop): e0-0 %.1f Mbps, e0-1 %.1f Mbps, e0-4 %.1f Mbps\n", e00/1e6, e01/1e6, e04/1e6
  }
'
