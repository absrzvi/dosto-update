---
type: component-index
title: Westermo AP — component knowledge
description: How the Westermo RT610LV consist access point behaves — factory vs Nomad config, the SNMP-silence and brick traps, the LuCI HTTP bypass, and firmware-activation flakiness — with the dead ends already disproven on live hardware.
component: westermo-ap
vendor: Westermo
project: dosto-neu
---

# Westermo AP (RT610LV)

Industrial IbexOS Wi-Fi access point used in the consist. Two config forms (factory / Nomad) with very
different management surfaces. Identify on the wire by MAC OUI `00:14:5a`.

## Configuration

* [Factory vs Nomad config](factory-vs-nomad-config.md) — why factory config silently blocks controller SNMP, the LuCI HTTP two-step import bypass, how to tell the two forms apart from the DHCP hostname (never from SNMP silence), the don't-diagnose-a-brick rule, the `coach_ap_mappings` report-label red herring, and how to read live radio/SSID state.

## Firmware

* [Firmware activation](firmware-activation.md) — why a push stages but doesn't always activate: the flash-trigger hang vs the download-failure-under-batch case, why the controller never verifies post-reboot, and the uptime + `rpcFwFlash` signals that tell "slow-but-fine" from "genuinely hung."
