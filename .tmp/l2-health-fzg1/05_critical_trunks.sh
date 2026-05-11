#!/bin/bash
# Step 5 — detail check on Stadler-facing trunks and ZFR ports.
# Re-runs the fingerprint to find A3 / B1 / B3 / D1 / D3, then dumps full details.
# Usage: ./05_critical_trunks.sh <CCU_IP>
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 5 — Critical Stadler-facing trunks"

vds=$(vds_switch_list "$CCU_IP")

a3="" ; b1="" ; b3="" ; d_obs=()  # arrays of D-class switches

for sw in $vds; do
  trunks=$(switch_run "$CCU_IP" "$sw" "show interface trunks" 2>/dev/null | awk 'NR>2 && /^e/{print $1}' | tr '\n' ',' | sed 's/,$//')
  vlans=$(switch_run "$CCU_IP" "$sw" "show vlans" 2>/dev/null)
  if echo "$trunks" | grep -q "e1-4"; then a3="$sw"; fi
  if echo "$trunks" | grep -q "e0-3"; then d_obs+=("$sw"); fi
  if echo "$vlans" | awk '/^0002/,/^----/' | grep -q "e1-11"; then
    if [ -z "$b1" ]; then b1="$sw"; else b3="$sw"; fi
  fi
done

echo "Identified: A3=${a3:-?}  B1=${b1:-?}  B3=${b3:-?}  D-class=${d_obs[*]:-?}"

show_port() {
  local sw="$1" port="$2" label="$3"
  echo
  echo "----- $label :: $sw $port -----"
  switch_run "$CCU_IP" "$sw" "show interface $port details" 2>&1
}

[ -n "$a3" ] && show_port "$a3" e1-4 "Stadler-FW (A3 e1-4)"
[ -n "$b1" ] && show_port "$b1" e1-11 "ZFR-R (B1 e1-11)"
[ -n "$b3" ] && show_port "$b3" e1-11 "ZFR (B3 e1-11)"
for d in "${d_obs[@]}"; do
  show_port "$d" e0-2 "OBS trunk ($d e0-2)"
  show_port "$d" e0-3 "RDC trunk ($d e0-3)"
done

echo
echo "----- Front coupler trunks (e0-2 on switches with e0-2 configured as trunk) -----"
for sw in $vds; do
  trunks=$(switch_run "$CCU_IP" "$sw" "show interface trunks" 2>/dev/null | awk 'NR>2 && /^e/{print $1}' | tr '\n' ',' | sed 's/,$//')
  if echo "$trunks" | grep -q "e0-2"; then
    state=$(switch_run "$CCU_IP" "$sw" "show interface summary" 2>/dev/null | awk '$1=="e0-2"{print $4}')
    printf "  %-15s e0-2  link=%s\n" "$sw" "${state:-unknown}"
  fi
done
