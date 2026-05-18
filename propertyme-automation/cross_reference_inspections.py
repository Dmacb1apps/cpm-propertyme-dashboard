"""
cross_reference_inspections.py

Two jobs:
  1. Cross-reference Properties Due (Report 3) against Active Inspections
     (Report 2) to correctly classify overdue properties.

  2. Check inspection frequency compliance across all active properties
     (target: 1 routine inspection every 17 weeks / ~3 per year).

Classification:
    OVERDUE    = past due date, no future booking
    SCHEDULED  = past due date, future booking already exists (not a real alarm)
    DONE       = left the due list with a Completed Date (legitimate)
    DELETED    = left the due list with no completion record (RED FLAG)

Frequency flags:
    LOW COUNT  = fewer than 3 routines in last 12 months of current tenancy
    LONG GAP   = more than 119 days (17 weeks) since last routine inspection
"""

import json
import pandas as pd
from datetime import date
from pathlib import Path


EXCLUSIONS_PATH = Path(__file__).parent / "property_exclusions.json"
OVERDUE_THRESHOLD_DAYS = 119   # 17 weeks


# ── Helpers ────────────────────────────────────────────────────────────────

def load_exclusions(path: Path = EXCLUSIONS_PATH) -> set:
    """Returns a set of excluded unit codes."""
    if not path.exists():
        return set()
    with open(path) as f:
        data = json.load(f)
    return {e["unit_code"] for e in data.get("excluded_properties", [])}


def extract_unit_code(property_str: str) -> str:
    """e.g. '12.31 31 / 36 Bunya Road...' → '12.31'"""
    if pd.isna(property_str):
        return ""
    return str(property_str).strip().split(" ")[0]


# ── Report loaders ─────────────────────────────────────────────────────────

def load_properties_due(path: str) -> pd.DataFrame:
    """
    Loads the Properties Due report (Report 3).
    Returns rows with: unit_code, property, inspection_due,
                       days_overdue, manager
    """
    raw = pd.read_excel(path, header=None)
    raw.columns = ["col0", "inspection_due", "frequency",
                   "property", "owner", "tenant", "manager"]

    df = raw[raw["inspection_due"].notna() & raw["col0"].isna()].copy()
    df["inspection_due"] = pd.to_datetime(df["inspection_due"])

    today = pd.Timestamp(date.today())
    df = df[df["inspection_due"] < today].copy()
    df["days_overdue"] = (today - df["inspection_due"]).dt.days
    df["unit_code"] = df["property"].apply(extract_unit_code)
    return df


