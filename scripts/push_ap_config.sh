#!/bin/bash
# Push Nomad config to Westermo APs via LuCI HTTP import
# Usage: push_ap_config.sh <ip> <mac_slug>
# mac_slug = MAC without colons, lowercase

IP=$1
MAC=$2
CONFIG="/data/auto-topology/upload/dostoneu-obn-${MAC}.cfg"
COOKIES="/tmp/cookies_${IP}.txt"
PASS="Nom@dCome1n"

rm -f "$COOKIES"

echo "[$(date '+%H:%M:%S')] $IP: authenticating..."
HTTP_CODE=$(curl -s -k -c "$COOKIES" -b "$COOKIES" \
  -X POST "https://${IP}/cgi-bin/luci/" \
  -d "luci_username=admin&luci_password=${PASS}" \
  -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 15)

if [ "$HTTP_CODE" != "302" ]; then
  echo "[ERROR] $IP: login failed (HTTP $HTTP_CODE)"
  exit 1
fi

echo "[$(date '+%H:%M:%S')] $IP: uploading config $CONFIG ..."
HTTP_CODE=$(curl -s -k -c "$COOKIES" -b "$COOKIES" \
  -X POST "https://${IP}/cgi-bin/luci/admin/system/flashops" \
  -F "config=@${CONFIG};type=text/plain" \
  -F "Import=Import Configuration" \
  -o /dev/null -w '%{http_code}' --connect-timeout 10 --max-time 30)

echo "[$(date '+%H:%M:%S')] $IP: upload done (HTTP $HTTP_CODE) - device will reboot"
rm -f "$COOKIES"
