#!/usr/bin/env bash
#
# apply_ccu_runtime_fixes.sh — apply the CCU runtime firewall/kernel fixes that
# AP firmware batch pushes need, in ONE self-contained, idempotent run.
#
# This is the RUNTIME companion to apply_all_obn_patches.py. It is a DELIBERATELY
# SEPARATE script because these fixes are a different KIND of thing:
#
#   * apply_all_obn_patches.py edits /usr/share/obn/*.py  -> FILESYSTEM state,
#     persists into a btrfs snapshot via the nd-systemupdate chroot.
#
#   * THIS script loads a kernel module + adds a live iptables rule + sets two
#     sysctls -> RUNTIME state. It is WIPED ON EVERY REBOOT and CANNOT be
#     persisted by the chroot (a live iptables rule is not filesystem state, and
#     the firewall chain is rebuilt from Puppet at boot anyway).
#
#     The only durable home for these is Puppet (60-allow-management), owned by
#     R&D under TRIAG-8585 (infra section). Until that ships, RE-RUN THIS SCRIPT
#     AFTER EVERY CCU REBOOT, before any `obn update f ap` batch.
#
# ------------------------------------------------------------------------------
# WHAT IT FIXES
# ------------------------------------------------------------------------------
#   Fix A — nf_conntrack_tftp helper gap
#           TFTP is two-flow: AP sends RRQ to udp/69; the CCU replies with DATA
#           from a random high port. Without the conntrack helper + a CT rule on
#           udp/69, the return flow isn't seen as RELATED and dies at INPUT DROP.
#           Symptom: `obn update f ap` batch -> ~5/15 succeed by conntrack-race
#           luck, the rest silently fail while OBN reports "Successful".
#           Fix: modprobe nf_conntrack_tftp + raw-PREROUTING CT --helper rule.
#
#   Fix B — UDP conntrack timeout too short for concurrent batches
#           Even WITH the helper, a full fan-out batch (e.g. 16 x ~100MB TFTP)
#           stalls each flow >30s; the default 30s UDP conntrack timeout expires
#           entries mid-transfer -> `in.tftpd: read(ack): Connection refused`,
#           AP reads rpcFwFlash=-1. Bumping the timeouts widens the window.
#           (Confirmed box1-t54 / 4734-190, 2026-06-09.)
#           NOTE: the standing operational rule is still single-AP / small-batch
#           serial pushes (CLAUDE.md handoff-lesson 11). This bump is a safety
#           margin, NOT a licence to full-fan-out.
#
# ------------------------------------------------------------------------------
# HOW TO USE
# ------------------------------------------------------------------------------
#   scp -i <openssh-key> apply_ccu_runtime_fixes.sh developer@<ccu-ip>:/tmp/
#   ssh -i <openssh-key> developer@<ccu-ip> 'sudo bash /tmp/apply_ccu_runtime_fixes.sh'
#
#   Flags:
#     --check    verify only; report state, change nothing, exit
#     -h|--help  this header
#
# Exit codes: 0 = all fixes present (after apply, or already present in --check)
#             2 = --check found something missing
#             1 = error (not root, wrong host, etc.)
# ------------------------------------------------------------------------------
set -u

CHECK_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK_ONLY=1 ;;
    -h|--help) sed -n '2,60p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg (use --check or --help)" >&2; exit 1 ;;
  esac
done

# ---- sanity ------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root (use sudo)." >&2
  exit 1
fi
if ! command -v iptables >/dev/null 2>&1; then
  echo "ERROR: iptables not found — is this a CCU?" >&2
  exit 1
fi

# The CT-helper rule comment — also our idempotency marker.
RULE_COMMENT="TFTP conntrack helper for in.tftpd (runtime fix apply_ccu_runtime_fixes.sh — Puppet TBD)"

TIMEOUT_TARGET=180
TIMEOUT_STREAM_TARGET=600

# ---- detectors (used by both check and apply) --------------------------------
module_loaded()   { lsmod 2>/dev/null | grep -q '^nf_conntrack_tftp'; }
ct_rule_present() { iptables -t raw -L PREROUTING -n -v 2>/dev/null | grep -qiE 'helper tftp|CT .*tftp'; }
udp_timeout()        { sysctl -n net.netfilter.nf_conntrack_udp_timeout 2>/dev/null || echo "?"; }
udp_timeout_stream() { sysctl -n net.netfilter.nf_conntrack_udp_timeout_stream 2>/dev/null || echo "?"; }
backend_is_nft()  { iptables --version 2>/dev/null | grep -qi 'nf_tables'; }

report() {
  echo "Current CCU runtime-fix state on $(hostname):"
  if module_loaded;   then echo "  [OK ] nf_conntrack_tftp module loaded";
                      else echo "  [!! ] nf_conntrack_tftp module NOT loaded"; fi
  if ct_rule_present; then echo "  [OK ] CT --helper tftp rule present on raw/PREROUTING udp/69";
                      else echo "  [!! ] CT --helper tftp rule MISSING on raw/PREROUTING udp/69"; fi
  local t ts; t=$(udp_timeout); ts=$(udp_timeout_stream)
  if [ "$t" != "?" ] && [ "$t" -ge "$TIMEOUT_TARGET" ] 2>/dev/null; then
    echo "  [OK ] nf_conntrack_udp_timeout = ${t}s (>= ${TIMEOUT_TARGET})";
  else echo "  [!! ] nf_conntrack_udp_timeout = ${t}s (want >= ${TIMEOUT_TARGET})"; fi
  if [ "$ts" != "?" ] && [ "$ts" -ge "$TIMEOUT_STREAM_TARGET" ] 2>/dev/null; then
    echo "  [OK ] nf_conntrack_udp_timeout_stream = ${ts}s (>= ${TIMEOUT_STREAM_TARGET})";
  else echo "  [!! ] nf_conntrack_udp_timeout_stream = ${ts}s (want >= ${TIMEOUT_STREAM_TARGET})"; fi
  if backend_is_nft; then
    echo "  [??] iptables backend is nf_tables — CT --helper via iptables MAY be a silent no-op."
    echo "       If a batch still fails with the rule 'present', verify the helper actually"
    echo "       attaches: 'cat /proc/net/nf_conntrack_expect' during a live RRQ should populate."
    echo "       If empty, the native-nft path is needed (see dosto-tftp-helper-check SKILL.md)."
  fi
}

