#
# Print a human-friendly map of the backbone for validation.
# This module is supposed to be called with the obn script (Click-enabled)
#
# TODO: move to cli module
#

import ipaddress
import json
import logging
import os
import sys
from operator import itemgetter

from colorama import Fore
from lib.configuration import Configuration
from lib.validate import Validate
from prettytable import PrettyTable

logger = logging.getLogger(__name__)


class Table:
    field_names = [
        "COACH",
        "DEVICE",
        "IP",
        "FIRMWARE",
        "CONFIG",
    ]
    title = {
        "SW": "Backbone switch overview",
        "AP": "Backbone access point overview",
        "ICL": "Backbone inter-coach link overview",
        "MEDIA": "Backbone media server overview",
    }

    def __init__(self, enable_color=True):
        self.cfg = Configuration()

        # What IP range do we expect the devices to be in?
        ip = (
            "10."
            + str(self.cfg["project_id"] + 128)
            + "."
            + str(self.cfg["train_id"])
            + ".0/24"
        )
        self.ip_range = ipaddress.ip_network(ip)

        # Fancy colourised output at your fingertips.
        if enable_color:
            self.OK = Fore.GREEN + "✓" + Fore.RESET
            self.NOK = Fore.RED + "✗" + Fore.RESET
        else:
            self.OK = "✓"
            self.NOK = "✗"

    def _draw_table(self, type_: str, rows: list) -> str:
        """Leverages PrettyTable to create a text tabled overview"""
        x = PrettyTable()
        x.title = self.title[type_]
        x.field_names = self.field_names
        for field_name in self.field_names:
            x.align[field_name] = "l"
        x.add_rows(rows)
        return x.get_string()

    def _validate(self, device: dict, item: str) -> str:
        """Validates a field (out of several) and returns a check or cross mark"""
        # Validate IP?
        valid = False

        # If that key is missing, validation for this item fails at the start.
        if item not in device:
            return "incomplete " + self.NOK

        # Retrieve the target configuration and other data.
        target = device.get("target", {}).get(item, "")

        # Validate the IP address of the device, which should be part of the on-board management network.
        if item == "ip":
            ip = ipaddress.ip_address(device["ip"])
            valid = ip in self.ip_range

        # Validate firmware or config?
        # E.g. switch reports "oring-000000000000-v0-M1", target config is "v0-M1".
        elif item in ["firmware", "config"]:
            valid = target in device[item]

        return (
            device[item]
            + " "
            + (
                self.OK
                if valid
                else (f"({target}) " + self.NOK if len(target) > 0 else self.NOK)
            )
        )

    def _create_overview(self, devices, type_) -> str:
        """Generic create-my-overview method, reusable for switches and access points"""
        devices = [x for x in devices if x["type"] == type_]
        rows = list()
        for device in devices:
            values = [
                device["coach_number"],
                device["device_number"],
                self._validate(device, "ip"),
                self._validate(device, "firmware"),
                self._validate(device, "config"),
            ]
            rows.append(values)
        rows.sort(key=itemgetter(0, 1))
        return self._draw_table(type_, rows) + "\n"

    def create_switch_overview(self, devices) -> str:
        return self._create_overview(devices, "SW")

    def create_accesspoint_overview(self, devices) -> str:
        return self._create_overview(devices, "AP")

    def create_inter_coach_link_overview(self, devices) -> str:
        return self._create_overview(devices, "ICL")

    def create_media_overview(self, devices) -> str:
        return self._create_overview(devices, "MEDIA")


# Side-file of console-only placeholder rows, written by DostoNeuReport.number_coaches.
# backbone_validate is SHARED by every fleet's `obn validate`; the merge below is
# therefore GUARDED to the DostoNeu report type so this file's behaviour is provably
# unchanged for all other fleets (ace/ccjpa/tgv/luna/queensland/dsb/via/dani/…).
_DOSTO_PLACEHOLDER_FILE = "/tmp/discovery.placeholders.json"


def load_devices(cfg) -> list:
    """Load discovery.prev.json into a list of devices.

    NDP-BYPASS-FIX (2026-07-04): for DostoNeu ONLY, merge in console-only placeholder
    rows (DOWN / UNKNOWN / UNPLACED / INCOMPLETE-banner) from the side-file written by
    DostoNeuReport.number_coaches. These rows are DELIBERATELY absent from the report
    snapshot and the NMS/MQTT message (they must not create Zabbix hosts) — they exist
    only to be shown here in `obn validate`. For every other fleet this is a no-op:
    the report_module guard skips the merge entirely (and the side-file wouldn't exist
    anyway, since only DostoNeuReport writes it)."""
    if not os.path.exists(cfg.report_file):
        logger.critical("no OBN report - exiting")
        sys.exit(1)

    with open(cfg.report_file) as fp:
        devices = json.load(fp)

    # GUARD: DostoNeu only. Non-DOSTO fleets return here with identical behaviour to
    # before this change.
    if cfg.get("report_module") != "DostoNeuReport":
        return devices

    try:
        if os.path.exists(_DOSTO_PLACEHOLDER_FILE):
            with open(_DOSTO_PLACEHOLDER_FILE) as fp:
                devices = devices + json.load(fp)
    except (OSError, ValueError) as exc:
        logger.warning("could not merge DostoNeu placeholder side-file: %s", exc)

    return devices


def validate(cfg: Configuration, type_: str = "all"):
    cfg.initialise_exception_hook(logger)  # Log unhandled exceptions
    logger.info("starting validate")

    # First phase will run a set of generic tests to inform the user if some issues have risen
    val = Validate()
    results = val.run_all()
    for test, result in results.items():
        print(f"{Fore.RED}⚠ {test}{Fore.RESET}: {result}", file=sys.stderr)
    print()

    # Second part shows a table of all correctly processed devices and their firmware en configuration versions.
    devices = load_devices(cfg)
    t = Table(enable_color=True)

    if type_ == "all":
        print(t.create_switch_overview(devices))
        print()
        print(t.create_accesspoint_overview(devices))

        # _If_ there are any ICL devices, show the ICL overview.
        if any([x["type"] == "ICL" for x in devices]):
            print()
            print(t.create_inter_coach_link_overview(devices))

        # _If_ there are any MEDIA devices,...
        if any([x["type"] == "MEDIA" for x in devices]):
            print()
            print(t.create_media_overview(devices))

    elif type_ == "sw":
        print(t.create_switch_overview(devices))

    elif type_ == "ap":
        print(t.create_accesspoint_overview(devices))

    elif type_ == "icl":
        print(t.create_inter_coach_link_overview(devices))

    elif type_ == "media":
        print(t.create_media_overview(devices))

    logger.info("done")


if __name__ == "__main__":
    validate()
