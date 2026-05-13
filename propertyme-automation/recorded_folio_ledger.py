import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(storage_state="session.json")
    page = context.new_page()
    page.goto("https://manager.propertyme.com/#/")
    page.locator("[data-test-id=\"reports-menu\"]").click()
    with page.expect_popup() as page1_info:
        page.get_by_role("link", name="Folio Ledger").click()
    page1 = page1_info.value
    with page1.expect_download() as download_info:
        page1.get_by_text("PDF").click()
    download = download_info.value
    page.get_by_role("tab", name="Custom").click()
    with page.expect_popup() as page2_info:
        page.get_by_role("link", name="Monthly Property/Rent").click()
    page2 = page2_info.value
    page2.get_by_role("button", name="Export").click()
    with page2.expect_download() as download1_info:
        page2.get_by_role("link", name="Export Excel").click()
    download1 = download1_info.value

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
