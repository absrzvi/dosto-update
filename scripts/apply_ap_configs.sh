#!/bin/bash
# Apply pending Nomad config on all APs via LuCI rpcCfgApply
# Run after configs have been uploaded via Import Configuration

PASS="Nom%40dCome1n"

APS=(
  "10.179.49.90 00145a04b04f"
  "10.179.49.91 00145a04b501"
  "10.179.49.92 00145a04b384"
  "10.179.49.93 00145a04b46a"
  "10.179.49.94 00145a04b350"
  "10.179.49.95 00145a04b3b9"
  "10.179.49.96 00145a04ad9e"
  "10.179.49.97 00145a04b2f4"
  "10.179.49.98 00145a04b4b9"
  "10.179.49.99 00145a04b482"
  "10.179.49.100 00145a04b415"
  "10.179.49.101 00145a04b3a9"
  "10.179.49.102 00145a04b3a5"
  "10.179.49.103 00145a04b37c"
  "10.179.49.104 00145a04b378"
  "10.179.49.105 00145a04b28e"
)

apply_config() {
  local IP=$1
  local COOK="/tmp/ck_apply_${IP}.txt"

  rm -f "$COOK"
  local CODE
  CODE=$(curl -s -k -c "$COOK" -b "$COOK" \
    -X POST "https://${IP}/cgi-bin/luci/" \
    -d "luci_username=admin&luci_password=${PASS}" \
    -o /dev/null -w '%{http_code}' --connect-timeout 8 --max-time 12 2>/dev/null)

  if [ "$CODE" != "302" ]; then
    echo "[$(date '+%H:%M:%S')] $IP: login failed (HTTP $CODE)"
    rm -f "$COOK"
    return 1
  fi

  # Check if there are pending changes
  local TITLE
  TITLE=$(curl -s -k -c "$COOK" -b "$COOK" "https://${IP}/cgi-bin/luci/" \
    --connect-timeout 8 --max-time 12 2>/dev/null | grep '<title>' | head -1)

  if echo "$TITLE" | grep -q 'Config Alert'; then
    # Apply pending config
    local RESP
    RESP=$(curl -s -k -c "$COOK" -b "$COOK" \
      -X POST "https://${IP}/cgi-bin/luci/admin/rpc" \
      -H 'Content-Type: application/json' \
      -d '{"key":"rpcCfgApply","value":1}' \
      -o /tmp/rpc_resp.txt -w '%{http_code}' --connect-timeout 8 --max-time 15 2>/dev/null)
    echo "[$(date '+%H:%M:%S')] $IP: rpcCfgApply HTTP $RESP - device rebooting"
  else
    echo "[$(date '+%H:%M:%S')] $IP: no pending config, title: $TITLE"
  fi

  rm -f "$COOK"
}

echo "=== Applying configs on all APs ==="
for entry in "${APS[@]}"; do
  IP=$(echo "$entry" | cut -d' ' -f1)
  apply_config "$IP"
  sleep 1
done

echo ""
echo "=== Waiting for all APs to reboot and come back ==="
for entry in "${APS[@]}"; do
  IP=$(echo "$entry" | cut -d' ' -f1)
  echo -n "Waiting for $IP ..."
  until ping -c 1 -W 2 "$IP" >/dev/null 2>&1; do
    echo -n "."
    sleep 5
  done
  echo " UP"
done

echo ""
echo "=== Checking SNMP on all APs ==="
cd /usr/share/obn && sudo venv/bin/python3 -c "
from pysnmp.hlapi import *
ips = [
  '10.179.49.90','10.179.49.91','10.179.49.92','10.179.49.93',
  '10.179.49.94','10.179.49.95','10.179.49.96','10.179.49.97',
  '10.179.49.98','10.179.49.99','10.179.49.100','10.179.49.101',
  '10.179.49.102','10.179.49.103','10.179.49.104','10.179.49.105'
]
ok=0; fail=0
for ip in ips:
    for g in getCmd(SnmpEngine(), CommunityData('NomadStayOut!'), UdpTransportTarget((ip,161),timeout=3,retries=1), ContextData(), ObjectType(ObjectIdentity('.1.3.6.1.4.1.16177.1.400.1.1.1.1.0')), lookupMib=False):
        ei,es,_,vb = g
        if ei or es:
            print(f'  {ip}: SNMP FAIL')
            fail+=1
        else:
            print(f'  {ip}: SNMP OK - {str(vb[0][1])}')
            ok+=1
        break
print(f'Result: {ok}/16 APs responding to SNMP')
"
