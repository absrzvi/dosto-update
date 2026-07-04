#!/usr/bin/env bash
# 99 — ECHO the revert for everything this test changed. ECHO-ONLY: prints, runs nothing.
# Use at end of test if NOT committing to v9 deploy. A power-cycle or `obn update c` (from the
# current package) also reverts all runtime switch changes — this script is the explicit path.
set -u
. "$(dirname "$0")/_common.sh"

echo "=== ECHO ONLY — revert recipe. Nothing has run. ==="
echo
echo "### Part 1 — coupler port-cost: restore ORIGINALS captured in 01_rstp_harvest ###"
echo "  Per coupler $COUPLER_PORT on each cab switch (both trains), set the original cost back:"
echo "    sshpass -p '$SW_PASS' ssh \$SSH_OPTS admin@<sw-ip> \"configure interface $COUPLER_PORT spanning-tree port-cost <ORIGINAL>\""
echo "  (If you never ran 'save running-config force', a power cycle alone restores them.)"
echo
echo "### Part 2 — backup VLAN-5 gateway: restore backup own FW ###"
echo "  Per backup switch hosting VLAN-5 cameras:"
echo "    sshpass -p '$SW_PASS' ssh \$SSH_OPTS admin@<backup-sw-ip> \"configure ip dhcp-server group video default-router $BACKUP_FW_VLAN5\""
echo "  Then renew leases (bounce VLAN-5 camera ports) so cameras pick the original gateway back up."
echo
echo "### Part 3 — backup FW VLAN-5 SVI: STADLER re-enables (not ours) ###"
echo
echo "### Debug logging — turn off on all switches touched ###"
echo "    sshpass -p '$SW_PASS' ssh \$SSH_OPTS admin@<sw-ip> \"no configure system logging debug\""
echo
echo "### Storm watchers / 03_churn_watch — Ctrl-C / kill; they leave no persistent state ###"
