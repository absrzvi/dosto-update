"""Shared lookup helper for fleet-status.md.

Source of truth for the Train# <-> Fzg mapping at runtime. Every dosto-* skill
that needs to resolve a Train# to a Fzg ID (or vice versa) goes through here.

Design rules:
  - Train# is the primary identifier (Nomad-internal name).
  - Fzg ID is derived from the fleet-status row, not from a formula.
  - If a row's Fzg cell is missing or '?' / 'UNKNOWN', skills MUST halt and
    ask the human, never guess from the per-series formula. Wrong Fzg
    silently rendered into switch hostnames / vlan7 IPs has caused real
    fleet-status corrupting outages.
  - Series headers are discovered dynamically (### NNNN series). Adding
    a new series to fleet-status.md needs no code change here.

Public functions:
  parse_fleet_status(path)         -> list[dict] (all rows, all series)
  lookup_by_train_number(rows, t#) -> dict or None
  lookup_by_fzg(rows, fzg)         -> dict or None
  ensure_fzg(row, interactive)     -> int or raises FzgUnknownError
  prompt_for_fzg(train_number)     -> int (interactive stdin)
  write_fzg_back(path, t#, fzg)    -> bool (updates the row in-place)
"""
from __future__ import annotations
import re, sys
from pathlib import Path
from typing import Optional


class FzgUnknownError(Exception):
    """Raised when a row's Fzg cell is missing/'?' and skill is non-interactive."""
    def __init__(self, train_number: str, ccu_ip: Optional[str] = None):
        self.train_number = train_number
        self.ccu_ip = ccu_ip
        super().__init__(
            f"Fzg ID for {train_number} is missing or unknown in fleet-status.md. "
            f"Look up in train-ip-allocation-commission/<series>-xxx/{train_number}/ "
            f"or by physical inspection, then populate the Fzg column."
        )


_TRAIN_NUMBER_RE = re.compile(r'^\d{4}-\d{3}$')
_IP_RE = re.compile(r'(\d+\.\d+\.\d+\.\d+)')


def _is_unknown(cell: str) -> bool:
    """A Fzg cell counts as unknown if it's blank, '?', '❓', or holds prose like 'UNKNOWN'."""
    s = (cell or '').strip().strip('`').lower()
    if not s: return True
    if s in ('?', '❓', 'unknown', '⚪ unknown', '⚪'): return True
    return False


def _parse_int_fzg(cell: str) -> Optional[int]:
    """Extract a numeric Fzg ID from a cell. Returns None if not parseable."""
    if _is_unknown(cell):
        return None
    m = re.match(r'^\s*(\d+)\s*$', (cell or '').strip())
    return int(m.group(1)) if m else None


def parse_fleet_status(path: str = 'fleet-status.md') -> list[dict]:
    """Parse every `### NNNN series` table in fleet-status.md.

    Returns a flat list of row dicts. Each row has at minimum:
      series, train_number, fzg (int or None), ccu_ip (str or None),
      nomad_status, stadler_status, next_action, raw_row (list[str]),
      header (list[str], the table's column names).
    Skills should index by `train_number`. Fzg may be None — call ensure_fzg()
    when you actually need the integer.
    """
    md = Path(path).read_text(encoding='utf-8')
    rows: list[dict] = []
    for m in re.finditer(r'^### (\d+) series', md, re.MULTILINE):
        series = m.group(1)
        section_start = m.end()
        section = md[section_start:]
        # Stop at the next `### ` or `## ` header.
        next_header = re.search(r'^#{2,3} ', section, re.MULTILINE)
        if next_header:
            section = section[:next_header.start()]
        rows.extend(_parse_section(section, series))
    return rows


def _parse_section(section: str, series: str) -> list[dict]:
    """Parse one series section's markdown table."""
    out = []
    header_cols: list[str] = []
    saw_header = False
    in_table = False
    for line in section.split('\n'):
        if line.startswith('|') and not saw_header and not re.match(r'^\|[-| ]+\|$', line):
            header_cols = [c.strip() for c in line.split('|')[1:-1]]
            saw_header = True
            continue
        if re.match(r'^\|[-| ]+\|$', line):
            in_table = True
            continue
        if in_table:
            if not line.startswith('|'): break
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) != len(header_cols): continue
            row = _row_from_cols(header_cols, cols, series)
            if row: out.append(row)
    return out


