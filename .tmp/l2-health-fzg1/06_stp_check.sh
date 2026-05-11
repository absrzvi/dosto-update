#!/bin/bash
# Step 6 — STP root consistency check across all switches.
# Usage: ./06_stp_check.sh <CCU_IP>
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 6 — RSTP root consistency"

vds=$(vds_switch_list "$CCU_IP")
declare -A roots
for sw in $vds; do
  root=$(switch_run "$CCU_IP" "$sw" "show spanning-tree" 2>/dev/null | awk '/Root bridge/{print $4; exit}')
  printf "  %-15s root=%s\n" "$sw" "${root:-?}"
  roots[$root]=$((${roots[$root]:-0}+1))
done

echo
echo "Root distribution:"
for r in "${!roots[@]}"; do
  echo "  $r — ${roots[$r]} switches"
done

if [ "${#roots[@]}" -eq 1 ]; then
  echo "PASS: single, consistent root bridge across the fleet."
else
  echo "FAIL: multiple roots detected — STP topology is unstable. Investigate."
fi
