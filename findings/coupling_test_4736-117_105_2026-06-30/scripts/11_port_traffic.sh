#!/usr/bin/env bash
# 11 — Part 2/3: VLAN-5 PORT-TRAFFIC monitor. READ-ONLY. Run ONCE PER STAGE (S0, S1, S2) with the
# SAME args so the three results are directly comparable. Replaces the CCU-ping idea — the CCU has
# no VLAN-5 leg, so we measure traffic AT THE SWITCH PORTS instead (cameras stream continuously).
#
# Takes two counter snapshots INTERVAL seconds apart on each watched port and reports the rate
# (Mbps + pps) and error-counter movement. Counter format per port: RX=<bytes> TX=<bytes>
# RXp=<pkts> TXp=<pkts> (same fields as the playbook Phase-5/7 sampler / .claude/sample1.txt).
#
# What to watch (pass as <switch-ip>:<port> pairs):
#   - backup camera ports (e.g. backup D1 e1-0/e1-1)  -> is the camera still streaming (TX)?
#   - master-FW trunk A3 e1-4 (on master train)       -> is VLAN-5 reaching the master FW (RX)?
#   - a master camera port (control)                  -> should be unchanged across stages
#
# Usage: ./11_port_traffic.sh <stage:S0|S1|S2> <interval-sec> <ip:port> [<ip:port> ...]
#   e.g. ./11_port_traffic.sh S0 30 10.179.1.50:e1-0 10.179.1.51:e1-0 10.179.32.40:e1-4
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -lt 3 ]; then
  echo "usage: $0 <S0|S1|S2> <interval-sec> <ip:port> [ip:port ...]"; exit 1
fi
STAGE=$1; INTERVAL=$2; shift 2; TARGETS=("$@")

# Pull RX/TX byte+pkt counters for one port from `show interface <port> details`. Echoes: RXb TXb RXp TXp
# NOTE: this regex is kept IDENTICAL to harvest_ports.sh — validate the field labels once with
# harvest_ports.sh on the day; if you adjust the regex there, mirror the change here.
read_counters() { # <ip> <port>
  local ip=$1 port=$2 d
  d=$(swcmd "$ip" "show interface $port details" 2>/dev/null)
  local rxb txb rxp txp
  rxb=$(echo "$d" | grep -ioE "(rx[ _-]*bytes|in[ _-]*octets)[ =:]*[0-9]+"    | grep -oE "[0-9]+" | head -1)
  txb=$(echo "$d" | grep -ioE "(tx[ _-]*bytes|out[ _-]*octets)[ =:]*[0-9]+"   | grep -oE "[0-9]+" | head -1)
  rxp=$(echo "$d" | grep -ioE "(rx[ _-]*packets|in[ _-]*packets)[ =:]*[0-9]+"  | grep -oE "[0-9]+" | head -1)
  txp=$(echo "$d" | grep -ioE "(tx[ _-]*packets|out[ _-]*packets)[ =:]*[0-9]+" | grep -oE "[0-9]+" | head -1)
  echo "${rxb:-0} ${txb:-0} ${rxp:-0} ${txp:-0}"
}

echo "################ $(ts)  PORT TRAFFIC  stage=$STAGE  interval=${INTERVAL}s ################"
declare -A S1
for t in "${TARGETS[@]}"; do
  ip=${t%%:*}; port=${t##*:}
  S1[$t]=$(read_counters "$ip" "$port")
  printf '  %-22s t0  RXb/TXb/RXp/TXp = %s\n' "$t" "${S1[$t]}"
done

sleep "$INTERVAL"

echo "--- $(ts) deltas over ${INTERVAL}s ---"
for t in "${TARGETS[@]}"; do
  ip=${t%%:*}; port=${t##*:}
  read r2b t2b r2p t2p <<<"$(read_counters "$ip" "$port")"
  read r1b t1b r1p t1p <<<"${S1[$t]}"
  dRXb=$(( r2b - r1b )); dTXb=$(( t2b - t1b ))
  dRXp=$(( r2p - r1p )); dTXp=$(( t2p - t1p ))
  rxmbps=$(awk "BEGIN{printf \"%.2f\", $dRXb*8/$INTERVAL/1e6}")
  txmbps=$(awk "BEGIN{printf \"%.2f\", $dTXb*8/$INTERVAL/1e6}")
  rxpps=$(( dRXp / INTERVAL )); txpps=$(( dTXp / INTERVAL ))
  printf '  %-22s RX=%6s Mbps (%6s pps)  TX=%6s Mbps (%6s pps)\n' "$t" "$rxmbps" "$rxpps" "$txmbps" "$txpps"
  # error-counter snapshot (should stay 0 across stages)
  swcmd "$ip" "show interface $port details" | grep -iE "crc|carrier false|drop" | sed 's/^/      /'
done

echo
echo ">> Record per-target RX/TX Mbps+pps for S0/S1/S2 in the README traffic table."
echo ">> Reading: a backup camera streaming healthily = steady TX; VLAN-5 reaching master FW = RX on"
echo ">>   A3 e1-4 holds across stages. A DROP at S1 but recovery at S2 (FW SVI down) supports A8."
echo ">> Pair every stage with the driver's HMI observation (timestamp + qualitative)."
