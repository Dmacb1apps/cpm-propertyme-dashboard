"""
Downloads two PropertyMe reports for the current month:
  - Folio Ledger (PDF)
  - Monthly Property/Rent (Excel)

Logs in on every run using PROPERTYME_EMAIL, PROPERTYME_PASSWORD, and
PROPERTYME_TOTP_SECRET environment variables. No session file required.

Usage:
    python3 download_reports.py
"""

import os
import time
import pyotp
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(Path(__file__).parent / ".env")

SCRIPT_DIR       = Path(__file__).parent
DOWNLOADS_DIR    = SCRIPT_DIR / "downloads"
SYSTEM_DOWNLOADS = Path.home() / "Downloads"
# Navigating to manager.propertyme.com redirects to login when unauthenticated,
# then redirects back after successful login — keeping session cookies on the right domain.
MANAGER_URL      = "https://manager.propertyme.com"
HEADLESS         = os.environ.get("CI") == "true"


def this_month_range():
    today = date.today()
    start = today.replace(day=1)
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
    Drive to manager.propertyme.com which redirects to login when unauthenticated.
    Fills credentials, handles 2FA if prompted, then waits for redirect back.
    """
    email    = os.environ["PROPERTYME_EMAIL"]
    password = os.environ["PROPERTYME_PASSWORD"]

    print(f"  Email being used: {email[:5]}...")
    print(f"  Password loaded: {'yes' if password else 'NO - EMPTY'}")

    print(f"Navigating to {MANAGER_URL} (will redirect to login)...")
    page.goto(MANAGER_URL)
    page.wait_for_load_state("networkidle", timeout=20000)
    print(f"  Landed on: {page.url}")

    screenshot_path = SCRIPT_DIR / "debug_login_page.png"
    page.screenshot(path=str(screenshot_path))
    print(f"  Screenshot saved: {screenshot_path}")

    inputs = page.query_selector_all("input")
    print(f"  Found {len(inputs)} input field(s):")
    for inp in inputs:
        print("  INPUT:",
              inp.get_attribute("type"),
              inp.get_attribute("name"),
              inp.get_attribute("id"),
              inp.get_attribute("placeholder"))

    # Wait for the form to fully load
    page.wait_for_selector("input[type='email']", timeout=15000)

    inputs = page.query_selector_all("input")
    print(f"  Found {len(inputs)} input field(s):")
    for inp in inputs:
        print("  INPUT found:",
              inp.get_attribute("type"),
              inp.get_attribute("name"),
              inp.get_attribute("id"))

    # Fill email
    email_input = page.locator("input[type='email']")
    email_input.click()
    email_input.fill(email)
    page.wait_for_timeout(800)

    # Fill password
    password_input = page.locator("input[type='password']")
    password_input.click()
    password_input.fill(password)
    page.wait_for_timeout(800)

    # Submit
    btn = page.locator("button:has-text('Log in')")
    btn.wait_for(state="visible")
    btn.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    btn.click()

    page.wait_for_timeout(2000)
    page.screenshot(path=str(SCRIPT_DIR / "debug_after_submit.png"))
    print(f"  URL after submit: {page.url}")

    # Handle 2FA — PropertyMe redirects to /auth/verify
    page.wait_for_load_state("networkidle", timeout=20000)
    if "/auth/verify" in page.url:
        print("  2FA page detected.")
        page.screenshot(path=str(SCRIPT_DIR / "debug_2fa_page.png"))
        print(f"  Screenshot saved: debug_2fa_page.png")

        inputs = page.query_selector_all("input")
        print(f"  Found {len(inputs)} input(s) on 2FA page:")
        for inp in inputs:
            print("  2FA INPUT:",
                  inp.get_attribute("type"),
                  inp.get_attribute("name"),
                  inp.get_attribute("id"))

        code = pyotp.TOTP(os.environ["PROPERTYME_TOTP_SECRET"]).now()
        print(f"  Entering 2FA code: {code}")

        otp_boxes = page.locator("input[type='text']")
        otp_boxes.first.click()
        page.keyboard.type(code)
        page.wait_for_timeout(500)

        page.get_by_role("button", name="Log in").click()
        # Use a broad pattern — redirect may land on manager.propertyme.com with or without a path
        page.wait_for_url("*manager.propertyme.com*", timeout=30000)
        print(f"  After 2FA: {page.url}")
    else:
        print("  No 2FA page detected — waiting for manager redirect...")
        page.wait_for_url("*manager.propertyme.com*", timeout=20000)

    print(f"  Login complete — current URL: {page.url}")


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
            print("  WARNING: File not found via either mechanism.")

    report.close()


def main():
    DOWNLOADS_DIR.mkdir(exist_ok=True)
    start_date, end_date, iso_date = this_month_range()
    print(f"Downloads dir: {DOWNLOADS_DIR.resolve()}")
    print(f"Headless     : {HEADLESS}")
    print(f"Date range   : {start_date} → {end_date}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page    = context.new_page()

        try:
            login(page)

            # login() already landed us on manager.propertyme.com after redirect —
            # wait for the reports menu to appear without navigating again.
            print("Waiting for reports menu...")
            page.locator("[data-test-id='reports-menu']").wait_for(state="visible", timeout=15000)
            page.locator("[data-test-id='reports-menu']").click()
            page.wait_for_timeout(500)

            download_folio_ledger(page, start_date, end_date, iso_date, DOWNLOADS_DIR)
            download_monthly_rent(page, start_date, end_date, iso_date, DOWNLOADS_DIR)

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
