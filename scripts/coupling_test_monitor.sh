#!/bin/bash
# coupling_test_monitor.sh — sample byte counters, STP state, LLDP on every consist switch
# every INTERVAL seconds. Append-only labelled snapshots to LOGFILE.
#
# Usage on the CCU:
#   bash /tmp/coupling_test_monitor.sh start <TRAIN#>    # backgrounds the sampler, prints PID
#   bash /tmp/coupling_test_monitor.sh stop              # kill the sampler
#   bash /tmp/coupling_test_monitor.sh tail              # tail the log
#   bash /tmp/coupling_test_monitor.sh once              # one snapshot, to stdout (debug)
#
# Output: /tmp/coupling-test-<TRAIN#>-<startISO>.log
# Each snapshot block delimited by:
#   ==SNAPSHOT <iso8601> seq=<n>==

INTERVAL=${COUPLING_INTERVAL:-30}
PIDFILE=/tmp/coupling-monitor.pid
LOGPTR=/tmp/coupling-monitor.logpath

# Switch IPs are derived from the CCU's vlan100 subnet (.178-.195)
# (DOSTO 6-car consist has 18 switches in this range)
ccu_subnet=$(ip -4 addr show vlan100 2>/dev/null | awk '/inet /{print $2}' | awk -F. '{print $1"."$2"."$3}')
if [ -z "$ccu_subnet" ]; then
  echo "ERROR: cannot determine vlan100 subnet" >&2
  exit 1
fi

SWITCHES=""
for last in $(seq 178 195); do
  SWITCHES="$SWITCHES ${ccu_subnet}.${last}"
done

case "${1:-help}" in
  start)
    TRAIN="${2:-unknown}"
    if [ -f "$PIDFILE" ] && kill -0 "$(cat $PIDFILE)" 2>/dev/null; then
      echo "Monitor already running, pid=$(cat $PIDFILE), log=$(cat $LOGPTR)"
      exit 1
    fi
    START=$(date -u +%Y%m%dT%H%M%SZ)
    LOG=/tmp/coupling-test-${TRAIN}-${START}.log
    echo "$LOG" > "$LOGPTR"
    (
      seq=0
      while true; do
        TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        echo "==SNAPSHOT $TS seq=$seq=="
        for ip in $SWITCHES; do
          for port in e0-0 e0-1 e0-2; do
            out=$(/tmp/swcmd.sh "$ip" "show interface $port details" 2>&1)
            # one line per port: status, packets, bytes, errors
            line_proto=$(echo "$out" | grep "line protocol" | head -1)
            rx_uni=$(echo "$out"  | grep "RX packets" -A1 | grep "unicasts" | head -1 | sed -E 's/.*unicasts:([0-9]+).*/\1/')
            rx_bc=$(echo "$out"   | grep "RX packets" -A1 | grep "unicasts" | head -1 | sed -E 's/.*broadcasts:([0-9]+).*/\1/')
            rx_bytes=$(echo "$out" | grep "RX bytes:" | head -1 | sed -E 's/.*RX bytes:([0-9]+).*/\1/')
            rx_crc=$(echo "$out"  | grep "RX crc errors:" | head -1 | sed -E 's/.*RX crc errors:\s*([0-9]+).*/\1/')
            cf=$(echo "$out"      | grep "carrier false:" | head -1 | sed -E 's/.*carrier false:([0-9]+).*/\1/')
            speed=$(echo "$out"   | grep -E "^\s*Speed:" | head -1 | awk '{print $2,$3,$4,$5,$6}')
            printf "%-16s %-5s | %s | uni=%s bc=%s bytes=%s crc=%s cf=%s speed=%s\n" \
              "$ip" "$port" "$line_proto" "$rx_uni" "$rx_bc" "$rx_bytes" "$rx_crc" "$cf" "$speed"
          done
        done
        # STP roots — one line per switch
        echo "--STP--"
        for ip in $SWITCHES; do
          r=$(/tmp/swcmd.sh "$ip" "show spanning-tree" 2>&1 | grep "Root bridge" | head -1)
          printf "%-16s %s\n" "$ip" "$r"
        done
        # LLDP front-coupler ports (e0-2 on A1/A3/B1/B3) — these wake up in doppeltraktion
        echo "--LLDP-couplers--"
        for ip in $SWITCHES; do
          peers=$(/tmp/swcmd.sh "$ip" "show lldp neighbours" 2>&1 | grep -E "^e0-2" | awk '{print $1, $3}')
          if [ -n "$peers" ]; then
            printf "%-16s %s\n" "$ip" "$peers"
          fi
        done
        seq=$((seq+1))
        sleep "$INTERVAL"
      done
    ) >> "$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    echo "started, pid=$(cat $PIDFILE), interval=${INTERVAL}s, log=$LOG"
    ;;

  stop)
    if [ ! -f "$PIDFILE" ]; then echo "not running"; exit 0; fi
    pid=$(cat "$PIDFILE")
    if kill "$pid" 2>/dev/null; then
      echo "stopped pid=$pid"
    else
      echo "could not kill pid=$pid (already dead?)"
    fi
    rm -f "$PIDFILE"
    ;;

  tail)
    if [ ! -f "$LOGPTR" ]; then echo "no log path recorded"; exit 0; fi
    tail -50 "$(cat $LOGPTR)"
    ;;

  once)
    seq=once
    TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "==SNAPSHOT $TS seq=$seq=="
    for ip in $SWITCHES; do
      for port in e0-0 e0-1 e0-2; do
        out=$(/tmp/swcmd.sh "$ip" "show interface $port details" 2>&1)
        rx_uni=$(echo "$out"  | grep "RX packets" -A1 | grep "unicasts" | head -1 | sed -E 's/.*unicasts:([0-9]+).*/\1/')
        rx_bc=$(echo "$out"   | grep "RX packets" -A1 | grep "unicasts" | head -1 | sed -E 's/.*broadcasts:([0-9]+).*/\1/')
        rx_crc=$(echo "$out"  | grep "RX crc errors:" | head -1 | sed -E 's/.*RX crc errors:\s*([0-9]+).*/\1/')
        printf "%-16s %-5s | uni=%s bc=%s crc=%s\n" "$ip" "$port" "$rx_uni" "$rx_bc" "$rx_crc"
      done
    done
    ;;

  *)
    cat <<USAGE
coupling_test_monitor.sh — DOSTO coupling-test live sampler

USAGE:
  bash $0 start <TRAIN#>      backgrounds the sampler; logs every \${COUPLING_INTERVAL:-30}s
  bash $0 stop                kill the sampler
  bash $0 tail                tail -50 the current log
  bash $0 once                one snapshot to stdout (debug)

Output log: /tmp/coupling-test-<TRAIN#>-<startISO>.log
Each snapshot block delimited by '==SNAPSHOT <iso8601> seq=<n>=='.
Sampler harvests on all 18 switches: e0-0/e0-1/e0-2 byte counters + STP roots + LLDP e0-2 peers.
USAGE
    ;;
esac
