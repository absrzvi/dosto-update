#!/bin/bash
# check_netdrop.sh — Zabbix UserParameter helper. Reads the LATEST netdrop.csv row and
# emits a single integer status for the "Stadler connectivity while online" alarm:
#
#   0 = OK        (Stadler path healthy while online, OR train legitimately offline/parked)
#   1 = VLAN7_DOWN  (vlan7 L2 link to the Stadler FW is down while the train is online)
#   2 = RDS_DOWN    (vlan7 up but the RDS VPN flow to the Stadler backend is down, while online)
#
# "while online" gate = tun_up=1 AND links_up>=1. If the train is offline (tunnel/cellular
# down) we return 0 here on purpose — that's a separate signal (whole-train offline), not a
# Stadler-path fault, and alarming on it would just duplicate the existing ICMP-down alarm.
#
# Read-only. Safe to run as the zabbix user (netdrop.csv is world-readable).
# netdrop.csv columns: iso_utc,reason,tun_up,default_route,rds_flow,links_up,vlan7_fw,fw_ip,link_detail,mm_detail
set -u
CSV=/data/netdrop-log/netdrop.csv

# last non-empty data row (skip header + 'start' boot rows which have empty fields)
row=$(awk -F, 'NF>=8 && $1!="iso_utc" && $2!="start" {last=$0} END{print last}' "$CSV" 2>/dev/null)
[ -z "$row" ] && { echo 0; exit 0; }   # no data yet -> not an alarm

tun_up=$(echo "$row"   | cut -d, -f3)
rds=$(echo "$row"      | cut -d, -f5)
links_up=$(echo "$row" | cut -d, -f6)
vlan7=$(echo "$row"    | cut -d, -f7)

# stale-data guard: if the last row is older than 5 min, the logger/CCU may be down ->
# don't assert a Stadler fault on stale data; return 0 (whole-train-down is covered elsewhere).
last_iso=$(echo "$row" | cut -d, -f1)
last_epoch=$(date -u -d "${last_iso/Z/}" +%s 2>/dev/null || echo 0)
now=$(date -u +%s)
if [ "$last_epoch" -gt 0 ] && [ $((now - last_epoch)) -gt 300 ]; then echo 0; exit 0; fi

# online gate
if [ "$tun_up" != "1" ] || [ -z "$links_up" ] || [ "$links_up" -lt 1 ] 2>/dev/null; then
  echo 0; exit 0
fi

# online: check the Stadler legs
if [ "$vlan7" = "0" ]; then echo 1; exit 0; fi         # L2 down
if [ "$rds" = "0" ]; then echo 2; exit 0; fi           # L3 (RDS VPN) down while L2/tunnel up
echo 0
