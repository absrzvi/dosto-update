#!/bin/bash
# Step 3 — identify special switches by config fingerprint.
# Hostname is not exposed; identify A3, B1/B3, D1/D3 from configured trunks/access ports.
# Usage: ./03_fingerprint.sh <CCU_IP>
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 3 — Schema fingerprint mapping"

vds=$(vds_switch_list "$CCU_IP")

printf "%-15s  %-45s  %-12s  %-10s  %s\n" "Switch IP" "Trunk ports" "ZFR(VLAN2)" "RDC(e0-3)" "Likely schema role"
printf "%-15s  %-45s  %-12s  %-10s  %s\n" "---------" "-----------" "----------" "---------" "------------------"

for sw in $vds; do
  trunks=$(switch_run "$CCU_IP" "$sw" "show interface trunks" 2>/dev/null | awk 'NR>2 && /^e/{print $1}' | tr '\n' ',' | sed 's/,$//')
  vlans=$(switch_run "$CCU_IP" "$sw" "show vlans" 2>/dev/null)

  zfr="no"
  if echo "$vlans" | awk '/^0002/,/^----/' | grep -q "e1-11"; then zfr="yes"; fi

  rdc="no"
  if echo "$trunks" | grep -q "e0-3"; then rdc="yes"; fi

  has_e14=$(echo "$trunks" | grep -o "e1-4" || echo "")

  role="(generic)"
  [ "$rdc" = "yes" ] && role="D1/D3 (OBS+RDC)"
  [ "$zfr" = "yes" ] && role="B1/B3 (ZFR)"
  [ -n "$has_e14" ] && role="A3 (Stadler firewall)"

  printf "%-15s  %-45s  %-12s  %-10s  %s\n" "$sw" "${trunks:--}" "$zfr" "$rdc" "$role"
done
