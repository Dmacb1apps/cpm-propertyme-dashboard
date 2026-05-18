"""
download_active_inspections.py

Downloads the "Inspection With Complete Date" custom report as Excel.
Follows the same popup pattern as download_monthly_rent — navigates back
to the reports menu, clicks the Custom tab, then opens the report by name.

Call this AFTER the other reports have been downloaded (authenticated page required).

Usage:
    from download_active_inspections import download_active_inspections_excel
    excel_path = download_active_inspections_excel(page, download_dir="./downloads")
"""

from pathlib import Path
from playwright.sync_api import Page

MANAGER_URL  = "https://manager.propertyme.com"
REPORT_NAME  = "Inspection With Complete Date"


def download_active_inspections_excel(
    page: Page,
    download_dir: str = "./downloads",
    timeout_ms: int = 90_000,
) -> str:
    """
    Navigate back to the reports menu, open the custom Active Inspections
    report in a popup, and export it as Excel.

    Args:
        page:         An authenticated Playwright Page object (already logged in)
        download_dir: Directory to save the downloaded file
        timeout_ms:   Max time to wait for the download (ms)

    Returns:
        Path to the downloaded Excel file.
    """
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    # After download_inspections_due the page has navigated away — go back to home
    print("[active_inspections] Navigating back to reports menu...")
    page.goto(MANAGER_URL, wait_until="networkidle", timeout=30_000)
    page.locator("[data-test-id='reports-menu']").wait_for(state="visible", timeout=15_000)
    page.locator("[data-test-id='reports-menu']").click()
    page.wait_for_timeout(500)

    # Switch to the Custom tab
    print("[active_inspections] Clicking Custom tab...")
    page.get_by_role("tab", name="Custom").click()
    page.wait_for_timeout(500)

    # Open the report — PropertyMe opens custom reports in a popup
    print(f"[active_inspections] Opening '{REPORT_NAME}'...")
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name=REPORT_NAME).click()
    report = popup_info.value
    report.wait_for_load_state("domcontentloaded")

    try:
        report.wait_for_load_state("networkidle", timeout=20_000)
        print("[active_inspections] Report loaded (networkidle).")
    except Exception:
        print("[active_inspections] networkidle timed out — waiting 5s as fallback.")
        report.wait_for_timeout(5_000)

    # Wait for the Export button to appear (data must be rendered first)
    print("[active_inspections] Waiting for Export button...")
    report.wait_for_selector(
        "button:has-text('Export'), a:has-text('Export'), [class*='export']",
        timeout=30_000,
    )
    report.wait_for_timeout(2_000)

    # Start download listener before any clicks so we can't miss the event
    print("[active_inspections] Starting download...")
    save_path = str(Path(download_dir) / "active_inspections.xlsx")
    with report.expect_download(timeout=timeout_ms) as dl_info:
        report.click("button:has-text('Export'), a:has-text('Export')")
        report.wait_for_timeout(1_000)
        report.wait_for_selector("text=Export Excel", timeout=10_000)
        report.click("text=Export Excel")

    dl_info.value.save_as(save_path)
    report.close()

    print(f"[active_inspections] Saved to: {save_path}")
    return save_path
