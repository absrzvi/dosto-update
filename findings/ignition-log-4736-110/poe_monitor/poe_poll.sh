#!/bin/bash
# poe_poll.sh — periodically SSH each VDS switch, read `show poe` + link state, and cache a
# per-port PoE-vs-link status to /data. The Zabbix UserParameter reads the CACHE (instant) so
# the agent never blocks on the slow switch SSH. Decoupled poller pattern (like netdrop/vign).
#
# WHY: the switches do NOT expose PoE status over SNMP (standard POWER-ETHERNET-MIB absent; vendor
# only exposes PoE control actions). So the existing SNMP ifOperStatus alarm can't tell a PoE
# failure (powered device lost power) from a plain link-down (cable/peer). This poller adds the
# PoE status so a trigger can distinguish them.
#
# Per port on a PoE-capable port that is DOWN:
#   poe=off/fault  -> PoE FAILURE (device lost power)
#   poe=on         -> LINK DOWN (cable/peer; PoE fine)
#
# Output: /data/poe-monitor/poe_status.json  — one object per switch:
#   { "<sw_ip>": { "iso":"...", "ports":{ "e1-0":{"poe":"on","link":"up"}, ... } }, ... }
# Plus a rolled-up worst-case code the Zabbix reader turns into an alarm.
#
# Run cadence: every ~5 min via cron/timer. Switch CLI = one command per SSH session (slow) — we
# do 2 sessions per switch (show poe + show interface summary). Keep the switch list SMALL if load
# is a concern; default = all VDS switches from dhcp-lease-list.
set -u
OUT=/data/poe-monitor
JSON="$OUT/poe_status.json"
PW='Nom@dCome1n'
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=6 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"
mkdir -p "$OUT"

# switch IPs: VDS OUI a0:59:3a on vlan100. Prefer live ARP neighbours (IP is field 1 there);
# fall back to dhcp-lease-list (IP is field 2, MAC is field 1). Take only dotted-quad tokens.
switches=$(ip neigh show dev vlan100 2>/dev/null | awk '/a0:59:3a/{print $1}' | grep -E '^[0-9.]+$' | sort -u)
[ -z "$switches" ] && switches=$(sudo dhcp-lease-list 2>/dev/null | awk '/a0:59:3a/{print $2}' | grep -E '^[0-9.]+$' | sort -u)

iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Collect this cycle's raw per-switch, per-port poe+link into a temp file the Python step reads.
RAW="$OUT/.raw.$$"; : > "$RAW"
for sw in $switches; do
  poe=$(sshpass -p "$PW" ssh $SSH_OPTS admin@"$sw" "show poe" 2>/dev/null | grep -E "^e[01]-")
  [ -z "$poe" ] && continue   # switch unreachable / no PoE table -> skip (keep prior cache entry)
  lnk=$(sshpass -p "$PW" ssh $SSH_OPTS admin@"$sw" "show interface summary" 2>/dev/null | grep -E "^e[01]-")
  while read -r port pmode pstat prest; do
    [ -z "$port" ] && continue
    linkst=$(echo "$lnk" | awk -v p="$port" '$1==p{print $4}')   # field 4 = Line = up/down
    [ -z "$linkst" ] && linkst="?"
    echo "$sw|$port|$pstat|$linkst" >> "$RAW"
  done <<< "$poe"
done

# Python: merge with previous cache to detect on->off transitions (poe_lost flag).
# poe_lost latches until the port's link comes back up (link=up clears it) OR poe returns on.
python3 - "$JSON" "$RAW" "$iso" <<'PY'
import json,sys,os
cache_path,raw_path,iso=sys.argv[1],sys.argv[2],sys.argv[3]
prev={}
if os.path.exists(cache_path):
    try: prev=json.load(open(cache_path))
    except: prev={}
cur={}
for line in open(raw_path):
    line=line.rstrip("\n")
    if not line: continue
    sw,port,poe,link=line.split("|")
    p_prev=prev.get(sw,{}).get("ports",{}).get(port,{})
    prev_poe=p_prev.get("poe"); prev_flag=p_prev.get("flag","")
    flag=""
    # a device that WAS being powered (prev poe=on) now shows off -> PoE lost (failure)
    if prev_poe=="on" and poe=="off":
        flag="poe_lost"
    # latch: keep poe_lost until link recovers or poe returns on (avoids flapping the alarm)
    elif prev_flag=="poe_lost" and not (link=="up" or poe=="on"):
        flag="poe_lost"
    cur.setdefault(sw,{"iso":iso,"ports":{}})
    cur[sw]["iso"]=iso
    cur[sw]["ports"][port]={"poe":poe,"link":link,"flag":flag}
# carry forward switches we couldn't reach this cycle (so a transient SSH miss doesn't drop state)
for sw,d in prev.items():
    if sw not in cur: cur[sw]=d
tmp=cache_path+".tmp"
json.dump(cur,open(tmp,"w"))
os.replace(tmp,cache_path)
PY
rm -f "$RAW"
logger -t nd-poe-poll "poe poll done: $(echo "$switches" | wc -w) switches"
