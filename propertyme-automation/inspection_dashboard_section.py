"""
Generates the HTML section for the inspection monitor dashboard.
Drop this into process_and_push.py and call generate_inspection_html(data)
"""

def generate_inspection_html(inspection_data: dict) -> str:
    """
    Takes the dict returned by parse_inspections_due()
    and returns an HTML string for the dashboard card.
    """
    overdue   = inspection_data['overdue']
    no_date   = inspection_data['no_date']
    by_mgr    = inspection_data['by_manager']
    total     = inspection_data['total_properties']
    rep_date  = inspection_data['report_date']

    # Overdue rows
    if overdue:
        rows_html = ""
        for p in overdue:
            days = p['days_overdue']
            # Severity colour: >21d = deep red, 8-21 = orange, 1-7 = amber
            if days > 21:
                badge_style = "background:#CC0000;color:#fff"
                row_style   = "border-left:4px solid #CC0000"
            elif days > 7:
                badge_style = "background:#e07b00;color:#fff"
                row_style   = "border-left:4px solid #e07b00"
            else:
                badge_style = "background:#c9a800;color:#111"
                row_style   = "border-left:4px solid #c9a800"

            prop    = p['property']
            mgr     = p['manager'].split()[0]          # first name only
            due     = p['due_date']
            tenant  = p['tenant'][:45] + '…' if len(p['tenant']) > 45 else p['tenant']

            rows_html += f"""
        <div class="insp-row" style="{row_style}">
          <div class="insp-left">
            <div class="insp-prop">{prop}</div>
            <div class="insp-tenant">{tenant}</div>
          </div>
          <div class="insp-right">
            <span class="insp-badge" style="{badge_style}">{days}d overdue</span>
            <span class="insp-mgr">{mgr}</span>
          </div>
        </div>"""
        overdue_section = f"""
      <div class="insp-alert-header">
        ⚠️ {len(overdue)} propert{'y' if len(overdue)==1 else 'ies'} overdue — action required
      </div>
      {rows_html}"""
    else:
        overdue_section = """
      <div class="insp-all-clear">
        ✅ All inspections are on schedule
      </div>"""

    # No-date warnings (skip body corp / SSKB rows)
    real_no_date = [x for x in no_date if 'BODY' not in x['property'] and 'SSKB' not in x['property']]
    no_date_html = ""
    if real_no_date:
        nd_items = "".join(f"<li>{x['property']} ({x['manager'].split()[0]})</li>" for x in real_no_date)
        no_date_html = f"""
      <div class="insp-nodate">
        <strong>⚠️ No due date set:</strong>
        <ul>{nd_items}</ul>
      </div>"""

    # Manager summary pills
    mgr_pills = ""
    for mgr, stats in by_mgr.items():
        first = mgr.split()[0]
        od    = stats['overdue']
        pill_style = "background:#CC0000;color:#fff" if od > 0 else "background:#2a6e3f;color:#fff"
        mgr_pills += f"""
        <span class="insp-pill" style="{pill_style}">
          {first}: {od} overdue / {stats['total']} total
        </span>"""

    return f"""
  <!-- INSPECTION MONITOR SECTION -->
  <style>
    .insp-card          {{ background:#1e2530; border-radius:10px; padding:18px 20px; margin:18px 0; }}
    .insp-card-header   {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
    .insp-card-title    {{ font-size:15px; font-weight:700; color:#e0e6ef; letter-spacing:.3px; }}
    .insp-card-tag      {{ font-size:11px; color:#8a95a3; background:#252d3a; padding:3px 8px; border-radius:4px; }}
    .insp-alert-header  {{ font-size:13px; font-weight:600; color:#ff6b6b; margin-bottom:10px; padding:8px 10px;
                           background:rgba(204,0,0,.12); border-radius:6px; }}
    .insp-all-clear     {{ font-size:13px; color:#4ade80; padding:10px; background:rgba(74,222,128,.08);
                           border-radius:6px; margin-bottom:10px; }}
    .insp-row           {{ display:flex; justify-content:space-between; align-items:center;
                           padding:9px 12px; margin:5px 0; background:#252d3a;
                           border-radius:6px; gap:10px; }}
    .insp-left          {{ flex:1; min-width:0; }}
    .insp-prop          {{ font-size:12.5px; font-weight:600; color:#c8d3e0;
                           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .insp-tenant        {{ font-size:11px; color:#6b7a8d; margin-top:2px;
                           white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .insp-right         {{ display:flex; align-items:center; gap:8px; flex-shrink:0; }}
    .insp-badge         {{ font-size:11px; font-weight:700; padding:3px 8px;
                           border-radius:12px; white-space:nowrap; }}
    .insp-mgr           {{ font-size:11px; color:#8a95a3; white-space:nowrap; }}
    .insp-pills         {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }}
    .insp-pill          {{ font-size:11px; font-weight:600; padding:4px 10px;
                           border-radius:12px; white-space:nowrap; }}
    .insp-nodate        {{ font-size:11px; color:#8a95a3; margin-top:10px;
                           padding:8px 10px; background:#252d3a; border-radius:6px; }}
    .insp-nodate ul     {{ margin:4px 0 0 14px; padding:0; }}
    .insp-nodate li     {{ margin-top:2px; }}
  </style>

  <div class="insp-card">
    <div class="insp-card-header">
      <span class="insp-card-title">🏠 Inspection Monitor</span>
      <span class="insp-card-tag">As at {rep_date} · {total} properties</span>
    </div>
    {overdue_section}
    {no_date_html}
    <div class="insp-pills">
      {mgr_pills}
    </div>
  </div>
  <!-- END INSPECTION MONITOR -->
"""


# ── Quick test ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, '/home/claude')
    from parse_inspections import parse_inspections_due

    data = parse_inspections_due(
        '/mnt/user-data/uploads/Properties-Inspections_-_Properties_Due_2026-05-15_.xlsx'
    )
    html = generate_inspection_html(data)
    # Write a quick preview
    with open('/mnt/user-data/outputs/inspection_preview.html', 'w') as f:
        f.write(f"""<!DOCTYPE html><html><head>
<meta charset="utf-8">
<style>body{{background:#151c27;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
padding:20px;color:#e0e6ef;}}</style></head><body>
{html}
</body></html>""")
    print("Preview written to inspection_preview.html")
    print(f"\nSummary: {data['overdue_count']} overdue, {data['upcoming_count']} due within 30d")
