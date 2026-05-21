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
    """Pick the train with no gate in next 3 stages. Tie-break: longest runway."""
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
    return train['fzg'], rationale

def rationale_for(train, recommended_fzg):
    stage = train['stage']
    if stage == 'BLOCKED':
        return 'BLOCKED — Stadler-dependent'
    if stage == '?':
        return 'Next action prose unmapped — engineer review'
    upcoming = stages_remaining(stage)[:3]
    if not upcoming:
        return 'no upcoming stages'
    gate_in = next((i+1 for i, s in enumerate(upcoming) if s in GATES), None)
    if train['fzg'] == recommended_fzg:
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

PENDING_MARKER = '<!-- pending Fzg assignment (managed by dosto-morning-brief) -->'

def ip_already_known(path: str, ip: str) -> bool:
    """An IP is 'known' if it appears anywhere in fleet-status.md — either in
    a series table (assigned) or in the Pending section (skip-listed)."""
    return ip in Path(path).read_text(encoding='utf-8')

def append_to_pending(path: str, ip: str):
    """Add an IP to the 'Pending Fzg assignment' section. Engineer skipped it
    at the prompt; we record it so next morning's brief doesn't re-ask."""
    content = Path(path).read_text(encoding='utf-8')
    today = datetime.now().strftime('%Y-%m-%d')
    if PENDING_MARKER not in content:
        section = (
            f'\n\n{PENDING_MARKER}\n\n'
            f'## Pending Fzg assignment\n\n'
            f'CCU IPs discovered by morning-brief network sweep where the engineer '
            f'has not yet provided a Fzg ID. These are skip-listed (not re-prompted '
            f'next run). Hand-edit this section: delete the row and add a proper '
            f'entry to the 4736 or 4734 series table once you identify the train '
            f'(physical inspection or cross-ref against `train-ip-allocation-commission/` PDFs — '
            f'do NOT trust .cfg filenames or switch hostnames since the train_id formula '
            f'is broken pre-commissioning).\n\n'
            f'| CCU IP | Discovered |\n|---|---|\n'
        )
        content += section
    new_row = f'| `{ip}` | {today} |'
    content = content.rstrip() + '\n' + new_row + '\n'
    Path(path).write_text(content, encoding='utf-8')

def assign_to_series(path: str, ip: str, fzg: str, series: str):
    """Insert a new row into the 4736 or 4734 series table for an engineer-supplied
    (ip, fzg, series) triplet. Idempotent: skips if a row with this Fzg + IP exists."""
    content = Path(path).read_text(encoding='utf-8')
    if ip in content:
        return False
    header = f'### {series} series'
    idx = content.find(header)
    if idx == -1:
        raise ValueError(f'series header not found: {header}')
    # Find the end of this table (first blank line after the table starts).
    lines = content.split('\n')
    start_line = next(i for i, l in enumerate(lines) if l.startswith(header))
    # Walk forward to find the table, then to the first non-pipe line after rows begin.
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
    # Trainset hint: if 4736 series, trainset = fzg - 28; if 4734, trainset = fzg + 100.
    fzg_i = int(fzg)
    trainset = f'{series}-{fzg_i - 28:03d}' if series == '4736' else f'{series}-{fzg_i + 100:03d}'
    new_row = f'| {fzg} | {trainset} | `{ip}` | ⚪ UNKNOWN | ❓ | initial visit |'
    lines.insert(insert_at, new_row)
    Path(path).write_text('\n'.join(lines), encoding='utf-8')
    return True

