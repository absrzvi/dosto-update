import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
import pandas as pd
from datetime import datetime

md = Path('fleet-status.md').read_text(encoding='utf-8')

def parse_table(text, header):
    idx = text.find(header)
    if idx == -1:
        return []
    section = text[idx:]
    rows = []
    in_table = False
    for line in section.split('\n'):
        if re.match(r'^\|[-| ]+\|$', line):
            in_table = True
            continue
        if in_table:
            if not line.startswith('|'):
                break
            cols = [c.strip() for c in line.split('|')[1:-1]]
            if len(cols) >= 5:
                rows.append(cols)
    return rows

rows_4736 = parse_table(md, '### 4736 series')
rows_4734 = parse_table(md, '### 4734 series')

def status_class(status_cell):
    s = status_cell.lower()
    if 'done' in s or '✅' in status_cell:
        return 'done'
    if 'blocked' in s or '\U0001f534' in status_cell:
        return 'blocked'
    if 'paused' in s or '\U0001f7e1' in status_cell:
        return 'paused'
    if 'progress' in s or '\U0001f535' in status_cell:
        return 'inprogress'
    return 'unknown'

def clean(text):
    t = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    return t.strip()

STATUS_LABELS = {
    'done':       ('DONE',        '#22c55e'),
    'blocked':    ('BLOCKED',     '#ef4444'),
    'paused':     ('PAUSED',      '#eab308'),
    'inprogress': ('IN PROGRESS', '#3b82f6'),
    'unknown':    ('UNKNOWN',     '#94a3b8'),
}

def status_badge(status_cell):
    cls = status_class(status_cell)
    label, color = STATUS_LABELS[cls]
    return f'<span class="badge" style="background:{color}">{label}</span>'

def fleet_row_html(cols):
    fzg        = cols[0]
    trainset   = cols[1]
    ccu        = clean(cols[2]) if len(cols) > 2 else ''
    status_cell= cols[3]        if len(cols) > 3 else ''
    next_action= clean(cols[4]) if len(cols) > 4 else ''
    badge = status_badge(status_cell)
    if ccu in ('', '❓', '?'):
        ccu_display = '<span style="color:#475569">—</span>'
    else:
        ccu_display = f'<span class="mono">{ccu}</span>'
    return (
        f'<tr class="row-{status_class(status_cell)}">'
        f'<td class="mono center">{fzg}</td>'
        f'<td class="mono">{trainset}</td>'
        f'<td>{ccu_display}</td>'
        f'<td>{badge}</td>'
        f'<td class="small">{next_action}</td>'
        f'</tr>'
    )

# Cable issues
df = pd.read_excel('trackers/cable-issues-tracker.xlsx', sheet_name=0)
cable_rows = df.dropna(subset=['ID']).copy()
cable_rows = cable_rows[cable_rows['ID'].apply(lambda x: str(x).replace('.0','').isdigit())]

def issue_row_html(row):
    id_     = int(float(row['ID']))
    trainset= str(row['Trainset'])
    consist = str(row['Consist'])
    link    = str(row['Switch / Link'])
    ports   = str(row['Port(s)'])
    fault   = str(row['Fault Type'])
    action  = str(row['Required Action'])
    if len(action) > 130:
        action = action[:130] + '…'
    status  = str(row['Status'])
    df_date = row['Date Found']
    if hasattr(df_date, 'strftime'):
        date_str = df_date.strftime('%Y-%m-%d')
    else:
        s = str(df_date)
        date_str = s[:10] if s and s != 'nan' else '—'
    sc = '#ef4444' if status == 'OPEN' else '#22c55e'
    badge = f'<span class="badge" style="background:{sc}">{status}</span>'
    return (
        f'<tr>'
        f'<td class="mono center">{id_}</td>'
        f'<td class="mono">{trainset}</td>'
        f'<td class="small">{consist}</td>'
        f'<td class="small">{link}</td>'
        f'<td class="small mono">{ports}</td>'
        f'<td><span class="fault-tag">{fault}</span></td>'
        f'<td class="small">{action}</td>'
        f'<td>{badge}</td>'
        f'<td class="small">{date_str}</td>'
        f'</tr>'
    )

all_fleet = rows_4736 + rows_4734
stat_counts = {k: 0 for k in STATUS_LABELS}
for r in all_fleet:
    stat_counts[status_class(r[3] if len(r) > 3 else '')] += 1

open_issues = int((cable_rows['Status'] == 'OPEN').sum())
now = datetime.now().strftime('%Y-%m-%d %H:%M')

fleet_4736_html = '\n'.join(fleet_row_html(r) for r in rows_4736)
fleet_4734_html = '\n'.join(fleet_row_html(r) for r in rows_4734)
cable_html      = '\n'.join(issue_row_html(r) for _, r in cable_rows.iterrows())

