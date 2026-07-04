#!/usr/bin/env bash
# harvest_ports.sh — emit the compact "<ip> <port> RX=<b> TX=<b> RXp=<p> TXp=<p>" line for given
# ports, the SAME format as .claude/sample1.txt / the playbook Phase-5/7 sampler. READ-ONLY.
#
# Purpose: settle the counter-field-parsing question BEFORE you're trackside. Run it against one
# real port; if it prints a clean RX=/TX=/RXp=/TXp= line, 11_port_traffic.sh will parse correctly.
# If the numbers come out as 0 or blank, the live `show interface <port> details` uses different
# field labels than this regex expects — adjust the FIELD greps below (and mirror into
# 11_port_traffic.sh read_counters()).
#
# Usage: ./harvest_ports.sh <switch-ip> <port> [<port> ...]
#   e.g. ./harvest_ports.sh 10.179.1.50 e1-0 e1-1 e0-2
# Tip: snapshot twice N s apart and diff for a rate, e.g.
#   ./harvest_ports.sh $SW e1-0 > /tmp/s1; sleep 30; ./harvest_ports.sh $SW e1-0 > /tmp/s2
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -lt 2 ]; then
  echo "usage: $0 <switch-ip> <port> [port ...]"; exit 1
fi
SW=$1; shift

for port in "$@"; do
  d=$(swcmd "$SW" "show interface $port details" 2>/dev/null)
  # Field extraction — tolerant of "RX bytes", "RX:", "rx-bytes", "in octets" style labels.
  rxb=$(echo "$d" | grep -ioE "(rx[ _-]*bytes|in[ _-]*octets)[ =:]*[0-9]+"   | grep -oE "[0-9]+" | head -1)
  txb=$(echo "$d" | grep -ioE "(tx[ _-]*bytes|out[ _-]*octets)[ =:]*[0-9]+"  | grep -oE "[0-9]+" | head -1)
  rxp=$(echo "$d" | grep -ioE "(rx[ _-]*packets|in[ _-]*packets)[ =:]*[0-9]+"  | grep -oE "[0-9]+" | head -1)
  txp=$(echo "$d" | grep -ioE "(tx[ _-]*packets|out[ _-]*packets)[ =:]*[0-9]+" | grep -oE "[0-9]+" | head -1)
  if [ -z "${rxb:-}" ] && [ -z "${txb:-}" ]; then
    echo "# $SW $port : could not parse counters — raw details follow, adjust regex:"
    echo "$d" | grep -iE "byte|octet|packet|rx|tx" | sed 's/^/#   /'
  else
    echo "$SW $port RX=${rxb:-0} TX=${txb:-0} RXp=${rxp:-0} TXp=${txp:-0}"
  fi
done
