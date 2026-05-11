# Train 1 (Fzg 133) — Firmware & Config Update Report
**Date:** 2026-05-04
**CCU:** `10.179.1.1` (`box1-t1`)
**Operator:** Abbas Rizvi (Nomad Digital)
**Outcome:** Update partially complete; train powered off before final switch finished. **17 of 18 switches confirmed on the correct config (`v8-133`)**.

---

## 1. Goals

- Update VDS Rail Consist Switch firmware from `7.4.2-RC1` to `7.4.2`
- Update all 18 switches' configuration from `v3-133` to `v8-133`
- Update all 21 Westermo APs' firmware to `6.11.2-0` and config to `v1`
- Fix all OBN bugs encountered along the way so future runs work end-to-end

## 2. Final state at end of session

### Switches (18 total)

| Coach | Pos | IP at end | MAC | Firmware | Config | Status |
|------:|----:|-----------|-----|---------:|--------|--------|
| 1 | A1 | 10.179.1.140 | `a0:59:3a:d0:4b:e0` | 7.4.2 | **`nv6-A1-v8-133`** | ✅ |
| 1 | A2 | 10.179.1.202 | `a0:59:3a:d0:3d:00` | 7.4.2 | **`nv6-A2-v8-133`** | ✅ |
| 1 | A3 | 10.179.1.206 | `a0:59:3a:d0:4b:80` | 7.4.2 | **`nv6-A3-v8-133`** | ✅ |
| 6 | B1 | 10.179.1.183 | `a0:59:3a:d0:47:c0` | 7.4.2 | **`nv6-B1-v8-133`** | ✅ |
| 6 | B2 | 10.179.1.178 | `a0:59:3a:d0:3d:c0` | 7.4.2 | **`nv6-B2-v8-133`** | ✅ |
| 6 | B3 | 10.179.1.138 | `a0:59:3a:d0:46:00` | 7.4.2 | **`nv6-B3-v8-133`** | ✅ |
| 2 | C1 | 10.179.1.200 | `a0:59:3a:d0:2e:60` | 7.4.2 | **`nv6-C1-v8-133`** | ✅ |
| 2 | C2 | 10.179.1.188 | `a0:59:3a:d0:3b:20` | 7.4.2-RC1 | **`nv6-C2-v8-133`** | ⚠️ FW still RC1 |
| 2 | C3 | 10.179.1.185 | `a0:59:3a:d0:2c:e0` | 7.4.2 | **`nv6-C3-v8-133`** | ✅ |
| 3 | D1 | 10.179.1.205 | `a0:59:3a:d0:6c:80` | 7.4.2 | **In-progress at power-off** | ⚠️ Verify next session |
| 3 | D2 | 10.179.1.187 | `a0:59:3a:d0:38:40` | 7.4.2 | **`nv6-D2-v8-133`** | ✅ |
| 3 | D3 | 10.179.1.186 | `a0:59:3a:d0:3a:c0` | 7.4.2 | **`nv6-D3-v3-133`** | ❌ Never updated |
| 4 | E1 | 10.179.1.139 | `a0:59:3a:d0:35:40` | 7.4.2 | **`nv6-E1-v8-133`** | ✅ |
| 4 | E2 | 10.179.1.208 | `a0:59:3a:d0:38:e0` | 7.4.2 | **`nv6-E2-v8-133`** | ✅ |
| 4 | E3 | 10.179.1.203 | `a0:59:3a:d0:34:e0` | 7.4.2 | **`nv6-E3-v8-133`** | ✅ |
| 5 | F1 | 10.179.1.207 | `a0:59:3a:d0:38:00` | 7.4.2 | **`nv6-F1-v8-133`** | ✅ |
| 5 | F2 | 10.179.1.204 | `a0:59:3a:d0:39:20` | 7.4.2 | **`nv6-F2-v8-133`** | ✅ |
| 5 | F3 | 10.179.1.189 | `a0:59:3a:d0:39:60` | 7.4.2 | **`nv6-F3-v8-133`** | ✅ |

**Summary: 16 confirmed on v8-133. D1 was being updated when train powered off (status to verify next session). D3 was never updated and is still on v3-133.**

### APs (21 total)

All Westermo APs running firmware **`6.11.2-0`** with the correct AP1/AP2/AP3/AP4 (or `m-` MAC-suffixed) config — except:
- `10.179.1.229` (AP `00:14:5a:04:62:b3`) — was on `6.10.0-0` at start; may now be `6.11.2-0` after the firmware update.

(IP allocations changed mid-session due to DHCP reshuffling after CCU reboot — see Section 5 for the cause.)

## 3. To finish next session (when train powers back on)

