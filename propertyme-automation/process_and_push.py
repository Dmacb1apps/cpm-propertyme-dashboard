"""
Parses the latest Folio Ledger PDF and Monthly Rent Excel from downloads/,
then pushes the processed data to a Google Sheet called "CPM Portfolio Dashboard".

Requires credentials.json (Google service account) in this folder.
Run refresh_session.py + download_reports.py first to get fresh files.

Usage:
    python3 process_and_push.py
"""

import json
import os
import re
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pdfplumber
import gspread
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

COMPLEX_MAP = {
    "01": "Everton Ridge",
    "02": "Upper West Arana Hills",
    "03": "Greystone Terraces",
    "09": "Kingsbury Estate",
    "11": "Bunya Heights",
    "12": "Treetops at Everton",
    "13": "Everton Breeze",
    "14": "Trend Everton Park",
    "15": "Vue Taigum",
}

SCRIPT_DIR       = Path(__file__).parent
DOWNLOADS_DIR    = SCRIPT_DIR / "downloads"
CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"
SHEET_NAME       = "CPM Portfolio Dashboard"
JSON_OUTPUT      = SCRIPT_DIR.parent / "public" / "dashboard_data.json"

# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def latest_file(pattern):
    files = sorted(DOWNLOADS_DIR.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching '{pattern}' in {DOWNLOADS_DIR}/")
    return files[-1]


def complex_name(code):
    return COMPLEX_MAP.get(code, f"Complex {code}")


# ---------------------------------------------------------------------------
# Monthly Rent parser
# ---------------------------------------------------------------------------

def parse_monthly_rent(xlsx_path):
    """
    Excel structure:
      Col A (Unnamed:0): owner name on owner-header rows, NaN on property rows
      Col B (Property):  ref like "01.02 02/40 Bunya Rd..." on property rows
      Col C (Rent):      weekly rent amount

    Returns dict keyed by complex_code:
      { "complex_name", "unit_count", "avg_rent" }
    """
    df = pd.read_excel(xlsx_path)
    props = df[df["Property"].notna()].copy()
    props["complex_code"] = props["Property"].str.extract(r"^(\d{2})\.")

    result = {}
    for code, group in props.groupby("complex_code"):
        rents = group["Rent"].dropna()
        result[code] = {
            "complex_name": complex_name(code),
            "unit_count": len(rents),
            "avg_rent": round(float(rents.mean()), 2) if len(rents) > 0 else 0.0,
        }
    return result


# ---------------------------------------------------------------------------
# Folio Ledger parser
# ---------------------------------------------------------------------------

# Lines that carry no transaction data
_SKIP_RE = re.compile(
    r"^\d{2}/\d{2}/\d{4} \d+:\d+"          # page timestamp header
    r"|^(Folio Ledger|From \d|Owner folios)"
    r"|^Consolidated Property"
    r"|^PropertyMe \("
    r"|^Audit\s+Date\s+Ref"                 # column header row
    r"|^(Opening|Closing) Balance"
    r"|^Trust Acc"
)


def parse_folio_ledger(pdf_path):
    """
    PDF structure per owner:

      Header (two formats):
        "09.04 Hon Kong Benny Chan - (OWN00016) 09.04 04/79 Cartwright St ..."
        "Hanne Bragh Frederiksen - (OWN00023) 09.07 07/79 Cartwright St ..."

      Transactions:
        "{6-digit-audit} {date} {ref} {Type} {details...} ${amount} [${balance}]"
        Type is one of: Payment | Receipt | Withdrawal

    Rules:
      - Receipt  → credits  → rent_received
      - Payment  → debits   → bills
      - Withdrawal → debits → skip (owner disbursement, not a bill)

    Returns list of owner dicts sorted by unit_ref:
      { unit_ref, owner_name, complex_code, complex_name,
        rent_received, bills, net, flagged }
    """
    owners = {}
    current_unit = None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                line = line.strip()
                if not line or _SKIP_RE.search(line):
                    continue

                # --- Owner header ---
                # Both formats contain "(OWN\d+)" followed by the unit ref "XX.YY"
                owner_m = re.search(r"^(.*?)\s*-\s*\(OWN\d+\)\s+(\d{2})\.(\d+)", line)
                if owner_m:
                    raw_name    = owner_m.group(1).strip()
                    cx_code     = owner_m.group(2)
                    unit_num    = owner_m.group(3)
                    unit_ref    = f"{cx_code}.{unit_num}"
                    current_unit = unit_ref

                    # Strip leading "XX.YY " from name (format 1)
                    owner_name = re.sub(r"^\d{2}\.\d+\s+", "", raw_name).strip()

                    if unit_ref not in owners:
                        owners[unit_ref] = {
                            "unit_ref":     unit_ref,
                            "owner_name":   owner_name,
                            "complex_code": cx_code,
                            "complex_name": complex_name(cx_code),
                            "rent_received": 0.0,
                            "bills":         0.0,
                        }
                    continue

                if current_unit is None:
                    continue

                # --- Transaction line ---
                # Must start: {6-digit-audit} {date} {ref} {Type}
                tx_m = re.match(
                    r"^\d{6}\s+\S+\s+\S+\s+(Payment|Receipt|Withdrawal)\b",
                    line, re.IGNORECASE
                )
                if not tx_m:
                    continue

                tx_type = tx_m.group(1).lower()
                if tx_type == "withdrawal":
                    continue  # owner disbursement — not a bill

                # First dollar amount on the line = transaction amount
                amounts = re.findall(r"\$([\d,]+\.\d{2})", line)
                if not amounts:
                    continue
                amount = float(amounts[0].replace(",", ""))

                if tx_type == "receipt":
                    owners[current_unit]["rent_received"] += amount
                elif tx_type == "payment":
                    owners[current_unit]["bills"] += amount

    result = []
    for unit_ref in sorted(owners):
        d = owners[unit_ref]
        d["rent_received"] = round(d["rent_received"], 2)
        d["bills"]         = round(d["bills"], 2)
        d["net"]           = round(d["rent_received"] - d["bills"], 2)
        d["flagged"]       = d["bills"] > d["rent_received"]
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_summary(owner_data, rent_data):
    """One row per complex aggregating both data sources."""
    stats = defaultdict(lambda: {
        "owner_count": 0, "flagged_count": 0,
        "total_rent": 0.0, "total_bills": 0.0,
    })

    for o in owner_data:
        code = o["complex_code"]
        stats[code]["owner_count"]   += 1
        stats[code]["flagged_count"] += 1 if o["flagged"] else 0
        stats[code]["total_rent"]    += o["rent_received"]
        stats[code]["total_bills"]   += o["bills"]

    summary = []
    all_codes = sorted(set(list(stats.keys()) + list(rent_data.keys())))
    for code in all_codes:
        s = stats[code]
        r = rent_data.get(code, {})
        summary.append({
            "complex_name":  complex_name(code),
            "unit_count":    r.get("unit_count", 0),
            "avg_rent":      round(r.get("avg_rent", 0.0), 2),
            "owner_count":   s["owner_count"],
            "flagged_count": s["flagged_count"],
            "total_rent":    round(s["total_rent"], 2),
            "total_bills":   round(s["total_bills"], 2),
        })
    return summary


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

# CPM navy header / flagged red
_HEADER_FMT = {
    "backgroundColor": {"red": 0.118, "green": 0.165, "blue": 0.227},
    "textFormat": {
        "bold": True,
        "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
    },
}
_FLAGGED_FMT = {
    "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8},
}
_TIMESTAMP_FMT = {
    "textFormat": {
        "italic": True,
        "foregroundColor": {"red": 0.5, "green": 0.5, "blue": 0.5},
    }
}


def _col(n):
    """1-based column index → letter (1→A, 27→AA)."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _ensure_worksheet(spreadsheet, title, rows=500, cols=10):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title, rows=rows, cols=cols)


def write_sheet(ws, timestamp_str, headers, rows, flagged_indices=None):
    """
    Row 1: Last Updated timestamp (grey italic)
    Row 2: Column headers (CPM navy, white bold text)
    Row 3+: Data rows; flagged rows highlighted red
    """
    ws.clear()
    all_data = [[f"Last Updated: {timestamp_str}"], headers] + rows
    ws.update(range_name="A1", values=all_data, value_input_option="USER_ENTERED")

    last_col = _col(len(headers))

    # Collect all format requests and send as one batch call
    fmt_requests = [
        {"range": "A1",                  "format": _TIMESTAMP_FMT},
        {"range": f"A2:{last_col}2",     "format": _HEADER_FMT},
    ]
    if flagged_indices:
        for i in flagged_indices:
            row = i + 3  # +1 timestamp, +1 header, +1 for 1-based
            fmt_requests.append({"range": f"A{row}:{last_col}{row}", "format": _FLAGGED_FMT})

    ws.batch_format(fmt_requests)
    time.sleep(1)  # stay well inside Sheets API rate limits


# ---------------------------------------------------------------------------
# Xero financials
# ---------------------------------------------------------------------------

def _xero_find_label(rows, label):
    """
    Recursively find a Row or SummaryRow whose first cell exactly matches label.
    Returns the float value from the second cell, or None if not found.
    """
    for row in rows:
        rt = row.get("RowType")
        if rt in ("Row", "SummaryRow"):
            cells = row.get("Cells", [])
            if cells and cells[0].get("Value", "").strip() == label:
                try:
                    return float(cells[1].get("Value") or 0)
                except (IndexError, ValueError):
                    return 0.0
        elif rt == "Section":
            result = _xero_find_label(row.get("Rows", []), label)
            if result is not None:
                return result
    return None


def _xero_sum_keyword(rows, keyword):
    """
    Recursively sum all Row values whose first cell contains keyword (case-insensitive).
    Handles reports that split a category across multiple line items.
    """
    total = 0.0
    for row in rows:
        rt = row.get("RowType")
        if rt == "Row":
            cells = row.get("Cells", [])
            if cells and keyword.lower() in cells[0].get("Value", "").lower():
                try:
                    total += abs(float(cells[1].get("Value") or 0))
                except (IndexError, ValueError):
                    pass
        elif rt == "Section":
            total += _xero_sum_keyword(row.get("Rows", []), keyword)
    return total


def _xero_section_total(rows, title):
    """Return the SummaryRow value for a named section (used for Balance Sheet Bank total)."""
    for row in rows:
        if row.get("RowType") == "Section" and title.lower() in row.get("Title", "").lower():
            for sub in row.get("Rows", []):
                if sub.get("RowType") == "SummaryRow":
                    try:
                        return abs(float(sub["Cells"][1].get("Value") or 0))
                    except (IndexError, ValueError):
                        return 0.0
    return 0.0


def fetch_xero_data():
    """
    Refresh the Xero access token, pull MTD P&L and Balance Sheet,
    and return a financials dict. Returns None if credentials are missing.
    """
    client_id     = os.environ.get("XERO_CLIENT_ID")
    client_secret = os.environ.get("XERO_CLIENT_SECRET")
    refresh_token = os.environ.get("XERO_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("  Xero credentials not set — skipping financials.")
        return None

    # Get fresh access token
    token_resp = requests.post(
        "https://identity.xero.com/connect/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    # Get tenant ID
    connections = requests.get("https://api.xero.com/connections", headers=headers)
    connections.raise_for_status()
    tenant_id = connections.json()[0]["tenantId"]
    headers["Xero-Tenant-Id"] = tenant_id

    today     = date.today()
    from_date = today.replace(day=1).strftime("%Y-%m-%d")
    to_date   = today.strftime("%Y-%m-%d")

    # Profit & Loss
    pl_resp = requests.get(
        "https://api.xero.com/api.xro/2.0/Reports/ProfitAndLoss",
        headers=headers,
        params={"fromDate": from_date, "toDate": to_date},
    )
    pl_resp.raise_for_status()
    pl_rows = pl_resp.json()["Reports"][0].get("Rows", [])

    # "Total Income" and "Net Profit" appear as Row/SummaryRow cells in empty-title
    # sections — use exact label matching rather than section title matching.
    total_income   = _xero_find_label(pl_rows, "Total Income") or 0.0
    total_expenses = (
        (_xero_find_label(pl_rows, "Total Operating Expenses") or 0.0) +
        (_xero_find_label(pl_rows, "Total Non-operating Expenses") or 0.0)
    )
    net_profit      = _xero_find_label(pl_rows, "Net Profit") or 0.0

    # Sum all wage and interest lines (each category has multiple accounts)
    management_fees = _xero_find_label(pl_rows, "Management Fees") or 0.0
    wages           = _xero_sum_keyword(pl_rows, "wages")
    loan_interest   = _xero_sum_keyword(pl_rows, "interest")

    # Balance Sheet for cash position
    cash_balance = 0.0
    bs_resp = requests.get(
        "https://api.xero.com/api.xro/2.0/Reports/BalanceSheet",
        headers=headers,
        params={"date": to_date},
    )
    if bs_resp.ok:
        bs_rows = bs_resp.json()["Reports"][0].get("Rows", [])
        cash_balance = _xero_section_total(bs_rows, "Bank")

    return {
        "cash_balance":    round(cash_balance, 2),
        "total_income":    round(total_income, 2),
        "total_expenses":  round(total_expenses, 2),
        "net_profit":      round(net_profit, 2),
        "management_fees": round(management_fees, 2),
        "wages":           round(wages, 2),
        "loan_interest":   round(loan_interest, 2),
    }


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

_REVERSE_MAP = {v: k for k, v in COMPLEX_MAP.items()}


def save_json(summary, owner_data, financials=None):
    now = datetime.now()
    payload = {
        "updated": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "month":   now.strftime("%B %Y"),
        "complexes": [
            {
                "code":       _REVERSE_MAP.get(s["complex_name"], "??"),
                "name":       s["complex_name"],
                "owners":     s["owner_count"],
                "flagged":    s["flagged_count"],
                "avgRent":    round(s["avg_rent"]),
                "totalRent":  round(s["total_rent"], 2),
                "totalBills": round(s["total_bills"], 2),
            }
            for s in summary
        ],
        "flagged": [
            {
                "code":    o["unit_ref"],
                "complex": o["complex_name"],
                "name":    o["owner_name"],
                "rent":    o["rent_received"],
                "bills":   o["bills"],
                "net":     o["net"],
            }
            for o in sorted(owner_data, key=lambda o: o["net"])
            if o["flagged"]
        ],
        "allOwners": [
            {
                "code":    o["unit_ref"],
                "complex": o["complex_name"],
                "name":    o["owner_name"],
                "rent":    o["rent_received"],
                "bills":   o["bills"],
                "net":     o["net"],
            }
            for o in sorted(owner_data, key=lambda o: (o["complex_code"], o["unit_ref"]))
        ],
    }

    if financials:
        payload["financials"] = financials

    JSON_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(payload, indent=2))
    print(f"  Saved: {JSON_OUTPUT}")


# ---------------------------------------------------------------------------
# Push to Google Sheets
# ---------------------------------------------------------------------------

def push_to_sheets(summary, owner_data):
    gc = gspread.service_account(filename=str(CREDENTIALS_FILE))

    ss = gc.open(SHEET_NAME)

    ts = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    owner_cols = ["Complex", "Unit", "Owner", "Rent Received", "Bills", "Net Position"]

    def owner_row(o):
        return [
            o["complex_name"], o["unit_ref"], o["owner_name"],
            f"${o['rent_received']:,.2f}",
            f"${o['bills']:,.2f}",
            f"${o['net']:,.2f}",
        ]

    # --- Sheet 1: Summary ---
    ws = _ensure_worksheet(ss, "Summary")
    summary_cols = ["Complex", "Units", "Avg Rent", "Owners", "Flagged",
                    "Total Rent MTD", "Total Bills MTD"]
    summary_rows = [
        [
            s["complex_name"],
            s["unit_count"],
            f"${s['avg_rent']:,.0f}",
            s["owner_count"],
            s["flagged_count"],
            f"${s['total_rent']:,.2f}",
            f"${s['total_bills']:,.2f}",
        ]
        for s in summary
    ]
    flagged_summary = [i for i, s in enumerate(summary) if s["flagged_count"] > 0]
    write_sheet(ws, ts, summary_cols, summary_rows, flagged_summary)
    print("  Written: Summary")

    # --- Sheet 2: Flagged Owners ---
    ws = _ensure_worksheet(ss, "Flagged Owners")
    flagged = sorted([o for o in owner_data if o["flagged"]], key=lambda o: o["net"])
    write_sheet(ws, ts, owner_cols, [owner_row(o) for o in flagged],
                flagged_indices=list(range(len(flagged))))
    print("  Written: Flagged Owners")

    # --- Sheet 3: All Owners ---
    ws = _ensure_worksheet(ss, "All Owners")
    all_sorted = sorted(owner_data, key=lambda o: (o["complex_code"], o["unit_ref"]))
    flagged_all = [i for i, o in enumerate(all_sorted) if o["flagged"]]
    write_sheet(ws, ts, owner_cols, [owner_row(o) for o in all_sorted], flagged_all)
    print("  Written: All Owners")

    # Remove default "Sheet1" if present
    try:
        ss.del_worksheet(ss.worksheet("Sheet1"))
    except gspread.WorksheetNotFound:
        pass

    return ss.url


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== CPM Portfolio Dashboard ===\n")

    pdf_path  = latest_file("folio_ledger_*.pdf")
    xlsx_path = latest_file("monthly_rent_*.xlsx")
    print(f"Folio Ledger : {pdf_path.name}")
    print(f"Monthly Rent : {xlsx_path.name}\n")

    print("Parsing Monthly Rent Excel...")
    rent_data = parse_monthly_rent(xlsx_path)
    print(f"  {len(rent_data)} complexes\n")

    print("Parsing Folio Ledger PDF...")
    owner_data = parse_folio_ledger(pdf_path)
    flagged    = [o for o in owner_data if o["flagged"]]
    print(f"  {len(owner_data)} owners, {len(flagged)} flagged\n")

    summary = build_summary(owner_data, rent_data)

    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found — see setup steps below.")
        return

    print("Fetching Xero financials...")
    financials = fetch_xero_data()
    if financials:
        print(f"  Net profit: ${financials['net_profit']:,.2f}")
        print(f"  Cash balance: ${financials['cash_balance']:,.2f}")
    print()

    print("Saving dashboard_data.json...")
    save_json(summary, owner_data, financials)

    print("\nPushing to Google Sheets...")
    url = push_to_sheets(summary, owner_data)
    print(f"\nDone.  Dashboard: {url}")


if __name__ == "__main__":
    main()
