# Companion 2 — Factory-config Westermo APs silently reject OBN SNMP → require LuCI HTTP bypass

**Repo:** AP image / Westermo provisioning (no clear single owner)
**Not in:** `nd-obn`

## Summary

Westermo RT610LV APs shipped in factory config (firmware string `RT610LV-...-v1-FD`) use SNMP community `admin-community`. OBN sends SNMP with community `NomadStayOut!`. The AP silently drops the unknown-community packets — no ICMP unreachable, no log entry that OBN sees. OBN prints "configuration update applied, device rebooting" regardless, because it does not check the SNMP return value before printing the success line.

Result: `obn update c <factory-ap-ip>` looks successful but does nothing. The AP stays in factory config forever, blocks subsequent firmware pushes (same SNMP path), and the engineer's only recourse is a LuCI HTTP-based bypass (login → flashops upload → rpcCfgApply) to push the Nomad config.

## Affected APs

Every Westermo AP that ships factory-default (most of them, until they've been touched at least once). Once an AP has Nomad config applied (any successful pass), it switches to community `NomadStayOut!` and OBN SNMP works normally.

## Reproducer

1. Any consist with at least one factory-config AP (firmware string ends in `v1-FD`).
2. `sudo obn discover && sudo obn update c <factory-ap-ip>`.
3. Observe "configuration update applied, device rebooting" on stdout, exit 0.
4. AP does not actually reboot. Re-discover shows it still in factory config.

## Current workaround (in production, hand-applied)

`scripts/push_ap_config.sh` and `scripts/apply_ap_configs.sh` perform a LuCI HTTP-based push:
1. POST to `https://<ap-ip>/cgi-bin/luci/` with admin credentials (`Nom@dCome1n` on factory; the script handles both).
2. POST to `https://<ap-ip>/cgi-bin/luci/admin/system/flashops/upload` with the Nomad config tarball.
3. POST to the `rpcCfgApply` endpoint to trigger the apply.
4. Wait for AP to reboot, re-verify via SNMP (community now correct).

This works but it's not what OBN should look like. Confirmed reliable on 4734-120 (2026-05-05) and many trains since.

## The actual fix (two options)

**Option A — Make OBN detect factory APs and use LuCI fallback automatically.**
OBN's `update_device` for an AP could, on SNMP timeout/community-mismatch, fall back to the LuCI HTTP path. This is the cleanest user experience but is the most code change. Roughly mirrors what our shell scripts do — could be lifted into OBN's `lib/device/vendor/westermo.py` (or wherever the AP vendor module lives).

**Option B — Have Westermo ship factory APs with the Nomad community baked in.**
Requires coordination with Westermo's manufacturing. Out of scope for this handoff but worth raising — it eliminates the bypass entirely.

**Option C — At minimum, fix OBN's "Successful" lie.**
Even without an automatic fallback, OBN should not print "Successful" when the SNMP set was silently dropped. Check the SNMP return code; if no positive ACK from the AP, print a clear `FAILED: SNMP community mismatch (likely factory-default AP — use LuCI bypass)` and exit non-zero. This is a 10-line change and would prevent the silent-success failure mode that engineers currently work around manually.

We'd take any of the three. Option C is the minimum-viable.

## Test evidence

Reliable reproducer on every consist with new APs. Workaround scripts validated on dozens of trains. See memory [`project_ap_factory_config.md`](../?).

## Marker / detection

Pre-fix: a factory-config AP responds on `https://<ip>` (LuCI title `RT610LV-...-v1-FD`) and ignores SNMP from community `NomadStayOut!`. The current skill `dosto-ap-config-update` autodetects this and routes to the LuCI bypass.

## Notes for R&D

The friction here is that "OBN should know about LuCI" feels like a layering violation — OBN is the orchestrator, the AP-specific config-push mechanism is implementation. But factually, we've spent more engineering hours on this workaround than on most of the OBN bugs. It's worth either codifying it in OBN or eliminating it via the Westermo provisioning path.
