#!/usr/bin/env bash
# Shared helpers for the 2026-06-30 coupled-train test (4736-117 master + 4736-105 backup).
# Source this from the other scripts:  . ./_common.sh
# Runs ON THE CCU. Switch SSH uses the VDS legacy-algo snippet (one command per session).

# --- Switch SSH (legacy KEX/host-key; one command per session; CLI rejects ; chaining) ---
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss -o PubkeyAuthentication=no"
SW_PASS='Nom@dCome1n'

# swcmd <switch-ip> <single-command>   -> runs one command on a VDS switch.
# Uses sshpass when present (e.g. 105 backup); falls back to python3+pexpect when sshpass is
# absent (e.g. 117 master — confirmed missing 2026-06-30). The VDS prompt is "(admin@IP) Password:"
# (capital P) — the pexpect matcher is case-insensitive to handle it.
swcmd() {
  local ip="$1" cmd="$2"
  if command -v sshpass >/dev/null 2>&1; then
    sshpass -p "$SW_PASS" ssh $SSH_OPTS admin@"$ip" "$cmd"
  else
    SW_PASS="$SW_PASS" SW_OPTS="$SSH_OPTS" python3 - "$ip" "$cmd" <<'PYEOF'
import sys, os, pexpect
ip, cmd = sys.argv[1], sys.argv[2]
opts = os.environ["SW_OPTS"]; pw = os.environ["SW_PASS"]
c = pexpect.spawn('ssh %s admin@%s "%s"' % (opts, ip, cmd), timeout=25, encoding="utf-8")
i = c.expect(["[Pp]assword:", pexpect.EOF, pexpect.TIMEOUT])
if i == 0:
    c.sendline(pw); c.expect(pexpect.EOF)
sys.stdout.write(c.before or "")
PYEOF
  fi
}

# --- Coupler ports are e0-2 on A1, A3, B1, B3 of each train ---
COUPLER_PORT="e0-2"
CAB_SWITCHES="A1 A3 B1 B3"

# --- Reference addressing (CONFIRM LIVE ON THE DAY — do not trust blindly) ---
# Master = 4736-117 / Fzg 145 ; Backup = 4736-105 / Fzg 133
MASTER_FW_VLAN5="172.18.200.129"     # master FW VLAN-5 gateway (cameras repoint here)
BACKUP_FW_VLAN5="172.18.194.129"     # backup FW VLAN-5 gateway (its own, today / revert target)
# master cameras 172.18.200.158+ ; backup cameras 172.18.194.158+
# VLAN-5 space = 172.18.128.0/17

# echo_cmd <description> <switch-ip> <command>
# Prints a copy-paste-ready swcmd line WITHOUT running it (echo-only safety for mutations).
echo_cmd() {
  printf '  # %s\n' "$1"
  printf "  sshpass -p '%s' ssh \$SSH_OPTS admin@%s \"%s\"\n\n" "$SW_PASS" "$2" "$3"
}

# ts -> iso8601 for log lines
ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
