# Bug 8 fix: device.py needs_configuration_update() crashes when self.config is None
path = "/usr/share/obn/lib/report/device.py"
with open(path) as f:
    src = f.read()

old = '        return not self.config.endswith(self.target["config"])'
new = '        return bool(self.config) and not self.config.endswith(self.target["config"])'

if old in src:
    src = src.replace(old, new, 1)
    print("device.py Bug8 (config None guard): applied")
else:
    print("device.py Bug8: anchor not found — already patched or changed")

with open(path, "w") as f:
    f.write(src)

# Verify
import subprocess
r = subprocess.run(["grep", "-n", "bool(self.config)", path], capture_output=True, text=True)
print(r.stdout)
