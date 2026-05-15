"""
CPM Inspection Monitor - parse_inspections.py
Reads the PropertyMe "Inspections - Properties Due" Excel export
and returns structured data for the dashboard.
"""

import pandas as pd
from datetime import date
import json


def parse_inspections_due(filepath: str, today: date = None) -> dict:
    """
    Parse the PropertyMe 'Inspections - Properties Due' Excel report.
    Returns a dict ready for JSON serialisation and dashboard injection.
    """
    if today is None:
        today = date.today()

    today_ts = pd.Timestamp(today)

    df = pd.read_excel(filepath, header=0)
    df.columns = ['group_col', 'inspection_due', 'frequency', 'property', 'owner', 'tenant', 'manager']

    # Keep only real property rows
    data = df[
        df['property'].notna() &
        ~df['property'].str.startswith('Subtotal', na=False) &
        ~df['property'].str.startswith('Total', na=False) &
        df['manager'].notna()
    ].copy()

    data['inspection_due'] = pd.to_datetime(data['inspection_due'], errors='coerce')
    data['frequency'] = pd.to_numeric(data['frequency'], errors='coerce').fillna(0).astype(int)

    # Split into has-date and no-date
    has_date = data[data['inspection_due'].notna()].copy()
    no_date  = data[data['inspection_due'].isna()].copy()

    has_date['days_overdue'] = (today_ts - has_date['inspection_due']).dt.days

    overdue  = has_date[has_date['days_overdue'] > 0].sort_values('days_overdue', ascending=False)
    upcoming = has_date[(has_date['days_overdue'] <= 0) & (has_date['days_overdue'] >= -30)].sort_values('days_overdue', ascending=False)
    ok       = has_date[has_date['days_overdue'] < -30]

    def row_to_dict(r):
        return {
            'property':       r['property'],
            'manager':        r['manager'],
            'tenant':         r['tenant'] if pd.notna(r['tenant']) else '',
            'due_date':       str(r['inspection_due'])[:10],
            'frequency_wks':  int(r['frequency']),
            'days_overdue':   int(r['days_overdue']) if pd.notna(r.get('days_overdue')) else None,
        }

    return {
        'report_date':      str(today),
        'total_properties': len(data),
        'overdue_count':    len(overdue),
        'upcoming_count':   len(upcoming),
        'no_date_count':    len(no_date),
        'overdue':          [row_to_dict(r) for _, r in overdue.iterrows()],
        'upcoming':         [row_to_dict(r) for _, r in upcoming.iterrows()],
        'no_date':          [{'property': r['property'], 'manager': r['manager']} for _, r in no_date.iterrows()],
        'by_manager': {
            mgr: {
                'overdue':  int((overdue['manager'] == mgr).sum()),
                'upcoming': int((upcoming['manager'] == mgr).sum()),
                'total':    int((data['manager'] == mgr).sum()),
            }
            for mgr in data['manager'].dropna().unique()
        }
    }


if __name__ == '__main__':
    result = parse_inspections_due(
        '/mnt/user-data/uploads/Properties-Inspections_-_Properties_Due_2026-05-15_.xlsx'
    )
    print(json.dumps(result, indent=2))
