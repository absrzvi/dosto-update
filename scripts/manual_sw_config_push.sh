#!/bin/bash
# Manual VDS Consist Switch config push — bypasses OBN (raw TFTP+SNMP).
# Canonical implementation for skill dosto-sw-config-manual.
#
# Use when OBN's `obn update c` has FAILED (hangs, or silently no-ops) but switches
# must still reach their target v8 config. Replicates OBN's own push per validated
# recipe (memory project_manual_tftp_obn_bypass; proven Fzg123 bench 2026-05-21,
# box1-t41/Fzg231 2026-07-07 for 11 switches after OBN hung).
#
# Runs DETACHED (launch with: sudo setsid bash manual_sw_config_push.sh & disown)
# so a flaky cellular link can't interrupt a multi-switch run.
#
# CONFIG the two vars below per run, then feed the SWITCHES list (IP MAC TEMPLATE-STEM),
# leaf/mid first, HEAD-OF-TRAIN A1 LAST. Derive positions from `obn validate`
# cross-checked against the LLDP ring — NOT from stale switch hostnames.
#
# All OIDs/creds are read live from /etc/obn/vendors.yaml (vdsrail block) — the
# defaults below match box1-t41 but VERIFY per train.
set -u

# ---- per-run config ----
FZG="${FZG:?set FZG=<train_id/Fzg to render, e.g. 231>}"
CCU_OCTET="${CCU_OCTET:?set CCU_OCTET=<box id, e.g. 41 for 10.179.41.x>}"
SWITCHES_FILE="${SWITCHES_FILE:-/var/tmp/manual_sw_config_switches.txt}"  # lines: "IP MAC STEM"
# ------------------------

SRC="10.179.${CCU_OCTET}.129"            # vlan100 SVI — switches reach CCU here (NOT bond0 .1)
TFTP_DIR=/data/auto-topology
UPLOAD="$TFTP_DIR/upload"
RENDER=/usr/share/obn/venv/bin/python3
TPLDIR=/etc/obn/template
LOG=/var/tmp/manual_sw_config_push.log
DONE=/var/tmp/manual_sw_config_push_done
rm -f "$DONE"
exec > "$LOG" 2>&1

# SNMP v3 + OIDs (vdsrail; verify vs /etc/obn/vendors.yaml per train)
SNMP="-v3 -u snmpadmin -l authPriv -a SHA -A NomadStayOut! -x AES -X NomadStayOut!"
OID_TFTP_LOC=".1.3.6.1.4.1.8072.1.3.2.2.1.3.7.108.111.97.100.117.114.108"
OID_TRIGGER=".1.3.6.1.4.1.8072.1.3.2.2.1.7.7.108.111.97.100.117.114.108"
OID_TASK=".1.3.6.1.4.1.8072.1.3.2.3.1.2.9.99.104.101.99.107.116.97.115.107"
OID_GET_HOST=".1.3.6.1.2.1.1.5.0"
OID_SET_HOST="1.3.6.1.4.1.8072.1.3.2.2.1.3.6.114.101.98.111.111.116"
OID_REBOOT=".1.3.6.1.4.1.8072.1.3.2.2.1.7.6.114.101.98.111.111.116"

echo "=== manual sw config push START $(date) (Fzg $FZG, CCU .$CCU_OCTET) ==="

# 3 CCU-side bypasses (OBN normally does these; runtime-only)
modprobe nf_conntrack_tftp
iptables -t raw -C PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp 2>/dev/null \
  || iptables -t raw -I PREROUTING -i vlan100 -p udp --dport 69 -j CT --helper tftp
iptables -C MGMTI -p udp --dport 69 -j ACCEPT 2>/dev/null \
  || iptables -I MGMTI 1 -p udp --dport 69 -j ACCEPT
mkdir -p "$UPLOAD"
echo "bypasses applied"

push_one() {
  local ip="$1" mac="$2" stem="$3"
  local fname="${stem}-${mac//:/}.cfg"
  echo "----- $ip ($stem) -----"

  STEM="$stem" OUT="$UPLOAD/$fname" TID="$FZG" $RENDER <<'PYEOF'
import os
from jinja2 import Environment, FileSystemLoader, StrictUndefined
env=Environment(loader=FileSystemLoader("/etc/obn/template"),autoescape=False,undefined=StrictUndefined)
o=env.get_template(os.environ["STEM"]+".cfg").render(train_id=int(os.environ["TID"]))
open(os.environ["OUT"],"w").write(o)
PYEOF
  [ -s "$UPLOAD/$fname" ] || { echo "  RENDER FAILED — skip"; return 1; }
  # STRIP '#' comment lines — the VDS switch CLI rejects them ('param is "#" [wrong]')
  # and a single '#' line fails the whole config-test ("Error testing ... at line N").
  # This is what breaks the fv5 COUPLER templates (A1/A3/B1/B3 have '# v9:' comments)
  # and is also why OBN's own update c fails on those switches. Validated box1-t41 2026-07-07.
  grep -vE '^[[:space:]]*#' "$UPLOAD/$fname" > "$UPLOAD/$fname.nc" && mv "$UPLOAD/$fname.nc" "$UPLOAD/$fname"
  local hn; hn=$(grep -m1 "system hostname" "$UPLOAD/$fname" | awk '{print $3}')
  echo "  rendered $fname (hostname=$hn, $(wc -l < "$UPLOAD/$fname") lines)"

  ipset add tftp_allowed "$ip" 2>/dev/null || true
  snmpset $SNMP "$ip" "$OID_TFTP_LOC" s "tftp://${SRC}/upload/${fname}" >/dev/null 2>&1
  snmpset $SNMP "$ip" "$OID_TRIGGER" i 3 >/dev/null 2>&1

  local ok=0
  for i in $(seq 1 20); do
    sleep 2
    local st; st=$(snmpget $SNMP -Ovq "$ip" "$OID_TASK" 2>/dev/null)
    echo "    task[$i]: $st"
    echo "$st" | grep -qi "configuration .* loaded" && { ok=1; break; }
    echo "$st" | grep -qi "Last error" && { echo "  LOAD ERROR"; return 1; }
  done
  [ "$ok" = 1 ] || { echo "  load did not confirm — skip reboot"; return 1; }

  local cur; cur=$(snmpget $SNMP -Ovq "$ip" "$OID_GET_HOST" 2>/dev/null | tr -d '"')
  snmpset $SNMP "$ip" "$OID_SET_HOST" s "$cur" >/dev/null 2>&1   # commit trigger (required)
  snmpset $SNMP "$ip" "$OID_REBOOT" i 3 >/dev/null 2>&1
  echo "  reboot triggered; waiting for $hn ..."

  for i in $(seq 1 24); do
    sleep 5
    local nh; nh=$(snmpget $SNMP -Ovq "$ip" "$OID_GET_HOST" 2>/dev/null | tr -d '"')
    [ "$nh" = "$hn" ] && { echo "  OK $ip now $nh"; return 0; }
  done
  echo "  WARN $ip did not confirm new hostname (re-push this one)"
  return 1
}

while read -r ip mac stem; do
  [ -z "${ip:-}" ] && continue
  case "$ip" in \#*) continue;; esac
  push_one "$ip" "$mac" "$stem"
done < "$SWITCHES_FILE"

echo "=== manual sw config push DONE $(date) ==="
touch "$DONE"
