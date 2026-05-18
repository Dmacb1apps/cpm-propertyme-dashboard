"""
download_active_inspections.py

Downloads the PropertyMe Active Inspections custom report as Excel.
Call this AFTER authentication is complete in the main download script.

Usage:
    from download_active_inspections import download_active_inspections_excel
    excel_path = download_active_inspections_excel(page, download_dir="./downloads")
"""

import os
from pathlib import Path
from playwright.sync_api import Page

REPORT_URL = (
    "https://manager.propertyme.com/reporting/#/Properties/"
    "InspectionReport/b44e0053-6f4f-4514-9cc1-617091c3a1f9/false"
)


def download_active_inspections_excel(
    page: Page,
    download_dir: str = "./downloads",
    timeout_ms: int = 30_000,
) -> str:
    """
    Navigate to the Active Inspections custom report and download as Excel.

    Args:
        page:         An authenticated Playwright Page object (already logged in)
        download_dir: Directory to save the downloaded file
        timeout_ms:   Max time to wait for page load and download (ms)

    Returns:
        Absolute path to the downloaded Excel file.
    """
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    print("[active_inspections] Navigating to Active Inspections report...")
    page.goto(REPORT_URL, wait_until="networkidle", timeout=timeout_ms)

    print("[active_inspections] Waiting for Export button...")
    page.wait_for_selector(
        "button:has-text('Export'), a:has-text('Export'), [class*='export']",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(2_000)

    print("[active_inspections] Clicking Export...")
    page.click("button:has-text('Export'), a:has-text('Export')")
    page.wait_for_selector("text=Export Excel", timeout=10_000)

    print("[active_inspections] Selecting 'Export Excel'...")
    save_path = os.path.join(download_dir, "active_inspections.xlsx")
    with page.expect_download(timeout=timeout_ms) as dl_info:
        page.click("text=Export Excel")
    dl_info.value.save_as(save_path)

    print(f"[active_inspections] Saved to: {save_path}")
    return os.path.abspath(save_path)