all_present() {
  module_loaded && ct_rule_present || return 1
  local t ts; t=$(udp_timeout); ts=$(udp_timeout_stream)
  [ "$t" != "?" ] && [ "$t" -ge "$TIMEOUT_TARGET" ] 2>/dev/null || return 1
  [ "$ts" != "?" ] && [ "$ts" -ge "$TIMEOUT_STREAM_TARGET" ] 2>/dev/null || return 1
  return 0
}

# ---- check mode --------------------------------------------------------------
if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "CCU runtime-fix check (read-only):"
  echo ""
  report
  echo ""
  if all_present; then
    echo "  => all runtime fixes present (this boot). Remember: NOT persistent — re-run after reboot."
    exit 0
  else
    echo "  => one or more runtime fixes MISSING. Run without --check to apply."
    exit 2
  fi
fi

# ---- apply mode --------------------------------------------------------------
echo "Applying CCU runtime firewall/kernel fixes (idempotent)."
echo "  *** RUNTIME ONLY — these are WIPED ON REBOOT and CANNOT be persisted by"
echo "      the nd-systemupdate chroot. Re-run after every CCU reboot until the"
echo "      Puppet fix (60-allow-management, TRIAG-8585) ships. ***"
echo ""

# Fix A.1 — kernel module
if module_loaded; then
  echo "  Fix A.1 nf_conntrack_tftp module: ALREADY LOADED"
else
  if modprobe nf_conntrack_tftp 2>/tmp/_mp_err; then
    echo "  Fix A.1 nf_conntrack_tftp module: LOADED"
  else
    echo "  Fix A.1 nf_conntrack_tftp module: FAILED — $(cat /tmp/_mp_err)"
    echo "         (kernel image may be missing the module — escalate to R&D)"
  fi
fi

# Fix A.2 — CT helper rule on raw/PREROUTING udp/69.
# Insert at TOP (-I), not append (-A): ordering can matter under nft compat.
if ct_rule_present; then
  echo "  Fix A.2 CT --helper tftp rule: ALREADY PRESENT"
else
  if iptables -t raw -I PREROUTING -p udp --dport 69 -j CT --helper tftp \
       -m comment --comment "$RULE_COMMENT" 2>/tmp/_ipt_err; then
    echo "  Fix A.2 CT --helper tftp rule: ADDED"
  else
    echo "  Fix A.2 CT --helper tftp rule: FAILED — $(cat /tmp/_ipt_err)"
  fi
fi

# Fix B — UDP conntrack timeouts (idempotent; sysctl -w is a set, always safe).
cur_t=$(udp_timeout)
if [ "$cur_t" != "?" ] && [ "$cur_t" -ge "$TIMEOUT_TARGET" ] 2>/dev/null; then
  echo "  Fix B.1 nf_conntrack_udp_timeout: ALREADY ${cur_t}s (>= ${TIMEOUT_TARGET})"
else
  sysctl -w net.netfilter.nf_conntrack_udp_timeout=${TIMEOUT_TARGET} >/dev/null 2>&1 \
    && echo "  Fix B.1 nf_conntrack_udp_timeout: SET ${cur_t}s -> ${TIMEOUT_TARGET}s" \
    || echo "  Fix B.1 nf_conntrack_udp_timeout: FAILED to set"
fi
cur_ts=$(udp_timeout_stream)
if [ "$cur_ts" != "?" ] && [ "$cur_ts" -ge "$TIMEOUT_STREAM_TARGET" ] 2>/dev/null; then
  echo "  Fix B.2 nf_conntrack_udp_timeout_stream: ALREADY ${cur_ts}s (>= ${TIMEOUT_STREAM_TARGET})"
else
  sysctl -w net.netfilter.nf_conntrack_udp_timeout_stream=${TIMEOUT_STREAM_TARGET} >/dev/null 2>&1 \
    && echo "  Fix B.2 nf_conntrack_udp_timeout_stream: SET ${cur_ts}s -> ${TIMEOUT_STREAM_TARGET}s" \
    || echo "  Fix B.2 nf_conntrack_udp_timeout_stream: FAILED to set"
fi

echo ""
report
echo ""
if all_present; then
  echo "  => all runtime fixes present. Safe to attempt an AP firmware push."
  echo "     (Still prefer single-AP / small-batch serial — handoff lesson 11.)"
  echo "     Verify a real transfer: 'journalctl -u tftpd-hpa -f' during one push;"
  echo "     the tftp_allowed byte counter should grow by ~6-8 MB per AP image."
  RC=0
else
  echo "  => NOT all fixes present after apply — review the FAILED lines above."
  if backend_is_nft; then
    echo "     nf_tables backend: the CT --helper rule may be a silent no-op. See the"
    echo "     native-nft workaround in dosto-tftp-helper-check SKILL.md section 4."
  fi
  RC=2
fi

echo ""
echo "  REMINDER: runtime only. After the next reboot, re-run this script before"
echo "            any AP firmware batch. Durable fix = Puppet (TRIAG-8585)."
exit $RC
