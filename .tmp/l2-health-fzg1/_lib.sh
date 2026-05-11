# Shared helpers for dosto-l2-health scripts.
# Source this from each step script: `source "$(dirname "$0")/_lib.sh"`

# Defaults — can be overridden via env vars.
SSH_KEY="${SSH_KEY:-C:/Users/AbbasRizvi/Documents/dosto-troubleshooting/openssh}"
SWITCH_PASSWORD="${SWITCH_PASSWORD:-Nom@dCome1n}"
SWITCH_USER="${SWITCH_USER:-admin}"
CCU_USER="${CCU_USER:-developer}"

# SSH option strings.
CCU_SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o ServerAliveInterval=10"
SWITCH_SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=8 -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"

# ccu_run <ccu_ip> <remote_command_string>
# Runs a command on the CCU. Output goes to stdout.
ccu_run() {
  local ccu_ip="$1"; shift
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" "$@"
}

# switch_run <ccu_ip> <switch_ip> <switch_command>
# Runs ONE command on a VDS switch via the CCU. The switch CLI does not accept `;`-chained commands.
switch_run() {
  local ccu_ip="$1"; local switch_ip="$2"; local cmd="$3"
  # Fzg 1 (4734-101) CCU has no sshpass — use pre-installed pexpect helper at /tmp/swssh.py
  ssh $CCU_SSH_OPTS "$CCU_USER@$ccu_ip" "python3 /tmp/swssh.py $switch_ip '$cmd'"
}

# vds_switch_list <ccu_ip>
# Returns a sorted list of VDS switch IPs on vlan100 (OUI a0:59:3a).
vds_switch_list() {
  local ccu_ip="$1"
  ccu_run "$ccu_ip" 'ip neigh show dev vlan100' \
    | grep "lladdr a0:59:3a" \
    | awk '{print $1}' \
    | sort -t. -k4 -n
}

# westermo_count <ccu_ip>
westermo_count() {
  local ccu_ip="$1"
  ccu_run "$ccu_ip" 'ip neigh show dev vlan100' \
    | grep -c "lladdr 00:14:5a" || true
}

# Pretty section header.
section() {
  echo
  echo "============================================================"
  echo "## $*"
  echo "============================================================"
}
