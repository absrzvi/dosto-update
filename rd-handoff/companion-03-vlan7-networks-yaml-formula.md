# Companion 3 — `/etc/nd-redundancy/networks.yaml` vlan7 IP formula computes from OBN's `train_id` not Fzg ID

**Repo:** Puppet (`nd-redundancy` module) — likely; needs confirmation
**Not in:** `nd-obn`

## Summary

The vlan7 IP (CCU's static IP on the Stadler interconnect VLAN) is computed by a formula in `/etc/nd-redundancy/networks.yaml`. The formula reads OBN's internal `train_id` variable to derive the IP. But OBN's `train_id` is a separate concept from the customer-facing Fzg ID — on DOSTO NEU consists they're deliberately decoupled (mar5 migration workaround). So the formula computes a wrong IP for the consist's actual Fzg.

Symptom: on commissioning, the CCU comes up with a vlan7 IP that doesn't match what the Stadler firewall expects to peer with. ARP fails, end-to-end probes fail, every L2 health check fails Phase 6 (vlan7 reachability) even though the L2 fabric itself is healthy.

The active vlan7 IP at runtime actually comes from `/etc/NetworkManager/system-connections/ndrd-vlan-vlan7.nmconnection` (the `address1=` line), which is set per-train via `nd-systemupdate.sh shell` chroot. So the `networks.yaml` formula is **vestigial but harmful** — it computes a wrong value that fights with the nmconnection at boot if NetworkManager hasn't already won the race.

## Reproducer

1. Fresh CCU on current image, no engineer has touched the chroot yet.
2. Boot. Observe `ip -br addr show vlan7` reports an IP that does NOT match the bit-packed-from-Fzg expected IP for the train.
3. `cat /etc/nd-redundancy/networks.yaml` — find the formula. It uses `train_id` (OBN's), not the Fzg.
4. The right value comes from `nmconnection`. After the engineer applies the chroot fix (per skill `dosto-vlan7-config`), `nmconnection` wins and the IP is correct.

## The actual fix

Two options:

**Option A — Remove the formula from `networks.yaml` entirely.**
The `nmconnection` file is the source of truth on this image. Have Puppet stop shipping a `networks.yaml`-driven vlan7 IP; let `nmconnection` own it. The skill `dosto-vlan7-config` would then just edit `nmconnection` and the chroot wouldn't have to fight a wrong yaml value.

**Option B — Make the formula compute from the right input.**
The formula should derive vlan7 IP from the Fzg ID (the bit-packed scheme documented in `CLAUDE.md` § vlan7 IP formula). This requires the CCU to *know* the Fzg ID, which currently it does only via the `train_id` in `/etc/obn/template/nv*-*.cfg` (which has its own breakage — see [Companion 4](companion-04-fzg-id-template-formula.md)). Solving Companion 4 first would unblock this.

We prefer Option A — fewer moving parts.

## Bit-packed vlan7 IP formula (for reference)

For DOSTO NEU CCUs:
- octet 1–2: `172.19` (static prefix)
- octet 3: `128 + (Fzg // 2)`
- octet 4: `(128 if Fzg is odd else 0) + 2`
- prefix: `/17`

So Fzg 132 → `172.19.194.2/17`; Fzg 133 → `172.19.194.130/17`. Stadler FW is always `.1` on the same `/17`.

## Test evidence

Confirmed on every train where the engineer hasn't yet applied the `dosto-vlan7-config` chroot fix. See [.claude/skills/dosto-vlan7-config/SKILL.md](../.claude/skills/dosto-vlan7-config/SKILL.md) and memory `project_obn_update_target_catch22.md` for the Fzg 130 instance.

## Marker

After fix, on a fresh CCU boot, `ip -br addr show vlan7` should show the bit-packed-from-Fzg expected IP without engineer intervention.
