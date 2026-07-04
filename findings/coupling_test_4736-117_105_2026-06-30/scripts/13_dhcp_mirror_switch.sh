#!/usr/bin/env bash
# 13_dhcp_mirror_switch.sh — F4 DHCP diagnostic, SWITCH-SIDE capture.
#
# Pairs with 12_dhcp_diag_ccu.sh. The CCU log proves the OFFER is SENT and the
# switch never sends a REQUEST. The only way to know WHICH leg breaks is to look
# at the wire AT THE VICTIM SWITCH. We port-mirror the victim's uplink (its root
# port, toward the CCU) onto a spare access port, plug a laptop/capture box into
# that access port, and capture. Then read against the CCU capture:
#
#   OFFER not seen at switch          -> lost in coupled fabric (our L2 / RSTP)
#   OFFER seen, no REQUEST emitted     -> switch DHCP CLIENT wedged (-> VDS)
#   REQUEST emitted, absent at CCU     -> return-path broadcast loss (our L2)
#
# SAFETY / ROLLBACK:
#   * Uses `sysadmin port-mirror` (NOT `configure`) -> runtime-only, NOT written
#     to running/startup config, and CLEARED ON REBOOT (manual ch.13 NOTE).
#   * Mirror is non-intrusive: copies traffic, does not alter the source port.
#   * Destination must be a SPARE access port with nothing important on it.
#     Default e0-5 ("Service FIS/CCTV") — verify it's unused on the day, OR use
#     an AP port (e0-4) with the AP unplugged. NEVER mirror onto a trunk.
#   * Teardown line included; reboot also clears it.
#
# This script is ECHO-ONLY for the mutating mirror command (you paste it), and
# runs the read-only verification/teardown directly. Runs ON THE CCU.
#
# Usage:
#   ./13_dhcp_mirror_switch.sh <victim-ip> <uplink-port> [dest-access-port]
#   e.g. ./13_dhcp_mirror_switch.sh 10.179.32.195 e0-1 e0-5
#        (find <uplink-port> = the victim's ROOT port from `show spanning-tree`)

set -u
. "$(dirname "$0")/_common.sh"

VIP="${1:-}"
UPLINK="${2:-}"
DEST="${3:-e0-5}"
if [ -z "$VIP" ] || [ -z "$UPLINK" ]; then
  echo "usage: 13_dhcp_mirror_switch.sh <victim-ip> <uplink-port> [dest-access-port]"
  echo "  <uplink-port> = the victim's ROOT port (from show spanning-tree), e.g. e0-1"
  exit 1
fi

echo "=== F4 switch-side mirror setup — victim $VIP ==="
echo ""

# (1) READ-ONLY pre-checks: confirm the uplink really is the root port, and that
#     the destination access port is spare (access, link state, description).
echo "--- victim spanning-tree (confirm $UPLINK is ROOT/the uplink toward CCU) ---"
swcmd "$VIP" "show spanning-tree" | sed -n '1,20p'
echo ""
echo "--- destination port $DEST status (must be SPARE access, not a trunk) ---"
swcmd "$VIP" "show interface $DEST" | sed -n '1,8p'
echo ""
echo "--- $DEST trunk membership check (should NOT appear as a configured trunk) ---"
swcmd "$VIP" "show interface trunks" | grep -E "(^| )$DEST( |$)" \
  && echo "  !! WARNING: $DEST is a TRUNK — pick a real spare access port instead" \
  || echo "  OK: $DEST is not a configured trunk"
echo ""

# (2) ECHO-ONLY mutating step — you review, then paste.
echo "=== MIRROR COMMAND (ECHO-ONLY — paste to apply; runtime-only, reboot-clears) ==="
echo_cmd "Mirror victim uplink ($UPLINK) -> spare access port ($DEST). sysadmin form = NOT persisted." \
  "$VIP" "sysadmin port-mirror destination $DEST source $UPLINK"
echo "  # then attach a capture laptop to the physical $DEST jack on this switch and run:"
echo "  #   sudo tcpdump -ni <laptop-if> -e -tttt '(port 67 or port 68)' -w switch_side.pcap"
echo ""

# (3) Verify helper (read-only) — run AFTER you've pasted the mirror command.
echo "=== VERIFY (read-only; run after applying) ==="
echo "  swcmd $VIP 'sysadmin show port-mirror'   # should list dest=$DEST source=$UPLINK"
echo ""

# (4) Teardown — ECHO-ONLY (paste when done) + note reboot also clears it.
echo "=== TEARDOWN (ECHO-ONLY — paste when capture complete) ==="
echo_cmd "Remove the mirror (no- form). A reboot also clears it automatically." \
  "$VIP" "sysadmin no-port-mirror destination $DEST source $UPLINK"
echo "  # (exact no- syntax: confirm against switch_manual.txt ch.13 on the day;"
echo "  #  if unsure, 'sysadmin show port-mirror' then reboot the victim to clear.)"
echo ""
echo "NOTE: mirror is runtime-only (sysadmin form). If anything looks wrong, an"
echo "      SNMP/OBN reboot of $VIP returns it to a clean mirror-free state."