def _col_idx(header_cols: list[str], name_substr: str) -> Optional[int]:
    for i, h in enumerate(header_cols):
        if name_substr.lower() in h.lower():
            return i
    return None


def _clean(text: str) -> str:
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', text or '')
    t = re.sub(r'`([^`]+)`', r'\1', t)
    return t.strip()


def _row_from_cols(header_cols: list[str], cols: list[str], series: str) -> Optional[dict]:
    """Build a row dict from a header + cells tuple. Returns None if no train number found."""
    i_train  = _col_idx(header_cols, 'train')
    i_fzg    = _col_idx(header_cols, 'fzg')
    i_ccu    = _col_idx(header_cols, 'ccu')
    i_nomad  = _col_idx(header_cols, 'nomad status')
    if i_nomad is None: i_nomad = _col_idx(header_cols, 'status')
    i_stadler = _col_idx(header_cols, 'stadler')
    i_next    = _col_idx(header_cols, 'next action')

    train_number = _clean(cols[i_train]) if i_train is not None else ''
    # Fall back: 4705/4706 tables historically put the train# in the Fzg column
    # because they had no separate Fzg column. Be tolerant during the transition.
    if not _TRAIN_NUMBER_RE.match(train_number) and i_fzg is not None:
        alt = _clean(cols[i_fzg])
        if _TRAIN_NUMBER_RE.match(alt):
            train_number = alt
    if not _TRAIN_NUMBER_RE.match(train_number):
        return None

    fzg = _parse_int_fzg(cols[i_fzg]) if i_fzg is not None else None
    ccu_match = _IP_RE.search(_clean(cols[i_ccu])) if i_ccu is not None else None
    ccu_ip = ccu_match.group(1) if ccu_match else None

    return {
        'series': series,
        'train_number': train_number,
        'fzg': fzg,
        'ccu_ip': ccu_ip,
        'nomad_status': cols[i_nomad] if i_nomad is not None else '',
        'stadler_status': cols[i_stadler] if i_stadler is not None else '',
        'next_action': _clean(cols[i_next]) if i_next is not None else '',
        'raw_row': cols,
        'header': header_cols,
    }


def lookup_by_train_number(rows: list[dict], train_number: str) -> Optional[dict]:
    """Find a row by Train# (e.g. '4736-104'). Returns None if not present."""
    train_number = train_number.strip()
    for r in rows:
        if r['train_number'] == train_number:
            return r
    return None


def lookup_by_fzg(rows: list[dict], fzg: int) -> Optional[dict]:
    """Find a row by Fzg ID. Returns None if no row has that Fzg or all rows have ? Fzg."""
    for r in rows:
        if r['fzg'] == fzg:
            return r
    return None


def lookup_by_ccu_ip(rows: list[dict], ccu_ip: str) -> Optional[dict]:
    """Find a row by CCU IP. Returns None if no row has that IP."""
    for r in rows:
        if r['ccu_ip'] == ccu_ip:
            return r
    return None


# ---- In-flight claim parsing (added 2026-05-22 for concurrent-orchestration visibility) ----

# Canonical format for the Nomad status cell when a train is claimed by an active
# orchestrator session:
#
#   🔵 IN PROGRESS — stage <stage_id> (<step>/<total>, t+<elapsed>), hb <iso8601>, sess <short-id>
#
# Examples (all valid):
#   🔵 IN PROGRESS — stage push_switch_config (3/18, t+12m), hb 2026-05-22T14:32:00Z, sess 1212Z
#   🔵 IN PROGRESS — stage initial_diagnostics (1/1, t+45s), hb 2026-05-22T09:15:30Z, sess 0913Z
#   🔵 IN PROGRESS — stage apply_obn_patches (-, t+2m), hb 2026-05-22T11:02:00Z, sess 1100Z
#
# The `step/total` portion may be `-` when the stage is one-shot. `elapsed` accepts
# `Ns`/`Nm`/`Nh` units. `sess` is the last 4 chars of the orchestrator's cycle_id.
#
# Why prose-blob rather than structured columns: engineers eyeball fleet-status as the
# at-a-glance fleet view; a single cell with all the in-flight detail is scannable.
# Morning-brief and any other consumer parses via the regex below — load-bearing.

