#!/bin/bash
# Push Nomad config to all 16 Westermo APs via LuCI HTTP import

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

for entry in "${APS[@]}"; do
  IP=$(echo "$entry" | cut -d' ' -f1)
  MAC=$(echo "$entry" | cut -d' ' -f2)
  /tmp/push_ap_config.sh "$IP" "$MAC"
  echo "--- waiting 65s for $IP to reboot and come back ---"
  until ping -c 1 -W 2 "$IP" >/dev/null 2>&1; do sleep 5; done
  echo "[$(date '+%H:%M:%S')] $IP is back up"
done

echo "All APs done. Running obn validate..."
sudo obn validate