def load_active_inspections(path: str) -> pd.DataFrame:
    """
    Loads the full Active Inspections report (Report 2).
    Columns: Date, Time, Property, Type, Assigned Manager,
             Status, Tenant, Completed Date
    """
    df = pd.read_excel(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Completed Date"] = pd.to_datetime(df["Completed Date"], errors="coerce")
    df["unit_code"] = df["Property"].apply(extract_unit_code)
    return df


# ── Job 1: Cross-reference overdue vs scheduled ────────────────────────────

def classify_overdue(due_df: pd.DataFrame,
                     active_df: pd.DataFrame,
                     exclusions: set) -> dict:
    """
    For each overdue property, check if a future Scheduled booking exists.
    Returns { overdue: [...], scheduled: [...] }
    """
    today = pd.Timestamp(date.today())

    # Future bookings in active report
    future_scheduled = active_df[
        (active_df["Status"] == "Scheduled") &
        (active_df["Date"] > today)
    ].copy()
    booked_units = set(future_scheduled["unit_code"].unique())

    overdue_list = []
    scheduled_list = []

    for _, row in due_df.iterrows():
        unit = row["unit_code"]
        if unit in exclusions:
            continue

        record = {
            "unit_code":    unit,
            "property":     row["property"],
            "manager":      row["manager"],
            "due_date":     row["inspection_due"].date().isoformat(),
            "days_overdue": int(row["days_overdue"]),
        }

        if unit in booked_units:
            booking = future_scheduled[
                future_scheduled["unit_code"] == unit
            ].sort_values("Date").iloc[0]
            record["booked_date"] = booking["Date"].date().isoformat()
            scheduled_list.append(record)
        else:
            overdue_list.append(record)

    return {
        "overdue":   sorted(overdue_list,   key=lambda x: x["days_overdue"], reverse=True),
        "scheduled": sorted(scheduled_list, key=lambda x: x["booked_date"]),
    }


# ── Job 2: Inspection frequency compliance ─────────────────────────────────

def check_frequency(active_df: pd.DataFrame, exclusions: set) -> list:
    """
    Flags properties falling behind on the 17-week inspection cadence.
    Only analyses properties where the current tenancy started 12+ months ago.
    Returns list of flagged properties sorted by days_since_last desc.
    """
    today = pd.Timestamp(date.today())
    one_year_ago = today - pd.Timedelta(days=365)

    routine = active_df[
        (active_df["Type"] == "Routine") &
        (active_df["Status"] == "Closed")
    ].copy()

    entries = active_df[active_df["Type"] == "Entry"].copy()
    latest_entry = (
        entries.groupby("unit_code")["Date"]
        .max()
        .reset_index()
        .rename(columns={"Date": "tenancy_start"})
    )

    # Only properties with tenancy 12+ months old
    eligible = latest_entry[latest_entry["tenancy_start"] <= one_year_ago]

    flagged = []
    for _, row in eligible.iterrows():
        unit = row["unit_code"]
        if unit in exclusions:
            continue

        start = row["tenancy_start"]
        prop_routines = routine[
            (routine["unit_code"] == unit) &
            (routine["Date"] >= start)
        ].sort_values("Date")

        count = len(prop_routines)
        months = (today - start).days / 30.44

        if count > 0:
            last_date = prop_routines["Date"].max()
            days_since = (today - last_date).days
            property_name = prop_routines["Property"].iloc[-1]
            manager = prop_routines["Assigned Manager"].iloc[-1]
        else:
            days_since = (today - start).days
            entry_row = entries[entries["unit_code"] == unit].sort_values("Date").iloc[-1]
            property_name = entry_row["Property"]
            manager = entry_row["Assigned Manager"]

        behind_count = count < 3 and months >= 12
        long_gap = days_since > OVERDUE_THRESHOLD_DAYS

        if not (behind_count or long_gap):
            continue

        if behind_count and long_gap:
            flag = "LOW COUNT + LONG GAP"
        elif behind_count:
            flag = "LOW COUNT"
        else:
            flag = "LONG GAP"

        flagged.append({
            "unit_code":                unit,
            "property":                 property_name,
            "manager":                  manager,
            "tenancy_months":           round(months, 1),
            "routine_inspections_done": count,
            "days_since_last_routine":  days_since,
            "flag":                     flag,
        })

    return sorted(flagged, key=lambda x: x["days_since_last_routine"], reverse=True)


# ── Main entry point ───────────────────────────────────────────────────────

def run_inspection_analysis(due_path: str, active_path: str) -> dict:
    """
    Full analysis. Call this from process_and_push.py.

    Returns a dict ready to merge into dashboard_data.json:
    {
        "inspections": {
            "overdue":    [...],
            "scheduled":  [...],
            "frequency_flags": [...],
            "summary": { ... }
        }
    }
    """
    exclusions  = load_exclusions()
    due_df      = load_properties_due(due_path)
    active_df   = load_active_inspections(active_path)

    classified      = classify_overdue(due_df, active_df, exclusions)
    frequency_flags = check_frequency(active_df, exclusions)

    overdue_count   = len(classified["overdue"])
    scheduled_count = len(classified["scheduled"])
    freq_flag_count = len(frequency_flags)

    # Per-manager summary
    by_manager = {}
    for p in classified["overdue"]:
        m = p["manager"]
        by_manager.setdefault(m, {"overdue": 0, "scheduled": 0, "frequency_flags": 0})
        by_manager[m]["overdue"] += 1
    for p in classified["scheduled"]:
        m = p["manager"]
        by_manager.setdefault(m, {"overdue": 0, "scheduled": 0, "frequency_flags": 0})
        by_manager[m]["scheduled"] += 1
    for p in frequency_flags:
        m = p["manager"]
        by_manager.setdefault(m, {"overdue": 0, "scheduled": 0, "frequency_flags": 0})
        by_manager[m]["frequency_flags"] += 1

    return {
        "inspections": {
            "overdue":         classified["overdue"],
            "scheduled":       classified["scheduled"],
            "frequency_flags": frequency_flags,
            "summary": {
                "total_overdue":         overdue_count,
                "total_scheduled":       scheduled_count,
                "total_frequency_flags": freq_flag_count,
                "by_manager":            by_manager,
            }
        }
    }


# ── Standalone test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json as _json

    due    = sys.argv[1] if len(sys.argv) > 1 else "./downloads/inspections_due.xlsx"
    active = sys.argv[2] if len(sys.argv) > 2 else "./downloads/active_inspections.xlsx"

    result = run_inspection_analysis(due, active)
    s = result["inspections"]["summary"]

    print(f"\nOverdue (real):     {s['total_overdue']}")
    print(f"Scheduled (booked): {s['total_scheduled']}")
    print(f"Frequency flags:    {s['total_frequency_flags']}")
    print("\nBy manager:")
    for mgr, counts in s["by_manager"].items():
        print(f"  {mgr}: {counts}")

    print("\nFull JSON written to inspection_analysis.json")
    with open("inspection_analysis.json", "w") as f:
        _json.dump(result, f, indent=2, default=str)
