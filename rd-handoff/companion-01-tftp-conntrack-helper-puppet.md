# Companion 1 — CCU firewall TFTP conntrack helper missing → silent `obn update f ap` batch failure

**Repo:** Puppet (`60-allow-management` module or equivalent)
**Not in:** `nd-obn`

## Summary

On the current CCU image, the kernel module `nf_conntrack_tftp` is not loaded and no iptables raw-PREROUTING rule exists to mark UDP/69 traffic for TFTP CT-helper handling. Without these, TFTP data connections (UDP from random high port back to the requesting client) are not associated with the TFTP control connection in conntrack. Most are silently dropped by `60-allow-management`'s default-deny stance.

Symptom: `obn update f ap` against a 16-AP batch sees ~5/16 succeed (the ones whose data-port choice happens to race past conntrack), the rest silently fail. OBN reports "Successful" because it never sees an error. Engineer finds out via `obn discover` afterwards.

## Affected versions

Confirmed on every CCU image we've touched in this rollout. The Puppet module `60-allow-management` is the one we'd expect to set this up — it doesn't.

## Reproducer

1. Any CCU on the current image. `sudo lsmod | grep nf_conntrack_tftp` returns nothing.
2. `sudo iptables -t raw -L PREROUTING -n -v | grep -i tftp` returns nothing.
3. `sudo obn discover && sudo obn update f ap` on a consist with ≥10 APs needing firmware.
4. Wait. Observe ~5 succeed, rest silently fail. Confirm via post-run `obn discover` that the failed APs are still on old firmware.

## Runtime workaround (does not survive reboot)

```bash
sudo modprobe nf_conntrack_tftp
sudo iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp
```

After applying, `obn update f ap` works against all APs in the batch.

This is what our skill `dosto-tftp-helper-check` prints; the engineer runs it before every AP firmware batch. It's wiped on every CCU reboot.

## Persistent fix (the actual ask)

Two parts, both in Puppet:

1. Ensure `nf_conntrack_tftp` is in `/etc/modules-load.d/` so it loads at boot.
2. Add a raw-PREROUTING rule (likely to `60-allow-management` or a sibling module) that marks UDP/69 for TFTP CT-helper handling. Equivalent to the `iptables` line above, but persisted via Puppet's iptables resource type.

The rule must apply before NetworkManager / nftables resets the chain, which is currently the failure mode for hand-edited persistent attempts.

## Test evidence

- Validated runtime fix on Fzg 132 (2026-05-09) and Fzg 143 (2026-05-20). With the runtime fix applied pre-push, 15/15 APs succeeded on a batch run. Without it, 5/15.
- See memory [`project_tftp_conntrack_helper.md`](../?) and [`project_obn_update_f_ap_batch_experiment_fzg143.md`](../?).

## Marker (regression test)

After a CCU reboot, `sudo lsmod | grep -q nf_conntrack_tftp` should exit 0, and `sudo iptables -t raw -S PREROUTING | grep -q "tftp"` should exit 0. Our skill `dosto-tftp-helper-check` already encodes both checks.

## Notes for R&D

This is the dependency for Bug 5 (`tftp_allowed` ipset pre-population) to actually work end-to-end. Bug 5 ensures the ipset has the right IPs; this fix ensures the kernel's conntrack layer associates TFTP data flows correctly so those IPs' TFTP requests actually arrive at OBN's TFTP server. Both must land together for the AP firmware-batch path to be reliable.
