#!/bin/bash
# netdrop_poll.sh — durable tunnel/uplink drop logger for MAR5 CCUs.
# Purpose: give the NEXT disputed-availability period clean, purpose-built evidence for
# WHY the RDS/VPN tunnel dropped when it was NOT a power cut (the power logger covers power).
# Companion to vign_poll.sh. Writes to /data (survives reboot). Read-only w.r.t. the system.
#
# What it records, every INTERVAL seconds, one CSV row:
#   - per-modem link state (ce0p0..ce3p0 carrier-up? has-IP?), from `ip -o addr`
#   - ModemManager per-modem state + access-tech + signal (if mmcli present)
#   - whether the RDS app flow to the RDS host is present in conntrack (tunnel actually carrying)
#   - default route present / mar5-tun up
#   - vlan7 FW reachability: is the Stadler firewall an ARP-REACHABLE neighbour on vlan7?
#     (the raw vlan7 link to Stadler, distinct from the tunnel-carried RDS app flow above).
#     Uses ARP state NOT ICMP — a commissioned Stadler FW drops ICMP by policy (CLAUDE.md Phase 6
#     Q1), so ping would false-negative; ARP REACHABLE is the correct "is the FW there" signal.
# On ANY change vs the previous sample it writes a row tagged 'change'; plus a heartbeat row
# every HB seconds so the last sample before a drop is recent.
#
# Classification is done OFFLINE by netdrop_analyze.py — this script only records facts.
set -u
OUT=/data/netdrop-log
CSV="$OUT/netdrop.csv"
INTERVAL="${INTERVAL:-5}"       # sample cadence (s)
HB="${HB:-60}"                  # heartbeat row cadence (s)
RDS_HOST="${RDS_HOST:-62.2.130.53}"   # RDS application endpoint (per-train; 110 = 62.2.130.53)
MODEMS="ce0p0 ce1p0 ce2p0 ce3p0"
TUN="mar5-tun"
VLAN7="vlan7"

mkdir -p "$OUT"
if [ ! -f "$CSV" ]; then
  echo "iso_utc,reason,tun_up,default_route,rds_flow,links_up,vlan7_fw,fw_ip,link_detail,mm_detail" >> "$CSV"
fi

# Derive the Stadler FW address on vlan7 WITHOUT hardcoding (per-train). The CCU's own vlan7
# host is .130 (odd Fzg) or .2 (even Fzg); the FW is one less (.129) or .1 respectively. We
# don't need the parity: the FW is simply the existing vlan7 neighbour that is NOT our own IP.
# Fallback if no neighbour yet: CCU_vlan7_last_octet - 1 (covers the .130->.129 case) else .1.
derive_fw() {
  local myip fw
  myip=$(ip -o -4 addr show "$VLAN7" 2>/dev/null | grep -oE "inet [0-9.]+" | awk '{print $2}' | head -1)
  [ -z "$myip" ] && { echo ""; return; }
  # prefer an existing non-self neighbour on vlan7 (the FW answers ARP)
  fw=$(ip neigh show dev "$VLAN7" 2>/dev/null | grep -vE "$myip" | grep -oE "^[0-9.]+" | head -1)
  if [ -n "$fw" ]; then echo "$fw"; return; fi
  # else compute: last octet - 1 (works for .130->.129); if that underflows use .1 of the /17
  local a b c d; IFS=. read -r a b c d <<< "$myip"
  if [ "$d" -gt 1 ] 2>/dev/null; then echo "$a.$b.$c.$((d-1))"; else echo "$a.$b.$c.1"; fi
}
FW_IP="$(derive_fw)"

prev_sig=""
last_hb=0

sample() {
  local now iso tun_up defr rds links_up detail mm reason sig vlan7_fw
  now=$(date -u +%s); iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # tunnel iface up?
  if ip link show "$TUN" 2>/dev/null | grep -q "state \(UP\|UNKNOWN\)"; then tun_up=1; else tun_up=0; fi
  # default route present?
  if ip route show default 2>/dev/null | grep -q .; then defr=1; else defr=0; fi
  # RDS app flow present in conntrack? (tunnel actually carrying app traffic)
  if command -v conntrack >/dev/null 2>&1 && sudo conntrack -L 2>/dev/null | grep -q "$RDS_HOST"; then rds=1; else rds=0; fi

  # vlan7 FW reachability: is the Stadler FW an ARP-REACHABLE/STALE neighbour on vlan7?
  # 1 = FW present (REACHABLE or STALE = we have its MAC, link to Stadler up)
  # 0 = FAILED/absent/no-entry (vlan7 link to Stadler down) ; "-" = no FW_IP known.
  # Re-derive FW_IP each sample in case vlan7 re-addressed (cheap). Nudge ARP with a 1-pkt
  # ping so the neighbour state stays fresh even though the FW itself won't reply (ICMP dropped
  # by policy) — the ARP resolution still happens at L2.
  local fw
  fw="$FW_IP"; [ -z "$fw" ] && fw="$(derive_fw)"
  if [ -n "$fw" ]; then
    ping -c1 -W1 -I "$VLAN7" "$fw" >/dev/null 2>&1   # nudge ARP only; reply not expected
    if ip neigh show "$fw" dev "$VLAN7" 2>/dev/null | grep -qiE "REACHABLE|STALE|DELAY|PROBE"; then
      vlan7_fw=1
    else
      vlan7_fw=0
    fi
  else
    vlan7_fw="-"; fw="-"
  fi

  # per-modem: has an IPv4 on its carrier iface? capture the IP too, so a carrier
  # RE-ADDRESS (new IP on the same modem = the churn driver) shows as a change row.
  links_up=0; detail=""
  for m in $MODEMS; do
    mip=$(ip -o -4 addr show "$m" 2>/dev/null | grep -oE "inet [0-9.]+" | awk '{print $2}' | head -1)
    if [ -n "$mip" ]; then st=1; links_up=$((links_up+1)); else st=0; mip="-"; fi
    detail="${detail}${m}:${st}:${mip} "
  done
  detail="${detail% }"

  # ModemManager per-modem state + access tech (best-effort; skip if mmcli missing)
  mm=""
  if command -v mmcli >/dev/null 2>&1; then
    for idx in $(mmcli -L 2>/dev/null | grep -oE "/Modem/[0-9]+" | grep -oE "[0-9]+$"); do
      s=$(mmcli -m "$idx" 2>/dev/null | grep -E "state:|access tech" | tr -d ' ' | tr '\n' '/' )
      mm="${mm}m${idx}=${s};"
    done
  fi

  sig="${tun_up}|${defr}|${rds}|${links_up}|${vlan7_fw}|${detail}"
  reason="hb"
  if [ "$sig" != "$prev_sig" ]; then reason="change"; fi

  if [ "$reason" = "change" ] || [ $(( now - last_hb )) -ge "$HB" ]; then
    echo "${iso},${reason},${tun_up},${defr},${rds},${links_up},${vlan7_fw},${fw},\"${detail}\",\"${mm}\"" >> "$CSV"
    last_hb=$now
  fi
  prev_sig="$sig"
}

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),start,,,,,,,\"boot\",\"\"" >> "$CSV"
while true; do sample; sleep "$INTERVAL"; done