_IN_FLIGHT_RE = re.compile(
    r'IN PROGRESS\s*[—-]\s*stage\s+(?P<stage>\w+)\s*'
    r'\((?P<step>\d+|-)\s*/\s*(?P<total>\d+|-)\s*,\s*t\+(?P<elapsed>\d+[smh])\)\s*,\s*'
    r'hb\s+(?P<hb>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?)\s*,\s*'
    r'sess\s+(?P<sess>[\w-]+)',
    re.IGNORECASE,
)


def parse_in_flight(status_cell: str) -> Optional[dict]:
    """Parse a Nomad status cell. Returns the in-flight detail dict, or None if
    the cell isn't an IN PROGRESS claim.

    Returned dict shape:
      {
        "stage": "push_switch_config",     # canonical stage_id from subagent-report contract
        "step": 3,                          # int, or None for one-shot stages
        "total": 18,                        # int, or None for one-shot stages
        "elapsed": "12m",                   # raw string with unit (s/m/h)
        "elapsed_seconds": 720,             # parsed to seconds for arithmetic
        "heartbeat_iso": "2026-05-22T14:32:00Z",
        "session_id": "1212Z",              # last 4 chars of orchestrator cycle_id
      }

    If the cell doesn't match the canonical format (no in-flight claim, or a
    malformed claim), returns None. Callers should treat a non-None return as
    "this row is currently claimed by an orchestrator session."
    """
    if not status_cell or 'IN PROGRESS' not in status_cell.upper():
        return None
    m = _IN_FLIGHT_RE.search(status_cell)
    if not m:
        return None
    step_raw = m.group('step')
    total_raw = m.group('total')
    elapsed = m.group('elapsed')
    # Parse elapsed unit suffix.
    unit = elapsed[-1].lower()
    n = int(elapsed[:-1])
    elapsed_seconds = n * {'s': 1, 'm': 60, 'h': 3600}[unit]
    return {
        'stage': m.group('stage'),
        'step': int(step_raw) if step_raw != '-' else None,
        'total': int(total_raw) if total_raw != '-' else None,
        'elapsed': elapsed,
        'elapsed_seconds': elapsed_seconds,
        'heartbeat_iso': m.group('hb'),
        'session_id': m.group('sess'),
    }


def format_in_flight(stage: str, step: Optional[int], total: Optional[int],
                     elapsed_seconds: int, heartbeat_iso: str, session_id: str) -> str:
    """Format an in-flight claim into the canonical Nomad-status-cell string.

    Inverse of parse_in_flight(). The orchestrator MUST use this helper rather
    than string-formatting inline, so the regex above stays load-bearing on a
    single canonical shape.
    """
    # Pick the most readable elapsed unit.
    if elapsed_seconds < 90:
        elapsed = f'{elapsed_seconds}s'
    elif elapsed_seconds < 5400:
        elapsed = f'{elapsed_seconds // 60}m'
    else:
        elapsed = f'{elapsed_seconds // 3600}h'
    step_str = str(step) if step is not None else '-'
    total_str = str(total) if total is not None else '-'
    return (f'🔵 IN PROGRESS — stage {stage} ({step_str}/{total_str}, t+{elapsed}), '
            f'hb {heartbeat_iso}, sess {session_id}')


def heartbeat_age_seconds(heartbeat_iso: str, now_iso: Optional[str] = None) -> int:
    """Compute seconds between heartbeat and now. Tolerates fractional seconds + missing Z.
    Used by morning-brief to classify health: fresh (<10m) / lagging (10-30m) / stale (>30m).
    """
    from datetime import datetime, timezone
    def _parse(s):
        s = s.rstrip('Z')
        # Accept HH:MM or HH:MM:SS
        if len(s) == 16:  # YYYY-MM-DDTHH:MM
            s += ':00'
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    hb = _parse(heartbeat_iso)
    now = _parse(now_iso) if now_iso else datetime.now(timezone.utc)
    return int((now - hb).total_seconds())


def ensure_fzg(row: dict, interactive: bool = True, fleet_status_path: str = 'fleet-status.md') -> int:
    """Return the row's Fzg ID. If missing and interactive, prompt human and write back.
    If missing and non-interactive (subagents), raise FzgUnknownError so the caller
    can surface a BLOCKED status with a proper next_action.
    """
    if row['fzg'] is not None:
        return row['fzg']
    if not interactive:
        raise FzgUnknownError(row['train_number'], row.get('ccu_ip'))
    fzg = prompt_for_fzg(row['train_number'], row.get('ccu_ip'))
    write_fzg_back(fleet_status_path, row['train_number'], fzg)
    row['fzg'] = fzg
    return fzg


