# Draft email to ÖBB — Fzg 138 / 4736-110 power-logging

**Attachment:** `vign_4736-110_20260618_normalized.csv`
**Suggested subject:** Fzg 138 (4736-110) — power-supply logging in place; repeated ignition-input dropouts observed

---

Dear [Name],

To investigate the repeated unplanned power-downs on Fzg 138, we have installed continuous power-monitoring on the onboard CCU. The attached CSV is the recording to date. We would like your help engaging Stadler, as the evidence points to a vehicle-side ignition-input issue rather than a Nomad equipment fault.

**1. What we set up**

The CCU now records its supply voltages directly from the chassis power module every few seconds, to persistent storage that survives a power-down. For each sample we log two key values:

- **Vin** — the vehicle battery supply to the CCU.
- **Vign** — the vehicle ignition signal that tells the CCU to stay powered.

A healthy state has both at roughly the same voltage (~108–125 V).

**2. What we observed**

On at least two occasions the ignition signal (Vign) dropped to **0 V while the battery supply (Vin) stayed normal**, and the CCU then powered down shortly afterwards. A loss of ignition while the battery is healthy is a vehicle-side electrical event, not a CCU fault.

Three unplanned power-downs occurred over the three days monitored (times in local CEST):

| Event (CEST) | Vin (battery) | Vign (ignition) | Power restored (CEST) | Outcome |
|---|---|---|---|---|
| 16 Jun, 21:12 | 114.9 V (normal) | **0 V** | 17 Jun, 08:03 (~11 h later) | ignition lost; CCU powered down |
| 17 Jun, ~08:28 | 125.6 V (normal) | not captured* | 17 Jun, 23:40 (~15 h later) | CCU powered down; last reading before shutdown was healthy |
| 18 Jun, 07:31 | 109.8 V (normal) | **0 V** | 18 Jun, 07:38 (~7 min later) | ignition lost; CCU powered down |

In the CSV the captured events are the rows where the `vign_v` column reads `0.00` while `vin_v` remains around 110–115 V (filter or sort on `vign_v` to find them). The `reason` column marks logged events; a `start` value indicates the CCU restarting after a power-down.

\* On 17 Jun the logger was sampling at 5-minute intervals and the exact shutdown moment fell between samples, so the voltage transition was not captured for that event. We have since **tightened the logging to record at much shorter intervals** (every 30 seconds), which is what allowed us to capture the 18 Jun event directly. Monitoring is ongoing and will capture the full detail of any further events.

**3. What we are asking**

1. Please raise this with Stadler to check the **vehicle ignition feed and the CCU front-panel power switch wiring** on Fzg 138 — the recurring loss of the ignition signal with the battery healthy indicates a fault on the vehicle ignition input.
2. We are happy to share the raw data and join a short call to walk through it.

The logging remains active and will capture any further events. We will send an updated recording if more occur.

Best regards,
[Your name]
Nomad Digital

---

## Notes for you (not part of the email)

- **One honesty caveat for internal awareness:** the chassis currently reports power mode `MANUAL_on` (front-panel switch = ON), in which the ignition input is *supposed* to be bypassed. Yet the CCU still powers down right after Vign→0. This is the open contradiction — it means either the switch isn't truly on Manual (a wiring/readout mismatch, which itself supports the "check the wiring" ask) or Vign and the power-down share an upstream cause. I kept this OUT of the customer email to avoid muddying the ask, but it's the thing to confirm by eye on the next physical visit. If ÖBB/Stadler push back, this is the nuance to raise.
- The 17 Jun ~08:30 silence you saw in NMS is also in the data (a `start` gap), but it fell in an older 5-minute sampling window so we don't have the exact Vign transition for it — that's why I cited only the two clean captures.
- Attachment column reference is in the conversation / `vign.csv` header; send only the normalized file.
