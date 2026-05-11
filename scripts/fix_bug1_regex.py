# Bug 1 fix: vdsrail.py set_firmware_version() regex — direct replacement
path = "/usr/share/obn/lib/device/vendor/vdsrail.py"
with open(path) as f:
    src = f.read()

old = r'        matchstr = r"Not running. System Firmware image loaded \[(.*)\]"'
new = (
    '        # Handle both response formats depending on switch firmware state\n'
    '        matchstr = r"Not running. System Firmware (?:default image is now|image loaded \\[)(.*?)\\]?"'
)

if old in src:
    src = src.replace(old, new, 1)
    print("vdsrail.py Bug1 (regex): applied")
else:
    print("vdsrail.py Bug1: anchor not found, showing context...")
    # Find the line manually
    for i, line in enumerate(src.splitlines()):
        if 'matchstr' in line:
            print(f"  line {i+1}: {repr(line)}")

with open(path, "w") as f:
    f.write(src)

# Verify
import subprocess
r = subprocess.run(["grep", "-n", "matchstr", path], capture_output=True, text=True)
print(r.stdout)
