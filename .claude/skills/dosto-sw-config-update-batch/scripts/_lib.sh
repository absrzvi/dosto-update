#!/usr/bin/env bash
# Shared helpers for dosto-sw-config-update-batch scripts.
# Source this from each stage script: `source "$(dirname "$0")/_lib.sh"`

set -euo pipefail

# Defaults — can be overridden via env vars.
SSH_KEY="${SSH_KEY:-C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh}"
SWITCH_PASSWORD="${SWITCH_PASSWORD:-Nom@dCome1n}"
SWITCH_USER="${SWITCH_USER:-admin}"
CCU_USER="${CCU_USER:-developer}"

# SSH option strings.
CCU_SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=10"
SWITCH_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"

# ccu_run <ccu_ip> <remote_command_string>
ccu_run() {
  local ccu_ip="$1"; shift
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" "$@"
}

# switch_run <ccu_ip> <switch_ip> <switch_command>
# One command per session — the VDS CLI rejects `;`-chained commands.
switch_run() {
  local ccu_ip="$1"; local switch_ip="$2"; local cmd="$3"
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" \
    "sshpass -p '$SWITCH_PASSWORD' ssh $SWITCH_SSH_OPTS $SWITCH_USER@$switch_ip '$cmd'"
}

# emit_event <event_name> [key=value ...]
# Emits one-line JSON to stdout. Used by --execute and --dry-run-execute.
emit_event() {
  local event="$1"; shift
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  local extras=""
  for kv in "$@"; do
    local k="${kv%%=*}"
    local v="${kv#*=}"
    # Numeric? embed raw. Otherwise quote.
    if [[ "$v" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || [[ "$v" == "true" ]] || [[ "$v" == "false" ]] || [[ "$v" == "null" ]] || [[ "$v" == \[* ]] || [[ "$v" == \{* ]]; then
      extras="$extras,\"$k\":$v"
    else
      # Escape embedded double-quotes.
      local v_esc; v_esc="${v//\"/\\\"}"
      extras="$extras,\"$k\":\"$v_esc\""
    fi
  done
  echo "{\"event\":\"$event\",\"timestamp\":\"$ts\"$extras}"
}

# rstp_root_mac <ccu_ip> <neighbour_switch_ip>
# Extracts the RSTP root MAC by reading `show spanning-tree` from a neighbour switch.
rstp_root_mac() {
  local ccu_ip="$1"; local neighbour_ip="$2"
  switch_run "$ccu_ip" "$neighbour_ip" "show spanning-tree" 2>/dev/null \
    | grep -oE '[a-f0-9]{2}(:[a-f0-9]{2}){5}' | head -1
}

# pretty section header for non-JSON human runs
section() {
  echo
  echo "============================================================"
  echo "## $*"
  echo "============================================================"
}
