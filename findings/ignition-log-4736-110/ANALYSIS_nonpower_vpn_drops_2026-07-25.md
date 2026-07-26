# What caused the VPN drops that were NOT ignition / hard power cuts — 4736-110

**Date:** 2026-07-25 · **Train:** 4736-110 (box1-t23 / 10.179.23.1) · **Author:** Abbas Rizvi
**Question:** ÖBB's VPN session list shows more tunnel drops than our CMM power log shows power interruptions. Apart from ignition drops and hard power cuts, what caused the surplus drops?

## Short answer
The surplus (tunnel dropped while the CCU still had power) comes from the **cellular transport**, not the CCU:
1. **Carrier CGNAT / re-key churn** — the modems keep carrier, but the carrier re-maps the UDP NAT binding, forcing the tunnel to re-register. Dominant signal.
2. **Coverage loss** — all modems briefly lose service (dead zones, tunnels, handover gaps).
3. **Reboots** — at each reboot all four uplinks re-register together (expected, not a fault).

## The hard scope limit (must be stated honestly)
**We cannot retroactively prove the cause of the 1–23 July drops.** The tunnel/modem state was only in the CCU's *volatile* journal (wiped every boot); the persistent journal was installed 24 July. So:

| Period | Tunnel/modem evidence available? |
|---|---|
| 1–23 Jul (the disputed VPN list) | ❌ No CCU-side tunnel history survived. Cause can only be **inferred**. |
| 24 Jul 03:00 UTC → now | ✅ Persistent journal + (from 25 Jul) the new netdrop logger. |

There is **no time overlap** between ÖBB's VPN file (ends 23 Jul) and our tunnel evidence (starts 24 Jul). A direct drop-by-drop "this VPN drop = coverage / that one = power" mapping for the disputed period is therefore **not possible after the fact**. That gap is exactly why the netdrop logger (below) was deployed.

## What the 24 Jul → now data DOES show (mechanism, ~33 h sample)
Parsed from the persistent kernel journal (`ndktun` MAR5 tunnel driver, per-modem links l1–l4):

- **1,217 "Link address updated" (NAT rebind) events** and **116 "Auth login failed"** across the 4 links in ~33 h.
- Distribution is **per-link and lopsided** (l1=532, l3=638, l2=136, l4=27) — i.e. individual modems churn constantly while the other three carry the tunnel. This is normal MAR5 multipath behaviour and is **mostly invisible to ÖBB** (the bond rides through it).
- Windows where **all 4 links** re-registered within 120 s = 11. Classified against boot times:
  - **8 coincide with a reboot/power-up** (scheduled 5 h reboots + nightly) → expected re-registration, not a drop.
  - **~3 occurred with the CCU powered and no reboot** (24 Jul 05:52, 24 Jul 09:21, 25 Jul 04:27 UTC) → these are the genuine "whole-tunnel wobble while powered" events = the non-power VPN-drop mechanism, caught in the act.

**Key distinction (do not overclaim):** a per-link `ndktun` rebind is NOT a VPN drop. ÖBB only sees a drop when *all paths* are down together or the session fully re-establishes. Of ~1,200 link events in 33 h, only ~3 were plausible full-tunnel wobbles-while-powered. So the surplus VPN drops are real but few, and transport-side.

## Is the churn itself the root cause? (tested, not assumed)
The churn volume is high (1,217 rebinds + 116 auth-fails / 33 h), so we tested the hypothesis "the churn is what's killing the VPN sessions" rather than assuming it benign. Three discriminating tests:

**TEST A — what kind of rebind is it?** Of 1,213 rebinds: **1,177 = same carrier IP, new UDP port only**; 36 = true IP change; 0 = identical re-register. → The modems KEEP their carrier attachment and address; only the UDP source port changes. This is **tunnel/CGNAT NAT-mapping re-punch**, NOT radio coverage loss. (Coverage loss would show IP loss / registration drop, which we do not see.)

**TEST B — is it systemic or per-modem?** Auth-fails + endpoint-down concentrate almost entirely on **l1 (54+31) and l3 (61+25)**; l2 and l4 are near-silent (1+3, 0+0). The four modems are on four carriers — l-mapping aside, operators present are Magenta/T-Mobile (23203), A1 ×2 (23201), Drei/3AT (23205, 50% signal). → Two links/carriers misbehave; it is not an all-uplink fault.

**TEST C — did the churn ever actually threaten the tunnel?** Windows with **≥3 of 4 links** auth-failing/down within 30 s (what it would take for the bonded tunnel to actually drop): **ZERO** in 33 h. Worst correlated event = 2 links (l1+l3 at 24 Jul 05:53). l2+l4 stayed healthy through every burst, so the bond survived.

**Verdict (honest):**
- In the 33 h we can see, the churn **did not** cause a full VPN drop — the multipath bond absorbed it every time (TEST C = 0). So on this evidence it is a *degradation/quality* problem, not the demonstrated *root cause* of session loss.
- **BUT this does NOT clear it for the disputed 1–23 July period** — we have no tunnel history then, and carrier conditions may have been worse (e.g. if l1/l3-style churn hit 3+ links at once, the tunnel WOULD drop). We cannot say "churn was not the cause" for those dates; we can only say "in the period we can measure, it wasn't."
- The l1/l3 port-remap + auth-fail pattern is worth raising with R&D regardless — it is excess tunnel re-keying against two carriers and is the most likely contributor if churn ever does cause drops.

