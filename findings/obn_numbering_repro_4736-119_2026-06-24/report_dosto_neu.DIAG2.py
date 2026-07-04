#
# Module to create an NMS report for the OEBB Dosto Neu project.
#
import re
import logging
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


class DostoNeuReport(Report):
    def number_coaches(self):
        # Create a FIFO queue of all devices for which we know the coach number, adding the device type on the go.
        # Working off that queue and going through the neighbours will get us a coach number of all other devices. The
        # first, and for now only item on that queue is the CCU.
        #
        # For nv4 (4 coaches), start from the CCU in coach 2
        # For nv6 (6 coaches), start from the CCU in coach 3
        queue = deque()
        for device in self.device_instances.values():
            device.type = self.find_type(device, retype_icl=False)
            if device.type == "BOX":
                if self.train_type == "nv4":
                    device.coach_number = 2
                elif self.train_type == "nv6":
                    device.coach_number = 3
                device.device_number = 1
                queue.append(device)

        while queue:
            from_device = queue.pop()
            for neighbour in from_device.neighbours:
                port = neighbour.get("port", 0)
                to_device = self.get_device(neighbour)

                # If we can't match the neighbour's MAC with a discovered device, skip it. If the target device already
                # has a coach number, skip it as well.
                if to_device is None or to_device.coach_number is not None:
                    continue

                # CCU neighbours switch 1 and 3 of the same coach
                if from_device.type == "BOX":
                    # CCU neighbour must be switch
                    if to_device.type == "SW":
                        if port == 1:
                            to_device.device_number = 1
                            to_device.coach_number = from_device.coach_number
                        elif port == 2:
                            to_device.device_number = 3
                            to_device.coach_number = from_device.coach_number

                # Switches neighbour switches and access points
                if from_device.type == "SW":
                    # Switches have 1 or 2 AP neighbours
                    if to_device.type == "AP":
                        # APs are in the same coach as their connecting switch
                        to_device.coach_number = from_device.coach_number
                        # Each switch has an AP neighbour on port E0-4
                        if port == 7:
                            to_device.device_number = from_device.device_number
                        # Switch 3 has a single AP neighbour on port E1-2
                        if from_device.device_number == 3:
                            if port == 11:
                                to_device.device_number = 4

                    # nv4 - BEGIN
                    if self.train_type == "nv4":
                        # Switches can neighbour switches
                        if to_device.type == "SW":
                            # All SW3 connect to SW2 of same coach on port E0-1
                            if from_device.device_number == 3:
                                if port == 4:
                                    to_device.coach_number = from_device.coach_number
                                    to_device.device_number = 2
                            # SW 2 of coach 2 connects to SW 1 of coach 3 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 2
                            ):
                                if port == 4:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                            # SW 1 of coach 3 connects to SW 1 of coach 4 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 3
                            ):
                                if port == 3:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                            # SW 1 of coach 4 connects to SW 3 of coach 4 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 4
                            ):
                                if port == 3:
                                    to_device.device_number = 3
                                    to_device.coach_number = from_device.coach_number
                            # SW 3 of coach 1 connects to SW 2 of coach 1 on port E0-1
                            # if (
                            #     from_device.device_number == 3
                            #     and from_device.coach_number == 1
                            # ):
                            #     if port == 4:
                            #         to_device.device_number = 2
                            #         to_device.coach_number = from_device.coach_number
                            # SW 2 of coach 4 connects to SW 3 of coach 3 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 4
                            ):
                                if port == 4:
                                    to_device.device_number = 3
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 3 of coach 2 connects to SW 2 of coach 2 on port E0-1
                            # if (
                            #     from_device.device_number == 3
                            #     and from_device.coach_number == 2
                            # ):
                            #     if port == 4:
                            #         to_device.device_number = 2
                            #         to_device.coach_number = from_device.coach_number
                            # SW 2 of coach 3 connects to SW 1 of coach 2 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 3
                            ):
                                if port == 4:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 1 of coach 2 connects to SW 1 of coach 1 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 2
                            ):
                                if port == 3:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 1 of coach 1 connects to SW 3 of coach 1 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 1
                            ):
                                if port == 3:
                                    to_device.device_number = 3
                                    to_device.coach_number = from_device.coach_number
                            # SW 3 of coach 1 connects to SW 2 of coach 1 on port E0-1
                            if (
                                from_device.device_number == 3
                                and from_device.coach_number == 1
                            ):
                                if port == 4:
                                    to_device.device_number = 2
                                    to_device.coach_number = from_device.coach_number
                            # SW 2 of coach 1 connects to SW 3 of coach 2 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 1
                            ):
                                if port == 4:
                                    to_device.device_number = 3
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                    # nv4 - END

                    # nv6 - BEGIN
                    elif self.train_type == "nv6":
                        # Switches can neighbour switches
                        if to_device.type == "SW":
                            # All SW3 connect to SW2 of same coach on port E0-1
                            if from_device.device_number == 3:
                                if port == 4:
                                    to_device.coach_number = from_device.coach_number
                                    to_device.device_number = 2
                            # SW 2 of coach 3 connects to SW 1 of coach 4 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 3
                            ):
                                if port == 4:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                            # SW 1 of coach 4 and 5 connect to SW 1 of coach 5 and 6 respectively on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number in [4, 5]
                            ):
                                if port == 3:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                            # SW 1 of coach 6 connects to SW 3 of coach 6 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 6
                            ):
                                if port == 3:
                                    to_device.device_number = 3
                                    to_device.coach_number = from_device.coach_number
                            # SW 2 of coach 6 and 5 connect to SW 3 of coach 5 and 4 respectively on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number in [5, 6]
                            ):
                                if port == 4:
                                    to_device.device_number = 3
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 2 of coach 4 connects to SW 1 of coach 3 on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number == 4
                            ):
                                if port == 4:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 1 of coach 3 and 2 connect to SW 1 of coach 2 and 1 respectively on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number in [2, 3]
                            ):
                                if port == 3:
                                    to_device.device_number = 1
                                    to_device.coach_number = (
                                        from_device.coach_number - 1
                                    )
                            # SW 1 of coach 1 connects to SW 3 of coach 1 on port E0-0
                            if (
                                from_device.device_number == 1
                                and from_device.coach_number == 1
                            ):
                                if port == 3:
                                    to_device.device_number = 3
                                    to_device.coach_number = from_device.coach_number
                            # SW 3 of coach 1 connects to SW 2 of coach 1 on port E0-1
                            if (
                                from_device.device_number == 3
                                and from_device.coach_number == 1
                            ):
                                if port == 4:
                                    to_device.device_number = 2
                                    to_device.coach_number = from_device.coach_number
                            # SW 2 of coach 1 and 2 connect to SW 3 of coach 2 and 3 respectively on port E0-1
                            if (
                                from_device.device_number == 2
                                and from_device.coach_number in [1, 2]
                            ):
                                if port == 4:
                                    to_device.device_number = 3
                                    to_device.coach_number = (
                                        from_device.coach_number + 1
                                    )
                    # nv6 - END

                # Add to_device to queue # NDP-PATCH-BUG10-BFS-GUARD
                # Bug 10 fix: only enqueue if coach_number was assigned in
                # one of the branches above. Without this, APs and edge
                # switches whose conditions didn't match get re-enqueued
                # forever, hanging obn report at 100% CPU.
                if to_device.coach_number is not None:
                    queue.appendleft(to_device)
                continue

                # Or use algo from DSB?
                # self.fixed_consist_algo(queue, from_device, to_device, port)


        # ===================== NDP-PATCH-OBNFALLBACK =====================
        # Robustness fallback: the hardcoded walk above numbers switches on
        # their EXPECTED wiring. If a single inter-switch LLDP edge is missing
        # (e.g. a broken intra-coach cable), the walk can leave a reachable
        # switch unnumbered, dropping it from the inventory. The link-down is
        # already caught by the SNMP port alarm; OBN's job is "if reachable,
        # show it". For each still-unnumbered SWITCH reachable via ANY LLDP
        # switch-to-switch path from the numbered set, recover its
        # (coach, device) from its OWN config string and place it, flagged.
        try:
            _u=[d for d in self.device_instances.values() if d.type=="SW" and d.coach_number is None]
            self.logger.error("OBNFB2 unSW=%d attrs=%r", len(_u),
                [(d.mac, getattr(d,"config",None), getattr(d,"configuration_version",None),
                  [a for a in dir(d) if "conf" in a.lower()]) for d in _u][:2])
            _L2C = {"A": 1, "C": 2, "D": 3, "E": 4, "F": 5, "B": 6}

            def _fb_ident(cfgver):
                m = re.match(r"nv6-([A-F])(\d)-", cfgver or "")
                if m:
                    return _L2C[m.group(1)], int(m.group(2))
                m = re.match(r"nv4-([A-G])(\d)-", cfgver or "")
                if m:
                    return _L2C.get(m.group(1)), int(m.group(2))
                return None

            _fb_sw = [d for d in self.device_instances.values() if d.type == "SW"]
            _fb_adj = {}
            for _d in _fb_sw:
                _fb_adj.setdefault(_d.mac, set())
                for _nb in _d.neighbours:
                    _t = self.get_device(_nb)
                    if _t is not None and _t.type == "SW":
                        _fb_adj.setdefault(_d.mac, set()).add(_t.mac)
                        _fb_adj.setdefault(_t.mac, set()).add(_d.mac)

            _fb_reach = set(d.mac for d in _fb_sw if d.coach_number is not None)
            _fb_front = list(_fb_reach)
            while _fb_front:
                _x = _fb_front.pop()
                for _y in _fb_adj.get(_x, ()):
                    if _y not in _fb_reach:
                        _fb_reach.add(_y)
                        _fb_front.append(_y)

            for _d in _fb_sw:
                if _d.coach_number is not None:
                    continue
                if _d.mac not in _fb_reach:
                    continue
                _id = _fb_ident(getattr(_d, "config", None))
                if not _id or _id[0] is None:
                    continue
                _d.coach_number, _d.device_number = _id
                self.logger.warning(
                    "fallback-numbered %s (%s) at coach %s device %s via "
                    "redundant LLDP path - OFF EXPECTED WIRING (check cabling)",
                    _d.mac, getattr(_d, "config", "?"),
                    _d.coach_number, _d.device_number,
                )
        except Exception as _fb_e:
            self.logger.warning("OBNFALLBACK pass error (ignored): %s", _fb_e)
        # =================== END NDP-PATCH-OBNFALLBACK ===================

        # Remove any devices that were not detected properly (switch on wrong ports etc.)
        self.normalise_devices()
