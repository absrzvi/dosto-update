#!/usr/bin/env python3
# Cross-reference live SNMP admin-up/oper-down ports against nv6 template design
# for 4736-114 / Fzg 142 (6027). Ad-hoc analysis, 2026-06-20.

# SNMP admin-up / oper-DOWN observed live (this session):
down = {
 "A1": ["e0-2", "e0-5", "e2-0", "e2-2"],
 "A2": [],
 "A3": ["e0-2"],
 "C1": ["e0-5", "e2-1", "e2-3"],
 "C2": ["e2-1"],
 "C3": [],
 "D1": ["e0-5"],
 "D2": ["e2-0"],
 "D3": [],
 "E1": ["e0-5", "e2-0"],
 "E2": ["e2-2"],
 "E3": ["e2-0"],
 "F1": ["e0-5", "e2-3"],
 "F2": ["e0-5"],
 "F3": [],
 "B1": ["e0-2", "e0-5", "e2-0", "e2-1", "e2-3"],
 "B2": ["e2-2"],
 "B3": ["e0-2"],
}

# Template enable(1/0) + description, from nv6-*.cfg dump (only e0-2/e0-5/e2-0..5)
D = {
 "A1": {"e0-2": (1, "Frontkupplung A1"), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm A7"), "e2-1": (1, "Bildschirm A5"), "e2-2": (1, "Bildschirm A1"), "e2-3": (1, "Bildschirm A3"), "e2-4": (1, "ADU A"), "e2-5": (1, "Audio Amp. A1")},
 "A2": {"e0-2": (0, ""), "e0-5": (0, "Reserved"), "e2-0": (1, "Bildschirm A8"), "e2-1": (1, "Bildschirm A6"), "e2-2": (1, "Bildschirm A2"), "e2-3": (1, "Bildschirm A4"), "e2-4": (0, ""), "e2-5": (1, "Audio Amp. A2")},
 "A3": {"e0-2": (1, "Frontkupplung A3"), "e0-5": (0, "reserved"), "e2-0": (0, ""), "e2-1": (0, ""), "e2-2": (0, ""), "e2-3": (0, ""), "e2-4": (1, "ADU AR"), "e2-5": (0, "Service VLAN PWLAN")},
 "C1": {"e0-2": (0, ""), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm C7"), "e2-1": (1, "Bildschirm C5"), "e2-2": (1, "Bildschirm C1"), "e2-3": (1, "Bildschirm C3"), "e2-4": (1, "Bildschirm C"), "e2-5": (1, "Audio Amp. C1")},
 "C2": {"e0-2": (0, ""), "e0-5": (0, "Reserved"), "e2-0": (1, "Bildschirm C8"), "e2-1": (1, "Bildschirm C6"), "e2-2": (1, "Bildschirm C2"), "e2-3": (1, "Bildschirm C4"), "e2-4": (1, "Bildschirm C11"), "e2-5": (1, "Audio Amp. C2")},
 "C3": {k: (0, "") for k in ["e0-2", "e0-5", "e2-0", "e2-1", "e2-2", "e2-3", "e2-4", "e2-5"]},
 "D1": {"e0-2": (1, "OBS D1"), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm D7"), "e2-1": (1, "Bildschirm D5"), "e2-2": (1, "Bildschirm D1"), "e2-3": (1, "Bildschirm D3"), "e2-4": (1, "Bildschirm D"), "e2-5": (1, "Audio Amp. D1")},
 "D2": {"e0-2": (0, "OBS D2 Reserved"), "e0-5": (0, "Reserved"), "e2-0": (1, "Bildschirm D8"), "e2-1": (1, "Bildschirm D6"), "e2-2": (1, "Bildschirm D2"), "e2-3": (1, "Bildschirm D4"), "e2-4": (1, "Bildschirm D11"), "e2-5": (1, "Audio Amp. D2")},
 "D3": {"e0-2": (1, "OBS D3"), "e0-5": (0, "Reserved"), "e2-0": (0, ""), "e2-1": (0, ""), "e2-2": (0, ""), "e2-3": (0, ""), "e2-4": (0, ""), "e2-5": (0, "")},
 "E1": {"e0-2": (0, ""), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm E7"), "e2-1": (1, "Bildschirm E5"), "e2-2": (1, "Bildschirm E1"), "e2-3": (1, "Bildschirm E3"), "e2-4": (1, "Bildschirm E"), "e2-5": (1, "Audio Amp. E1")},
 "E2": {"e0-2": (0, ""), "e0-5": (0, "Reserved"), "e2-0": (1, "Bildschirm E8"), "e2-1": (1, "Bildschirm E6"), "e2-2": (1, "Bildschirm E2"), "e2-3": (1, "Bildschirm E4"), "e2-4": (1, "Bildschirm E11"), "e2-5": (1, "Audio Amp. E2")},
 "E3": {"e0-2": (0, ""), "e0-5": (0, "Reserved"), "e2-0": (1, "Energiezaehler E"), "e2-1": (0, ""), "e2-2": (0, ""), "e2-3": (0, ""), "e2-4": (0, ""), "e2-5": (0, "")},
 "F1": {"e0-2": (0, ""), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm F7"), "e2-1": (1, "Bildschirm F5"), "e2-2": (1, "Bildschirm F1"), "e2-3": (1, "Bildschirm F3"), "e2-4": (1, "Bildschirm F"), "e2-5": (1, "Audio Amp. F1")},
 "F2": {"e0-2": (0, ""), "e0-5": (1, "Reserved"), "e2-0": (1, "Bildschirm F8"), "e2-1": (1, "Bildschirm F6"), "e2-2": (1, "Bildschirm F2"), "e2-3": (1, "Bildschirm F"), "e2-4": (1, "Bildschirm F11"), "e2-5": (1, "Audio Amp. F2")},
 "F3": {k: (0, "") for k in ["e0-2", "e0-5", "e2-0", "e2-1", "e2-2", "e2-3", "e2-4", "e2-5"]},
 "B1": {"e0-2": (1, "Frontkupplung B1"), "e0-5": (1, "Service FIS/CCTV"), "e2-0": (1, "Bildschirm B7"), "e2-1": (1, "Bildschirm B5"), "e2-2": (1, "Bildschirm B1"), "e2-3": (1, "Bildschirm B3"), "e2-4": (1, "ADU B"), "e2-5": (1, "Audio Amp. B1")},
 "B2": {"e0-2": (0, ""), "e0-5": (0, "Reserved"), "e2-0": (1, "Bildschirm B8"), "e2-1": (1, "Bildschirm B6"), "e2-2": (1, "Bildschirm B2"), "e2-3": (1, "Bildschirm B4"), "e2-4": (0, ""), "e2-5": (1, "Audio Amp. B2")},
 "B3": {"e0-2": (1, "Frontkupplung B3"), "e0-5": (0, "Reserved"), "e2-0": (0, ""), "e2-1": (0, ""), "e2-2": (0, ""), "e2-3": (0, ""), "e2-4": (1, "ADU BR"), "e2-5": (0, "Service VLAN PWLAN")},
}


def is_coupler(desc):
    return "Frontkupplung" in desc or desc.startswith("OBS")


real, expected_solo, service, drift = [], [], [], []
for sw, ports in down.items():
    for p in ports:
        en, desc = D[sw].get(p, (None, "?"))
        if en == 0:
            drift.append((sw, p, desc))
        elif is_coupler(desc):
            expected_solo.append((sw, p, desc))
        elif p == "e0-5":
            service.append((sw, p, desc))
        else:
            real.append((sw, p, desc))

print("=== REAL candidate faults: template-ENABLED end-device port, link DOWN ===")
for sw, p, d in real:
    print(f"  {sw} {p}: {d}")
print(f"  >>> {len(real)} ports")

print("\n=== Expected-down: coupler/OBS on solo train ===")
for sw, p, d in expected_solo:
    print(f"  {sw} {p}: {d}")

print("\n=== Service FIS/CCTV (e0-5) down: enabled, may simply have no attached device ===")
for sw, p, d in service:
    print(f"  {sw} {p}: {d}")

print("\n=== SNMP admin-up but template DISABLED (would be config drift) ===")
for sw, p, d in drift:
    print(f"  {sw} {p}: '{d}'")
if not drift:
    print("  (none)")
