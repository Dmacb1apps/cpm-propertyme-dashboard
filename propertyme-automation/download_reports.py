"""
Downloads two PropertyMe reports for the current month:
  - Folio Ledger (PDF)
  - Monthly Property/Rent (Excel)

Requires a valid session.json created by refresh_session.py.
Files are saved to the downloads/ folder with a date-stamped filename.

Usage:
    python3 download_reports.py
"""

import os
import time
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR     = Path(__file__).parent
SESSION_FILE   = SCRIPT_DIR / "session.json"
DOWNLOADS_DIR  = SCRIPT_DIR / "downloads"
SYSTEM_DOWNLOADS = Path.home() / "Downloads"
BASE_URL = "https://manager.propertyme.com/#/"
HEADLESS = os.environ.get("CI") == "true"


def this_month_range():
    today = date.today()
    start = today.replace(day=1)
    # display format for PropertyMe date fields
    display = start.strftime("%d/%m/%Y"), today.strftime("%d/%m/%Y")
    # ISO format for filenames: 2026-05-13
    iso_today = today.strftime("%Y-%m-%d")
    return display[0], display[1], iso_today


def set_date_field(page, selector, value):
    """Clear a date input and type the new value."""
    field = page.locator(selector)
    field.click()
    field.triple_click()
    field.type(value)
    field.press("Tab")


def download_folio_ledger(page, start_date, end_date, iso_date, downloads_dir):
    print("  Opening Folio Ledger report...")
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="Folio Ledger").click()
    report = popup_info.value
    report.wait_for_load_state("domcontentloaded")

    # Wait for the report content to fully render before exporting
    try:
        report.wait_for_load_state("networkidle", timeout=15000)
        print("  Report loaded (networkidle).")
    except Exception:
        print("  networkidle timed out — waiting 3s as fallback.")
        report.wait_for_timeout(3000)

    # Set date range if date fields are present
    if report.locator("input[placeholder*='date'], input[type='date']").count() >= 2:
        date_inputs = report.locator("input[placeholder*='date'], input[type='date']").all()
        set_date_field(report, date_inputs[0], start_date)
        set_date_field(report, date_inputs[1], end_date)

    filename = f"folio_ledger_{iso_date}.pdf"
    save_path = downloads_dir / filename

    with report.expect_download() as dl_info:
        report.get_by_text("PDF").click()
    dl_info.value.save_as(save_path)

    print(f"  Saved: {save_path}")
    report.close()


def click_export_button(report):
    """Try multiple strategies to click the Export button."""
    # Strategy 1: role=button with exact name
    btn = report.locator("button:has-text('Export')")
    try:
        btn.wait_for(state="visible", timeout=8000)
        print("  Found Export button via :has-text selector.")
        btn.first.click()
        return
    except Exception:
        pass

    # Strategy 2: get_by_role
    try:
        report.get_by_role("button", name="Export").click(timeout=5000)
        print("  Found Export button via get_by_role.")
        return
    except Exception:
        pass

    # Strategy 3: get_by_text (broader match)
    try:
        report.get_by_text("Export", exact=True).click(timeout=5000)
        print("  Found Export button via get_by_text.")
        return
    except Exception:
        pass

    raise RuntimeError("Could not find or click the Export button after all strategies.")


def click_export_excel(report):
    """Try multiple strategies to click the Export Excel option."""
    for selector in [
        "a:has-text('Export Excel')",
        "li:has-text('Export Excel')",
        "span:has-text('Export Excel')",
        "[class*='export']:has-text('Excel')",
    ]:
        try:
            el = report.locator(selector)
            el.wait_for(state="visible", timeout=5000)
            print(f"  Found Export Excel via: {selector}")
            el.first.click()
            return
        except Exception:
            continue

    # Final fallback: get_by_role link
    try:
        report.get_by_role("link", name="Export Excel").click(timeout=5000)
        print("  Found Export Excel via get_by_role link.")
        return
    except Exception:
        pass

    raise RuntimeError("Could not find or click Export Excel after all strategies.")


def download_monthly_rent(page, start_date, end_date, iso_date, downloads_dir):
    print("  Opening Monthly Property/Rent report...")
    page.get_by_role("tab", name="Custom").click()

    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="Monthly Property/Rent").click()
    report = popup_info.value
    report.wait_for_load_state("domcontentloaded")

    # Wait for report data to load before interacting
    try:
        report.wait_for_load_state("networkidle", timeout=15000)
        print("  Report loaded (networkidle).")
    except Exception:
        print("  networkidle timed out — waiting 3s as fallback.")
        report.wait_for_timeout(3000)

    # Set date range if date fields are present
    if report.locator("input[placeholder*='date'], input[type='date']").count() >= 2:
        date_inputs = report.locator("input[placeholder*='date'], input[type='date']").all()
        set_date_field(report, date_inputs[0], start_date)
        set_date_field(report, date_inputs[1], end_date)

    filename = f"monthly_rent_{iso_date}.xlsx"
    save_path = downloads_dir / filename

    # Use expect_download to catch the file, with filesystem fallback.
    # Snapshot ~/Downloads first so we can detect it either way.
    before = set(SYSTEM_DOWNLOADS.glob("*.xlsx"))

    try:
        with report.expect_download(timeout=30000) as dl_info:
            click_export_button(report)
            click_export_excel(report)
        dl_info.value.save_as(save_path)
        print(f"  Saved: {save_path}")
    except Exception as e:
        print(f"  expect_download did not fire ({e.__class__.__name__}) — checking ~/Downloads...")
        new_file = None
        for _ in range(40):  # up to 20s
            time.sleep(0.5)
            after = set(SYSTEM_DOWNLOADS.glob("*.xlsx"))
            new_files = after - before
            if new_files:
                new_file = max(new_files, key=lambda f: f.stat().st_mtime)
                break
        if new_file:
            new_file.rename(save_path)
            print(f"  Saved (moved from ~/Downloads): {save_path}")
        else:
            print("  WARNING: File not found via either mechanism.")

    report.close()


def main():
    if not SESSION_FILE.exists():
        print(f"No session found at {SESSION_FILE}. Run refresh_session.py first.")
        return

    DOWNLOADS_DIR.mkdir(exist_ok=True)
    start_date, end_date, iso_date = this_month_range()
    print(f"Session file : {SESSION_FILE}")
    print(f"Downloads dir: {DOWNLOADS_DIR.resolve()}")
    print(f"Headless     : {HEADLESS}")
    print(f"Date range   : {start_date} → {end_date}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        page.goto(BASE_URL)
        page.wait_for_load_state("domcontentloaded")
        page.locator("[data-test-id='reports-menu']").wait_for(state="visible", timeout=15000)
        page.locator("[data-test-id='reports-menu']").click()
        page.wait_for_timeout(500)

        download_folio_ledger(page, start_date, end_date, iso_date, DOWNLOADS_DIR)
        download_monthly_rent(page, start_date, end_date, iso_date, DOWNLOADS_DIR)

        context.close()
        browser.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
