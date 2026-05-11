#!/usr/bin/env python3
"""
fix_obn.py — apply OBN bug fixes 1–7 in-place on a CCU.

Idempotent: detects which patches are already applied and skips them.
Run as root after making the root filesystem writable:

    sudo btrfs property set / ro false
    sudo python3 /tmp/fix_obn.py
    sudo btrfs property set / ro true

Bugs covered (see troubleshooting-runbook.md for full descriptions):
  1. vdsrail.py set_firmware_version regex doesn't match "default image is now"
  2. vdsrail.py polling loops crash when SNMP returns None
  3. snmpdevice.py KeyError from pysnmp asyncore
  4. device.py needs_firmware_update AttributeError on None firmware
  5. update.py tftp_allowed ipset not pre-populated for restart safety
  6. tree.py NoneType crash on cross-consist LLDP neighbours
  7. vdsrail.py reboot() crashes when SNMP-get hostname returns None
"""
import re
import sys
from pathlib import Path

VDSRAIL = Path("/usr/share/obn/lib/device/vendor/vdsrail.py")
SNMPDEVICE = Path("/usr/share/obn/lib/device/snmpdevice.py")
DEVICE = Path("/usr/share/obn/lib/report/device.py")
UPDATE = Path("/usr/share/obn/cli/update.py")
TREE = Path("/usr/share/obn/lib/tree.py")


def patch(path: Path, old: str, new: str, marker: str, label: str) -> str:
    """Replace `old` with `new` in `path`. Detect if already patched via `marker`."""
    if not path.exists():
        return f"  {label}: SKIP (file not found: {path})"
    content = path.read_text()
    if marker in content:
        return f"  {label}: ALREADY APPLIED"
    if old not in content:
        return f"  {label}: PATTERN NOT FOUND (manual review needed)"
    path.write_text(content.replace(old, new))
    return f"  {label}: PATCHED"


def fix_bug_1():
    """vdsrail.py: regex for 'default image is now' alongside 'image loaded [...]'."""
    old = 'matchstr = r"Not running. System Firmware image loaded \\[(.*)\\]"'
    new = 'matchstr = r"Not running. System Firmware (?:default image is now|image loaded \\[)(.*?)\\]?$"'
    return patch(VDSRAIL, old, new,
                 marker="default image is now|image loaded",
                 label="Bug 1 (firmware regex)")


def fix_bug_2():
    """vdsrail.py: None guard around SNMP polling results in firmware + config loops."""
    # Firmware loop
    old1 = '''        result = ""
        for _ in range(120):
            sleep(1)
            result = self._snmp_get(
                self.device_config["snmp_firmware_task_running_oid"]
            )
            search = re.search("Not running", result)'''
    new1 = '''        result = ""
        for _ in range(120):
            sleep(1)
            result = self._snmp_get(
                self.device_config["snmp_firmware_task_running_oid"]
            )
            if not result:
                continue
            search = re.search("Not running", result)'''
    r1 = patch(VDSRAIL, old1, new1,
               marker='if not result:\n                continue\n            search = re.search("Not running", result)',
               label="Bug 2a (firmware polling None guard)")

    # Config loop
    old2 = '''        for _ in range(120):
            sleep(1)
            result = self._snmp_get(self.device_config["snmp_config_task_running_oid"])
            search = re.search("Not running", result)'''
    new2 = '''        for _ in range(120):
            sleep(1)
            result = self._snmp_get(self.device_config["snmp_config_task_running_oid"])
            if not result:
                continue
            search = re.search("Not running", result)'''
    r2 = patch(VDSRAIL, old2, new2,
               marker='if not result:\n                continue\n            search = re.search("Not running", result)',
               label="Bug 2b (config polling None guard)")
    # The marker check above will match if either bug 2a or 2b has been applied;
    # if 2a applied first, 2b will report ALREADY APPLIED but actually still need patching.
    # Re-read content to be sure.
    content = VDSRAIL.read_text()
    if old2 in content:
        VDSRAIL.write_text(content.replace(old2, new2))
        r2 = "  Bug 2b (config polling None guard): PATCHED (post-check)"
    return r1 + "\n" + r2


def fix_bug_3():
    """snmpdevice.py: KeyError guard around pysnmp generator."""
    old = '''        for error_indication, error_status, _, var_binds in generator:'''
    new = '''        try:
            gen_items = list(generator)
        except KeyError:
            return {}
        for error_indication, error_status, _, var_binds in gen_items:'''
    return patch(SNMPDEVICE, old, new,
                 marker="except KeyError:\n            return {}",
                 label="Bug 3 (pysnmp KeyError guard)")


def fix_bug_4():
    """device.py: firmware None guard in needs_firmware_update.
    Already partially patched on this CCU but re-check."""
    # The runbook fix is on the .endswith line; current code uses different pattern.
    # We check for the canonical bug pattern.
    old = '''return not self.firmware.endswith(self.target["firmware"])'''
    new = '''return bool(self.firmware) and not self.firmware.endswith(self.target["firmware"])'''
    return patch(DEVICE, old, new,
                 marker='return bool(self.firmware) and not self.firmware.endswith',
                 label="Bug 4 (firmware None guard)")


def fix_bug_5():
    """update.py: pre-populate tftp_allowed ipset for all targets before first batch."""
    old = '''    logger.info("calculated the update order")

    # Now, for each batch, we check if they contain devices we need to update.'''
    new = '''    logger.info("calculated the update order")

    # Bug 5 fix: pre-populate tftp_allowed ipset for all targets so that a
    # mid-run restart doesn't leave devices unable to fetch firmware.
    import subprocess as _sp
    for _dev in update_set.firmware_updates:
        _sp.run(["ipset", "add", "tftp_allowed", _dev.ip, "-exist"],
                capture_output=True)

    # Now, for each batch, we check if they contain devices we need to update.'''
    return patch(UPDATE, old, new,
                 marker="Bug 5 fix: pre-populate tftp_allowed ipset",
                 label="Bug 5 (TFTP ipset pre-population)")


def fix_bug_6():
    """tree.py: None guard for neighbours not in this consist (cross-coupled)."""
    old = '''                if neighbour_device.type == "BOX":
                    continue
                if neighbour_device.mac not in tree:'''
    new = '''                if neighbour_device is None:
                    continue  # neighbour not in this consist (e.g. coupled train on another subnet)
                if neighbour_device.type == "BOX":
                    continue
                if neighbour_device.mac not in tree:'''
    return patch(TREE, old, new,
                 marker="neighbour not in this consist",
                 label="Bug 6 (tree.py cross-consist guard)")


def fix_bug_7():
    """vdsrail.py: None guard on hostname before SNMP-set in reboot()."""
    old = '''    def reboot(self) -> bool:
        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])
        self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
        self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})'''
    new = '''    def reboot(self) -> bool:
        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])
        if hostname is not None:
            self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})
        self._snmp_set({self.device_config["snmp_reboot_oid"]: 3})'''
    return patch(VDSRAIL, old, new,
                 marker="if hostname is not None:\n            self._snmp_set",
                 label="Bug 7 (reboot hostname None guard)")


def main():
    print("Applying OBN bug fixes 1-7 (idempotent):")
    for fn in [fix_bug_1, fix_bug_2, fix_bug_3, fix_bug_4, fix_bug_5, fix_bug_6, fix_bug_7]:
        try:
            print(fn() if fn.__doc__ else f"  {fn.__name__}: ?")
        except Exception as e:
            print(f"  {fn.__name__}: ERROR — {e}")
    print("\nDone. Re-lock root with: sudo btrfs property set / ro true")


if __name__ == "__main__":
    main()