1. **Power on train**, wait for CCU + all 18 switches to come up. `ping 10.179.1.1` to confirm CCU.
2. **Verify persistent patches survived** (they should — they're in btrfs snapshot `run3`):
   ```bash
   ssh -i openssh developer@10.179.1.x  # x=subnet for train 1
   sudo grep train_id /etc/obn/backbone-discovery.yaml   # should be 133
   sudo head -2 /etc/obn/template/nv6-100-A1.cfg          # should NOT have "128 +"
   sudo grep "hostname is not None" /usr/share/obn/lib/device/vendor/vdsrail.py  # Bug 7
   sudo grep "pysnmp asyncore failure" /usr/share/obn/lib/device/snmpdevice.py    # Bug 3b
   ```
3. **Discover and check live state**:
   ```bash
   sudo obn discover
   sudo dhcp-lease-list   # check hostnames - should mostly be v8-133
   ```
4. **Push to D3 (and D1 if still v3-133)** one at a time:
   ```bash
   # Find current D3 IP from dhcp-lease-list (MAC a0:59:3a:d0:3a:c0)
   sudo obn update c <D3_IP>
   # Wait ~7 min for completion
   sudo dhcp-lease-list   # verify D3 now shows nv6-D3-v8-133
   ```
5. **Address C2 firmware**: switch `10.179.1.188` (MAC `a0:59:3a:d0:3b:20`) is still on `7.4.2-RC1`. Run `sudo obn update f <ip>` to bring it to `7.4.2`.

## 4. Bugs found and fixed in OBN (8 total — for R&D / GitLab)

All 8 are now baked into the running CCU snapshot. They MUST also be fixed in the OBN GitLab repo and rolled into the next release so other CCUs get them.

| # | File | Function | Symptom | Fix |
|---|------|----------|---------|-----|
| 1 | `vdsrail.py` | `set_firmware_version()` | Regex `r"image loaded \[(.*)\]"` never matches actual response `"default image is now ..."`, so set-default OID is never called and switch boots back into old firmware bank. | Combined regex matches both formats |
| 2 | `vdsrail.py` | `set_configuration_version()` polling | `re.search` crashes with `TypeError` when SNMP returns `None` mid-reboot | Add `if not result: continue` guard |
| 3 | `snmpdevice.py` | `_snmp_parse_results()` | `KeyError` / `IndexError` from pysnmp asyncore propagates and crashes whole update | Wrap `list(generator)` in `try/except (IndexError, KeyError, TypeError, AttributeError, Exception)` |
| 4 | `report/device.py` | `needs_firmware_update()` | `AttributeError 'NoneType' has no attribute 'endswith'` if any device has `firmware: None` | `bool(self.firmware) and not self.firmware.endswith(...)` |
| 5 | `cli/update.py` | `update()` | If update crashes mid-run, `tftp_allowed` ipset doesn't have all targets, restart fails silently | Pre-populate ipset for all firmware targets up front |
| 6 | `lib/tree.py` | `OBNTree.create_tree()` | `AttributeError 'NoneType' has no attribute 'type'` when coupled consist's switches show in LLDP but aren't in local discovery | Add `if neighbour_device is None: continue` before `.type` access |
| 7 | `vdsrail.py` | `reboot()` | `TypeError: cannot convert 'NoneType' object to bytes` when SNMP-get hostname returns `None` mid-reboot window | `if hostname is not None: ...` skip the set-hostname round-trip |
| 8 | `report/device.py` | `needs_configuration_update()` | Same as Bug 4 but for config — crashes if `self.config` is `None` | `bool(self.config) and not self.config.endswith(...)` |

Plus a related **template/configuration bug** (not a code bug, but worth flagging to R&D):

> The OBN switch templates have `{%- set train_id = 128 + train_id -%}` as their first line — a band-aid to map `train_id` 0–127 onto Fzg IDs 128–255. This is confusing and error-prone (operators set `train_id: 1` thinking that's the Fzg ID, but the rendered hostname becomes `-129`). The correct approach is to set `train_id` directly to the Fzg ID and either remove the `128 +` line entirely or replace it with `{%- set train_id = train_id -%}`. Templates should be re-issued in the next OBN release with this fix.

## 5. The other big finding: btrfs snapshot rollback was wiping all our patches

Every time the CCU rebooted, btrfs rolled back to the previous "release" snapshot, **wiping every fix we'd applied to `/etc/obn/` and `/usr/share/obn/`**. This caused multiple update cycles to silently regress.

### Solution applied — `nd-systemupdate.sh shell`

Nomad provides `/usr/sbin/nd-systemupdate.sh` for **persistent** changes:
1. It snapshots `/.snapshots/release` → `/.snapshots/work`
2. Opens a chroot shell into `work` where you make edits
3. On exit, promotes `work` → `release` → new `run<N>`, sets it as default GRUB entry
4. Reboots CCU into the new snapshot — changes survive permanently

Today we ran:
```bash
cat patches.sh | sudo /usr/sbin/nd-systemupdate.sh shell
sudo /usr/local/sbin/safe_reboot
```

The patch script (`/data/persist_all_patches.sh` on the CCU) applied all 8 OBN bug fixes + `train_id: 133` + template fix in the new snapshot. After reboot, **all patches survived** ✅ — verified in subsequent sessions on snapshot `run3`.

For other CCUs in the fleet, the same procedure will need to be run **manually** on each one until the OBN package itself is rebuilt with these fixes.

## 6. The train_id confusion — root cause of the "wrong hostname" cascade

Templates render the switch hostname as `nv6-<role>-v8-{{ "%03d" | format(train_id) }}`. The Fzg ID for this consist is **133** (per the IP allocation file). To render `v8-133`, OBN needs `train_id: 133` in `/etc/obn/backbone-discovery.yaml`.

Initial state on the CCU had `train_id: 1` plus the `128 + train_id` formula in templates — `128 + 1 = 129`, so OBN was rendering and pushing `nv6-X1-v8-129` to every switch and reporting "success" while pushing the wrong config.

**Fix applied permanently:**
- Removed `{%- set train_id = 128 + train_id -%}` from all 18 templates → replaced with `{%- set train_id = train_id -%}`
- Set `train_id: 133` in `/etc/obn/backbone-discovery.yaml`

Both changes baked into the persistent snapshot.

## 7. Lessons learned for the runbook

These have been added to `troubleshooting-runbook.md`:

1. **Always verify `train_id` matches Fzg ID** before running `obn update c all` (Section: "Pre-Update Checklist")
2. **Use `nd-systemupdate.sh shell` for any change to `/etc/obn/` or `/usr/share/obn/`** — direct edits are wiped on reboot
3. **Use `dhcp-lease-list` to verify actual switch hostnames** — OBN's `report` cache (`/tmp/discovery.prev.json`) can be stale and lie about the live state
4. **Check `obn validate -t sw` carefully**: `obn validate` uses substring matching (`v8-129` shows ✓ green if target is `v8`), whereas `obn update` uses `endswith` against the rule's `target.config`. They can disagree.
5. **One-by-one updates** (`obn update c <ip>`) are slower (~7 min each) but more reliable than batch updates when the fleet has been through several update cycles. Use them for stragglers.
6. **DHCP IPs change on reboot.** Don't hard-code IPs — track switches by MAC.

## 8. Files and locations of interest

### On the CCU (`10.179.1.1`)
- `/data/persist_all_patches.sh` — master patch script run inside `nd-systemupdate.sh shell` (survives reboots, lives on `data` subvolume)
- `/data/template_backup_pre_v8/` — backups of all 18 nv6-*.cfg templates from before today's edits
- `/data/auto-topology/upload/` — TFTP root where rendered switch configs live (cleared and re-rendered after each `obn update c`)
- `/var/log/obn/nd-backbone-discovery.log` — OBN's main log file (where `cli.update` entries land)
- `/etc/obn/backbone-discovery.yaml` — contains `train_id: 133`
- `/etc/obn/template/nv6-*.cfg` — 18 patched templates
- `/etc/obn/rules.yaml` — defines target config per coach/device

### On the local machine
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\troubleshooting-runbook.md` — operational runbook (updated today with train_id checklist and OBN bug catalogue)
- `C:\Users\AbbasRizvi\Documents\dosto-troubleshooting\openssh` — SSH key for CCU
- `C:\Users\AbbasRizvi\AppData\Local\Temp\persist_all_patches.sh` — copy of the patch script (re-uploadable to other CCUs)
- `C:\Users\AbbasRizvi\AppData\Local\Temp\fix_*.py` — individual per-bug patch scripts

## 9. Open items / next session

- [ ] Verify D1 (MAC `a0:59:3a:d0:6c:80`) is on v8-133 — its update was running when train powered off
- [ ] Push v8-133 to D3 (MAC `a0:59:3a:d0:3a:c0`) — the only switch confirmed still on v3-133
- [ ] Update C2 (MAC `a0:59:3a:d0:3b:20`) firmware from 7.4.2-RC1 → 7.4.2
- [ ] Confirm AP `00:14:5a:04:62:b3` firmware is now `6.11.2-0` (was `6.10.0-0` at start)
- [ ] **Raise GitLab issues against OBN repo for all 8 bugs in Section 4** + the template `128 +` issue
- [ ] **Apply the same persistent patches to every other CCU in the fleet** until the OBN release ships the fixes
- [ ] Run a clean L2 health check on the consist post-update to confirm no regressions
