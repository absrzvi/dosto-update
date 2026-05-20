#!/usr/bin/env python3
"""L2 error scan for Fzg 12 - runs on CCU, checks trunk port error counters on all switches."""
import subprocess, re

SWITCHES = {
  '10.179.41.178': ('C1', ['e0-0','e0-1','e0-2','e0-3','e0-4']),
  '10.179.41.179': ('C2', ['e0-0','e0-1','e0-4']),
  '10.179.41.180': ('F1', ['e0-0','e0-1','e0-4']),
  '10.179.41.181': ('B3', ['e0-0','e0-1','e0-2','e0-4','e1-2']),
  '10.179.41.182': ('A3', ['e0-0','e0-1','e0-2','e0-4','e1-2','e1-4']),
  '10.179.41.183': ('F3', ['e0-0','e0-1','e0-4','e1-2']),
  '10.179.41.184': ('A2', ['e0-0','e0-1','e0-4']),
  '10.179.41.185': ('B1', ['e0-0','e0-1','e0-2','e0-4','e1-11']),
  '10.179.41.186': ('F2', ['e0-0','e0-1','e0-4']),
  '10.179.41.187': ('E3', ['e0-0','e0-1','e0-4','e1-2']),
  '10.179.41.188': ('A1', ['e0-0','e0-1','e0-2','e0-4']),
  '10.179.41.189': ('C3', ['e0-0','e0-1','e0-2','e0-3','e0-4','e1-2']),
  '10.179.41.190': ('B2', ['e0-0','e0-1','e0-4']),
  '10.179.41.191': ('E2', ['e0-0','e0-1','e0-4']),
  '10.179.41.192': ('E1', ['e0-0','e0-1','e0-4']),
}

SSH_OPTS = ['-o','StrictHostKeyChecking=no','-o','ConnectTimeout=6',
  '-o','KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1',
  '-o','HostKeyAlgorithms=+ssh-rsa,ssh-dss','-o','PubkeyAuthentication=no']

error_pattern = re.compile(r'(RX errors|RX crc errors|TX crc errors|carrier false|Excessive collisions|Late collisions|pause frames received):\s*(\d+)')

alerts = []
for ip, (role, ports) in sorted(SWITCHES.items()):
  for port in ports:
    cmd = ['sshpass','-p','Nom@dCome1n','ssh'] + SSH_OPTS + [f'admin@{ip}', f'show interface {port} details']
    try:
      out = subprocess.run(cmd, capture_output=True, text=True, timeout=12).stdout
    except Exception as e:
      print(f"FAIL {ip} ({role}) {port}: {e}")
      continue
    speed = ''
    for ln in out.split('\n'):
      if 'Speed:' in ln: speed = ln.strip()
    errors = {}
    for m in error_pattern.finditer(out):
      if int(m.group(2)) != 0:
        errors[m.group(1)] = m.group(2)
    status = 'OK' if not errors else f'NONZERO {errors}'
    if errors:
      alerts.append(f"ALERT {ip} ({role}) {port}: {speed} | {status}")
      print(f"ALERT {ip} ({role}) {port}: {speed} | {status}")
    else:
      print(f"  OK  {ip} ({role}) {port}: {speed}")

print("\n=== SUMMARY ===")
if alerts:
  print(f"{len(alerts)} ALERTS:")
  for a in alerts:
    print(" ", a)
else:
  print("ALL CLEAR - no non-zero error counters on checked ports")
