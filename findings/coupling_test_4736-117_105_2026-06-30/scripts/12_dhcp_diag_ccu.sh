#!/usr/bin/env bash
# 12_dhcp_diag_ccu.sh — F4 DHCP diagnostic, CCU-SIDE capture (READ-ONLY).
#
# WHY: the 2026-06-30 coupled test showed ~9/18 of 117's switches loop
#   DISCOVER -> OFFER -> (no REQUEST, no ACK) -> DISCOVER while coupled, and
#   recover on decouple (finding F4). The server log proves a SINGLE server
#   (one server-id, no 105 offers crossed) and the failure is BETWEEN the
#   server's OFFER and the switch's REQUEST. This script instruments the
#   CCU side of that gap. Pair it with 13_dhcp_mirror_switch.sh, which
#   instruments the SWITCH side at the same time, so we can localise:
#     * OFFER leaves CCU but never seen at switch  -> lost in coupled fabric
#     * OFFER seen at switch, no REQUEST emitted    -> switch DHCP client
#     * REQUEST emitted at switch, never reaches CCU-> lost on return path
#
# Runs ON THE CCU.  Nothing here mutates switch or CCU config.
#
# Usage:
#   ./12_dhcp_diag_ccu.sh                 # capture ALL switch DHCP, 600s
#   ./12_dhcp_diag_ccu.sh <MAC> 300       # focus one switch MAC, 300s
#   (run once COUPLED, once again after DECOUPLE, for A/B comparison)

set -u
. "$(dirname "$0")/_common.sh"

FOCUS_MAC="${1:-}"           # optional: a0:59:3a:d0:5b:20
DUR="${2:-600}"             # seconds
OUT="/var/tmp/f4_ccu_$(date -u +%Y%m%d_%H%M%S)"
mkdir -p "$OUT"

echo "=== F4 CCU-side DHCP diagnostic ==="
echo "    output dir : $OUT"
echo "    duration   : ${DUR}s"
[ -n "$FOCUS_MAC" ] && echo "    focus MAC  : $FOCUS_MAC" || echo "    focus MAC  : (all switches)"
echo "    state NOW  : $(ts)  -- LABEL THIS RUN coupled/decoupled in your notes"
echo ""

# (1) lease baseline — how many switches actually hold a lease right now
echo "--- switch lease count (a0:59:3a) at start ---"
sudo dhcp-lease-list 2>/dev/null | grep -i "a0:59:3a" | sort | tee "$OUT/leases_start.txt" | wc -l

# (2) confirm single server / catch any rogue: list distinct server-ids offering
echo "--- (will summarise server-ids from the capture at the end) ---"

# (3) the capture — full DORA frames on the mgmt VLAN, with ethernet + timestamps.
#     -e ethernet hdr (see src/dst MAC), -tttt wallclock, -s0 full packet.
FILTER='(udp and (port 67 or port 68))'
[ -n "$FOCUS_MAC" ] && FILTER="$FILTER and ether host $FOCUS_MAC"
echo "--- tcpdump vlan100 : $FILTER ---"
echo "    (Ctrl-C to stop early; pcap saved for offline analysis)"
sudo tcpdump -ni vlan100 -e -tttt -s0 -w "$OUT/dhcp.pcap" "$FILTER" &
TPID=$!
# human-readable tail alongside the pcap
sudo timeout "$DUR" tcpdump -ni vlan100 -e -tttt -s0 "$FILTER" \
  | tee "$OUT/dhcp_readable.txt"
kill "$TPID" 2>/dev/null

# (4) post-capture summary: per-MAC DORA stage tally (who looped vs completed)
echo ""
echo "--- per-switch DORA tally (D=Discover O=Offer R=Request A=Ack) ---"
python3 - "$OUT/dhcp_readable.txt" <<'PYEOF'
import sys, re, collections
stages=collections.defaultdict(lambda: collections.Counter())
srvids=collections.Counter()
for line in open(sys.argv[1], errors='ignore'):
    l=line.lower()
    full=re.findall(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', line)
    cli=None
    # client switch MAC = a0:59:3a... if present
    for m in full:
        if m.lower().startswith('a0:59:3a'): cli=m.lower(); break
    if not cli: continue
    if 'discover' in l: stages[cli]['D']+=1
    elif 'offer'  in l: stages[cli]['O']+=1
    elif 'request' in l: stages[cli]['R']+=1
    elif 'ack'    in l: stages[cli]['A']+=1
    m=re.search(r'server-id[:\s]+(\d+\.\d+\.\d+\.\d+)', l)
    if m: srvids[m.group(1)]+=1
print(f"  distinct server-ids seen: {dict(srvids) or 'n/a (parse from pcap if empty)'}")
print(f"  {'switch MAC':20} D   O   R   A   verdict")
for mac,c in sorted(stages.items()):
    D,O,R,A=c['D'],c['O'],c['R'],c['A']
    if A>0: v="OK (leased)"
    elif O>0 and R==0: v=">>> F4 LOOP (offer, no request)"
    elif R>0 and A==0: v="request sent, no ack (return-path?)"
    else: v="incomplete"
    print(f"  {mac:20} {D:<3} {O:<3} {R:<3} {A:<3} {v}")
PYEOF

echo ""
echo "=== done. pcap: $OUT/dhcp.pcap  readable: $OUT/dhcp_readable.txt ==="
echo "    Compare a COUPLED run vs a DECOUPLED run. The F4 LOOP rows are the"
echo "    affected switches. Cross-reference their MACs with 13_dhcp_mirror"
echo "    switch-side capture to localise the OFFER->REQUEST gap."
