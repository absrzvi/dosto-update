# VDS Rail Consist Switch — CLI Reference (curated for L2 health checks)

This is the focused subset of the VDS Consist Switch CLI commands the health check actually uses. The full reference is in `docs/switch_user_manual.pdf` (relative to the project root) — only consult it if you need a command not listed here.

Tested against firmware 7.4.2 build 77411 (DOSTO Fzg. 146, 2 May 2026). Earlier firmwares may have minor output-format differences but the command names are stable.

## Connecting

The VDS switch SSH server requires legacy KEX and host-key algorithms. From the CCU:

```bash
sshpass -p "Nom@dCome1n" ssh \
  -o StrictHostKeyChecking=no \
  -o ConnectTimeout=8 \
  -o KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1 \
  -o HostKeyAlgorithms=+ssh-rsa,ssh-dss \
  -o PubkeyAuthentication=no \
  admin@<switch-ip> "<single-command>"
```

**One command per session.** The switch CLI rejects `;`-chained commands with `Error in command, param is "..." [wrong]`. Loop in the surrounding shell.

User levels are visible in the prompt: `O@` is operator, `A@` is admin. `admin` user is required for all configuration writes; reads work for either.

## Information commands (read-only, used in the health check)

### `show version`
Firmware version and build number. Use to verify fleet-wide firmware consistency.

```
Consist Switch by VDS Rail.
Firmware Version: 7.4.2
Build Release:    77411
```

### `show interface summary`
One-line state per port. The fastest way to see which ports are up, at what speed, and admin-enabled vs. disabled.

Columns: `Port  Type  Status  Line  Speed  Duplex  MDI  FlowCtrl`. The fields you care about are `Status` (enabled/disabled = admin state) and `Line` (up/down = link state).

### `show interface <port>`
Brief per-port view. Includes admin/line state, speed, duplex, hardware MAC, VLAN membership, RX/TX packet counters. Skip in favour of `show interface <port> details` if you want error counters.

### `show interface <port> details`
**The single most useful command in the L2 check.** Returns every per-port counter the switch tracks. Parse these fields:

| Field | What it measures | Healthy value |
|-------|------------------|---------------|
| `RX packets` / `TX packets` | Cumulative since last counter reset | grows |
| `RX bytes` / `TX bytes` | Cumulative bytes | grows |
| `collisions` | Half-duplex collision count | 0 |
| `pause frames received` / `sent` | 802.3x flow control | 0 |
| `carrier false` | Link-layer instability events | 0 |
| `RX errors` | Frame-level RX errors (umbrella) | 0 |
| `runts` / `giants` / `frag` / `jabber` | Malformed frames | 0 |
| `RX crc errors` | CRC mismatch on receive — bad cable, EMI, dirty connector | 0 |
| `TX crc errors` | CRC errors on TX side | 0 |
| `Excessive collisions` / `Late collisions` | Half-duplex contention | 0 on full-duplex links |

A non-zero RX CRC count or sustained carrier-false count is a real fault. A single-digit RX error count over millions of packets is noise.

### `show interface trunks`
Lists ports configured as trunks, plus native VLAN and the prune set (allowed VLAN list).

```
Trunk   Line   Native  Tag   Prune Set
e0-0    up     0001    No    allow 1-1000
e0-1    up     0001    No    allow 1-1000
e0-4    up     0001    No    allow 100,10,20,30,31,131,150,1
```

### `show vlans`
VLAN-to-port mapping. Use to identify ZFR access ports (VLAN 2 with `e1-11` listed).

`show vlans <id-list>` filters to specific VLANs, e.g. `show vlans 1,2,100,200-202`.

### `show spanning-tree`
RSTP / STP state. Use to confirm one stable root across the fleet.

Output includes:
- `Selected redundancy protocol RSTP is running.`
- `Root bridge : <priority>/<MAC>` — must match across all switches in the consist
- `Bridge ID : <priority>/<MAC>` — this switch's own ID
- Per-port table with role (`ROOT`/`DESG`/`EDGE`/`ALT`/`BACK`), state (`FWD`/`BLK`/`LRN`), cost, port mode

### `show counters protocol lldp`
LLDP TX/RX per port plus errors. Used to confirm neighbour discovery is working.

### `show counters protocol ttcmp`
Train Topology and Train Communication Management Protocol counters. Confirms train-discovery protocol is active.

### `show system temperature`
Internal switch temperature. Max safe is 100 °C; field readings of 35–55 °C are normal.

### `show system memory`
RAM usage. Cause for concern only if `free` approaches zero.

### `show log`
Event log. Useful for spotting historical link flaps and STP topology change events.

`show log persistent` — the persistent (across-reboot) log.
`show log update` — firmware update history.

### `show running-config`
Full active configuration. Useful to confirm port assignments match the schema. Verbose; usually filter with `grep` from the calling shell.

## Anti-patterns (don't do these in a health check)

- **Don't issue configuration commands.** This skill is read-only. `configure interface ...`, `no configure ...`, etc. modify state.
- **Don't reset counters.** Useful for fresh measurement windows but destroys the cumulative-since-boot history. Only do it when explicitly requested by the user.
- **Don't run `reload` or `reboot`.** Should be obvious; mentioning because the switch CLI does accept these without confirmation in admin mode.

## Output parsing tips

- Counters live on lines with the pattern `<Field>:<digits>` — most can be extracted with `sed -nE 's/.*<Field>:([0-9]+).*/\1/p'`.
- Field labels are sometimes followed by a space (e.g. `RX crc errors: 0`) — match either form.
- When a port is `disabled`, `show interface <port> details` still works; the stats just show zeros.
- When a port's Line is `down`, counters reflect the last time it was up. Useful for "did this port ever flap" forensics — if it currently shows `down` but has nonzero `RX packets`, it has been up at some point.

## Reference cards

### Quick health check (one switch)

```text
show interface summary           # any unexpected DOWN links?
show interface trunks            # trunks at expected speeds, carrying expected VLANs?
show spanning-tree               # root MAC matches the rest of the fleet?
show interface e0-0 details      # zero on errors / CRC / carrier-false?
show interface e0-1 details
show interface e0-4 details
```

### Critical Stadler trunks (whole consist)

```text
# A3 (firewall switch — has e1-4 as trunk):
show interface e1-4 details

# D1 / D3 (OBS+RDC — have e0-3 as trunk):
show interface e0-2 details      # OBS trunk
show interface e0-3 details      # RDC trunk

# B1 / B3 (ZFR — have e1-11 as access on VLAN 2):
show interface e1-11 details
```

### Throughput sample

```text
show interface <port> details    # take twice, N seconds apart, diff RX/TX bytes
```

Rate (Mbps) = (delta_bytes × 8) / interval_seconds / 1e6.
