---
type: component-knowledge
title: Nomad Connect / CCU — NDSU chroot & the btrfs persistence model
description: How to make edits to a btrfs-snapshot CCU survive reboot via nd-systemupdate.sh, the .dont rename, the chroot heredoc rule, and the work-vs-run subvol trap.
component: nomad-connect-obn
project: dosto-neu
tags: [ccu, btrfs, nd-systemupdate, chroot, persistence, snapshot, dead-ends]
maturity: field-validated
timestamp: 2026-07-04T00:00:00Z
---

# Overview

The Nomad **CCU** (`box1-tNN`, a Debian jump box) runs its root filesystem from a **btrfs read-only
snapshot**. This has one dominant consequence for anyone who edits files on it: **a plain edit to `/`
does not survive a reboot** — the next boot rolls back to the previous "release" snapshot and your
change vanishes. Persistence is a deliberate, multi-step operation via the system-update tool
(`nd-systemupdate.sh`). This doc is the model for making CCU edits durable without losing them to a
rollback or a nightly auto-update.

Three classes of CCU state you'll touch and how each persists:

| State | Owned by dpkg? | Survives an NDSU update? | Persistence path |
|---|---|---|---|
| OBN engine code (`/usr/share/obn/**`) | **Yes** (`nd-obn`) | **No** — rewritten on package upgrade | chroot promote; re-apply after every `nd-obn` bump |
| `/etc` config (vlan7 nmconnection, `train_id` templates) | **No** | **Yes** — unowned `/etc` survives | chroot promote once; persists across updates |
| Firewall runtime (TFTP conntrack helper, iptables) | n/a (runtime) | **No** — lost on any reboot | Puppet (durable) or re-apply every boot |

> **Portability note.** `nd-systemupdate.sh`, the `.dont` rename, `box1-tNN`, and dates in the
> `EXAMPLE` block are DOSTO-NEU deployment specifics. The btrfs-ro-snapshot + chroot-promote *model*
> is generic to the CCU image.

# The two write modes

### Runtime (non-durable) — btrfs ro-toggle
For a fix you want live *now* (before the next reboot), unlock the root, edit, re-lock:

```bash
sudo btrfs property set / ro false
sudo python3 /var/tmp/fix_obn.py     # or any edit
sudo btrfs property set / ro true
```

This is enough to run `obn update` this session. It is **wiped on the next reboot** — btrfs rolls back.

### Durable — `nd-systemupdate.sh shell` chroot promote
The only path that survives reboot. `nd-systemupdate.sh shell` drops you into a chroot on the **`work`
subvol**; on `exit` it promotes `work → release → new runN` and points GRUB at the new `runN`.

# The `.dont` rename (fleet convention)

`/usr/sbin/nd-systemupdate.sh` is **deliberately renamed to `nd-systemupdate.sh.dont`** on every CCU.
This disables the nightly `nd-auto-system-update.timer` (`OnCalendar=*-*-* 0,1,2,3,4:21:00`) — with the
canonical name gone, the timer's `ExecStart` fails with ENOENT and rearms harmlessly. Puppet *agent*
runs are unaffected.

**Why:** the Puppet env does not yet ship the OBN patches. If the timer fired with the canonical name,
it would pull vanilla OBN, promote a snapshot, reboot the train (GPS-gated to standstill), and **wipe
every hand-applied patch**. So the `.dont` rename is the guard that keeps patched trains patched until
R&D upstreams the fixes.

- Invoke the chroot by its actual filename: `sudo /usr/sbin/nd-systemupdate.sh.dont shell`. The
  canonical `nd-systemupdate.sh` does not exist on a properly-configured CCU.
- If you find a CCU with the **canonical name present** (`.dont` missing), it is *exposed* to the
  nightly auto-update. Re-rename it (`sudo mv …sh …sh.dont`) inside the same chroot before promoting.
- The rename is preserved across promotes (it lives in `/usr/sbin`, which is inside the snapshot lineage).
- Remove the `.dont` **only** after R&D ships the patches into the Puppet env — not before.

# The chroot rules (load-bearing)

### Rule 1 — heredoc, never paste
`…sh.dont shell` opens an **interactive** chroot bash (`chroot ${MOUNT_DIR} bash`). If you paste a
multi-line block (edit + `exit` + reboot) into a plain SSH session, the lines *after* `… shell` queue
in the **parent** shell and run after the chroot exits on EOF. Result: your edit hits the read-only
**live** root (silent no-op), the promote produces no new snapshot, and reboot lands on the OLD subvol.
Symptom: btrfs subvol generations frozen across the reboot, file unchanged.

