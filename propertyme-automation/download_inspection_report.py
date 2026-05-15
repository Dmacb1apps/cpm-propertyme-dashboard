"""
download_inspection_report.py

Playwright function to download the PropertyMe "Inspections - Properties Due"
report as Excel. Designed to run inside the existing login session — call this
AFTER authentication is complete in the main script.

Usage (add to your existing process_and_push.py or scraper script):

    from download_inspection_report import download_inspections_due_excel
    excel_path = download_inspections_due_excel(page, download_dir="./downloads")
"""

import asyncio
import os
from pathlib import Path
from playwright.async_api import Page, Download


REPORT_URL = (
    "https://manager.propertyme.com/reporting/#/Properties/"
    "PropertyDetailsReport/a8e30508-f824-4993-a50e-1957a2a4d9dd/true"
)


async def download_inspections_due_excel(
    page: Page,
    download_dir: str = "./downloads",
    timeout_ms: int = 30_000,
) -> str:
    """
    Navigate to the Inspections - Properties Due report and download as Excel.

    Args:
        page:         An authenticated Playwright Page object (already logged in)
        download_dir: Directory to save the downloaded file
        timeout_ms:   Max time to wait for page load and download (ms)

    Returns:
        Absolute path to the downloaded Excel file.
    """
    Path(download_dir).mkdir(parents=True, exist_ok=True)

    print("[inspections] Navigating to Properties Due report...")
    await page.goto(REPORT_URL, wait_until="networkidle", timeout=timeout_ms)

    # Wait for the report to finish loading — the export button appears
    # once the data has rendered
    print("[inspections] Waiting for report to load...")
    await page.wait_for_selector(
        "button:has-text('Export'), a:has-text('Export'), [class*='export']",
        timeout=timeout_ms,
    )

    # Small buffer — some Angular/React reports need a moment after
    # the button appears before the underlying data is ready
    await page.wait_for_timeout(2_000)

    print("[inspections] Clicking Export button...")
    await page.click("button:has-text('Export'), a:has-text('Export')")

    # Wait for dropdown to appear
    await page.wait_for_selector(
        "text=Export Excel",
        timeout=10_000,
    )

    print("[inspections] Selecting 'Export Excel'...")
    async with page.expect_download(timeout=timeout_ms) as download_info:
        await page.click("text=Export Excel")

    download: Download = await download_info.value

    # Save with a predictable filename so the parser always finds it
    save_path = os.path.join(download_dir, "inspections_due.xlsx")
    await download.save_as(save_path)

    print(f"[inspections] Saved to: {save_path}")
    return os.path.abspath(save_path)


# ── Standalone test (run this file directly to verify) ────────────────────
async def _test():
    """
    Standalone test. Uses your existing TOTP auth flow.
    Run with:  python3 download_inspection_report.py
    """
    from playwright.async_api import async_playwright
    import importlib.util, sys

    # Try to import your existing auth helper if available
    print("[test] Launching browser...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)  # headless=True in Actions
        context = await browser.new_context(accept_downloads=True)
        page    = await context.new_page()

        # ── Log in manually for this test ──────────────────────────────
        print("[test] Go to PropertyMe and log in, then press Enter here...")
        await page.goto("https://manager.propertyme.com/")
        input("[test] Press Enter once you are logged in...")

        # ── Run the download ───────────────────────────────────────────
        path = await download_inspections_due_excel(page, download_dir="./downloads")
        print(f"[test] Download complete: {path}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(_test())
