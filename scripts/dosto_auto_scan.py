#!/usr/bin/env python3
"""
DOSTO auto-scanner — single-train validation stub (Phase i).

Implements Tier 1 (reachability + lightweight state probe) for one train,
plus the file-write mechanics with strict allowlist enforcement on
fleet-status.md and append-only writes on cable-issues-register.md.

Tier 2 is not implemented in this stub. Use --inject-test-signal to
exercise the cable-register draft path without needing a real fault.

Contract: .claude/contracts/auto-scanner-boundary.md
Skill spec: .claude/skills/dosto-auto-scan/SKILL.md

Usage:
  python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1
  python scripts/dosto_auto_scan.py --fzg 132 --ccu-ip 10.179.10.1 \\
      --inject-test-signal "missing_ap=.240/lldp=D3.e1-4"
  python scripts/dosto_auto_scan.py --status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SSH_KEY = REPO_ROOT / "openssh"
STATE_DIR = REPO_ROOT / ".claude" / "state"
LOGS_DIR = REPO_ROOT / ".claude" / "logs"
FLEET_STATUS = REPO_ROOT / "fleet-status.md"
CABLE_REGISTER = REPO_ROOT / "cable-issues-register.md"
STATE_FILE = REPO_ROOT / "auto-scan-state.json"
LOCKFILE = STATE_DIR / "auto-scan.lock"
ORCHESTRATOR_LOCK = STATE_DIR / "orchestrator.lock"
ERRORS_LOG = LOGS_DIR / "auto-scan-errors.jsonl"

ALLOWED_FLEET_COLUMNS = {"Last reachable", "Last auto-scan", "Auto-detected issues"}
DEBOUNCE_SCANS = 3
LOCK_STALE_SECONDS = 60 * 60  # orchestrator lock considered stale after 60 min


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utcnow_short() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def log_error(kind: str, **fields) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"utc": utcnow_iso(), "kind": kind, **fields}
    with ERRORS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ─── Lock handling ───────────────────────────────────────────────────────────

def take_lock() -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCKFILE.exists():
        age = time.time() - LOCKFILE.stat().st_mtime
        if age < LOCK_STALE_SECONDS:
            return False
    LOCKFILE.write_text(f"pid={os.getpid()} utc={utcnow_iso()}\n")
    return True


def release_lock() -> None:
    if LOCKFILE.exists():
        LOCKFILE.unlink()


def orchestrator_active() -> bool:
    if not ORCHESTRATOR_LOCK.exists():
        return False
    age = time.time() - ORCHESTRATOR_LOCK.stat().st_mtime
    return age < LOCK_STALE_SECONDS


# ─── State file ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "schema_version": 1,
            "last_full_scan_utc": None,
            "trains": {},
            "scan_history": [],
            "thresholds": {"debounce_scans": DEBOUNCE_SCANS, "crc_high_threshold": 100},
        }
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ─── Tier 1 — reachability + lightweight state probe ────────────────────────

def tcp_reachable(ip: str, port: int = 22, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def ssh_probe(ip: str, command: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a single SSH command on the CCU. Returns (rc, stdout, stderr)."""
    cmd = [
        "ssh",
        "-i", str(SSH_KEY),
        "-o", "StrictHostKeyChecking=no",
        "-o", "BatchMode=yes",
        "-o", f"ConnectTimeout={timeout}",
        f"developer@{ip}",
        command,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "ssh timeout"


def lightweight_state_probe(ip: str) -> dict:
    """
    Stub for the Tier-1 state probe. The full version delegates to
    /dosto-state-inventory; this stub captures the 4 cheapest facts in
    one SSH heredoc to validate the SSH path works end-to-end.
    """
    heredoc = (
        "echo '=== uptime ==='; uptime; "
        "echo '=== hostname ==='; hostname; "
        "echo '=== vlan7 ==='; ip -br addr show vlan7 2>/dev/null || echo 'NO_VLAN7'; "
        "echo '=== ndsu ==='; "
        "if [ -f /usr/sbin/nd-systemupdate.sh.dont ]; then echo dont; "
        "elif [ -f /usr/sbin/nd-systemupdate.sh ]; then echo canonical; "
        "else echo MISSING; fi"
    )
    rc, stdout, stderr = ssh_probe(ip, heredoc)
    if rc != 0:
        return {"ok": False, "rc": rc, "stderr": stderr.strip()[:200]}
    return {"ok": True, "raw": stdout, "captured_at_utc": utcnow_iso()}


# ─── Signal hashing ──────────────────────────────────────────────────────────

def hash_signal(fzg: int, kind: str, **fields) -> str:
    payload = f"fzg={fzg}/{kind}/" + "/".join(f"{k}={v}" for k, v in sorted(fields.items()))
    short = hashlib.sha1(payload.encode()).hexdigest()[:10]
    return f"{payload}#{short}"


# ─── fleet-status.md write — allowlisted columns only ───────────────────────

class AllowlistViolation(Exception):
    pass


def parse_fleet_table(content: str) -> dict:
    """
    Locate the fleet table header and rows. Returns:
      {"headers": [...], "header_line_idx": N, "rows": [(line_idx, train_number, cells), ...]}
    Caller passes file content split into lines; we operate on indices.

    Post-2026-05-22 schema: tables are `| Train# | Fzg | CCU IP | ... |`. Rows are keyed
    by Train# (first cell). Old code keyed by Fzg in col 0 — now Fzg is in col 1.
    """
    lines = content.split("\n")
    headers: list[str] = []
    header_idx = -1
    rows: list[tuple[int, str, list[str]]] = []

    for i, line in enumerate(lines):
        if line.strip().startswith("| Train#") and "|" in line[6:]:
            headers = [h.strip() for h in line.strip().strip("|").split("|")]
            header_idx = i
            continue
        if header_idx >= 0 and i > header_idx + 1 and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # Train# format is NNNN-NNN (e.g. 4736-104)
            if cells and re.match(r'^\d{4}-\d{3}$', cells[0]):
                rows.append((i, cells[0], cells))
            elif cells and cells[0].startswith("---"):
                continue
            else:
                if rows:
                    break

    return {"headers": headers, "header_line_idx": header_idx, "rows": rows, "lines": lines}


def update_fleet_row(train_number: str, updates: dict, dry_run: bool = False) -> str:
    """
    Update allowlisted cells for one Train# row. Atomic write with mtime guard.
    Returns one of: 'applied', 'no_changes', 'train_not_found',
    'columns_missing', 'conflict', 'allowlist_violation'.

    Post-2026-05-22 schema: row key is Train# (col 0), not Fzg.
    """
    forbidden = set(updates) - ALLOWED_FLEET_COLUMNS
    if forbidden:
        log_error("fleet_status_allowlist_violation_caller", forbidden=list(forbidden))
        raise AllowlistViolation(f"caller passed forbidden columns: {forbidden}")

    for attempt in range(3):
        if not FLEET_STATUS.exists():
            return "train_not_found"
        read_mtime = FLEET_STATUS.stat().st_mtime
        content = FLEET_STATUS.read_text(encoding="utf-8")
        parsed = parse_fleet_table(content)

        missing_cols = [c for c in updates if c not in parsed["headers"]]
        if missing_cols:
            return "columns_missing"

        target_row = next((r for r in parsed["rows"] if r[1] == train_number), None)
        if target_row is None:
            return "train_not_found"

        line_idx, _, cells = target_row
        new_cells = list(cells)
        changed = False
        for col, value in updates.items():
            col_idx = parsed["headers"].index(col)
            if col_idx < len(new_cells) and new_cells[col_idx] != value:
                new_cells[col_idx] = value
                changed = True

        if not changed:
            return "no_changes"

        new_line = "| " + " | ".join(new_cells) + " |"
        new_lines = list(parsed["lines"])
        new_lines[line_idx] = new_line
        new_content = "\n".join(new_lines)

        # Cheap allowlist sanity: diff lines and confirm only the target line changed
        old_lines = parsed["lines"]
        diff_idx = [i for i in range(len(old_lines)) if old_lines[i] != new_lines[i]]
        if diff_idx != [line_idx]:
            log_error("fleet_status_unexpected_diff", diff_idx=diff_idx, target=line_idx)
            raise AllowlistViolation("write would change unexpected lines")

        if dry_run:
            return "applied (dry-run)"

        if FLEET_STATUS.stat().st_mtime != read_mtime:
            time.sleep(0.5)
            continue  # retry

        tmp = FLEET_STATUS.with_suffix(".md.tmp")
        tmp.write_text(new_content, encoding="utf-8")
        tmp.replace(FLEET_STATUS)
        return "applied"

    log_error("fleet_status_write_conflict", fzg=fzg)
    return "conflict"


# ─── cable-issues-register.md — append-only auto-detected rows ──────────────

def parse_register_rows(content: str) -> list[dict]:
    """Parse register markdown into a list of {row_num, status, hash, line_start, line_end}."""
    rows: list[dict] = []
    lines = content.split("\n")
    current: dict = {}
    line_start = -1

    for i, line in enumerate(lines):
        m = re.match(r"^## Row #(\d+)", line)
        if m:
            if current:
                current["line_end"] = i - 1
                rows.append(current)
            current = {"row_num": int(m.group(1)), "line_start": i, "status": None, "hash": None}
            line_start = i
        elif line.startswith("**Status:**") and current:
            current["status"] = line.split("**Status:**", 1)[1].strip()
        elif line.startswith("**Signal hash:**") and current:
            m2 = re.search(r"`([^`]+)`", line)
            if m2:
                current["hash"] = m2.group(1)

    if current:
        current["line_end"] = len(lines) - 1
        rows.append(current)
    return rows


def highest_row_num() -> int:
    if not CABLE_REGISTER.exists():
        return 0
    rows = parse_register_rows(CABLE_REGISTER.read_text(encoding="utf-8"))
    return max((r["row_num"] for r in rows), default=0)


def find_row_by_hash(signal_hash: str) -> dict | None:
    if not CABLE_REGISTER.exists():
        return None
    rows = parse_register_rows(CABLE_REGISTER.read_text(encoding="utf-8"))
    return next((r for r in rows if r["hash"] == signal_hash), None)


def append_register_row(fzg: int, train_num: str, signal: dict, dry_run: bool = False) -> str:
    """
    Append a new Status: auto-detected row. Caller has verified scan_count >= debounce.
    Returns 'appended' or 'appended (dry-run)'.
    """
    row_num = highest_row_num() + 1
    now = utcnow_short()

    block = f"""---

## Row #{row_num} — auto-detected {now} UTC

**Status:** auto-detected
**Train:** Fzg {fzg} / {train_num}
**Signal source:** {signal['source']}
**Signal hash:** `{signal['hash']}`
**First seen:** {signal['first_seen']}
**Last seen:** {now} UTC (scan #{signal['scan_count']})
**Localisation:** {signal['localisation']}
**Suggested category:** {signal['category']}
**Stadler instructions:** _(engineer to fill before promoting to confirmed)_
**Engineer notes:** _(none yet)_
"""

    if dry_run:
        print(f"[dry-run] would append {len(block.splitlines())} lines to cable-issues-register.md:")
        print(block)
        return "appended (dry-run)"

    if CABLE_REGISTER.exists():
        existing = CABLE_REGISTER.read_text(encoding="utf-8")
        if not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + block
    else:
        new_content = "# Cable issues register\n" + block

    tmp = CABLE_REGISTER.with_suffix(".md.tmp")
    tmp.write_text(new_content, encoding="utf-8")
    tmp.replace(CABLE_REGISTER)
    return "appended"


# ─── Cycle driver ────────────────────────────────────────────────────────────

def run_cycle(args) -> dict:
    if orchestrator_active():
        log_error("cycle_skipped", reason="orchestrator_active")
        return {"status": "skipped", "reason": "orchestrator_active"}

    if not take_lock():
        log_error("cycle_skipped", reason="lock_taken")
        return {"status": "skipped", "reason": "lock_taken"}

    try:
        return _run_cycle_inner(args)
    finally:
        release_lock()


def _run_cycle_inner(args) -> dict:
    state = load_state()
    fzg_str = str(args.fzg)
    train = state["trains"].setdefault(fzg_str, {
        "ccu_ip": args.ccu_ip,
        "last_reachable_utc": None,
        "consecutive_unreachable_scans": 0,
        "active_signals": {},
    })
    train["ccu_ip"] = args.ccu_ip

    summary = {"fzg": args.fzg, "ccu_ip": args.ccu_ip}

    # Tier 1 — reachability
    reachable = tcp_reachable(args.ccu_ip)
    summary["reachable"] = reachable

    fleet_updates: dict[str, str] = {}
    if reachable:
        train["last_reachable_utc"] = utcnow_iso()
        train["consecutive_unreachable_scans"] = 0
        fleet_updates["Last reachable"] = utcnow_short()

        probe = lightweight_state_probe(args.ccu_ip)
        summary["state_probe_ok"] = probe.get("ok", False)
        if probe.get("ok"):
            train["last_state_probe_utc"] = probe["captured_at_utc"]
        else:
            log_error("state_probe_failed", fzg=args.fzg, ip=args.ccu_ip,
                      rc=probe.get("rc"), stderr=probe.get("stderr"))
    else:
        train["consecutive_unreachable_scans"] += 1
        summary["state_probe_ok"] = False

    # Inject test signal (validation path for Tier 2 cable-register write)
    if args.inject_test_signal:
        signal = parse_test_signal(args.fzg, args.inject_test_signal)
        result = process_high_signal(args.fzg, args.train_num, signal, train, args.dry_run)
        summary["test_signal"] = result
    else:
        summary["test_signal"] = None

    # Recompute "Auto-detected issues" count for this Fzg
    auto_count = count_auto_detected_for_fzg(args.fzg)
    if auto_count is not None:
        fleet_updates["Auto-detected issues"] = str(auto_count) if auto_count else "—"

    if fleet_updates:
        write_result = update_fleet_row(args.train_num, fleet_updates, dry_run=args.dry_run)
        summary["fleet_status_write"] = write_result
    else:
        summary["fleet_status_write"] = "no_updates"

    # Persist state
    state["last_full_scan_utc"] = utcnow_iso()
    state["scan_history"].append({
        "utc": utcnow_iso(), "fzg": args.fzg, "reachable": reachable,
        "duration_seconds": None,
    })
    state["scan_history"] = state["scan_history"][-100:]  # cap
    # State (auto-scan-state.json) always persists — it tracks scan_count for
    # debounce. --dry-run only suppresses fleet-status.md / cable-register writes.
    save_state(state)

    summary["status"] = "ok"
    return summary


def parse_test_signal(fzg: int, spec: str) -> dict:
    """Parse 'missing_ap=.240/lldp=D3.e1-4' → structured signal."""
    parts = dict(p.split("=", 1) for p in spec.split("/") if "=" in p)
    if "missing_ap" in parts:
        ap = parts["missing_ap"]
        lldp = parts.get("lldp", "unknown")
        return {
            "source": "dosto-device-discovery (test injection)",
            "kind": "missing_device",
            "hash": hash_signal(fzg, "missing_device", role=f"AP_{ap}", lldp_port=lldp),
            "localisation": f"AP {ap} not in DHCP leases; last LLDP neighbour at switch {lldp}",
            "category": "missing AP — likely cable fault",
        }
    raise ValueError(f"unknown test signal spec: {spec}")


def process_high_signal(fzg: int, train_num: str, signal: dict, train_state: dict, dry_run: bool) -> dict:
    h = signal["hash"]
    active = train_state["active_signals"]

    existing_row = find_row_by_hash(h)
    if existing_row and existing_row["status"] == "confirmed":
        if h in active:
            active[h]["register_status"] = "confirmed"
        return {"action": "already_confirmed", "row": existing_row["row_num"]}

    sig_state = active.setdefault(h, {
        "first_seen_utc": utcnow_iso(),
        "scan_count": 0,
        "register_row": None,
        "register_status": None,
    })
    sig_state["scan_count"] += 1
    sig_state["last_seen_utc"] = utcnow_iso()

    if existing_row and existing_row["status"] == "auto-detected":
        sig_state["register_row"] = existing_row["row_num"]
        sig_state["register_status"] = "auto-detected"
        # In a fuller impl we'd bump 'Last seen' on the row in-place.
        return {"action": "bumped_existing_auto_detected", "row": existing_row["row_num"]}

    if sig_state["scan_count"] < DEBOUNCE_SCANS:
        return {"action": "debouncing", "scan_count": sig_state["scan_count"], "needed": DEBOUNCE_SCANS}

    signal["first_seen"] = sig_state["first_seen_utc"]
    signal["scan_count"] = sig_state["scan_count"]
    result = append_register_row(fzg, train_num, signal, dry_run=dry_run)
    if not dry_run:
        sig_state["register_row"] = highest_row_num()
        sig_state["register_status"] = "auto-detected"
    return {"action": result, "scan_count": sig_state["scan_count"]}


def count_auto_detected_for_fzg(fzg: int) -> int | None:
    if not CABLE_REGISTER.exists():
        return None
    rows = parse_register_rows(CABLE_REGISTER.read_text(encoding="utf-8"))
    count = 0
    for r in rows:
        if r["status"] != "auto-detected":
            continue
        # Check the Train: line within the row block to match Fzg
        # Cheap approach: scan source content for Train: Fzg <fzg>
        pass
    # Stub: return total auto-detected count for now; per-Fzg filtering deferred to full build
    return sum(1 for r in rows if r["status"] == "auto-detected")


# ─── Status mode ─────────────────────────────────────────────────────────────

def cmd_status() -> dict:
    state = load_state()
    return {
        "last_full_scan_utc": state.get("last_full_scan_utc"),
        "trains_tracked": list(state.get("trains", {}).keys()),
        "scan_history_recent": state.get("scan_history", [])[-5:],
        "lockfile_present": LOCKFILE.exists(),
        "orchestrator_lock_present": ORCHESTRATOR_LOCK.exists(),
    }


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="DOSTO auto-scanner (single-train stub)")
    ap.add_argument("--train-num", "--train-number", dest="train_num",
                    help="Train number, primary identifier (e.g. 4736-104)")
    ap.add_argument("--ccu-ip", help="CCU IP address")
    ap.add_argument("--fzg", type=int, default=None,
                    help="Optional Fzg ID override. If omitted, the scanner reads it from "
                         "the fleet-status row for --train-num.")
    ap.add_argument("--inject-test-signal", help="Test signal spec, e.g. 'missing_ap=.240/lldp=D3.e1-4'")
    ap.add_argument("--dry-run", action="store_true", help="Preview writes without applying")
    ap.add_argument("--status", action="store_true", help="Print scanner state, no probes")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    if args.status:
        out = cmd_status()
    else:
        if not args.train_num or args.ccu_ip is None:
            print("error: --train-num and --ccu-ip required (unless --status)", file=sys.stderr)
            sys.exit(2)
        # Resolve Fzg from fleet-status if not explicitly passed.
        if args.fzg is None:
            try:
                sys.path.insert(0, str(Path(__file__).parent))
                from fleet_status_lookup import parse_fleet_status, lookup_by_train_number
                rows = parse_fleet_status()
                row = lookup_by_train_number(rows, args.train_num)
                if row and row['fzg'] is not None:
                    args.fzg = row['fzg']
            except Exception:
                pass
        out = run_cycle(args)

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        for k, v in out.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    main()
