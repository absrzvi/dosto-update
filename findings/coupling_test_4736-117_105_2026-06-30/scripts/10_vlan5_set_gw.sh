#!/usr/bin/env bash
# 10 — Part 2: ECHO the backup-train VLAN-5 gateway repoint.
# ECHO-ONLY: prints the change, runs nothing.
#
# Mechanism (CONFIRMED from nv6 templates): cameras are DHCP clients of the switch; the gateway is
# the `default-router` option in the `video` DHCP client-group (dhcp_groups/video_group.j2) — NOT a
# per-port line. So the change is to the BACKUP train's `video` group default-router:
#     172.18.194.129 (backup own FW)  ->  172.18.200.129 (master FW)
#
# CLI VERIFIED from Consist Switch User Manual v2.0.4 (line 4597):
#     [ no ] configure ip dhcp-server group NAME default-router ADDRESS
# So the per-switch edit is:
#     configure ip dhcp-server group video default-router 172.18.200.129
# Sanity-read the live group first to confirm the current value:
#     swcmd $SW "show running-config" | grep -A8 "dhcp-server group video"
#
# Run AGAINST THE BACKUP TRAIN (4736-105 / Fzg 133) cab+coach switches that host VLAN-5 cameras.
# Usage: ./10_vlan5_set_gw.sh <backup-sw-ip-1> [<backup-sw-ip-2> ...]
set -u
. "$(dirname "$0")/_common.sh"

if [ $# -lt 1 ]; then
  echo "usage: $0 <backup-sw-ip-1> [ip2 ...]   (backup train switches hosting VLAN-5 cameras)"; exit 1
fi

echo "=== ECHO ONLY — backup-train VLAN-5 default-router: $BACKUP_FW_VLAN5 -> $MASTER_FW_VLAN5 ==="
echo "=== STEP 0: read the live group form on ONE switch first ==="
echo "  sshpass -p '$SW_PASS' ssh \$SSH_OPTS admin@$1 \"show running-config\" | grep -A8 'dhcp-server group video'"
echo
echo "=== STEP 1: per backup switch, set the video group default-router to the master FW ==="
for ip in "$@"; do
  echo_cmd "video group default-router -> master FW ($MASTER_FW_VLAN5)" "$ip" \
    "configure ip dhcp-server group video default-router $MASTER_FW_VLAN5"
done

echo "=== STEP 2: force lease renewal so cameras pick up the new gateway ==="
echo "  Cameras keep the old gateway until lease renews. Bounce each VLAN-5 camera port:"
echo "    swcmd \$SW \"configure interface <cam-port> no enable\"   # then re-enable"
echo "    swcmd \$SW \"configure interface <cam-port> enable\""
echo "  (or wait out the DHCP lease). Verify a camera's gateway after renewal."
echo
echo ">> Then run 11_latency_matrix.sh for stage S1."
echo ">> STADLER DEPENDENCY: master FW must have a return route to 172.18.194.0/24"
echo ">>   (works if its VLAN-5 iface is the /17; else Stadler adds the route)."
