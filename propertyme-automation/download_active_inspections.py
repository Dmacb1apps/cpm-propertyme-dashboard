"""
download_active_inspections.py

Downloads the PropertyMe Active Inspections custom report as Excel.
Call this AFTER authentication is complete in the main download script.

Usage:
    from download_active_inspections import download_active_inspections_excel
    excel_path = download_active_inspections_excel(page, download_dir="./downloads")
"""

from pathlib import Path
from playwright.sync_api import Page

REPORT_URL = (
    "https://manager.propertyme.com/reporting/#/Properties/"
    "InspectionReport/b44e0053-6f4f-4514-9cc1-617091c3a1f9/false"
)


def download_active_inspections_excel(
    page: Page,
    download_dir: str = "./downloads",
    timeout_ms: int = 90_000,
) -> str:
    """
    Navigate to the Active Inspections custom report and download as Excel.

    Args:
        page:         An authenticated Playwright Page object (already logged in)
        download_dir: Directory to save the downloaded file
        timeout_ms:   Max time to wait for the download (ms); default 90s for large file

    Returns:
        Path to the downloaded Excel file.
    """
    from pathlib import Path as _Path
    _Path(download_dir).mkdir(parents=True, exist_ok=True)

    print("[active_inspections] Navigating to Active Inspections report...")
    page.goto(REPORT_URL, wait_until="networkidle", timeout=60_000)

    print("[active_inspections] Waiting for report to load...")
    page.wait_for_selector(
        "button:has-text('Export'), a:has-text('Export'), [class*='export']",
        timeout=30_000,
    )
    page.wait_for_timeout(3_000)

    print("[active_inspections] Starting download listener before export clicks...")
    with page.expect_download(timeout=timeout_ms) as dl_info:
        # Click Export to open dropdown
        page.click("button:has-text('Export'), a:has-text('Export')")
        page.wait_for_timeout(1_000)

        # Click Export Excel inside the dropdown
        page.wait_for_selector("text=Export Excel", timeout=10_000)
        page.click("text=Export Excel")

    download = dl_info.value
    save_path = str(_Path(download_dir) / "active_inspections.xlsx")
    download.save_as(save_path)
    print(f"[active_inspections] Saved to: {save_path}")
    return save_path
