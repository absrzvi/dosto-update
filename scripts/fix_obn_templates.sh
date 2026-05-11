#!/bin/bash
# Usage: sudo bash fix_obn_templates.sh
# Fixes /etc/obn/template/nv6-*.cfg files:
#   1. Sets correct train_id on line 1
#   2. Quotes any bare {% include foo.j2 %} paths

read -p "Enter train_id: " train_id

sudo python3 << EOF
import re, glob

train_id = $train_id
files = sorted(glob.glob("/etc/obn/template/nv6-*.cfg"))

for path in files:
    lines = open(path).readlines()

    # Fix line 1
    lines[0] = "{%- set train_id = " + str(train_id) + " -%}\n"

    txt = "".join(lines)

    # Quote any unquoted include paths: {% include foo.j2 %} -> {% include 'foo.j2' %}
    txt = re.sub(
        r"""{%-?\s*include\s+([^'"{\s][^\s}]*)\s*-?%}""",
        lambda m: "{{% include '{}' %}}".format(m.group(1).strip()),
        txt
    )

    open(path, "w").write(txt)
    print("Updated", path)

print("Done.")
EOF