**Fix:** pipe the in-chroot commands via heredoc into the subcommand's stdin so they run *inside* the chroot:
```bash
sudo /usr/sbin/nd-systemupdate.sh.dont shell <<'CHROOT_EOF'
python3 /var/tmp/fix_obn.py
# ... other edits ...
CHROOT_EOF
```
Success looks like: `PATCHED…` printed, then
`Create a readonly snapshot of '/.snapshots/work' in '/.snapshots/release'` →
`… 'release' in '/.snapshots/runN'` → `Please reboot…`. The `qgroup … Device or resource busy` lines
are benign btrfs quota cleanup, not a failure.

### Rule 2 — stage in `/var/tmp/`, not `/tmp/`
The chroot bind-mounts `/var/tmp` (per `DIR_TO_MOUNT="boot/grub data dev var/cache var/tmp"`) but
**not** `/tmp`. Scripts staged in `/tmp/` are **invisible inside the chroot**. Stage in `/var/tmp/`.
(The `developer` SSH user can't write `/var/tmp` directly — scp to `/tmp`, then `sudo mv` to `/var/tmp`.)
Both `/tmp` and `/var/tmp` are tmpfs → **wiped on reboot**; re-scp scripts after any reboot between
apply and persist.

### Rule 3 — the chroot snapshots from `work`, which can be stale
`…sh.dont shell` snapshots from the **`work` subvol**, which may be *stale* relative to edits you made
on the **live (active `run`) subvol** outside the chroot. If you edit outside the chroot then promote,
the new snapshot can be created **without** your edit → you reboot and it's gone.

**Fix:** re-apply every edit **INSIDE the chroot** before `exit` (via the heredoc). Then verify the new
`runN` snapshot actually contains it before rebooting.

### Rule 4 — verify by subvolume ID, then reboot
Folder names (`run1`, `run2`, …) **recycle** and the new slot is not monotonic — a promote from `run2`
can land on `run1`. Never identify the new snapshot by name; resolve it and verify before committing
the reboot. Pre-reboot gate (all four must agree):

```bash
# a) generations of work/release/runN moved
sudo btrfs subvolume get-default /          # b) == the new runN's ID
# c) GRUB saved_entry maps to that runN's menuentry
# d) read the edited file straight out of the runN snapshot:
NEW=$(sudo btrfs subvolume list / | grep snapshots/run | sort -k2 -n | tail -1 | awk '{print $NF}')
sudo mount -o subvol=$NEW,ro /dev/sda2 /mnt/chk
sudo grep -c "NDP-PATCH-BUG10-BFS-GUARD" /mnt/chk/usr/share/obn/lib/report/report_dosto_neu.py
sudo head -1 /mnt/chk/etc/obn/template/nv6-*.cfg    # train_id directive present?
sudo umount /mnt/chk
```

Only `sudo /usr/local/sbin/safe_reboot` once the new subvol is confirmed to contain the change. If any
check fails, re-enter the chroot and fix — each chroot session creates a fresh `runN`; the broken one
is ignored on next boot (GRUB default is the latest).

The `assert old in content` guards inside the fix scripts are load-bearing: they abort cleanly if run
against the wrong CCU (e.g. a vlan7 IP that doesn't match) — keep them.

# The NDSU update survival model

An NDSU *update* (`…sh.dont up`) = snapshot `work` → apt/Puppet update in chroot → promote. It is **not
a re-image**. What survives:

- **Unowned `/etc` files survive** — the vlan7 nmconnection and `train_id` templates persist (provided
  they were persisted into the subvol lineage via a chroot edit, not left as runtime-only fixes).
- **`/usr/share/obn/**` is dpkg-owned → fully rewritten on any `nd-obn` upgrade** → **all hand-patches
  wiped.** After every `nd-obn` bump you must re-apply the OBN patches that the new package doesn't
  carry natively (on 2.2.23, at minimum Bug 11).
- **The TFTP conntrack helper is runtime-only → lost on any reboot regardless.** See its own doc.

# Proven dead ends — do NOT repeat these

> Approaches tried and disproven on live CCUs.

1. **Do NOT edit `/` and expect it to persist.** The root is a btrfs ro snapshot; a bare edit is rolled
   back on reboot. Use the ro-toggle for runtime, the chroot promote for durable.
2. **Do NOT run `nmcli con mod` / any runtime `/etc` write and call it durable.** On the ro rootfs a
   runtime edit works this session but does not survive; and unless it's captured into the subvol
   lineage it can be lost even across an NDSU update. Persist `/etc` changes through the chroot.
3. **Do NOT paste multi-line chroot commands into an interactive `… shell` session.** Lines after
   `… shell` run in the *parent* shell after the chroot exits, hitting the ro live root — silent no-op,
   no promote, reboot lands on the old subvol. Pipe via heredoc-into-stdin.
4. **Do NOT stage scripts in `/tmp/` for a chroot session.** `/tmp` is not bind-mounted into the chroot;
   the files are invisible. Use `/var/tmp/`.
5. **Do NOT assume `/var/tmp/` scripts survive a reboot.** It's tmpfs. Re-scp between apply and persist
   if a reboot happened in between.
6. **Do NOT edit only outside the chroot and then promote.** The chroot snapshots from the (possibly
   stale) `work` subvol; your outside edit can be dropped from the new snapshot. Re-apply inside the
   chroot before `exit`.
7. **Do NOT identify the new snapshot by folder name.** `run1/run2` slots recycle and don't increment
   monotonically. Resolve and verify by subvolume ID; verify the file content in the mounted `runN`
   *before* `safe_reboot`.
8. **Do NOT remove the `.dont` rename to "re-enable updates" before R&D ships the patches.** The nightly
   timer will promote a vanilla-OBN snapshot and wipe every patch. `.dont` stays until the Puppet env
   carries the fixes.
9. **Do NOT assume `/usr/share/obn` edits survive an `nd-obn` upgrade.** The package rewrites the whole
   tree; re-apply the non-native patches after every bump.

# EXAMPLE (DOSTO NEU) — deployment specifics (NON-portable)

- **Chroot binary:** `/usr/sbin/nd-systemupdate.sh.dont` (canonical `…sh` deliberately absent). Invoke
  `… shell` for a manual promote, `… up` for an update, `… version` to read the Puppet-served target hash.
- **Timer disabled:** `nd-auto-system-update.timer`, `OnCalendar=*-*-* 0,1,2,3,4:21:00`.
- **Chroot bind mounts:** `DIR_TO_MOUNT="boot/grub data dev var/cache var/tmp"` — note `/tmp` absent.
- **Root device / reboot:** `/dev/sda2`; `sudo /usr/local/sbin/safe_reboot`.
- **The `-f` not `-x` gotcha:** the `.dont` file is mode 0500 owner=root; test its existence with
  `[ -f … ]` — `[ -x … ]` returns false for the `developer` SSH user even though `sudo` runs it fine.
- **Evidence:** heredoc-not-paste confirmed on box1-t24 (Fzg 139) 2026-06-16 after two failed
  interactive-paste attempts. work-vs-run stale-subvol confirmed on 4734-112 2026-06-09 (edit outside
  chroot dropped; re-applied inside, verified in `run2`, then rebooted). Survival model verified on
  4736-119 (box1-t12) 2026-06-12 (vlan7 + templates survived an NDSU update; `/usr/share/obn` rewritten,
  Bug 11 re-patched). box1-t1 (Fzg 133) found `.dont`-exposed 2026-05-09.

# Related

- [Nomad Connect / OBN — the 11-bug suite](/.kb/components/nomad-connect-obn/bug-suite.md)
- [Nomad Connect / OBN — TFTP conntrack helper gap](/.kb/components/nomad-connect-obn/tftp-conntrack-helper.md)
- [Nomad Connect / OBN — publish → Puppet pipeline](/.kb/components/nomad-connect-obn/publish-to-puppet-pipeline.md)

# Citations

[1] Memory `project_nd_systemupdate_dont.md` — `.dont` rename rationale, timer, invocation, `/var/tmp` bind mount.
[2] Memory `project_ndsu_chroot_heredoc_not_paste.md` — interactive-paste no-op; heredoc fix; pre-reboot 4-point gate.
[3] Memory `project_chroot_promotes_from_work_subvol.md` — work-vs-run stale-subvol trap; re-apply inside chroot.
[4] Memory `project_ndsu_update_survival_model.md` — unowned `/etc` survives, `/usr/share/obn` rewritten.
[5] `.claude/skills/dosto-obn-patches/SKILL.md` — `--persist` recipe, `/var/tmp` vs `/tmp`, subvol-ID verification, `-f` not `-x`.
