# Report to the back-end
#
# This script will take the JSON report of the backbone discovery script and
# will send it to the NMS (over MQTT) if the contents has changed since last
# transmission. This module implements the Report class and should not contain
# any project-specific code, just parts that are reusable throughout all
# projects.
#
import json
import logging
import os
import re
import time
from abc import abstractmethod
from collections.abc import Callable
from json import JSONDecodeError
from operator import itemgetter

import paho.mqtt.publish
import yaml
from lib import ospf
from lib.configuration import Configuration
from lib.report.device import Device
from lib.report.rules_engine import RulesEngine

logger = logging.getLogger(__name__)


class Report:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cfg = Configuration()
        self.train_type = self.cfg.get("train_type", "unknown")
        self.output_file = self.cfg["output_file"]

        self.device_instances = dict()
        self.previous_instances = dict()
        self.physical_coach_map = None
        self.physical_coach_map_file = self.cfg.get("physical_coach_map_file", None)

    @staticmethod
    def load_device_instances(dictionary: list[dict]) -> dict[str, Device]:
        """Convert a list of dictionaries (loaded from JSON) to a list of Device instances."""
        return {x["mac"]: Device(**x) for x in dictionary}

    def dump_device_instances(self) -> list[dict]:
        """Convert our dictionary of Device instance to a plain dictionary."""
        plain = [x.as_dict() for x in self.device_instances.values()]
        return sorted(plain, key=itemgetter("mac"))

    def load_json(self):
        """
        Try to load both JSON files. If loading the current one fails, we can't send out a report to the NMS,
        so report False. If reading the previous version fails, we need to send out a report, so report True.
        """
        # Check if we can read the JSON report.
        if not os.path.exists(self.output_file):
            self.logger.critical("no report found at %s", self.output_file)
            return False

        # Load the JSON report.
        try:
            with open(self.output_file) as fp:
                output_json = json.load(fp)
            # RD-7740: use the Device class
            self.device_instances = self.load_device_instances(output_json)

        except (PermissionError, TypeError, ValueError, JSONDecodeError) as exc:
            # Log the traceback, but only at DEBUG level to avoid FUD.
            self.logger.debug(repr(exc))
            self.logger.critical("error reading discovery report %s", self.output_file)
            return False

        # If there is no previous version, then this is definitely a new message.
        if not os.path.exists(self.cfg.report_file):
            self.logger.debug("no previous report, so new message")
            return True

        # We load in the previous version of the message.
        try:
            with open(self.cfg.report_file) as fp:
                backup_json = json.load(fp)
            self.previous_instances = self.load_device_instances(backup_json)
        except (PermissionError, TypeError, ValueError, JSONDecodeError):
            self.logger.debug("error reading previous report, new message required")
            return True
        return True

    def compare_json(self) -> bool:
        """
        Compare the JSON files and try to find some differences.

        This method is used to trigger a write of the report to disk and a
        retransmission of the report to the back-end. Devices are unchanged if
        MAC, IP, serial etc... haven't changed, while other properties, like
        uptime, are ignored. For a complete list, see the lib.report.Device
        class.

        :return: True if differences have been found
        """
        # If there's no backup, there's no comparing. If the lists are of different size, same.
        if len(self.device_instances) != len(self.previous_instances):
            self.logger.debug("list has different size, GO for send")
            return True

        # Sort the lists, ignore uptime of the devices and compare.
        current_sort = sorted(self.device_instances.values())
        previous_sort = sorted(self.previous_instances.values())

        # RD-8794: Was not saving discovery.prev.json even if a port was missing in discovery.json
        missing_neighbours = [
            x
            for x in current_sort
            if x.neighbours not in [y.neighbours for y in previous_sort]
        ]

        if current_sort != previous_sort or missing_neighbours:
            self.logger.debug("changes to the report detected, GO for send")
            return True

        self.logger.debug("no changes to the report, not sending")
        return False

    def store_report(self):
        with open(self.cfg.report_file, "w") as fp:
            results = self.dump_device_instances()
            results.sort(key=itemgetter("coach_number", "device_number", "type"))
            json.dump(results, fp, indent=2)

    def report_unexpected_connection(
        self, from_device: Device, to_device: Device, port
    ):
        """Report (c.q. log) an unexpected connection

        Because reports about unexpected connections are often ignored or misunderstood and the message delivered to
        the user has changed often over the course of the years in an attempt to solve that, we spin off the
        reporting part from the coach numbering algorithm, so we can change reporting liberally without touching algo
        code.
        """
        self.logger.warning(
            f"unexpected connection in coach {from_device.coach_number} from {from_device.type}{from_device.device_number} over port {port} to a {to_device.type}"
        )
        self.logger.debug(
            f"from: {from_device.type} with IP {from_device.ip} and MAC {from_device.mac}"
        )
        self.logger.debug(
            f"to  : {to_device.type} with IP {to_device.ip} and MAC {to_device.mac}"
        )

    # --- NMS methods
    def create_nms_report(self, device_nodes) -> dict:
        """
        Create the NMS report from the discovered data. Overrides the Report.convert_... method.

        OBN-134: make sure that, if the method is called more than once, that we don't attempt to coach number the coach
        numbered list - cache the result of the first try and use that.

        :return: the NMS report in dictionary format
        """
        root_node = self.create_nms_root_node()
        root_node["devices"] = device_nodes
        return root_node

    def create_nms_root_node(self) -> dict:
        """
        Create the root node of our report.
        :return: the root node for our NMS message
        """
        new_node = dict()
        new_node["messageInfo"] = "HYBRID_CONSIST_V1"
        new_node["timestamp"] = int(time.time() * 1000)
        new_node["devices"] = list()
        new_node["projectId"] = self.cfg["rtl_project_id"]
        new_node["trainId"] = self.cfg["rtl_train_id"]
        new_node["boxId"] = self.cfg["unit_id"]
        return new_node

    def create_nms_device_nodes(self) -> list[dict]:
        """
        Create the devices list of the NMS report.
        :return: a sorted list of device dictionaries
        """
        results = list()
        for device in self.device_instances.values():
            new_node = dict()
            new_node["coachId"] = device.coach_number
            new_node["paintedCoachId"] = self.get_painted_coach_id(device.coach_number)
            new_node["deviceId"] = device.device_number
            new_node["devicePosition"] = device.device_number
            new_node["type"] = device.type
            new_node["ipAddr"] = device.ip
            new_node["macAddr"] = device.mac.upper()
            new_node["deviceSerial"] = device.serial if device.serial else "unknown"
            new_node["firmwareVersion"] = (
                self.parse_version_string(device.firmware)
                if device.firmware
                else "unknown"
            )
            new_node["configVersion"] = (
                self.parse_version_string(device.config) if device.config else "unknown"
            )
            new_node["uptime"] = device.uptime

            # RD-10294: add target firmware and configuration version to the
            # NMS report / MQTT message, so we can use this info on Engineering
            # Pages.
            if device.target:
                if "firmware" in device.target:
                    new_node["targetFirmwareVersion"] = device.target["firmware"]
                if "config" in device.target:
                    new_node["targetConfigVersion"] = device.target["config"]

            results.append(new_node)

        return sorted(results, key=itemgetter("coachId", "deviceId", "type"))

    @abstractmethod
    def number_coaches(self):
        """
        Abstract method, overridden in child class. Responsible for number the coaches properly.
        :return: the modified json including the coach numbering.
        """
        pass

    def normalise_devices(self, inc=0):
        """
        Go over the list of devices, removing devices without coach number and adding the normalisation to the other
        ones. Sort the list at the end.

        This method is reused in all subclassed reports. It changes self.device_instances, but avoids the for-loop bug
        of RD-8123.
        """
        # Remove the unnumbered devices from the list.
        self.device_instances = {
            k: v
            for k, v in self.device_instances.items()
            if v.coach_number is not None
            and v.device_number is not None
            and v.type is not None
        }

        # Normalise the coach numbers - some algorithms complete with negative coach numbers.
        # TODO: replace inc arg with in-method search and rescue
        if inc != 0:
            self.logger.debug("normalising coach numbers with inc %s", inc)
            for device in self.device_instances.values():
                device.coach_number += inc

    def label_ccu_coach_devices(self):
        """
        Identify the coaches that have a CCU. Then, go over the list of devices,
        setting ccu_coach to True if the device is in the same coach as a CCU or
        False otherwise - RD-9197.
        """

        # Prepare set of coaches containing a CCU
        ccu_coaches = set()
        for k, v in self.device_instances.items():
            if v.type == "BOX":
                ccu_coaches.add(v.coach_number)

        # Label each device with ccu_coach = True/False where appropriate
        for k, v in self.device_instances.items():
            if v.coach_number in ccu_coaches:
                v.ccu_coach = True
            else:
                v.ccu_coach = False

    def apply_firmware_and_configuration_rules(self):
        """
        Will update the required_firmware and required_config fields for each discovered device. This can
        subsequently be used by the update scripts to know exactly what the expected config and firmware should
        be.
        """

        # abort if neither config_rules nor firmware_rules are defined in the config
        if not ("config_rules" in self.cfg and "firmware_rules" in self.cfg):
            return

        # build ourselves a nice rules engine based on the configuration
        rules_engine = RulesEngine(
            self.cfg.get("config_rules", None), self.cfg.get("firmware_rules", None)
        )

        # update the device_instances
        for device in self.device_instances.values():
            if device.type in ["SW", "AP", "ICL"]:
                target = dict()

                expected_config = rules_engine.select_config_target(device)
                if expected_config is not None:
                    target.update(expected_config)

                expected_firmware = rules_engine.select_firmware_target(device)
                if expected_firmware is not None:
                    target.update(expected_firmware)

                device.target = target

    # --- Methods for mapping to physical coach numbers
    def map_to_physical_coach_numbers(self):
        """Add the physical coach number to switch devices if known."""
        for device in self.device_instances.values():
            if device.type == "SW":
                device.physical_coach_number = self.get_physical_coach_number(
                    device.mac
                )

    def get_physical_coach_number(self, mac):
        if self.physical_coach_map is None:
            if self.physical_coach_map_file:
                with open(self.physical_coach_map_file) as fp:
                    self.physical_coach_map = yaml.safe_load(fp.read())
            else:
                self.physical_coach_map = {}

        return self.physical_coach_map.get(mac, None)

    def get_painted_coach_id(self, coach_number):
        for device in self.device_instances.values():
            if (
                coach_number == device.coach_number
                and device.physical_coach_number is not None
            ):
                return device.physical_coach_number
        return "unknown"

    @staticmethod
    def parse_version_string(version_string):
        """
        Support as many version strings as possible. Unrecognised patterns are sent on unchanged.

        We are going to leave the ORing firmware version string ("Kernel K12.57 Software V1.02") unchanged, because it
        contains two values that are both equally important to identify the correct version.

        The Extreme firmware version string can be recorded without change too ("5.9.2.5-001R").
        """
        patterns = {
            "oring": r"oring\-\w+\-(?P<keep>v\d+\-\w+)",
            "extreme": r"ap7562(?:\-\w+)*\-(?P<keep>v\d+\-\w+)",
        }
        for pattern in patterns.values():
            m = re.search(pattern, version_string)
            if m:
                return m["keep"]
        return version_string

    def find_type(self, device: Device, retype_icl: bool = True):
        """
        Based on the data in the device dictionary, we're making an educated guess on what type of device this is.

        :param device: Device instance
        :param retype_icl: whether to retype access points to ICL when applicable
        :return: str: AP/SW/ICL/BOX
        """
        type_found = "UNKNOWN"

        # Find the matching configuration for this MAC address.
        brand = self.cfg.find_brand(device.mac)
        if brand:
            type_found = self.cfg["vendor_specific"][brand]["type"]

        # Check if we're dealing with an access point gone ICL. We can check that by going over its list of
        # neighbours. If any of them are ICL neighbours (c.q. the dictionary has an "icl" key), then this is an ICL
        # type device.
        if retype_icl and type_found == "AP":
            if not device.neighbours:
                self.logger.warning(
                    "AP device %s reports no LLDP neighbours at all", device.mac
                )
            elif any(map(lambda x: "icl" in x, device.neighbours)):
                type_found = "ICL"

        # In the near future, OBN should rely on the "nomad_ccu" (NomadCCUDevice, with SNMPv3) and not on this shortcut.
        # TODO: rework naive CCU detection
        if device.serial and device.serial.startswith("box"):
            type_found = "BOX"

        return type_found

    def get_device(self, meta: str | dict) -> Device | None:
        """Get the device instance from its MAC address or device dictionary."""
        mac = meta if not isinstance(meta, dict) else meta["mac"]
        return self.device_instances.get(mac, None)

    def find_neighbour(self, device: Device, boolean_func: Callable) -> Device | None:
        """Use a boolean function to select a neighbour device to return."""
        if device is None or not hasattr(device, "neighbours"):
            return None
        # We don't expect two neighbours to match the boolean function. Could come back to bite us.
        it = iter(self.get_device(x) for x in device.neighbours if boolean_func(x))
        return next(it, None)

    # --- MQTT methods
    def publish_to_mqtt(self, topic, message):
        if self.cfg.get("enable_mqtt", True):
            self.logger.debug(f"publishing to topic {topic}")
            try:
                paho.mqtt.publish.single(
                    topic, message, hostname="localhost", retain=True
                )
            except ValueError:
                self.logger.error("sending MQTT message failed")
        else:
            self.logger.warning("MQTT disabled, not publishing anything")

    def publish_consist_to_mqtt(self, nms_report):
        """
        Publishes the state of the backbone to the localhost MQTT broker.
        """
        self.publish_to_mqtt("obn/consist", json.dumps(nms_report))

    def generate_device_mqtt_events(self):
        new_devices, old_devices = self.device_instances, self.previous_instances

        added_macs = set(new_devices.keys()) - set(old_devices.keys())
        removed_macs = set(old_devices.keys()) - set(new_devices.keys())
        common_macs = set(old_devices.keys()).intersection(set(new_devices.keys()))

        for added_mac in added_macs:
            self.publish_to_mqtt(
                "obn/event/device_added", json.dumps(new_devices[added_mac].as_dict())
            )

        for removed_mac in removed_macs:
            self.publish_to_mqtt(
                "obn/event/device_removed",
                json.dumps(old_devices[removed_mac].as_dict()),
            )

        for common_mac in common_macs:
            if new_devices[common_mac] != old_devices[common_mac]:
                self.publish_to_mqtt(
                    "obn/event/device_changed",
                    json.dumps(new_devices[common_mac].as_dict()),
                )

    def generate_uptime_mqtt_events(self):
        new_devices, old_devices = self.device_instances, self.previous_instances
        common_macs = set(old_devices.keys()).intersection(set(new_devices.keys()))
        for common_mac in common_macs:
            new_device_uptime = new_devices[common_mac].uptime
            old_device_uptime = old_devices[common_mac].uptime
            if (
                new_device_uptime is not None
                and old_device_uptime is not None
                and new_device_uptime < old_device_uptime
            ):
                self.publish_to_mqtt(
                    "obn/event/uptime_changed",
                    json.dumps(new_devices[common_mac].as_dict()),
                )

    @staticmethod
    def find_ap(device_instances, device_nodes, coach_number, ap):
        for device_node in device_nodes:
            if (
                device_node["type"] == "AP"
                and device_node["coachId"] == coach_number
                and device_node["deviceId"] == ap
            ):
                for device_instance in device_instances.values():
                    if device_instance.ip == device_node["ipAddr"]:
                        return device_instance
        return None

    # --- MAC address file methods
    def generate_mac_addresses_data(
        self, device_instances: dict[str, Device], device_nodes: list[dict]
    ):
        """Generate the MAC address file for the Wi-Fi test tool.

        device_instances is a dictionary of lib.report.Device instances, mapped to their MAC address
        device_nodes is a list of NMS dictionaries
        """
        data = list()

        if self.cfg.get("coach_ap_mapping", False):
            coaches = self.cfg["coach_ap_mapping"]
            for coach_number in coaches:
                coach_configuration = coaches[coach_number]
                # we support two types of configuration, depending on the required use case
                # see for examples:
                # * tests/resources/3ufc/coach_ap_mappings.yaml
                # * tests/resources/tgva/coach_ap_mappings.yaml
                if "radios" in coach_configuration:
                    for radio in coach_configuration["radios"]:
                        ap = radio["ap"]
                        device = radio["device"]
                        self.fill_data(
                            ap,
                            coach_number,
                            data,
                            device,
                            device_instances,
                            device_nodes,
                            radio,
                        )
                else:
                    for ap in coach_configuration:
                        radios = coach_configuration[ap]
                        for radio in radios:
                            radio_data = radios[radio]
                            self.fill_data(
                                ap,
                                coach_number,
                                data,
                                radio,
                                device_instances,
                                device_nodes,
                                radio_data,
                            )

        return data

    def fill_data(
        self, ap, coach_number, data, device, device_instances, device_nodes, radio
    ):
        # support the older config style with "updown" key
        floor = radio["location"] if "location" in radio else radio["updown"]
        frequency = radio["freq"]
        ap_device = self.find_ap(device_instances, device_nodes, coach_number, ap)
        if ap_device and ap_device.bssids and device in ap_device.bssids:
            bssid = ap_device.bssids[device]
        else:
            bssid = "MISSING"
        data.append(
            {
                "bssid": bssid,
                "coach_number": coach_number,
                "floor": floor,
                "ap_number": f"ap{ap}",
                "frequency": frequency,
            }
        )

    def write_mac_address_data(self, data):
        if len(data) > 0:
            self.logger.info("writing mac address data")
            # Folder is taken care of by Puppet, being the root TFTP folder.
            mac_path = self.cfg.get(
                "mac_address_file", "/data/auto-topology/mac-addresses.txt"
            )
            with open(mac_path, "w") as fp:
                for d in data:
                    fp.write(
                        "{};C{};{};{};{}\n".format(
                            d["bssid"].upper(),
                            d["coach_number"],
                            d["floor"],
                            d["ap_number"],
                            d["frequency"],
                        )
                    )
        else:
            self.logger.warning("no data available for mac address file")

    def generate_mac_addresses_file(self, device_nodes: list[dict]):
        """
        Each line of the mac addresses file should contain the following data:

            BSSID;COACH_NUMBER;FLOOR;FREQUENCY

        Where:

        * BSSID is the MAC address of the infrastructure
        * COACH_NUMBER is the coach number preceded by "C"
        * FLOOR is either UP or DOWN (default DOWN if only one floor in coach)
        * FREQUENCY should be 2.4Ghz or 5Ghz

        Example: "04:F0:21:3B:35:3C;C2;UP;2.4Ghz"
        """
        if self.cfg.get("generate_mac_addresses_file", False):
            self.write_mac_address_data(
                self.generate_mac_addresses_data(self.device_instances, device_nodes)
            )

    def run_report(self):
        cfg = Configuration()
        cfg.initialise_logging()

        logger.info(f"starting {type(self).__name__}")

        # Basic workflow when generating a report:
        # - load the newly discovered devices and add coach numbers, type etc...
        # - compare this new report to the old one, excl. uptime...
        # - if there is a difference:
        #   + generate a new report
        #   + publish the report to MQTT
        #   + generate MQTT events

        # We need the coach numbering to apply rules, and we need the rules applied to see if targets have changed.
        self.load_json()
        self.number_coaches()
        self.label_ccu_coach_devices()
        self.map_to_physical_coach_numbers()
        self.apply_firmware_and_configuration_rules()

        # Now we can compare with our previous results to find out if we need to report changes.
        if self.compare_json():
            device_nodes = self.create_nms_device_nodes()
            nms_report = self.create_nms_report(device_nodes)

            logger.info("saving state")
            self.store_report()

            if not self.cfg.get("only_send_as_master", False) or ospf.is_master_ccu():
                logger.info("publishing state to mqtt")
                self.publish_consist_to_mqtt(nms_report)
                logger.info("generating mqtt events")
                self.generate_device_mqtt_events()

            self.generate_mac_addresses_file(device_nodes)

        elif self.cfg.get("always_publish_mqtt", False):
            device_nodes = self.create_nms_device_nodes()
            nms_report = self.create_nms_report(device_nodes)

            logger.info("publishing state to mqtt")
            self.publish_consist_to_mqtt(nms_report)

        self.generate_uptime_mqtt_events()
