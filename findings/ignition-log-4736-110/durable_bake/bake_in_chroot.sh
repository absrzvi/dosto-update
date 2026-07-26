#!/bin/bash
# Runs INSIDE the nd-systemupdate .dont chroot (work subvol, already rw). Lays down the logger
# stack into the snapshot so the promoted release boots with it. Does NOT start services or
# toggle btrfs ro (chroot handles that) and does NOT run the loggers (they start on real boot).
set -u
P=/root/logger_payload   # copied here from /var/tmp before entering (var/tmp is wiped in snapshot)
IGN=/data/ignition-log; NET=/data/netdrop-log
say(){ echo "[bake] $*"; }
[ -d "$P" ] || { echo "MISSING payload $P"; exit 1; }

# NOTE: /data is a SHARED subvol (id 258) mounted across all snapshots — writing scripts there
# from the chroot is fine and they're already present from the runtime install; re-install to be safe.
mkdir -p "$IGN" "$NET"
install -m 0755 "$P/vign_poll.sh"        "$IGN/vign_poll.sh"
install -m 0755 "$P/shutdown_marker.sh"  "$IGN/shutdown_marker.sh"
install -m 0755 "$P/hardcut_classify.sh" "$IGN/hardcut_classify.sh"
install -m 0755 "$P/netdrop_poll.sh"     "$NET/netdrop_poll.sh"
say "payload scripts installed to /data (shared subvol)"

# check scripts + zabbix confs into the SNAPSHOT's /etc + /usr (this is the durable part)
install -m 0755 "$P/check-netdrop.sh" /usr/local/bin/check-netdrop.sh
install -m 0755 "$P/check-hardcut.sh" /usr/local/bin/check-hardcut.sh
install -m 0644 "$P/check_netdrop.conf" /etc/zabbix/zabbix_agentd.conf.d/check_netdrop.conf
install -m 0644 "$P/check_hardcut.conf" /etc/zabbix/zabbix_agentd.conf.d/check_hardcut.conf
say "check scripts + zabbix confs baked into snapshot /etc + /usr/local"

# systemd units into the snapshot
cat > /etc/systemd/system/vign-logger.service << 'U'
[Unit]
Description=DOSTO CCU ignition/supply (Vin/Vign) logger via CMM I2C
After=multi-user.target
[Service]
Type=simple
ExecStart=/data/ignition-log/vign_poll.sh
Restart=always
RestartSec=5
Nice=10
[Install]
WantedBy=multi-user.target
U
cat > /etc/systemd/system/vign-shutdown-marker.service << 'U'
[Unit]
Description=DOSTO CCU graceful-shutdown breadcrumb to /data (hard-cut vs clean-stop discriminator)
DefaultDependencies=no
Before=shutdown.target umount.target final.target
Conflicts=reboot.target
After=network.target
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStop=/data/ignition-log/shutdown_marker.sh
[Install]
WantedBy=multi-user.target
U
install -m 0644 "$P/netdrop-poll.service"        /etc/systemd/system/netdrop-poll.service
install -m 0644 "$P/nd-hardcut-classify.service" /etc/systemd/system/nd-hardcut-classify.service
say "systemd units baked into snapshot"

# enable units in the snapshot (creates .wants symlinks under the snapshot's /etc — durable)
systemctl --root=/ enable vign-logger.service vign-shutdown-marker.service netdrop-poll.service nd-hardcut-classify.service 2>&1 | sed 's/^/[enable] /'
# fallback if systemctl --root fails inside chroot: create symlinks by hand
for u in vign-logger vign-shutdown-marker netdrop-poll nd-hardcut-classify; do
  ln -sf "/etc/systemd/system/$u.service" "/etc/systemd/system/multi-user.target.wants/$u.service" 2>/dev/null
done
say "units enabled in snapshot (symlinks under multi-user.target.wants)"

echo "===== BAKE VERIFY (in snapshot) ====="
ls -l /etc/systemd/system/multi-user.target.wants/ | grep -E "vign|netdrop|hardcut" || echo "  WARN no wants symlinks"
ls -l /etc/zabbix/zabbix_agentd.conf.d/check_netdrop.conf /etc/zabbix/zabbix_agentd.conf.d/check_hardcut.conf
ls -l /usr/local/bin/check-netdrop.sh /usr/local/bin/check-hardcut.sh
echo "===== BAKE DONE — exit chroot to promote ====="
