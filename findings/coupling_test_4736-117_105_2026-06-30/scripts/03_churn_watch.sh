#!/usr/bin/env bash
# 03 — Part 1: TC-churn watcher. READ-ONLY. Samples each cab switch's TC / "Flushing all entries"
# count from the log at an interval, and reports whether the count is FROZEN (churn stopped) or
# still INCREMENTING. This is the decisive Part-1 measurement.
# Usage: ./03_churn_watch.sh <interval-sec> <iterations> <ip1> [ip2 ...]
#   e.g. ./03_churn_watch.sh 60 12 $A1 $A3 $B1 $B3     # 12 min window, 1-min samples
# Pre-req: RSTP debug enabled first ->  swcmd $SW "configure system logging debug rstp,coupled"
# Run on both trains (or pass all 8 cab-switch IPs if reachable from one CCU).
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -lt 3 ]; then
  echo "usage: $0 <interval-sec> <iterations> <ip1> [ip2 ...]"; exit 1
fi
INTERVAL=$1; ITERS=$2; shift 2; IPS=("$@")

# count TC/flush events in a switch's current log
flush_count() { swcmd "$1" "show log" 2>/dev/null | grep -ciE "Flushing all entries|topology change|TC "; }

declare -A PREV
echo "=== $(ts) churn watch: ${#IPS[@]} switches, ${INTERVAL}s x ${ITERS} ==="
for ip in "${IPS[@]}"; do PREV[$ip]=$(flush_count "$ip"); printf '  %-15s start count=%s\n' "$ip" "${PREV[$ip]}"; done

for ((i=1;i<=ITERS;i++)); do
  sleep "$INTERVAL"
  echo "--- $(ts) sample $i/$ITERS ---"
  for ip in "${IPS[@]}"; do
    cur=$(flush_count "$ip"); delta=$(( cur - ${PREV[$ip]} ))
    state="FROZEN"; [ "$delta" -gt 0 ] && state="CHURNING (+$delta)"
    printf '  %-15s count=%-8s %s\n' "$ip" "$cur" "$state"
    PREV[$ip]=$cur
  done
done

echo
echo ">> PASS criterion: every switch reads FROZEN for the whole window (delta 0)."
echo ">> Run this BEFORE the cost change (expect CHURNING baseline) and AFTER (expect FROZEN)."