CSS = """
  :root {
    --bg: #0f172a; --surface: #1e293b; --surface2: #273344;
    --border: #334155; --text: #e2e8f0; --text-muted: #94a3b8; --accent: #38bdf8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; }
  header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; }
  header h1 { font-size: 18px; font-weight: 700; color: var(--accent); letter-spacing: .05em; }
  header .subtitle { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
  header .updated { font-size: 11px; color: var(--text-muted); }
  .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }
  .stats-row { display: grid; grid-template-columns: repeat(6,1fr); gap: 12px; margin-bottom: 28px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
  .stat-card .num { font-size: 28px; font-weight: 700; }
  .stat-card .lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .05em; margin-top: 4px; }
  .section { margin-bottom: 32px; }
  .section-header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
  .section-header h2 { font-size: 16px; font-weight: 600; }
  .section-header .count { font-size: 12px; color: var(--text-muted); }
  .table-wrap { overflow-x: auto; border-radius: 8px; border: 1px solid var(--border); }
  table { width: 100%; border-collapse: collapse; }
  thead tr { background: var(--surface2); }
  thead th { padding: 10px 14px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); font-weight: 600; white-space: nowrap; border-bottom: 1px solid var(--border); }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--surface2); }
  td { padding: 9px 14px; vertical-align: top; }
  .row-done       { border-left: 3px solid #22c55e; }
  .row-paused     { border-left: 3px solid #eab308; }
  .row-blocked    { border-left: 3px solid #ef4444; }
  .row-inprogress { border-left: 3px solid #3b82f6; }
  .row-unknown    { border-left: 3px solid var(--border); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; color: #fff; letter-spacing: .04em; white-space: nowrap; }
  .fault-tag { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 11px; background: #1e3a5f; color: #93c5fd; border: 1px solid #2563eb44; }
  .mono { font-family: "Consolas","Courier New",monospace; font-size: 12px; }
  .small { font-size: 12px; color: var(--text-muted); }
  .center { text-align: center; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media (max-width: 900px) { .two-col { grid-template-columns: 1fr; } .stats-row { grid-template-columns: repeat(3,1fr); } }
"""

html_parts = [
    '<!DOCTYPE html>',
    '<html lang="en">',
    '<head>',
    '<meta charset="UTF-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
    '<title>DOSTO Fleet Dashboard</title>',
    f'<style>{CSS}</style>',
    '</head>',
    '<body>',
    f'''<header>
  <div>
    <h1>DOSTO Fleet Dashboard</h1>
    <div class="subtitle">Nomad Digital &middot; &Ouml;BB DOSTO NEU commissioning status</div>
  </div>
  <div class="updated">Generated {now}</div>
</header>''',
    '<div class="container">',

    # Stats
    f'''<div class="stats-row">
  <div class="stat-card"><div class="num" style="color:#22c55e">{stat_counts["done"]}</div><div class="lbl">Done</div></div>
  <div class="stat-card"><div class="num" style="color:#3b82f6">{stat_counts["inprogress"]}</div><div class="lbl">In Progress</div></div>
  <div class="stat-card"><div class="num" style="color:#eab308">{stat_counts["paused"]}</div><div class="lbl">Paused</div></div>
  <div class="stat-card"><div class="num" style="color:#ef4444">{stat_counts["blocked"]}</div><div class="lbl">Blocked</div></div>
  <div class="stat-card"><div class="num" style="color:#94a3b8">{stat_counts["unknown"]}</div><div class="lbl">Unknown</div></div>
  <div class="stat-card"><div class="num" style="color:#fb923c">{open_issues}</div><div class="lbl">Cable Issues Open</div></div>
</div>''',

    # Fleet side by side
    '<div class="two-col">',

    f'''<div class="section">
  <div class="section-header"><h2>4736 Series</h2><span class="count">{len(rows_4736)} trains</span></div>
  <div class="table-wrap"><table>
    <thead><tr><th>Fzg</th><th>Trainset</th><th>CCU IP</th><th>Status</th><th>Next Action</th></tr></thead>
    <tbody>{fleet_4736_html}</tbody>
  </table></div>
</div>''',

    f'''<div class="section">
  <div class="section-header"><h2>4734 Series</h2><span class="count">{len(rows_4734)} trains</span></div>
  <div class="table-wrap"><table>
    <thead><tr><th>Fzg</th><th>Trainset</th><th>CCU IP</th><th>Status</th><th>Next Action</th></tr></thead>
    <tbody>{fleet_4734_html}</tbody>
  </table></div>
</div>''',

    '</div>',  # .two-col

    # Cable issues
    f'''<div class="section">
  <div class="section-header"><h2>Cable Issues Register</h2><span class="count">{len(cable_rows)} total &middot; {open_issues} open</span></div>
  <div class="table-wrap"><table>
    <thead><tr><th>#</th><th>Trainset</th><th>Consist</th><th>Switch / Link</th><th>Port(s)</th><th>Fault Type</th><th>Required Action</th><th>Status</th><th>Found</th></tr></thead>
    <tbody>{cable_html}</tbody>
  </table></div>
</div>''',

    '</div>',  # .container
    '</body>',
    '</html>',
]

out = '\n'.join(html_parts)
Path('dashboard.html').write_text(out, encoding='utf-8')
print(f"Written dashboard.html ({len(out):,} bytes)")
print(f"Stats: {stat_counts}")
print(f"Open cable issues: {open_issues}")
