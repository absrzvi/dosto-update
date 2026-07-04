#!/usr/bin/env python3
"""
Patch /usr/share/obn/lib/report/report_dosto_neu.py on the live CCU:
insert a FALLBACK pass at the end of number_coaches() (before self.normalise_devices())
that recovers redundant-path-reachable switches the hardcoded walk could not number,
taking identity from each device's own configuration_version (e.g. 'nv6-E2-v8-147').

Idempotent: keyed on marker NDP-PATCH-OBNFALLBACK. Re-running is a no-op.
Run ON THE CCU (it edits the local file). Caller handles btrfs ro-toggle.
"""
import re, sys, io

PATH = "/usr/share/obn/lib/report/report_dosto_neu.py"
MARKER = "NDP-PATCH-OBNFALLBACK"

src = open(PATH).read()
if MARKER in src:
    print("already patched (marker present) — no-op")
    sys.exit(0)

# The fallback block. Indentation = 8 spaces (method body level, same as `while queue:`).
# It runs after the primary BFS while-loop and before self.normalise_devices().
FALLBACK = '''
        # ===================== NDP-PATCH-OBNFALLBACK =====================
        # Robustness fallback: the hardcoded walk above numbers switches on
        # their EXPECTED wiring. If a single inter-switch LLDP edge is missing
        # (e.g. a broken intra-coach cable), the walk can leave a reachable
        # switch unnumbered, dropping it from the inventory entirely. The
        # underlying link-down is already caught by the SNMP port alarm; OBN's
        # job here is "if it is reachable, show it".
        #
        # For each still-unnumbered SWITCH that is reachable via ANY LLDP
        # switch-to-switch path from the already-numbered set, recover its
        # (coach, device) from its OWN rendered config string and place it,
        # logging a warning that it is off its expected wiring.
        try:
            import re as _re
            _L2C = {"A": 1, "C": 2, "D": 3, "E": 4, "F": 5, "B": 6}

            def _ident(cfgver):
                m = _re.match(r"nv6-([A-F])(\\d)-", cfgver or "")
                if m:
                    return _L2C[m.group(1)], int(m.group(2))
                m = _re.match(r"nv4-([A-G])(\\d)-", cfgver or "")
                if m:
                    return _L2C.get(m.group(1)), int(m.group(2))
                return None

            _devs = list(self.device_instances.values())
            _sw = [d for d in _devs if d.type == "SW"]

            # undirected SW-SW LLDP adjacency
            _adj = {}
            for d in _sw:
                _adj.setdefault(d.mac, set())
                for nb in d.neighbours:
                    t = self.get_device(nb)
                    if t is not None and t.type == "SW":
                        _adj.setdefault(d.mac, set()).add(t.mac)
                        _adj.setdefault(t.mac, set()).add(d.mac)

            # reachable set seeded by all currently-numbered switches
            _reach = set(d.mac for d in _sw if d.coach_number is not None)
            _frontier = list(_reach)
            while _frontier:
                _x = _frontier.pop()
                for _y in _adj.get(_x, ()):
                    if _y not in _reach:
                        _reach.add(_y)
                        _frontier.append(_y)

            for d in _sw:
                if d.coach_number is not None:
                    continue
                if d.mac not in _reach:
                    continue  # genuinely unreachable -> leave unplaced (reported as today)
                ident = _ident(getattr(d, "configuration_version", None))
                if not ident or ident[0] is None:
                    continue
                d.coach_number, d.device_number = ident
                self.logger.warning(
                    "fallback-numbered %s (%s) at coach %s device %s via redundant "
                    "LLDP path - OFF EXPECTED WIRING (check inter-switch cabling)",
                    d.mac, getattr(d, "configuration_version", "?"),
                    d.coach_number, d.device_number,
                )
        except Exception as _e:  # never let the fallback break report generation
            self.logger.warning("OBNFALLBACK pass error (ignored): %s", _e)
        # =================== END NDP-PATCH-OBNFALLBACK ===================
'''

# Insert immediately before the `self.normalise_devices()` call that follows the BFS loop.
needle = "        # Remove any devices that were not detected properly (switch on wrong ports etc.)\n        self.normalise_devices()"
if needle not in src:
    print("ERROR: anchor not found; aborting (file structure unexpected)")
    sys.exit(2)

patched = src.replace(needle, FALLBACK + "\n" + needle, 1)
open(PATH, "w").write(patched)
print("patched OK — marker inserted before normalise_devices()")
'''
'''
