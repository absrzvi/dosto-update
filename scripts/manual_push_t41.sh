#!/bin/bash
# Manual VDS config push (bypass OBN) for box1-t41 / Fzg 231.
# OBN's update c hangs / no-ops on this consist; this replicates OBN's own
# TFTP+SNMP config-push per the validated recipe (memory project-manual-tftp-obn-bypass,
# proven Fzg123 bench 2026-05-21). Runs detached — drop-proof.
#
# Templates already hardcode train_id=231, so rendered hostnames = fv5-*-v8-231.
# Push order: leaf-side + non-head first, HEAD-OF-TRAIN A1 (.180) LAST (v8 port
# reassignment can island the CCU — memory project-bench-v8-cabling-trap).
set -u
LOG=/var/tmp/manual_push_t41.log
DONE=/var/tmp/manual_push_t41_done
rm -f "$DONE"
exec > "$LOG" 2>&1

TFTP_DIR=/data/auto-topology
UPLOAD=$TFTP_DIR/upload
SRC=10.179.41.129                      # vlan100 SVI — switches reach CCU here
RENDER=/usr/share/obn/venv/bin/python3
TPLDIR=/etc/obn/template

# SNMP v3 creds + OIDs (from /etc/obn/vendors.yaml vdsrail block)
SNMP="-v3 -u snmpadmin -l authPriv -a SHA -A NomadStayOut! -x AES -X NomadStayOut!"
OID_TFTP_LOC=".1.3.6.1.4.1.8072.1.3.2.2.1.3.7.108.111.97.100.117.114.108"
OID_TRIGGER=".1.3.6.1.4.1.8072.1.3.2.2.1.7.7.108.111.97.100.117.114.108"
OID_TASK=".1.3.6.1.4.1.8072.1.3.2.3.1.2.9.99.104.101.99.107.116.97.115.107"
OID_GET_HOST=".1.3.6.1.2.1.1.5.0"
OID_SET_HOST="1.3.6.1.4.1.8072.1.3.2.2.1.3.6.114.101.98.111.111.116"
OID_REBOOT=".1.3.6.1.4.1.8072.1.3.2.2.1.7.6.114.101.98.111.111.116"

echo "=== manual push START $(date) ==="

# --- 3 CCU-side bypasses (runtime; OBN normally does these) ---
modprobe nf_conntrack_tftp
iptables -t raw -C PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp 2>/dev/null \
  || iptables -t raw -I PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp
iptables -C MGMTI -p udp --dport 69 -j ACCEPT 2>/dev/null \
  || iptables -I MGMTI 1 -p udp --dport 69 -j ACCEPT
mkdir -p "$UPLOAD"
echo "bypasses applied"

# stuck switches: IP MAC TEMPLATESTEM   (A1 .180 intentionally LAST)
SWITCHES=(
  "10.179.41.189 a0:59:3a:d0:8e:60 fv5-400-E1"
  "10.179.41.183 a0:59:3a:d0:8d:20 fv5-400-E2"
  "10.179.41.184 a0:59:3a:d0:8a:a0 fv5-400-E3"
  "10.179.41.186 a0:59:3a:d0:8a:00 fv5-500-F1"
  "10.179.41.187 a0:59:3a:d0:9f:e0 fv5-500-F2"
  "10.179.41.191 a0:59:3a:d0:8d:a0 fv5-500-F3"
  "10.179.41.185 a0:59:3a:d0:8d:60 fv5-600-B1"
  "10.179.41.192 a0:59:3a:d0:8d:40 fv5-600-B3"
  "10.179.41.178 a0:59:3a:d0:8c:e0 fv5-100-A3"
  "10.179.41.180 a0:59:3a:d0:89:a0 fv5-100-A1"
)

push_one() {
  local ip="$1" mac="$2" stem="$3"
  local macnc="${mac//:/}"
  local fname="${stem}-${macnc}.cfg"
  local url="tftp://${SRC}/upload/${fname}"
  echo "----- $ip ($stem) -----"

  # 1. render config (OBN's own jinja env; train_id=231 already in template)
  #    heredoc form (inline -c mangles quotes over ssh)
  STEM="$stem" OUT="$UPLOAD/$fname" $RENDER <<'PYEOF'
import os
from jinja2 import Environment, FileSystemLoader, StrictUndefined
env=Environment(loader=FileSystemLoader("/etc/obn/template"),autoescape=False,undefined=StrictUndefined)
o=env.get_template(os.environ["STEM"]+".cfg").render(train_id=231)
open(os.environ["OUT"],"w").write(o)
PYEOF
  if [ ! -s "$UPLOAD/$fname" ]; then echo "  RENDER FAILED — skip"; return 1; fi
  local hn; hn=$(grep -m1 "system hostname" "$UPLOAD/$fname" | awk '{print $3}')
  echo "  rendered $fname  (hostname=$hn, $(wc -l < "$UPLOAD/$fname") lines)"

  # 2. allow this switch through TFTP firewall
  ipset add tftp_allowed "$ip" 2>/dev/null || true

  # 3. set TFTP location + trigger the config pull
  snmpset $SNMP "$ip" "$OID_TFTP_LOC" s "$url" >/dev/null 2>&1
  snmpset $SNMP "$ip" "$OID_TRIGGER" i 3 >/dev/null 2>&1

  # 4. poll task-running until "configuration ... loaded" or error (max ~40s)
  local ok=0
  for i in $(seq 1 20); do
    sleep 2
    local st; st=$(snmpget $SNMP -Ovq "$ip" "$OID_TASK" 2>/dev/null)
    echo "    task[$i]: $st"
    if echo "$st" | grep -qi "configuration .* loaded"; then ok=1; break; fi
    if echo "$st" | grep -qi "Last error"; then echo "  LOAD ERROR"; return 1; fi
  done
  if [ "$ok" != 1 ]; then echo "  load did not confirm — skip reboot"; return 1; fi

  # 5. commit trigger: set hostname OID to CURRENT hostname (required before reboot)
  local cur; cur=$(snmpget $SNMP -Ovq "$ip" "$OID_GET_HOST" 2>/dev/null | tr -d '"')
  snmpset $SNMP "$ip" "$OID_SET_HOST" s "$cur" >/dev/null 2>&1

  # 6. reboot to persist running->startup
  snmpset $SNMP "$ip" "$OID_REBOOT" i 3 >/dev/null 2>&1
  echo "  reboot triggered; waiting for $hn ..."

  # 7. verify new hostname appears (max ~120s)
  for i in $(seq 1 24); do
    sleep 5
    local nh; nh=$(snmpget $SNMP -Ovq "$ip" "$OID_GET_HOST" 2>/dev/null | tr -d '"')
    if [ "$nh" = "$hn" ]; then echo "  ✅ $ip now $nh"; return 0; fi
  done
  echo "  ⚠️ $ip did not confirm new hostname (check manually)"
  return 1
}

for entry in "${SWITCHES[@]}"; do
  set -- $entry
  push_one "$1" "$2" "$3"
done

echo "=== manual push DONE $(date) ==="
touch "$DONE"
