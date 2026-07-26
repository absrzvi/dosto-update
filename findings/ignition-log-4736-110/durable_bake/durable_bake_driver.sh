#!/bin/bash
# durable_bake_driver.sh — run ON the CCU as: sudo bash durable_bake_driver.sh
# Bakes the logger stack into a promoted NDSU snapshot so it survives reboots + NDSU updates.
# Requires: payload already staged in /tmp/logger_payload/ (bind-visible in the chroot).
# Mechanics (verified from nd-systemupdate.sh.dont): shell -> chroot of a fresh snapshot cloned
# from RELEASE; /var/tmp is bind-mounted in; on clean 'exit' the snapshot promotes to release+run
# and becomes default-boot. We pipe the in-chroot commands via STDIN heredoc (interactive paste
# no-ops per NDSU behaviour). NOTE: var/tmp is wiped in the promoted snapshot, so we copy the
# payload to /root/logger_payload INSIDE the chroot first.
set -u
PAY=/tmp/logger_payload
[ -d "$PAY" ] || { echo "MISSING $PAY — stage payload first"; exit 1; }
[ -f "$PAY/bake_in_chroot.sh" ] || { echo "MISSING bake_in_chroot.sh in payload"; exit 1; }

echo "[driver] entering NDSU chroot to bake logger stack into a new snapshot..."
# Feed the chroot shell via stdin. Everything between the markers runs INSIDE the snapshot chroot.
sudo /usr/sbin/nd-systemupdate.sh.dont shell << 'CHROOT'
set -e
mkdir -p /root/logger_payload
cp -a /tmp/logger_payload/. /root/logger_payload/
chmod +x /root/logger_payload/*.sh
bash /root/logger_payload/bake_in_chroot.sh
exit
CHROOT
rc=$?
echo "[driver] chroot exited rc=$rc"
if [ $rc -eq 0 ]; then
  echo "[driver] snapshot promoted. The logger stack is baked into the new default-boot snapshot."
  echo "[driver] It ACTIVATES on the next reboot. Runtime install (if present) keeps it live until then."
  echo "[driver] Verify pending: sudo /usr/sbin/nd-systemupdate.sh.dont version"
else
  echo "[driver] NON-ZERO exit — promote may NOT have happened. Do NOT reboot; investigate."
fi
