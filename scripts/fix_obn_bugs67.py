import re

# ── Bug 7 fix: vdsrail.py reboot() — correct None guard ──────────────────────
path = "/usr/share/obn/lib/device/vendor/vdsrail.py"
with open(path) as f:
    src = f.read()

old7 = (
    '        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"]) or ""\n'
    '        self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})\n'
)
new7 = (
    '        hostname = self._snmp_get(self.device_config["snmp_get_hostname_oid"])\n'
    '        if hostname is not None:\n'
    '            self._snmp_set({self.device_config["snmp_set_hostname_oid"]: hostname})\n'
)
if old7 in src:
    src = src.replace(old7, new7, 1)
    print("vdsrail.py Bug7 (reboot hostname None guard): applied")
else:
    print("vdsrail.py Bug7: anchor not found — already patched or changed")

with open(path, "w") as f:
    f.write(src)

# ── Bug 6 fix: tree.py — None guard for coupled consist neighbours ────────────
# Cross-script idempotency note (added 2026-05-11 per audit finding F7):
#   fix_obn.py ALSO patches Bug 6 in this file, with a slightly different guard
#   comment ("...on another subnet"). If fix_obn.py has already run, applying
#   our patch on top produces TWO redundant guard lines back-to-back — both
#   correct, but the grep -c marker count returns 2 instead of the expected 1.
#   Detect either script's marker before patching to avoid the double-guard.
path2 = "/usr/share/obn/lib/tree.py"
with open(path2) as f:
    src2 = f.read()

# Detect prior patch from EITHER script. Both insert "if neighbour_device is None:"
# with a "neighbour not in this consist" comment on the next line.
already_patched = (
    "neighbour_device is None" in src2
    and "neighbour not in this consist" in src2
)

old6 = '                if neighbour_device.type == "BOX":\n                    continue\n'
new6 = (
    '                if neighbour_device is None:\n'
    '                    continue  # neighbour not in this consist (e.g. coupled train)\n'
    '                if neighbour_device.type == "BOX":\n'
    '                    continue\n'
)

if already_patched:
    print("tree.py Bug6: already patched by either fix_obn.py or a prior run — skipping (idempotent)")
elif old6 in src2:
    src2 = src2.replace(old6, new6, 1)
    print("tree.py Bug6 (coupled consist None guard): applied")
    with open(path2, "w") as f:
        f.write(src2)
else:
    print("tree.py Bug6: anchor not found AND no prior-patch marker — file in unexpected state, manual review needed")

print("\nDone. Verify:")
import subprocess
r = subprocess.run(["grep", "-n", "hostname is not None\|neighbour_device is None",
                    path, path2], capture_output=True, text=True)
print(r.stdout)
