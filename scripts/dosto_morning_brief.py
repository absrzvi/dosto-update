#!/usr/bin/env python3
"""DOSTO Morning Brief — dry-run reachability scan + start-first recommendation.

Reads fleet-status.md, TCP-probes every known CCU IP, infers a resume stage
from each train's Next action prose, and renders morning-brief.html.

Never invokes /dosto-orchestrate. Never writes fleet-status.md. Only output
file is morning-brief.html at workspace root.
"""
import sys, io, re, socket, argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Canonical 19-stage pipeline order, from .claude/contracts/subagent-report.md
STAGES = [
    'initial_diagnostics',
    'await_device_count_mismatch',
    'ensure_v8_templates',
    'apply_obn_patches',
    'apply_train_id_fix',
    'apply_vlan7_fix',
    'await_promote_snapshot',
    'promote_snapshot',
    'await_safe_reboot',
    'reboot_and_wait',
    'post_reboot_verify',
    'obn_discover_initial',
    'await_obn_update_c',
    'push_switch_config',
    'obn_discover_post_sw_config',
    'await_obn_update_f',
    'push_switch_firmware',
    'ap_factory_bypass',
    'push_ap_firmware',
    'push_ap_config',
    'final_l2_health_check',
    'generate_report',
    'done',
]
GATES = {s for s in STAGES if s.startswith('await_')}

# Stage inference rules — (regex, stage_id). First match wins, order matters.
STAGE_RULES = [
    (r'wait for stadler|blocked.*stadler|awaiting stadler|stadler.*pending', 'BLOCKED'),
    (r'initial visit|confirm v8 state', 'initial_diagnostics'),
    (r'v3 config|v5 config|needs (?:full )?v8 push|v8 templates? missing|nd-systemupdate.*up\b', 'ensure_v8_templates'),
    (r'fix obn template|hardcode.*train_id|train_id\s*(?:→|->|to\s)', 'apply_train_id_fix'),
    (r'vlan7.*(fix|wrong|change|repair)|fix.*vlan7', 'apply_vlan7_fix'),
    (r'apply obn patches|fix_obn\.py|8/8.*(apply|missing)|obn patches.*apply', 'apply_obn_patches'),
    (r'persist|chroot|promote.*snapshot|nd-systemupdate\.sh.*shell', 'await_promote_snapshot'),
    (r'\breboot\b|safe_reboot|activate run\d', 'await_safe_reboot'),
    (r'push config|obn update c|update c all|push.*switch.*config', 'await_obn_update_c'),
    (r'push ap fw|push ap firmware|obn update f|6\.11\.2-0', 'await_obn_update_f'),
    (r'factory|luci|RT610LV', 'ap_factory_bypass'),
    (r'health check|l2 health|/dosto-l2-health', 'final_l2_health_check'),
    (r'customer report|report v1', 'generate_report'),
]

def infer_stage(next_action: str) -> str:
    s = next_action.lower()
    for pattern, stage in STAGE_RULES:
        if re.search(pattern, s):
            return stage
    return '?'

def status_class(status_cell: str) -> str:
    s = status_cell.lower()
    if 'done' in s: return 'done'
    if 'blocked' in s: return 'blocked'
    if 'paused' in s: return 'paused'
    if 'progress' in s: return 'inprogress'
    return 'unknown'

STATUS_LABELS = {
    'done':       ('DONE',        '#22c55e'),
    'blocked':    ('BLOCKED',     '#ef4444'),
    'paused':     ('PAUSED',      '#eab308'),
    'inprogress': ('IN PROGRESS', '#3b82f6'),
    'unknown':    ('UNKNOWN',     '#94a3b8'),
}

def clean(text: str) -> str:
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    return t.strip()

def parse_table(text: str, header: str):
    """Return list of (header_cols, data_rows). Captures the header row so callers can map column names to indices — the 4736/4734 tables grew a 'Stadler status' column on 2026-05-21 between 'Nomad status' (formerly 'Status') and 'Next action', so positional indexing is fragile."""
    idx = text.find(header)
    if idx == -1: return [], []
    header_cols = []
    rows = []
    saw_header = False
    in_table = False
    for line in text[idx:].split('\n'):
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
            if len(cols) == len(header_cols):
                rows.append(cols)
    return header_cols, rows

def col_idx(header_cols, name_substr_lower):
    """Find a column index by lower-cased substring match in the header."""
    for i, h in enumerate(header_cols):
        if name_substr_lower in h.lower():
            return i
    return None

