#!/bin/bash
# Step 4 — full per-port error counter scan across all VDS switches.
# Walks every enabled port, reads RX errors / CRC / carrier-false / collisions.
# Usage: ./04_error_scan.sh <CCU_IP>
# Outputs: a summary table and (if anomalies found) per-port detail lines.
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 4 — Per-port error counter scan"

vds=$(vds_switch_list "$CCU_IP")

# All ports we want to check on each switch.
PORTS="e0-0 e0-1 e0-2 e0-3 e0-4 e0-5 e1-0 e1-1 e1-2 e1-3 e1-4 e1-5 e1-6 e1-7 e1-8 e1-9 e1-10 e1-11 e1-12 e1-13 e1-14 e1-15 e2-0 e2-1 e2-2 e2-3 e2-4 e2-5"

printf "%-15s %-12s %s\n" "Switch" "Status" "Anomalies"
printf "%-15s %-12s %s\n" "------" "------" "---------"

for sw in $vds; do
  summary=$(switch_run "$CCU_IP" "$sw" "show interface summary" 2>/dev/null)
  bad=""
  for p in $PORTS; do
    state=$(echo "$summary" | awk -v p=$p '$1==p{print $3}')
    [ "$state" = "enabled" ] || continue
    d=$(switch_run "$CCU_IP" "$sw" "show interface $p details" 2>/dev/null)
    rx=$(echo "$d"   | sed -nE 's/.*RX errors:([0-9]+).*/\1/p' | head -1)
    crc=$(echo "$d"  | sed -nE 's/.*RX crc errors: ?([0-9]+).*/\1/p' | head -1)
    txc=$(echo "$d"  | sed -nE 's/.*TX crc errors:([0-9]+).*/\1/p' | head -1)
    car=$(echo "$d"  | sed -nE 's/.*carrier false:([0-9]+).*/\1/p' | head -1)
    exc=$(echo "$d"  | sed -nE 's/.*Excessive collisions?:([0-9]+).*/\1/p' | head -1)
    total=$((${rx:-0}+${crc:-0}+${txc:-0}+${car:-0}+${exc:-0}))
    if [ "$total" -gt 0 ]; then
      bad="$bad $p(rx=${rx:-0},crc=${crc:-0},carr=${car:-0})"
    fi
  done
  printf "%-15s %-12s %s\n" "$sw" "scanned" "${bad:-clean}"
done
