"""
Downloads two PropertyMe reports for the current month:
  - Folio Ledger (PDF)
  - Monthly Property/Rent (Excel)

Authenticates via full email/password/TOTP login under a non-headless
Chromium browser (via xvfb in CI), with Turnstile-retry logic shared with
test_xvfb_login.py. Session cookies (PROPERTYME_COOKIES, extract_cookies.py)
expired every 18-24h and required manual renewal — no longer used here, but
left in place as a manual rollback option.

Usage:
    python3 download_reports.py
"""

import os
import time
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from download_active_inspections import download_active_inspections_excel
from propertyme_login import login_with_retry

load_dotenv(Path(__file__).parent / ".env")

SCRIPT_DIR       = Path(__file__).parent
DOWNLOADS_DIR    = SCRIPT_DIR / "downloads"
SYSTEM_DOWNLOADS = Path.home() / "Downloads"
# Navigating to manager.propertyme.com redirects to login when unauthenticated,
# then redirects back after successful login — keeping session cookies on the right domain.
MANAGER_URL      = "https://manager.propertyme.com"


def this_month_range():
    today = date.today()
    start = today.replace(day=2)
    display = start.strftime("%d/%m/%Y"), today.strftime("%d/%m/%Y")
    iso_today = today.strftime("%Y-%m-%d")
    return display[0], display[1], iso_today


def set_date_field(page, selector, value):
    """Clear a date input and type the new value."""
    field = page.locator(selector)
    field.click()
    field.triple_click()
    field.type(value)
    field.press("Tab")


def login(page):
    """
    Full email/password/TOTP login, reusing the same Turnstile-detection
    and retry logic validated in test_xvfb_login.py (see propertyme_login.py).

    Requires PROPERTYME_EMAIL, PROPERTYME_PASSWORD, PROPERTYME_TOTP_SECRET
    env vars.
    """
    result = login_with_retry(page)
    if result != "success":
        screenshot_path = SCRIPT_DIR / "debug_login_failed.png"
        page.screenshot(path=str(screenshot_path))
        raise RuntimeError(
            f"PropertyMe login failed — final result: {result}. "
            f"Screenshot saved to {screenshot_path}"
        )

    print(f"  Login succeeded — current URL: {page.url}")


def dismiss_feature_popup(page):
    """
    PropertyMe occasionally shows a Product Fruits "New Features" promo
    modal right after login (e.g. "Switching to MePay Fast"), overlaying
    the page and intercepting clicks on report links/buttons underneath it
    (element seen blocking clicks: <div class="productfruits--container">).
    Dismiss it if present, using multiple strategies since its close-button
    markup isn't pinned down.
    """
    popup = page.locator("[class*='productfruits']")
    try:
        popup.first.wait_for(state="visible", timeout=3000)
    except Exception:
        return  # no popup — nothing to do

    print("  Feature announcement popup detected — dismissing...")
    for selector in [
        "[class*='productfruits'] button[aria-label='Close']",
        "[class*='productfruits'] [class*='close']",
        "[class*='productfruits'] svg",
    ]:
        try:
            page.locator(selector).first.click(timeout=3000)
            print(f"  Dismissed popup via: {selector}")
            page.wait_for_timeout(500)
            return
        except Exception:
            continue

    print("  No close button matched — falling back to Escape key.")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    if popup.count() > 0 and popup.first.is_visible():
        print("  Popup still visible after Escape — clicking outside it.")
        page.mouse.click(10, 10)
        page.wait_for_timeout(500)


def download_folio_ledger(page, start_date, end_date, iso_date, downloads_dir):
    print("  Opening Folio Ledger report...")
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="Folio Ledger").click()
    report = popup_info.value
    report.wait_for_load_state("domcontentloaded")

    try:
        report.wait_for_load_state("networkidle", timeout=15000)
        print("  Report loaded (networkidle).")
    except Exception:
        print("  networkidle timed out — waiting 3s as fallback.")
        report.wait_for_timeout(3000)

    if report.locator("input[placeholder*='date'], input[type='date']").count() >= 2:
        date_inputs = report.locator("input[placeholder*='date'], input[type='date']").all()
        set_date_field(report, date_inputs[0], start_date)
        set_date_field(report, date_inputs[1], end_date)

    filename  = f"folio_ledger_{iso_date}.pdf"
    save_path = downloads_dir / filename

    with report.expect_download() as dl_info:
        report.get_by_text("PDF").click()
    dl_info.value.save_as(save_path)

    print(f"  Saved: {save_path}")
    report.close()


