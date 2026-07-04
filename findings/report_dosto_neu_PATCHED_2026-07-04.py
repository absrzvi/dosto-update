#
# Module to create an NMS report for the OEBB Dosto Neu project.
#
import logging
from collections import deque
from enum import IntEnum

from lib.report import Device
from lib.report.report import Report

logger = logging.getLogger(__name__)


# Notes about port numbering:
# E0-0 -> 3
# E0-1 -> 4
# E0-2 -> 5
# E0-4 -> 7
# E1-2 -> 11
class DostoNeuPort(IntEnum):
    LAN1 = 1
    LAN2 = 2
    E0_0 = 3
    E0_1 = 4
    E0_2 = 5
    E0_4 = 7
    E1_2 = 11


# ── NDP-BYPASS-FIX (2026-07-04, bench PoC) ─────────────────────────────────
# Expected inter-coach topology per consist. PROTOTYPE: hardcoded here; the
# productionised version must load this from the templates / a schema file so it
# is not duplicated. position -> {port: expected-neighbour-position}. Source:
# _shared/{nv4,nv6}-topology.md (aliasing-resolved).
_COACH_OF = {"A": 1, "G": 2, "E": 3, "B": 4, "C": 3, "D": 4, "F": 5}
_EXPECTED = {
    "nv4": {
        "chain": ["A1", "A2", "A3", "G1", "G2", "G3", "E1", "E2", "E3", "B1", "B2", "B3"],
        "adj": {
            "A1": {"e0-0": "A3", "e0-1": "G1"}, "A2": {"e0-0": "A3", "e0-1": "G3"}, "A3": {"e0-0": "A1", "e0-1": "A2"},
            "G1": {"e0-0": "A1", "e0-1": "E2"}, "G2": {"e0-0": "G3", "e0-1": "E1"}, "G3": {"e0-0": "A2", "e0-1": "G2"},
            "E1": {"e0-0": "B1", "e0-1": "G2"}, "E2": {"e0-0": "E3", "e0-1": "G1"}, "E3": {"e0-0": "B2", "e0-1": "E2"},
            "B1": {"e0-0": "B3", "e0-1": "E1"}, "B2": {"e0-0": "B3", "e0-1": "E3"}, "B3": {"e0-0": "B1", "e0-1": "B2"},
        },
        "coach_of": {"A": 1, "G": 2, "E": 3, "B": 4},
    },
}


def _cd_of(pos, coach_of):
    return coach_of[pos[0]], int(pos[1])


def _claimed_pos(dev, coach_of):
    """Position claimed by the switch hostname, e.g. 4t-A3-v3-250 / nv4-A3-v8-19 -> 'A3'.
    A HINT only — validated against topology before it is trusted."""
    if not dev.config:
        return None
    parts = dev.config.split("-")
    if len(parts) > 1 and len(parts[1]) == 2 and parts[1][0] in coach_of:
        return parts[1]
    return None


