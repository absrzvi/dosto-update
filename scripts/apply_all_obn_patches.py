#!/usr/bin/env python3
"""
apply_all_obn_patches.py — apply ALL 11 known OBN bug fixes on a DOSTO CCU
in ONE self-contained, idempotent run.

This is the "hand it to an engineer, they run it on the CCU" script. It bundles
every patch that used to live across fix_obn.py + fix_obn_bug8/9/10/11.py so
there is nothing to scp except this single file, and no manual btrfs ro-toggle
to remember.

--------------------------------------------------------------------------------
HOW TO USE
--------------------------------------------------------------------------------

  1. Copy this one file to the CCU (developer can't write /var/tmp directly):

       scp -i <openssh-key> apply_all_obn_patches.py developer@<ccu-ip>:/tmp/
       ssh  -i <openssh-key> developer@<ccu-ip> 'sudo mv /tmp/apply_all_obn_patches.py /var/tmp/'

     Stage in /var/tmp/ (not /tmp/) so the SAME file is visible inside the
     nd-systemupdate chroot for the persist step below.

  2a. APPLY NOW (active until next reboot) — the script unlocks btrfs, patches,
      re-locks, and verifies, all by itself:

       ssh -i <openssh-key> developer@<ccu-ip>
       sudo python3 /var/tmp/apply_all_obn_patches.py

  2b. PERSIST ACROSS REBOOT (recommended for any train you'll revisit) — run the
      exact same script INSIDE the persistent-edit chroot. It auto-detects the
      chroot and skips its own btrfs toggle (the chroot handles that):

       sudo /usr/sbin/nd-systemupdate.sh.dont shell   # fleet standard
       # (or: sudo /usr/sbin/nd-systemupdate.sh shell  if no .dont on this CCU)
       python3 /var/tmp/apply_all_obn_patches.py
       exit                                           # promotes work -> release -> new runN
       sudo /usr/local/sbin/safe_reboot

     After reboot, re-run step 2a's command with --check to confirm 11/11 survived.

  Other flags:
       --check      verify only; report per-bug status, change nothing, exit
       --no-btrfs   skip the btrfs ro-toggle (use if you manage locking yourself)

--------------------------------------------------------------------------------
THE 11 BUGS (see .claude/skills/dosto-obn-patches/SKILL.md for full detail)
--------------------------------------------------------------------------------
   1  vdsrail.py   firmware regex ("default image is now")
   2  vdsrail.py   None guards in the two SNMP polling loops (expect 2 hits)
   3  snmpdevice.py  pysnmp KeyError guard
   4  device.py    firmware None guard (needs_firmware_update)
   5  update.py    pre-populate tftp_allowed ipset
   6  tree.py      cross-consist neighbour None guard
   7  vdsrail.py   reboot() hostname None guard
   8  device.py    config None guard (needs_configuration_update)
   9  snmpdevice.py  pysnmp dispatcher thread-safety Lock
  10  report_dosto_neu.py  number_coaches BFS infinite-loop guard
  11  westermo.py  AP firmware activation verify (poll rpcFwFlash + uptime)

All 11 must be applied together — partial patches are worse than vanilla (they
leave crash/hang modes open so an update dies mid-run and writes partial state).
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# File locations under the OBN install.
# ---------------------------------------------------------------------------
VDSRAIL = Path("/usr/share/obn/lib/device/vendor/vdsrail.py")
SNMPDEVICE = Path("/usr/share/obn/lib/device/snmpdevice.py")
DEVICE = Path("/usr/share/obn/lib/report/device.py")
UPDATE = Path("/usr/share/obn/cli/update.py")
TREE = Path("/usr/share/obn/lib/tree.py")
REPORT_DOSTONEU = Path("/usr/share/obn/lib/report/report_dosto_neu.py")
WESTERMO = Path("/usr/share/obn/lib/device/vendor/westermo.py")

RPCFWFLASH_OID = "1.3.6.1.4.1.16177.1.400.1.3.2.1.0"

# Result codes returned by each fix function.
PATCHED = "PATCHED"
ALREADY = "ALREADY APPLIED"
NOT_FOUND = "PATTERN NOT FOUND (manual review needed)"
NO_FILE = "SKIP (file not found)"


# ---------------------------------------------------------------------------
# Small helpers.
# ---------------------------------------------------------------------------
def _apply(path: Path, old: str, new: str, marker: str):
    """Replace one occurrence of `old` with `new` in `path`.

    Returns (status, path). Idempotent via `marker`. Never raises on a
    missing pattern — reports NOT_FOUND so the caller can decide.
    """
    if not path.exists():
        return NO_FILE, path
    content = path.read_text()
    if marker in content:
        return ALREADY, path
    if old not in content:
        return NOT_FOUND, path
    path.write_text(content.replace(old, new, 1))
    return PATCHED, path


def _count(path: Path, needle: str) -> int:
    if not path.exists():
        return -1
    return path.read_text().count(needle)


# ---------------------------------------------------------------------------
# Bugs 1-7 — same edits as scripts/fix_obn.py.
# ---------------------------------------------------------------------------
def fix_bug_1():
    old = 'matchstr = r"Not running. System Firmware image loaded \\[(.*)\\]"'
    new = 'matchstr = r"Not running. System Firmware (?:default image is now|image loaded \\[)(.*?)\\]?$"'
    return [_apply(VDSRAIL, old, new, marker="default image is now")]


def fix_bug_2():
    """Two SNMP polling loops in vdsrail.py — firmware side and config side."""
    results = []

    old1 = ('        result = ""\n'
            '        for _ in range(120):\n'
            '            sleep(1)\n'
            '            result = self._snmp_get(\n'
            '                self.device_config["snmp_firmware_task_running_oid"]\n'
            '            )\n'
            '            search = re.search("Not running", result)')
    new1 = ('        result = ""\n'
            '        for _ in range(120):\n'
            '            sleep(1)\n'
            '            result = self._snmp_get(\n'
            '                self.device_config["snmp_firmware_task_running_oid"]\n'
            '            )\n'
            '            if not result:\n'
            '                continue\n'
            '            search = re.search("Not running", result)')
    # For the firmware loop we can't use the shared "if not result:" marker
    # (the config loop shares it). Detect this specific loop by its patched form.
    if VDSRAIL.exists() and new1 in VDSRAIL.read_text():
        results.append((ALREADY, VDSRAIL))
    else:
        results.append(_apply(VDSRAIL, old1, new1, marker="\x00never\x00"))

    old2 = ('        for _ in range(120):\n'
            '            sleep(1)\n'
            '            result = self._snmp_get(self.device_config["snmp_config_task_running_oid"])\n'
            '            search = re.search("Not running", result)')
    new2 = ('        for _ in range(120):\n'
            '            sleep(1)\n'
            '            result = self._snmp_get(self.device_config["snmp_config_task_running_oid"])\n'
            '            if not result:\n'
            '                continue\n'
            '            search = re.search("Not running", result)')
    if VDSRAIL.exists() and new2 in VDSRAIL.read_text():
        results.append((ALREADY, VDSRAIL))
    else:
        results.append(_apply(VDSRAIL, old2, new2, marker="\x00never\x00"))

    return results


def fix_bug_3():
    old = '        for error_indication, error_status, _, var_binds in generator:'
    new = ('        try:\n'
           '            gen_items = list(generator)\n'
           '        except KeyError:\n'
           '            return {}\n'
           '        for error_indication, error_status, _, var_binds in gen_items:')
    return [_apply(SNMPDEVICE, old, new, marker="except KeyError:\n            return {}")]


def fix_bug_4():
    old = '        return not self.firmware.endswith(self.target["firmware"])'
    new = '        return bool(self.firmware) and not self.firmware.endswith(self.target["firmware"])'
    return [_apply(DEVICE, old, new, marker="bool(self.firmware) and not self.firmware.endswith")]


def fix_bug_5():
    old = ('    logger.info("calculated the update order")\n'
           '\n'
           '    # Now, for each batch, we check if they contain devices we need to update.')
    new = ('    logger.info("calculated the update order")\n'
           '\n'
           '    # Bug 5 fix: pre-populate tftp_allowed ipset for all targets so that a\n'
           '    # mid-run restart doesn\'t leave devices unable to fetch firmware.\n'
           '    import subprocess as _sp\n'
           '    for _dev in update_set.firmware_updates:\n'
           '        _sp.run(["ipset", "add", "tftp_allowed", _dev.ip, "-exist"],\n'
           '                capture_output=True)\n'
           '\n'
           '    # Now, for each batch, we check if they contain devices we need to update.')
    return [_apply(UPDATE, old, new, marker="Bug 5 fix: pre-populate tftp_allowed ipset")]


def fix_bug_6():
    old = ('                if neighbour_device.type == "BOX":\n'
           '                    continue\n'
           '                if neighbour_device.mac not in tree:')
    new = ('                if neighbour_device is None:\n'
           '                    continue  # neighbour not in this consist (e.g. coupled train on another subnet)\n'
           '                if neighbour_device.type == "BOX":\n'
           '                    continue\n'
           '                if neighbour_device.mac not in tree:')
    return [_apply(TREE, old, new, marker="neighbour not in this consist")]


def fix_bug_7():
    old = ('    def reboot(self) -> bool:\n'
           '        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])\n'
           '        self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})\n'
           '        self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})')
    new = ('    def reboot(self) -> bool:\n'
           '        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])\n'
           '        if hostname is not None:\n'
           '            self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})\n'
           '        self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})')
    return [_apply(VDSRAIL, old, new, marker="if hostname is not None:\n            self._snmp_set")]


# ---------------------------------------------------------------------------
# Bug 8 — device.py config None guard (from fix_obn_bug8.py).
# ---------------------------------------------------------------------------
def fix_bug_8():
    old = '        return not self.config.endswith(self.target["config"])'
    new = '        return bool(self.config) and not self.config.endswith(self.target["config"])'
    return [_apply(DEVICE, old, new, marker="bool(self.config) and not self.config.endswith")]


# ---------------------------------------------------------------------------
# Bug 9 — pysnmp dispatcher thread-safety Lock (from fix_obn_bug9_*.py).
# Two-step edit (import + lock block, then wrap list(generator)) so it can't
# use the simple _apply helper.
# ---------------------------------------------------------------------------
def fix_bug_9():
    marker = "_SNMP_DISPATCH_LOCK"
    if not SNMPDEVICE.exists():
        return [(NO_FILE, SNMPDEVICE)]
    src = SNMPDEVICE.read_text()
    if marker in src:
        return [(ALREADY, SNMPDEVICE)]

    if "import threading" not in src:
        src = re.sub(r"(\nimport logging\n)", r"\1import threading\n", src, count=1)

    lock_block = (
        "\n"
        "# Bug 9 fix: pysnmp's asyncore transportDispatcher is not thread-safe.\n"
        "# OBN's process_batch runs SNMP calls from a ThreadPoolExecutor sharing\n"
        "# one SnmpEngine, and the dispatcher's out-queue races on pop(0). We\n"
        "# serialise the single `list(generator)` site in _snmp_parse_results\n"
        "# with this module-level lock. Released between SNMP calls.\n"
        f"{marker} = threading.Lock()\n"
    )
    anchor = "from pysnmp.proto.rfc1902 import TimeTicks"
    if anchor not in src:
        return [(NOT_FOUND, SNMPDEVICE)]
    src = src.replace(anchor + "\n", anchor + "\n" + lock_block, 1)

    # Bug 3 must be applied first (it introduces the `gen_items = list(generator)`
    # site this wraps). fix_bug_3 runs before fix_bug_9 in main().
    old = "        try:\n            gen_items = list(generator)\n"
    new = ("        try:\n"
           f"            with {marker}:\n"
           "                gen_items = list(generator)\n")
    if old not in src:
        return [(NOT_FOUND, SNMPDEVICE)]
    src = src.replace(old, new, 1)

    SNMPDEVICE.write_text(src)
    return [(PATCHED, SNMPDEVICE)]


# ---------------------------------------------------------------------------
# Bug 10 — report_dosto_neu BFS guard (from fix_obn_bug10_*.py).
# ---------------------------------------------------------------------------
def fix_bug_10():
    marker = "# NDP-PATCH-BUG10-BFS-GUARD"
    old = ("                    # nv6 - END\n"
           "\n"
           "                # Add to_device to queue\n"
           "                queue.appendleft(to_device)\n"
           "                continue\n")
    new = ("                    # nv6 - END\n"
           "\n"
           f"                # Add to_device to queue {marker}\n"
           "                # Bug 10 fix: only enqueue if coach_number was assigned in\n"
           "                # one of the branches above. Without this, APs and edge\n"
           "                # switches whose conditions didn't match get re-enqueued\n"
           "                # forever, hanging obn report at 100% CPU.\n"
           "                if to_device.coach_number is not None:\n"
           "                    queue.appendleft(to_device)\n"
           "                continue\n")
    return [_apply(REPORT_DOSTONEU, old, new, marker=marker)]


# ---------------------------------------------------------------------------
# Bug 11 — westermo AP firmware activation verify (from fix_obn_bug11_*.py).
# ---------------------------------------------------------------------------
def fix_bug_11():
    marker = "# NDP-PATCH-BUG11-FW-VERIFY"
    old = ('''        # Send instructions to the device.
        self.logger.debug("sending firmware update instructions")
        result = self._snmp_set(firmware_instructions)
        if result.get("1.3.6.1.4.1.16177.1.400.1.3.2.1.0") != 2:
            self.logger.debug("something happened on the way to heaven")
            return False

        return True''')
    new = (f'''        # Send instructions to the device.
        self.logger.debug("sending firmware update instructions")
        result = self._snmp_set(firmware_instructions)
        if result.get("{RPCFWFLASH_OID}") != 2:
            self.logger.debug("something happened on the way to heaven")
            return False

        # {marker}
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
        return False''')
    return [_apply(WESTERMO, old, new, marker=marker)]


# ---------------------------------------------------------------------------
# Verification — the same grep markers dosto-obn-patches --check uses.
# Returns list of (bug_no, ok, detail).
# ---------------------------------------------------------------------------
def verify():
    checks = [
        (1, VDSRAIL, "default image is now", lambda c: c >= 1),
        (2, VDSRAIL, "if not result:", lambda c: c >= 2),
        (3, SNMPDEVICE, "except KeyError:", lambda c: c >= 1),
        (4, DEVICE, "bool(self.firmware) and not self.firmware.endswith", lambda c: c >= 1),
        (5, UPDATE, "Bug 5 fix: pre-populate tftp_allowed ipset", lambda c: c >= 1),
        (6, TREE, "neighbour not in this consist", lambda c: c >= 1),
        (7, VDSRAIL, "if hostname is not None:", lambda c: c >= 1),
        (8, DEVICE, "bool(self.config) and not self.config.endswith", lambda c: c >= 1),
        (9, SNMPDEVICE, "_SNMP_DISPATCH_LOCK", lambda c: c >= 2),
        (10, REPORT_DOSTONEU, "NDP-PATCH-BUG10-BFS-GUARD", lambda c: c >= 1),
        (11, WESTERMO, "NDP-PATCH-BUG11-FW-VERIFY", lambda c: c >= 1),
    ]
    out = []
    for bug, path, needle, ok_fn in checks:
        cnt = _count(path, needle)
        if cnt < 0:
            out.append((bug, False, f"file not found: {path}"))
        else:
            out.append((bug, ok_fn(cnt), f"{cnt}x '{needle}' in {path.name}"))
    return out


# ---------------------------------------------------------------------------
# btrfs ro-toggle — only on a live rootfs, never inside the chroot.
# ---------------------------------------------------------------------------
def _in_chroot() -> bool:
    """Best-effort chroot detection.

    nd-systemupdate.sh's `shell` gives a chroot whose / differs from the real
    root's mount. If we can't tell, assume NOT in a chroot (the safe default —
    we then do the btrfs toggle, which is harmless if / is already rw).
    """
    try:
        # In a chroot, /proc/1/root/. and /. usually have different device/inode.
        root_stat = os.stat("/")
        init_root = os.stat("/proc/1/root/.")
        return (root_stat.st_dev, root_stat.st_ino) != (init_root.st_dev, init_root.st_ino)
    except Exception:
        return False


def _btrfs_set_ro(ro: bool) -> bool:
    val = "true" if ro else "false"
    r = subprocess.run(["btrfs", "property", "set", "/", "ro", val],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  WARNING: `btrfs property set / ro {val}` failed: "
              f"{(r.stderr or r.stdout).strip()}")
        return False
    return True


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
FIXES = [
    ("Bug 1  (vdsrail firmware regex)", fix_bug_1),
    ("Bug 2  (vdsrail polling None guards x2)", fix_bug_2),
    ("Bug 3  (snmpdevice KeyError guard)", fix_bug_3),
    ("Bug 4  (device.py firmware None guard)", fix_bug_4),
    ("Bug 5  (update.py tftp ipset)", fix_bug_5),
    ("Bug 6  (tree.py cross-consist guard)", fix_bug_6),
    ("Bug 7  (vdsrail reboot hostname guard)", fix_bug_7),
    ("Bug 8  (device.py config None guard)", fix_bug_8),
    ("Bug 9  (pysnmp dispatcher Lock)", fix_bug_9),
    ("Bug 10 (report_dosto_neu BFS guard)", fix_bug_10),
    ("Bug 11 (westermo fw activation verify)", fix_bug_11),
]


def print_verification():
    print("\nVerification (grep markers):")
    results = verify()
    all_ok = True
    for bug, ok, detail in results:
        mark = "OK " if ok else "!! "
        if not ok:
            all_ok = False
        print(f"  [{mark}] Bug {bug:>2}: {detail}")
    total_ok = sum(1 for _, ok, _ in results if ok)
    print(f"\n  => {total_ok}/11 patched.")
    if all_ok:
        print("  All 11 present. OBN is safe to run update/report on this snapshot.")
    else:
        print("  NOT all 11 present — do NOT run `obn report` if any device may be")
        print("  offline (Bug 10 hang), and do NOT run parallel `obn update` (Bug 9).")
        print("  A '!!' with count 0 and 'PATTERN NOT FOUND' during apply means the file")
        print("  was in an unexpected state — review that file manually.")
    return all_ok


def main():
    ap = argparse.ArgumentParser(
        description="Apply all 11 OBN bug patches on a DOSTO CCU (self-contained, idempotent).")
    ap.add_argument("--check", action="store_true",
                    help="Verify only; do not modify anything.")
    ap.add_argument("--no-btrfs", action="store_true",
                    help="Skip the btrfs ro-toggle (use if you manage locking yourself).")
    args = ap.parse_args()

    obn_root = Path("/usr/share/obn")
    if not obn_root.exists():
        print("ERROR: /usr/share/obn not found — is this a CCU with OBN installed?",
              file=sys.stderr)
        return 1

    if args.check:
        # Read-only: greppable files are world-readable, so no root needed. If a
        # file happens to be root-only on some image, re-run with sudo.
        print("OBN patch check (read-only):")
        return 0 if print_verification() else 2

    if os.geteuid() != 0:
        print("ERROR: applying patches requires root (use sudo).", file=sys.stderr)
        return 1

    in_chroot = _in_chroot()
    do_toggle = not args.no_btrfs and not in_chroot

    print("Applying all 11 OBN bug patches (idempotent).")
    print(f"  context: {'INSIDE nd-systemupdate chroot (persist)' if in_chroot else 'live rootfs (active until reboot)'}")
    if in_chroot:
        print("  -> chroot handles rootfs writability; skipping btrfs toggle.")
        print("  -> patches will PERSIST when you `exit` the chroot and reboot.")
    elif args.no_btrfs:
        print("  -> --no-btrfs: assuming / is already writable.")
    else:
        print("  -> live run: will unlock btrfs, patch, then re-lock. These patches")
        print("     will be WIPED on next reboot unless you also run inside the chroot.")

    if do_toggle:
        print("\nUnlocking rootfs: btrfs property set / ro false")
        if not _btrfs_set_ro(False):
            print("Could not unlock rootfs — aborting before any edit.")
            return 3

    try:
        print("")
        any_not_found = False
        for label, fn in FIXES:
            try:
                results = fn()
            except Exception as e:
                print(f"  {label}: ERROR — {e}")
                any_not_found = True
                continue
            # Collapse multi-part results (bug 2) into one status line.
            statuses = [s for s, _ in results]
            if all(s == ALREADY for s in statuses):
                status = ALREADY
            elif any(s == NOT_FOUND for s in statuses):
                status = NOT_FOUND
                any_not_found = True
            elif any(s == NO_FILE for s in statuses):
                status = NO_FILE
            else:
                status = PATCHED
            print(f"  {label}: {status}")
    finally:
        if do_toggle:
            print("\nRe-locking rootfs: btrfs property set / ro true")
            _btrfs_set_ro(True)

    all_ok = print_verification()

    if not in_chroot and all_ok:
        print("\nNOTE: to make these survive a reboot, run this same script inside:")
        print("      sudo /usr/sbin/nd-systemupdate.sh.dont shell")
        print("      python3 /var/tmp/apply_all_obn_patches.py")
        print("      exit && sudo /usr/local/sbin/safe_reboot")

    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
