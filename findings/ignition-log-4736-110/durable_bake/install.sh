#!/bin/bash
# Idempotent logger-stack installer for DOSTO MAR5 CCU. Run as: sudo bash -s < install.sh
# Payload staged in /tmp/logger_deploy/. Installs: netdrop logger, power logger (10s),
# shutdown-marker, hardcut classifier, Zabbix UserParameters. Enables units while / is rw.
set -u
P=/tmp/logger_deploy
IGN=/data/ignition-log
NET=/data/netdrop-log
say(){ echo "[install] $*"; }

[ -d "$P" ] || { echo "MISSING $P"; exit 1; }

# --- 1. payload scripts to /data (data subvol is always writable, survives reboot) ---
mkdir -p "$IGN" "$NET"
install -m 0755 "$P/vign_poll.sh"        "$IGN/vign_poll.sh"
install -m 0755 "$P/shutdown_marker.sh"  "$IGN/shutdown_marker.sh"
install -m 0755 "$P/hardcut_classify.sh" "$IGN/hardcut_classify.sh"
install -m 0755 "$P/netdrop_poll.sh"     "$NET/netdrop_poll.sh"
say "payload scripts installed to /data"

# --- 2. check scripts to /usr/local/bin (needs / rw) + zabbix confs to /etc (needs / rw) ---
ROWAS=$(btrfs property get -ts / ro 2>/dev/null | grep -oE 'true|false')
say "root subvol ro=$ROWAS ; toggling rw for /etc + /usr writes"
btrfs property set -ts / ro false 2>/dev/null || { echo "FAILED ro-toggle"; exit 1; }

install -m 0755 "$P/check-netdrop.sh" /usr/local/bin/check-netdrop.sh
install -m 0755 "$P/check-hardcut.sh" /usr/local/bin/check-hardcut.sh
install -m 0644 "$P/check_netdrop.conf" /etc/zabbix/zabbix_agentd.conf.d/check_netdrop.conf
install -m 0644 "$P/check_hardcut.conf" /etc/zabbix/zabbix_agentd.conf.d/check_hardcut.conf
say "check scripts + zabbix confs installed"

# --- 3. systemd units to /etc/systemd/system (needs / rw). Written inline (canonical from 110). ---
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
say "systemd units installed"

# --- 4. enable units WHILE / IS WRITABLE (the .wants symlink lives under /etc) ---
systemctl daemon-reload
systemctl enable vign-logger.service vign-shutdown-marker.service netdrop-poll.service nd-hardcut-classify.service 2>&1 | sed 's/^/[enable] /'
say "units enabled"

# --- 5. close / back to ro ---
btrfs property set -ts / ro true 2>/dev/null || say "WARN: could not re-close ro (non-fatal)"
say "root subvol ro re-closed"

# --- 6. start the loggers now ---
systemctl start vign-logger.service vign-shutdown-marker.service netdrop-poll.service
# classifier is oneshot-at-boot; run it once now so a state file exists
systemctl start nd-hardcut-classify.service 2>/dev/null || true
say "loggers started"

# --- 7. reload zabbix agent so it picks up the new UserParameters ---
# Restart whichever agent is ACTIVE (some CCUs have both units present but only one running;
# blindly restarting agent2 "succeeds" with exit 0 even when the CLASSIC agent is the live one,
# leaving the UserParameters unloaded -> item shows "Unsupported item key". So restart by active state.
restarted=0
for u in zabbix-agent2 zabbix-agent; do
  if systemctl is-active --quiet "$u"; then systemctl restart "$u" && { say "restarted active agent: $u"; restarted=1; }; fi
done
[ "$restarted" = 0 ] && say "WARN: no ACTIVE zabbix-agent unit found to restart"
say "zabbix agent reloaded"

# --- 8. verify ---
sleep 8
echo "===== VERIFY ====="
echo "-- units --"; systemctl is-active vign-logger vign-shutdown-marker netdrop-poll nd-hardcut-classify 2>/dev/null | paste -sd' '
echo "-- vign.csv tail --"; tail -2 "$IGN/vign.csv" 2>/dev/null || echo "  (no vign.csv yet)"
echo "-- netdrop.csv tail --"; tail -2 "$NET/netdrop.csv" 2>/dev/null || echo "  (no netdrop.csv yet)"
echo "-- hardcut-state --"; cat "$IGN/hardcut-state.json" 2>/dev/null || echo "  (no state yet)"
echo "-- UserParameter probes (as agent would call) --"
echo "check_netdrop_stadler = $(/usr/local/bin/check-netdrop.sh 2>&1)"
echo "check_hardcut_total   = $(/usr/local/bin/check-hardcut.sh total 2>&1)"
echo "===== DONE ====="