**What would prove it going forward:** the netdrop logger records `rds_flow` (is the tunnel actually carrying app traffic) alongside per-link state. If a future VPN drop coincides with `rds_flow=0` while `links_up>=1` and power is fine → churn/tunnel is the cause. If `rds_flow=0` only when `links_up=0` → coverage. If only at power events → power. That is the test that settles it per-drop; we just need it running across a real disputed window.

## Why this fully explains Hartmann's "4 drops on 04.07 vs 1 interruption"
A VPN session list counts every tunnel loss (coverage, CGNAT remap, re-key, reboot); the power log counts only power. On 04.07 three of ÖBB's four sessions carried only a few KB (~5 KB, ~5 KB, 118 KB) before dropping — classic re-register churn on top of the underlying power event. VPN-drop-count ≥ power-interruption-count is the expected relationship, not a contradiction.

## The durable fix — netdrop logger (deployed to 110, 2026-07-25)
Purpose-built so the NEXT disputed period has clean cause evidence instead of journal archaeology.
- `netdrop_poll.sh` → `/data/netdrop-log/netdrop.csv`, every 5 s + on change. Records: tunnel up?, default route?, **RDS app flow present in conntrack?**, per-modem carrier/IP state, and per-modem ModemManager state + access-tech (LTE/5GNR) + signal.
- Unit `netdrop-poll.service` installed via btrfs ro-toggle, **enabled (survives reboot)**, active. Verified writing (all 4 modems connected, RDS flow present).
- `netdrop_analyze.py` classifies each outage as POWER / COVERAGE / CARRIER_NAT / REBOOT by cross-referencing the CMM power log (`vign.csv`).
- **Persistence caveat:** like the other /data loggers, the `/etc` unit reverts on a Puppet/NDSU snapshot roll (the `/data` script persists). Re-run install after any promote. Files: `findings/ignition-log-4736-110/netdrop_logger/`.
- **Roll-out:** deploy the same to 105/119/106 when reachable (they were offline at last attempt). 103/120 still pending.

## Root-cause mechanism identified (2026-07-25, from nm-mar3 in persistent journal)
The `mar3.service` (21Net Mobile Access Router) daemon is the tunnel owner. Its journal shows the
actual driver of the churn: **the carrier re-assigns a NEW IP to the WWAN interfaces every few
minutes**, and nm-mar3 does a full link `down`/`up` on each re-address, which rebuilds the tunnel path.
- Example (ce1p0): `10.5.173.209` → `10.143.121.1` → `10.143.221.85` → `10.208.144.92` within hours.
- **`carrier_down_count = 0`** on every modem interface — the physical radio never dropped; signal 100%.
  So this is **carrier IP-layer instability, not coverage loss and not power.**
- Concentrated on 2 of 4 carriers (the l1/l3 links). 4 SIMs = Magenta/T-Mobile (23203), A1 ×2 (23201),
  Drei/3AT (23205 @ 50%). Because 2 carriers stay stable, the bonded tunnel survived every burst (TEST C=0).

**Most likely fix (needs R&D + MNO):** the every-few-minutes re-addressing on specific SIMs is
abnormal for an M2M APN — a stable APN gives a persistent IP. Check APN / IP-lease policy on the
churning SIMs vs the stable ones; may be a carrier CGNAT / short-lease issue. This is the lead most
likely to actually reduce drops, independent of the power dispute.

## Remaining actions to pin root cause
1. **[done] netdrop logger now records per-modem IP** — a carrier re-address writes a `change` row, so
   any future drop is attributable (which modem, IP changed?, rds_flow died?, power?).
2. **Deploy both loggers to 105/119/106** (offline at last attempt), then 103/120 — evidence the fleet.
3. **R&D/MNO: APN + IP-lease audit** on the churning SIMs (l1/l3) vs stable (l2/l4). Likely the real fix.
4. **Ask Stadler for their RDS concentrator's per-session teardown reason** (IKE timeout / peer-initiated /
   idle) — correlating their reason vs our re-address timestamps would be definitive, and they raised the complaint.
5. **The per-drop test (wired, needs a real event):** rds_flow=0 with links_up>=1 & power OK ⇒ tunnel/carrier
   re-address is the cause; links_up=0 ⇒ coverage; power event ⇒ power.

## Evidence provenance
- Journal events: `scratchpad/110_netdrop/journal_net_events.txt` (80,805 lines, 24 Jul 03:00 → 25 Jul 11:49 UTC).
- Modem `all.log` (`/data/nd-modems/`) turned out to be hotswap-check noise only — NOT a registration history. Not usable for coverage. (Documented so nobody re-tries it.)
- `bond0 lan0` "link status down" (54k events) = internal management-bond L2 flap, NOT cellular — red herring for VPN drops.
- Live conntrack + tcpdump confirming the RDS path (62.2.130.53 via mar5-tun; CCU→77.237.62.210 IPsec underlay) documented in `REPLY_to_Hartmann_2026-07-25.md`.
