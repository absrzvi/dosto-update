#!/usr/bin/env bash
# 00 — Resolve live switch IPs on the CCU you're logged into. READ-ONLY.
# Run ON EACH CCU separately (master 10.179.32.1, backup 10.179.1.1).
# VDS DHCP leases are 2 min — always resolve fresh, never reuse IPs.
set -u
. "$(dirname "$0")/_common.sh"

echo "=== $(ts) DHCP leases (VDS switches: hostname nv6-*-vN-<fzg>) ==="
sudo dhcp-lease-list 2>/dev/null | grep -E "nv6-" | sort -t. -k4 -n

echo
echo "=== Cab switches for this train (A1/A3/B1/B3 carry coupler e0-2) ==="
sudo dhcp-lease-list 2>/dev/null | grep -E "nv6-(A1|A3|B1|B3)-"

echo
echo "=== vlan100 ARP cross-check (VDS OUI a0:59:3a) ==="
ip neigh show dev vlan100 2>/dev/null | grep -i "a0:59:3a" | sort -t. -k4 -n

echo
echo ">> Record the A1/A3/B1/B3 IPs for THIS train; you'll pass them to 01/02/03."
echo ">> Confirm coupler ports are link-UP before trusting any churn result (June A6/A7 phantom-link trap)."