def render_html(reachable, unreachable, discovered, recommended_fzg, recommended_rationale, would_be_cmd):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    date_str = datetime.now().strftime('%Y-%m-%d')
    rows = []
    for t in reachable:
        row_cls = 'recommended' if t['fzg'] == recommended_fzg else f'row-{status_class(t["status"])}'
        rationale = rationale_for(t, recommended_fzg)
        rec_cell = ('<strong style="color:#22c55e">YES</strong><br>' if t['fzg'] == recommended_fzg else 'no<br>') \
                   + f'<span class="small">{rationale}</span>'
        rows.append(
            f'<tr class="{row_cls}">'
            f'<td class="mono center">{t["fzg"]}</td>'
            f'<td class="mono">{t["trainset"]}</td>'
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
        un_lines = '<br>'.join(f'Fzg {t["fzg"]} / {t["trainset"]} ({t["ip"]}) — {t["next_action"][:80]}' for t in unreachable)
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
  <div class="updated">{now}<br><span style="color:var(--accent)">{len(reachable)} of {reach_total_known} known-CCU trains reachable</span></div>
</header>
<div class="container">

<div class="section">
  <div class="section-header"><h2>Reachable trains</h2><span class="count">{len(reachable)} online</span></div>
  <div class="table-wrap"><table>
    <thead><tr><th>Fzg</th><th>Trainset</th><th>CCU IP</th><th>Nomad status</th><th>Stadler status</th><th>Next Action</th><th>Resume Stage</th><th>Recommended?</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table></div>
</div>

<div class="section">
  <div class="section-header"><h2>To proceed, type:</h2>
    <span class="count">dry run &middot; not invoked</span></div>
  <div class="cmd-block">{would_be_cmd}</div>
  <div class="dry-run-note">
    {('Recommended start-first: <strong style="color:#22c55e">Fzg ' + str(recommended_fzg) + '</strong> &mdash; ' + recommended_rationale) if recommended_fzg else 'No train eligible for autonomous start-first (all reachable trains hit an approval gate within the next 3 stages or are BLOCKED).'}
  </div>
  <div class="dry-run-note">Paste the command above manually to dispatch. This page does not invoke /dosto-orchestrate.</div>
</div>

{('<div class="section"><div class="section-header"><h2>Discovered CCUs &mdash; awaiting Fzg assignment</h2><span class="count">' + str(len(discovered)) + ' new &middot; gate</span></div><div class="urlist" style="padding:12px 16px;background:var(--surface);border:1px solid #ef444466;border-radius:8px;">' + '<br>'.join(f"<code>{ip}</code> &mdash; <code>python scripts/dosto_morning_brief.py --assign {ip} &lt;FZG&gt; &lt;SERIES&gt;</code> or <code>--skip {ip}</code>" for ip in discovered) + '<br><br><span class="small">Engineer gate: identify Fzg ID via <strong>physical inspection</strong> or <strong>train-ip-allocation-commission/ PDFs</strong>. Do NOT trust .cfg filenames or switch hostnames &mdash; the <code>train_id</code> formula is broken pre-commissioning and renders the wrong Fzg in those names.</span></div></div>') if discovered else ''}

<details>
  <summary>Unreachable trains ({len(unreachable)} known-CCU, failed TCP/22 probe)</summary>
  <div class="urlist">{un_lines}</div>
</details>

</div></body></html>"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=5.0)
    ap.add_argument('--fleet-status', default='fleet-status.md')
    ap.add_argument('--out', default='morning-brief.html')
    ap.add_argument('--no-discover', action='store_true',
                    help='Skip the 10.179.x.1 discovery sweep')
    ap.add_argument('--assign', nargs=3, metavar=('IP', 'FZG', 'SERIES'),
                    help='Assign a discovered IP to a Fzg/series (engineer response to gate). '
                         'Writes a row to the matching series table. Repeatable via shell loop.')
    ap.add_argument('--skip', metavar='IP',
                    help='Skip-list a discovered IP (append to Pending section, do not re-prompt).')
    args = ap.parse_args()

    # Subcommands: --assign / --skip are write-only operations invoked by the skill
    # after the engineer answers the per-IP prompt. They short-circuit the brief.
    if args.assign:
        ip, fzg, series = args.assign
        ok = assign_to_series(args.fleet_status, ip, fzg, series)
        print(f'{"assigned" if ok else "already present"}: {ip} -> Fzg {fzg} / {series}')
        return
    if args.skip:
        append_to_pending(args.fleet_status, args.skip)
        print(f'skip-listed: {args.skip}')
        return

    md = Path(args.fleet_status).read_text(encoding='utf-8')

    trains_with_ip = []
    for header in ('### 4736 series', '### 4734 series'):
        hdr, rows = parse_table(md, header)
        if not hdr: continue
        i_fzg = col_idx(hdr, 'fzg') or 0
        i_trainset = col_idx(hdr, 'train')
        i_ccu = col_idx(hdr, 'ccu')
        # Nomad status replaced 'Status' on 2026-05-21; accept either name.
        i_status = col_idx(hdr, 'nomad status')
        if i_status is None: i_status = col_idx(hdr, 'status')
        i_stadler = col_idx(hdr, 'stadler')
        i_next = col_idx(hdr, 'next action')
        for r in rows:
            ip = extract_ip(clean(r[i_ccu])) if i_ccu is not None else None
            if not ip: continue
            trains_with_ip.append({
                'fzg': r[i_fzg],
                'trainset': clean(r[i_trainset]) if i_trainset is not None else '',
                'ip': ip,
                'status': r[i_status] if i_status is not None else '',
                'stadler': r[i_stadler] if i_stadler is not None else '',
                'next_action': clean(r[i_next]) if i_next is not None else '',
            })

    # Parallel TCP/22 probe
    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(lambda t: probe_tcp(t['ip'], 22, args.timeout), trains_with_ip))

    reachable, unreachable = [], []
    for t, ok in zip(trains_with_ip, results):
        t['stage'] = infer_stage(t['next_action'])
        (reachable if ok else unreachable).append(t)

    # Discovery sweep: 10.179.0.1 .. 10.179.255.1, minus already-known IPs.
    # IPs already in any section of fleet-status.md (series tables OR pending list)
    # are excluded. New IPs surface as `needs_assignment` for the engineer gate.
    discovered = []
    needs_assignment = []
    if not args.no_discover:
        fleet_content = Path(args.fleet_status).read_text(encoding='utf-8')
        candidates = [f'10.179.{i}.1' for i in range(256) if f'10.179.{i}.1' not in fleet_content]
        with ThreadPoolExecutor(max_workers=64) as ex:
            disc_results = list(ex.map(lambda ip: probe_tcp(ip, 22, args.timeout), candidates))
        discovered = [ip for ip, ok in zip(candidates, disc_results) if ok]
        needs_assignment = discovered[:]  # all discovered are new (already filtered above)

    rec_fzg, rec_rationale = recommend(reachable)

    fzg_list = ','.join(t['fzg'] for t in reachable)
    would_be_cmd = f'/dosto-orchestrate fzg={fzg_list}' if reachable else '(no reachable trains)'

    html = render_html(reachable, unreachable, needs_assignment, rec_fzg, rec_rationale, would_be_cmd)
    out_path = Path(args.out).resolve()
    out_path.write_text(html, encoding='utf-8')

    print(f"Written: {out_path}")
    print(f"Would-be command: {would_be_cmd}")
    print()
    print(f"Reachable ({len(reachable)}):")
    for t in reachable:
        marker = ' <- RECOMMENDED' if t['fzg'] == rec_fzg else ''
        print(f"  Fzg {t['fzg']:>3} / {t['trainset']:<8} ({t['ip']:<14}) stage={t['stage']:<28} next: {t['next_action'][:60]}{marker}")
    print(f"Unreachable ({len(unreachable)}): {', '.join(t['fzg'] for t in unreachable) or '(none)'}")
    if not args.no_discover:
        print(f"Discovered new CCUs not in fleet-status ({len(needs_assignment)}): {', '.join(needs_assignment) or '(none)'}")
        if needs_assignment:
            print()
            print("===== GATE: Fzg assignment needed =====")
            print("For each IP, run one of:")
            print("  python scripts/dosto_morning_brief.py --assign <IP> <FZG> <SERIES>   # e.g. --assign 10.179.17.1 145 4736")
            print("  python scripts/dosto_morning_brief.py --skip <IP>                    # add to Pending section")
    if rec_fzg:
        print(f"\nRecommendation: Fzg {rec_fzg} — {rec_rationale}")
    else:
        print("\nNo start-first recommendation: all reachable trains hit a gate or are BLOCKED.")

if __name__ == '__main__':
    main()
