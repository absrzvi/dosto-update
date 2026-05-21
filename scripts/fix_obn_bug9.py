# Bug 9 fix: report_dosto_neu.py:number_coaches() infinite-loops when a neighbour
# device cannot be assigned a coach number (missing switch on the consist, or
# duplicate/unexpected position triggering no topology rule). The existing visited
# guard (to_device.coach_number is not None) only filters devices that already
# have a number — but the loop unconditionally re-enqueues to_device at the end,
# even when no rule fired and coach_number stayed None. Each iteration re-pops,
# fails to assign, re-enqueues → spin forever at 99% CPU.
#
# Fix: only enqueue to_device if a topology rule actually assigned coach_number
# during this iteration. Triggered on Fzg 130 (duplicate misimaged switch
# positions, 2026-05-12) and Fzg 191 (missing switches C1/C3 offline, 2026-05-20).
#
# Idempotent.

path = "/usr/share/obn/lib/report/report_dosto_neu.py"
with open(path) as f:
    src = f.read()

old = """                # Add to_device to queue
                queue.appendleft(to_device)
                continue"""

new = """                # Bug 9 fix: only enqueue if a topology rule actually assigned
                # this device a coach number. Otherwise the device sits in the queue
                # forever (coach_number stays None, visited-guard at top never fires).
                # Triggered on Fzg 130 (duplicate positions) and Fzg 191 (missing
                # switches C1/C3 offline).
                if to_device.coach_number is not None:
                    queue.appendleft(to_device)
                continue"""

if old in src:
    src = src.replace(old, new, 1)
    print("report_dosto_neu.py Bug9 (number_coaches BFS guard): applied")
elif "Bug 9 fix:" in src:
    print("report_dosto_neu.py Bug9: already patched")
else:
    print("report_dosto_neu.py Bug9: anchor not found — file structure changed, manual review needed")

with open(path, "w") as f:
    f.write(src)

import subprocess
r = subprocess.run(["grep", "-n", "Bug 9 fix:", path], capture_output=True, text=True)
print(r.stdout)
