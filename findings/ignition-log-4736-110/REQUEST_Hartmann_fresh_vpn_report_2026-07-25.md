# Request to Hartmann — fresh VPN connectivity report for the logged trains

**Draft — for Abbas to review and send.** Same thread / distribution as the RDS Verfügbarkeit chain.
Send timing: end of this week, so the ask lines up with the Monday log review.

---

Subject: AW: [EXTERNAL]AW: AW: [Dosto Neu] RDS Verfügbarkeit

Hello Mr Hartmann,

Thank you again for the VPN session list for 4736-110 — it was very useful. To close the loop on the connection drops, we have now put additional monitoring on the trains, and I would like to ask for one matching data set from your side.

What we have done this week:
1. On 4736-110, 105 and 106 we have enabled detailed connectivity logging on the CCU. It records, per cellular modem, the link state, the carrier IP address, and whether the tunnel is actively carrying traffic — sampled continuously and on every change. This lets us attribute each connection drop to a specific cause (power, cellular coverage, or carrier-side IP re-addressing).
2. We are extending the same logging to 119, 103 and 120 as they come back online.

What would help from your side:
- Please send a fresh VPN connectivity-state report for 4736-110, 105 and 106, covering Monday 28.07 backwards to today. Same format as the 4736-110 list you already sent is perfect.

With both data sets over the same period, we can line up each VPN session drop in your report against our per-drop cause data and give you a clear, evidence-based breakdown of what is behind each one. Our earlier correlation was limited because our detailed logs only began after your list ended; this time the two will overlap fully.

One early technical note from the new logs, for your awareness: the cellular network is re-assigning new IP addresses to some of the modems every few minutes, while the radio signal itself stays healthy. Each re-address briefly rebuilds the tunnel path. We are investigating this with our mobile-network side in parallel, as it looks like a likely contributor to the extra connection drops.

I will review our logs on Monday and we can compare notes once your report is in.

Best regards,
Abbas Rizvi
Nomad Digital

---

## Notes (not for sending)
- Trains named = only where logging is live (110/105/106 as of 2026-07-25). Do NOT ask for trains we
  can't yet correlate (119/103/120 offline) — keep the ask tight to what we can actually match.
- The "carrier re-addressing" note is deliberately brief and framed as "we're investigating with our
  mobile side" — sets up the APN/MNO workstream without over-committing a root cause to the customer.
- Window: "Mon 28.07 back to today (25.07)" gives the weekend of overlap where our loggers run and
  (hopefully) some of ÖBB's drops fall — the whole point of waiting till Monday.
- Keep it in the existing thread so the distribution (Ruisz/Milutinovic/John/etc.) stays looped.
