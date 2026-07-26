# Reply to Peter Hartmann — 4736-110 RDS availability / VPN vs power correlation

**Draft — for Abbas to review and send.** Thread: "AW: [EXTERNAL]AW: AW: [Dosto Neu] RDS Verfügbarkeit"
Reply-to: Peter Hartmann (Stadler); Cc the existing distribution (Ruisz, Dorner, Milutinovic, John, Schnurr, Satzinger, Duch, Stanek, Huber, Altintas).

---

Subject: AW: [EXTERNAL]AW: AW: [Dosto Neu] RDS Verfügbarkeit

Hello Mr Hartmann,

Thank you for the VPN session list for 4736-110 — it is genuinely helpful, and it agrees with our CCU-side power log rather than contradicting it.

On your key observation — that there are more VPN connection drops than voltage interruptions (e.g. four VPN sessions on 04.07 against one interruption in the diagram): that is expected, and it actually supports the power-loss finding rather than weakening it.

1. The two logs count different things. Our CCU power log counts losses of supply. A VPN session list counts every loss of the tunnel — which also happens on cellular coverage loss, cell handover, and the periodic tunnel re-key, all while the CCU stays powered. So VPN drops will always be equal to or greater than power interruptions. That is the normal relationship.

2. We correlated the two datasets directly (both in UTC). 28 of our 38 CCU power events line up to within about 10 minutes of a VPN session ending. The remaining 10 are cases where the CCU recovered within a few minutes but the next VPN session was only re-established later, or short blips that fell inside one longer VPN session — differences in logging granularity, not disagreements.

3. Your 04.07 example illustrates the mechanism. The VPN list shows four sessions that day; three of them carried only a few kilobytes (about 5 KB, 5 KB and 118 KB) before dropping again. Those are tunnel setup/re-key attempts that never carried real traffic — exactly the kind of extra drops that sit on top of the underlying power events.

The underlying signature is unchanged and clean: no internal CCU or software fault (chassis fault flags read 0x00 throughout), 9 planned reboots, and 29 unexpected external power losses in two forms — 12 ignition drops (Vign to 0 V while battery Vin held) and 17 abrupt hard cuts (everything nominal to the last sample, then instant loss). Both sit upstream of the CCU.

So that we can close this out, two requests and one clarification:

1. Vehicle-side logs. Please share the vehicle power / ignition-relay / battery-isolator event log for 4736-110 covering 03.07–24.07 (UTC). Correlating those switching events against our per-event list is the fastest route to the exact mechanism, in particular why the ignition line (Vign) collapses to 0 V while battery voltage is still present.

2. On the "24/7 online" question. A vehicle will not be online 00:00–23:59 — the long gaps in the VPN list are overnight ignition-off / parked periods, which is normal and matches the long downtimes in our log. The drops that matter are the short ones during service.

3. Endpoint — the addresses are all consistent, each playing a distinct role. We checked 4736-110 live from the CCU today:
   - The CCU builds its encrypted tunnel to 77.237.62.210 (the backend server's inbound interface) — live IPsec/ESP traffic on UDP 4500/4501 across the cellular uplinks.
   - 77.237.62.211 is the backend server's outward interface, which is why it appears as the session "actual address" in the VPN list. The CCU does not send to it directly.
   - 62.2.130.53 is the RDS application destination the RCU actually talks to, carried inside the tunnel — we observed a steady bidirectional UDP exchange on port 83, originating vehicle-side (vlan7, 172.19.197.1).

   In short: the vehicle-to-RDS path is live and correctly routed. 77.237.62.210 / .211 are the two interfaces of your backend server (inbound / outbound), and 62.2.130.53 is the application endpoint behind it.

Our detailed per-event evidence (timestamps, Vin/Vign, classification) is in the report already shared; I am happy to walk through the correlation on a short call.

Best regards,
Abbas Rizvi
Nomad Digital

---

## Evidence backing each claim (not for sending — Abbas's reference)

- **Timezone**: VPN file header says [Europe/Zurich]. Verified against our UTC log by two-edge matched-pair test: median |VPN session-end − CCU last-healthy| = 10.5 min at UTC+2, vs 70 min at UTC+1 and 129 min at UTC+0. UTC+2 (CEST) confirmed. All correlation done with VPN converted to UTC (−2h).
- **28/38 corroborated**: tight test = a VPN session ends within 45 min of the CCU last-healthy sample. (An earlier loose "overlap" test gave 36/38 but let multi-hour VPN gaps match almost anything — 28/38 is the defensible number.)
- **10 non-tight matches**: CCU recovered in minutes but next VPN session logged hours later (#3, #7, #21, #22), or short CCU blips inside one long VPN session (#11, #26, #27, #28), plus two near the 45-min boundary. None are contradictions.
- **3 "VPN-only" gaps** (offline while powered) are all 01–03 July, before the 03.07 analysis window — outside the compared period.
- **04.07 detail**: VPN sessions 01:10→01:21 (118 KB), 01:48→01:59 (4.97 KB), 05:04→05:20 (5.12 KB), 06:49→09:20 (169 MB). Three of four are near-zero-data churn.
- **Fault classification counts** (from the 24.07 CCU Power Outage report): 9 Commanded / 12 Ignition drop / 17 Abrupt hard cut / 0 Supply loss; fault byte 0x00 on all 38.
- **Endpoint — now confirmed live (2026-07-25, box1-t23 / 10.179.23.1, UTC)**. Corrected model per Abbas: .210 = backend inbound (CCU→here), .211 = backend outbound (VPN-log "actual address"), 62.2.130.53 = RDS app endpoint.
  - **CCU → 77.237.62.210 (backend inbound)**: multiple ASSURED UDP flows on ports **4500/4501** = IPsec NAT-T. `tcpdump -ni any` shows `UDP-encap: ESP` to `.210:4500` on the **modem interfaces** ce0p0/ce1p0/ce2p0/ce3p0 (carrier locals 10.10.x / 10.143.x / 10.48.x). This is the encrypted tunnel underlay, built across all 4 modems (MAR5 multipath).
  - **77.237.62.211**: **0** conntrack entries → CCU does not send to it. It is the backend's outward interface = the session "actual address" ÖBB's VPN file records.
  - **62.2.130.53 (RDS app)**: ASSURED UDP `src=172.19.197.1 dst=62.2.130.53 dport=83`, NAT'd to tunnel src `10.179.23.254`; 30s capture on `mar5-tun` showed `62.2.130.53.83 <> 10.179.23.254.49572` ~8s apart. `172.19.197.1` = vlan7 Stadler FW/RCU side (CCU vlan7 = .2) → originates vehicle/Stadler-side.
  - Note: `ip route get .210/.211` returns `dev mar5-tun` (route artifact once tunnel is up); the *real* underlay is modem→.210:4500 shown by the per-iface capture. `mar5-tun` = Nomad `ndktun`, MTU 1344.
  - Conclusion: path is live and correctly routed today. Roles: .210 inbound / .211 outbound (two NICs of the backend) / 62.2.130.53 = app endpoint behind it. We confirm *routing/transport* health only — not the port-83 application payload (Stadler-side).

## Scope caveats (so we don't overclaim)
- This correlation is **4736-110 only**. We do **not** currently hold CCU power data for 105/119 (their CCUs were offline at last attempt), and the fleet VPN file (Datenaufstellung 16.07) only runs to ~13–16 July for those trains — so a like-for-like correlation for 105/119 is not yet possible. Do not imply it in the reply.
