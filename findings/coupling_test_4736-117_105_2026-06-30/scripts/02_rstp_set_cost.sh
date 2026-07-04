#!/usr/bin/env bash
# 02 — Part 1: ECHO the v9 Option-A cost change (port-cost 20000 on all 4 coupler ports).
# ECHO-ONLY: prints copy-paste commands, runs NOTHING. You eyeball, then paste each line.
# Run per train (pass that train's cab-switch IPs). One command per SSH session (CLI constraint).
# Cost change does NOT reboot the switch — live + reversible. DO NOT save yet (verify behaviour first).
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -ne 4 ]; then
  echo "usage: $0 <A1-ip> <A3-ip> <B1-ip> <B3-ip>"; exit 1
fi
A1=$1; A3=$2; B1=$3; B3=$4

echo "=== ECHO ONLY — review, then paste each line. Nothing has run. ==="
echo "=== Set coupler $COUPLER_PORT port-cost = 20000 on all four cab switches ==="
echo
for pair in "A1:$A1" "A3:$A3" "B1:$B1" "B3:$B3"; do
  name=${pair%%:*}; ip=${pair##*:}
  echo_cmd "$name $COUPLER_PORT -> cost 20000" "$ip" \
    "configure interface $COUPLER_PORT spanning-tree port-cost 20000"
done

echo "=== After pasting on BOTH trains (8 ports total): ==="
echo "  - run 01_rstp_harvest again -> all four = 20000, both ends of each link EQUAL"
echo "  - run 03_churn_watch        -> TC/flush count must FREEZE (>=10 min)"
echo "  - topology: single root, one coupler link FWD, its twin ALTR/BLK"
echo "  - DO NOT 'save running-config force' until the test passes (keeps revert trivial)."
echo "  - native-vlan 999 (M2) is a SEPARATE later step — do not combine here (trunk-rewrite trap)."
