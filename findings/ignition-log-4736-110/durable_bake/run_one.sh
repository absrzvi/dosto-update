#!/bin/bash
# run_one.sh <ccu-ip> <runtime:0|1>  — stage + (optional runtime install) + durable bake + verify. NO reboot.
set -u
IP="$1"; RUNTIME="${2:-0}"
KEY="C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh"
STAGE="C:/Users/ABBASR~1/AppData/Local/Temp/claude/C--Users-AbbasRizvi-Documents-dosto-troubleshooting/0b48415e-dedd-49a6-adfe-d1695c45c30a/scratchpad/logger_deploy"
S(){ ssh -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=10 developer@"$IP" "$@"; }
echo "############## $IP (runtime=$RUNTIME) ##############"
# stage
S 'rm -rf /tmp/logger_payload && mkdir -p /tmp/logger_payload' 2>&1
scp -i "$KEY" -o StrictHostKeyChecking=no \
  "$STAGE"/vign_poll.sh "$STAGE"/shutdown_marker.sh "$STAGE"/hardcut_classify.sh "$STAGE"/netdrop_poll.sh \
  "$STAGE"/check-netdrop.sh "$STAGE"/check-hardcut.sh "$STAGE"/check_netdrop.conf "$STAGE"/check_hardcut.conf \
  "$STAGE"/netdrop-poll.service "$STAGE"/nd-hardcut-classify.service "$STAGE"/bake_in_chroot.sh \
  "$STAGE"/durable_bake_driver.sh "$STAGE"/install.sh \
  developer@"$IP":/tmp/logger_payload/ >/dev/null 2>&1
echo "[$IP] staged $(S 'ls /tmp/logger_payload | wc -l' 2>/dev/null) files"
# optional runtime install (bare CCUs) so it's live immediately + reset baseline
if [ "$RUNTIME" = "1" ]; then
  echo "[$IP] runtime install..."
  S 'sudo cp -f /tmp/logger_payload/install.sh /tmp/logger_payload/ && sudo mkdir -p /tmp/logger_deploy && sudo cp -f /tmp/logger_payload/* /tmp/logger_deploy/ && sudo bash /tmp/logger_deploy/install.sh 2>&1 | tail -6' 2>&1
  S 'sudo tee /data/ignition-log/hardcut-state.json >/dev/null << J
{"total":0,"last_event_iso":"baseline-reset","last_was_hardcut":0,"last_boot_iso":"pending","prev_loss_iso":""}
J' 2>&1
fi
# durable bake (detached)
echo "[$IP] baking (detached)..."
S 'sudo rm -f /tmp/bake.log; sudo bash -c "setsid bash /tmp/logger_payload/durable_bake_driver.sh > /tmp/bake.log 2>&1 < /dev/null &"' 2>&1
