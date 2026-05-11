#!/bin/bash
# Step 1 — verify SSH to CCU works, capture basic networking info.
# Usage: ./01_ccu_probe.sh <CCU_IP>
set -uo pipefail
source "$(dirname "$0")/_lib.sh"

CCU_IP="${1:?usage: $0 <CCU_IP>}"

section "Step 1 — CCU probe ($CCU_IP)"

if ! ccu_run "$CCU_IP" 'echo SSH_OK; hostname; uname -r' 2>&1 | head -5; then
  echo "ERROR: cannot SSH to CCU at $CCU_IP" >&2
  exit 1
fi

echo
echo "--- Interfaces ---"
ccu_run "$CCU_IP" 'ip -br addr | grep -E "vlan|bond"'

echo
echo "--- Routes (default + onboard) ---"
ccu_run "$CCU_IP" 'ip route | head -20'
