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
    # ── NDP-BYPASS-FIX: retain discovered-but-unnumberable devices (§5c) ──
    # Override the base normalise_devices (shared with ace/ccjpa reports) so this
    # behaviour is scoped to DostoNeu only. A device OBN discovered and could poll
    # is NEVER silently dropped: if it could not be placed it is kept as UNPLACED.
    # Sentinel coach/device for UNPLACED devices: keeps them sortable/renderable in
    # backbone_validate._create_overview (which sorts on coach/device and would
    # TypeError on None) and sorts them to the end of the table.
    _UNPLACED_COACH = 99
    _UNPLACED_DEVICE = 0

    def normalise_devices(self, inc=0):
        kept = {}
        for k, v in self.device_instances.items():
            if v.type is None:
                continue
            if "UNPLACED" in (getattr(v, "config", "") or ""):
                # discovered but unnumbered — retained (§5c) with sortable sentinels
                if v.coach_number is None:
                    v.coach_number = self._UNPLACED_COACH
                if v.device_number is None:
                    v.device_number = self._UNPLACED_DEVICE
                if getattr(v, "firmware", None) is None:
                    v.firmware = "-"
                kept[k] = v
            elif v.coach_number is not None and v.device_number is not None:
                kept[k] = v  # numbered (incl. DOWN placeholders)
        self.device_instances = kept
        if inc != 0:
            for device in self.device_instances.values():
                if device.coach_number is not None and device.coach_number < 90:
                    device.coach_number += inc

    def _make_placeholder(self, pos, status, note, coach_of):
        """Synthetic Device row for an absent/unplaced position so it appears in the
        report instead of vanishing. Fields are stubbed so backbone_validate's
        _create_overview renders it without edits (it reads ip/firmware/config and
        sorts on coach/device — all non-None here)."""
        coach, dev = _cd_of(pos, coach_of)
        # ip must be a parseable address: backbone_validate._validate("ip") calls
        # ipaddress.ip_address(device["ip"]) and would ValueError on a placeholder
        # string. 0.0.0.0 parses, is not in the management range (renders NOK), and
        # flags the row as not-a-real-device. firmware/config are non-None strings so
        # _validate("firmware"/"config") and the incomplete-device test are satisfied.
        ph = Device(mac=f"DOWN:{pos}", ip="0.0.0.0")
        ph.type = "SW"
        ph.coach_number = coach
        ph.device_number = dev
        ph.firmware = f"{pos} {status}"
        ph.config = f"{pos} {status} ({note})"
        ph.target = {}
        return ph

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

        for device in self.device_instances.values():
            device.type = self.find_type(device, retype_icl=False)

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

        # Validate each switch's hostname claim against expected adjacency.
        claims = {}
        for sw in switches:
            cp = _claimed_pos(sw, coach_of)
            if cp is None:
                sw.config = f"{(sw.config or sw.ip)} UNPLACED (no position in hostname)"
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
                sw.config = f"{(sw.config or sw.ip)} UNPLACED (hostname claims {cp}, neighbours {sorted(live)} inconsistent)"

        anchored = set()
        for pos, claimants in claims.items():
            if len(claimants) == 1:
                sw = claimants[0]
                sw.coach_number, sw.device_number = _cd_of(pos, coach_of)
                anchored.add(pos)
            else:
                for sw in claimants:
                    sw.config = f"{(sw.config or sw.ip)} UNPLACED (duplicate claim on {pos})"

        # Emit DOWN/ABSENT for expected positions with no validated claimant.
        for pos in chain:
            if pos in anchored:
                continue
            neigh_anchored = [n for n in adj[pos].values() if n in anchored]
            status = "DOWN" if neigh_anchored else "ABSENT"
            note = ("localised via " + ",".join(neigh_anchored)) if neigh_anchored else "no anchored neighbour"
            ph = self._make_placeholder(pos, status, note, coach_of)
            self.device_instances[ph.mac] = ph

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
