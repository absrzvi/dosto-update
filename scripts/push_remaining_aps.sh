#!/bin/bash
# Push Nomad config to remaining 14 APs (AP1=.94 and AP2=.99 already done)
# Push all, then wait for all to come back

PASS="Nom@dCome1n"

APS=(
  "10.179.49.90 00145a04b04f"
  "10.179.49.91 00145a04b501"
  "10.179.49.92 00145a04b384"
  "10.179.49.93 00145a04b46a"
  "10.179.49.95 00145a04b3b9"
  "10.179.49.96 00145a04ad9e"
  "10.179.49.97 00145a04b2f4"
  "10.179.49.98 00145a04b4b9"
  "10.179.49.100 00145a04b415"
  "10.179.49.101 00145a04b3a9"
  "10.179.49.102 00145a04b3a5"
  "10.179.49.103 00145a04b37c"
  "10.179.49.104 00145a04b378"
  "10.179.49.105 00145a04b28e"
)

echo "=== Phase 1: Push config to all APs ==="
for entry in "${APS[@]}"; do
  IP=$(echo "$entry" | cut -d' ' -f1)
  MAC=$(echo "$entry" | cut -d' ' -f2)
  /tmp/push_ap_config.sh "$IP" "$MAC"
  sleep 2
done

echo ""
echo "=== Phase 2: Waiting for all APs to reboot and come back ==="
ALL_IPS="10.179.49.90 10.179.49.91 10.179.49.92 10.179.49.93 10.179.49.94 10.179.49.95 10.179.49.96 10.179.49.97 10.179.49.98 10.179.49.99 10.179.49.100 10.179.49.101 10.179.49.102 10.179.49.103 10.179.49.104 10.179.49.105"

for IP in $ALL_IPS; do
  echo -n "Waiting for $IP ..."
  until ping -c 1 -W 2 "$IP" >/dev/null 2>&1; do
    echo -n "."
    sleep 5
  done
  echo " UP"
done

echo ""
echo "=== All APs back online. Running obn validate ==="
sudo obn validate
