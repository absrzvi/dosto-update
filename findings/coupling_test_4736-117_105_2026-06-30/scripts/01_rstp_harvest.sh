#!/usr/bin/env bash
# 01 — Part 1 RSTP harvest. READ-ONLY. Captures coupler port costs, STP roles/states,
# trunk config, and coupler error counters for revert + before/after comparison.
# Usage: ./01_rstp_harvest.sh <A1-ip> <A3-ip> <B1-ip> <B3-ip>
# Run on EACH train (pass that train's cab-switch IPs). Tee output to a harvest file.
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -ne 4 ]; then
  echo "usage: $0 <A1-ip> <A3-ip> <B1-ip> <B3-ip>"; exit 1
fi
A1=$1; A3=$2; B1=$3; B3=$4

for pair in "A1:$A1" "A3:$A3" "B1:$B1" "B3:$B3"; do
  name=${pair%%:*}; ip=${pair##*:}
  echo "################ $(ts)  $name = $ip  (coupler $COUPLER_PORT) ################"
  echo "---- spanning-tree (role/state/cost of $COUPLER_PORT) ----"
  swcmd "$ip" "show spanning-tree"
  echo "---- running-config @ $COUPLER_PORT (exact current cost line for revert) ----"
  swcmd "$ip" "show running-config" | grep -A4 "interface $COUPLER_PORT"
  echo "---- interface trunks (native + prune set on $COUPLER_PORT) ----"
  swcmd "$ip" "show interface trunks"
  echo "---- $COUPLER_PORT details (CRC / carrier-false baseline) ----"
  swcmd "$ip" "show interface $COUPLER_PORT details"
  echo
done

echo ">> SAVE the per-port cost lines — 02_set_cost echoes the change; 99_revert needs the originals."
