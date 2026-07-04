#
# Module to create an NMS report for the OEBB Dosto Neu project.
#
# MERGED coach-numbering (2026-07-04): feature B (topology-anchored numbering +
# never-drop-discovered + DOWN/UNPLACED + completeness gate) with feature A's
# redundant-path recovery folded in (a switch reachable only via an alternate
# LLDP path but hostname-identifiable is PLACED + flagged off-expected-wiring,
# NOT dropped). CCUContext/CCU2 (feature C) deliberately NOT integrated — the
# ccu1_coach hardcode is verified correct for all train_types (nv4=2, nv6=3,
# fv5=2, fv6=3) and the CCUContext swap has a per-hostname-key trap; that is a
# separate engine MR gated on DOSTO getting a second CCU.
#
# Verified-hardening baked in (from the 2026-07-04 adversarial review):
#   - _claimed_pos is null- AND format-guarded (no int()/AttributeError crash on
#     a malformed/None hostname).
#   - MAC lookups are case-normalised on both sides.
#   - coupled-consist (more switches than chain slots) → loud banner, not a
#     silent half-UNPLACE.
#   - the dead _COACH_OF module dict is removed.
#
import logging
import re
from collections import deque

from lib.report import Device
from lib.report.report import Report

logger = logging.getLogger(__name__)


# Notes about port numbering:
# E0-0 -> 3
# E0-1 -> 4
# E0-2 -> 5
# E0-4 -> 7
# E1-2 -> 11
from enum import IntEnum


class DostoNeuPort(IntEnum):
    LAN1 = 1
    LAN2 = 2
    E0_0 = 3
    E0_1 = 4
    E0_2 = 5
    E0_4 = 7
    E1_2 = 11


# ── Expected inter-coach topology per consist. PROTOTYPE: nv4 hardcoded here;
#    productionise by loading per train_type from the templates / a schema file so
#    it is not duplicated. position -> {port: expected-neighbour-position}. Source:
#    _shared/{nv4,nv6}-topology.md (aliasing-resolved). Train_types without a model
#    fall through to the legacy walk (no regression). ─────────────────────────────
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
    # nv6 / fv5 / fv6 chains to be added (confirm fv5/fv6 first) — until then they
    # take the legacy walk via _number_coaches_legacy.
}


def _claimed_pos(dev, coach_of):
    """Position claimed by the switch hostname, e.g. 4t-A3-v3-250 / nv4-A3-v8-19 -> 'A3'.
    A HINT only — validated against topology before it is trusted.

    Null- and format-guarded (2026-07-04 review): returns None for a missing device,
    a device with no config, or a config whose 2nd segment is not <coach-letter><1-9>.
    This kills the _claimed_pos(None) AttributeError and the int(pos[1]) ValueError on
    a malformed/misimaged hostname — such a switch becomes UNPLACED, never a crash."""
    if dev is None or not dev.config:
        return None
    parts = dev.config.split("-")
    if len(parts) < 2:
        return None
    seg = parts[1]
    # exactly: one coach letter (present in this model) + one device digit 1-9
    if len(seg) == 2 and seg[0] in coach_of and seg[1].isdigit() and seg[1] != "0":
        return seg
    return None


def _cd_of(pos, coach_of):
    # pos is always a validated position (from _claimed_pos or the hardcoded chain),
    # so pos[0] in coach_of and pos[1] is a 1-9 digit — safe.
    return coach_of[pos[0]], int(pos[1])


def _mac(x):
    """Case-normalised MAC. Real discovery is lowercase today, but a mixed-case scan
    would silently orphan every neighbour lookup without this."""
    return x.lower() if x else x


