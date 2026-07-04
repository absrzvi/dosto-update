#!/usr/bin/env bash
# 09 — PRECHECK the VLAN-5 measurement method before S0. READ-ONLY.
#
# Why: the CCU has NO interface on VLAN 5 (cameras live on 172.18.x.x, a Stadler device VLAN; the
# CCU only sees vlan100 / vlan7 / bond0). So we CANNOT ping cameras from the CCU. Instead we measure
# the CAMERA SWITCH PORTS' RX/TX counters (cameras stream continuously) and the master-FW trunk's
# throughput. This precheck proves the switch ports are reachable and actually carrying traffic
# BEFORE we commit to the staged test — so we don't discover mid-window that we can see nothing.
#
# Usage: ./09_precheck_measure.sh <switch-ip> <cam-port> [<cam-port> ...]
#   e.g. backup D1 cameras:  ./09_precheck_measure.sh <D1-ip> e1-0 e1-1 e1-2
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -lt 2 ]; then
  echo "usage: $0 <switch-ip> <cam-port> [cam-port ...]"; exit 1
fi
SW=$1; shift; PORTS=("$@")

echo "=== $(ts) precheck: reach $SW, confirm camera ports stream ==="
echo "[1] switch reachable + port summary:"
swcmd "$SW" "show interface summary" | grep -E "^(Port|e1-)" | head -20 || { echo "  !! cannot reach $SW"; exit 2; }

echo
echo "[2] camera ports — link state + VLAN-5 access:"
for p in "${PORTS[@]}"; do
  echo "  -- $p --"
  swcmd "$SW" "show interface $p details" | grep -iE "link|speed|duplex|vlan|RX|TX|error|crc|carrier" | head -12
done

echo
echo "[3] 10s traffic sanity (are the cameras actually streaming?):"
for p in "${PORTS[@]}"; do
  a=$(swcmd "$SW" "show interface $p details" | grep -ioE "TX[ =:]+[0-9]+" | grep -oE "[0-9]+" | head -1)
  sleep 0  # placeholder; real delta done below in one pass
  echo "  $p TX-bytes sample-1 = ${a:-?}"
done
echo "  (run 11_port_traffic.sh for the proper timed delta; this is just a reachability sanity check)"

echo
echo ">> PASS precheck if: ports link-UP on VLAN 5, counters non-zero and moving."
echo ">> If a port reads 0/idle, that camera isn't streaming — pick a known-live camera port for the test."
echo ">> Also identify the MASTER-FW trunk (A3 e1-4) on the master train to watch VLAN-5 arriving at the FW."
