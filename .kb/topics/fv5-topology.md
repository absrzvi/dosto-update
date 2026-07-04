---
type: topic
title: fv5 / fv6 (CAT & FV) topology reference
description: Topology of the 4705 (fv5, 5-car CAT) and 4706 (fv6, 6-car FV) consists — coach order, switch/AP counts, CCU cabling, and the unreliable-cfg-descriptions trap.
project: dosto-neu
tags: [fv5, fv6, 4705, 4706, topology, cat]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# fv5 / fv6 topology

The 4705 (**fv5**, CAT 5-Teiler) and 4706 (**fv6**, 6-car FV) consists are separate platform
families from the standard nv4 (4734, 4-car) and nv6 (4736, 6-car) trains. The commissioning
tooling historically did **not** enumerate them (only 4-car/6-car) — see Proven dead ends.

## fv5 (4705 / CAT 5-Teiler)

**= the 6-car nv6 layout with the D/300 wagon removed.** 5 physical coaches, backbone order
**A → C → E → F → B**. Per coach: **3 switches** (X1/X2/X3) + **4 APs** = **15 switches + ~20 APs**.
X3 is the intra-coach hub (connects X1↔X2). Switch hostnames render `fv5-<pos>-v<n>-<fzg>`.

- **CCU/box is in coach C**, cabled to **C1 and C3** (via each C-switch's `e0-2` "OBS D1" trunk).
  Engineer-confirmed 2026-07-03.
- The **firewall on A3** (`e1-4`, "Statische Konfiguration STADLER") is the **Stadler** firewall
  on vlan7 — *not* the Nomad CCU. Do not conflate.
- OBN's `topology.yaml` numbers the CCU coach as `D=3` (6-slot scheme) even though the NMS
  diagram shows it inside coach C. Assembly map: `{1:a100, 2:c200, 3:d300(BOX), 4:e400, 5:f500, 6:b600}`.

### Authoritative sources (priority order)
1. **IP-Port-Allocation PDF** (e.g. `4705-103_IP-Port-Allocation.pdf`, Fzg 231). PDF page-render
   may be unavailable locally, but **text extracts cleanly** via `pdfplumber`/`pypdf` — use that,
   not read-as-image. The `e0-0`/`e0-1` "FIS Switch XY" rows are the real backbone; `e0-2` =
   coupler or OBS-D1 (CCU on C1/C3); `e0-4`/`e1-2` = APs.
2. **OBN `topology.yaml`** (pulled from a live CCU). Encodes wiring as
   `<port>: {type, coach_inc, device_val}`. Note it has duplicate `"SW":` keys per wagon —
   invalid-looking YAML that OBN parses positionally.

Port-level backbone (per-switch `e0-0`/`e0-1` neighbours, coupler/OBS/RDC/FW ports) is extracted
into [**`_shared/fv5-topology.md`**](/train-ip-allocation-commission/extracted/_shared/fv5-topology.md)
(from the 4705-103 IPA PDF, Fzg 231, via `scripts/extract_fv_topology.py`).

## fv6 (4706 / 6-car FV)

6-car FV family (coach order **A-C-D-E-F-B**, D is the OBS coach); **18 switches + 24 APs** like
nv6, hostnames `fv6-<pos>-v<n>-<fzg>`. Port-level backbone is extracted into
[**`_shared/fv6-topology.md`**](/train-ip-allocation-commission/extracted/_shared/fv6-topology.md)
(from the 4706-101 IPA PDF, Fzg 189). Structurally near-identical to nv6.

# Proven dead ends — do NOT repeat these

1. **Do NOT trust the raw `fv5-*.cfg` `e0-0`/`e0-1` `description` strings for wiring.** They are
   hand-typed and **asymmetric** — cross-checking both ends disagrees (E1 desc says peer C2, but
   C2 desc says peer E3; B2 says F2, F2 says F3). Use the IPA PDF trunk rows or `topology.yaml`.
2. **Do NOT run `dosto-commission-train` against a 4705/4706 unmodified.** Its pre-flight
   enumerates only 4-car/6-car; a CAT/FV train (`fv5-*`/`fv6-*` hostnames, ~14–15 switches for
   fv5) blocks pre-flight. The skill needs a platform update first.
3. **Do NOT commission a CAT/FV train with box=Fzg.** Fzg for 4705/4706 is 129–231, which exceeds
   the `factory up` train-ID cap of 0–127 (= 3rd IP octet). box=Fzg only fits 4734 (Fzg 1–90).
   See [box-id / Fzg two-namespaces](/.kb/topics/fzg-id-two-namespaces.md).

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- fv5 switch positions from a live box1-t41 lease (Fzg 231, DHCP so not fixed):
  A1=.179 A2=.184 A3=.182 C1=.181 C2=.189 C3=.178 E1=.186 E2=.183 E3=.185 F1=.192 F2=.188 F3=.180
  B1=.190 B2=.187 B3=.191; APs .218–.237. Hostnames rendered `-231` (Fzg) even though `train_id=41`.
- fv5 `topology.yaml` snapshot on disk:
  `findings/coupling_test_4736-110_119_2026-06-12/fv5_topology_t41.yaml`.

# Related

- [Fzg-ID two-namespaces](/.kb/topics/fzg-id-two-namespaces.md)
- [L2 health methodology](/.kb/topics/l2-health-methodology.md)
- [Fleet: 4705-101 record](/.kb/fleet/4705-101.md)
- [nv6 6-car topology (structural analog)](/train-ip-allocation-commission/extracted/_shared/nv6-topology.md)

# Citations

[1] fv5 topology reference, engineer-confirmed CCU-in-coach-C cabling (2026-07-03).
[2] Live box1-t41 lease + `topology.yaml` pull (Fzg 231, 2026-07-03).
[3] Orchestrator pre-flight block on 4705 platform (2026-05-22).
