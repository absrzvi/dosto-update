#!/bin/bash
# Step 2 — discover VDS switches and Westermo radios on vlan100.
# Usage: ./02_discover.sh <CCU_IP>
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 2 — Discovery on vlan100"

# fping the management VLAN to populate ARP, then read.
ccu_run "$CCU_IP" 'mgmt=$(ip -br addr show vlan100 | awk "{print \$3}" | cut -d/ -f1 | cut -d. -f1-3); fping -a -q -g ${mgmt}.128 ${mgmt}.255 2>/dev/null || true' >/dev/null

vds=$(vds_switch_list "$CCU_IP")
vds_count=$(echo "$vds" | grep -c .)
wes_count=$(westermo_count "$CCU_IP")

echo "VDS Rail consist switches (OUI a0:59:3a): $vds_count found"
echo "$vds" | sed 's/^/  /'
echo
echo "Westermo radios (OUI 00:14:5a): $wes_count found"
echo
case "$vds_count" in
  12) echo "Switch count consistent with a 4-car DOSTO consist." ;;
  18) echo "Switch count consistent with a 6-car DOSTO consist." ;;
  *)  echo "WARNING: switch count $vds_count does not match a standard 4-car (12) or 6-car (18) consist." ;;
esac