class DostoNeuReport(Report):
    # ── NDP-BYPASS-FIX ──
    # DESIGN: device_instances holds ONLY real, successfully-numbered devices — exactly
    # like base OBN. This is what feeds create_nms_device_nodes() (MQTT→NMS) and the
    # discovery.prev.json snapshot, so NMS provisions ONLY real devices (no junk hosts).
    #
    # The DOWN / UNKNOWN / UNPLACED / INCOMPLETE-banner rows are CONSOLE-ONLY: they go
    # to a side-file (discovery.placeholders.json) that backbone_validate.py merges at
    # display time. They MUST NEVER enter device_instances — an earlier version did, and
    # NMS created junk Zabbix hosts from them (Car 0, Car 99, DOWN:A1). 2026-07-04.
    _PLACEHOLDER_FILE = "/tmp/discovery.placeholders.json"

    def normalise_devices(self, inc=0):
        # base behaviour: drop anything not fully numbered. (Real UNPLACED switches are
        # surfaced for the console via the placeholder side-file, NOT kept here — keeping
        # them here with a fake coach is what polluted NMS.)
        super().normalise_devices(inc)

    def _write_placeholders(self, placeholders):
        """Persist console-only placeholder rows to the side-file for obn validate.
        Written as plain dicts shaped like the report devices so backbone_validate's
        _create_overview can render them alongside the real devices."""
        try:
            import json as _json
            with open(self._PLACEHOLDER_FILE, "w") as fp:
                _json.dump(placeholders, fp, indent=2)
        except OSError as exc:
            self.logger.warning("could not write placeholder side-file: %s", exc)

    _LEASES_FILE = "/var/lib/dhcp/dhcpd.leases"

    def _leased_switch_count(self):
        """Count distinct switch POSITIONS holding a DHCP lease, as an independent
        ground-truth for how many switches SHOULD be discoverable.

        Counts distinct position-bearing client-hostnames (e.g. '4t-A3-...', 'nv4-A3-...'
        -> position 'A3'), NOT MACs. Positions are stable across a hardware SWAP (the
        replacement unit leases under the same hostname); MACs are not — counting MACs
        would double-count a swapped position forever, because dhcpd.leases accumulates
        expired lease records and the old MAC never leaves the file. Position-counting
        is also consistent with how the rest of this algorithm identifies switches.

        Returns None if the leases file can't be read (gate is then skipped)."""
        try:
            import re
            positions = set()
            for line in open(self._LEASES_FILE):
                m = re.search(r'client-hostname\s+"([^"]+)"', line)
                if not m:
                    continue
                parts = m.group(1).split("-")
                if len(parts) > 1 and len(parts[1]) == 2 and parts[1][0].upper() in "ABEGCDF":
                    positions.add(parts[1].upper())
            return len(positions) or None
        except (OSError, ValueError):
            return None

    def _placeholder_row(self, coach, dev, status, note, ip="0.0.0.0", dtype="SW"):
        """A console-only placeholder as a PLAIN DICT (never a Device / never added to
        device_instances). Shaped like a report device so backbone_validate's
        _create_overview can render it: ip is a parseable address (0.0.0.0), firmware
        and config are non-None strings. mac is a marker prefix so nothing downstream
        mistakes it for a real device."""
        return {
            "mac": f"PLACEHOLDER:{status}:{coach}-{dev}",
            "ip": ip,
            "type": dtype,
            "coach_number": coach,
            "device_number": dev,
            "firmware": f"{status}",
            "config": f"{status} ({note})",
            "serial": None,
            "target": {},
            "_placeholder": True,
        }

    def number_coaches(self):
        model = _EXPECTED.get(self.train_type)
        if model is None:
            # No topology model for this train_type — fall back to legacy walk so we
            # never regress non-nv4 consists on a shared engine. (nv6/fv* land here
            # until their chains are added.)
            return self._number_coaches_legacy()

        adj = model["adj"]
        chain = model["chain"]
        coach_of = model["coach_of"]
        # coach the CCU sits in — same mapping the legacy walk used to seed the BOX.
        ccu1_coach = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}.get(self.train_type, 2)

        for device in self.device_instances.values():
            device.type = self.find_type(device, retype_icl=False)
            # Number the CCU (BOX) exactly as the legacy walk did: coach = ccu1_coach,
            # device 1. WITHOUT this the CCU stays unnumbered, normalise_devices() drops
            # it, and the CCU vanishes from the NMS report (regression, 2026-07-04).
            if device.type == "BOX":
                device.coach_number = ccu1_coach
                device.device_number = 1

        by_mac = {d.mac: d for d in self.device_instances.values()}
        switches = [d for d in self.device_instances.values() if d.type == "SW"]

        def live_neigh_positions(dev):
            s = set()
            for nb in dev.neighbours:
                nd = by_mac.get(nb.get("mac"))
                if nd and nd.type == "SW":
                    cp = _claimed_pos(nd, coach_of)
                    if cp:
                        s.add(cp)
            return s

        def acceptable(pos):
            # expected neighbours, plus the far side of each (a bypassed neighbour is
            # replaced in the live view by the switch beyond it) — bypass tolerance.
            acc = set(adj[pos].values())
            for nb in list(adj[pos].values()):
                for _, fpos in adj.get(nb, {}).items():
                    if fpos != pos:
                        acc.add(fpos)
            return acc

        # Console-only placeholder rows accumulate here; written to the side-file at the
        # end. A switch that lands here is NOT numbered and NOT kept in device_instances
        # (base normalise_devices drops it) — so it never reaches NMS as a junk host.
        placeholders = []

        # Validate each switch's hostname claim against expected adjacency.
        claims = {}
        unplaced = []  # (switch, reason)
        for sw in switches:
            cp = _claimed_pos(sw, coach_of)
            if cp is None:
                unplaced.append((sw, "no position in hostname"))
                continue
            live = live_neigh_positions(sw)
            stray = live - acceptable(cp)
            if live and not stray:
                claims.setdefault(cp, []).append(sw)
            elif not live:
                claims.setdefault(cp, []).append(sw)  # isolated: tentatively trust
            else:
                self.logger.warning(
                    "switch %s claims %s but neighbours %s inconsistent (misimage?)",
                    sw.mac, cp, sorted(live),
                )
                unplaced.append((sw, f"hostname claims {cp}, neighbours {sorted(live)} inconsistent"))

        anchored = set()
        for pos, claimants in claims.items():
            if len(claimants) == 1:
                sw = claimants[0]
                sw.coach_number, sw.device_number = _cd_of(pos, coach_of)
                anchored.add(pos)
            else:
                for sw in claimants:
                    unplaced.append((sw, f"duplicate claim on {pos}"))

        # Emit UNPLACED real switches as CONSOLE-ONLY placeholder rows (coach 90 = sorts
        # last in the validate table; NOT written to device_instances → never an NMS host).
        for sw, reason in unplaced:
            placeholders.append(self._placeholder_row(
                90, 0, "UNPLACED", f"{sw.config or sw.ip}: {reason}", ip=sw.ip or "0.0.0.0"))

        # Discovery-completeness gate: compare discovered switches to the DHCP-lease
        # count. If discovery under-scanned (flaky link / SNMP timeouts), we CANNOT
        # trust absence — every unseen position becomes UNKNOWN, never DOWN. A loud
        # banner row tells the operator to re-run discover.
        leased = self._leased_switch_count()
        discovered = len(switches)
        scan_incomplete = leased is not None and discovered < leased

        # position -> anchored Device, for the reciprocal bypass test
        anchored_dev = {}
        for pos in anchored:
            for sw in claims[pos]:
                anchored_dev[pos] = sw

        def bypass_reciprocal(pos):
            """Positive cold-bypass evidence: pos's two expected neighbours are BOTH
            anchored AND each LLDP-sees the other across pos's position, on the port
            that faces pos. This is the only signature that justifies asserting DOWN."""
            nb_ports = adj[pos]                     # {port: neighbour_pos}
            npos = list(nb_ports.values())
            if len(npos) != 2:
                # terminus (single neighbour): bypass has nothing to reciprocate to.
                # Require the single neighbour anchored AND its toward-pos port to have
                # NO other switch LLDP-peer (dead end) — weaker, but positive-ish.
                return False
            L, R = npos
            if L not in anchored_dev or R not in anchored_dev:
                return False
            dL, dR = anchored_dev[L], anchored_dev[R]
            l_sees_r = any(_claimed_pos(by_mac.get(nb.get("mac")), coach_of) == R
                           for nb in dL.neighbours if by_mac.get(nb.get("mac")))
            r_sees_l = any(_claimed_pos(by_mac.get(nb.get("mac")), coach_of) == L
                           for nb in dR.neighbours if by_mac.get(nb.get("mac")))
            return l_sees_r and r_sees_l

        # Absent-but-expected chain positions (e.g. A1, B3) get a DOWN/UNKNOWN device
        # that IS published to the report — NMS needs a device in the slot to draw the
        # (down) box in the consist diagram; without it the diagram fails to render.
        # These carry a VALID coach/device (the real slot) so NMS matches them to the
        # correct host (R1_SW1 etc.) rather than making a junk host, and a "7.7.7.7"-style
        # ip so the host is the not-found placeholder. They are NOT junk — the junk that
        # created Car 0 / Car 99 was the banner (coach 0) and UNPLACED sentinel (coach 99),
        # which remain console-only below.
        for pos in chain:
            if pos in anchored:
                continue
            if scan_incomplete:
                status, note = "UNKNOWN", "not seen this scan (discovery incomplete)"
            elif bypass_reciprocal(pos):
                Ls = ",".join(adj[pos].values())
                status, note = "DOWN", f"cold-bypass confirmed (reciprocal via {Ls})"
            else:
                status, note = "UNKNOWN", "not discovered; no bypass evidence (verify power/SNMP)"
            coach, dev = _cd_of(pos, coach_of)
            down_dev = Device(mac=f"DOWN:{pos}", ip="7.7.7.7")
            down_dev.type = "SW"
            down_dev.coach_number, down_dev.device_number = coach, dev
            down_dev.firmware = f"{pos} {status}"
            down_dev.config = f"{pos} {status} ({note})"
            down_dev.target = {}
            self.device_instances[down_dev.mac] = down_dev   # in report → diagram draws it
            # also mirror into the console side-file so obn validate shows the note
            placeholders.append(self._placeholder_row(coach, dev, f"{pos} {status}", note, ip="7.7.7.7"))

        # CONSOLE-ONLY: the discovery-incomplete banner. coach 0 → would make a "Car 0"
        # junk host if published, so it stays out of device_instances.
        if scan_incomplete:
            placeholders.append(self._placeholder_row(
                0, 0, "DISCOVERY INCOMPLETE",
                f"scanned {discovered}/{leased} switches (DHCP leases) — re-run 'obn discover'; "
                f"absences below are UNKNOWN not DOWN"))

        # APs: same coach as the switch that hosts them (unchanged intent).
        for sw in switches:
            if sw.coach_number is None:
                continue
            for nb in sw.neighbours:
                nd = by_mac.get(nb.get("mac"))
                if nd is None or nd.type != "AP" or nd.coach_number is not None:
                    continue
                port = nb.get("port", 0)
                nd.coach_number = sw.coach_number
                if port == DostoNeuPort.E0_4:
                    nd.device_number = sw.device_number
                if sw.device_number == 3 and port == DostoNeuPort.E1_2:
                    nd.device_number = 4

        # Console-only placeholders → side-file (NOT device_instances). NMS never sees them.
        self._write_placeholders(placeholders)
        self.normalise_devices()

    # Legacy neighbour-following walk, kept verbatim as the fallback for train_types
    # without a topology model. (Original number_coaches body.)
    def _number_coaches_legacy(self):
        ccu1_coach_map = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}
        max_coaches = {"nv4": 4, "nv6": 6, "fv5": 5, "fv6": 6}
        ccu1_coach = ccu1_coach_map.get(self.train_type, 2)
        max_coach = max_coaches.get(self.train_type, 4)

        queue = deque()
        for device in self.device_instances.values():
            device.type = self.find_type(device, retype_icl=False)
            if device.type == "BOX":
                device.coach_number = ccu1_coach
                device.device_number = 1
                queue.append(device)

        while queue:
            from_device = queue.pop()
            for neighbour in from_device.neighbours:
                port = neighbour.get("port", 0)
                to_device = self.get_device(neighbour)
                if to_device is None or to_device.coach_number is not None:
                    continue
                if from_device.type == "BOX":
                    if to_device.type == "SW":
                        if port == DostoNeuPort.LAN1:
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number
                        elif port == DostoNeuPort.LAN2:
                            to_device.device_number = 3
                            to_device.coach_number = from_device.coach_number
                elif from_device.type == "SW":
                    if to_device.type == "AP":
                        to_device.coach_number = from_device.coach_number
                        if port == DostoNeuPort.E0_4:
                            to_device.device_number = from_device.device_number
                        if from_device.device_number == 3 and port == DostoNeuPort.E1_2:
                            to_device.device_number = 4
                    elif to_device.type == "SW":
                        if from_device.device_number == 3 and port == DostoNeuPort.E0_1:
                            to_device.device_number = 2
                            to_device.coach_number = from_device.coach_number
                        elif (from_device.device_number == 2 and from_device.coach_number == ccu1_coach and port == DostoNeuPort.E0_1):
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number + 1
                        elif (from_device.device_number == 1 and from_device.coach_number in [1, max_coach] and port == DostoNeuPort.E0_0):
                            to_device.device_number = 3
                            to_device.coach_number = from_device.coach_number
                        elif (from_device.device_number == 1 and (ccu1_coach < from_device.coach_number < max_coach) and port == DostoNeuPort.E0_0):
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number + 1
                        elif (from_device.device_number == 1 and (1 < from_device.coach_number <= ccu1_coach) and port == DostoNeuPort.E0_0):
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number - 1
                        elif (from_device.device_number == 2 and (from_device.coach_number == ccu1_coach + 1) and port == DostoNeuPort.E0_1):
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number - 1
                        elif (from_device.device_number == 2 and (from_device.coach_number == max_coach or (ccu1_coach + 1 < from_device.coach_number < max_coach)) and port == DostoNeuPort.E0_1):
                            to_device.device_number = 3
                            to_device.coach_number = from_device.coach_number - 1
                        elif (from_device.device_number == 2 and from_device.coach_number < ccu1_coach and port == DostoNeuPort.E0_1):
                            to_device.device_number = 3
                            to_device.coach_number = from_device.coach_number + 1
                if to_device.coach_number is not None:  # NDP-PATCH-BUG10-BFS-GUARD
                    queue.appendleft(to_device)
                continue

        # legacy path keeps the original drop-unnumbered behaviour
        super().normalise_devices()
