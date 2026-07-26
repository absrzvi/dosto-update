#!/bin/bash
# Step 9 — aggregate all measurements into findings.json.
# This is the structured output the dosto-l2-report skill consumes.
# Usage: ./09_aggregate.sh <CCU_IP> [output_path] [FW_IP, default 172.19.196.1]
# ALWAYS pass FW_IP explicitly: 172.19.<128+Fzg//2>.<128*(Fzg%2)+1>
# (even Fzg -> .1, odd Fzg -> .129; field-verified 2026-07-09 on Fzg 231/box1-t41).
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP> [output_path] [FW_IP]}"
DEFAULT_OUT="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/findings_${CCU_IP}_$(date +%Y%m%d_%H%M%S).json"
OUTPUT="${2:-$DEFAULT_OUT}"
FW_IP="${3:-172.19.196.1}"

section "Step 9 — Aggregate findings → $OUTPUT"

vds=$(vds_switch_list "$CCU_IP")
vds_count=$(echo "$vds" | grep -c .)
wes_count=$(westermo_count "$CCU_IP")

# Gather firmware versions and uptime from each switch.
declare -A fw
for sw in $vds; do
  v=$(switch_run "$CCU_IP" "$sw" "show version" 2>/dev/null | grep -E "Firmware Version|Build" | tr '\n' ' ' | sed 's/  */ /g')
  fw[$sw]="$v"
done

# Pick a representative switch to read STP root from (every switch should agree).
first_sw=$(echo "$vds" | head -1)
stp_root=$(switch_run "$CCU_IP" "$first_sw" "show spanning-tree" 2>/dev/null | awk '/Root bridge/{print $4; exit}')

# Count STP root agreement across the fleet.
stp_agree=0; stp_total=0
for sw in $vds; do
  r=$(switch_run "$CCU_IP" "$sw" "show spanning-tree" 2>/dev/null | awk '/Root bridge/{print $4; exit}')
  stp_total=$((stp_total+1))
  [ "$r" = "$stp_root" ] && stp_agree=$((stp_agree+1))
done

# Per-port error scan, summarised: any switch with anomalies?
port_anomalies=()
PORTS="e0-0 e0-1 e0-2 e0-3 e0-4 e0-5 e1-0 e1-1 e1-2 e1-3 e1-4 e1-5 e1-6 e1-7 e1-8 e1-9 e1-10 e1-11 e1-12 e1-13 e1-14 e1-15 e2-0 e2-1 e2-2 e2-3 e2-4 e2-5"
for sw in $vds; do
  summary=$(switch_run "$CCU_IP" "$sw" "show interface summary" 2>/dev/null)
  for p in $PORTS; do
    state=$(echo "$summary" | awk -v p=$p '$1==p{print $3}')
    [ "$state" = "enabled" ] || continue
    d=$(switch_run "$CCU_IP" "$sw" "show interface $p details" 2>/dev/null)
    rx=$(echo "$d"   | sed -nE 's/.*RX errors:([0-9]+).*/\1/p' | head -1)
    crc=$(echo "$d"  | sed -nE 's/.*RX crc errors: ?([0-9]+).*/\1/p' | head -1)
    car=$(echo "$d"  | sed -nE 's/.*carrier false:([0-9]+).*/\1/p' | head -1)
    total=$((${rx:-0}+${crc:-0}+${car:-0}))
    if [ "$total" -gt 0 ]; then
      port_anomalies+=("{\"switch\":\"$sw\",\"port\":\"$p\",\"rx_errors\":${rx:-0},\"crc\":${crc:-0},\"carrier_false\":${car:-0}}")
    fi
  done
done

# Trunk speeds: count e0-0/e0-1/e0-4 UP and at expected speed.
e00_up=0; e01_up=0; e04_up=0
for sw in $vds; do
  s=$(switch_run "$CCU_IP" "$sw" "show interface summary" 2>/dev/null)
  echo "$s" | awk '$1=="e0-0" && $4=="up"{print}' | grep -q . && e00_up=$((e00_up+1))
  echo "$s" | awk '$1=="e0-1" && $4=="up"{print}' | grep -q . && e01_up=$((e01_up+1))
  echo "$s" | awk '$1=="e0-4" && $4=="up"{print}' | grep -q . && e04_up=$((e04_up+1))