def click_export_button(report):
    """Try multiple strategies to click the Export button."""
    btn = report.locator("button:has-text('Export')")
    try:
        btn.wait_for(state="visible", timeout=8000)
        print("  Found Export button via :has-text selector.")
        btn.first.click()
        return
    except Exception:
        pass

    try:
        report.get_by_role("button", name="Export").click(timeout=5000)
        print("  Found Export button via get_by_role.")
        return
    except Exception:
        pass

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

    try:
        report.wait_for_load_state("networkidle", timeout=15000)
        print("  Report loaded (networkidle).")
    except Exception:
        print("  networkidle timed out — waiting 3s as fallback.")
        report.wait_for_timeout(3000)

    if report.locator("input[placeholder*='date'], input[type='date']").count() >= 2:
        date_inputs = report.locator("input[placeholder*='date'], input[type='date']").all()
        set_date_field(report, date_inputs[0], start_date)
        set_date_field(report, date_inputs[1], end_date)

    filename  = f"monthly_rent_{iso_date}.xlsx"
    save_path = downloads_dir / filename

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
            raise RuntimeError(
                f"Monthly rent download failed — file not found via Playwright "
                f"expect_download OR ~/Downloads fallback. "
                f"Expected: {save_path}"
            )

    report.close()


INSPECTION_REPORT_URL = (
    "https://manager.propertyme.com/reporting/#/Properties/"
    "PropertyDetailsReport/a8e30508-f824-4993-a50e-1957a2a4d9dd/true"
)


def download_inspections_due(page, downloads_dir):
    """Download the Inspections - Properties Due report as Excel (sync)."""
    print("  Opening Inspections Due report...")
    save_path = downloads_dir / "inspections_due.xlsx"

    page.goto(INSPECTION_REPORT_URL, wait_until="networkidle", timeout=30000)

    # Wait for the Export button — signals report data has rendered
    page.wait_for_selector(
        "button:has-text('Export'), a:has-text('Export'), [class*='export']",
        timeout=30000,
    )
    page.wait_for_timeout(2000)  # Angular/React reports need a moment after button appears

    print("  Clicking Export...")
    page.click("button:has-text('Export'), a:has-text('Export')")
    page.wait_for_selector("text=Export Excel", timeout=10000)

    print("  Selecting Export Excel...")
    with page.expect_download(timeout=30000) as dl_info:
        page.click("text=Export Excel")
    dl_info.value.save_as(save_path)

    print(f"  Saved: {save_path}")


def main():
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    start_date, end_date, iso_date = this_month_range()
    print(f"Downloads dir: {DOWNLOADS_DIR.resolve()}")
    print(f"Date range   : {start_date} → {end_date}")

    with sync_playwright() as p:
        # Must run non-headless (Cloudflare Turnstile blocks headless login) —
        # in CI this requires the workflow to wrap this script with xvfb-run.
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page    = context.new_page()

        try:
            login(page)

            # login() already landed us on manager.propertyme.com after redirect —
            # wait for the reports menu to appear without navigating again.
            print("Waiting for reports menu...")
            page.locator("[data-test-id='reports-menu']").wait_for(state="visible", timeout=15000)
            page.locator("[data-test-id='reports-menu']").click()
            page.wait_for_timeout(500)
            dismiss_feature_popup(page)

            download_folio_ledger(page, start_date, end_date, iso_date, DOWNLOADS_DIR)
            download_monthly_rent(page, start_date, end_date, iso_date, DOWNLOADS_DIR)
            download_inspections_due(page, DOWNLOADS_DIR)
            download_active_inspections_excel(page, download_dir=str(DOWNLOADS_DIR))

        except Exception as e:
            screenshot_path = SCRIPT_DIR / "debug_screenshot.png"
            page.screenshot(path=str(screenshot_path))
            print(f"ERROR: {e}")
            print(f"Screenshot saved to {screenshot_path}")
            raise

        context.close()
        browser.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
