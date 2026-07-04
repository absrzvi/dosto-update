# Query to Stadler — passenger displays unable to reach ZFR at power-up (4736-120)

**Draft for Abbas Rizvi to review/send. Keep the body short; the detail section is for the linked doc, not the message.**

---

**Subject:** 4736-120 — displays reach ZFR only after a switch reboot at power-up

Hi [Stadler contact],

On 4736-120 this morning the passenger displays had link but could not reach the ZFR until the consist switches (F2, A2) were rebooted. From the Nomad side the L2 network checks out, so we'd like your read on the display/ZFR side.

Three questions:

1. At power-up, is there a known ordering dependency where the displays come up before the ZFR (or before the Stadler firewall has applied its config), and how do the displays recover if their first ZFR connection attempt fails?

2. Do the displays retry the ZFR indefinitely, or can they enter a stuck state that only a link bounce (switch reboot) clears?

3. Is there anything on the Stadler side (ZFR boot time, firewall policy load, display app) that would explain why a switch reboot — which just bounces the display links — restores ZFR reachability?

We're running a controlled cold-boot capture on a switch in parallel to rule in/out a switch-side cause. Happy to share what we find.

Thanks,
Abbas

---

## Background detail (for a linked doc / on request — NOT the message body)

- **Symptom (on-site tester, 2026-06-24):** displays had link but no ZFR data. Switch A2 e1-9 showed a red PoE LED. Rebooting F2 and A2 restored ZFR reachability for almost all displays.
- **Nomad-side findings:**
  - Display access ports are physically clean — `carrier false: 0`, no CRC/RX errors, correct 100M/full negotiation.
  - The displays sit on the Stadler display VLAN behind the Stadler firewall; the CCU/switches have no direct visibility of display-to-ZFR traffic (only the vlan7 transit link).
  - We could not reproduce a switch-side dataplane fault across 126 switches on 7 trains (switch logs are shallow, so this is not conclusive).
- **Separate, confirmed switch-side item (not the ZFR symptom):** A2 e1-9 (redundant Sprechstelle link) has a genuine PoE fault (`E(1e)`, 0 W, no RX) that a reboot did not clear — logged for a physical cable/connector/device check. See cable-issues register #12.
- Why we're asking Stadler: a switch reboot only bounces the display links, yet it restores ZFR reachability — which points at a power-up ordering / recovery behaviour on the display or ZFR side rather than a persistent network fault.
