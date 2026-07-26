**To:** [Stadler contact]
**From:** Abbas Rizvi, Nomad Digital
**Date:** 2026-07-24
**Subject:** CCU availability — monitoring in place on 106/110/105/119, and the 5-hour reboot

Hi [name],

Quick update on the CCU offline issue. Two asks answered up front:

1. The 5-hour automatic reboot you requested is implemented and persistent on all four
   currently-reachable trains as of today; first cycle runs from ~14:07 UTC.
2. We have added detailed monitoring to the same trains so the next occurrence is captured
   with the data we need to find the cause.

**What we have put on the trains today**

1. **5-hour auto-reboot (your requested stopgap).** Live on 106, 110, 105, 119. Each CCU
   reboots 5 hours after it last started, and re-arms automatically after any restart. It is
   set up so each scheduled reboot is clearly logged as a planned event, so it does not hide
   or distort the fault data we are collecting.
2. **Power logger** on 110, 105 and 119. Records the CCU input and ignition voltage, internal
   rails and temperature every 2 seconds to non-volatile storage, so we can see exactly what
   the supply does in the moments before a shutdown.
3. **Persistent system logs** on 106, 110, 105 and 119. The CCU's normal logs are cleared on
   every reboot; we have redirected them to storage that survives a reboot, so the next
   "on but unreachable" event leaves a diagnosable record.

Trains 103 and 120 were powered down / unreachable while we worked; we will apply the same
three items as soon as they come online.

**What the evidence shows so far**

The data points to two different failure modes behind the same "offline" symptom:

1. On 110 and 105, the CCU loses input power while otherwise healthy (no internal fault, no
   controlled shutdown). This is consistent with a vehicle-side power event and is not
   something a reboot prevents.
2. On 106, the CCU stayed powered but became unreachable and recovered on a manual reboot —
   a different, software/hardware hang-type behaviour. For this mode a scheduled reboot is a
   useful stopgap.

For context, the R5001C CCU draws roughly 2 A continuous at 110 V and its internal rails were
stable through every event we logged, so the unit itself is behaving within specification.

**Next steps**

1. Run the four trains next week as planned; we will review the captured data and share findings.
2. Please share the vehicle power / ignition-relay log for 106, 110 and 105 over 03–24 July if
   available — correlating it against our CCU records is the fastest route to root cause.

Happy to walk through any of this on a call.

Best regards,
Abbas Rizvi
Nomad Digital