done

# Stadler FW e2e probe.
fw_tcp80="unknown"; fw_tcp22="unknown"; fw_arp="unknown"; vlan7_errors="unknown"
probe_out=$(ccu_run "$CCU_IP" "
  ip neigh show dev vlan7 | grep $FW_IP || echo no-arp
  for port in 22 80; do
    if timeout 3 bash -c \"echo > /dev/tcp/$FW_IP/\$port\" 2>/dev/null; then echo tcp\$port=OPEN; else echo tcp\$port=closed; fi
  done
  ip -s link show vlan7 | awk '/RX:/ {getline; print \"vlan7_rx_errors=\"\$3\" vlan7_rx_drops=\"\$4}'
" 2>/dev/null || true)

echo "$probe_out" | grep -q "REACHABLE" && fw_arp="reachable"
echo "$probe_out" | grep -q "tcp80=OPEN" && fw_tcp80="open"
echo "$probe_out" | grep -q "tcp22=OPEN" && fw_tcp22="open"
vlan7_errors=$(echo "$probe_out" | grep -oE "vlan7_rx_errors=[0-9]+" | cut -d= -f2)

# Now assemble JSON. We avoid jq dependency; emit by hand.
{
  echo "{"
  echo "  \"generated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"ccu_ip\": \"$CCU_IP\","
  echo "  \"vds_switches\": {"
  echo "    \"count\": $vds_count,"
  echo -n "    \"ips\": ["
  echo "$vds" | awk 'BEGIN{c=0}{if(c++)printf ", "; printf "\"%s\"", $0}'
  echo "],"
  echo "    \"consist_size\": \"$([ $vds_count -eq 12 ] && echo 4-car || ([ $vds_count -eq 18 ] && echo 6-car || echo unknown))\","
  echo -n "    \"firmware\": {"
  first=1
  for sw in $vds; do
    [ $first -eq 1 ] || echo -n ","
    echo -n " \"$sw\": \"${fw[$sw]}\""
    first=0
  done
  echo " }"
  echo "  },"
  echo "  \"westermo_radio_count\": $wes_count,"
  echo "  \"stp\": {"
  echo "    \"root\": \"$stp_root\","
  echo "    \"agreement\": \"$stp_agree/$stp_total\","
  echo "    \"consistent\": $([ $stp_agree -eq $stp_total ] && echo true || echo false)"
  echo "  },"
  echo "  \"trunks_up\": {"
  echo "    \"e0-0\": \"$e00_up/$vds_count\","
  echo "    \"e0-1\": \"$e01_up/$vds_count\","
  echo "    \"e0-4\": \"$e04_up/$vds_count\""
  echo "  },"
  echo -n "  \"port_anomalies\": ["
  first=1
  for a in "${port_anomalies[@]:-}"; do
    [ -z "$a" ] && continue
    [ $first -eq 1 ] || echo -n ","
    echo -n "$a"
    first=0
  done
  echo "],"
  echo "  \"stadler_fw\": {"
  echo "    \"arp\": \"$fw_arp\","
  echo "    \"tcp_22\": \"$fw_tcp22\","
  echo "    \"tcp_80\": \"$fw_tcp80\","
  echo "    \"vlan7_rx_errors\": \"${vlan7_errors:-unknown}\","
  echo "    \"icmp_note\": \"ICMP filtered by FW policy on most installs — interpret 100% loss with TCP/ARP context\""
  echo "  },"
  echo "  \"verdict\": {"
  total_anomalies=${#port_anomalies[@]}
  if [ $total_anomalies -eq 0 ] && [ $stp_agree -eq $stp_total ] && [ $vds_count -gt 0 ]; then
    echo "    \"overall\": \"HEALTHY\","
  else
    echo "    \"overall\": \"NEEDS_REVIEW\","
  fi
  echo "    \"port_anomaly_count\": $total_anomalies,"
  echo "    \"notes\": \"See port_anomalies array and headline metrics above.\""
  echo "  }"
  echo "}"
} > "$OUTPUT"

echo "Wrote $OUTPUT"
echo
cat "$OUTPUT"
