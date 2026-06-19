Firmware binaries are NOT committed here (large, and identical to nv4/nv6 packages).
Before building the .deb, copy these two from the nv4 template repo
(onboard/nd-obn-template-dostoneu-nv4, src/etc/obn/firmware/):
  - ipart-ng.kad-7-4-2          (VDS switch fw 7.4.2, referenced by rules.yaml firmware_rules SW)
  - IBEX-firmware-6.11.2-0.img  (Westermo AP fw 6.11.2-0, referenced by AP)
These match the firmware_rules targets and the current fleet target versions.