def probe_tcp(ip: str, port: int = 22, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def extract_ip(ccu_cell: str):
    m = re.search(r'(\d+\.\d+\.\d+\.\d+)', ccu_cell)
    return m.group(1) if m else None

def stages_remaining(stage: str):
    """Return list of upcoming canonical stages starting at `stage`."""
    if stage in ('BLOCKED', '?'): return []
    if stage not in STAGES: return []
    return STAGES[STAGES.index(stage):]

def recommend(trains):
    """Pick the train with no gate in next 3 stages. Tie-break: longest runway.
    Returns (train_number, rationale) — Train# is the recommendation key."""
    candidates = []
    for t in trains:
        upcoming = stages_remaining(t['stage'])[:3]
        if not upcoming: continue
        if any(s in GATES for s in upcoming): continue
        runway = len(stages_remaining(t['stage']))
        candidates.append((runway, t, upcoming))
    if not candidates:
        return None, None
    candidates.sort(key=lambda x: -x[0])
    runway, train, upcoming = candidates[0]
    rationale = (f"Next {len(upcoming)} stages ({', '.join(upcoming)}) — "
                 f"no approval gate, {runway} stages to done.")
    return train['train_number'], rationale

def rationale_for(train, recommended_train):
    stage = train['stage']
    if stage == 'BLOCKED':
        return 'BLOCKED — Stadler-dependent'
    if stage == '?':
        return 'Next action prose unmapped — engineer review'
    upcoming = stages_remaining(stage)[:3]
    if not upcoming:
        return 'no upcoming stages'
    gate_in = next((i+1 for i, s in enumerate(upcoming) if s in GATES), None)
    if train['train_number'] == recommended_train:
        return f"✅ {', '.join(upcoming)} — no gate, {len(stages_remaining(stage))} to done"
    if gate_in:
        return f"Gate at step {gate_in} ({upcoming[gate_in-1]}) — needs engineer attention"
    return f"eligible but not top: {', '.join(upcoming)}"

CSS = """
:root { --bg:#0f172a; --surface:#1e293b; --surface2:#273344; --border:#334155;
        --text:#e2e8f0; --text-muted:#94a3b8; --accent:#38bdf8; --recommend:#0e3a2a; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text);
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; }
header { background:var(--surface); border-bottom:1px solid var(--border);
         padding:16px 32px; display:flex; align-items:center; justify-content:space-between; }
header h1 { font-size:18px; font-weight:700; color:var(--accent); letter-spacing:.05em; }
header .subtitle { font-size:12px; color:var(--text-muted); margin-top:2px; }
header .updated { font-size:11px; color:var(--text-muted); text-align:right; }
.container { max-width:1400px; margin:0 auto; padding:24px 32px; }
.section { margin-bottom:32px; }
.section-header { display:flex; align-items:baseline; gap:12px; margin-bottom:12px;
                  border-bottom:1px solid var(--border); padding-bottom:8px; }
.section-header h2 { font-size:16px; font-weight:600; }
.section-header .count { font-size:12px; color:var(--text-muted); }
.table-wrap { overflow-x:auto; border-radius:8px; border:1px solid var(--border); }
table { width:100%; border-collapse:collapse; }
thead tr { background:var(--surface2); }
thead th { padding:10px 14px; text-align:left; font-size:11px; text-transform:uppercase;
           letter-spacing:.06em; color:var(--text-muted); font-weight:600;
           white-space:nowrap; border-bottom:1px solid var(--border); }
table.sortable thead th { cursor:pointer; user-select:none; position:relative; padding-right:24px; }
table.sortable thead th:hover { color:var(--accent); }
table.sortable thead th::after { content:'\\2195'; position:absolute; right:8px; opacity:.35; font-size:10px; }
table.sortable thead th.sort-asc::after  { content:'\\25B2'; opacity:1; color:var(--accent); }
table.sortable thead th.sort-desc::after { content:'\\25BC'; opacity:1; color:var(--accent); }
tbody tr { border-bottom:1px solid var(--border); transition:background .1s; }
tbody tr:last-child { border-bottom:none; }
tbody tr:hover { background:var(--surface2); }
tbody tr.recommended { background:var(--recommend); border-left:3px solid #22c55e; }
td { padding:9px 14px; vertical-align:top; }
.row-done       { border-left:3px solid #22c55e; }
.row-paused     { border-left:3px solid #eab308; }
.row-blocked    { border-left:3px solid #ef4444; }
.row-inprogress { border-left:3px solid #3b82f6; }
.row-unknown    { border-left:3px solid var(--border); }
.badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px;
         font-weight:700; color:#fff; letter-spacing:.04em; white-space:nowrap; }
.stage-tag { display:inline-block; padding:2px 7px; border-radius:4px; font-size:11px;
             background:#1e3a5f; color:#93c5fd; border:1px solid #2563eb44;
             font-family:Consolas,"Courier New",monospace; }
.stage-tag.blocked { background:#3a1a1a; color:#fca5a5; border-color:#ef444466; }
.stage-tag.unknown { background:#1e293b; color:#94a3b8; border-color:var(--border); }
.mono { font-family:Consolas,"Courier New",monospace; font-size:12px; }
.small { font-size:12px; color:var(--text-muted); }
.center { text-align:center; }
.cmd-block { background:#020617; border:1px solid var(--accent); border-radius:8px;
             padding:16px 20px; margin-top:12px; font-family:Consolas,"Courier New",monospace;
             font-size:14px; color:var(--accent); overflow-x:auto; }
.dry-run-note { margin-top:8px; font-size:12px; color:var(--text-muted); font-style:italic; }
details { background:var(--surface); border:1px solid var(--border); border-radius:8px;
          padding:12px 16px; margin-top:24px; }
summary { cursor:pointer; font-size:13px; color:var(--text-muted); }
details[open] summary { margin-bottom:8px; color:var(--text); }
details .urlist { font-family:Consolas,"Courier New",monospace; font-size:12px;
                  color:var(--text-muted); line-height:1.6; }
"""

def status_badge(status_cell: str) -> str:
    cls = status_class(status_cell)
    label, color = STATUS_LABELS[cls]
    return f'<span class="badge" style="background:{color}">{label}</span>'

def stage_tag(stage: str) -> str:
    if stage == 'BLOCKED':
        return f'<span class="stage-tag blocked">{stage}</span>'
    if stage == '?':
        return '<span class="stage-tag unknown">?</span>'
    return f'<span class="stage-tag">{stage}</span>'

PENDING_MARKER = '<!-- pending Train# assignment (managed by dosto-morning-brief) -->'
_TRAIN_NUMBER_RE = re.compile(r'^(\d{4})-\d{3}$')

def append_to_pending(path: str, ip: str):
    """Add an IP to the 'Pending Train# assignment' section. Engineer skipped it
    at the prompt; we record it so next morning's brief doesn't re-ask."""
    content = Path(path).read_text(encoding='utf-8')
    today = datetime.now().strftime('%Y-%m-%d')
    if PENDING_MARKER not in content:
        section = (
            f'\n\n{PENDING_MARKER}\n\n'
            f'## Pending Train# assignment\n\n'
            f'CCU IPs discovered by morning-brief network sweep where the engineer '
            f'has not yet provided a Train#. These are skip-listed (not re-prompted '
            f'next run). Hand-edit this section: delete the row and add a proper '
            f'entry to the matching series table once you identify the train '
            f'(cross-ref against `train-ip-allocation-commission/` PDFs — do NOT '
            f'trust .cfg filenames or switch hostnames since the train_id formula '
            f'is broken pre-commissioning).\n\n'
            f'| CCU IP | Discovered |\n|---|---|\n'
        )
        content += section
    new_row = f'| `{ip}` | {today} |'
    content = content.rstrip() + '\n' + new_row + '\n'
    Path(path).write_text(content, encoding='utf-8')

# A Nomad-status cell is "claimed" iff it carries the 🔵 IN PROGRESS lozenge,
# whether or not the trailing text matches the canonical format_in_flight() shape.
# parse_in_flight() (canonical regex) deliberately returns None for hand-written
# prose claims like "🔵 IN PROGRESS — sess 0900Z: CCU work done; ..." — but the
# stale-claim cleaner must still flip those, otherwise it silently no-ops on the
# exact rows an engineer most needs cleaned (regression observed 2026-06-08 on
# 4734-109 / 4734-115). We therefore match on the lozenge, not the full format.
_IN_PROGRESS_LOZENGE_RE = re.compile(r'🔵\s*IN\s*PROGRESS', re.IGNORECASE)
# Best-effort session-id grab for non-canonical claims, so the PAUSED note can
# still name the dead session.
_SESS_RE = re.compile(r'\bsess(?:ion)?\s+([\w-]+)', re.IGNORECASE)


def clean_stale_claim(path: str, train_number: str) -> tuple[bool, str]:
    """Flip an in-flight claim back to PAUSED. Used by morning-brief's stale-claim
    gate after the engineer confirms the orchestrator session is dead.

    Matches ANY cell carrying the 🔵 IN PROGRESS lozenge — canonical
    format_in_flight() claims AND hand-written prose claims alike. Canonical
    claims yield a rich PAUSED note (stage + heartbeat); prose claims yield a
    best-effort note tagged 'non-canonical claim'.

    Returns (ok, message). `ok=False` (and the CLI exits non-zero) when the row
    is genuinely NOT in-flight, the train isn't in fleet-status, or the row line
    couldn't be located for the swap. Critically, `ok=False` is never paired with
    a 'cleaned' message — a false-success print here makes the engineer believe a
    claim is gone when it isn't, so next morning's brief and orchestrate Step 6.0
    keep tripping over it.
    """
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from fleet_status_lookup import parse_fleet_status, lookup_by_train_number, parse_in_flight

    rows = parse_fleet_status(path)
    target = lookup_by_train_number(rows, train_number)
    if target is None:
        return False, f'{train_number} not found in fleet-status'

    cell = target['nomad_status']
    if not _IN_PROGRESS_LOZENGE_RE.search(cell):
        return False, f'{train_number} is not currently marked 🔵 IN PROGRESS (no claim to clean)'

    # Prefer the canonical parse (rich note); fall back to a best-effort prose grab.
    claim = parse_in_flight(cell)
    if claim is not None:
        note = (f'🟡 PAUSED — stale claim auto-cleaned from session {claim["session_id"]} '
                f'(stage {claim["stage"]}, last hb {claim["heartbeat_iso"]})')
        sess_part = f'sess {claim["session_id"]}'
    else:
        m = _SESS_RE.search(cell)
        sess = m.group(1) if m else 'unknown'
        note = (f'🟡 PAUSED — stale claim auto-cleaned from session {sess} '
                f'(non-canonical claim; original text could not be parsed by parse_in_flight)')
        sess_part = f'sess {sess} (non-canonical)'

    # Rebuild the row line with the cleaned-up Nomad status cell. Read raw content
    # and do a literal swap of the old row line for the new one.
    content = Path(path).read_text(encoding='utf-8')
    header = target['header']
    i_nomad = None
    for i, h in enumerate(header):
        if 'nomad status' in h.lower() or h.lower() == 'status':
            i_nomad = i; break
    if i_nomad is None:
        return False, f'fleet-status row for {train_number} has no Nomad status column'

    old_cells = list(target['raw_row'])
    new_cells = list(old_cells)
    new_cells[i_nomad] = note
    old_line = '| ' + ' | '.join(old_cells) + ' |'
    new_line = '| ' + ' | '.join(new_cells) + ' |'
    if old_line not in content:
        return False, f'could not locate row line for {train_number} (file may have been edited concurrently)'
    content = content.replace(old_line, new_line, 1)
    Path(path).write_text(content, encoding='utf-8')
    return True, f'cleaned: {train_number} → PAUSED (was claimed by {sess_part})'


def assign_to_series(path: str, ip: str, train_number: str, fzg: str = None):
    """Insert a new row into the matching series table for an engineer-supplied
    (ip, train_number) tuple. Series is derived from the Train# prefix. Fzg is
    optional — if not supplied, written as `❓` (engineer fills later from PDF).
    Idempotent: skips if this IP already appears anywhere in the file."""
    m = _TRAIN_NUMBER_RE.match(train_number)
    if not m:
        raise ValueError(f'invalid train#: {train_number!r} (expected NNNN-NNN)')
    series = m.group(1)
    if series not in {'4734', '4736', '4705', '4706'}:
        raise ValueError(f'unknown series: {series}')
    content = Path(path).read_text(encoding='utf-8')
    if ip in content:
        return False
    header = f'### {series} series'
    if header not in content:
        raise ValueError(f'series header not found: {header}')
    lines = content.split('\n')
    start_line = next(i for i, l in enumerate(lines) if l.startswith(header))
    in_table = False
    insert_at = None
    for i in range(start_line, len(lines)):
        if re.match(r'^\|[-| ]+\|$', lines[i]):
            in_table = True; continue
        if in_table:
            if not lines[i].startswith('|'):
                insert_at = i
                break
    if insert_at is None:
        insert_at = len(lines)
    fzg_cell = str(fzg) if fzg else '❓'
    new_row = f'| {train_number} | {fzg_cell} | `{ip}` | ⚪ UNKNOWN | ❓ | initial visit |'
    lines.insert(insert_at, new_row)
    Path(path).write_text('\n'.join(lines), encoding='utf-8')
    return True

def _render_in_flight_section(in_flight):
    """Render the 'Currently in flight' HTML section, or empty string if list is empty."""
    if not in_flight:
        return ''
    HEALTH = {
        'fresh':   ('🟢', '#22c55e', '< 10 min'),
        'lagging': ('🟡', '#eab308', '10-30 min'),
        'stale':   ('🔴', '#ef4444', '> 30 min — likely dead session'),
        'unknown': ('❔', '#94a3b8', 'unparseable heartbeat'),
    }
    rows = []
    for f in in_flight:
        icon, color, _ = HEALTH[f['health']]
        step_str = f"{f['step']}/{f['total']}" if f['step'] is not None else '—'
        age_min = (f['age_seconds'] // 60) if f['age_seconds'] is not None else '?'
        fzg_str = str(f['fzg']) if f['fzg'] else '❓'
        rows.append(
            f'<tr>'
            f'<td class="mono">{f["train_number"]}</td>'
            f'<td class="mono center">{fzg_str}</td>'
            f'<td class="mono">{f["ccu_ip"]}</td>'
            f'<td><span class="stage-tag">{f["stage"]}</span></td>'
            f'<td class="mono center">{step_str}</td>'
            f'<td class="mono">t+{f["elapsed"]}</td>'
            f'<td><span style="color:{color}">{icon} {age_min}m ago</span></td>'
            f'<td class="mono small">{f["session_id"]}</td>'
            f'</tr>'
        )
    stale_count = sum(1 for f in in_flight if f['health'] == 'stale')
    stale_note = (f' &middot; <span style="color:#ef4444;font-weight:600">{stale_count} stale — needs cleanup</span>'
                  if stale_count else '')
    return f'''
<div class="section">
  <div class="section-header"><h2>🔵 Currently in flight</h2>
    <span class="count">{len(in_flight)} active{stale_note}</span></div>
  <div class="table-wrap"><table class="sortable">
    <thead><tr><th>Train#</th><th>Fzg</th><th>CCU IP</th><th>Stage</th><th>Step</th><th>Elapsed</th><th>Heartbeat</th><th>Session</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table></div>
  <div class="dry-run-note">
    Health: 🟢 fresh (&lt; 10 min) &middot; 🟡 lagging (10–30 min) &middot; 🔴 stale (&gt; 30 min — likely dead session, run cleanup).
  </div>
</div>
'''


def render_html(reachable, unreachable, discovered, recommended_train, recommended_rationale, would_be_cmd, in_flight=None):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    date_str = datetime.now().strftime('%Y-%m-%d')
    in_flight = in_flight or []
    in_flight_html = _render_in_flight_section(in_flight)
    rows = []
    for t in reachable:
        row_cls = 'recommended' if t['train_number'] == recommended_train else f'row-{status_class(t["status"])}'
        rationale = rationale_for(t, recommended_train)
        rec_cell = ('<strong style="color:#22c55e">YES</strong><br>' if t['train_number'] == recommended_train else 'no<br>') \
                   + f'<span class="small">{rationale}</span>'
        rows.append(
            f'<tr class="{row_cls}">'
            f'<td class="mono">{t["train_number"]}</td>'
            f'<td class="mono center">{t["fzg"] if t["fzg"] else "❓"}</td>'
            f'<td class="mono">{t["ip"]}</td>'
            f'<td>{status_badge(t["status"])}</td>'
            f'<td class="small">{t.get("stadler", "")}</td>'
            f'<td class="small">{t["next_action"]}</td>'
            f'<td>{stage_tag(t["stage"])}</td>'
            f'<td class="small">{rec_cell}</td>'
            f'</tr>'
        )
    rows_html = '\n'.join(rows) or '<tr><td colspan="8" class="small center">No reachable trains.</td></tr>'

    if unreachable:
        un_lines = '<br>'.join(f'{t["train_number"]} (Fzg {t["fzg"] or "❓"}) ({t["ip"]}) — {t["next_action"][:80]}' for t in unreachable)
    else:
        un_lines = '<em>All known-CCU trains reachable.</em>'

    reach_total_known = len(reachable) + len(unreachable)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DOSTO Morning Brief — {date_str}</title>
<style>{CSS}</style></head><body>
<header>
  <div>
    <h1>DOSTO Morning Brief</h1>
    <div class="subtitle">Dry-run reachability scan &middot; start-first recommendation</div>
  </div>
  <div class="updated">{now}<br><span style="color:var(--accent)">{len(reachable)} of {reach_total_known} known-CCU trains reachable</span>{(' · <span style="color:#3b82f6">' + str(len(in_flight)) + ' in flight</span>') if in_flight else ''}</div>
</header>
<div class="container">
{in_flight_html}
<div class="section">
  <div class="section-header"><h2>Reachable trains</h2><span class="count">{len(reachable)} online</span></div>
  <div class="table-wrap"><table class="sortable">
    <thead><tr><th>Train#</th><th>Fzg</th><th>CCU IP</th><th>Nomad status</th><th>Stadler status</th><th>Next Action</th><th>Resume Stage</th><th>Recommended?</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table></div>
</div>

<div class="section">
  <div class="section-header"><h2>To proceed, type:</h2>
    <span class="count">dry run &middot; not invoked</span></div>
  <div class="cmd-block">{would_be_cmd}</div>
  <div class="dry-run-note">
    {('Recommended start-first: <strong style="color:#22c55e">' + str(recommended_train) + '</strong> &mdash; ' + recommended_rationale) if recommended_train else 'No train eligible for autonomous start-first (all reachable trains hit an approval gate within the next 3 stages or are BLOCKED).'}
  </div>
  <div class="dry-run-note">Paste the command above manually to dispatch. This page does not invoke /dosto-orchestrate.</div>
</div>

{('<div class="section"><div class="section-header"><h2>Discovered CCUs &mdash; awaiting Train# assignment</h2><span class="count">' + str(len(discovered)) + ' new &middot; gate</span></div><div class="urlist" style="padding:12px 16px;background:var(--surface);border:1px solid #ef444466;border-radius:8px;">' + '<br>'.join(f"<code>{ip}</code> &mdash; <code>python scripts/dosto_morning_brief.py --assign {ip} &lt;TRAIN#&gt; [--fzg N]</code> or <code>--skip {ip}</code>" for ip in discovered) + '<br><br><span class="small">Engineer gate: identify Train# via <strong>train-ip-allocation-commission/ PDFs</strong> (filename + header <code>Fahrzeugnummer</code>) or physical inspection. Do NOT trust .cfg filenames or switch hostnames &mdash; the <code>train_id</code> formula is broken pre-commissioning and renders the wrong Fzg in those names.</span></div></div>') if discovered else ''}

<details>
  <summary>Unreachable trains ({len(unreachable)} known-CCU, failed TCP/22 probe)</summary>
  <div class="urlist">{un_lines}</div>
</details>

</div>
<script>
(function() {{
  function cellKey(td) {{
    if (td.dataset.sort !== undefined) return td.dataset.sort;
    return (td.textContent || '').trim();
  }}
  function ipKey(s) {{
    var m = s.match(/(\\d+)\\.(\\d+)\\.(\\d+)\\.(\\d+)/);
    if (!m) return null;
    return ((+m[1])*16777216 + (+m[2])*65536 + (+m[3])*256 + (+m[4]));
  }}
  function numKey(s) {{
    var m = s.match(/-?\\d+(?:\\.\\d+)?/);
    return m ? parseFloat(m[0]) : null;
  }}
  function compare(a, b) {{
    var ipA = ipKey(a), ipB = ipKey(b);
    if (ipA !== null && ipB !== null) return ipA - ipB;
    var nA = numKey(a), nB = numKey(b);
    if (nA !== null && nB !== null) return nA - nB;
    return a.localeCompare(b, undefined, {{numeric:true, sensitivity:'base'}});
  }}
  document.querySelectorAll('table.sortable').forEach(function(table) {{
    var ths = table.querySelectorAll('thead th');
    ths.forEach(function(th, idx) {{
      th.addEventListener('click', function() {{
        var asc = !th.classList.contains('sort-asc');
        ths.forEach(function(o) {{ o.classList.remove('sort-asc','sort-desc'); }});
        th.classList.add(asc ? 'sort-asc' : 'sort-desc');
        var tbody = table.tBodies[0];
        var rows = Array.from(tbody.rows);
        rows.sort(function(r1, r2) {{
          var c = compare(cellKey(r1.cells[idx]), cellKey(r2.cells[idx]));
          return asc ? c : -c;
        }});
        rows.forEach(function(r) {{ tbody.appendChild(r); }});
      }});
    }});
  }});
}})();
</script>
</body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=5.0)
    ap.add_argument('--fleet-status', default='fleet-status.md')
    ap.add_argument('--out', default='morning-brief.html')
    ap.add_argument('--no-discover', action='store_true',
                    help='Skip the 10.179.x.1 discovery sweep')
    ap.add_argument('--assign', nargs=2, metavar=('IP', 'TRAIN_NUMBER'),
                    help='Assign a discovered IP to a Train# (engineer response to gate). '
                         'Series is derived from the Train# prefix. Writes a row to the '
                         'matching series table with Fzg=❓ unless --fzg is also passed.')
    ap.add_argument('--fzg', type=int, default=None,
                    help='Optional Fzg integer for --assign. If omitted, Fzg cell is ❓.')
    ap.add_argument('--skip', metavar='IP',
                    help='Skip-list a discovered IP (append to Pending section, do not re-prompt).')
    ap.add_argument('--clean-stale-claim', metavar='TRAIN_NUMBER', dest='clean_stale_claim',
                    help='Flip an in-flight claim back to PAUSED. Used after the engineer '
                         'confirms the orchestrator session that claimed this train is dead. '
                         'Surfaced via the stale-claim gate in interactive runs.')
    args = ap.parse_args()

    # Subcommands: --assign / --skip are write-only operations invoked by the skill
    # after the engineer answers the per-IP prompt. They short-circuit the brief.
    if args.assign:
        ip, train_number = args.assign
        ok = assign_to_series(args.fleet_status, ip, train_number, fzg=args.fzg)
        fzg_part = f' / Fzg {args.fzg}' if args.fzg else ' / Fzg ❓ (fill in later)'
        print(f'{"assigned" if ok else "already present"}: {ip} -> {train_number}{fzg_part}')
        return
    if args.skip:
        append_to_pending(args.fleet_status, args.skip)
        print(f'skip-listed: {args.skip}')
        return
    if args.clean_stale_claim:
        ok, msg = clean_stale_claim(args.fleet_status, args.clean_stale_claim)
        print(msg)
        sys.exit(0 if ok else 1)

    # Use the shared lookup helper as the single source for parsing fleet-status.
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from fleet_status_lookup import parse_fleet_status, parse_in_flight, heartbeat_age_seconds

    rows = parse_fleet_status(args.fleet_status)
    known_by_ip = {}
    for r in rows:
        if not r['ccu_ip']: continue
        known_by_ip[r['ccu_ip']] = {
            'train_number': r['train_number'],
            'fzg': r['fzg'],
            'ip': r['ccu_ip'],
            'status': r['nomad_status'],
            'stadler': r['stadler_status'],
            'next_action': r['next_action'],
        }

    # Detect in-flight claims across all rows (independent of reachability — a session
    # may have claimed a train that's now offline mid-stage; that's still in-flight
    # data the engineer needs to see).
    in_flight = []
    for r in rows:
        claim = parse_in_flight(r['nomad_status'])
        if not claim:
            continue
        try:
            age = heartbeat_age_seconds(claim['heartbeat_iso'])
        except Exception:
            age = None
        if age is None:
            health = 'unknown'
        elif age < 600:
            health = 'fresh'   # < 10 min
        elif age < 1800:
            health = 'lagging' # 10-30 min
        else:
            health = 'stale'   # > 30 min
        in_flight.append({
            'train_number': r['train_number'],
            'fzg': r['fzg'],
            'ccu_ip': r['ccu_ip'],
            'stage': claim['stage'],
            'step': claim['step'],
            'total': claim['total'],
            'elapsed': claim['elapsed'],
            'heartbeat_iso': claim['heartbeat_iso'],
            'session_id': claim['session_id'],
            'age_seconds': age,
            'health': health,
        })

    # IPs in pending/skip section — known but not yet assigned; don't re-prompt.
    md = Path(args.fleet_status).read_text(encoding='utf-8')
    pending_ips = set(re.findall(r'10\.179\.\d+\.1', md[md.find('Pending'):] if 'Pending' in md else ''))

    # Unified sweep: probe all 256 10.179.X.1 addresses in parallel.
    all_candidates = [f'10.179.{i}.1' for i in range(256)]
    with ThreadPoolExecutor(max_workers=64) as ex:
        all_results = list(ex.map(lambda ip: probe_tcp(ip, 22, args.timeout), all_candidates))

    reachable, unreachable, needs_assignment = [], [], []
    for ip, ok in zip(all_candidates, all_results):
        if ip in known_by_ip:
            t = dict(known_by_ip[ip])
            t['stage'] = infer_stage(t['next_action'])
            (reachable if ok else unreachable).append(t)
        elif ok and ip not in pending_ips and not args.no_discover:
            needs_assignment.append(ip)

    rec_train, rec_rationale = recommend(reachable)

    dispatchable = [t for t in reachable if not (t['status'].startswith('🟢') or 'DONE' in t['status'].upper())]
    train_list = ','.join(t['train_number'] for t in dispatchable)
    would_be_cmd = f'/dosto-orchestrate trains={train_list}' if dispatchable else '(no reachable trains)'

    html = render_html(reachable, unreachable, needs_assignment, rec_train, rec_rationale, would_be_cmd, in_flight)
    out_path = Path(args.out).resolve()
    out_path.write_text(html, encoding='utf-8')

    print(f"Written: {out_path}")
    print(f"Would-be command: {would_be_cmd}")
    print()
    if in_flight:
        print(f"Currently in flight ({len(in_flight)}):")
        health_icon = {'fresh': '🟢', 'lagging': '🟡', 'stale': '🔴', 'unknown': '❔'}
        for f in in_flight:
            step_str = f"{f['step']}/{f['total']}" if f['step'] is not None else '-/-'
            age_str = f"{f['age_seconds']//60}m" if f['age_seconds'] is not None else '?'
            fzg_str = f"Fzg {f['fzg']:>3}" if f['fzg'] else "Fzg ❓ "
            print(f"  {health_icon[f['health']]} {f['train_number']:<10} ({fzg_str}) stage={f['stage']:<28} {step_str:<7} t+{f['elapsed']:<5} hb={age_str:<5} ago, sess {f['session_id']}")
        print()
    print(f"Reachable ({len(reachable)}):")
    for t in reachable:
        marker = ' <- RECOMMENDED' if t['train_number'] == rec_train else ''
        fzg_str = f"Fzg {t['fzg']:>3}" if t['fzg'] else "Fzg ❓ "
        print(f"  {t['train_number']:<10} ({fzg_str}, {t['ip']:<14}) stage={t['stage']:<28} next: {t['next_action'][:60]}{marker}")
    print(f"Unreachable ({len(unreachable)}): {', '.join(t['train_number'] for t in unreachable) or '(none)'}")
    if not args.no_discover:
        print(f"Discovered new CCUs not in fleet-status ({len(needs_assignment)}): {', '.join(needs_assignment) or '(none)'}")
        if needs_assignment:
            print()
            print("===== GATE: Train# assignment needed =====")
            print("For each IP, run one of:")
            print("  python scripts/dosto_morning_brief.py --assign <IP> <TRAIN#> [--fzg N]   # e.g. --assign 10.179.17.1 4706-103 --fzg 191")
            print("  python scripts/dosto_morning_brief.py --skip <IP>                       # add to Pending section")
    # Stale-claim gate — surface any IN PROGRESS rows whose heartbeat aged past 30 min.
    stale_claims = [f for f in in_flight if f['health'] == 'stale']
    if stale_claims:
        print()
        print("===== GATE: stale orchestration claims =====")
        print(f"Found {len(stale_claims)} train(s) marked IN PROGRESS with heartbeat > 30 min.")
        print("Likely means the orchestrator session that claimed them is dead.")
        print()
        for f in stale_claims:
            age_min = (f['age_seconds'] // 60) if f['age_seconds'] is not None else '?'
            fzg_str = f"Fzg {f['fzg']}" if f['fzg'] else "Fzg ❓"
            print(f"  🔴 {f['train_number']} ({fzg_str}, {f['ccu_ip']}):")
            print(f"     Claimed by session {f['session_id']} at stage {f['stage']} ({age_min} min ago)")
            print(f"     Last heartbeat: {f['heartbeat_iso']}")
        print()
        print("For each train, decide:")
        print("  [c]lean: python scripts/dosto_morning_brief.py --clean-stale-claim <TRAIN#>")
        print("     → flips Nomad status to 🟡 PAUSED with note 'stale claim auto-cleaned from <sess>'")
        print("  [k]eep: leave as-is (use if you know the session is just slow, not dead)")
        print("  [s]kip: tomorrow's brief will re-prompt")

    if rec_train:
        print(f"\nRecommendation: {rec_train} — {rec_rationale}")
    else:
        print("\nNo start-first recommendation: all reachable trains hit a gate or are BLOCKED.")

if __name__ == '__main__':
    main()
