#!/usr/bin/env python3
"""
Enable nv2 (2-coach) support in OBN's DOSTO NEU coach-numbering BFS.

Context: the OEBB-251 2-coach bench (NMS train 2123 / OEBB-Bench-2C, CCU
box1-t123 / 10.179.123.1) cannot be discovered because
report_dosto_neu.py::number_coaches() has no "nv2" entry in its train-type
maps, so with train_type=nv2 it falls back to nv4 defaults (4 coaches, CCU in
coach 2) and mis-numbers / fails. Result: NMS registers all devices as coach 2
(R2_*), so the consist diagram shows coach A as "N/A".

Decided topology (engineer, 2026-06-04):
  - Coach A = 1, Coach B = 2. CCU is in coach A => ccu1_coach = 1, max_coach = 2.
  - CCU bond re-cabled so lan0 -> A1 (coach-1 SW1), lan1 -> A3 (coach-1 SW3),
    matching OBN's existing BOX->SW LAN1/LAN2 seed rule (lan0->LAN1->dev1,
    lan1->LAN2->dev3). No new seed code needed.
  - Inter-coach A<->B trunk is A1.e0-1 <-> B1.e0-1 (SW1<->SW1 on e0-1). The
    existing inter-coach SW1->SW1 rule keys on e0-0, so a new e0-1 hop rule is
    required to cross from coach 1 to coach 2.

This script makes THREE idempotent edits to
/usr/share/obn/lib/report/report_dosto_neu.py:

  1. Add "nv2" to ccu1_coach_map (=1) and max_coaches (=2).
  2. Add an inter-coach hop rule: SW1 of the ccu1 (==first) coach reached on
     port E0-1 -> SW1 of the next coach (+1). Collision-free: no existing rule
     matches (device_number==1 AND port==E0_1); all dev1 rules key on E0_0.
  3. Fold in the Bug-10 BFS guard (only enqueue to_device if a coach_number was
     assigned this iteration) -- this file variant lacks it, and enabling the
     nv2 BFS path would otherwise hang obn report at 100% CPU on APs / edge
     switches. (Same fix as fix_obn_bug10_report_dosto_neu_bfs.py, adapted to
     this 162-line file variant.)

File:   /usr/share/obn/lib/report/report_dosto_neu.py
Target md5 (pre-patch, bench box1-t123 2026-06-04): bf2c9d9dd02500a413cb942d229bf7f5

Idempotent -- safe to run twice. Run inside the NDSU chroot to persist
(/var/tmp is bind-mounted; /tmp is not). File any upstream change as an R&D
ticket alongside OBN bugs 1-10.
"""
from pathlib import Path
import sys

TARGET = Path("/usr/share/obn/lib/report/report_dosto_neu.py")

# ---- Edit 1: dict entries -------------------------------------------------
DICT_MARKER = "nv2"  # presence of "nv2" key in the maps == edit 1 applied
DICT_OLD = (
    '        ccu1_coach_map = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}\n'
    '        max_coaches = {"nv4": 4, "nv6": 6, "fv5": 5, "fv6": 6}\n'
)
DICT_NEW = (
    '        ccu1_coach_map = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3, "nv2": 1}  # NDP-PATCH-NV2\n'
    '        max_coaches = {"nv4": 4, "nv6": 6, "fv5": 5, "fv6": 6, "nv2": 2}  # NDP-PATCH-NV2\n'
)

# ---- Edit 2: inter-coach e0-1 hop rule ------------------------------------
# Insert immediately AFTER the existing "SW1 of first and last coaches connect
# to SW3 of same coach on port E0-0" block, before the next elif.
HOP_MARKER = "# NDP-PATCH-NV2-INTERCOACH-E01"
HOP_ANCHOR = (
    "                        # SW1 of first and last coaches connect to SW3 of same coach on port E0-0\n"
    "                        elif (\n"
    "                            from_device.device_number == 1\n"
    "                            and from_device.coach_number in [1, max_coach]\n"
    "                            and port == DostoNeuPort.E0_0\n"
    "                        ):\n"
    "                            to_device.device_number = 3\n"
    "                            to_device.coach_number = from_device.coach_number\n"
)
HOP_INSERT = (
    "                        # SW1 of the ccu1 (first) coach reached on E0-1 -> SW1 of next coach (+1) "
    + HOP_MARKER + "\n"
    "                        # nv2 bench: A1.e0-1 <-> B1.e0-1 is the inter-coach trunk.\n"
    "                        elif (\n"
    "                            from_device.device_number == 1\n"
    "                            and from_device.coach_number == ccu1_coach\n"
    "                            and from_device.coach_number < max_coach\n"
    "                            and port == DostoNeuPort.E0_1\n"
    "                        ):\n"
    "                            to_device.device_number = 1\n"
    "                            to_device.coach_number = from_device.coach_number + 1\n"
)

# ---- Edit 3: Bug-10 BFS guard --------------------------------------------
GUARD_MARKER = "# NDP-PATCH-BUG10-BFS-GUARD"
GUARD_OLD = (
    "                # Add to_device to queue\n"
    "                queue.appendleft(to_device)\n"
    "                continue\n"
)
GUARD_NEW = (
    "                # Add to_device to queue " + GUARD_MARKER + "\n"
    "                # Only enqueue if a coach_number was assigned in a branch\n"
    "                # above; otherwise APs / edge switches re-enqueue forever\n"
    "                # and obn report hangs at 100% CPU.\n"
    "                if to_device.coach_number is not None:\n"
    "                    queue.appendleft(to_device)\n"
    "                continue\n"
)


def apply_edit(content, name, marker, old, new, anchor=None, mode="replace"):
    if marker in content:
        print(f"  [{name}] ALREADY APPLIED")
        return content, False
    if mode == "replace":
        if old not in content:
            print(f"  [{name}] ERROR: anchor text not found -- review file manually")
            sys.exit(2)
        return content.replace(old, new), True
    if mode == "insert_after":
        if anchor not in content:
            print(f"  [{name}] ERROR: insertion anchor not found -- review file manually")
            sys.exit(2)
        return content.replace(anchor, anchor + new), True
    raise ValueError(mode)


def main():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found")
        sys.exit(1)
    content = TARGET.read_text()
    changed = False

    content, c1 = apply_edit(content, "nv2 dict entries", "NDP-PATCH-NV2",
                             DICT_OLD, DICT_NEW)
    changed |= c1
    content, c2 = apply_edit(content, "nv2 inter-coach e0-1 hop", HOP_MARKER,
                             None, HOP_INSERT, anchor=HOP_ANCHOR, mode="insert_after")
    changed |= c2
    content, c3 = apply_edit(content, "bug-10 BFS guard", GUARD_MARKER,
                             GUARD_OLD, GUARD_NEW)
    changed |= c3

    if changed:
        TARGET.write_text(content)
        print("nv2 report_dosto_neu patch: WRITTEN")
    else:
        print("nv2 report_dosto_neu patch: nothing to do (all applied)")


if __name__ == "__main__":
    main()