class DostoNeuReport(Report):
    # ── DESIGN: device_instances holds ONLY real, numbered devices PLUS DOWN/UNKNOWN
    # rows for real chain slots (valid coach/device + not-found ip) so NMS draws the
    # down box in the consist diagram and matches the right R#_SW# host. The coach-0
    # INCOMPLETE banner and coach-90 UNPLACED rows are CONSOLE-ONLY (side-file) — they
    # have no valid slot, so publishing them makes junk Zabbix hosts (Car 0/Car 99).
    _PLACEHOLDER_FILE = "/tmp/discovery.placeholders.json"
    _LEASES_FILE = "/var/lib/dhcp/dhcpd.leases"
    _NOT_FOUND_IP = "7.7.7.7"

    def normalise_devices(self, inc=0):
        # base behaviour: drop anything not fully numbered. DOWN rows carry a real
        # coach/device so they survive; UNPLACED reals are surfaced via the side-file.
        super().normalise_devices(inc)

    def _write_placeholders(self, placeholders):
        try:
            import json as _json
            with open(self._PLACEHOLDER_FILE, "w") as fp:
                _json.dump(placeholders, fp, indent=2)
        except OSError as exc:
            self.logger.warning("could not write placeholder side-file: %s", exc)

    def _leased_switch_count(self):
        """Distinct switch POSITIONS holding a DHCP lease — an independent ground truth
        for how many switches SHOULD be discoverable. Position-keyed (not MAC) so a
        hardware swap (same hostname, new MAC) doesn't double-count. Returns None if the
        leases file can't be read (gate then skipped)."""
        try:
            positions = set()
            for line in open(self._LEASES_FILE):
                m = re.search(r'client-hostname\s+"([^"]+)"', line)
                if not m:
                    continue
                parts = m.group(1).split("-")
                if len(parts) > 1 and len(parts[1]) == 2 and parts[1][0].upper() in "ABEGCDF" and parts[1][1:].isdigit():
                    positions.add(parts[1].upper())
            return len(positions) or None
        except (OSError, ValueError):
            return None

    def _placeholder_row(self, coach, dev, status, note, ip="0.0.0.0", dtype="SW"):
        """Console-only placeholder as a PLAIN DICT (never a Device, never in
        device_instances). Shaped like a report device so backbone_validate's
        _create_overview can render it alongside the real devices."""
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
            "status": status,
            "_placeholder": True,
        }

    def number_coaches(self):
        model = _EXPECTED.get(self.train_type)
        if model is None:
            # No topology model for this train_type — legacy walk (nv6/fv* until their
            # chains are added). No regression on those consists.
            return self._number_coaches_legacy()

        adj = model["adj"]
        chain = model["chain"]
        coach_of = model["coach_of"]
        # Coach the CCU sits in. Verified per train_type (nv4=2, nv6=3, fv5=2, fv6=3).
        # NOT sourced from CCUContext/box1_coach_number — that swap is deferred (see
        # module header). Kept as the authoritative anchor for now.
        ccu1_coach = {"nv4": 2, "nv6": 3, "fv5": 2, "fv6": 3}.get(self.train_type, 2)

        for device in self.device_instances.values():
            device.type = self.find_type(device, retype_icl=False)
            if device.type == "BOX":
                device.coach_number = ccu1_coach
                device.device_number = 1

        by_mac = {_mac(d.mac): d for d in self.device_instances.values()}
        switches = [d for d in self.device_instances.values() if d.type == "SW"]

        def sw_neighbours(dev):
            """The discovered SW neighbours of dev (Device objects), MAC-normalised."""
            out = []
            for nb in dev.neighbours:
                nd = by_mac.get(_mac(nb.get("mac")))
                if nd is not None and nd.type == "SW":
                    out.append(nd)
            return out

        def live_neigh_positions(dev):
            s = set()
            for nd in sw_neighbours(dev):
                cp = _claimed_pos(nd, coach_of)
                if cp:
                    s.add(cp)
            return s

        def acceptable(pos):
            # expected neighbours + the far side of each (a bypassed neighbour is
            # replaced in the live view by the switch beyond it) — bypass tolerance.
            acc = set(adj[pos].values())
            for nb in list(adj[pos].values()):
                for _, fpos in adj.get(nb, {}).items():
                    if fpos != pos:
                        acc.add(fpos)
            return acc

        placeholders = []

        # ── Coupled-consist guard: if we discovered more switches than the single
        # chain has slots, this is (most likely) a coupled consist the single-chain
        # numbering can't handle. Emit a loud banner and DO NOT silently UNPLACE half
        # the train. (We still number what we can below; the banner tells the operator
        # the numbering is single-consist only.) ─────────────────────────────────────
        coupled = len(switches) > len(chain)
        if coupled:
            placeholders.append(self._placeholder_row(
                0, 0, "COUPLED CONSIST",
                f"discovered {len(switches)} switches > {len(chain)} chain slots for "
                f"{self.train_type} — single-consist numbering only; second consist not numbered"))

        # ── Validate each switch's hostname claim against expected adjacency ──────────
        claims = {}
        unplaced = []  # (switch, reason)
        for sw in switches:
            cp = _claimed_pos(sw, coach_of)
            if cp is None:
                unplaced.append((sw, "no/invalid position in hostname"))
                continue
            live = live_neigh_positions(sw)
            stray = live - acceptable(cp)
            if not live:
                claims.setdefault(cp, []).append(sw)   # isolated: tentatively trust
            elif not stray:
                claims.setdefault(cp, []).append(sw)
            else:
                self.logger.warning(
                    "switch %s claims %s but neighbours %s inconsistent (misimage/miswire?)",
                    sw.mac, cp, sorted(live))
                unplaced.append((sw, f"hostname claims {cp}, neighbours {sorted(live)} inconsistent"))

        anchored = set()
        anchored_dev = {}
        for pos, claimants in claims.items():
            if len(claimants) == 1:
                sw = claimants[0]
                sw.coach_number, sw.device_number = _cd_of(pos, coach_of)
                sw.status = "UP"
                anchored.add(pos)
                anchored_dev[pos] = sw
            else:
                # duplicate claim on one position = at least one misimage; can't trust
                # either, both UNPLACED (operator investigates).
                for sw in claimants:
                    unplaced.append((sw, f"duplicate claim on {pos} ({len(claimants)} switches) — misimage?"))

        # ── FEATURE A: off-expected-wiring recovery ──────────────────────────────────
        # An anchored switch whose EXPECTED inter-coach edge is down but which is still
        # reachable via a redundant SW-SW LLDP path is a single-cable-fault (switch fine).
        # It is already placed above (anchored by validated hostname); here we just FLAG
        # it off-expected-wiring so the fault is surfaced, not hidden, and so it is never
        # mistaken for healthy. Build the undirected SW-SW graph and BFS from the CCU-
        # reachable set; an anchored switch NOT on its expected edge but IN the reachable
        # set is off-expected-wiring.
        graph = {}
        for sw in switches:
            graph.setdefault(_mac(sw.mac), set())
            for nd in sw_neighbours(sw):
                graph[_mac(sw.mac)].add(_mac(nd.mac))
                graph.setdefault(_mac(nd.mac), set()).add(_mac(sw.mac))
        # seed reachability from the BOX's directly-cabled switches (its SW neighbours)
        seed = set()
        for d in self.device_instances.values():
            if d.type == "BOX":
                for nd in sw_neighbours(d):
                    seed.add(_mac(nd.mac))
        reach = set(seed)
        frontier = deque(seed)
        while frontier:
            x = frontier.popleft()
            for y in graph.get(x, ()):
                if y not in reach:
                    reach.add(y)
                    frontier.append(y)

        def on_expected_edge(sw, pos):
            """True if sw is LLDP-adjacent to at least one of pos's EXPECTED neighbours."""
            live = live_neigh_positions(sw)
            return bool(live & set(adj[pos].values()))

        for pos, sw in anchored_dev.items():
            if _mac(sw.mac) in reach and not on_expected_edge(sw, pos):
                sw.status = "OFF_EXPECTED_WIRING"
                placeholders.append(self._placeholder_row(
                    sw.coach_number, sw.device_number, "OFF-EXPECTED-WIRING",
                    f"{pos}: reachable via redundant path, not on expected edge "
                    f"(broken inter-coach cable?) — verify wiring",
                    ip=sw.ip or "0.0.0.0"))

        # ── Emit UNPLACED real switches as CONSOLE-ONLY rows (coach 90 = sorts last;
        #    never in device_instances → never an NMS junk host) ───────────────────────
        for sw, reason in unplaced:
            placeholders.append(self._placeholder_row(
                90, 0, "UNPLACED", f"{sw.config or sw.ip}: {reason}", ip=sw.ip or "0.0.0.0"))

        # ── Discovery-completeness gate: discovered vs DHCP-lease positions. If the scan
        #    under-scanned, absence is UNKNOWN not DOWN (no false DOWN on a flaky link). ─
        leased = self._leased_switch_count()
        discovered = len(switches)
        scan_incomplete = leased is not None and discovered < leased and not coupled

        def bypass_reciprocal(pos):
            """Positive cold-bypass evidence: pos's two expected neighbours are BOTH
            anchored AND each LLDP-sees the other across pos's slot. Only signature that
            justifies DOWN. Terminus (single neighbour) → False → UNKNOWN, never DOWN."""
            npos = list(adj[pos].values())
            if len(npos) != 2:
                return False
            L, R = npos
            if L not in anchored_dev or R not in anchored_dev:
                return False
            dL, dR = anchored_dev[L], anchored_dev[R]
            l_sees_r = any(_claimed_pos(nd, coach_of) == R for nd in sw_neighbours(dL))
            r_sees_l = any(_claimed_pos(nd, coach_of) == L for nd in sw_neighbours(dR))
            return l_sees_r and r_sees_l

        # ── Absent-but-expected chain positions → DOWN (bypass-proven) / UNKNOWN. These
        #    are PUBLISHED (valid slot + not-found ip) so NMS draws the down box. ────────
        for pos in chain:
            if pos in anchored:
                continue
            if scan_incomplete:
                status, note = "UNKNOWN", "not seen this scan (discovery incomplete)"
            elif bypass_reciprocal(pos):
                Ls = ",".join(adj[pos].values())
                status, note = "DOWN", f"cold-bypass confirmed (reciprocal via {Ls}) — verify power"
            else:
                status, note = "UNKNOWN", "not discovered; no bypass evidence (verify power/SNMP)"
            coach, dev = _cd_of(pos, coach_of)
            down_dev = Device(mac=f"DOWN:{pos}", ip=self._NOT_FOUND_IP)
            down_dev.type = "SW"
            down_dev.coach_number, down_dev.device_number = coach, dev
            down_dev.firmware = f"{pos} {status}"
            down_dev.config = f"{pos} {status} ({note})"
            down_dev.target = {}
            down_dev.status = status
            self.device_instances[down_dev.mac] = down_dev
            placeholders.append(self._placeholder_row(coach, dev, f"{pos} {status}", note, ip=self._NOT_FOUND_IP))

        if scan_incomplete:
            placeholders.append(self._placeholder_row(
                0, 0, "DISCOVERY INCOMPLETE",
                f"scanned {discovered}/{leased} switches (DHCP leases) — re-run 'obn discover'; "
                f"absences above are UNKNOWN not DOWN"))

        # ── APs: same coach as the switch that hosts them (unchanged intent) ──────────
        for sw in switches:
            if sw.coach_number is None:
                continue
            for nb in sw.neighbours:
                nd = by_mac.get(_mac(nb.get("mac")))
                if nd is None or nd.type != "AP" or nd.coach_number is not None:
                    continue
                port = nb.get("port", 0)
                nd.coach_number = sw.coach_number
                if port == DostoNeuPort.E0_4:
                    nd.device_number = sw.device_number
                if sw.device_number == 3 and port == DostoNeuPort.E1_2:
                    nd.device_number = 4

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

        super().normalise_devices()