def prompt_for_fzg(train_number: str, ccu_ip: Optional[str] = None) -> int:
    """Interactive stdin prompt. Returns the engineer-supplied Fzg ID (validated int)."""
    series = train_number.split('-')[0] if '-' in train_number else '?'
    print()
    print(f"⚠️  Fzg ID for {train_number} is missing in fleet-status.md.")
    if ccu_ip:
        print(f"   CCU IP: {ccu_ip}")
    print(f"   Look up in: train-ip-allocation-commission/{series}-xxx/{train_number}/")
    print(f"               <train#>_IP-Port-Allocation.pdf (header line)")
    print(f"   Or via physical inspection (Fzg number painted on the carriage).")
    print()
    while True:
        try:
            raw = input(f"Enter Fzg ID for {train_number} (integer, or 'abort'): ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit("Aborted at Fzg prompt.")
        if raw.lower() == 'abort':
            raise SystemExit(f"Aborted: Fzg ID for {train_number} not supplied.")
        if raw.isdigit() and 1 <= int(raw) <= 999:
            return int(raw)
        print(f"  '{raw}' is not a valid Fzg ID (expected 1-999). Try again.")


def write_fzg_back(path: str, train_number: str, fzg: int) -> bool:
    """Update the Fzg cell for a Train# row in-place. Returns True if the file changed.

    The cell to write into is whichever column the row's table header calls 'Fzg'.
    If the table has no Fzg column (legacy 4705/4706 shape), this is a no-op — the
    schema-migration step adds the column first.
    """
    content = Path(path).read_text(encoding='utf-8')
    rows = parse_fleet_status(path)
    target = lookup_by_train_number(rows, train_number)
    if target is None:
        return False
    i_fzg = _col_idx(target['header'], 'fzg')
    if i_fzg is None:
        return False  # legacy 4705/4706 table without Fzg column
    # Rebuild the row line with the new Fzg cell, then string-replace.
    old_cols = target['raw_row']
    new_cols = list(old_cols)
    new_cols[i_fzg] = str(fzg)
    # Reconstruct the line as fleet-status writes them (leading and trailing |, spaces).
    old_line = '| ' + ' | '.join(old_cols) + ' |'
    new_line = '| ' + ' | '.join(new_cols) + ' |'
    if old_line not in content:
        return False
    content = content.replace(old_line, new_line, 1)
    Path(path).write_text(content, encoding='utf-8')
    return True


# ---- CLI: useful for skills that want to shell out to this helper. ----

def _cli():
    import argparse, json
    ap = argparse.ArgumentParser(description="fleet-status.md lookup helper")
    ap.add_argument('--fleet-status', default='fleet-status.md')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list', help='Print all rows as JSON.')
    p_lookup = sub.add_parser('lookup', help='Look up a row by train number.')
    p_lookup.add_argument('train_number')
    p_lookup.add_argument('--require-fzg', action='store_true',
                          help='Halt (exit 2) if Fzg unknown; do not prompt.')
    p_fzg = sub.add_parser('ensure-fzg', help='Get Fzg for a Train#, prompting if missing.')
    p_fzg.add_argument('train_number')
    p_fzg.add_argument('--non-interactive', action='store_true')
    args = ap.parse_args()

    rows = parse_fleet_status(args.fleet_status)

    if args.cmd == 'list':
        print(json.dumps(rows, default=str, indent=2))
        return

    if args.cmd == 'lookup':
        row = lookup_by_train_number(rows, args.train_number)
        if row is None:
            print(f"not_found: {args.train_number}", file=sys.stderr)
            sys.exit(1)
        if args.require_fzg and row['fzg'] is None:
            print(f"fzg_unknown: {args.train_number}", file=sys.stderr)
            sys.exit(2)
        print(json.dumps(row, default=str, indent=2))
        return

    if args.cmd == 'ensure-fzg':
        row = lookup_by_train_number(rows, args.train_number)
        if row is None:
            print(f"not_found: {args.train_number}", file=sys.stderr)
            sys.exit(1)
        try:
            fzg = ensure_fzg(row, interactive=not args.non_interactive,
                             fleet_status_path=args.fleet_status)
        except FzgUnknownError as e:
            print(f"fzg_unknown: {e}", file=sys.stderr)
            sys.exit(2)
        print(fzg)


if __name__ == '__main__':
    _cli()
