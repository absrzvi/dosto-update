#!/bin/bash
# sw_bootwindow_poll.sh — CCU-side boot-window evidence poller for the display-transient RCA.
#
# Runs ON the CCU (or via ssh-to-CCU). Polls one VDS switch every INTERVAL seconds for
# the variables that distinguish a CLEAN boot from a KMdev-crash boot where display ports
# come up linked-but-dataless:
#   - ifOperStatus  (link up/down)              .1.3.6.1.2.1.2.2.1.8.<idx>
#   - ifLastChange  (when port last flipped)    .1.3.6.1.2.1.2.2.1.9.<idx>
#   - ifInOctets    (is the port RECEIVING?)    .1.3.6.1.2.1.2.2.1.10.<idx>   <-- the "dataless" tell
#   - ifOutOctets   (is the switch sending?)    .1.3.6.1.2.1.2.2.1.16.<idx>
# Plus uptime, so we can see the boot moment.
#
# The KMdev-crash signature in the captured data:
#   a display port reaches ifOperStatus=1 (UP) but ifInOctets stays 0 / barely moves
#   -> "link but no data". On a clean boot the same port shows ifInOctets climbing.
#
# Display-port ifIndexes on a 28-port NV6 VDS switch (7.4.2), confirmed via ifDescr walk:
#   e1-14=23 e1-15=24 e2-0=25 e2-1=26 e2-2=27 e2-3=28 e2-4=29
# (Walk .1.3.6.1.2.1.2.2.1.2 to confirm per switch if in doubt.)
#
# Usage (from laptop):
#   ssh -i openssh developer@<CCU> 'bash -s' < scripts/sw_bootwindow_poll.sh <SW_IP> [SECONDS] [INTERVAL] > capture.txt
# Or copy to CCU and run:  bash sw_bootwindow_poll.sh <SW_IP> 300 3 > capture.txt

SW="${1:?usage: sw_bootwindow_poll.sh <switch-ip> [duration_s=300] [interval_s=3]}"
DUR="${2:-300}"
INT="${3:-3}"
IDXS="23 24 25 26 27 28 29"          # display ports; edit for NV4 / different consist
SNMP="-v3 -l authPriv -u snmpadmin -a SHA -A NomadStayOut! -x AES -X NomadStayOut! -t 2 -r 1"

echo "# boot-window poll  switch=$SW  duration=${DUR}s  interval=${INT}s  start=$(date -u +%FT%TZ)"
echo "# columns: utc  uptime  idx  oper(1up/2down)  lastchange(ticks)  inOctets  outOctets"
ITERS=$(( DUR / INT ))
for n in $(seq 1 "$ITERS"); do
  TS=$(date -u +%H:%M:%S)
  UP=$(snmpget $SNMP "$SW" .1.3.6.1.2.1.1.3.0 -Ovq 2>/dev/null)
  for IDX in $IDXS; do
    OP=$(snmpget $SNMP "$SW" .1.3.6.1.2.1.2.2.1.8.$IDX -Ovq 2>/dev/null)
    LC=$(snmpget $SNMP "$SW" .1.3.6.1.2.1.2.2.1.9.$IDX -Ovq 2>/dev/null)
    IN=$(snmpget $SNMP "$SW" .1.3.6.1.2.1.2.2.1.10.$IDX -Ovq 2>/dev/null)
    OUT=$(snmpget $SNMP "$SW" .1.3.6.1.2.1.2.2.1.16.$IDX -Ovq 2>/dev/null)
    echo "$TS  $UP  idx$IDX  oper=$OP  lc=$LC  in=$IN  out=$OUT"
  done
  sleep "$INT"
done
echo "# end=$(date -u +%FT%TZ)"
