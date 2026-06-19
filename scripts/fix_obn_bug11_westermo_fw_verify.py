#!/usr/bin/env python3
"""
Fix OBN Bug 11: Westermo AP firmware update reports success without verifying activation.

Symptom: `obn update f <ap-ip>` reports success, but the AP stays on the old
firmware version ("staged-not-activated" — `obn validate` shows
`6.10.0-0 (6.11.2-0) ✗`). Fleet-wide; leans m-variant but also hits plain APs
(e.g. 4736-116 .228 AP4-v1). Confirmed across the 2026-06-08 9-train run on
4734-112/114/115/122 and 4736-108/109/116.

Root cause: `westermo.py::set_firmware_version` writes the three firmware OIDs
(setFwFileUrl, setFwKeepConfig, rpcFwFlash=flash(2)) in one SNMP SET, then checks
ONLY the SET echo:

    result = self._snmp_set(firmware_instructions)
    if result.get("...3.2.1.0") != 2:
        return False
    return True

pysnmp's SET returns the value you just wrote, so `result.get(rpcFwFlash)` is
always 2 — the check is `2 != 2` and always passes. OBN declares success the
instant the SET is acknowledged, BEFORE any download / validation / flash.

But per WESTERMO-SW6-MIB, `rpcFwFlash` is a STATUS field on read-back:
    flash(2)         = currently writing
    downloadError(-1)= download or validation failed
    flashError(-2)   = flash write failed
    nop(0)           = idle / flash complete (device then reboots)

OBN never reads it back, so a downloadError(-1) / flashError(-2) is reported as
success. The firmware never lands; the AP keeps booting the old image.

Fix: after the SET, POLL rpcFwFlash via _snmp_get (a real GET, not the echo)
until it reaches a terminal state. Treat -1/-2 as failure, nop(0) as success
(flash complete, device rebooting), keep polling while it reads 2 (writing).
This makes OBN use the standard SNMP firmware path CORRECTLY — no LuCI bypass,
no skill-side workaround.

File:   /usr/share/obn/lib/device/vendor/westermo.py
        (`time` is already imported at module top; _snmp_get(oid, cast) exists
         in snmpdevice.py and returns the read-back value.)

Idempotent — safe to run twice.
"""
from pathlib import Path
import sys

TARGET = Path("/usr/share/obn/lib/device/vendor/westermo.py")
MARKER = "# NDP-PATCH-BUG11-FW-VERIFY"

RPCFWFLASH_OID = "1.3.6.1.4.1.16177.1.400.1.3.2.1.0"

# Anchor: the exact broken echo-check block (must match byte-for-byte).
OLD = '''        # Send instructions to the device.
        self.logger.debug("sending firmware update instructions")
        result = self._snmp_set(firmware_instructions)
        if result.get("1.3.6.1.4.1.16177.1.400.1.3.2.1.0") != 2:
            self.logger.debug("something happened on the way to heaven")
            return False

        return True'''

NEW = f'''        # Send instructions to the device.
        self.logger.debug("sending firmware update instructions")
        result = self._snmp_set(firmware_instructions)
        if result.get("{RPCFWFLASH_OID}") != 2:
            self.logger.debug("something happened on the way to heaven")
            return False

        # {MARKER}
        # Bug 11 fix: the SET above only echoes the value we wrote (always 2),
        # so trusting it is NOT verification. Per WESTERMO-SW6-MIB, rpcFwFlash is
        # a STATUS field on read-back: flash(2)=writing, downloadError(-1),
        # flashError(-2), nop(0)=done. POLL the real status until terminal.
        #
        # Proven two failure modes on RT-610 (4736-109, 2026-06-08):
        #  (a) SLOW-BUT-FINE: flash succeeds, AP reboots and activates the new
        #      firmware, but the whole flash->reboot->SNMP-re-report cycle can take
        #      well over 5 min. OBN's old echo-check (and a short poll) reads the
        #      old version mid-cycle and false-flags it as failed. Confirmed by an
        #      uptime RESET (.236: came back at uptime 312s on the new fw).
        #  (b) GENUINE HANG: AP ACKs rpcFwFlash=2 then sits at "writing" forever and
        #      never reboots (e.g. .226 uptime 21668s, still old fw). This is a real
        #      RT-610 defect; the flash trigger is flaky (sometimes hangs).
        #
        # So success == an actual REBOOT (uptime reset) or a clean nop(0). Failure
        # == -1/-2, OR "still status 2 with NO reboot" at the end of a GENEROUS
        # window. We poll up to ~10 min because (a) is real and common; treating a
        # slow-but-fine AP as failed is the worse error (it's already correct).
        rpcfwflash_oid = "{RPCFWFLASH_OID}"
        uptime_oid = self.device_config.get("snmp_uptime_oid", ".1.3.6.1.2.1.1.3.0")
        try:
            uptime_before = self._snmp_get(uptime_oid, cast=int)
        except Exception:
            uptime_before = None
        rebooted = False
        for _ in range(60):  # 60 x 10s = 600s (~10 min): RT-610 flash+reboot+report
            time.sleep(10)                                       # can exceed 5 min
            # Always check uptime first: a reset is the definitive success signal,
            # whether or not rpcFwFlash is still readable.
            try:
                uptime_now = self._snmp_get(uptime_oid, cast=int)
            except Exception:
                uptime_now = None
            if uptime_before is not None and uptime_now is not None \\
                    and uptime_now < uptime_before:
                self.logger.debug(
                    "%s rebooted (uptime %s->%s) — firmware activated",
                    self.ip, uptime_before, uptime_now)
                rebooted = True
                break
            try:
                status = self._snmp_get(rpcfwflash_oid, cast=int)
            except Exception:
                continue  # transient SNMP gap; keep polling, do NOT assume success
            if status in (-1, -2):
                self.logger.error(
                    "firmware flash failed on %s: rpcFwFlash=%s "
                    "(-1=downloadError, -2=flashError)", self.ip, status)
                return False
            if status in (0, None):  # nop(0): flash complete
                self.logger.debug("firmware flash complete (rpcFwFlash=nop) on %s", self.ip)
                return True
            # status == 2: still writing, keep polling.

        if rebooted:
            return True

        # ~10 min elapsed, status still 2, no reboot — case (b) genuine hang. Report
        # honestly so the caller retries / escalates instead of recording false
        # success. (A retry sometimes succeeds; the trigger is flaky.)
        self.logger.error(
            "firmware flash on %s did NOT complete within 600s — rpcFwFlash stuck "
            "at writing(2), no reboot. RT-610 flash-trigger hang (OBN bug #11); "
            "retry or escalate.", self.ip)
        return False'''


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found")
        sys.exit(1)
    content = TARGET.read_text()
    if MARKER in content:
        print("Bug 11 (westermo fw activation verify): ALREADY APPLIED")
        return
    if OLD not in content:
        print(f"ERROR: expected pattern not found in {TARGET}")
        print("Likely the file was modified upstream; review set_firmware_version manually before patching.")
        sys.exit(2)
    TARGET.write_text(content.replace(OLD, NEW))
    print("Bug 11 (westermo fw activation verify): PATCHED")


if __name__ == "__main__":
    main()
